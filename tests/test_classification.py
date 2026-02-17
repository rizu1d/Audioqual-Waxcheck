"""
Tests de clasificacion de calidad y status.

Verifica que el status y la calidad detectada coinciden
con lo esperado en tests.json.
"""


def run_tests(test_cases, analysis_results):
    """
    Ejecuta tests de clasificacion.

    Args:
        test_cases: Lista de test cases desde tests.json
        analysis_results: Dict {filepath: AnalysisResult} con resultados pre-calculados

    Returns:
        Lista de dicts con resultados: {id, description, status, expected, actual, detail}
    """
    results = []

    for tc in test_cases:
        expected = tc.get("expected", {})
        has_status = "status" in expected
        has_quality = "detected_quality_in" in expected
        has_uncertain = "is_uncertain" in expected

        if not has_status and not has_quality and not has_uncertain:
            continue

        tc_id = tc["id"]
        filepath = tc["file"]
        known_bug = tc.get("known_bug", False)

        # Buscar resultado de analisis
        analysis = analysis_results.get(filepath)
        if analysis is None:
            results.append({
                "id": tc_id,
                "description": tc["description"],
                "test_type": "classification",
                "status": "FAIL",
                "detail": "Archivo no analizado (no encontrado en resultados)",
                "expected": str(expected),
                "actual": "N/A",
            })
            continue

        if analysis.error:
            status = "SKIP" if known_bug else "FAIL"
            results.append({
                "id": tc_id,
                "description": tc["description"],
                "test_type": "classification",
                "status": status,
                "detail": f"Error en analisis: {analysis.error}",
                "expected": str(expected),
                "actual": f"Error: {analysis.error}",
            })
            continue

        passed = True
        details = []

        # Verificar status
        if has_status:
            expected_status = expected["status"]
            actual_status = analysis.status
            if actual_status != expected_status:
                passed = False
                details.append(f"status '{actual_status}' != esperado '{expected_status}'")
            else:
                details.append(f"status '{actual_status}' OK")

        # Verificar detected_quality
        if has_quality:
            expected_qualities = expected["detected_quality_in"]
            actual_quality = analysis.detected_quality
            if actual_quality not in expected_qualities:
                passed = False
                details.append(
                    f"quality '{actual_quality}' no esta en {expected_qualities}"
                )
            else:
                details.append(f"quality '{actual_quality}' OK")

        # Verificar is_uncertain
        if has_uncertain:
            expected_uncertain = expected["is_uncertain"]
            actual_uncertain = analysis.is_uncertain
            if actual_uncertain != expected_uncertain:
                passed = False
                details.append(
                    f"is_uncertain={actual_uncertain} != esperado {expected_uncertain}"
                )
            else:
                details.append(f"is_uncertain={actual_uncertain} OK")

        result_entry = {
            "id": tc_id,
            "description": tc["description"],
            "test_type": "classification",
            "expected": str(expected),
            "actual": f"status='{analysis.status}', quality='{analysis.detected_quality}', uncertain={analysis.is_uncertain}",
            "detail": "; ".join(details),
        }

        if known_bug:
            result_entry["status"] = "SKIP"
            result_entry["detail"] = f"Known bug - {'; '.join(details)}"
        elif passed:
            result_entry["status"] = "PASS"
        else:
            result_entry["status"] = "FAIL"

        results.append(result_entry)

    return results
