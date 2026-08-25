#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

CONFIG_FILE="${CONFIG_FILE:-$ROOT/config/experiment.conf}"
RAW="$ROOT/data/raw_measurements.csv"
T_VALUES=(32 64 128 256 512 1024 2048 4096)

if [[ ! -x "$ROOT/build/vector_distance" ]]; then
  echo "Building release executable..."
  make release
fi
make test >/dev/null

if [[ ! -f "$CONFIG_FILE" ]]; then
  echo "No frozen experiment configuration found. Running calibration first."
  python3 scripts/calibrate_n.py
fi
# shellcheck disable=SC1090
source "$CONFIG_FILE"
: "${N:?N missing from config}"
: "${SEED:?SEED missing from config}"
: "${REPETITIONS:?REPETITIONS missing from config}"
: "${WARMUP:?WARMUP missing from config}"
BATCHES="${BATCHES:-5}"

if (( REPETITIONS % BATCHES != 0 )); then
  echo "ERROR: REPETITIONS=$REPETITIONS must be divisible by BATCHES=$BATCHES" >&2
  exit 2
fi
PER_BATCH=$((REPETITIONS / BATCHES))

if [[ -z "${CPU:-}" ]]; then
  echo "ERROR: CPU missing from frozen configuration. Re-run scripts/calibrate_n.py." >&2
  exit 2
fi
if ! taskset -c "$CPU" true 2>/dev/null; then
  echo "ERROR: frozen CPU=$CPU is no longer allowed/online in this execution context." >&2
  echo "Re-run calibration before starting a new official campaign." >&2
  exit 2
fi

scripts/collect_system_info.sh
{
  echo "N=$N"
  echo "SEED=$SEED"
  echo "REPETITIONS_PER_T=$REPETITIONS"
  echo "BATCHES=$BATCHES"
  echo "REPETITIONS_PER_BATCH=$PER_BATCH"
  echo "WARMUP_PER_T_PER_BATCH=$WARMUP"
  echo "CPU=$CPU"
  echo "T_VALUES=${T_VALUES[*]}"
  echo "ORDER=randomized_blocks_deterministic"
  echo "ORDER_SEED_BASE=$SEED"
  echo "CXX=${CXX:-g++}"
  echo "RELEASE_FLAGS=${RELEASE_FLAGS:--O3 -march=native}"
} > system/experiment_parameters.txt

rm -f "$RAW"
for (( batch=1; batch<=BATCHES; batch++ )); do
  mapfile -t ORDER < <(python3 - "$SEED" "$batch" "${T_VALUES[@]}" <<'PY'
import random, sys
seed = int(sys.argv[1])
batch = int(sys.argv[2])
values = [int(x) for x in sys.argv[3:]]
rng = random.Random(seed + batch)
rng.shuffle(values)
print(*values, sep='\n')
PY
  )
  echo "Batch $batch/$BATCHES order: ${ORDER[*]}"
  offset=$(((batch - 1) * PER_BATCH))
  pos=0
  for T in "${ORDER[@]}"; do
    pos=$((pos + 1))
    echo "  T=$T, N=$N, CPU=$CPU, reps=$PER_BATCH"
    taskset -c "$CPU" "$ROOT/build/vector_distance" \
      --n "$N" --t "$T" \
      --repetitions "$PER_BATCH" --warmup "$WARMUP" \
      --seed "$SEED" --batch "$batch" --order-position "$pos" \
      --repetition-offset "$offset" \
      --csv "$RAW" --append --quiet
  done
done

echo "Raw measurements: $RAW"
echo "Now run: python3 scripts/analyze_results.py && python3 scripts/plot_results.py"
