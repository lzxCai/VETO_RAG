"""PDF 转图片（基于 PyMuPDF / fitz）。"""

from __future__ import annotations

import os
import uuid
from pathlib import Path
from typing import List, Tuple


ROOT_DIR = Path(__file__).resolve().parent.parent.parent
TMP_ROOT = ROOT_DIR / "data" / "tmp"


def convert_pdf_to_images(
    pdf_path: str,
    dpi: int = 200,
    output_dir: str | None = None,
) -> Tuple[List[str], str]:
    if not os.path.exists(pdf_path):
        raise FileNotFoundError(f"PDF 文件不存在: {pdf_path}")

    try:
        import fitz  # pymupdf
    except ImportError as exc:
        raise ImportError("未安装 PyMuPDF(fitz)，无法将 PDF 转为图片。") from exc

    if output_dir:
        out_dir = output_dir
    else:
        TMP_ROOT.mkdir(parents=True, exist_ok=True)
        out_dir = str(TMP_ROOT / f"contract_pdf_pages_{uuid.uuid4().hex[:8]}")
    os.makedirs(out_dir, exist_ok=True)

    image_paths: List[str] = []
    zoom = max(dpi, 72) / 72.0
    matrix = fitz.Matrix(zoom, zoom)

    doc = fitz.open(pdf_path)
    try:
        for i, page in enumerate(doc):
            pix = page.get_pixmap(matrix=matrix, alpha=False)
            image_path = os.path.join(out_dir, f"page_{i + 1:04d}.png")
            Path(image_path).write_bytes(pix.tobytes("png"))
            image_paths.append(image_path)
    finally:
        doc.close()

    return image_paths, out_dir
