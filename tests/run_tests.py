#!/usr/bin/env python3
"""
Ejecutor principal de tests para AudioQual.

Uso:
    python tests/run_tests.py [--summary] [--suite SUITE] [--save]

Opciones:
    --summary    Solo mostrar resumen final
    --suite      Ejecutar solo una suite: detection, classification, ui
    --save       Guardar resultados en tests/results_YYYYMMDD_HHMMSS.json
"""
import argparse
import json
import os
import sys
import time
from datetime import datetime

# Asegurar que el directorio raiz del proyecto esta en el path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
TESTS_JSON = os.path.join(TESTS_DIR, "tests.json")

# Colores ANSI
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
BOLD = "\033[1m"
DIM = "\033[2m"
RESET = "\033[0m"


def load_test_cases():
    """Carga los test cases desde tests.json."""
    with open(TESTS_JSON, "r", encoding="utf-8") as f:
        return json.load(f)


def resolve_filepath(tc):
    """Resuelve la ruta del archivo relativa al proyecto."""
    filepath = tc["file"]
    if not os.path.isabs(filepath):
        filepath = os.path.join(PROJECT_ROOT, filepath)
    return filepath


def run_all_analyses(test_cases):
    """
    Ejecuta el analizador sobre todos los archivos de test una sola vez.

    Returns:
        Dict {filepath_relativo: AnalysisResult}
    """
    from src.core.analyzer import AudioAnalyzer

    analyzer = AudioAnalyzer()
    results = {}

    # Recolectar archivos unicos
    files = {}
    for tc in test_cases:
        rel_path = tc["file"]
        abs_path = resolve_filepath(tc)
        if rel_path not in files:
            files[rel_path] = abs_path

    total = len(files)
    print(f"\n{CYAN}{BOLD}Analizando {total} archivos...{RESET}")

    for i, (rel_path, abs_path) in enumerate(files.items(), 1):
        filename = os.path.basename(abs_path)
        print(f"  [{i}/{total}] {filename}...", end="", flush=True)

        if not os.path.exists(abs_path):
            print(f" {RED}NO ENCONTRADO{RESET}")
            continue

        try:
            result = analyzer.analyze_file(abs_path)
            # Limpiar frequency_analysis para liberar memoria
            result.frequency_analysis = None
            results[rel_path] = result
            print(f" {GREEN}OK{RESET} ({result.cutoff_frequency_khz:.1f} kHz, {result.status})")
        except Exception as e:
            print(f" {RED}ERROR: {e}{RESET}")

    print()
    return results


def print_result(r, summary_only=False):
    """Imprime un resultado individual."""
    if summary_only:
        return

    status = r["status"]
    if status == "PASS":
        icon = f"{GREEN}PASS{RESET}"
    elif status == "FAIL":
        icon = f"{RED}FAIL{RESET}"
    else:  # SKIP
        icon = f"{YELLOW}SKIP{RESET}"

    print(f"  [{icon}] {r['id']}: {r['description']}")
    if status != "PASS":
        print(f"         {DIM}{r['detail']}{RESET}")


def print_summary(all_results):
    """Imprime el resumen final."""
    passed = sum(1 for r in all_results if r["status"] == "PASS")
    failed = sum(1 for r in all_results if r["status"] == "FAIL")
    skipped = sum(1 for r in all_results if r["status"] == "SKIP")
    total = len(all_results)

    print(f"\n{BOLD}{'=' * 60}{RESET}")
    print(f"{BOLD}RESUMEN{RESET}")
    print(f"{'=' * 60}")
    print(f"  {GREEN}Passed:  {passed}{RESET}")
    if failed > 0:
        print(f"  {RED}Failed:  {failed}{RESET}")
    else:
        print(f"  Failed:  {failed}")
    if skipped > 0:
        print(f"  {YELLOW}Skipped: {skipped} (known bugs){RESET}")
    print(f"  Total:   {total}")
    print()

    if failed == 0:
        print(f"  {GREEN}{BOLD}{passed}/{total} passed, {failed} failed, {skipped} known bugs{RESET}")
    else:
        print(f"  {RED}{BOLD}{passed}/{total} passed, {failed} failed, {skipped} known bugs{RESET}")

    # Mostrar tests fallidos
    if failed > 0:
        print(f"\n  {RED}Tests fallidos:{RESET}")
        for r in all_results:
            if r["status"] == "FAIL":
                print(f"    - {r['id']}: {r['detail']}")

    print()
    return failed


def save_results(all_results, analysis_results):
    """Guarda los resultados en un archivo JSON."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"results_{timestamp}.json"
    filepath = os.path.join(TESTS_DIR, filename)

    # Serializar analysis_results
    analysis_data = {}
    for path, result in analysis_results.items():
        analysis_data[path] = {
            "filename": result.filename,
            "format": result.format,
            "cutoff_frequency_khz": result.cutoff_frequency_khz,
            "status": result.status,
            "detected_quality": result.detected_quality,
            "confidence": result.confidence,
            "is_uncertain": result.is_uncertain,
            "details": result.details,
        }

    output = {
        "timestamp": datetime.now().isoformat(),
        "test_results": all_results,
        "analysis_results": analysis_data,
        "summary": {
            "passed": sum(1 for r in all_results if r["status"] == "PASS"),
            "failed": sum(1 for r in all_results if r["status"] == "FAIL"),
            "skipped": sum(1 for r in all_results if r["status"] == "SKIP"),
            "total": len(all_results),
        },
    }

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print(f"{CYAN}Resultados guardados en: {filename}{RESET}")
    return filepath


def main():
    parser = argparse.ArgumentParser(description="Ejecutor de tests AudioQual")
    parser.add_argument("--summary", action="store_true", help="Solo mostrar resumen")
    parser.add_argument("--suite", choices=["detection", "classification", "ui"],
                        help="Ejecutar solo una suite")
    parser.add_argument("--save", action="store_true", help="Guardar resultados en JSON")
    args = parser.parse_args()

    print(f"\n{BOLD}{'=' * 60}{RESET}")
    print(f"{BOLD}  AudioQual Test Suite{RESET}")
    print(f"{'=' * 60}")

    all_results = []
    analysis_results = {}

    # Cargar test cases (necesario para detection y classification)
    if args.suite != "ui":
        test_cases = load_test_cases()

        # Ejecutar analisis una sola vez
        start = time.time()
        analysis_results = run_all_analyses(test_cases)
        elapsed = time.time() - start
        print(f"{DIM}Analisis completado en {elapsed:.1f}s{RESET}\n")

    # Suite: detection
    if args.suite is None or args.suite == "detection":
        from tests import test_detection
        print(f"{BOLD}--- Detection Tests ---{RESET}")
        detection_results = test_detection.run_tests(test_cases, analysis_results)
        for r in detection_results:
            print_result(r, args.summary)
        all_results.extend(detection_results)
        print()

    # Suite: classification
    if args.suite is None or args.suite == "classification":
        from tests import test_classification
        print(f"{BOLD}--- Classification Tests ---{RESET}")
        classification_results = test_classification.run_tests(test_cases, analysis_results)
        for r in classification_results:
            print_result(r, args.summary)
        all_results.extend(classification_results)
        print()

    # Suite: ui
    if args.suite is None or args.suite == "ui":
        from tests import test_ui
        print(f"{BOLD}--- UI Tests ---{RESET}")
        ui_results = test_ui.run_tests()
        for r in ui_results:
            print_result(r, args.summary)
        all_results.extend(ui_results)
        print()

    # Resumen
    failed = print_summary(all_results)

    # Guardar si se pide
    if args.save:
        save_results(all_results, analysis_results)

    # Exit code
    sys.exit(1 if failed > 0 else 0)


if __name__ == "__main__":
    main()
