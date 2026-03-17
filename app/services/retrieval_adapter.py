"""
将合同条款与知识文档适配为 LightRAG 可插入的统一检索文档。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Optional

from app.config.risk_rules import RISK_RULES
from ragmain.lightrag_embed import _chunk_text


def _compact_json(data: Dict) -> str:
    return json.dumps(data, ensure_ascii=False, separators=(",", ":"))


def make_retrieval_document(
    *,
    doc_id: str,
    doc_type: str,
    title: str,
    content: str,
    source: str,
    metadata: Optional[Dict] = None,
) -> Dict:
    metadata = metadata or {}
    rendered = (
        f"[ITEM_TYPE]: {doc_type}\n"
        f"[ITEM_ID]: {doc_id}\n"
        f"[TITLE]: {title}\n"
        f"[SOURCE]: {source}\n"
        f"[META]: {_compact_json(metadata)}\n"
        f"[CONTENT]:\n{content.strip()}"
    )
    return {
        "doc_id": doc_id,
        "doc_type": doc_type,
        "title": title,
        "content": content.strip(),
        "source": source,
        "metadata": metadata,
        "rendered_text": rendered.strip(),
    }


def build_contract_clause_documents(
    classified_contract: Dict,
    contract_source: str,
) -> List[Dict]:
    documents: List[Dict] = []

    for clause in classified_contract.get("main_body", []):
        clause_id = clause.get("clause_id", "")
        section_title = clause.get("section_title") or ""
        section = clause.get("section") or ""
        title = clause.get("title") or clause_id or "合同条款"
        clause_type = clause.get("clause_type") or "未分类"
        text = clause.get("text", "").strip()
        if not text:
            continue

        full_title = " ".join(part for part in [section_title, section, title] if part).strip()
        full_content = "\n".join(part for part in [section_title, section, text] if part).strip()
        metadata = {
            "clause_id": clause_id,
            "clause_type": clause_type,
            "part": clause.get("part", "main_body"),
        }
        documents.append(
            make_retrieval_document(
                doc_id=f"contract_clause:{clause_id}",
                doc_type="contract_clause",
                title=full_title or title,
                content=full_content,
                source=contract_source,
                metadata=metadata,
            )
        )

    for attachment in classified_contract.get("attachments", []):
        attachment_id = attachment.get("attachment_id", "")
        text = attachment.get("text", "").strip()
        if not text:
            continue
        metadata = {
            "attachment_id": attachment_id,
            "part": attachment.get("part", "attachment"),
        }
        documents.append(
            make_retrieval_document(
                doc_id=f"contract_attachment:{attachment_id}",
                doc_type="contract_clause",
                title=attachment.get("title") or attachment_id or "合同附件",
                content=text,
                source=contract_source,
                metadata=metadata,
            )
        )

    return documents


def build_risk_card_documents() -> List[Dict]:
    documents: List[Dict] = []
    for rule in RISK_RULES:
        risk_type = rule["risk_type"]
        content_parts = [
            f"风险类型：{risk_type}",
            f"说明：{rule.get('description', '')}",
        ]
        keywords = rule.get("keywords", [])
        if keywords:
            content_parts.append(f"关键词：{'、'.join(keywords)}")
        strong_keywords = rule.get("strong_keywords", [])
        if strong_keywords:
            content_parts.append(f"强触发词：{'、'.join(strong_keywords)}")
        example_scenarios = rule.get("example_scenarios", [])
        if example_scenarios:
            content_parts.append(f"典型场景：{'；'.join(example_scenarios)}")

        documents.append(
            make_retrieval_document(
                doc_id=f"risk_card:{risk_type}",
                doc_type="risk_card",
                title=f"{risk_type}知识卡",
                content="\n".join(content_parts),
                source="app/config/risk_rules.py",
                metadata={"risk_type": risk_type},
            )
        )
    return documents


def build_legal_basis_documents(markdown_path: str, doc_type: str = "legal_basis") -> List[Dict]:
    path = Path(markdown_path)
    if not path.exists():
        raise FileNotFoundError(f"法律依据文件不存在: {markdown_path}")

    text = path.read_text(encoding="utf-8")
    chunks = _chunk_text(text, max_chars=1200, overlap=120)

    documents: List[Dict] = []
    for idx, chunk in enumerate(chunks, start=1):
        documents.append(
            make_retrieval_document(
                doc_id=f"{doc_type}:{path.stem}:{idx}",
                doc_type=doc_type,
                title=f"{path.stem} 法律依据片段 {idx}",
                content=chunk,
                source=str(path),
                metadata={"chunk_index": idx, "file_name": path.name},
            )
        )
    return documents


def parse_retrieval_text(item_text: str) -> Dict:
    """将 LightRAG 返回的上下文文本还原为结构化结果。"""
    result = {
        "item_type": "unknown",
        "item_id": "",
        "title": "",
        "source": "",
        "metadata": {},
        "content": item_text.strip(),
    }
    lines = item_text.splitlines()
    content_start = None
    for idx, line in enumerate(lines):
        if line.startswith("[ITEM_TYPE]:"):
            result["item_type"] = line.split(":", 1)[1].strip()
        elif line.startswith("[ITEM_ID]:"):
            result["item_id"] = line.split(":", 1)[1].strip()
        elif line.startswith("[TITLE]:"):
            result["title"] = line.split(":", 1)[1].strip()
        elif line.startswith("[SOURCE]:"):
            result["source"] = line.split(":", 1)[1].strip()
        elif line.startswith("[META]:"):
            raw_meta = line.split(":", 1)[1].strip()
            try:
                result["metadata"] = json.loads(raw_meta)
            except Exception:
                result["metadata"] = {"raw_meta": raw_meta}
        elif line.startswith("[CONTENT]:"):
            content_start = idx + 1
            break

    if content_start is not None:
        result["content"] = "\n".join(lines[content_start:]).strip()

    return result
