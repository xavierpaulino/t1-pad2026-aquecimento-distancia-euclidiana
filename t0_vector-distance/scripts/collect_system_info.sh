#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT="$ROOT/system/system_info.txt"
mkdir -p "$ROOT/system"
{
  echo "# Timestamp (UTC)"
  date -u +'%Y-%m-%dT%H:%M:%SZ'
  echo
  echo "# uname -a"
  uname -a
  echo
  echo "# /etc/os-release"
  cat /etc/os-release 2>/dev/null || true
  echo
  echo "# lscpu"
  lscpu
  echo
  echo "# lscpu -C"
  lscpu -C 2>/dev/null || true
  echo
  echo "# memory"
  free -h
  echo
  echo "# compiler"
  "${CXX:-g++}" --version
  echo
  echo "# Python"
  python3 --version
  echo
  echo "# CPU frequency policy (if exposed by sysfs)"
  for f in /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor; do
    [[ -r "$f" ]] && printf '%s: %s\n' "$f" "$(cat "$f")"
  done
  echo
  echo "# Turbo/boost controls (if exposed)"
  for f in /sys/devices/system/cpu/intel_pstate/no_turbo /sys/devices/system/cpu/cpufreq/boost; do
    [[ -r "$f" ]] && printf '%s: %s\n' "$f" "$(cat "$f")"
  done
  echo
  echo "# allowed CPUs for this shell"
  grep '^Cpus_allowed_list:' /proc/self/status || true
  echo
  echo "# automatic CPU-selection policy result"
  python3 "$ROOT/scripts/cpu_selection.py" --json 2>/dev/null || true
  echo
  echo "# git commit (if repository already initialized)"
  git -C "$ROOT" rev-parse HEAD 2>/dev/null || echo "not a git repository / no commit yet"
} > "$OUT"
echo "Wrote $OUT"
