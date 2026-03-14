"""
PDF -> 图片（基于 PyMuPDF / fitz）。
"""

from __future__ import annotations

import os
import tempfile
from typing import List, Tuple


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

    out_dir = output_dir or tempfile.mkdtemp(prefix="contract_pdf_pages_")
    os.makedirs(out_dir, exist_ok=True)

    image_paths: List[str] = []
    zoom = max(dpi, 72) / 72.0
    matrix = fitz.Matrix(zoom, zoom)

    doc = fitz.open(pdf_path)
    try:
        for i, page in enumerate(doc):
            pix = page.get_pixmap(matrix=matrix, alpha=False)
            image_path = os.path.join(out_dir, f"page_{i + 1:04d}.png")
            pix.save(image_path)
            image_paths.append(image_path)
    finally:
        doc.close()

    return image_paths, out_dir
