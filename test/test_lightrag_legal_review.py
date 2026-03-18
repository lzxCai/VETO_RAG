import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.services.contract_pipeline import run_contract_parsing_pipeline
from app.services.lightrag_connector import hybrid_search
from ragmain.lightrag_embed import _build_llm_func


PDF_PATH = PROJECT_ROOT / "module_1_2" / "data" / "P020210610345840579453.pdf"
CLASSIFIED_CACHE_PATH = PROJECT_ROOT / "data" / "output" / "classified_contract_from_bailian.json"
OUTPUT_PATH = PROJECT_ROOT / "data" / "output" / "lightrag_legal_review_result.json"
LABOR_LAW_DIR = PROJECT_ROOT / "rag_storage" / "labor_law"
CIVIL_CODE_DIR = PROJECT_ROOT / "rag_storage" / "civil_code"
MAX_CLAUSES = 5
TOP_K_PER_KB = 3


def load_or_parse_contract() -> Dict[str, Any]:
    if CLASSIFIED_CACHE_PATH.exists():
        return json.loads(CLASSIFIED_CACHE_PATH.read_text(encoding="utf-8"))

    pipeline_result = run_contract_parsing_pipeline(
        input_source=str(PDF_PATH),
        parser="auto",
        fallback_to_legacy=True,
        return_parse_meta=False,
    )
    CLASSIFIED_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    CLASSIFIED_CACHE_PATH.write_text(
        json.dumps(pipeline_result, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return pipeline_result


def select_clauses(main_body: List[Dict[str, Any]], max_clauses: int = MAX_CLAUSES) -> List[Dict[str, Any]]:
    preferred_types = {
        "劳动报酬",
        "社会保险和福利待遇",
        "培训服务期",
        "保密义务/竞业限制",
        "工作内容和工作地点",
        "合同期限",
    }
    selected: List[Dict[str, Any]] = []
    seen_ids = set()

    for clause in main_body:
        if clause.get("clause_type") in preferred_types and clause.get("text"):
            clause_id = clause.get("clause_id")
            if clause_id not in seen_ids:
                selected.append(clause)
                seen_ids.add(clause_id)
        if len(selected) >= max_clauses:
            return selected

    for clause in main_body:
        if clause.get("text"):
            clause_id = clause.get("clause_id")
            if clause_id not in seen_ids:
                selected.append(clause)
                seen_ids.add(clause_id)
        if len(selected) >= max_clauses:
            break
    return selected


def build_clause_query(clause: Dict[str, Any]) -> str:
    return "\n".join(
        [
            clause.get("section_title", ""),
            clause.get("section", ""),
            clause.get("title", ""),
            clause.get("text", ""),
        ]
    ).strip()


def retrieve_legal_basis(query: str) -> List[Dict[str, Any]]:
    results: List[Dict[str, Any]] = []

    for kb_name, working_dir in [
        ("labor_law", LABOR_LAW_DIR),
        ("civil_code", CIVIL_CODE_DIR),
    ]:
        raw = hybrid_search(query, working_dir=str(working_dir), top_k=TOP_K_PER_KB)
        for item in raw.get("results", []):
            item_type = item.get("item_type", "")
            normalized = dict(item)
            normalized["kb_name"] = kb_name
            if item_type == "legal_basis" or (item_type == "unknown" and normalized.get("content")):
                normalized["item_type"] = "legal_basis"
                results.append(normalized)

    deduplicated: List[Dict[str, Any]] = []
    seen = set()
    for item in results:
        key = (item.get("item_id"), item.get("title"), item.get("kb_name"))
        if key in seen:
            continue
        seen.add(key)
        deduplicated.append(item)
    return deduplicated


async def review_clause_with_llm(clause: Dict[str, Any], legal_basis: List[Dict[str, Any]]) -> Dict[str, Any]:
    if not legal_basis:
        return {
            "risk_candidate": False,
            "risk_level": "证据不足",
            "mismatch_summary": "本次检索未召回明确法律依据，当前不基于模型内置知识直接下风险结论。",
            "reasoning": "为避免模型在缺少检索证据时自行补充法条，本条款暂标记为证据不足，建议后续优化法律依据召回后再判断。",
            "advice": "建议补充更稳定的法律依据检索，或转人工复核。",
            "legal_basis_refs": [],
            "evidence_insufficient": True,
            "llm_model": "",
        }

    llm_func, llm_model_name = _build_llm_func()
    allowed_titles = [item.get("title", "") for item in legal_basis[:6] if item.get("title")]
    legal_basis_text = "\n\n".join(
        [
            (
                f"[{idx}] {item.get('title', '')}\n"
                f"来源库: {item.get('kb_name', '')}\n"
                f"内容: {item.get('content', '')}"
            )
            for idx, item in enumerate(legal_basis[:6], start=1)
        ]
    )
    prompt = f"""
你是一名劳动合同风险审查助手。请根据“合同条款”和“检索到的法律依据”，判断该条款是否可能存在风险或与法律精神不一致的情形。

要求：
1. 输出 JSON，不要输出多余解释。
2. 字段固定为：
{{
  "risk_candidate": true/false,
  "risk_level": "高/中/低/无明显风险/证据不足",
  "mismatch_summary": "...",
  "reasoning": "...",
  "advice": "...",
  "legal_basis_refs": ["标题1", "标题2"]
}}
3. 只能依据“检索到的法律依据”判断，不得引用未提供的法条、法名或条号。
4. 如果检索证据不足以支持判断，必须输出 "risk_level":"证据不足"。
5. legal_basis_refs 只能从以下标题中选择，不能编造：
{json.dumps(allowed_titles, ensure_ascii=False)}

合同条款：
标题：{clause.get("title", "")}
条款类型：{clause.get("clause_type", "")}
正文：
{clause.get("text", "")}

检索到的法律依据：
{legal_basis_text if legal_basis_text else "未检索到明确法律依据"}
""".strip()
    raw = await llm_func(prompt)
    text = raw if isinstance(raw, str) else str(raw)
    start = text.find("{")
    end = text.rfind("}")
    if 0 <= start < end:
        text = text[start : end + 1]
    try:
        parsed = json.loads(text)
    except Exception:
        parsed = {
            "risk_candidate": False,
            "risk_level": "证据不足",
            "mismatch_summary": "模型输出非标准 JSON，暂无法稳定解析。",
            "reasoning": text[:800],
            "advice": "建议人工复核。",
            "legal_basis_refs": allowed_titles[:3],
        }
    parsed["legal_basis_refs"] = [
        title for title in parsed.get("legal_basis_refs", []) if title in allowed_titles
    ]
    if not parsed["legal_basis_refs"] and legal_basis:
        parsed["risk_level"] = "证据不足"
        parsed["risk_candidate"] = False
        parsed["mismatch_summary"] = "模型未能稳定引用本次检索到的法律依据，结果降级为证据不足。"
        parsed["advice"] = "建议人工复核，或优化法律依据召回质量。"
    parsed["evidence_insufficient"] = parsed.get("risk_level") == "证据不足"
    parsed["llm_model"] = llm_model_name
    return parsed


def main() -> None:
    contract = load_or_parse_contract()
    clauses = select_clauses(contract.get("main_body", []), max_clauses=MAX_CLAUSES)
    results: List[Dict[str, Any]] = []

    for clause in clauses:
        query = build_clause_query(clause)
        legal_basis = retrieve_legal_basis(query)
        llm_review = asyncio.run(review_clause_with_llm(clause, legal_basis))
        results.append(
            {
                "clause_id": clause.get("clause_id"),
                "clause_type": clause.get("clause_type"),
                "section_title": clause.get("section_title"),
                "title": clause.get("title"),
                "query_text": query,
                "retrieved_legal_basis": [
                    {
                        "kb_name": item.get("kb_name"),
                        "item_id": item.get("item_id"),
                        "title": item.get("title"),
                        "rank": item.get("rank"),
                        "content_preview": item.get("content", "")[:300],
                    }
                    for item in legal_basis[:6]
                ],
                "llm_review": llm_review,
            }
        )

    summary = {
        "reviewed_clause_count": len(results),
        "risk_candidate_count": sum(1 for item in results if item["llm_review"].get("risk_candidate")),
        "high_or_medium_count": sum(
            1 for item in results if item["llm_review"].get("risk_level") in {"高", "中"}
        ),
        "evidence_insufficient_count": sum(
            1 for item in results if item["llm_review"].get("risk_level") == "证据不足"
        ),
    }
    output = {
        "pdf_path": str(PDF_PATH),
        "summary": summary,
        "results": results,
    }

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")

    print("=" * 100)
    print("实验版 legal review 汇总")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print("=" * 100)
    for item in results:
        preview = {
            "clause_id": item["clause_id"],
            "clause_type": item["clause_type"],
            "title": item["title"],
            "risk_candidate": item["llm_review"].get("risk_candidate"),
            "risk_level": item["llm_review"].get("risk_level"),
            "mismatch_summary": item["llm_review"].get("mismatch_summary"),
        }
        print(json.dumps(preview, ensure_ascii=False, indent=2))
    print("=" * 100)
    print(f"已保存结果: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
