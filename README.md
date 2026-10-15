# CS683: Advanced Computer Architecture — Programming Assignment 2

**Course:** CS683 Autumn 2026, IIT Bombay  
**Simulator:** [ChampSim](https://github.com/ChampSim/ChampSim)  
**Simulation Budget:** Warmup: 25M instructions, Detailed Simulation: 25M instructions  

---

## 1. Project Overview & Team Structure

This repository contains the complete implementation, evaluation scripts, and experimental deliverables for **CS683 PA2**, focusing on high-performance data prefetching and cache replacement policies for server and desktop workloads.

The project is structured into three primary tasks:
- **Task 1: Stride Pattern Data Prefetching (L1D)**
  - **Task 1A:** Understanding and evaluating the IP-Stride prefetcher (`prefetcher/ip_stride.l1d_pref`).
  - **Task 1B:** Designing and implementing the Stride Pattern Prefetcher (SPP) (`prefetcher/spp.l1d_pref`) to track repeating non-uniform delta patterns within 4KB physical pages.
- **Task 2: Instruction-Conscious L2 Cache Replacement (L2C)**
  - **Task 2A (I-RRIP):** Extending ChampSim core replacement signature (`update_replacement_state`) with instruction awareness, prioritizing instruction lines over data lines (`replacement/irrip.l2c_repl`).
  - **Task 2B (Dynamic I-RRIP):** Implementing a Set-Dueling mechanism with 32 dedicated leader sets to dynamically throttle instruction prioritization during data-intensive workload phases (`replacement/dyn_irrip.l2c_repl`).
- **Task 3: Cross-Layer Co-Design (SPP Prefetcher + Dynamic I-RRIP)**
  - Synergistic integration of SPP with Dynamic I-RRIP. Incorporates prefetch awareness (`packet.type == PREFETCH`), inserting speculative prefetches with low cache priority ($RRPV=3$) to prevent cache pollution while aggressively protecting high-utility demand instructions.

---

## 2. Directory Structure

```text
.
├── Makefile                      # Cross-platform Makefile (Linux -static and macOS Darwin support)
├── README.md                     # Comprehensive project documentation
├── Summary.pdf                   # Final 3-page technical report with full tables, rationales, and plots
├── build_champsim.sh             # ChampSim compilation script
├── parse_results.py              # Automated result parser, table generator, and plotting engine
├── run_task1a.sh                 # Simulation runner for Task 1A & 1B
├── run_task2_task3.sh            # Simulation runner for Tasks 2A, 2B, and 3
├── branch/                       # Branch predictor models (hashed_perceptron default)
├── inc/
│   ├── cache.h                   # Core cache interface extended with uint8_t isInstruction
│   └── ...
├── prefetcher/
│   ├── ip_stride.l1d_pref        # Task 1A: IP-Stride prefetcher
│   ├── spp.l1d_pref              # Task 1B: Stride Pattern Prefetcher (SPP)
│   └── ...
├── replacement/
│   ├── irrip.l2c_repl            # Task 2A: Instruction-Conscious RRIP
│   ├── dyn_irrip.l2c_repl        # Task 2B & 3: Dynamic I-RRIP with Set-Dueling & Prefetch Awareness
│   └── ...
├── results/                      # Merged simulation outputs across all tasks (25M/25M)
│   ├── baseline/                 # Baseline (no prefetcher, LRU replacement)
│   ├── ip_stride/                # Task 1A results
│   ├── spp/                      # Task 1B results
│   ├── irrip/                    # Task 2A results
│   ├── dyn_irrip/                # Task 2B results
│   ├── task3/                    # Task 3 results (SPP + Dyn-IRRIP)
│   ├── plots_baseline_ip_stride_spp_irrip_dyn_irrip_task3/  # Full unified plots
│   └── summary_baseline_ip_stride_spp_irrip_dyn_irrip_task3.csv
└── src/
    ├── cache.cc                  # Cache implementation updated to pass packet.instruction
    └── ooo_cpu.cc                # Out-of-order CPU core patched for BTB replacement calls
```

---

## 3. Microarchitectural Implementation Details

### Task 2A: Instruction-Conscious L2 Replacement Policy (I-RRIP)
- **Signature Extension (`inc/cache.h`, `src/cache.cc`, `src/ooo_cpu.cc`):**
  The `update_replacement_state` pointer signature and all 9 replacement levels were extended to take `uint8_t isInstruction`.
  Call sites in `src/cache.cc` pass `packet.instruction` for demand/writeback/prefetch hits and misses.
- **Replacement State (`replacement/irrip.l2c_repl`):**
  - Maintains 2-bit RRPV per line ($0 \le \text{RRPV} \le 3$).
  - **Insertion:** Instruction misses are inserted at $RRPV=0$ (MRU) to aggressively retain code footprint; Data misses are inserted at distant $RRPV=2$.
  - **Promotion:** Any cache hit promotes the line to $RRPV=0$.
  - **Victim Selection:** First scans for candidate lines at $maxRRPV=3$. If both data and instruction lines have $RRPV=3$, data lines are strictly prioritized for eviction over instruction lines. If no line has $RRPV=3$, all RRPVs in the set are incremented until a victim is identified.

### Task 2B: Dynamic I-RRIP with Set-Dueling
- **Set-Dueling Mechanism (`replacement/dyn_irrip.l2c_repl`):**
  - Out of 1024 L2 sets, **32 sets** (every 32nd set: $0, 32, 64, \dots, 992$) are designated as dedicated **leader sets** running baseline RRIP.
  - The leader sets track instruction accesses/misses vs total accesses/misses:
    $$\text{ratio} = \frac{\text{instr\_hits} + \text{instr\_misses}}{\text{total\_hits} + \text{total\_misses}}$$
  - **Follower Sets:** If $\text{ratio} > \theta$ ($\theta=0.25$ by default), follower sets operate in I-RRIP mode. Otherwise, they operate in baseline RRIP mode to shield data lines from cache thrashing.

### Task 3: Incorporating SPP with Dynamic I-RRIP
- **Prefetch Pollution Mitigation:**
  Prefetches issued by SPP are inherently speculative. If inserted with high priority, mispredicted prefetches displace vital instruction and demand data lines.
- **Prefetch-Aware Handling:**
  - In `replacement/dyn_irrip.l2c_repl`, prefetch packets are detected via `(type == PREFETCH)`.
  - **Speculative Insertion:** Prefetch lines are inserted with distant priority ($RRPV = 3$). If the line is never referenced, it is evicted immediately without displacing useful lines.
  - **Demand Hit Promotion:** If a prefetched block receives a demand hit (useful prefetch), it is promoted to MRU ($RRPV = 0$).
  - **Eviction Hierarchy:** `Unused Prefetches` $\rightarrow$ `Data Demand` $\rightarrow$ `Instruction Lines`.

---

## 4. How to Compile ChampSim

To compile any configuration, use `./build_champsim.sh <L1D_PREFETCHER> <L2C_REPLACEMENT> <BINARY_NAME>`:

```bash
# Baseline (No prefetcher, LRU L2 replacement)
./build_champsim.sh no lru baseline

# Task 1A: IP Stride Prefetcher + LRU
./build_champsim.sh ip_stride lru ip_stride

# Task 1B: Stride Pattern Prefetcher (SPP) + LRU
./build_champsim.sh spp lru spp

# Task 2A: Instruction-Conscious RRIP (I-RRIP)
./build_champsim.sh no irrip irrip

# Task 2B: Dynamic I-RRIP (Set-Dueling)
./build_champsim.sh no dyn_irrip dyn_irrip

# Task 3: SPP Prefetcher + Dynamic I-RRIP
./build_champsim.sh spp dyn_irrip task3
```

Generated binaries are stored in `bin/`.

---

## 5. How to Run Simulations

### Prerequisites: Traces
ChampSim traces should be placed in `traces/` or `/work/` (supporting `.gz` or `.xz` compressed traces):
- `Trace1.gz` / `trace1.champsimtrace.gz`
- `Trace2.gz` / `trace2.champsimtrace.gz`
- `Trace3.gz` / `trace3.champsimtrace.gz`

### Running Single Simulations
```bash
./bin/[BINARY_NAME] \
  -warmup_instructions 25000000 \
  -simulation_instructions 25000000 \
  -traces traces/Trace1.gz > results/[CONFIG]/Trace1.txt 2>&1
```

### Automated Batch Runners
- Run Task 1A & 1B:
  ```bash
  ./run_task1a.sh
  ```
- Run Tasks 2A, 2B, and 3:
  ```bash
  ./run_task2_task3.sh [path_to_traces]
  ```

---

## 6. Parsing Results & Generating Deliverables

The repository provides a unified analysis tool `parse_results.py` that extracts metrics, generates markdown/CSV tables, and produces publication-quality bar plots:

```bash
# Parse Task 1 results:
python3 parse_results.py results baseline ip_stride spp

# Parse Tasks 2A, 2B, and Task 3 results:
python3 parse_results.py results baseline irrip dyn_irrip task3

# Parse ALL tasks simultaneously (unified comparison):
python3 parse_results.py results baseline ip_stride spp irrip dyn_irrip task3
```

Outputs:
- CSV Table: `results/summary_baseline_ip_stride_spp_irrip_dyn_irrip_task3.csv`
- Generated Plots:
  - `speedup.png` (Speedup over baseline)
  - `l1d_load_mpki.png` (L1D Load MPKI comparison)
  - `l2c_load_mpki.png` (L2C Total Load MPKI)
  - `l2c_instr_load_mpki.png` (L2C Instruction Load MPKI)
  - `accuracy.png` (Prefetch accuracy percentage)
  - `coverage.png` (Prefetch coverage percentage)

---

## 7. Performance Evaluation Summary (25M Warmup / 25M Simulation)

The table below summarizes the official simulation results across all configurations and traces:

| Trace | Configuration | IPC | Speedup | L1D Load MPKI | L2C Load MPKI | L2C Instr MPKI | Prefetch Accuracy | Coverage |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **Trace 1** | Baseline | 0.2322 | 1.0000x | 10.678 | 17.709 | 10.370 | - | - |
| | IP-stride | 0.2333 | 1.0046x | 10.117 | 17.709 | 10.370 | 53.0% | 5.3% |
| | SPP | 0.2339 | 1.0074x | 9.786 | 17.654 | 10.370 | 52.1% | 8.4% |
| | I-RRIP (Task 2A) | 0.2317 | 0.9977x | 10.679 | 17.720 | **9.804** ($\downarrow 0.57$) | - | - |
| | Dyn-IRRIP (Task 2B) | 0.2317 | 0.9977x | 10.680 | 17.758 | **9.828** ($\downarrow 0.54$) | - | - |
| | **Task 3 (SPP + Dyn-IRRIP)** | **0.2333** | **1.0047x** | **9.787** | **16.899** ($\downarrow 0.81$) | **9.828** | **51.9%** | **8.3%** |
| **Trace 2** | Baseline | 0.2506 | 1.0000x | 13.539 | 28.315 | 19.881 | - | - |
| | IP-stride | 0.2506 | 1.0001x | 13.442 | 28.315 | 19.881 | 38.0% | 0.7% |
| | SPP | 0.2510 | 1.0013x | 13.377 | 28.290 | 19.881 | 34.3% | 1.2% |
| | I-RRIP (Task 2A) | 0.2548 | 1.0167x | 13.543 | 23.756 | **14.777** ($\downarrow 5.10$) | - | - |
| | Dyn-IRRIP (Task 2B) | 0.2547 | 1.0164x | 13.543 | 23.800 | **14.858** ($\downarrow 5.02$) | - | - |
| | **Task 3 (SPP + Dyn-IRRIP)** | **0.2552** | **1.0181x** | **13.381** | **23.740** ($\downarrow 4.58$) | **14.858** | **34.3%** | **1.2%** |
| **Trace 3** | Baseline | 0.3819 | 1.0000x | 3.403 | 3.963 | 1.126 | - | - |
| | IP-stride | 0.3827 | 1.0023x | 3.318 | 3.963 | 1.126 | 16.1% | 2.5% |
| | SPP | 0.3861 | 1.0111x | 3.090 | 3.950 | 1.126 | 29.4% | 9.2% |
| | I-RRIP (Task 2A) | 0.3820 | 1.0004x | 3.403 | 3.836 | **0.959** ($\downarrow 0.17$) | - | - |
| | Dyn-IRRIP (Task 2B) | 0.3820 | 1.0003x | 3.403 | 3.837 | **0.965** ($\downarrow 0.16$) | - | - |
| | **Task 3 (SPP + Dyn-IRRIP)** | **0.3863** | **1.0116x** | **3.091** | **3.820** ($\downarrow 0.14$) | **0.965** | **29.2%** | **9.2%** |

### Key Takeaways
1. **Task 2A (I-RRIP):** Successfully achieves the primary design goal — reducing L2C instruction MPKI across all three traces, with an exceptional **5.10 MPKI reduction** on Trace 2.
2. **Task 2B (Dynamic I-RRIP):** Effectively balances code vs data pressure via Set-Dueling, matching I-RRIP's instruction gains while protecting data lines.
3. **Task 3 (SPP + Dyn-IRRIP Milestone):** By mitigating prefetch-induced cache pollution, **Task 3 outperforms BOTH standalone SPP and Dyn-IRRIP alone in IPC** on Trace 2 (0.2552 vs 0.2510 SPP and 0.2547 Dyn-IRRIP) and Trace 3 (0.3863 vs 0.3861 SPP and 0.3820 Dyn-IRRIP).

---

## 8. Summary Report
For comprehensive theoretical rationales, storage overhead breakdowns, sensitivity curves, and complete figures, please refer to:
- [`Summary.pdf`](Summary.pdf)
