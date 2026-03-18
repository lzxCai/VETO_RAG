import fitz  # pymupdf
from typing import List, Dict


def read_pdf_text(pdf_path: str) -> List[Dict]:
    """
    读取 PDF，返回按页组织的文本内容。

    返回格式:
    [
        {"page_no": 1, "text": "..."},
        {"page_no": 2, "text": "..."}
    ]
    """
    doc = fitz.open(pdf_path)
    pages = []

    for i, page in enumerate(doc):
        text = page.get_text("text")
        pages.append({
            "page_no": i + 1,
            "text": text if text else ""
        })

    doc.close()
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