"""
阿里云百炼（DashScope）多模态解析器。

输入：页面图像列表
输出：与现有系统兼容的 pages 文本结构
"""

from __future__ import annotations

import base64
import json
import mimetypes
import os
import re
from typing import Dict, List, Optional


def _load_dotenv_if_available() -> None:
    try:
        from dotenv import load_dotenv  # type: ignore
    except Exception:
        return
    load_dotenv(override=False)


def _guess_mime_type(path: str) -> str:
    mime, _ = mimetypes.guess_type(path)
    return mime or "image/png"


def _to_data_url(image_path: str) -> str:
    with open(image_path, "rb") as f:
        encoded = base64.b64encode(f.read()).decode("utf-8")
    mime = _guess_mime_type(image_path)
    return f"data:{mime};base64,{encoded}"


def _file_to_data_url(file_path: str, mime_type: str) -> str:
    with open(file_path, "rb") as f:
        encoded = base64.b64encode(f.read()).decode("utf-8")
    return f"data:{mime_type};base64,{encoded}"


def _build_prompt() -> str:
    return (
        "你是劳动合同文档解析助手。"
        "请严格提取当前页面可见文本，尽量保持原始顺序，不要臆测补全。"
        "请优先输出严格JSON（不要加解释）：\n"
        "{\n"
        '  "page_no": <int>,\n'
        '  "blocks": [\n'
        "    {\"block_type\":\"section_title|clause|attachment|other\", \"text\":\"...\"}\n"
        "  ]\n"
        "}\n"
        "要求：\n"
        "1) 保留原文编号（如“一、”“第X条”“附件X”）；\n"
        "2) blocks按版面顺序；\n"
        "3) 不要输出风险分析或总结。\n"
        "若无法输出JSON，则输出Markdown正文。"
    )


def _build_pdf_prompt() -> str:
    return (
        "你是劳动合同文档解析助手。"
        "请读取整份 PDF 合同并按页输出文本。"
        "输出要求：\n"
        "1) 仅输出合同文本，不要解释；\n"
        "2) 每页以“===== 第N页 =====”作为标题分隔；\n"
        "3) 保留章节标题、条款编号、附件标识。"
    )


def _extract_text_from_response(resp: object) -> str:
    """
    兼容 openai 风格响应，提取文本内容。
    """
    try:
        content = resp.choices[0].message.content
    except Exception:
        return ""

    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts: List[str] = []
        for item in content:
            if isinstance(item, dict):
                text = item.get("text")
                if text:
                    parts.append(str(text))
            else:
                text = getattr(item, "text", None)
                if text:
                    parts.append(str(text))
        return "\n".join(parts).strip()
    return str(content).strip()


def _extract_json_from_text(text: str) -> Optional[Dict]:
    """
    从模型输出中提取JSON对象，支持 ```json 包裹和纯文本混排。
    """
    if not text:
        return None

    cleaned = text.strip()
    cleaned = re.sub(r"^```json\s*", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"^```\s*", "", cleaned)
    cleaned = re.sub(r"\s*```$", "", cleaned)

    candidates = [cleaned]

    # 尝试从文本中抓取最外层对象
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if 0 <= start < end:
        candidates.append(cleaned[start : end + 1])

    for candidate in candidates:
        try:
            obj = json.loads(candidate)
            if isinstance(obj, dict):
                return obj
        except Exception:
            continue
    return None


def _normalize_blocks(page_no: int, data: Dict) -> Optional[List[Dict]]:
    blocks = data.get("blocks")
    if not isinstance(blocks, list) or not blocks:
        return None

    normalized: List[Dict] = []
    valid_types = {"section_title", "clause", "attachment", "other"}
    for block in blocks:
        if not isinstance(block, dict):
            continue
        block_type = str(block.get("block_type", "other")).strip().lower()
        if block_type not in valid_types:
            block_type = "other"
        text = str(block.get("text", "")).strip()
        if not text:
            continue
        normalized.append(
            {
                "page_no": page_no,
                "block_type": block_type,
                "text": text,
            }
        )
    return normalized if normalized else None


def _render_page_text_from_blocks(blocks: List[Dict]) -> str:
    """
    将结构化blocks转为下游兼容的文本：
    - section_title独立换行
    - clause中优先将“第X条”独立成行
    - attachment统一以“附件X”起始
    """
    lines: List[str] = []
    for block in blocks:
        block_type = block["block_type"]
        text = block["text"].strip()

        if block_type == "section_title":
            lines.append("")
            lines.append(text)
            lines.append("")
            continue

        if block_type == "clause":
            # 强化条款边界
            text = re.sub(
                r"(?<!\n)(第[一二三四五六七八九十百零\d]+条)",
                r"\n\1",
                text,
            )
            lines.append(text)
            continue

        if block_type == "attachment":
            if not re.match(r"^附件\d+", text):
                text = f"附件 {text}"
            lines.append("")
            lines.append(text)
            lines.append("")
            continue

        lines.append(text)

    rendered = "\n".join(lines)
    rendered = re.sub(r"\n{3,}", "\n\n", rendered)
    return rendered.strip()


def read_pages_with_bailian(
    page_images: List[Dict],
    api_key: Optional[str] = None,
    model: str = "qwen-vl-max-latest",
    timeout: int = 120,
) -> List[Dict]:
    """
    调用百炼多模态模型逐页识别，返回统一 pages 文本结构。
    """
    if not page_images:
        return []

    _load_dotenv_if_available()

    resolved_api_key = (
        api_key
        or os.getenv("DASHSCOPE_API_KEY")
        or os.getenv("BAILIAN_API_KEY")
    )
    if not resolved_api_key:
        raise ValueError("未找到百炼 API Key，请设置 DASHSCOPE_API_KEY。")

    try:
        from openai import OpenAI
    except ImportError as exc:
        raise ImportError(
            "未安装 openai SDK。请安装后再调用百炼多模态解析。"
        ) from exc

    client = OpenAI(
        api_key=resolved_api_key,
        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        timeout=timeout,
    )

    pages: List[Dict] = []
    prompt = _build_prompt()

    for page in page_images:
        page_no = page["page_no"]
        image_path = page["image_path"]
        image_url = _to_data_url(image_path)

        response = client.chat.completions.create(
            model=model,
            messages=[
                {
                    "role": "system",
                    "content": "你是一个严谨的合同OCR解析器。",
                },
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": image_url}},
                    ],
                },
            ],
            temperature=0,
        )
        text = _extract_text_from_response(response)
        parsed = _extract_json_from_text(text)
        blocks: Optional[List[Dict]] = None
        if parsed:
            blocks = _normalize_blocks(page_no=page_no, data=parsed)

        if blocks:
            page_text = _render_page_text_from_blocks(blocks)
            pages.append(
                {
                    "page_no": page_no,
                    "text": page_text,
                    "blocks": blocks,
                    "parse_mode": "json_blocks",
                    "raw_response_text": text,
                }
            )
        else:
            # 同次响应降级：直接使用文本/Markdown，不追加二次调用
            pages.append(
                {
                    "page_no": page_no,
                    "text": text.strip(),
                    "blocks": [],
                    "parse_mode": "fallback_markdown",
                    "raw_response_text": text,
                }
            )

    return pages


def read_pdf_with_bailian(
    pdf_path: str,
    api_key: Optional[str] = None,
    model: str = "qwen-vl-max-latest",
    timeout: int = 180,
) -> List[Dict]:
    """
    直接将 PDF 作为多模态输入交给百炼，并按页分割文本。
    """
    if not os.path.exists(pdf_path):
        raise FileNotFoundError(f"PDF 文件不存在: {pdf_path}")

    _load_dotenv_if_available()
    resolved_api_key = (
        api_key
        or os.getenv("DASHSCOPE_API_KEY")
        or os.getenv("BAILIAN_API_KEY")
    )
    if not resolved_api_key:
        raise ValueError("未找到百炼 API Key，请设置 DASHSCOPE_API_KEY。")

    try:
        from openai import OpenAI
    except ImportError as exc:
        raise ImportError("未安装 openai SDK。请安装后再调用百炼多模态解析。") from exc

    client = OpenAI(
        api_key=resolved_api_key,
        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        timeout=timeout,
    )

    pdf_data_url = _file_to_data_url(pdf_path, "application/pdf")
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": "你是一个严谨的合同OCR解析器。"},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": _build_pdf_prompt()},
                    {"type": "image_url", "image_url": {"url": pdf_data_url}},
                ],
            },
        ],
        temperature=0,
    )
    full_text = _extract_text_from_response(response)
    if not full_text:
        return []

    # 按页标记拆分；若模型未按要求输出分页，则整体按单页返回。
    import re

    parts = re.split(r"\s*=+\s*第\s*(\d+)\s*页\s*=+\s*", full_text)
    if len(parts) <= 1:
        return [{"page_no": 1, "text": full_text.strip()}]

    pages: List[Dict] = []
    i = 1
    while i < len(parts):
        page_no_raw = parts[i]
        page_text = parts[i + 1] if i + 1 < len(parts) else ""
        try:
            page_no = int(page_no_raw)
        except Exception:
            page_no = len(pages) + 1
        pages.append({"page_no": page_no, "text": page_text.strip()})
        i += 2

    if not pages:
        return [{"page_no": 1, "text": full_text.strip()}]
    return pages
