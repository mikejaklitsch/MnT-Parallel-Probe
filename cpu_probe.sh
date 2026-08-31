#!/usr/bin/env bash
# Per-process + total CPU sampler for the EU5 parallelism probe.
# Logs once per second to a CSV on the same wall clock as the game's
# [HH:MM:SS] MONTH_START / MONTH_END markers, so the two line up directly.
#
#   eu5  % Processor Time : 0..1600 on this 16-core box.
#                           ~100  = one core  = serial
#                           >100 toward 1600  = running on N threads at once
#   _Total % Processor Time : whole-machine load (context / background noise)
#
# Usage:  ./cpu_probe.sh [seconds]      (default: runs until Ctrl-C)
# Output: ./cpu_probe.csv  (timestamped, CSV)

OUT="${OUT:-cpu_probe.csv}"
DUR="${1:-0}"     # 0 = until Ctrl-C
SI="${SI:-1}"     # sample interval, seconds

# -sc 0 with DUR=0 means run forever; otherwise sample count = DUR/SI
if [ "$DUR" -gt 0 ]; then SC=$(( DUR / SI )); else SC=0; fi

echo "Sampling eu5.exe CPU every ${SI}s -> ${OUT}  (Ctrl-C to stop)"
typeperf.exe \
  "\\Process(eu5)\\% Processor Time" \
  "\\Processor(_Total)\\% Processor Time" \
  -si "$SI" ${SC:+-sc "$SC"} -f CSV -o "$(wslpath -w "$PWD/$OUT")"
