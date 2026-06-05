#!/usr/bin/env python3
"""
Benchmark de rendimiento de AudioQual (Capa 1: carga determinista).

Mide tiempo, CPU y memoria del pipeline de analisis sobre el conjunto fijo de
archivos de test, de forma reproducible y SIN dependencias externas (solo
stdlib: time, resource, tracemalloc). Pensado para correr cada X dias y detectar
regresiones de rendimiento (p.ej. el STFT roto de f91cb5e: 4x mas lento, +2 GB).

Uso:
    python3 tests/benchmark.py                 # mide y compara contra baseline
    python3 tests/benchmark.py --update-baseline   # fija el run actual como referencia
    python3 tests/benchmark.py --save          # ademas vuelca detalle por-archivo
    python3 tests/benchmark.py --no-history    # no anexa a benchmark_history.jsonl

Salida: codigo 0 = sin regresion; 1 = alguna metrica supero el umbral.

Que se mide (dos pasadas separadas para no contaminar el tiempo):
  - Pasada A (tracemalloc OFF): wall time (perf_counter) y CPU time (getrusage
    user+sys). Tambien ru_maxrss, el RSS pico del proceso (marca de agua alta).
  - Pasada B (tracemalloc ON): pico del heap de Python. Es DETERMINISTA e
    independiente del hardware, asi que es la senal fiable de regresion en CI.

Sobre comparar entre maquinas: tiempo y ru_maxrss dependen del hardware; solo
tienen sentido contra un baseline tomado en la MISMA maquina. Por eso cada run
guarda el campo `machine` y la comparacion avisa si no coincide con el baseline.
"""
import argparse
import json
import os
import platform
import resource
import subprocess
import sys
import time
import tracemalloc
from datetime import datetime

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
TESTS_JSON = os.path.join(TESTS_DIR, "tests.json")
BASELINE_JSON = os.path.join(TESTS_DIR, "benchmark_baseline.json")
HISTORY_JSONL = os.path.join(TESTS_DIR, "benchmark_history.jsonl")

# Umbrales de regresion (fraccion sobre el baseline). Si una metrica los supera,
# el script sale con codigo 1.
THRESHOLDS = {
    "wall_s": 0.10,        # +10% tiempo de pared
    "cpu_s": 0.10,         # +10% tiempo de CPU
    "rss_peak_mb": 0.15,   # +15% RSS pico del proceso
    "heap_peak_mb": 0.15,  # +15% pico del heap de Python (determinista)
}

# Colores ANSI (mismo estilo que run_tests.py)
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
BOLD = "\033[1m"
DIM = "\033[2m"
RESET = "\033[0m"


def load_files():
    """Lista de (rel_path, abs_path) unicos desde tests.json."""
    with open(TESTS_JSON, "r", encoding="utf-8") as f:
        test_cases = json.load(f)
    files = {}
    for tc in test_cases:
        rel = tc["file"]
        abs_path = rel if os.path.isabs(rel) else os.path.join(PROJECT_ROOT, rel)
        if rel not in files and os.path.exists(abs_path):
            files[rel] = abs_path
    return list(files.items())


def maxrss_mb():
    """RSS pico del proceso en MB. ru_maxrss esta en bytes en macOS y en KB en Linux."""
    raw = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    divisor = 1024 * 1024 if sys.platform == "darwin" else 1024
    return raw / divisor


def cpu_seconds():
    """CPU acumulada del proceso (user+sys), incluye threads. En segundos."""
    ru = resource.getrusage(resource.RUSAGE_SELF)
    return ru.ru_utime + ru.ru_stime


def run_pass(files, with_tracemalloc):
    """
    Ejecuta el analizador secuencialmente sobre todos los archivos.

    Devuelve dict con metricas. Replica run_tests.py: libera frequency_analysis
    tras cada archivo para reflejar el flujo real de memoria.
    """
    from src.core.analyzer import AudioAnalyzer

    analyzer = AudioAnalyzer()

    if with_tracemalloc:
        tracemalloc.start()

    cpu_start = cpu_seconds()
    wall_start = time.perf_counter()
    per_file = []

    for rel, abs_path in files:
        t0 = time.perf_counter()
        try:
            result = analyzer.analyze_file(abs_path)
            result.frequency_analysis = None  # liberar (~100-200 MB), ver memory-management.md
            ok = True
        except Exception as e:
            print(f"  {RED}ERROR{RESET} {os.path.basename(abs_path)}: {e}")
            ok = False
        per_file.append({"file": rel, "wall_s": time.perf_counter() - t0, "ok": ok})

    wall = time.perf_counter() - wall_start
    cpu = cpu_seconds() - cpu_start

    metrics = {
        "wall_s": round(wall, 3),
        "cpu_s": round(cpu, 3),
        "rss_peak_mb": round(maxrss_mb(), 1),
    }

    if with_tracemalloc:
        _, heap_peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        metrics["heap_peak_mb"] = round(heap_peak / (1024 * 1024), 1)

    return metrics, per_file


def machine_tag():
    """Identificador de clase de hardware (no hostname). p.ej. 'Darwin-arm64-8c'."""
    return f"{platform.system()}-{platform.machine()}-{os.cpu_count()}c"


def git_sha():
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"], cwd=PROJECT_ROOT,
            stderr=subprocess.DEVNULL,
        ).decode().strip()
    except Exception:
        return "unknown"


def measure(files):
    """Pasada A (tiempo/CPU/RSS, sin tracemalloc) + Pasada B (heap)."""
    print(f"{CYAN}{BOLD}Pasada A — tiempo/CPU/RSS ({len(files)} archivos)...{RESET}")
    metrics_a, per_file = run_pass(files, with_tracemalloc=False)

    print(f"{CYAN}{BOLD}Pasada B — heap de Python (tracemalloc, ~2-3x mas lento)...{RESET}")
    metrics_b, _ = run_pass(files, with_tracemalloc=True)

    metrics = {**metrics_a, "heap_peak_mb": metrics_b["heap_peak_mb"]}
    return {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "git_sha": git_sha(),
        "machine": machine_tag(),
        "python": platform.python_version(),
        "n_files": len(files),
        "metrics": metrics,
        "per_file": per_file,
    }


def fmt(metric, value):
    if metric.endswith("_mb"):
        return f"{value:.1f} MB"
    return f"{value:.2f} s"


def compare(run, baseline):
    """Imprime tabla y devuelve True si hay regresion sobre algun umbral."""
    print(f"\n{BOLD}{'=' * 64}{RESET}")
    print(f"{BOLD}BENCHMARK{RESET}  ({run['git_sha']}, {run['machine']})")
    print(f"{'=' * 64}")

    if baseline is None:
        for m, v in run["metrics"].items():
            print(f"  {m:<14} {fmt(m, v)}")
        print(f"\n{YELLOW}Sin baseline. Crea uno con --update-baseline.{RESET}")
        return False

    if baseline.get("machine") != run["machine"]:
        print(f"{YELLOW}AVISO: baseline tomado en '{baseline.get('machine')}', "
              f"este run en '{run['machine']}'.\n"
              f"  wall/cpu/rss NO son comparables entre maquinas; fiate de heap_peak_mb.{RESET}\n")

    print(f"  {'metrica':<14} {'actual':>12} {'baseline':>12} {'delta':>9}")
    print(f"  {'-' * 49}")
    regressed = False
    for m in THRESHOLDS:
        cur = run["metrics"].get(m)
        base = baseline["metrics"].get(m)
        if cur is None or base is None or base == 0:
            continue
        delta = (cur - base) / base
        over = delta > THRESHOLDS[m]
        color = RED if over else (GREEN if delta <= 0 else "")
        flag = f" {RED}REGRESION{RESET}" if over else ""
        print(f"  {m:<14} {fmt(m, cur):>12} {fmt(m, base):>12} "
              f"{color}{delta:+8.1%}{RESET}{flag}")
        regressed = regressed or over

    print()
    if regressed:
        print(f"{RED}{BOLD}✗ Regresion detectada (umbral superado).{RESET}")
    else:
        print(f"{GREEN}{BOLD}✓ Sin regresion.{RESET}")
    return regressed


def main():
    ap = argparse.ArgumentParser(description="Benchmark de rendimiento de AudioQual")
    ap.add_argument("--update-baseline", action="store_true",
                    help="Fija el run actual como benchmark_baseline.json")
    ap.add_argument("--save", action="store_true",
                    help="Vuelca detalle por-archivo en benchmark_results_<ts>.json")
    ap.add_argument("--no-history", action="store_true",
                    help="No anexa el run a benchmark_history.jsonl")
    args = ap.parse_args()

    files = load_files()
    if not files:
        print(f"{RED}No se encontraron archivos de test (references/test-files/).{RESET}")
        return 2

    run = measure(files)

    baseline = None
    if os.path.exists(BASELINE_JSON):
        with open(BASELINE_JSON, "r", encoding="utf-8") as f:
            baseline = json.load(f)

    regressed = compare(run, baseline)

    # history.jsonl: una linea por run (sin per_file, para mantenerlo ligero)
    if not args.no_history:
        line = {k: v for k, v in run.items() if k != "per_file"}
        with open(HISTORY_JSONL, "a", encoding="utf-8") as f:
            f.write(json.dumps(line, ensure_ascii=False) + "\n")
        print(f"{DIM}→ anexado a {os.path.relpath(HISTORY_JSONL, PROJECT_ROOT)}{RESET}")

    if args.save:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        out = os.path.join(TESTS_DIR, f"benchmark_results_{ts}.json")
        with open(out, "w", encoding="utf-8") as f:
            json.dump(run, f, ensure_ascii=False, indent=2)
        print(f"{DIM}→ detalle por-archivo en {os.path.relpath(out, PROJECT_ROOT)}{RESET}")

    if args.update_baseline:
        baseline_run = {k: v for k, v in run.items() if k != "per_file"}
        with open(BASELINE_JSON, "w", encoding="utf-8") as f:
            json.dump(baseline_run, f, ensure_ascii=False, indent=2)
        print(f"{GREEN}→ baseline actualizado: "
              f"{os.path.relpath(BASELINE_JSON, PROJECT_ROOT)}{RESET}")

    return 1 if regressed else 0


if __name__ == "__main__":
    sys.exit(main())
