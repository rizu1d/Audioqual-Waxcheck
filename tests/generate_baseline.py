#!/usr/bin/env python3
"""
Genera tests.json con resultados baseline del analizador actual.

Ejecutar una vez para crear el registro maestro de tests.
NO EDITAR tests.json manualmente despues; este script es la unica fuente.
"""
import json
import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from src.core.analyzer import AudioAnalyzer

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
TEST_FILES_DIR = os.path.join(PROJECT_ROOT, "references", "test-files")
OUTPUT = os.path.join(TESTS_DIR, "tests.json")

# Definicion de archivos y sus expectativas conocidas
# category: "base", "youtuberips", "casos-excepcionales"
# type: "legit", "transcode", "fake-format", "youtube-rip", "edge-case"

FILE_DEFS = [
    # === BASE: Archivos legitimos ===
    {
        "id": "BASE_001",
        "subdir": "base",
        "filename": "1A. Orbit (3) Featuring Carol Hall - The Beat Goes On (Lunar Mix).aiff",
        "description": "AIFF legitimo - debe ser lossless/OK",
        "type": "legit",
    },
    {
        "id": "BASE_002",
        "subdir": "base",
        "filename": "Agoria - Teardrops (Don't Stop The Music) (Nick Morgan Remix).mp3",
        "description": "MP3 legitimo - debe ser OK",
        "type": "legit",
    },
    {
        "id": "BASE_003",
        "subdir": "base",
        "filename": "Silicone Soul - Chic-O-Laa (H-Foundation Remix).mp3",
        "description": "MP3 legitimo - debe ser OK",
        "type": "legit",
    },
    # === BASE: AIFF falsos ===
    {
        "id": "BASE_004",
        "subdir": "base",
        "filename": "notaiff-detected.aiff",
        "description": "AIFF falso (transcode) - debe detectar transcode",
        "type": "fake-format",
    },
    {
        "id": "BASE_005",
        "subdir": "base",
        "filename": "notaiff-undetected.aiff",
        "description": "AIFF falso (transcode no detectado) - known bug",
        "type": "fake-format",
        "known_bug": True,
        "notes": "Transcode no detectado - pendiente de mejora en algoritmo",
    },
    # === BASE: Transcodes conocidos ===
    {
        "id": "BASE_006",
        "subdir": "base",
        "filename": "transcode-manuchao.mp3",
        "description": "MP3 transcode - Manu Chao",
        "type": "transcode",
    },
    {
        "id": "BASE_007",
        "subdir": "base",
        "filename": "transcode-portishead.mp3",
        "description": "MP3 transcode - Portishead",
        "type": "transcode",
    },
    {
        "id": "BASE_008",
        "subdir": "base",
        "filename": "transcode-sickomode.mp3",
        "description": "MP3 transcode - Sicko Mode",
        "type": "transcode",
    },
    {
        "id": "BASE_009",
        "subdir": "base",
        "filename": "transcode-thebox.mp3",
        "description": "MP3 transcode - The Box",
        "type": "transcode",
    },
    # === YOUTUBE RIPS ===
    {
        "id": "YT_001",
        "subdir": "youtuberips",
        "filename": "C.R.E.A.M. (A Cappella).mp3",
        "description": "YouTube rip - C.R.E.A.M. acapella",
        "type": "youtube-rip",
    },
    {
        "id": "YT_002",
        "subdir": "youtuberips",
        "filename": "C'est justifiable (Acapella).mp3",
        "description": "YouTube rip - C'est justifiable acapella",
        "type": "youtube-rip",
    },
    {
        "id": "YT_003",
        "subdir": "youtuberips",
        "filename": "De La Soul  Chaka Khan  All Good Acapella.mp3",
        "description": "YouTube rip - De La Soul acapella",
        "type": "youtube-rip",
    },
    {
        "id": "YT_004",
        "subdir": "youtuberips",
        "filename": "Hip Hop Hooray (Acapella) (Unrelease.mp3",
        "description": "YouTube rip - Hip Hop Hooray acapella",
        "type": "youtube-rip",
    },
    {
        "id": "YT_005",
        "subdir": "youtuberips",
        "filename": "IAM - Sad Hill (Acapella).mp3",
        "description": "YouTube rip - IAM Sad Hill acapella",
        "type": "youtube-rip",
    },
    {
        "id": "YT_006",
        "subdir": "youtuberips",
        "filename": "Mama lova (acapella) 81 bpm.mp3",
        "description": "YouTube rip - Mama lova acapella",
        "type": "youtube-rip",
    },
    {
        "id": "YT_007",
        "subdir": "youtuberips",
        "filename": "Poison (Isolated Vocals).mp3",
        "description": "YouTube rip - Poison isolated vocals",
        "type": "youtube-rip",
    },
    {
        "id": "YT_008",
        "subdir": "youtuberips",
        "filename": "poppa large acapella ultramagnetic mcs.mp3",
        "description": "YouTube rip - Poppa Large acapella",
        "type": "youtube-rip",
    },
    {
        "id": "YT_009",
        "subdir": "youtuberips",
        "filename": "Public Enemy Acapella Pack.mp3",
        "description": "YouTube rip - Public Enemy acapella",
        "type": "youtube-rip",
    },
    {
        "id": "YT_010",
        "subdir": "youtuberips",
        "filename": "Regulate Acapella.mp3",
        "description": "YouTube rip - Regulate acapella",
        "type": "youtube-rip",
    },
    {
        "id": "YT_011",
        "subdir": "youtuberips",
        "filename": "Shook Ones Pt. 2 (Acapella) 94 bpm.mp3",
        "description": "YouTube rip - Shook Ones acapella",
        "type": "youtube-rip",
    },
    {
        "id": "YT_012",
        "subdir": "youtuberips",
        "filename": "Supreme NTM - Boogie man acapellaaaa.mp3",
        "description": "YouTube rip - NTM Boogie Man acapella",
        "type": "youtube-rip",
    },
    {
        "id": "YT_013",
        "subdir": "youtuberips",
        "filename": "Suprême NTM - Come Again (Remix) (A.mp3",
        "description": "YouTube rip - NTM Come Again acapella",
        "type": "youtube-rip",
    },
    {
        "id": "YT_014",
        "subdir": "youtuberips",
        "filename": "Suprême NTM - Seine Saint Denis Styl.mp3",
        "description": "YouTube rip - NTM Seine Saint Denis acapella",
        "type": "youtube-rip",
    },
    {
        "id": "YT_015",
        "subdir": "youtuberips",
        "filename": "The Humpty Dance (Acapella).mp3",
        "description": "YouTube rip - Humpty Dance acapella",
        "type": "youtube-rip",
    },
    {
        "id": "YT_016",
        "subdir": "youtuberips",
        "filename": "Walkman Music (Acapella).mp3",
        "description": "YouTube rip - Walkman Music acapella",
        "type": "youtube-rip",
    },
    {
        "id": "YT_017",
        "subdir": "youtuberips",
        "filename": "Jocelyn Brown - Love's Gonna Get You.mp3",
        "description": "YouTube rip 128kbps - Jocelyn Brown acapella",
        "type": "youtube-rip",
    },
    {
        "id": "YT_018",
        "subdir": "youtuberips",
        "filename": "yt5s.io - Kinny - Afro Love Forest - A Cappella (128 kbps).mp3",
        "description": "YouTube rip 128kbps - Kinny acapella",
        "type": "youtube-rip",
    },
    # === CASOS EXCEPCIONALES ===
    {
        "id": "EDGE_001",
        "subdir": "casos-excepcionales",
        "filename": "LaTour - People Are Still Having Sex.mp3",
        "description": "Edge case - LaTour (contenido HF genuino antiguo)",
        "type": "edge-case",
    },
    {
        "id": "EDGE_002",
        "subdir": "casos-excepcionales",
        "filename": "DJ Assault - Bangapella.mp3",
        "description": "Edge case - DJ Assault acapella",
        "type": "edge-case",
    },
    {
        "id": "EDGE_003",
        "subdir": "casos-excepcionales",
        "filename": "Golden Boy - Autopilot (Original).mp3",
        "description": "Edge case - Golden Boy",
        "type": "edge-case",
    },
    {
        "id": "EDGE_004",
        "subdir": "casos-excepcionales",
        "filename": "Plaisir de France - Américaine (2002 Mix).mp3",
        "description": "Edge case - Plaisir de France",
        "type": "edge-case",
    },
    {
        "id": "EDGE_005",
        "subdir": "casos-excepcionales",
        "filename": "The 45 King - Beat Suite One (Part Four).mp3",
        "description": "Edge case - The 45 King",
        "type": "edge-case",
    },
]


def build_expected(file_def, result):
    """
    Construye el bloque 'expected' basado en el tipo de archivo y resultado actual.
    """
    ftype = file_def["type"]
    expected = {}

    if result.error:
        expected["status"] = result.status
        return expected

    # Guardar siempre el status actual como baseline
    expected["status"] = result.status

    # Guardar detected_quality como lista aceptable
    expected["detected_quality_in"] = [result.detected_quality]

    # Cutoff ranges segun tipo
    cutoff = result.cutoff_frequency_khz

    if ftype == "legit":
        # Archivos legitimos: cutoff alto
        expected["cutoff_above_khz"] = max(cutoff - 1.5, 15.0)
    elif ftype in ("transcode", "fake-format"):
        # Transcodes: cutoff debe ser bajo
        expected["cutoff_below_khz"] = min(cutoff + 1.5, 20.0)
    elif ftype == "youtube-rip":
        # YouTube rips: generalmente cutoff bajo
        expected["cutoff_below_khz"] = min(cutoff + 1.5, 20.0)
    elif ftype == "edge-case":
        # Edge cases: rango mas amplio alrededor del resultado actual
        expected["cutoff_above_khz"] = max(cutoff - 2.0, 5.0)
        expected["cutoff_below_khz"] = min(cutoff + 2.0, 22.5)

    # Marcar incertidumbre si aplica
    if result.is_uncertain:
        expected["is_uncertain"] = True

    return expected


def main():
    analyzer = AudioAnalyzer()
    test_cases = []

    print("Generando baseline de tests...")
    print(f"Directorio de test files: {TEST_FILES_DIR}\n")

    for fdef in FILE_DEFS:
        filepath = os.path.join(TEST_FILES_DIR, fdef["subdir"], fdef["filename"])
        rel_path = os.path.relpath(filepath, PROJECT_ROOT)

        print(f"  [{fdef['id']}] {fdef['filename']}...", end="", flush=True)

        if not os.path.exists(filepath):
            print(" NO ENCONTRADO - skipping")
            continue

        try:
            result = analyzer.analyze_file(filepath)
            result.frequency_analysis = None

            expected = build_expected(fdef, result)

            tc = {
                "id": fdef["id"],
                "file": rel_path,
                "description": fdef["description"],
                "expected": expected,
                "known_bug": fdef.get("known_bug", False),
                "notes": fdef.get("notes", ""),
                "_baseline": {
                    "cutoff_khz": round(result.cutoff_frequency_khz, 2),
                    "status": result.status,
                    "quality": result.detected_quality,
                    "confidence": round(result.confidence, 3),
                    "is_uncertain": result.is_uncertain,
                    "details": result.details,
                },
            }

            test_cases.append(tc)
            print(f" OK ({result.cutoff_frequency_khz:.1f} kHz, {result.status})")

        except Exception as e:
            print(f" ERROR: {e}")

    # Guardar
    with open(OUTPUT, "w", encoding="utf-8") as f:
        json.dump(test_cases, f, indent=2, ensure_ascii=False)

    print(f"\n{len(test_cases)} test cases guardados en {OUTPUT}")


if __name__ == "__main__":
    main()
