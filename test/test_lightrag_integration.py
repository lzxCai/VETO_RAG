import json
import os
import shutil
import sys
from pathlib import Path
from typing import Any, Dict, List

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.services.contract_pipeline import run_contract_parsing_pipeline
from app.services.lightrag_connector import hybrid_search, insert_retrieval_documents
from app.services.retrieval_adapter import (
    build_contract_clause_documents,
    build_legal_basis_documents,
    build_risk_card_documents,
)


PDF_PATH = PROJECT_ROOT / "module_1_2" / "data" / "P020210610345840579453.pdf"
WORKING_DIR = PROJECT_ROOT / "rag_storage" / "contract_review_demo"
OUTPUT_PATH = PROJECT_ROOT / "data" / "output" / "lightrag_integration_result.json"
MAX_LEGAL_DOCS = 4
MAX_CONTRACT_DOCS = 5
MAX_RISK_CARD_DOCS = 3


def _select_legal_basis_documents(
    all_legal_docs: List[Dict[str, Any]],
    query_text: str,
    max_docs: int = MAX_LEGAL_DOCS,
) -> List[Dict[str, Any]]:
    focus_terms = [
        "试用",
        "工资",
        "薪酬",
        "劳动报酬",
        "社会保险",
        "公积金",
        "竞业",
        "培训",
        "服务期",
        "违约",
        "解除",
        "工作地点",
        "调岗",
    ]
    matched_terms = [term for term in focus_terms if term in query_text]
    if not matched_terms:
        return all_legal_docs[:max_docs]

    selected: List[Dict[str, Any]] = []
    for doc in all_legal_docs:
        content = doc.get("content", "")
        if any(term in content for term in matched_terms):
            selected.append(doc)
        if len(selected) >= max_docs:
            break

    return selected or all_legal_docs[:max_docs]


def _select_contract_documents(
    contract_docs: List[Dict[str, Any]],
    query_clause: Dict[str, Any],
    max_docs: int = MAX_CONTRACT_DOCS,
) -> List[Dict[str, Any]]:
    query_clause_id = query_clause.get("clause_id")
    query_clause_type = query_clause.get("clause_type")
    same_type_docs = []
    other_docs = []

    for doc in contract_docs:
        metadata = doc.get("metadata", {})
        if metadata.get("clause_id") == query_clause_id:
            same_type_docs.insert(0, doc)
        elif metadata.get("clause_type") == query_clause_type:
            same_type_docs.append(doc)
        else:
            other_docs.append(doc)

    selected = same_type_docs[:max_docs]
    if len(selected) < max_docs:
        selected.extend(other_docs[: max_docs - len(selected)])
    return selected


def _select_risk_card_documents(
    risk_card_docs: List[Dict[str, Any]],
    query_text: str,
    max_docs: int = MAX_RISK_CARD_DOCS,
) -> List[Dict[str, Any]]:
    focus_terms = [
        "试用",
        "工资",
        "薪酬",
        "社会保险",
        "公积金",
        "竞业",
        "培训",
        "服务期",
        "调岗",
        "调薪",
    ]
    matched_terms = [term for term in focus_terms if term in query_text]
    if not matched_terms:
        return risk_card_docs[:max_docs]

    selected: List[Dict[str, Any]] = []
    for doc in risk_card_docs:
        text = doc.get("content", "")
        if any(term in text for term in matched_terms):
            selected.append(doc)
        if len(selected) >= max_docs:
            break
    return selected or risk_card_docs[:max_docs]


def _select_query_clause(main_body: List[Dict[str, Any]]) -> Dict[str, Any]:
    preferred_types = {
        "劳动报酬",
        "社会保险和福利待遇",
        "培训服务期",
        "保密义务/竞业限制",
        "工作内容和工作地点",
    }
    for clause in main_body:
        if clause.get("clause_type") in preferred_types and clause.get("text"):
            return clause
    for clause in main_body:
        if clause.get("text"):
            return clause
    raise ValueError("没有可用于检索的条款")


def main() -> None:
    if not PDF_PATH.exists():
        raise FileNotFoundError(f"未找到测试 PDF: {PDF_PATH}")
    if WORKING_DIR.exists():
        shutil.rmtree(WORKING_DIR)
    os.environ.setdefault("LR_LLM_MODEL", "qwen-turbo")
    os.environ.setdefault("LR_MAX_PARALLEL_INSERT", "4")

    pipeline_result: Dict[str, Any] = run_contract_parsing_pipeline(
        input_source=str(PDF_PATH),
        parser="auto",
        fallback_to_legacy=True,
        return_parse_meta=True,
    )
    classified_contract = pipeline_result["classified_contract"]
    parse_meta = pipeline_result["parse_meta"]

    query_clause = _select_query_clause(classified_contract.get("main_body", []))
    query_text = "\n".join(
        [
            query_clause.get("section_title", ""),
            query_clause.get("title", ""),
            query_clause.get("text", ""),
        ]
    ).strip()

    contract_docs_all = build_contract_clause_documents(
        classified_contract,
        contract_source=str(PDF_PATH),
    )
    contract_docs = _select_contract_documents(contract_docs_all, query_clause, max_docs=MAX_CONTRACT_DOCS)
    risk_card_docs_all = build_risk_card_documents()
    risk_card_docs = _select_risk_card_documents(risk_card_docs_all, query_text, max_docs=MAX_RISK_CARD_DOCS)
    legal_docs_all = build_legal_basis_documents(str(PROJECT_ROOT / "dataset" / "labor_law.md"))
    legal_docs = _select_legal_basis_documents(legal_docs_all, query_text, max_docs=MAX_LEGAL_DOCS)

    all_docs = contract_docs + risk_card_docs + legal_docs
    insert_meta = insert_retrieval_documents(all_docs, working_dir=str(WORKING_DIR))
    search_result = hybrid_search(query_text, working_dir=str(WORKING_DIR), top_k=6)

    output = {
        "pdf_path": str(PDF_PATH),
        "parse_meta": parse_meta,
        "insert_meta": insert_meta,
        "query_clause": {
            "clause_id": query_clause.get("clause_id"),
            "clause_type": query_clause.get("clause_type"),
            "section_title": query_clause.get("section_title"),
            "title": query_clause.get("title"),
            "text_preview": query_clause.get("text", "")[:300],
        },
        "retrieval_summary": {
            "contract_doc_count": len(contract_docs),
            "contract_doc_total_available": len(contract_docs_all),
            "risk_card_count": len(risk_card_docs),
            "risk_card_total_available": len(risk_card_docs_all),
            "legal_basis_count": len(legal_docs),
            "legal_basis_total_available": len(legal_docs_all),
            "result_count": len(search_result.get("results", [])),
        },
        "retrieval_results": search_result.get("results", []),
    }

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")

    print("=" * 100)
    print("解析元信息")
    print(json.dumps(parse_meta, ensure_ascii=False, indent=2))
    print("=" * 100)
    print("入库统计")
    print(json.dumps(insert_meta, ensure_ascii=False, indent=2))
    print("=" * 100)
    print("查询条款")
    print(json.dumps(output["query_clause"], ensure_ascii=False, indent=2))
    print("=" * 100)
    print("检索结果预览")
    for item in output["retrieval_results"][:6]:
        preview = {
            "rank": item.get("rank"),
            "item_type": item.get("item_type"),
            "title": item.get("title"),
            "source": item.get("source"),
            "content_preview": item.get("content", "")[:160],
        }
        print(json.dumps(preview, ensure_ascii=False, indent=2))
    print("=" * 100)
    print(f"已保存输出结果: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
