# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

CompressImage is a Python/Tkinter desktop app providing three utilities: image compression, file/folder archiving, and file hash calculation. The UI is in Chinese; code uses English identifiers.

## Running the App

```bash
python3 -m pip install -r requirements.txt
python3 app.py
```

There are no tests, linting, or build steps configured.

## Architecture

The entire application lives in a single file: **`app.py`** (~737 lines).

### Structure within `app.py`

1. **Imports & optional dependency checks** (top) — `tkinterdnd2`, `imagequant`, and `zopfli` are optional; the app degrades gracefully if missing.
2. **Utility functions** (lines ~45–112) — `format_size`, `hash_file`, `compress_single_file_gz`, `save_png_standard`, `save_png_tinify_like`, `find_image_files`, `find_regular_files`, `infer_base_dir`.
3. **`CompressApp` class** (lines ~115–727) — the monolithic Tkinter application class:
   - **UI construction**: `_configure_styles()`, `_build_layout()`, `_build_image_tab()`, `_build_archive_tab()`, `_build_hash_tab()`
   - **File selection & drag-drop**: `choose_images()`, `choose_files()`, `handle_drop()` and tab-specific drop handlers
   - **Image compression**: `compress_images()` → `_save_compressed_image()` with format resolution and PNG mode handling
   - **File archiving**: `compress_files()` → `_create_archive()` supporting ZIP, TAR.GZ, TAR.XZ, GZ
   - **Hash calculation**: `calculate_hashes()` using streaming 1MB chunks

### Key constants

- `IMAGE_EXTENSIONS`: `.jpg`, `.jpeg`, `.png`, `.webp`, `.bmp`, `.tiff`
- PNG modes: standard (PIL optimize) and Tinify-like (imagequant 256-color quantization + optional zopfli)
- Dark theme colors: background `#0f172a`, accent `#2563eb`, cards `#111827`

## Dependencies

- **Pillow** — image processing (required)
- **tkinterdnd2** — drag-and-drop support (optional, app works without it)
- **imagequant** + **zopfli** — Tinify-like PNG compression mode (optional)

## Conventions

- Modern Python 3 style: type hints, f-strings, walrus operators
- Snake_case for functions/variables, CamelCase for the class
- All user-facing strings are in Chinese
- Errors shown via `messagebox` dialogs with Chinese text
