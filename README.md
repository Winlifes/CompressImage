# CompressImage

[English](./README.md) | [简体中文](./README.zh-CN.md)

A lightweight desktop tool built with Python + Tkinter for:

- Image compression
- File compression
- File hash calculation (`MD5 / SHA1 / SHA256`)
- MD5 modification (change file MD5 without affecting visible content)

## Features

### 1. Image Compression

- Supports `JPG / PNG / WEBP / BMP / TIFF`
- Supports selecting a whole image folder
- Supports recursive batch processing for subfolders
- Keeps the original file name after compression
- Output format options: `Keep Original / JPEG / WEBP / PNG`
- Adjustable quality for lossy formats
- PNG modes: `Standard PNG` and `Tinify-like PNG`
- Single-file mode outputs to `compressed_output` next to the source image
- Folder mode outputs to `compressed_output` under the selected folder while preserving relative structure
- Built-in thumbnail preview for the first few selected images

### 2. File Compression

- Supports selecting a whole folder
- Supports recursive file collection before archiving
- Supports `zip`
- Supports `tar.gz`
- Supports `tar.xz`
- Supports single-file `gz`
- Folder mode preserves directory structure inside the archive

### 3. Hash Calculation

- Calculate `MD5`
- Calculate `SHA1`
- Calculate `SHA256`

### 4. MD5 Modification

- Change the MD5 hash of any file without affecting its visible content
- Appends random bytes to a copy of the file
- Supports batch processing and folder recursion
- Preserves directory structure in the output `md5_modified` folder
- Displays before and after MD5 values

## UI Highlights

- Dark header with status cards
- Clear tab-based workflow
- Scrollable result logs
- Bottom status bar for current progress
- Drag and drop support for files and folders

## Drag & Drop

- `tkinterdnd2` is included in `requirements.txt`
- Reinstall dependencies once before first use if needed

## Tinify-like PNG Mode

- Uses `imagequant` for 256-color palette quantization
- Uses no dithering by default to better match the tested Tinify PNG samples
- Uses a fixed quantization quality range of `40~90`
- Runs an extra PNG optimization pass with `zopfli` when available
- Falls back to standard PNG compression automatically if dependencies are missing

## Run

Install dependencies:

```bash
python3 -m pip install -r requirements.txt
```

Start the app:

```bash
python3 app.py
```

## Possible Next Improvements

- Better drag-hover effects
- Image resize options
- Lossless/lossy WebP switch
- Export hash lists to text files
- Package as macOS / Windows desktop app
