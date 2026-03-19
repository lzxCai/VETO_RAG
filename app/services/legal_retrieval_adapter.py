"""
风险条款到法律依据的检索适配层。

职责：
1. 将模块二产出的 key_risk_clauses 转成风险类型定向的法律检索 query。
2. 查询现有 LightRAG 法律库（labor_law / civil_code）。
3. 过滤目录、章节标题、明显不相关条文，输出更干净的 legal_basis_results。
"""

from __future__ import annotations

import asyncio
import json
import re
from pathlib import Path
from typing import Any, Dict, List, Tuple

from app.config.legal_retrieval_rules import get_legal_retrieval_rule
from app.services.lightrag_connector import ahybrid_search


ROOT_DIR = Path(__file__).resolve().parent.parent.parent
LEGAL_KB_DIRS = {
    "labor_law": ROOT_DIR / "rag_storage" / "labor_law",
    "civil_code": ROOT_DIR / "rag_storage" / "civil_code",
}

NOISE_TOKENS = [
    "Knowledge Graph Data",
    "Document Chunks",
    "```json",
    "# 目录",
    "目 录",
]


def _normalize_text(text: str) -> str:
    if not text:
        return ""
    text = text.replace("\u3000", " ").replace("\xa0", " ")
    return re.sub(r"\s+", "", text).strip()


def _extract_title_from_content(content: str, fallback: str) -> str:
    for line in content.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("#"):
            return stripped.lstrip("#").strip() or fallback
        return stripped[:80]
    return fallback


def _is_heading_only(content: str) -> bool:
    lines = [line.strip() for line in content.splitlines() if line.strip()]
    if not lines:
        return True
    if len(lines) == 1 and lines[0].startswith("#"):
        return True
    if len(lines) <= 2 and all(len(line) <= 20 for line in lines) and not any("。" in line for line in lines):
        return True
    return False


def _is_noise_result(item: Dict[str, Any]) -> bool:
    content = (item.get("content") or "").strip()
    title = (item.get("title") or "").strip()
    combined = f"{title}\n{content}"
    if not content:
        return True
    if any(token in combined for token in NOISE_TOKENS):
        return True
    if _is_heading_only(content):
        return True
    return False


def _compute_relevance_score(
    *,
    risk_type: str,
    rule: Dict[str, List[str]],
    clause_detail: Dict[str, Any],
    item: Dict[str, Any],
    kb_name: str,
) -> Tuple[int, List[str]]:
    content = (item.get("content") or "").strip()
    title = (item.get("title") or "").strip()
    full_text = _normalize_text(f"{title}\n{content}")

    include_any = rule.get("include_any", [])
    prefer_any = rule.get("prefer_any", [])
    exclude_any = rule.get("exclude_any", [])

    score = 0
    notes: List[str] = []

    include_hits = [token for token in include_any if _normalize_text(token) in full_text]
    prefer_hits = [token for token in prefer_any if _normalize_text(token) in full_text]
    exclude_hits = [token for token in exclude_any if _normalize_text(token) in full_text]

    score += len(include_hits) * 5
    score += len(prefer_hits) * 8

    clause_text = _normalize_text(
        " ".join(
            [
                clause_detail.get("section_title", ""),
                clause_detail.get("title", ""),
                clause_detail.get("text", ""),
            ]
        )
    )
    overlap_hits = [token for token in prefer_any if _normalize_text(token) in clause_text and _normalize_text(token) in full_text]
    score += len(overlap_hits) * 4

    clause_mentions_wage = "工资" in clause_text or "报酬" in clause_text
    clause_mentions_overtime = "加班" in clause_text
    clause_mentions_adjustment = "调整" in clause_text or "调薪" in clause_text or "待遇" in clause_text

    if any(keyword in title for keyword in ["条", "款"]):
        score += 2
        notes.append("specific_article_title")

    if _is_heading_only(content):
        score -= 20
        notes.append("heading_only")

    if exclude_hits:
        score -= len(exclude_hits) * 7
        notes.append("exclude_hit")

    if kb_name == "civil_code":
        score -= 1
        notes.append("civil_code_penalty")

    if include_hits:
        notes.append("exact_match")
    elif prefer_hits:
        notes.append("topic_match")
    else:
        notes.append("weak_match")

    if not include_hits and not prefer_hits:
        score -= 5

    if risk_type == "培训服务期风险" and "职业培训" in full_text and "服务期" not in full_text and "违约" not in full_text:
        score -= 8
        notes.append("generic_training_only")

    if risk_type == "试用期工资风险" and "加班工资" in full_text:
        score -= 12
        notes.append("overtime_mismatch")

    if risk_type == "试用期风险" and clause_mentions_wage:
        if "工资" in full_text or "报酬" in full_text or "最低工资" in full_text:
            score += 8
            notes.append("wage_specific_match")
        else:
            score -= 24
            notes.append("missing_wage_specificity")

    if risk_type == "薪酬支付风险" and "加班工资" in full_text and clause_mentions_overtime:
        score += 3
        notes.append("overtime_related")
    elif risk_type == "薪酬支付风险" and "加班工资" in full_text and not clause_mentions_overtime:
        score -= 24
        notes.append("overtime_not_in_clause")

    if risk_type == "薪酬支付风险" and clause_mentions_adjustment:
        if "调整" in full_text or "协商一致" in full_text or "劳动报酬" in full_text:
            score += 5
            notes.append("adjustment_related")
        elif "加班工资" in full_text:
            score -= 20
            notes.append("adjustment_mismatch")

    return score, notes


def _normalize_legal_item(
    item: Dict[str, Any],
    *,
    kb_name: str,
    rank: int,
    score: int,
    notes: List[str],
) -> Dict[str, Any]:
    content = (item.get("content") or "").strip()
    title = (item.get("title") or "").strip()
    if not title:
        title = _extract_title_from_content(content, fallback=f"{kb_name} 法律依据 {rank}")
    return {
        "kb_name": kb_name,
        "title": title,
        "content": content,
        "rank": rank,
        "source": item.get("source") or str(LEGAL_KB_DIRS[kb_name]),
        "score": score,
        "notes": notes,
    }


def _build_targeted_queries(risk_item: Dict[str, Any], clause_detail: Dict[str, Any]) -> Tuple[List[str], Dict[str, List[str]]]:
    risk_type = risk_item.get("risk_type", "")
    rule = get_legal_retrieval_rule(risk_type)
    clause_parts = [
        clause_detail.get("section_title", ""),
        clause_detail.get("title", ""),
        clause_detail.get("text", ""),
    ]
    clause_text = "\n".join(part for part in clause_parts if part).strip()

    primary_keywords = " ".join(rule.get("include_any", []) + rule.get("prefer_any", [])[:3]).strip()
    fallback_keywords = " ".join(rule.get("fallback_keywords", [])).strip()

    queries = []
    if primary_keywords:
        queries.append(f"风险类型：{risk_type}\n重点主题：{primary_keywords}\n条款内容：{clause_text}")
    clause_normalized = _normalize_text(clause_text)
    if risk_type == "试用期风险" and "工资" in clause_normalized:
        queries.append(
            "风险类型：试用期工资相关风险\n"
            "重点主题：试用期 工资 劳动报酬 最低工资 不得低于\n"
            f"条款内容：{clause_text}"
        )
    if risk_type == "薪酬支付风险" and ("调整" in clause_normalized or "待遇" in clause_normalized):
        queries.append(
            "风险类型：工资调整风险\n"
            "重点主题：劳动报酬 工资待遇 协商一致 变更劳动合同\n"
            f"条款内容：{clause_text}"
        )
    if fallback_keywords and fallback_keywords != primary_keywords:
        queries.append(f"风险类型：{risk_type}\n法律主题：{fallback_keywords}\n条款内容：{clause_text}")
    if not queries:
        queries.append(f"风险类型：{risk_type}\n条款内容：{clause_text}")
    return queries, rule


async def aretrieve_legal_basis_for_risk_item(
    risk_item: Dict[str, Any],
    clause_detail: Dict[str, Any],
    top_k_per_kb: int = 3,
) -> Dict[str, Any]:
    risk_type = risk_item.get("risk_type", "")
    queries, rule = _build_targeted_queries(risk_item, clause_detail)

    candidates: List[Dict[str, Any]] = []
    retrieval_notes: List[str] = []

    for query_index, query in enumerate(queries):
        for kb_name, working_dir in LEGAL_KB_DIRS.items():
            search_result = await ahybrid_search(
                query=query,
                working_dir=str(working_dir),
                top_k=max(top_k_per_kb * 2, 6),
            )
            for item in search_result.get("results", []):
                if _is_noise_result(item):
                    continue
                score, notes = _compute_relevance_score(
                    risk_type=risk_type,
                    rule=rule,
                    clause_detail=clause_detail,
                    item=item,
                    kb_name=kb_name,
                )
                if score < 5:
                    continue
                if query_index > 0:
                    notes = notes + ["fallback_query"]
                candidates.append(
                    _normalize_legal_item(
                        item,
                        kb_name=kb_name,
                        rank=0,
                        score=score,
                        notes=notes,
                    )
                )

        if candidates:
            retrieval_notes.append("exact_match" if query_index == 0 else "fallback_query")
            break

    deduplicated: List[Dict[str, Any]] = []
    seen = set()
    for item in sorted(candidates, key=lambda x: (-x["score"], x["kb_name"], x["title"])):
        content_key = _normalize_text(item["content"])[:160]
        title_key = _normalize_text(item["title"])
        dedupe_key = (title_key, content_key)
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)
        deduplicated.append(item)

    if not deduplicated:
        retrieval_notes.append("insufficient_specificity")

    limited: List[Dict[str, Any]] = []
    per_kb_count = {"labor_law": 0, "civil_code": 0}
    final_rank = 1
    for item in deduplicated:
        kb_name = item["kb_name"]
        if per_kb_count[kb_name] >= top_k_per_kb:
            continue
        per_kb_count[kb_name] += 1
        limited.append(
            {
                "kb_name": kb_name,
                "title": item["title"],
                "content": item["content"],
                "rank": final_rank,
                "source": item["source"],
            }
        )
        final_rank += 1

    return {
        "clause_id": risk_item.get("clause_id", ""),
        "risk_type": risk_type,
        "clause_text": clause_detail.get("text", ""),
        "clause_title": clause_detail.get("title", ""),
        "section_title": clause_detail.get("section_title", ""),
        "clause_type": clause_detail.get("clause_type", ""),
        # 供前端「逐条风险」标题生成：风险触发词，避免仅用条文前若干字当概述
        "trigger_phrases": list(risk_item.get("trigger_phrases") or []),
        "risk_level_preliminary": risk_item.get("risk_level_preliminary", ""),
        "legal_basis_results": limited,
        "retrieval_notes": sorted(set(retrieval_notes)),
    }


async def aretrieve_legal_basis_for_risk_items(
    risk_items: List[Dict[str, Any]],
    clause_lookup: Dict[str, Dict[str, Any]],
    top_k_per_kb: int = 3,
) -> List[Dict[str, Any]]:
    enriched: List[Dict[str, Any]] = []
    for risk_item in risk_items:
        clause_id = risk_item.get("clause_id", "")
        clause_detail = clause_lookup.get(clause_id, {})
        enriched.append(
            await aretrieve_legal_basis_for_risk_item(
                risk_item=risk_item,
                clause_detail=clause_detail,
                top_k_per_kb=top_k_per_kb,
            )
        )
    return enriched


def retrieve_legal_basis_for_risk_items(
    risk_items: List[Dict[str, Any]],
    clause_lookup: Dict[str, Dict[str, Any]],
    top_k_per_kb: int = 3,
) -> List[Dict[str, Any]]:
    return asyncio.run(
        aretrieve_legal_basis_for_risk_items(
            risk_items=risk_items,
            clause_lookup=clause_lookup,
            top_k_per_kb=top_k_per_kb,
        )
    )


def build_clause_lookup(classified_contract: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    lookup: Dict[str, Dict[str, Any]] = {}
    for item in classified_contract.get("main_body", []):
        clause_id = item.get("clause_id")
        if clause_id:
            lookup[clause_id] = item
    for item in classified_contract.get("attachments", []):
        attachment_id = item.get("attachment_id")
        if attachment_id:
            lookup[attachment_id] = item
    return lookup


def build_report_context(
    contract_source: str,
    classified_contract: Dict[str, Any],
    risk_result: Dict[str, Any],
    retrieved_items: List[Dict[str, Any]],
) -> Dict[str, Any]:
    return {
        "contract_source": contract_source,
        "summary": {
            "main_body_clause_count": len(classified_contract.get("main_body", [])),
            "attachment_count": len(classified_contract.get("attachments", [])),
            "key_risk_clause_count": len(risk_result.get("key_risk_clauses", [])),
            "risk_type_counts": risk_result.get("summary", {}).get("risk_type_counts", {}),
        },
        "risk_items": [
            {
                "clause_id": item.get("clause_id", ""),
                "risk_type": item.get("risk_type", ""),
                "clause_title": item.get("clause_title", ""),
                "section_title": item.get("section_title", ""),
                "clause_text": item.get("clause_text", ""),
                "trigger_phrases": item.get("trigger_phrases", []),
                "risk_level_preliminary": item.get("risk_level_preliminary", ""),
                "legal_basis_results": item.get("legal_basis_results", []),
                "retrieval_notes": item.get("retrieval_notes", []),
            }
            for item in retrieved_items
        ],
    }
