#!/usr/bin/env python3
"""
Genera un informe HTML autocontenido desde los resultados CSV de la evaluacion.

Uso:
    python evaluation/report.py
"""
import csv
import os
import sys
import webbrowser
from collections import defaultdict
from datetime import datetime

EVAL_DIR = os.path.dirname(os.path.abspath(__file__))
CSV_PATH = os.path.join(EVAL_DIR, "results.csv")
HTML_PATH = os.path.join(EVAL_DIR, "report.html")

# Paleta del proyecto (de constants.py)
COLORS = {
    "bg": "#0c0b14",
    "bg_secondary": "#13121d",
    "bg_elevated": "#252530",
    "text": "#F3F1E5",
    "text_secondary": "#9A9A9A",
    "accent": "#7969A8",
    "gold": "#FCC844",
    "ok": "#5DB88C",
    "error": "#E05555",
    "border": "#1c192a",
    # Niveles de calidad
    "bajo": "#E85555",
    "medio": "#FCC844",
    "bueno": "#6BCB77",
    "lossless": "#6BA3E8",
}


def load_results():
    """Carga resultados desde el CSV."""
    rows = []
    with open(CSV_PATH, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            # Convertir tipos
            row["detected_cutoff_khz"] = float(row["detected_cutoff_khz"])
            row["expected_cutoff_min_khz"] = float(row["expected_cutoff_min_khz"])
            row["expected_cutoff_max_khz"] = float(row["expected_cutoff_max_khz"])
            row["confidence"] = float(row["confidence"])
            row["match"] = row["match"] == "True"
            row["status_match"] = row["status_match"] == "True"
            row["level_match"] = row["level_match"] == "True"
            row["quality_match"] = row["quality_match"] == "True"
            row["cutoff_in_range"] = row["cutoff_in_range"] == "True"
            row["bitrate_declared"] = int(row["bitrate_declared"])
            row["bitrate_original"] = int(row["bitrate_original"]) if row["bitrate_original"] else None
            rows.append(row)
    return rows


def compute_stats(rows):
    """Calcula estadisticas agregadas."""
    total = len(rows)
    matches = sum(1 for r in rows if r["match"])
    failures = total - matches
    precision = (matches / total * 100) if total > 0 else 0

    false_positives = sum(
        1 for r in rows
        if r["type"] == "legit" and r["detected_status"] == "Transcode detectado"
    )
    false_negatives = sum(
        1 for r in rows
        if r["type"] in ("transcode", "youtube")
        and r["detected_status"] != "Transcode detectado"
    )

    # Por tipo
    by_type = defaultdict(lambda: {"total": 0, "matches": 0})
    for r in rows:
        by_type[r["type"]]["total"] += 1
        if r["match"]:
            by_type[r["type"]]["matches"] += 1

    # Por nivel esperado
    by_level = defaultdict(lambda: {"total": 0, "matches": 0})
    for r in rows:
        by_level[r["expected_level"]]["total"] += 1
        if r["match"]:
            by_level[r["expected_level"]]["matches"] += 1

    # Matriz de confusion por nivel
    level_labels = ["bajo", "medio", "bueno", "lossless"]
    level_matrix = defaultdict(lambda: defaultdict(int))
    for r in rows:
        level_matrix[r["expected_level"]][r["detected_level"]] += 1

    # Matriz de confusion por status
    status_labels_set = set()
    for r in rows:
        status_labels_set.add(r["expected_status"])
        status_labels_set.add(r["detected_status"])
    status_labels = sorted(status_labels_set)
    status_matrix = defaultdict(lambda: defaultdict(int))
    for r in rows:
        status_matrix[r["expected_status"]][r["detected_status"]] += 1

    # Confianza: aciertos vs fallos
    conf_matches = [r["confidence"] for r in rows if r["match"]]
    conf_failures = [r["confidence"] for r in rows if not r["match"]]
    avg_conf_matches = sum(conf_matches) / len(conf_matches) if conf_matches else 0
    avg_conf_failures = sum(conf_failures) / len(conf_failures) if conf_failures else 0

    # Desglose por bitrate declarado (legitimos)
    legit_by_bitrate = defaultdict(lambda: {"total": 0, "matches": 0, "rows": []})
    for r in rows:
        if r["type"] == "legit":
            br = r["bitrate_declared"]
            legit_by_bitrate[br]["total"] += 1
            legit_by_bitrate[br]["rows"].append(r)
            if r["match"]:
                legit_by_bitrate[br]["matches"] += 1

    # Desglose transcodes
    transcode_by_combo = defaultdict(lambda: {"total": 0, "matches": 0, "rows": []})
    for r in rows:
        if r["type"] in ("transcode", "youtube"):
            combo = f"{r['bitrate_original'] or '?'}→{r['bitrate_declared']}"
            if r["type"] == "youtube":
                combo = f"YT {combo}"
            transcode_by_combo[combo]["total"] += 1
            transcode_by_combo[combo]["rows"].append(r)
            if r["match"]:
                transcode_by_combo[combo]["matches"] += 1

    return {
        "total": total,
        "matches": matches,
        "failures": failures,
        "precision": precision,
        "false_positives": false_positives,
        "false_negatives": false_negatives,
        "by_type": dict(by_type),
        "by_level": dict(by_level),
        "level_matrix": level_matrix,
        "level_labels": [l for l in level_labels if l in {r["expected_level"] for r in rows} | {r["detected_level"] for r in rows}],
        "status_matrix": status_matrix,
        "status_labels": status_labels,
        "avg_conf_matches": avg_conf_matches,
        "avg_conf_failures": avg_conf_failures,
        "legit_by_bitrate": dict(legit_by_bitrate),
        "transcode_by_combo": dict(transcode_by_combo),
    }


def level_color(level):
    """Devuelve el color hex para un nivel de calidad."""
    return COLORS.get(level, COLORS["text_secondary"])


def pct_color(pct):
    """Devuelve el color segun el porcentaje."""
    if pct == 100:
        return COLORS["ok"]
    if pct >= 80:
        return COLORS["gold"]
    return COLORS["error"]


def esc(text):
    """Escapa HTML."""
    return str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def generate_html(rows, stats):
    """Genera el HTML del informe."""
    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    failures = [r for r in rows if not r["match"]]

    html = f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>AudioQual — Informe de Evaluacion</title>
<style>
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{
    background: {COLORS['bg']};
    color: {COLORS['text']};
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', system-ui, sans-serif;
    line-height: 1.5;
    padding: 40px 20px;
}}
.container {{ max-width: 1100px; margin: 0 auto; }}
h1 {{
    font-size: 28px;
    font-weight: 700;
    margin-bottom: 8px;
}}
.subtitle {{
    color: {COLORS['text_secondary']};
    font-size: 14px;
    margin-bottom: 32px;
}}
h2 {{
    font-size: 18px;
    font-weight: 600;
    margin: 32px 0 16px;
    color: {COLORS['accent']};
}}

/* Cards */
.cards {{
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
    gap: 12px;
    margin-bottom: 32px;
}}
.card {{
    background: {COLORS['bg_secondary']};
    border: 1px solid {COLORS['border']};
    border-radius: 8px;
    padding: 16px;
    text-align: center;
}}
.card .value {{
    font-size: 32px;
    font-weight: 700;
    font-variant-numeric: tabular-nums;
}}
.card .label {{
    font-size: 12px;
    color: {COLORS['text_secondary']};
    text-transform: uppercase;
    letter-spacing: 0.5px;
    margin-top: 4px;
}}

/* Tables */
table {{
    width: 100%;
    border-collapse: collapse;
    font-size: 13px;
    margin-bottom: 24px;
}}
th {{
    background: {COLORS['bg_secondary']};
    color: {COLORS['text_secondary']};
    font-weight: 600;
    text-transform: uppercase;
    font-size: 11px;
    letter-spacing: 0.5px;
    padding: 10px 12px;
    text-align: left;
    border-bottom: 1px solid {COLORS['border']};
}}
td {{
    padding: 8px 12px;
    border-bottom: 1px solid {COLORS['border']};
    vertical-align: middle;
}}
tr:hover td {{ background: rgba(121, 105, 168, 0.06); }}

/* Confusion matrix */
.matrix {{
    width: auto;
    margin: 0 auto 24px;
}}
.matrix th, .matrix td {{
    text-align: center;
    padding: 8px 16px;
    min-width: 80px;
}}
.matrix .diag {{ font-weight: 700; }}
.matrix .off {{ color: {COLORS['text_secondary']}; }}
.matrix .corner {{
    background: transparent;
    border: none;
}}
.matrix .header-row th {{
    color: {COLORS['text']};
    font-size: 12px;
}}

/* Badges */
.badge {{
    display: inline-block;
    padding: 2px 8px;
    border-radius: 4px;
    font-size: 11px;
    font-weight: 600;
}}
.badge-ok {{ background: rgba(93, 184, 140, 0.15); color: {COLORS['ok']}; }}
.badge-fail {{ background: rgba(224, 85, 85, 0.15); color: {COLORS['error']}; }}

/* Confidence bars */
.conf-bar-container {{
    display: flex;
    align-items: center;
    gap: 8px;
    margin: 8px 0;
}}
.conf-bar-label {{
    width: 80px;
    font-size: 13px;
    text-align: right;
}}
.conf-bar-track {{
    flex: 1;
    height: 24px;
    background: {COLORS['bg_secondary']};
    border-radius: 4px;
    overflow: hidden;
    position: relative;
}}
.conf-bar-fill {{
    height: 100%;
    border-radius: 4px;
    transition: width 0.3s;
}}
.conf-bar-value {{
    width: 60px;
    font-size: 13px;
    font-variant-numeric: tabular-nums;
}}

/* Level dots */
.dot {{
    display: inline-block;
    width: 8px;
    height: 8px;
    border-radius: 50%;
    margin-right: 6px;
    vertical-align: middle;
}}
</style>
</head>
<body>
<div class="container">

<h1>AudioQual — Informe de Evaluacion</h1>
<p class="subtitle">Generado: {now} &middot; {stats['total']} variantes analizadas</p>

<!-- Resumen -->
<h2>Resumen</h2>
<div class="cards">
    <div class="card">
        <div class="value">{stats['total']}</div>
        <div class="label">Total</div>
    </div>
    <div class="card">
        <div class="value" style="color:{COLORS['ok']}">{stats['matches']}</div>
        <div class="label">Aciertos</div>
    </div>
    <div class="card">
        <div class="value" style="color:{COLORS['error'] if stats['failures'] else COLORS['text_secondary']}">{stats['failures']}</div>
        <div class="label">Fallos</div>
    </div>
    <div class="card">
        <div class="value" style="color:{pct_color(stats['precision'])}">{stats['precision']:.1f}%</div>
        <div class="label">Precision</div>
    </div>
    <div class="card">
        <div class="value" style="color:{COLORS['error'] if stats['false_positives'] else COLORS['text_secondary']}">{stats['false_positives']}</div>
        <div class="label">Falsos Positivos</div>
    </div>
    <div class="card">
        <div class="value" style="color:{COLORS['error'] if stats['false_negatives'] else COLORS['text_secondary']}">{stats['false_negatives']}</div>
        <div class="label">Falsos Negativos</div>
    </div>
</div>

<!-- Matriz de confusion por nivel -->
<h2>Matriz de Confusion — Nivel de Calidad</h2>
<p class="subtitle" style="margin-bottom:12px">Filas: nivel esperado. Columnas: nivel detectado.</p>
<table class="matrix">
<tr>
    <th class="corner"></th>
    {"".join(f'<th><span class="dot" style="background:{level_color(l)}"></span>{esc(l.capitalize())}</th>' for l in stats['level_labels'])}
</tr>
"""
    for expected in stats["level_labels"]:
        html += f'<tr><th style="text-align:right"><span class="dot" style="background:{level_color(expected)}"></span>{esc(expected.capitalize())}</th>'
        for detected in stats["level_labels"]:
            count = stats["level_matrix"][expected][detected]
            is_diag = expected == detected
            cls = "diag" if is_diag else "off"
            style = ""
            if is_diag and count > 0:
                style = f' style="color:{COLORS["ok"]}"'
            elif not is_diag and count > 0:
                style = f' style="color:{COLORS["error"]}"'
            html += f'<td class="{cls}"{style}>{count if count else "·"}</td>'
        html += "</tr>\n"

    html += """</table>

<!-- Matriz de confusion por status -->
<h2>Matriz de Confusion — Status</h2>
<p class="subtitle" style="margin-bottom:12px">Filas: status esperado. Columnas: status detectado.</p>
<table class="matrix">
<tr>
    <th class="corner"></th>
"""
    for s in stats["status_labels"]:
        html += f"<th>{esc(s)}</th>"
    html += "</tr>\n"

    for expected in stats["status_labels"]:
        html += f'<tr><th style="text-align:right">{esc(expected)}</th>'
        for detected in stats["status_labels"]:
            count = stats["status_matrix"][expected][detected]
            is_diag = expected == detected
            cls = "diag" if is_diag else "off"
            style = ""
            if is_diag and count > 0:
                style = f' style="color:{COLORS["ok"]}"'
            elif not is_diag and count > 0:
                style = f' style="color:{COLORS["error"]}"'
            html += f'<td class="{cls}"{style}>{count if count else "·"}</td>'
        html += "</tr>\n"

    html += "</table>\n"

    # Desglose legitimos
    html += '<h2>Desglose — Legitimos</h2>\n<table>\n'
    html += "<tr><th>Bitrate</th><th>Nivel Esperado</th><th>Aciertos</th><th>Total</th><th>Precision</th></tr>\n"
    for br in sorted(stats["legit_by_bitrate"].keys(), reverse=True):
        data = stats["legit_by_bitrate"][br]
        pct = data["matches"] / data["total"] * 100 if data["total"] else 0
        sample = data["rows"][0] if data["rows"] else {}
        expected_level = sample.get("expected_level", "")
        html += (
            f'<tr><td>{br}k</td>'
            f'<td><span class="dot" style="background:{level_color(expected_level)}"></span>{esc(expected_level)}</td>'
            f'<td>{data["matches"]}</td><td>{data["total"]}</td>'
            f'<td style="color:{pct_color(pct)}">{pct:.0f}%</td></tr>\n'
        )
    html += "</table>\n"

    # Desglose transcodes
    html += '<h2>Desglose — Transcodes</h2>\n<table>\n'
    html += "<tr><th>Combinacion</th><th>Aciertos</th><th>Total</th><th>Precision</th></tr>\n"
    for combo in sorted(stats["transcode_by_combo"].keys()):
        data = stats["transcode_by_combo"][combo]
        pct = data["matches"] / data["total"] * 100 if data["total"] else 0
        html += (
            f'<tr><td>{esc(combo)}</td>'
            f'<td>{data["matches"]}</td><td>{data["total"]}</td>'
            f'<td style="color:{pct_color(pct)}">{pct:.0f}%</td></tr>\n'
        )
    html += "</table>\n"

    # Lista de fallos
    if failures:
        html += '<h2>Fallos</h2>\n<table>\n'
        html += "<tr><th>Archivo</th><th>Tipo</th><th>Nivel Esperado</th><th>Nivel Detectado</th><th>Status Esperado</th><th>Status Detectado</th><th>Cutoff</th><th>Confianza</th></tr>\n"
        for r in failures:
            html += (
                f'<tr>'
                f'<td>{esc(r["filename"])}</td>'
                f'<td>{esc(r["type"])}</td>'
                f'<td><span class="dot" style="background:{level_color(r["expected_level"])}"></span>{esc(r["expected_level"])}</td>'
                f'<td><span class="dot" style="background:{level_color(r["detected_level"])}"></span>{esc(r["detected_level"])}</td>'
                f'<td>{esc(r["expected_status"])}</td>'
                f'<td>{esc(r["detected_status"])}</td>'
                f'<td>{r["detected_cutoff_khz"]:.1f} kHz</td>'
                f'<td>{r["confidence"]:.2f}</td>'
                f'</tr>\n'
            )
        html += "</table>\n"
    else:
        html += '<h2>Fallos</h2>\n<p style="color:{};margin-bottom:24px">Ninguno. Todos los resultados son correctos.</p>\n'.format(COLORS["ok"])

    # Distribucion de confianza
    html += '<h2>Distribucion de Confianza</h2>\n'
    max_conf = max(stats["avg_conf_matches"], stats["avg_conf_failures"], 0.01)

    html += f"""
<div class="conf-bar-container">
    <div class="conf-bar-label">Aciertos</div>
    <div class="conf-bar-track">
        <div class="conf-bar-fill" style="width:{stats['avg_conf_matches'] / max_conf * 100:.0f}%;background:{COLORS['ok']}"></div>
    </div>
    <div class="conf-bar-value" style="color:{COLORS['ok']}">{stats['avg_conf_matches']:.3f}</div>
</div>
<div class="conf-bar-container">
    <div class="conf-bar-label">Fallos</div>
    <div class="conf-bar-track">
        <div class="conf-bar-fill" style="width:{stats['avg_conf_failures'] / max_conf * 100:.0f}%;background:{COLORS['error']}"></div>
    </div>
    <div class="conf-bar-value" style="color:{COLORS['error']}">{stats['avg_conf_failures']:.3f}</div>
</div>
"""

    html += """
</div>
</body>
</html>"""

    return html


def main():
    if not os.path.exists(CSV_PATH):
        print(f"Error: No se encontro {CSV_PATH}")
        print(f"Ejecuta primero: python evaluation/evaluate.py")
        sys.exit(1)

    print("Cargando resultados...", end="", flush=True)
    rows = load_results()
    print(f" {len(rows)} filas")

    print("Calculando estadisticas...", end="", flush=True)
    stats = compute_stats(rows)
    print(" OK")

    print("Generando HTML...", end="", flush=True)
    html = generate_html(rows, stats)
    print(" OK")

    with open(HTML_PATH, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"Informe guardado en: {HTML_PATH}")
    webbrowser.open(f"file://{os.path.abspath(HTML_PATH)}")


if __name__ == "__main__":
    main()
