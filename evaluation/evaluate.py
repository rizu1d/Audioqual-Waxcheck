#!/usr/bin/env python3
"""
Evalua las variantes generadas usando AudioAnalyzer y produce un CSV de resultados.

Uso:
    python evaluation/evaluate.py [--summary]

Opciones:
    --summary    Solo mostrar resumen final
"""
import argparse
import csv
import json
import os
import sys
import time

# Setup path para importar el proyecto
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from src.core.analyzer import AudioAnalyzer
from src.utils.constants import STATUS_LOSSLESS

# Colores ANSI
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
BOLD = "\033[1m"
DIM = "\033[2m"
RESET = "\033[0m"

EVAL_DIR = os.path.dirname(os.path.abspath(__file__))
DATASET_DIR = os.path.join(EVAL_DIR, "dataset")
MANIFEST_PATH = os.path.join(DATASET_DIR, "manifest.json")
CSV_PATH = os.path.join(EVAL_DIR, "results.csv")

CSV_COLUMNS = [
    "filename", "source", "type", "bitrate_original", "bitrate_declared",
    "expected_cutoff_min_khz", "expected_cutoff_max_khz",
    "detected_cutoff_khz", "cutoff_in_range",
    "expected_status", "detected_status", "status_match",
    "expected_quality", "detected_quality", "quality_match",
    "expected_level", "detected_level", "level_match",
    "confidence", "match",
]


def classify_quality_level(cutoff_khz, status):
    """Clasifica el nivel de calidad basado en cutoff y status.

    A diferencia de get_quality_level() en constants.py que solo tiene
    bajo/bueno/excelente, esta version incluye el nivel 'medio'.
    """
    if status == STATUS_LOSSLESS:
        return "lossless"
    if cutoff_khz >= 18.5:
        return "bueno"
    if cutoff_khz >= 17.0:
        return "medio"
    return "bajo"


def evaluate_status_match(variant_type, expected_status, detected_status):
    """Evalua si el status detectado es aceptable.

    Returns:
        True si el status es correcto o aceptable
    """
    if detected_status == expected_status:
        return True

    # "Incierto" es aceptable para legitimos (conservador, no es error)
    if variant_type == "legit" and detected_status == "Incierto":
        return True

    # legit 192k puede ser "OK" o "Baja calidad"
    if variant_type == "legit" and expected_status in ("OK", "Baja calidad"):
        if detected_status in ("OK", "Baja calidad", "Incierto"):
            return True

    return False


def evaluate_level_match(variant_type, expected_level, detected_level, variant_entry):
    """Evalua si el nivel de calidad detectado es aceptable.

    Se acepta el nivel exacto o +-1 adyacente.
    """
    if detected_level == expected_level:
        return True

    # Definir adyacencia
    level_order = ["bajo", "medio", "bueno", "lossless"]
    try:
        expected_idx = level_order.index(expected_level)
        detected_idx = level_order.index(detected_level)
    except ValueError:
        return False

    # Aceptar +-1 nivel adyacente
    return abs(expected_idx - detected_idx) <= 1


def evaluate_match(variant_entry, result):
    """Evalua si el resultado del analisis coincide con lo esperado.

    Returns:
        dict con todos los campos de evaluacion
    """
    detected_cutoff = result.cutoff_frequency_khz
    detected_status = result.status
    detected_quality = result.detected_quality
    confidence = result.confidence

    expected_range = variant_entry["expected_cutoff_range_khz"]
    expected_status = variant_entry["expected_status"]
    expected_quality = variant_entry["expected_quality"]
    expected_level = variant_entry["expected_level"]
    variant_type = variant_entry["type"]

    detected_level = classify_quality_level(detected_cutoff, detected_status)

    cutoff_in_range = expected_range[0] <= detected_cutoff <= expected_range[1]
    status_ok = evaluate_status_match(variant_type, expected_status, detected_status)
    quality_ok = detected_quality == expected_quality
    level_ok = evaluate_level_match(variant_type, expected_level, detected_level, variant_entry)

    # Match global = status correcto AND nivel correcto
    overall_match = status_ok and level_ok

    return {
        "filename": variant_entry["filename"],
        "source": variant_entry["source"],
        "type": variant_type,
        "bitrate_original": variant_entry["bitrate_original"] or "",
        "bitrate_declared": variant_entry["bitrate_declared"],
        "expected_cutoff_min_khz": expected_range[0],
        "expected_cutoff_max_khz": expected_range[1],
        "detected_cutoff_khz": round(detected_cutoff, 2),
        "cutoff_in_range": cutoff_in_range,
        "expected_status": expected_status,
        "detected_status": detected_status,
        "status_match": status_ok,
        "expected_quality": expected_quality,
        "detected_quality": detected_quality,
        "quality_match": quality_ok,
        "expected_level": expected_level,
        "detected_level": detected_level,
        "level_match": level_ok,
        "confidence": round(confidence, 3),
        "match": overall_match,
    }


def main():
    parser = argparse.ArgumentParser(description="Evalua variantes de audio")
    parser.add_argument("--summary", action="store_true", help="Solo mostrar resumen")
    args = parser.parse_args()

    print(f"\n{BOLD}{'=' * 60}{RESET}")
    print(f"{BOLD}  AudioQual — Evaluacion de Dataset{RESET}")
    print(f"{'=' * 60}\n")

    # Cargar manifest
    if not os.path.exists(MANIFEST_PATH):
        print(f"{RED}Error: No se encontro {MANIFEST_PATH}{RESET}")
        print(f"Ejecuta primero: python evaluation/generate_dataset.py")
        sys.exit(1)

    with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    entries = manifest["files"]
    total = len(entries)
    print(f"Variantes a evaluar: {CYAN}{total}{RESET}")

    # Analizar
    analyzer = AudioAnalyzer()
    results = []

    start_time = time.time()

    for i, entry in enumerate(entries, 1):
        filepath = os.path.join(DATASET_DIR, entry["filename"])
        label = entry["filename"]

        if not args.summary:
            print(f"  [{i}/{total}] {label}...", end="", flush=True)

        if not os.path.exists(filepath):
            if not args.summary:
                print(f" {RED}NO ENCONTRADO{RESET}")
            continue

        try:
            result = analyzer.analyze_file(filepath)
            result.frequency_analysis = None  # Liberar ~4MB

            evaluation = evaluate_match(entry, result)
            results.append(evaluation)

            if not args.summary:
                match = evaluation["match"]
                icon = f"{GREEN}OK{RESET}" if match else f"{RED}FAIL{RESET}"
                cutoff = evaluation["detected_cutoff_khz"]
                status = evaluation["detected_status"]
                print(f" {icon}  cutoff={cutoff:.1f}kHz  status={status}")

                if not match:
                    details = []
                    if not evaluation["status_match"]:
                        details.append(
                            f"status: esperado={evaluation['expected_status']}, "
                            f"detectado={evaluation['detected_status']}"
                        )
                    if not evaluation["level_match"]:
                        details.append(
                            f"nivel: esperado={evaluation['expected_level']}, "
                            f"detectado={evaluation['detected_level']}"
                        )
                    for d in details:
                        print(f"         {DIM}{d}{RESET}")

        except Exception as e:
            if not args.summary:
                print(f" {RED}ERROR: {e}{RESET}")

    elapsed = time.time() - start_time

    # Escribir CSV
    with open(CSV_PATH, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        writer.writerows(results)

    # Resumen
    total_evaluated = len(results)
    matches = sum(1 for r in results if r["match"])
    failures = total_evaluated - matches
    precision = (matches / total_evaluated * 100) if total_evaluated > 0 else 0

    # Desglose por tipo
    types = {}
    for r in results:
        t = r["type"]
        if t not in types:
            types[t] = {"total": 0, "matches": 0}
        types[t]["total"] += 1
        if r["match"]:
            types[t]["matches"] += 1

    # Desglose por nivel
    levels = {}
    for r in results:
        lvl = r["expected_level"]
        if lvl not in levels:
            levels[lvl] = {"total": 0, "matches": 0}
        levels[lvl]["total"] += 1
        if r["match"]:
            levels[lvl]["matches"] += 1

    # Falsos positivos y negativos
    false_positives = sum(
        1 for r in results
        if r["type"] == "legit" and r["detected_status"] == "Transcode detectado"
    )
    false_negatives = sum(
        1 for r in results
        if r["type"] in ("transcode", "youtube")
        and r["detected_status"] != "Transcode detectado"
    )

    print(f"\n{'=' * 60}")
    print(f"{BOLD}Resumen{RESET}")
    print(f"{'=' * 60}")
    print(f"  Evaluados:  {total_evaluated}")
    print(f"  {GREEN}Aciertos:  {matches}{RESET}")
    if failures:
        print(f"  {RED}Fallos:    {failures}{RESET}")
    else:
        print(f"  Fallos:    {failures}")
    print(f"  Precision: {BOLD}{precision:.1f}%{RESET}")
    print(f"  Tiempo:    {elapsed:.1f}s")

    if false_positives:
        print(f"\n  {RED}Falsos positivos (legitimo -> transcode): {false_positives}{RESET}")
    if false_negatives:
        print(f"  {RED}Falsos negativos (transcode no detectado): {false_negatives}{RESET}")

    print(f"\n  {BOLD}Por tipo:{RESET}")
    for t, data in sorted(types.items()):
        pct = data["matches"] / data["total"] * 100 if data["total"] else 0
        color = GREEN if pct == 100 else (YELLOW if pct >= 80 else RED)
        print(f"    {t:20s}  {color}{data['matches']}/{data['total']} ({pct:.0f}%){RESET}")

    print(f"\n  {BOLD}Por nivel esperado:{RESET}")
    for lvl, data in sorted(levels.items()):
        pct = data["matches"] / data["total"] * 100 if data["total"] else 0
        color = GREEN if pct == 100 else (YELLOW if pct >= 80 else RED)
        print(f"    {lvl:20s}  {color}{data['matches']}/{data['total']} ({pct:.0f}%){RESET}")

    print(f"\n  CSV: {DIM}{CSV_PATH}{RESET}")
    print()

    return 0 if failures == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
