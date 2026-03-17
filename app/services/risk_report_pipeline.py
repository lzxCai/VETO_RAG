"""
风险报告编排入口。

主链路：
合同解析与条款结构化 -> 模块二风险识别 -> 筛出 key_risk_clauses ->
检索 labor_law/civil_code 法律依据 -> 组装报告上下文包
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

from app.services.contract_pipeline import run_contract_parsing_pipeline
from app.services.legal_retrieval_adapter import (
    build_clause_lookup,
    build_report_context,
    retrieve_legal_basis_for_risk_items,
)
from app.services.risk_identifier import identify_contract_risks


def generate_report_context_for_contract(
    contract_source: str,
    parser: str = "auto",
    fallback_to_legacy: bool = True,
    enable_image_preprocess: bool = False,
    top_k_per_kb: int = 3,
) -> Dict[str, Any]:
    pipeline_result = run_contract_parsing_pipeline(
        input_source=contract_source,
        parser=parser,
        fallback_to_legacy=fallback_to_legacy,
        enable_image_preprocess=enable_image_preprocess,
        return_parse_meta=True,
    )
    classified_contract = pipeline_result["classified_contract"]
    parse_meta = pipeline_result["parse_meta"]

    risk_result = identify_contract_risks(classified_contract)
    clause_lookup = build_clause_lookup(classified_contract)
    retrieved_items = retrieve_legal_basis_for_risk_items(
        risk_items=risk_result.get("key_risk_clauses", []),
        clause_lookup=clause_lookup,
        top_k_per_kb=top_k_per_kb,
    )

    report_context = build_report_context(
        contract_source=contract_source,
        classified_contract=classified_contract,
        risk_result=risk_result,
        retrieved_items=retrieved_items,
    )
    report_context["parse_meta"] = parse_meta
    return report_context


def save_report_context(report_context: Dict[str, Any], output_path: str) -> str:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report_context, ensure_ascii=False, indent=2), encoding="utf-8")
    return str(path)
