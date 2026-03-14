"""
LlamaParse PDF 读取适配层。

目标：
1. 将 LlamaParse 输出适配为现有系统统一 pages 结构。
2. 不改变下游模块依赖的数据格式。
"""

from __future__ import annotations

import os
import re
from typing import Dict, List, Optional


def _load_dotenv_if_available() -> None:
    """
    尝试加载 .env（可选依赖）。
    若未安装 python-dotenv，不影响主流程。
    """
    try:
        from dotenv import load_dotenv  # type: ignore
    except Exception:
        return
    load_dotenv(override=False)


def _normalize_llamaparse_language(language: str) -> str:
    """
    规范化语言参数，兼容常见别名。
    LlamaParse 当前不接受 'zh'，中文应使用 'ch_sim' 或 'ch_tra'。
    """
    value = (language or "").strip().lower()
    mapping = {
        "zh": "ch_sim",
        "zh-cn": "ch_sim",
        "zh_hans": "ch_sim",
        "zh-tw": "ch_tra",
        "zh-hk": "ch_tra",
        "zh_hant": "ch_tra",
    }
    return mapping.get(value, value or "ch_sim")


def _extract_text_from_docs(documents: List[object]) -> str:
    """将 LlamaParse 文档对象列表合并为文本。"""
    parts: List[str] = []
    for doc in documents:
        text = getattr(doc, "text", "")
        if text:
            parts.append(text)
    return "\n\n".join(parts).strip()


def _split_text_to_pages(raw_text: str) -> List[Dict]:
    """
    尝试从文本中切分页面。
    若无法识别页分隔符，则作为单页返回，保证兼容。
    """
    if not raw_text.strip():
        return []

    # 常见页标记：Page 1 / 第1页 / ==== Page 1 ====
    marker_pattern = re.compile(
        r"(?im)^\s*(?:=+\s*)?(?:page\s*\d+|第\s*\d+\s*页)(?:\s*=+)?\s*$"
    )
    chunks = re.split(marker_pattern, raw_text)
    chunks = [chunk.strip() for chunk in chunks if chunk and chunk.strip()]

    if len(chunks) <= 1:
        return [{"page_no": 1, "text": raw_text.strip()}]

    pages: List[Dict] = []
    for idx, chunk in enumerate(chunks, start=1):
        pages.append({"page_no": idx, "text": chunk})
    return pages


def read_pdf_text_with_llamaparse(
    pdf_path: str,
    api_key: Optional[str] = None,
    result_type: str = "markdown",
    language: str = "ch_sim",
) -> List[Dict]:
    """
    使用 LlamaParse 读取 PDF，并返回统一 pages 结构：
    [
      {"page_no": 1, "text": "..."},
      {"page_no": 2, "text": "..."}
    ]
    """
    try:
        from llama_parse import LlamaParse
    except ImportError as exc:
        raise ImportError(
            "llama_parse 未安装，请先安装后再启用 LlamaParse。"
        ) from exc

    # 支持从项目根目录 .env 读取 API Key
    _load_dotenv_if_available()

    resolved_api_key = (
        api_key
        or os.getenv("LLAMA_CLOUD_API_KEY")
        or os.getenv("LLAMAPARSE_API_KEY")
    )
    if not resolved_api_key:
        raise ValueError(
            "未找到 LlamaParse API Key，请设置 LLAMA_CLOUD_API_KEY 或 LLAMAPARSE_API_KEY。"
        )

    normalized_language = _normalize_llamaparse_language(language)

    parser = LlamaParse(
        api_key=resolved_api_key,
        result_type=result_type,
        language=normalized_language,
        verbose=False,
    )
    documents = parser.load_data(pdf_path)
    if not documents:
        return []

    # 优先按 doc 粒度映射页，若只有一段则尝试页标记切分
    if len(documents) > 1:
        pages: List[Dict] = []
        for i, doc in enumerate(documents, start=1):
            text = (getattr(doc, "text", "") or "").strip()
            pages.append({"page_no": i, "text": text})
        return pages

    full_text = _extract_text_from_docs(documents)
    return _split_text_to_pages(full_text)
