from __future__ import annotations

import gzip
import hashlib
import os
import tarfile
import zipfile
from io import BytesIO
from pathlib import Path
from tkinter import END, BooleanVar, StringVar, Tk, filedialog, messagebox, ttk
from tkinter.scrolledtext import ScrolledText

from PIL import Image, ImageTk

try:
    from tkinterdnd2 import DND_FILES, TkinterDnD
except ImportError:
    DND_FILES = None
    TkinterDnD = None

try:
    import imagequant
except ImportError:
    imagequant = None

try:
    import zopfli.png as zopfli_png
except ImportError:
    zopfli_png = None


IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tiff"}
THUMBNAIL_SIZE = (120, 120)
PREVIEW_LIMIT = 8
PNG_STANDARD_MODE = "标准 PNG"
PNG_TINIFY_MODE = "Tinify-like PNG"
TINIFY_LIKE_PARAMS = {
    "max_colors": 256,
    "dithering_level": 0.0,
    "min_quality": 40,
    "max_quality": 90,
}


def format_size(size: int) -> str:
    units = ["B", "KB", "MB", "GB", "TB"]
    value = float(size)
    for unit in units:
        if value < 1024 or unit == units[-1]:
            return f"{value:.2f} {unit}"
        value /= 1024
    return f"{size} B"


def hash_file(file_path: Path, algorithm: str) -> str:
    hasher = hashlib.new(algorithm)
    with file_path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            hasher.update(chunk)
    return hasher.hexdigest()


def compress_single_file_gz(source: Path, target: Path) -> None:
    with source.open("rb") as src, gzip.open(target, "wb", compresslevel=9) as dst:
        while chunk := src.read(1024 * 1024):
            dst.write(chunk)


def save_png_standard(image: Image.Image, output_path: Path) -> None:
    image.save(output_path, format="PNG", optimize=True, compress_level=9)


def save_png_tinify_like(image: Image.Image, output_path: Path) -> None:
    if imagequant is None:
        raise RuntimeError("缺少 imagequant 依赖，无法启用 Tinify-like PNG 模式。")

    rgba_image = image.convert("RGBA")
    quantized = imagequant.quantize_pil_image(
        rgba_image,
        dithering_level=TINIFY_LIKE_PARAMS["dithering_level"],
        max_colors=TINIFY_LIKE_PARAMS["max_colors"],
        min_quality=TINIFY_LIKE_PARAMS["min_quality"],
        max_quality=TINIFY_LIKE_PARAMS["max_quality"],
    )

    buffer = BytesIO()
    quantized.save(buffer, format="PNG", optimize=True, compress_level=9)
    png_data = buffer.getvalue()
    if zopfli_png is not None:
        png_data = zopfli_png.optimize(png_data, num_iterations=8, num_iterations_large=3)
    output_path.write_bytes(png_data)


def find_image_files(folder: Path, recursive: bool = True) -> list[Path]:
    iterator = folder.rglob("*") if recursive else folder.glob("*")
    return sorted(path for path in iterator if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS)


def find_regular_files(folder: Path, recursive: bool = True) -> list[Path]:
    iterator = folder.rglob("*") if recursive else folder.glob("*")
    return sorted(path for path in iterator if path.is_file())


def infer_base_dir(collected_files: list[Path], dropped_paths: list[Path]) -> Path | None:
    if len(dropped_paths) == 1 and dropped_paths[0].is_dir():
        return dropped_paths[0]
    if len(collected_files) == 1:
        return collected_files[0].parent
    if collected_files:
        common = Path(os.path.commonpath([str(path) for path in collected_files]))
        return common if common.is_dir() else common.parent
    return None


def modify_file_md5(source: Path, output: Path) -> tuple[str, str]:
    """复制文件并追加随机字节以改变 MD5，返回 (原始MD5, 新MD5)。"""
    original_md5 = hash_file(source, "md5")
    data = source.read_bytes()
    output.write_bytes(data + os.urandom(16))
    new_md5 = hash_file(output, "md5")
    return original_md5, new_md5


class CompressApp:
    def __init__(self, root: Tk) -> None:
        self.root = root
        self.root.title("压缩工具箱 Pro")
        self.root.geometry("1080x820")
        self.root.minsize(920, 720)

        self.image_files: list[Path] = []
        self.image_base_dir: Path | None = None
        self.file_items: list[Path] = []
        self.file_base_dir: Path | None = None
        self.hash_file_path: Path | None = None
        self.md5_files: list[Path] = []
        self.md5_base_dir: Path | None = None
        self.thumbnail_refs: list[ImageTk.PhotoImage] = []

        self.image_quality = StringVar(value="80")
        self.image_output_format = StringVar(value="保持原格式")
        self.png_mode = StringVar(
            value=PNG_TINIFY_MODE if imagequant is not None else PNG_STANDARD_MODE
        )
        self.archive_format = StringVar(value="zip")
        self.image_recursive = BooleanVar(value=True)
        self.file_recursive = BooleanVar(value=True)
        self.status_text = StringVar(value="准备就绪")
        self.drag_hint = StringVar(
            value="将文件或文件夹拖到窗口中；会按当前页签自动分发到图片压缩、文件压缩或哈希计算。"
        )

        self._configure_styles()
        self._build_layout()
        self._enable_drag_drop()

    def _configure_styles(self) -> None:
        self.root.configure(bg="#0f172a")
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except Exception:
            pass

        style.configure(".", font=("SF Pro Text", 12))
        style.configure("App.TFrame", background="#0f172a")
        style.configure("Card.TFrame", background="#111827")
        style.configure("Drop.TFrame", background="#1e293b")
        style.configure("Panel.TFrame", background="#ffffff")
        style.configure("Preview.TFrame", background="#f8fafc")
        style.configure("Preview.TLabel", background="#f8fafc")
        style.configure("HeroTitle.TLabel", background="#0f172a", foreground="#f8fafc", font=("SF Pro Display", 24, "bold"))
        style.configure("HeroSub.TLabel", background="#0f172a", foreground="#cbd5e1", font=("SF Pro Text", 12))
        style.configure("DropTitle.TLabel", background="#1e293b", foreground="#f8fafc", font=("SF Pro Display", 13, "bold"))
        style.configure("DropText.TLabel", background="#1e293b", foreground="#bfdbfe", font=("SF Pro Text", 11))
        style.configure("CardTitle.TLabel", background="#111827", foreground="#f8fafc", font=("SF Pro Display", 14, "bold"))
        style.configure("CardValue.TLabel", background="#111827", foreground="#60a5fa", font=("SF Pro Display", 16, "bold"))
        style.configure("PanelTitle.TLabel", background="#ffffff", foreground="#0f172a", font=("SF Pro Display", 13, "bold"))
        style.configure("PanelText.TLabel", background="#ffffff", foreground="#475569", font=("SF Pro Text", 11))
        style.configure("PreviewTitle.TLabel", background="#f8fafc", foreground="#0f172a", font=("SF Pro Display", 12, "bold"))
        style.configure("PreviewText.TLabel", background="#f8fafc", foreground="#64748b", font=("SF Pro Text", 10))
        style.configure("PreviewName.TLabel", background="#f8fafc", foreground="#1e293b", font=("SF Pro Text", 10, "bold"))
        style.configure("Status.TLabel", background="#0f172a", foreground="#93c5fd", font=("SF Pro Text", 11))
        style.configure("Primary.TButton", font=("SF Pro Text", 11, "bold"), padding=(14, 10), foreground="#ffffff", background="#2563eb", borderwidth=0)
        style.map("Primary.TButton", background=[("active", "#1d4ed8")])
        style.configure("Secondary.TButton", font=("SF Pro Text", 11), padding=(12, 9), foreground="#0f172a", background="#e2e8f0", borderwidth=0)
        style.map("Secondary.TButton", background=[("active", "#cbd5e1")])
        style.configure("TNotebook", background="#0f172a", borderwidth=0)
        style.configure("TNotebook.Tab", padding=(18, 10), font=("SF Pro Text", 11, "bold"))
        style.map("TNotebook.Tab", background=[("selected", "#ffffff")], foreground=[("selected", "#0f172a")])
        style.configure("TCheckbutton", background="#ffffff", foreground="#334155")
        style.configure("TCombobox", padding=6)

    def _build_layout(self) -> None:
        app = ttk.Frame(self.root, style="App.TFrame", padding=18)
        app.pack(fill="both", expand=True)

        header = ttk.Frame(app, style="App.TFrame")
        header.pack(fill="x")
        ttk.Label(header, text="压缩工具箱 Pro", style="HeroTitle.TLabel").pack(anchor="w")
        ttk.Label(
            header,
            text="更好看的桌面界面，支持图片压缩、文件归档、哈希计算，以及整个文件夹的批量处理。",
            style="HeroSub.TLabel",
        ).pack(anchor="w", pady=(4, 14))

        drop_banner = ttk.Frame(app, style="Drop.TFrame", padding=14)
        drop_banner.pack(fill="x", pady=(0, 14))
        ttk.Label(drop_banner, text="拖拽上传", style="DropTitle.TLabel").pack(anchor="w")
        self.drop_banner_text = ttk.Label(drop_banner, textvariable=self.drag_hint, style="DropText.TLabel", wraplength=980)
        self.drop_banner_text.pack(anchor="w", pady=(4, 0))

        stats = ttk.Frame(app, style="App.TFrame")
        stats.pack(fill="x", pady=(0, 14))
        self._build_stat_card(stats, "图片源", "未选择", 0)
        self._build_stat_card(stats, "归档源", "未选择", 1)
        self._build_stat_card(stats, "当前状态", "准备就绪", 2)

        self.notebook = ttk.Notebook(app)
        self.notebook.pack(fill="both", expand=True)

        self.image_log = self._build_image_tab(self.notebook)
        self.archive_log = self._build_archive_tab(self.notebook)
        self.hash_output = self._build_hash_tab(self.notebook)
        self.md5_log = self._build_md5_modify_tab(self.notebook)

        footer = ttk.Frame(app, style="App.TFrame")
        footer.pack(fill="x", pady=(10, 0))
        ttk.Label(footer, textvariable=self.status_text, style="Status.TLabel").pack(anchor="w")

    def _build_stat_card(self, parent: ttk.Frame, title: str, value: str, column: int) -> None:
        card = ttk.Frame(parent, style="Card.TFrame", padding=14)
        card.grid(row=0, column=column, sticky="nsew", padx=(0, 12) if column < 2 else 0)
        parent.columnconfigure(column, weight=1)

        value_var = StringVar(value=value)
        ttk.Label(card, text=title, style="CardTitle.TLabel").pack(anchor="w")
        ttk.Label(card, textvariable=value_var, style="CardValue.TLabel").pack(anchor="w", pady=(8, 0))

        if column == 0:
            self.image_stat = value_var
        elif column == 1:
            self.archive_stat = value_var
        else:
            self.run_stat = value_var

    def _build_panel(self, notebook: ttk.Notebook, title: str, note: str) -> ttk.Frame:
        panel = ttk.Frame(notebook, style="Panel.TFrame", padding=18)
        notebook.add(panel, text=title)
        ttk.Label(panel, text=title, style="PanelTitle.TLabel").pack(anchor="w")
        ttk.Label(panel, text=note, style="PanelText.TLabel", wraplength=940).pack(anchor="w", pady=(4, 14))
        return panel

    def _build_image_tab(self, notebook: ttk.Notebook) -> ScrolledText:
        panel = self._build_panel(
            notebook,
            "图片压缩",
            "支持选多张图片，也支持直接选整个图片文件夹递归压缩。压缩后保留原文件名，输出到对应目录下的 compressed_output 文件夹。",
        )

        source_row = ttk.Frame(panel, style="Panel.TFrame")
        source_row.pack(fill="x", pady=(0, 12))
        ttk.Button(source_row, text="选择图片", style="Secondary.TButton", command=self.choose_images).pack(side="left")
        ttk.Button(source_row, text="选择图片文件夹", style="Secondary.TButton", command=self.choose_image_folder).pack(side="left", padx=8)
        ttk.Checkbutton(source_row, text="递归扫描子文件夹", variable=self.image_recursive).pack(side="left", padx=10)

        self.image_summary = StringVar(value="未选择图片或文件夹")
        ttk.Label(panel, textvariable=self.image_summary, style="PanelText.TLabel").pack(anchor="w")

        options_row = ttk.Frame(panel, style="Panel.TFrame")
        options_row.pack(fill="x", pady=(12, 12))
        ttk.Label(options_row, text="压缩质量", style="PanelText.TLabel").pack(side="left")
        ttk.Combobox(
            options_row,
            textvariable=self.image_quality,
            values=["95", "90", "85", "80", "75", "70", "60", "50"],
            width=8,
            state="readonly",
        ).pack(side="left", padx=(8, 18))
        ttk.Label(options_row, text="输出格式", style="PanelText.TLabel").pack(side="left")
        ttk.Combobox(
            options_row,
            textvariable=self.image_output_format,
            values=["保持原格式", "JPEG", "WEBP", "PNG"],
            width=12,
            state="readonly",
        ).pack(side="left", padx=8)
        ttk.Label(options_row, text="PNG 模式", style="PanelText.TLabel").pack(side="left", padx=(18, 0))
        ttk.Combobox(
            options_row,
            textvariable=self.png_mode,
            values=[PNG_STANDARD_MODE, PNG_TINIFY_MODE],
            width=16,
            state="readonly",
        ).pack(side="left", padx=8)
        ttk.Button(options_row, text="开始压缩", style="Primary.TButton", command=self.compress_images).pack(side="right")

        self.png_mode_note = StringVar()
        self._refresh_png_mode_note()
        ttk.Label(panel, textvariable=self.png_mode_note, style="PanelText.TLabel").pack(anchor="w", pady=(0, 10))

        preview_panel = ttk.Frame(panel, style="Preview.TFrame", padding=12)
        preview_panel.pack(fill="x", pady=(0, 12))
        ttk.Label(preview_panel, text="图片预览", style="PreviewTitle.TLabel").pack(anchor="w")
        self.preview_summary = StringVar(value="选择图片后会在这里显示缩略图")
        ttk.Label(preview_panel, textvariable=self.preview_summary, style="PreviewText.TLabel").pack(anchor="w", pady=(4, 10))
        self.preview_grid = ttk.Frame(preview_panel, style="Preview.TFrame")
        self.preview_grid.pack(fill="x")

        log = self._make_log(panel)
        return log

    def _build_archive_tab(self, notebook: ttk.Notebook) -> ScrolledText:
        panel = self._build_panel(
            notebook,
            "文件压缩",
            "支持多文件归档，也支持直接选择整个文件夹打包。文件夹模式下会保留目录结构。",
        )

        source_row = ttk.Frame(panel, style="Panel.TFrame")
        source_row.pack(fill="x", pady=(0, 12))
        ttk.Button(source_row, text="选择文件", style="Secondary.TButton", command=self.choose_files).pack(side="left")
        ttk.Button(source_row, text="选择文件夹", style="Secondary.TButton", command=self.choose_file_folder).pack(side="left", padx=8)
        ttk.Checkbutton(source_row, text="递归扫描子文件夹", variable=self.file_recursive).pack(side="left", padx=10)

        self.file_summary = StringVar(value="未选择文件或文件夹")
        ttk.Label(panel, textvariable=self.file_summary, style="PanelText.TLabel").pack(anchor="w")

        options_row = ttk.Frame(panel, style="Panel.TFrame")
        options_row.pack(fill="x", pady=(12, 12))
        ttk.Label(options_row, text="压缩格式", style="PanelText.TLabel").pack(side="left")
        ttk.Combobox(
            options_row,
            textvariable=self.archive_format,
            values=["zip", "tar.gz", "tar.xz", "gz(单文件)"],
            width=12,
            state="readonly",
        ).pack(side="left", padx=8)
        ttk.Button(options_row, text="开始归档", style="Primary.TButton", command=self.compress_files).pack(side="right")

        log = self._make_log(panel)
        return log

    def _build_hash_tab(self, notebook: ttk.Notebook) -> ScrolledText:
        panel = self._build_panel(
            notebook,
            "哈希计算",
            "提供 MD5 / SHA1 / SHA256 校验值计算，方便做文件校验或整理记录。",
        )

        source_row = ttk.Frame(panel, style="Panel.TFrame")
        source_row.pack(fill="x", pady=(0, 12))
        ttk.Button(source_row, text="选择文件", style="Secondary.TButton", command=self.choose_hash_file).pack(side="left")
        ttk.Button(source_row, text="计算哈希", style="Primary.TButton", command=self.calculate_hashes).pack(side="right")

        self.hash_summary = StringVar(value="未选择文件")
        ttk.Label(panel, textvariable=self.hash_summary, style="PanelText.TLabel").pack(anchor="w")

        output = self._make_log(panel)
        return output

    def _build_md5_modify_tab(self, notebook: ttk.Notebook) -> ScrolledText:
        panel = self._build_panel(
            notebook,
            "MD5 改写",
            "在不影响文件内容显示的前提下修改其 MD5 值。输出到同目录下的 md5_modified 文件夹。",
        )

        source_row = ttk.Frame(panel, style="Panel.TFrame")
        source_row.pack(fill="x", pady=(0, 12))
        ttk.Button(source_row, text="选择文件", style="Secondary.TButton", command=self.choose_md5_files).pack(side="left")
        ttk.Button(source_row, text="选择文件夹", style="Secondary.TButton", command=self.choose_md5_folder).pack(side="left", padx=8)
        ttk.Checkbutton(source_row, text="递归扫描子文件夹", variable=self.file_recursive).pack(side="left", padx=10)

        self.md5_summary = StringVar(value="未选择文件")
        ttk.Label(panel, textvariable=self.md5_summary, style="PanelText.TLabel").pack(anchor="w")

        action_row = ttk.Frame(panel, style="Panel.TFrame")
        action_row.pack(fill="x", pady=(12, 12))
        ttk.Button(action_row, text="开始处理", style="Primary.TButton", command=self.modify_file_md5s).pack(side="right")

        log = self._make_log(panel)
        return log

    def _make_log(self, parent: ttk.Frame) -> ScrolledText:
        log = ScrolledText(
            parent,
            height=20,
            font=("SF Mono", 11),
            bg="#0f172a",
            fg="#e2e8f0",
            insertbackground="#f8fafc",
            relief="flat",
            padx=12,
            pady=12,
        )
        log.pack(fill="both", expand=True)
        return log

    def _enable_drag_drop(self) -> None:
        if not DND_FILES:
            self.drag_hint.set("拖拽功能需要安装 `tkinterdnd2`；当前仍可用按钮选择文件或文件夹。")
            return

        for widget in [self.root, self.drop_banner_text]:
            widget.drop_target_register(DND_FILES)
            widget.dnd_bind("<<Drop>>", self.handle_drop)

    def _set_status(self, message: str) -> None:
        self.status_text.set(message)
        self.run_stat.set(message)

    def _refresh_png_mode_note(self) -> None:
        if imagequant is None:
            self.png_mode_note.set("`Tinify-like PNG` 需要安装 `imagequant`；当前会自动使用标准 PNG 压缩。")
            return
        if zopfli_png is None:
            self.png_mode_note.set("当前可用 `imagequant` 调色板量化；未检测到 `zopfli` 时会跳过后置 PNG 深度优化。")
            return
        self.png_mode_note.set("`Tinify-like PNG` 使用 256 色量化、无抖动、质量 40~90，并追加 zopfli 优化。")

    def choose_images(self) -> None:
        selected = filedialog.askopenfilenames(
            title="选择图片",
            filetypes=[("Image Files", "*.jpg *.jpeg *.png *.webp *.bmp *.tiff"), ("All Files", "*.*")],
        )
        self._apply_image_selection([Path(item) for item in selected], base_dir=None)

    def choose_image_folder(self) -> None:
        selected = filedialog.askdirectory(title="选择图片文件夹")
        if not selected:
            return

        folder = Path(selected)
        images = find_image_files(folder, recursive=self.image_recursive.get())
        self._apply_image_selection(images, base_dir=folder, source_label=f"文件夹 {folder.name}")

    def choose_files(self) -> None:
        selected = filedialog.askopenfilenames(title="选择文件", filetypes=[("All Files", "*.*")])
        self._apply_file_selection([Path(item) for item in selected], base_dir=None)

    def choose_file_folder(self) -> None:
        selected = filedialog.askdirectory(title="选择文件夹")
        if not selected:
            return

        folder = Path(selected)
        files = find_regular_files(folder, recursive=self.file_recursive.get())
        self._apply_file_selection(files, base_dir=folder, source_label=f"文件夹 {folder.name}")

    def choose_hash_file(self) -> None:
        selected = filedialog.askopenfilename(title="选择文件", filetypes=[("All Files", "*.*")])
        self.hash_file_path = Path(selected) if selected else None
        if self.hash_file_path:
            self.hash_summary.set(str(self.hash_file_path))
            self._set_status("已选择哈希文件")
        else:
            self.hash_summary.set("未选择文件")

    def _apply_image_selection(self, image_files: list[Path], base_dir: Path | None, source_label: str | None = None) -> None:
        self.image_files = sorted(image_files)
        self.image_base_dir = base_dir
        if self.image_files:
            label = source_label or "已选择图片"
            self.image_summary.set(f"{label}，共 {len(self.image_files)} 张")
            self.image_stat.set(f"{len(self.image_files)} 张")
            self._set_status("已载入图片列表")
        else:
            self.image_summary.set("未选择图片或文件夹")
            self.image_stat.set("未选择")
        self.refresh_preview()

    def _apply_file_selection(self, files: list[Path], base_dir: Path | None, source_label: str | None = None) -> None:
        self.file_items = sorted(files)
        self.file_base_dir = base_dir
        if self.file_items:
            label = source_label or "已选择文件"
            self.file_summary.set(f"{label}，共 {len(self.file_items)} 个")
            self.archive_stat.set(f"{len(self.file_items)} 个")
            self._set_status("已载入归档文件列表")
        else:
            self.file_summary.set("未选择文件或文件夹")
            self.archive_stat.set("未选择")

    def refresh_preview(self) -> None:
        for child in self.preview_grid.winfo_children():
            child.destroy()
        self.thumbnail_refs.clear()

        if not self.image_files:
            self.preview_summary.set("选择图片后会在这里显示缩略图")
            return

        self.preview_summary.set(f"预览前 {min(len(self.image_files), PREVIEW_LIMIT)} 张图片")
        for index, image_path in enumerate(self.image_files[:PREVIEW_LIMIT]):
            card = ttk.Frame(self.preview_grid, style="Preview.TFrame", padding=8)
            row, column = divmod(index, 4)
            card.grid(row=row, column=column, padx=6, pady=6, sticky="nw")

            try:
                with Image.open(image_path) as image:
                    thumbnail = image.copy()
                    thumbnail.thumbnail(THUMBNAIL_SIZE)
                    photo = ImageTk.PhotoImage(thumbnail)
                    self.thumbnail_refs.append(photo)

                    ttk.Label(card, image=photo, style="Preview.TLabel").pack(anchor="center")
                    ttk.Label(card, text=image_path.name, style="PreviewName.TLabel", width=18).pack(anchor="w", pady=(8, 2))
                    meta = f"{image.width}×{image.height} · {format_size(image_path.stat().st_size)}"
                    ttk.Label(card, text=meta, style="PreviewText.TLabel").pack(anchor="w")
            except Exception:
                ttk.Label(card, text=image_path.name, style="PreviewName.TLabel", width=18).pack(anchor="w")
                ttk.Label(card, text="无法生成缩略图", style="PreviewText.TLabel").pack(anchor="w", pady=(6, 0))

    def handle_drop(self, event) -> str:
        paths = [Path(item) for item in self.root.tk.splitlist(event.data)]
        selected_tab = self.notebook.tab(self.notebook.select(), "text")

        if selected_tab == "图片压缩":
            self._handle_image_drop(paths)
        elif selected_tab == "文件压缩":
            self._handle_file_drop(paths)
        elif selected_tab == "MD5 改写":
            self._handle_md5_drop(paths)
        else:
            self._handle_hash_drop(paths)
        return "break"

    def _handle_image_drop(self, paths: list[Path]) -> None:
        images: list[Path] = []
        for path in paths:
            if path.is_dir():
                images.extend(find_image_files(path, recursive=self.image_recursive.get()))
            elif path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS:
                images.append(path)

        if not images:
            messagebox.showwarning("提示", "拖入的内容里没有可处理的图片。")
            return

        base_dir = infer_base_dir(images, paths)
        self._apply_image_selection(images, base_dir=base_dir, source_label="拖拽导入")
        self._set_status("已通过拖拽载入图片")

    def _handle_file_drop(self, paths: list[Path]) -> None:
        files: list[Path] = []
        for path in paths:
            if path.is_dir():
                files.extend(find_regular_files(path, recursive=self.file_recursive.get()))
            elif path.is_file():
                files.append(path)

        if not files:
            messagebox.showwarning("提示", "拖入的内容里没有可归档的文件。")
            return

        base_dir = infer_base_dir(files, paths)
        self._apply_file_selection(files, base_dir=base_dir, source_label="拖拽导入")
        self._set_status("已通过拖拽载入归档文件")

    def _handle_hash_drop(self, paths: list[Path]) -> None:
        target = next((path for path in paths if path.is_file()), None)
        if not target:
            messagebox.showwarning("提示", "哈希计算页只能接收单个文件。")
            return
        self.hash_file_path = target
        self.hash_summary.set(str(target))
        self._set_status("已通过拖拽选择哈希文件")

    def _handle_md5_drop(self, paths: list[Path]) -> None:
        files: list[Path] = []
        for path in paths:
            if path.is_dir():
                files.extend(find_regular_files(path, recursive=self.file_recursive.get()))
            elif path.is_file():
                files.append(path)

        if not files:
            messagebox.showwarning("提示", "拖入的内容里没有可处理的文件。")
            return

        base_dir = infer_base_dir(files, paths)
        self._apply_md5_selection(files, base_dir=base_dir, source_label="拖拽导入")
        self._set_status("已通过拖拽载入 MD5 改写文件")

    def choose_md5_files(self) -> None:
        selected = filedialog.askopenfilenames(title="选择文件", filetypes=[("All Files", "*.*")])
        self._apply_md5_selection([Path(item) for item in selected], base_dir=None)

    def choose_md5_folder(self) -> None:
        selected = filedialog.askdirectory(title="选择文件夹")
        if not selected:
            return
        folder = Path(selected)
        files = find_regular_files(folder, recursive=self.file_recursive.get())
        self._apply_md5_selection(files, base_dir=folder, source_label=f"文件夹 {folder.name}")

    def _apply_md5_selection(self, files: list[Path], base_dir: Path | None, source_label: str | None = None) -> None:
        self.md5_files = sorted(files)
        self.md5_base_dir = base_dir
        if self.md5_files:
            label = source_label or "已选择文件"
            self.md5_summary.set(f"{label}，共 {len(self.md5_files)} 个")
            self._set_status("已载入 MD5 改写文件列表")
        else:
            self.md5_summary.set("未选择文件")

    def modify_file_md5s(self) -> None:
        if not self.md5_files:
            messagebox.showwarning("提示", "请先选择文件。")
            return

        self.md5_log.delete("1.0", END)
        self._set_status("正在处理 MD5 改写…")

        success_count = 0
        for file_path in self.md5_files:
            try:
                if self.md5_base_dir and file_path.is_relative_to(self.md5_base_dir):
                    relative_parent = file_path.parent.relative_to(self.md5_base_dir)
                    output_dir = self.md5_base_dir / "md5_modified" / relative_parent
                else:
                    output_dir = file_path.parent / "md5_modified"
                output_dir.mkdir(parents=True, exist_ok=True)

                output_path = output_dir / file_path.name
                original_md5, new_md5 = modify_file_md5(file_path, output_path)

                self.md5_log.insert(
                    END,
                    f"{file_path}\n"
                    f"  原始 MD5: {original_md5}\n"
                    f"  新   MD5: {new_md5}\n"
                    f"  输出: {output_path}\n\n",
                )
                success_count += 1
            except Exception as exc:
                self.md5_log.insert(END, f"{file_path}\n  失败: {exc}\n\n")

        self._set_status(f"MD5 改写完成：{success_count}/{len(self.md5_files)}")
        messagebox.showinfo("完成", f"MD5 改写完成：成功 {success_count} / {len(self.md5_files)}")

    def compress_images(self) -> None:
        if not self.image_files:
            messagebox.showwarning("提示", "请先选择图片或图片文件夹。")
            return

        output_format = self.image_output_format.get()
        png_mode = self.png_mode.get()
        quality = int(self.image_quality.get())
        self.image_log.delete("1.0", END)
        self._set_status("正在压缩图片…")

        success_count = 0
        for image_path in self.image_files:
            try:
                output_dir = self._image_output_dir(image_path)
                output_dir.mkdir(parents=True, exist_ok=True)

                suffix, save_format = self._resolve_image_format(image_path, output_format)
                output_name = f"{image_path.stem}{suffix}"
                output_path = output_dir / output_name

                original_size = image_path.stat().st_size
                with Image.open(image_path) as image:
                    self._save_compressed_image(
                        image=image,
                        output_path=output_path,
                        save_format=save_format,
                        quality=quality,
                        png_mode=png_mode,
                    )

                new_size = output_path.stat().st_size
                ratio = (1 - new_size / original_size) * 100 if original_size else 0
                strategy_note = self._compression_strategy_label(save_format, png_mode)
                self.image_log.insert(
                    END,
                    f"{image_path}\n"
                    f"  原始: {format_size(original_size)}\n"
                    f"  压缩: {format_size(new_size)}\n"
                    f"  变化: {ratio:+.2f}%\n"
                    f"  模式: {strategy_note}\n"
                    f"  输出: {output_path}\n\n",
                )
                success_count += 1
            except Exception as exc:
                self.image_log.insert(END, f"{image_path}\n  失败: {exc}\n\n")

        self._set_status(f"图片压缩完成：{success_count}/{len(self.image_files)}")
        messagebox.showinfo("完成", f"图片处理完成：成功 {success_count} / {len(self.image_files)}")

    def _image_output_dir(self, image_path: Path) -> Path:
        if self.image_base_dir and image_path.is_relative_to(self.image_base_dir):
            relative_parent = image_path.parent.relative_to(self.image_base_dir)
            return self.image_base_dir / "compressed_output" / relative_parent
        return image_path.parent / "compressed_output"

    def _save_compressed_image(
        self,
        image: Image.Image,
        output_path: Path,
        save_format: str,
        quality: int,
        png_mode: str,
    ) -> None:
        if save_format == "PNG":
            png_image = image.copy()
            if png_mode == PNG_TINIFY_MODE and imagequant is not None:
                save_png_tinify_like(png_image, output_path)
            else:
                save_png_standard(png_image, output_path)
            return

        converted = image.convert("RGB") if save_format in {"JPEG", "WEBP"} else image.copy()
        save_kwargs: dict[str, int | bool] = {"optimize": True}
        if save_format in {"JPEG", "WEBP"}:
            save_kwargs["quality"] = quality
        converted.save(output_path, format=save_format, **save_kwargs)

    def _compression_strategy_label(self, save_format: str, png_mode: str) -> str:
        if save_format != "PNG":
            return f"{save_format} 品质压缩"
        if png_mode == PNG_TINIFY_MODE and imagequant is not None:
            return "Tinify-like PNG"
        return "标准 PNG"

    def _resolve_image_format(self, image_path: Path, output_format: str) -> tuple[str, str]:
        if output_format == "保持原格式":
            suffix = image_path.suffix.lower()
            if suffix in {".jpg", ".jpeg"}:
                return ".jpg", "JPEG"
            if suffix == ".png":
                return ".png", "PNG"
            if suffix == ".webp":
                return ".webp", "WEBP"
            return ".png", "PNG"
        return {"JPEG": (".jpg", "JPEG"), "WEBP": (".webp", "WEBP"), "PNG": (".png", "PNG")}[output_format]

    def compress_files(self) -> None:
        if not self.file_items:
            messagebox.showwarning("提示", "请先选择文件或文件夹。")
            return

        archive_format = self.archive_format.get()
        if archive_format == "gz(单文件)" and len(self.file_items) != 1:
            messagebox.showwarning("提示", "GZ 模式仅支持单文件。")
            return

        output_dir = self.file_base_dir if self.file_base_dir else self.file_items[0].parent
        self.archive_log.delete("1.0", END)
        self._set_status("正在打包文件…")

        try:
            target, entry_names = self._create_archive(output_dir, archive_format)
            original_total = sum(item.stat().st_size for item in self.file_items)
            compressed_size = target.stat().st_size
            ratio = (1 - compressed_size / original_total) * 100 if original_total else 0
            self.archive_log.insert(
                END,
                f"文件数: {len(self.file_items)}\n"
                f"原始总大小: {format_size(original_total)}\n"
                f"压缩后大小: {format_size(compressed_size)}\n"
                f"变化: {ratio:+.2f}%\n"
                f"输出: {target}\n\n"
                f"已归档条目:\n",
            )
            for name in entry_names[:80]:
                self.archive_log.insert(END, f"  - {name}\n")
            if len(entry_names) > 80:
                self.archive_log.insert(END, f"  ... 其余 {len(entry_names) - 80} 项未展开\n")

            self._set_status(f"文件归档完成：{target.name}")
            messagebox.showinfo("完成", "文件压缩完成。")
        except Exception as exc:
            self._set_status("文件归档失败")
            messagebox.showerror("错误", f"压缩失败：{exc}")

    def _create_archive(self, output_dir: Path, archive_format: str) -> tuple[Path, list[str]]:
        entry_names = [self._archive_entry_name(path) for path in self.file_items]

        if archive_format == "zip":
            target = output_dir / "archive_output.zip"
            with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
                for file_path, arcname in zip(self.file_items, entry_names, strict=True):
                    archive.write(file_path, arcname=arcname)
            return target, entry_names

        if archive_format == "tar.gz":
            target = output_dir / "archive_output.tar.gz"
            with tarfile.open(target, "w:gz") as archive:
                for file_path, arcname in zip(self.file_items, entry_names, strict=True):
                    archive.add(file_path, arcname=arcname)
            return target, entry_names

        if archive_format == "tar.xz":
            target = output_dir / "archive_output.tar.xz"
            with tarfile.open(target, "w:xz") as archive:
                for file_path, arcname in zip(self.file_items, entry_names, strict=True):
                    archive.add(file_path, arcname=arcname)
            return target, entry_names

        source = self.file_items[0]
        target = output_dir / f"{source.name}.gz"
        compress_single_file_gz(source, target)
        return target, [source.name]

    def _archive_entry_name(self, file_path: Path) -> str:
        if self.file_base_dir and file_path.is_relative_to(self.file_base_dir):
            return str(file_path.relative_to(self.file_base_dir))
        return file_path.name

    def calculate_hashes(self) -> None:
        if not self.hash_file_path:
            messagebox.showwarning("提示", "请先选择文件。")
            return

        try:
            self._set_status("正在计算哈希…")
            md5_value = hash_file(self.hash_file_path, "md5")
            sha1_value = hash_file(self.hash_file_path, "sha1")
            sha256_value = hash_file(self.hash_file_path, "sha256")
            file_size = self.hash_file_path.stat().st_size

            self.hash_output.delete("1.0", END)
            self.hash_output.insert(
                END,
                f"文件: {self.hash_file_path}\n"
                f"大小: {format_size(file_size)}\n\n"
                f"MD5:\n{md5_value}\n\n"
                f"SHA1:\n{sha1_value}\n\n"
                f"SHA256:\n{sha256_value}\n",
            )
            self._set_status("哈希计算完成")
        except Exception as exc:
            self._set_status("哈希计算失败")
            messagebox.showerror("错误", f"计算失败：{exc}")


def main() -> None:
    root = TkinterDnD.Tk() if TkinterDnD else Tk()
    CompressApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
