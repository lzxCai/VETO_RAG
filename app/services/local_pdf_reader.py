"""
本地 PDF 文本解析（无外部 API 依赖）。

用于在百炼/LlamaParse 不可用或不稳定时，仍能生成可用的 pages 结构，
从而让后续风险识别与报告导出流程可跑通。
"""

from __future__ import annotations

from typing import Dict, List


def read_pdf_text_with_pymupdf(pdf_path: str) -> List[Dict]:
    try:
        import fitz  # PyMuPDF
    except Exception as exc:  # noqa: BLE001
        raise ImportError("未安装 PyMuPDF(fitz)。请先安装 pymupdf。") from exc

    doc = fitz.open(pdf_path)
    pages: List[Dict] = []
    for i in range(doc.page_count):
        page = doc.load_page(i)
        text = (page.get_text("text") or "").strip()
        pages.append({"page_no": i + 1, "text": text})
    return pages

