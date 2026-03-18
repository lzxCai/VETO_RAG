"""
LightRAG 连接器。

职责：
1. 封装 LightRAG 初始化，避免主流程直接依赖脚本入口。
2. 提供文档入库与 hybrid search 查询能力。
3. 统一处理 .env、工作目录和返回结果标准化。
"""

from __future__ import annotations

import asyncio
import inspect
import json
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv
from lightrag import LightRAG, QueryParam
from lightrag.utils import setup_logger

from app.services.retrieval_adapter import parse_retrieval_text
from ragmain.lightrag_embed import (
    _build_embedding_func,
    _build_llm_func,
    _get_env_int,
    _get_env_json,
)
from ragmain.lightrag_query import _extract_context_list


ROOT_DIR = Path(__file__).resolve().parent.parent.parent
DEFAULT_WORKING_DIR = ROOT_DIR / "rag_storage" / "contract_retrieval_demo"


def _load_env() -> None:
    root_env = ROOT_DIR / ".env"
    rag_env = ROOT_DIR / "ragmain" / ".env"
    load_dotenv(dotenv_path=root_env, override=False)
    load_dotenv(dotenv_path=rag_env, override=False)


def _build_rag(working_dir: str) -> LightRAG:
    setup_logger("lightrag", level=os.getenv("LR_LOG_LEVEL", "INFO"))
    llm_model_func, llm_model_name = _build_llm_func()
    embedding_func = _build_embedding_func()

    vector_storage = os.getenv("LR_VECTOR_STORAGE", "NanoVectorDBStorage")
    graph_storage = os.getenv("LR_GRAPH_STORAGE", "NetworkXStorage")
    vector_kwargs = _get_env_json("LR_VECTOR_DB_KWARGS") or {}
    graph_kwargs = _get_env_json("LR_GRAPH_DB_KWARGS") or {}
    max_parallel_insert = _get_env_int("LR_MAX_PARALLEL_INSERT", 2)

    rag_kwargs = dict(
        working_dir=str(Path(working_dir)),
        llm_model_func=llm_model_func,
        llm_model_name=llm_model_name,
        embedding_func=embedding_func,
        vector_storage=vector_storage,
        graph_storage=graph_storage,
        max_parallel_insert=max_parallel_insert,
    )
    sig = inspect.signature(LightRAG.__init__).parameters
    if vector_kwargs:
        for key in ("vector_db_storage_cls_kwargs", "vector_storage_cls_kwargs"):
            if key in sig:
                rag_kwargs[key] = vector_kwargs
                break
    if graph_kwargs:
        for key in ("graph_storage_cls_kwargs", "graph_db_storage_cls_kwargs"):
            if key in sig:
                rag_kwargs[key] = graph_kwargs
                break

    return LightRAG(**rag_kwargs)


def _parse_json_block_items(text: str) -> List[Dict[str, Any]]:
    cleaned = text.strip()
    if cleaned.startswith("```json"):
        cleaned = cleaned[len("```json") :].strip()
    elif cleaned.startswith("```"):
        cleaned = cleaned[3:].strip()
    if cleaned.endswith("```"):
        cleaned = cleaned[:-3].strip()

    items: List[Dict[str, Any]] = []
    for line in cleaned.splitlines():
        line = line.strip()
        if not line or not line.startswith("{"):
            continue
        try:
            obj = json.loads(line)
        except Exception:
            continue
        if isinstance(obj, dict):
            items.append(obj)
    return items


def _extract_document_results(context_items: List[str]) -> List[Dict[str, Any]]:
    results: List[Dict[str, Any]] = []
    for item in context_items:
        if '"reference_id"' not in item or '"content"' not in item:
            continue
        for obj in _parse_json_block_items(item):
            content = obj.get("content")
            if not isinstance(content, str) or not content.strip():
                continue
            parsed = parse_retrieval_text(content)
            parsed["reference_id"] = obj.get("reference_id", "")
            results.append(parsed)

    deduplicated: List[Dict[str, Any]] = []
    seen_keys = set()
    for item in results:
        key = (
            item.get("item_id", ""),
            item.get("title", ""),
            item.get("source", ""),
        )
        if key in seen_keys:
            continue
        seen_keys.add(key)
        deduplicated.append(item)
    return deduplicated


async def ainsert_retrieval_documents(
    documents: List[Dict],
    working_dir: Optional[str] = None,
) -> Dict[str, Any]:
    _load_env()
    target_dir = working_dir or str(DEFAULT_WORKING_DIR)
    Path(target_dir).mkdir(parents=True, exist_ok=True)

    texts = [doc["rendered_text"] for doc in documents if doc.get("rendered_text")]
    file_paths = [doc.get("source", "") for doc in documents if doc.get("rendered_text")]
    if not texts:
        raise ValueError("没有可插入的检索文档")

    rag = _build_rag(target_dir)
    await rag.initialize_storages()
    try:
        await rag.ainsert(texts, file_paths=file_paths)
    finally:
        await rag.finalize_storages()

    return {
        "working_dir": target_dir,
        "inserted_count": len(texts),
    }


async def ahybrid_search(
    query: str,
    working_dir: Optional[str] = None,
    top_k: int = 5,
) -> Dict[str, Any]:
    _load_env()
    target_dir = working_dir or str(DEFAULT_WORKING_DIR)
    rag = _build_rag(target_dir)
    await rag.initialize_storages()
    try:
        param = QueryParam(mode="hybrid")
        if hasattr(param, "enable_rerank"):
            try:
                param.enable_rerank = False
            except Exception:
                pass
        if hasattr(param, "only_need_context"):
            try:
                param.only_need_context = True
            except Exception:
                pass

        raw_result = await rag.aquery(query, param=param)
    finally:
        await rag.finalize_storages()

    context_items = _extract_context_list(raw_result) or []
    parsed_items = _extract_document_results(context_items)
    if not parsed_items:
        parsed_items = [parse_retrieval_text(item) for item in context_items]
    return {
        "query": query,
        "working_dir": target_dir,
        "raw_result": raw_result,
        "results": [
            {
                **item,
                "rank": idx + 1,
            }
            for idx, item in enumerate(parsed_items)
        ],
    }


def insert_retrieval_documents(
    documents: List[Dict],
    working_dir: Optional[str] = None,
) -> Dict[str, Any]:
    return asyncio.run(ainsert_retrieval_documents(documents, working_dir=working_dir))


def hybrid_search(
    query: str,
    working_dir: Optional[str] = None,
    top_k: int = 5,
) -> Dict[str, Any]:
    return asyncio.run(ahybrid_search(query, working_dir=working_dir, top_k=top_k))
