#!/bin/bash
# Runs Task 2A (irrip), Task 2B (dyn_irrip), and Task 3 (spp + dyn_irrip) across all 3 traces.
TRACE_DIR=${1:-traces}
WARM=25000000
SIM=25000000

echo "=== Running Simulations for Tasks 2A, 2B, and 3 ==="
for cfg in irrip dyn_irrip task3; do
  BIN=$(ls bin/ 2>/dev/null | grep -- "-${cfg}$" | head -n 1)
  if [ -z "$BIN" ]; then
    echo "Warning: Binary for $cfg not found in bin/. Please build it first using build_champsim.sh."
    continue
  fi
  mkdir -p results/$cfg
  for t in Trace1 Trace2 Trace3; do
    TRACE_FILE=""
    for cand in "$TRACE_DIR/$t.gz" "$TRACE_DIR/$t.champsimtrace.gz" "$TRACE_DIR/$t.champsimtrace.xz" "$TRACE_DIR/$t.xz" "$TRACE_DIR/trace${t#Trace}.champsimtrace.gz"; do
      if [ -f "$cand" ]; then
        TRACE_FILE="$cand"
        break
      fi
    done

    if [ -z "$TRACE_FILE" ]; then
      echo "Warning: Could not find trace file for $t in $TRACE_DIR"
      continue
    fi

    echo "Running $cfg on $t using $TRACE_FILE..."
    ./bin/$BIN -warmup_instructions $WARM -simulation_instructions $SIM \
      -traces "$TRACE_FILE" > results/$cfg/$t.txt 2>&1
  done
done
echo "All Task 2 & 3 runs finished!"
