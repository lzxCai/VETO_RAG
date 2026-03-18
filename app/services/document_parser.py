"""
统一文档解析入口（多模态适配层）。

支持输入：
- PDF（优先百炼 PDF，多模态失败可回退 LlamaParse）
- 单张图片（JPG/JPEG/PNG...）
- 多张图片列表
- 图片目录/通配符
"""

from __future__ import annotations

import os
import shutil
from typing import Dict, List, Tuple, Union

from app.services.bailian_multimodal_reader import (
    read_pages_with_bailian,
    read_pdf_with_bailian,
)
from app.services.image_preprocessor import preprocess_page_images
from app.services.input_normalizer import normalize_contract_input_to_page_images


DocumentInput = Union[str, List[str]]
SUPPORTED_PARSERS = {"auto", "bailian", "llamaparse"}


def _is_pdf_input(input_source: DocumentInput) -> bool:
    return isinstance(input_source, str) and input_source.lower().endswith(".pdf")


def _safe_cleanup_temp_dirs(temp_dirs: List[str]) -> None:
    for path in temp_dirs:
        if path and os.path.isdir(path):
            shutil.rmtree(path, ignore_errors=True)


def parse_contract_document(
    input_source: DocumentInput,
    parser: str = "auto",
    fallback_to_legacy: bool = True,
    enable_image_preprocess: bool = False,
    cleanup_temp_files: bool = True,
) -> Tuple[List[Dict], Dict]:
    """
    统一解析入口，输出 pages 结构供 cleaner/splitter/classifier 使用。

    注意：
    - 保留 fallback_to_legacy 参数名用于兼容旧调用，
      当前语义是“是否允许回退到备选解析器（LlamaParse）”。
    - cleanup_temp_files 参数保留兼容，当前链路无本地 PDF 渲染临时文件。
    """
    _ = cleanup_temp_files  # 保留参数兼容性

    if parser not in SUPPORTED_PARSERS:
        raise ValueError(f"不支持的 parser: {parser}, 可选: {sorted(SUPPORTED_PARSERS)}")

    warnings: List[str] = []
    parser_used = parser
    fallback_used = False
    input_meta: Dict = {}
    temp_dirs: List[str] = []

    is_pdf = _is_pdf_input(input_source)

    try:
        # 1) 百炼优先（PDF/图片统一走页面图像）
        if parser in {"auto", "bailian"}:
            try:
                page_images, input_meta = normalize_contract_input_to_page_images(
                    input_source=input_source
                )
                temp_dirs = input_meta.get("temp_dirs", [])
                page_images = preprocess_page_images(
                    page_images=page_images,
                    enable_preprocess=enable_image_preprocess,
                )
                pages = read_pages_with_bailian(page_images=page_images)
                if pages:
                    parser_used = "bailian"
                    return pages, {
                        "parser_requested": parser,
                        "parser_used": parser_used,
                        "fallback_used": fallback_used,
                        "warnings": warnings,
                        "input_meta": input_meta,
                    }
                warnings.append("百炼图片通道返回空结果。")
            except Exception as exc:  # noqa: BLE001
                warnings.append(f"百炼解析失败: {exc}")
                # 对 PDF 再尝试一次原生 PDF 通道（有些账号支持直接PDF输入）
                if is_pdf:
                    try:
                        pages = read_pdf_with_bailian(str(input_source))
                        if pages:
                            parser_used = "bailian"
                            return pages, {
                                "parser_requested": parser,
                                "parser_used": parser_used,
                                "fallback_used": fallback_used,
                                "warnings": warnings,
                                "input_meta": {"input_source_kind": "pdf_native"},
                            }
                    except Exception as exc_pdf:  # noqa: BLE001
                        warnings.append(f"百炼PDF原生通道失败: {exc_pdf}")
                if parser == "bailian" and not fallback_to_legacy:
                    raise

        # 2) PDF 兜底：LlamaParse
        if is_pdf and (parser in {"auto", "llamaparse"} or fallback_to_legacy):
            try:
                from app.services.llamaparse_reader import read_pdf_text_with_llamaparse

                pages = read_pdf_text_with_llamaparse(str(input_source))
                if pages:
                    parser_used = "llamaparse"
                    fallback_used = parser != "llamaparse"
                    return pages, {
                        "parser_requested": parser,
                        "parser_used": parser_used,
                        "fallback_used": fallback_used,
                        "warnings": warnings,
                        "input_meta": {"input_source_kind": "pdf"},
                    }
                warnings.append("LlamaParse 返回空结果。")
            except Exception as exc:  # noqa: BLE001
                warnings.append(f"LlamaParse 解析失败: {exc}")
                if parser == "llamaparse" or (parser == "bailian" and not fallback_to_legacy):
                    raise

        raise RuntimeError(
            "解析失败：当前输入未获得可用结果。"
            "请检查 API Key、模型权限、输入格式，或切换 parser。"
            f" 详细原因: {' | '.join(warnings) if warnings else '无详细错误信息'}"
        )
    finally:
        if cleanup_temp_files:
            _safe_cleanup_temp_dirs(temp_dirs)


def parse_pdf_pages(
    pdf_path: str,
    parser: str = "auto",
    fallback_to_legacy: bool = True,
) -> Tuple[List[Dict], Dict]:
    """
    兼容旧接口：供现有代码最小改动调用。
    """
    return parse_contract_document(
        input_source=pdf_path,
        parser=parser,
        fallback_to_legacy=fallback_to_legacy,
    )
