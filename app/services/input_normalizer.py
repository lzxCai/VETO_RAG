"""
输入归一化：
- 支持 PDF / 单图片 / 多图片列表
- 统一输出为页面图像列表（按顺序）
"""

from __future__ import annotations

import glob
import os
from typing import Dict, List, Sequence, Tuple, Union

from app.services.pdf_to_images import convert_pdf_to_images

ImageInput = Union[str, Sequence[str]]

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}


def _is_pdf(path: str) -> bool:
    return os.path.splitext(path)[1].lower() == ".pdf"


def _is_image(path: str) -> bool:
    return os.path.splitext(path)[1].lower() in IMAGE_EXTENSIONS


def _resolve_image_sequence(input_path: str) -> List[str]:
    """
    解析单路径为图片序列：
    - 文件：直接返回单图
    - 目录：读取目录内图片并按文件名排序
    - 通配符：展开后排序
    """
    if os.path.isdir(input_path):
        files = []
        for ext in IMAGE_EXTENSIONS:
            files.extend(glob.glob(os.path.join(input_path, f"*{ext}")))
            files.extend(glob.glob(os.path.join(input_path, f"*{ext.upper()}")))
        return sorted(files)

    if any(char in input_path for char in ["*", "?"]):
        return sorted(glob.glob(input_path))

    return [input_path]


def normalize_contract_input_to_page_images(
    input_source: ImageInput,
    pdf_dpi: int = 200,
) -> Tuple[List[Dict], Dict]:
    """
    统一将输入归一化为页面图像列表：
    [
      {"page_no": 1, "image_path": "...", "source_type": "pdf|image"},
      ...
    ]
    """
    temp_dirs: List[str] = []
    page_images: List[Dict] = []

    if isinstance(input_source, (list, tuple)):
        image_paths = [str(item) for item in input_source]
        source_kind = "image_sequence"
    elif isinstance(input_source, str):
        if _is_pdf(input_source):
            image_paths, temp_dir = convert_pdf_to_images(input_source, dpi=pdf_dpi)
            temp_dirs.append(temp_dir)
            source_kind = "pdf"
        else:
            image_paths = _resolve_image_sequence(input_source)
            source_kind = "image_or_dir"
    else:
        raise TypeError("input_source 仅支持 str 或 List[str]。")

    if "image_paths" not in locals():
        image_paths = []

    validated_paths: List[str] = []
    for path in image_paths:
        if not os.path.exists(path):
            raise FileNotFoundError(f"输入文件不存在: {path}")
        if not _is_image(path):
            raise ValueError(f"不支持的图片格式: {path}")
        validated_paths.append(path)

    for idx, image_path in enumerate(validated_paths, start=1):
        page_images.append(
            {
                "page_no": idx,
                "image_path": image_path,
                "source_type": "pdf_page" if source_kind == "pdf" else "image",
            }
        )

    meta = {
        "input_source_kind": source_kind,
        "total_pages": len(page_images),
        "temp_dirs": temp_dirs,
    }
    return page_images, meta
