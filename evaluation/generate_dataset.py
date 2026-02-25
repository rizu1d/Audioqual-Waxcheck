#!/usr/bin/env python3
"""
Genera un dataset de variantes de audio desde archivos lossless usando FFmpeg.

Uso:
    python evaluation/generate_dataset.py [--force]

Opciones:
    --force    Regenerar archivos existentes (por defecto se saltan)
"""
import argparse
import json
import os
import subprocess
import sys
import tempfile
from datetime import datetime

# Colores ANSI
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
BOLD = "\033[1m"
DIM = "\033[2m"
RESET = "\033[0m"

EVAL_DIR = os.path.dirname(os.path.abspath(__file__))
ORIGINALS_DIR = os.path.join(EVAL_DIR, "originals")
DATASET_DIR = os.path.join(EVAL_DIR, "dataset")

SUPPORTED_EXTENSIONS = {".wav", ".flac", ".aiff", ".aif"}

# Definicion de variantes: (sufijo, tipo, bitrate_original, bitrate_declared, expected)
VARIANTS = [
    {
        "suffix": "_legit_320k.mp3",
        "type": "legit",
        "bitrate_original": None,
        "bitrate_declared": 320,
        "expected_cutoff_range_khz": [19.5, 20.5],
        "expected_status": "OK",
        "expected_quality": "320kbps",
        "expected_level": "bueno",
    },
    {
        "suffix": "_legit_256k.mp3",
        "type": "legit",
        "bitrate_original": None,
        "bitrate_declared": 256,
        "expected_cutoff_range_khz": [18.5, 19.5],
        "expected_status": "OK",
        "expected_quality": "256kbps",
        "expected_level": "bueno",
    },
    {
        "suffix": "_legit_192k.mp3",
        "type": "legit",
        "bitrate_original": None,
        "bitrate_declared": 192,
        "expected_cutoff_range_khz": [17.0, 18.5],
        "expected_status": "OK",
        "expected_quality": "192kbps",
        "expected_level": "medio",
    },
    {
        "suffix": "_legit_128k.mp3",
        "type": "legit",
        "bitrate_original": None,
        "bitrate_declared": 128,
        "expected_cutoff_range_khz": [15.0, 16.0],
        "expected_status": "Baja calidad",
        "expected_quality": "128kbps",
        "expected_level": "bajo",
    },
    {
        "suffix": "_legit_96k.mp3",
        "type": "legit",
        "bitrate_original": None,
        "bitrate_declared": 96,
        "expected_cutoff_range_khz": [13.0, 15.0],
        "expected_status": "Baja calidad",
        "expected_quality": "96kbps",
        "expected_level": "bajo",
    },
    {
        "suffix": "_transcode_128to320.mp3",
        "type": "transcode",
        "bitrate_original": 128,
        "bitrate_declared": 320,
        "expected_cutoff_range_khz": [15.0, 16.0],
        "expected_status": "Transcode detectado",
        "expected_quality": "128kbps",
        "expected_level": "bajo",
    },
    {
        "suffix": "_transcode_96to320.mp3",
        "type": "transcode",
        "bitrate_original": 96,
        "bitrate_declared": 320,
        "expected_cutoff_range_khz": [13.0, 15.0],
        "expected_status": "Transcode detectado",
        "expected_quality": "96kbps",
        "expected_level": "bajo",
    },
    {
        "suffix": "_transcode_128to256.mp3",
        "type": "transcode",
        "bitrate_original": 128,
        "bitrate_declared": 256,
        "expected_cutoff_range_khz": [15.0, 16.0],
        "expected_status": "Transcode detectado",
        "expected_quality": "128kbps",
        "expected_level": "bajo",
    },
    {
        "suffix": "_transcode_192to320.mp3",
        "type": "transcode",
        "bitrate_original": 192,
        "bitrate_declared": 320,
        "expected_cutoff_range_khz": [17.0, 18.5],
        "expected_status": "Transcode detectado",
        "expected_quality": "192kbps",
        "expected_level": "medio",
    },
    {
        "suffix": "_transcode_yt_128to320.mp3",
        "type": "youtube",
        "bitrate_original": 128,
        "bitrate_declared": 320,
        "expected_cutoff_range_khz": [15.0, 16.0],
        "expected_status": "Transcode detectado",
        "expected_quality": "128kbps",
        "expected_level": "bajo",
    },
]


def check_ffmpeg():
    """Verifica que FFmpeg esta instalado."""
    try:
        subprocess.run(
            ["ffmpeg", "-version"],
            capture_output=True,
            timeout=10,
        )
        return True
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def get_source_files():
    """Encuentra archivos lossless en originals/."""
    if not os.path.exists(ORIGINALS_DIR):
        return []

    files = []
    for name in sorted(os.listdir(ORIGINALS_DIR)):
        ext = os.path.splitext(name)[1].lower()
        if ext in SUPPORTED_EXTENSIONS:
            files.append(name)
    return files


def run_ffmpeg(args, timeout=120):
    """Ejecuta un comando FFmpeg."""
    cmd = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error"] + args
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    if result.returncode != 0:
        raise RuntimeError(f"FFmpeg error: {result.stderr.strip()}")


def generate_legit(source_path, output_path, bitrate_kbps):
    """Genera una variante legitima (lossless -> MP3 directo)."""
    run_ffmpeg([
        "-i", source_path,
        "-c:a", "libmp3lame",
        "-b:a", f"{bitrate_kbps}k",
        output_path,
    ])


def generate_transcode(source_path, output_path, original_bitrate, target_bitrate):
    """Genera un transcode (lossless -> bitrate bajo -> bitrate alto)."""
    with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp:
        tmp_path = tmp.name

    try:
        # Paso 1: lossless -> bitrate bajo
        run_ffmpeg([
            "-i", source_path,
            "-c:a", "libmp3lame",
            "-b:a", f"{original_bitrate}k",
            tmp_path,
        ])
        # Paso 2: bitrate bajo -> bitrate alto
        run_ffmpeg([
            "-i", tmp_path,
            "-c:a", "libmp3lame",
            "-b:a", f"{target_bitrate}k",
            output_path,
        ])
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)


def generate_youtube_rip(source_path, output_path, aac_bitrate, mp3_bitrate):
    """Genera un YouTube rip (lossless -> AAC -> MP3)."""
    with tempfile.NamedTemporaryFile(suffix=".m4a", delete=False) as tmp:
        tmp_path = tmp.name

    try:
        # Paso 1: lossless -> AAC
        run_ffmpeg([
            "-i", source_path,
            "-c:a", "aac",
            "-b:a", f"{aac_bitrate}k",
            tmp_path,
        ])
        # Paso 2: AAC -> MP3
        run_ffmpeg([
            "-i", tmp_path,
            "-c:a", "libmp3lame",
            "-b:a", f"{mp3_bitrate}k",
            output_path,
        ])
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)


def generate_variant(source_path, source_name, variant, force=False):
    """Genera una variante individual.

    Returns:
        (output_path, subfolder, skipped) — skipped=True si ya existia y no se regenero
    """
    stem = os.path.splitext(source_name)[0]
    subfolder = stem
    output_name = stem + variant["suffix"]
    subfolder_path = os.path.join(DATASET_DIR, subfolder)
    os.makedirs(subfolder_path, exist_ok=True)
    output_path = os.path.join(subfolder_path, output_name)

    if os.path.exists(output_path) and not force:
        return output_path, subfolder, True

    vtype = variant["type"]
    bitrate_declared = variant["bitrate_declared"]
    bitrate_original = variant["bitrate_original"]

    if vtype == "legit":
        generate_legit(source_path, output_path, bitrate_declared)
    elif vtype == "transcode":
        generate_transcode(source_path, output_path, bitrate_original, bitrate_declared)
    elif vtype == "youtube":
        generate_youtube_rip(source_path, output_path, bitrate_original, bitrate_declared)

    return output_path, subfolder, False


def write_manifest(source_files, all_entries):
    """Escribe el manifest.json."""
    manifest = {
        "generated_at": datetime.now().isoformat(),
        "source_files": source_files,
        "total_variants": len(all_entries),
        "files": all_entries,
    }

    manifest_path = os.path.join(DATASET_DIR, "manifest.json")
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)

    return manifest_path


def main():
    parser = argparse.ArgumentParser(description="Genera dataset de variantes de audio")
    parser.add_argument("--force", action="store_true", help="Regenerar archivos existentes")
    args = parser.parse_args()

    print(f"\n{BOLD}{'=' * 60}{RESET}")
    print(f"{BOLD}  AudioQual — Generador de Dataset{RESET}")
    print(f"{'=' * 60}\n")

    # Verificar FFmpeg
    if not check_ffmpeg():
        print(f"{RED}Error: FFmpeg no encontrado. Instalalo con: brew install ffmpeg{RESET}")
        sys.exit(1)

    # Buscar archivos fuente
    source_files = get_source_files()
    if not source_files:
        print(f"{RED}Error: No hay archivos lossless en {ORIGINALS_DIR}/{RESET}")
        print(f"Copia archivos WAV o FLAC a esa carpeta e intentalo de nuevo.")
        sys.exit(1)

    print(f"Archivos fuente: {CYAN}{len(source_files)}{RESET}")
    for name in source_files:
        print(f"  - {name}")

    total_variants = len(source_files) * len(VARIANTS)
    print(f"\nVariantes a generar: {CYAN}{total_variants}{RESET} ({len(VARIANTS)} por archivo)")

    # Crear directorio de salida
    os.makedirs(DATASET_DIR, exist_ok=True)

    # Generar variantes
    all_entries = []
    generated = 0
    skipped = 0
    errors = 0

    for source_name in source_files:
        source_path = os.path.join(ORIGINALS_DIR, source_name)
        print(f"\n{BOLD}{source_name}:{RESET}")

        for variant in VARIANTS:
            label = variant["suffix"].replace("_", " ").strip()
            print(f"  {label}...", end="", flush=True)

            try:
                output_path, subfolder, was_skipped = generate_variant(
                    source_path, source_name, variant, args.force
                )

                if was_skipped:
                    print(f" {YELLOW}SKIP{RESET} (ya existe)")
                    skipped += 1
                else:
                    print(f" {GREEN}OK{RESET}")
                    generated += 1

                # Ruta relativa dentro de dataset/ (subfolder/filename)
                output_name = os.path.basename(output_path)
                relative_path = os.path.join(subfolder, output_name)
                all_entries.append({
                    "filename": relative_path,
                    "source": source_name,
                    "type": variant["type"],
                    "bitrate_original": variant["bitrate_original"],
                    "bitrate_declared": variant["bitrate_declared"],
                    "expected_cutoff_range_khz": variant["expected_cutoff_range_khz"],
                    "expected_status": variant["expected_status"],
                    "expected_quality": variant["expected_quality"],
                    "expected_level": variant["expected_level"],
                })

            except Exception as e:
                print(f" {RED}ERROR: {e}{RESET}")
                errors += 1

    # Escribir manifest
    manifest_path = write_manifest([s for s in source_files], all_entries)

    # Resumen
    print(f"\n{'=' * 60}")
    print(f"{BOLD}Resumen{RESET}")
    print(f"  {GREEN}Generados: {generated}{RESET}")
    if skipped:
        print(f"  {YELLOW}Saltados:  {skipped} (usa --force para regenerar){RESET}")
    if errors:
        print(f"  {RED}Errores:   {errors}{RESET}")
    print(f"  Manifest: {DIM}{manifest_path}{RESET}")
    print()


if __name__ == "__main__":
    main()
