#!/bin/bash
# Mide CPU media e hilos del proceso de la app durante N segundos.
# Uso: bash scripts/measure_cpu.sh [segundos]   (por defecto 30)
# Lanza la app aparte (python3 src/main.py) y déjala en el estado a medir
# (reposo o monitorizando) antes de ejecutar este script.

DUR=${1:-30}
PID=$(pgrep -f "src/main.py")

if [ -z "$PID" ]; then
  echo "No encuentro la app. Lánzala con: python3 src/main.py"
  exit 1
fi

echo "PID $PID — muestreando ${DUR}s (cada 2s)..."
N=$((DUR / 2))
CPU0=$(ps -p "$PID" -o %cpu=)
THREADS=$(ps -M -p "$PID" 2>/dev/null | tail -n +2 | grep -c .)
echo "  inicio: ${CPU0}% CPU, ${THREADS} hilos"

for i in $(seq 1 "$N"); do
  ps -p "$PID" -o %cpu= 2>/dev/null
  sleep 2
done | awk '{s+=$1; n++} END {if(n)printf "\nCPU media: %.1f%%  (%d muestras)\n",s/n,n; else print "proceso terminado"}'
