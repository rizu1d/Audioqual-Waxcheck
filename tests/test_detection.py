"""
Tests de deteccion de cutoff de frecuencia.

Verifica que el cutoff detectado por el analizador esta dentro
del rango esperado definido en tests.json.
"""


def run_tests(test_cases, analysis_results):
    """
    Ejecuta tests de deteccion de cutoff.

    Args:
        test_cases: Lista de test cases desde tests.json
        analysis_results: Dict {filepath: AnalysisResult} con resultados pre-calculados

    Returns:
        Lista de dicts con resultados: {id, description, status, expected, actual, detail}
    """
    results = []

    for tc in test_cases:
        expected = tc.get("expected", {})
        has_cutoff_check = "cutoff_below_khz" in expected or "cutoff_above_khz" in expected

        if not has_cutoff_check:
            continue

        tc_id = tc["id"]
        filepath = tc["file"]
        known_bug = tc.get("known_bug", False)

        result_entry = {
            "id": tc_id,
            "description": tc["description"],
            "test_type": "detection",
        }

        # Buscar resultado de analisis
        analysis = analysis_results.get(filepath)
        if analysis is None:
            result_entry["status"] = "FAIL"
            result_entry["detail"] = "Archivo no analizado (no encontrado en resultados)"
            result_entry["expected"] = str(expected)
            result_entry["actual"] = "N/A"
            results.append(result_entry)
            continue

        if analysis.error:
            result_entry["status"] = "SKIP" if known_bug else "FAIL"
            result_entry["detail"] = f"Error en analisis: {analysis.error}"
            result_entry["expected"] = str(expected)
            result_entry["actual"] = f"Error: {analysis.error}"
            results.append(result_entry)
            continue

        actual_cutoff = analysis.cutoff_frequency_khz
        passed = True
        details = []

        # Verificar cutoff_below_khz
        if "cutoff_below_khz" in expected:
            max_cutoff = expected["cutoff_below_khz"]
            if actual_cutoff > max_cutoff:
                passed = False
                details.append(f"cutoff {actual_cutoff:.1f} kHz > max esperado {max_cutoff} kHz")
            else:
                details.append(f"cutoff {actual_cutoff:.1f} kHz <= {max_cutoff} kHz")

        # Verificar cutoff_above_khz
        if "cutoff_above_khz" in expected:
            min_cutoff = expected["cutoff_above_khz"]
            if actual_cutoff < min_cutoff:
                passed = False
                details.append(f"cutoff {actual_cutoff:.1f} kHz < min esperado {min_cutoff} kHz")
            else:
                details.append(f"cutoff {actual_cutoff:.1f} kHz >= {min_cutoff} kHz")

        if known_bug:
            result_entry["status"] = "SKIP"
            result_entry["detail"] = f"Known bug - {'; '.join(details)}"
        elif passed:
            result_entry["status"] = "PASS"
            result_entry["detail"] = "; ".join(details)
        else:
            result_entry["status"] = "FAIL"
            result_entry["detail"] = "; ".join(details)

        result_entry["expected"] = str(expected)
        result_entry["actual"] = f"{actual_cutoff:.1f} kHz"
        results.append(result_entry)

    return results
