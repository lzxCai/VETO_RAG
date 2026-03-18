# 第一模块合同解析流程：
# - 通过统一 document_parser 接入多模态解析器（百炼优先，LlamaParse 兜底）
# - 对下游保持同一结构输出，不影响第二模块使用
from typing import List, Union

from app.services.document_parser import parse_contract_document
from app.services.text_cleaner import clean_pages, merge_pages
from app.services.clause_splitter import split_contract
from app.services.clause_classifier import classify_contract_parts


def run_contract_parsing_pipeline(
    input_source: Union[str, List[str]],
    parser: str = "auto",
    fallback_to_legacy: bool = True,
    enable_image_preprocess: bool = False,
    return_parse_meta: bool = False,
):
    """
    合同解析主流程（兼容原接口）：
    - 默认返回 classified_result，与历史行为一致
    - 可选返回 parse_meta，便于观察当前使用的解析器
    """
    pages, parse_meta = parse_contract_document(
        input_source=input_source,
        parser=parser,
        fallback_to_legacy=fallback_to_legacy,
        enable_image_preprocess=enable_image_preprocess,
    )
    cleaning_mode = "multimodal" if parse_meta.get("parser_used") == "bailian" else "legacy"
    cleaned_pages = clean_pages(pages, mode=cleaning_mode)
    full_text = merge_pages(cleaned_pages, mode=cleaning_mode)
    split_result = split_contract(full_text)
    classified_result = classify_contract_parts(split_result)

    main_body = classified_result.get("main_body", [])
    attachments = classified_result.get("attachments", [])
    clause_lengths = [len(item.get("text", "")) for item in main_body if item.get("text")]
    avg_clause_length = int(sum(clause_lengths) / len(clause_lengths)) if clause_lengths else 0
    section_title_count = len(
        {
            item.get("section_title")
            for item in main_body
            if item.get("section_title")
        }
    )

    metrics = {
        "clause_count": len(main_body),
        "attachment_count": len(attachments),
        "section_title_count": section_title_count,
        "avg_clause_length": avg_clause_length,
        "full_text_length": len(full_text),
    }
    parse_meta["metrics"] = metrics

    if metrics["clause_count"] <= 1 and metrics["full_text_length"] > 1200:
        parse_meta["quality_flag"] = "under_segmented"
    else:
        parse_meta["quality_flag"] = "ok"

    if return_parse_meta:
        return {
            "classified_contract": classified_result,
            "parse_meta": parse_meta,
        }

    return classified_result
