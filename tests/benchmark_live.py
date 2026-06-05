#!/usr/bin/env python3
"""
Benchmark en vivo de AudioQual (Capa 2: muestreo de la app abierta con psutil).

La Capa 1 (benchmark.py) mide el pipeline de analisis en lote, de forma
determinista. Lo que NO cubre son los estados interactivos de la GUI con la app
corriendo. Esta Capa 2 los mide: se engancha al proceso vivo y muestrea CPU% y
RSS cada X segundos, atribuido SOLO a ese proceso (no a todo el sistema, al
contrario que `ps`/`powermetrics`).

Requiere psutil (dependencia de dev):  pip install -r requirements-dev.txt

Uso tipico (la app en una terminal, esto en otra):
    python3 src/main.py
    python3 tests/benchmark_live.py --state reposo
    python3 tests/benchmark_live.py --state analizando --seconds 20

Estados recomendados (ver --list para el guion de montaje de cada uno):
    reposo            app abierta, sin archivos, sin tocar nada
    tabla-llena       tabla cargada (p.ej. 300 archivos), nada en marcha
    analizando        durante un lote de analisis
    watcher           watcher activo sobre una carpeta, sin archivos nuevos

A diferencia de la Capa 1, esto NO falla con codigo 1: los estados en vivo son
demasiado ruidosos para umbrales automaticos. Mide, imprime stats y anexa al
historial por estado para ver la deriva a lo largo del tiempo.
"""
import argparse
import json
import os
import statistics
import sys
import time
from datetime import datetime

import psutil

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from benchmark import git_sha, machine_tag  # reutiliza helpers de la Capa 1

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
LIVE_HISTORY = os.path.join(TESTS_DIR, "benchmark_live_history.jsonl")

# Colores ANSI (mismo estilo que el resto de tests)
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
BOLD = "\033[1m"
DIM = "\033[2m"
RESET = "\033[0m"

STATES = {
    "reposo": "App abierta, sin archivos cargados, sin tocar nada. Espera ~5s tras abrir.",
    "tabla-llena": "Carga un lote (p.ej. 300 archivos) y deja que TERMINE de analizar. "
                   "Mide con la tabla llena y nada en marcha.",
    "analizando": "Lanza un lote y muestrea DURANTE el analisis (sube --seconds si el "
                  "lote es corto). Veras CPU% > 100% (varios cores).",
    "watcher": "Activa el watcher sobre una carpeta y NO metas archivos nuevos. "
               "Mide el coste del sondeo en reposo.",
}


def find_app_pid():
    """PIDs del interprete Python que ejecuta src/main.py. Devuelve lista (idealmente 1).

    Exige name=python para descartar el wrapper de shell, cuyo cmdline tambien
    contiene 'src/main.py' al haber lanzado la app (falso positivo).
    """
    pids = []
    for p in psutil.process_iter(["pid", "name", "cmdline"]):
        try:
            name = (p.info["name"] or "").lower()
            cmd = " ".join(p.info["cmdline"] or [])
        except (psutil.NoSuchProcess, psutil.AccessDenied, TypeError):
            continue
        if "python" not in name:
            continue
        if os.path.join("src", "main.py") in cmd or "audioqual" in cmd.lower():
            pids.append(p.info["pid"])
    return pids


def sample(pid, seconds, interval, state):
    """Muestrea CPU% y RSS del proceso durante `seconds`. Devuelve dict de metricas."""
    proc = psutil.Process(pid)
    cores = os.cpu_count() or 1

    print(f"{CYAN}{BOLD}Muestreando PID {pid} — estado '{state}' "
          f"({seconds}s cada {interval}s)...{RESET}")
    proc.cpu_percent(interval=None)  # primer cebado: la 1a lectura siempre es 0.0

    n = max(1, int(round(seconds / interval)))
    cpu_samples, rss_samples = [], []
    try:
        for i in range(n):
            cpu = proc.cpu_percent(interval=interval)  # bloquea `interval` s
            rss = proc.memory_info().rss / (1024 * 1024)
            cpu_samples.append(cpu)
            rss_samples.append(rss)
            print(f"\r  [{i + 1}/{n}] cpu {cpu:6.1f}%   rss {rss:7.1f} MB   ",
                  end="", flush=True)
    except psutil.NoSuchProcess:
        print(f"\n{RED}El proceso {pid} desaparecio durante el muestreo.{RESET}")
        sys.exit(1)
    print()

    return {
        "cpu_mean_pct": round(statistics.mean(cpu_samples), 1),
        "cpu_median_pct": round(statistics.median(cpu_samples), 1),
        "cpu_peak_pct": round(max(cpu_samples), 1),
        "rss_mean_mb": round(statistics.mean(rss_samples), 1),
        "rss_peak_mb": round(max(rss_samples), 1),
        "cores": cores,
        "n_samples": n,
    }


def previous_run(state, machine):
    """Ultimo run del mismo estado y maquina en el historial, o None."""
    if not os.path.exists(LIVE_HISTORY):
        return None
    last = None
    with open(LIVE_HISTORY, "r", encoding="utf-8") as f:
        for line in f:
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            if rec.get("state") == state and rec.get("machine") == machine:
                last = rec
    return last


def report(metrics, state, prev):
    print(f"\n{BOLD}{'=' * 56}{RESET}")
    print(f"{BOLD}EN VIVO{RESET}  estado '{state}'  ({metrics['cores']} cores)")
    print(f"{'=' * 56}")
    print(f"  CPU%   media {metrics['cpu_mean_pct']:>6}   "
          f"mediana {metrics['cpu_median_pct']:>6}   pico {metrics['cpu_peak_pct']:>6}")
    print(f"  RSS MB media {metrics['rss_mean_mb']:>6}   "
          f"pico {metrics['rss_peak_mb']:>6}")
    if metrics["cpu_peak_pct"] > 100:
        print(f"  {DIM}(CPU% > 100% es normal: usa varios cores, "
              f"100% = 1 core){RESET}")

    if prev:
        pm = prev["metrics"]
        print(f"\n  {DIM}vs run anterior ({prev['timestamp'][:16]}):{RESET}")
        for key, label in [("cpu_median_pct", "CPU% mediana"), ("rss_mean_mb", "RSS media")]:
            cur, old = metrics[key], pm.get(key)
            if old:
                d = (cur - old) / old
                color = "" if abs(d) < 0.1 else (YELLOW if d > 0 else GREEN)
                print(f"    {label:<14} {old:>7} → {cur:>7}  {color}{d:+.0%}{RESET}")


def main():
    ap = argparse.ArgumentParser(description="Benchmark en vivo de AudioQual (Capa 2)")
    ap.add_argument("--state", help="Etiqueta del estado medido (ver --list)")
    ap.add_argument("--seconds", type=float, default=30, help="Duracion del muestreo (def. 30)")
    ap.add_argument("--interval", type=float, default=0.5, help="Periodo de muestreo (def. 0.5)")
    ap.add_argument("--pid", type=int, help="PID explicito (si la autodeteccion falla)")
    ap.add_argument("--no-history", action="store_true", help="No anexa a benchmark_live_history.jsonl")
    ap.add_argument("--list", action="store_true", help="Lista los estados recomendados y su montaje")
    args = ap.parse_args()

    if args.list:
        print(f"{BOLD}Estados recomendados (mide los MISMOS antes/despues de un cambio):{RESET}\n")
        for name, how in STATES.items():
            print(f"  {CYAN}{name}{RESET}\n    {how}\n")
        return 0

    if not args.state:
        print(f"{RED}Falta --state. Usa --list para ver los recomendados.{RESET}")
        return 2

    pid = args.pid
    if pid is None:
        pids = find_app_pid()
        if not pids:
            print(f"{RED}No encuentro la app (src/main.py). Abrela con "
                  f"'python3 src/main.py' o pasa --pid.{RESET}")
            return 2
        if len(pids) > 1:
            print(f"{RED}Varios candidatos {pids}. Desambigua con --pid.{RESET}")
            return 2
        pid = pids[0]

    machine = machine_tag()
    metrics = sample(pid, args.seconds, args.interval, args.state)
    prev = previous_run(args.state, machine)
    report(metrics, args.state, prev)

    if not args.no_history:
        rec = {
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "git_sha": git_sha(),
            "machine": machine,
            "state": args.state,
            "metrics": metrics,
        }
        with open(LIVE_HISTORY, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        print(f"\n{DIM}→ anexado a {os.path.relpath(LIVE_HISTORY, PROJECT_ROOT)}{RESET}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
