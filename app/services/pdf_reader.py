"""
兼容层：保留 read_pdf_text 接口，内部走统一 document_parser。
不再依赖 PyMuPDF(fitz)。
"""

from typing import Dict, List


def read_pdf_text(pdf_path: str) -> List[Dict]:
    """
    读取 PDF，返回按页组织的文本内容。

    返回格式:
    [
        {"page_no": 1, "text": "..."},
        {"page_no": 2, "text": "..."}
    ]
    """
    from app.services.document_parser import parse_pdf_pages

    pages, _meta = parse_pdf_pages(
        pdf_path=pdf_path,
        parser="auto",
        fallback_to_legacy=True,
    )
    return pages


def pages_to_text(pages: List[Dict]) -> str:
    """
    将按页结果拼接为完整文本，保留页码标记。
    """
    parts = []
    for page in pages:
        parts.append(f"\n===== 第 {page['page_no']} 页 =====\n")
        parts.append(page["text"])
    return "\n".join(parts).strip()
