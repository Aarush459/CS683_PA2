#!/bin/bash
# Runs baseline and IP-stride on all three traces, all six in parallel.
TRACE_DIR=/work
WARM=25000000
SIM=25000000

for cfg in baseline ip_stride; do
  BIN=$(ls bin/ | grep -- "-${cfg}$")
  mkdir -p results/$cfg
  for t in Trace1 Trace2 Trace3; do
    ./bin/$BIN -warmup_instructions $WARM -simulation_instructions $SIM \
      -traces $TRACE_DIR/$t.gz > results/$cfg/$t.txt 2>&1 &
  done
done
wait
echo "All runs finished"
