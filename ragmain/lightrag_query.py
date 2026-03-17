import argparse
import asyncio
import json
import os
import sys
import inspect
import urllib.request
import urllib.error
from pathlib import Path
from datetime import datetime
from typing import Any, Optional

from dotenv import load_dotenv
from lightrag import LightRAG, QueryParam
from lightrag.utils import setup_logger, wrap_embedding_func_with_attrs


ROOT_DIR = Path(__file__).resolve().parent.parent
ENV_PATH = Path(__file__).resolve().parent / ".env"
DEFAULT_WORKING_DIR = ROOT_DIR / "rag_storage" / "civil_code"
DEFAULT_ZH_SYSTEM_PROMPT = "你是一个只说中文的助手，必须使用中文回答。"


def _get_env_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if not value:
        return default
    try:
        return int(value)
    except ValueError:
        raise ValueError(f"{name} must be int, got: {value}")


def _get_env_json(name: str) -> Optional[dict]:
    value = os.getenv(name)
    if not value:
        return None
    return json.loads(value)


def _build_embedding_func():
    provider = os.getenv("LR_EMBED_PROVIDER", "openai_like").lower()
    if provider == "openai_like":
        from lightrag.llm.openai import openai_embed

        embed_model = os.getenv("LR_EMBED_MODEL", "text-embedding-v3")
        embed_dim = _get_env_int("LR_EMBED_DIM", 1024)
        base_url = os.getenv(
            "LR_EMBED_BASE_URL",
            os.getenv("LR_LLM_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1"),
        )
        api_key = os.getenv(
            "LR_EMBED_API_KEY",
            os.getenv("LR_LLM_API_KEY", os.getenv("DASHSCOPE_API_KEY", "")),
        )
        if not api_key:
            raise ValueError("LR_EMBED_API_KEY is required for openai_like embedding provider")

        @wrap_embedding_func_with_attrs(
            embedding_dim=embed_dim,
            max_token_size=_get_env_int("LR_EMBED_MAX_TOKENS", 8192),
            model_name=embed_model,
        )
        async def embedding_func(texts: list[str]):
            return await openai_embed.func(
                texts,
                model=embed_model,
                api_key=api_key,
                base_url=base_url or None,
            )

        return embedding_func

    if provider == "ollama":
        from lightrag.llm.ollama import ollama_embed

        embed_model = os.getenv("LR_EMBED_MODEL", "nomic-embed-text")
        embed_dim = _get_env_int("LR_EMBED_DIM", 768)

        @wrap_embedding_func_with_attrs(
            embedding_dim=embed_dim,
            max_token_size=_get_env_int("LR_EMBED_MAX_TOKENS", 8192),
            model_name=embed_model,
        )
        async def embedding_func(texts: list[str]):
            return await ollama_embed.func(texts, embed_model=embed_model)

        return embedding_func

    if provider == "hf":
        from sentence_transformers import SentenceTransformer

        embed_model = os.getenv("LR_EMBED_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
        model = SentenceTransformer(embed_model)

        @wrap_embedding_func_with_attrs(
            embedding_dim=_get_env_int("LR_EMBED_DIM", 384),
            max_token_size=_get_env_int("LR_EMBED_MAX_TOKENS", 2048),
            model_name=embed_model,
        )
        async def embedding_func(texts: list[str]):
            return model.encode(texts, convert_to_numpy=True)

        return embedding_func

    raise ValueError(f"Unsupported LR_EMBED_PROVIDER: {provider}")


def _build_llm_func():
    provider = os.getenv("LR_LLM_PROVIDER", "openai_like").lower()
    if provider == "openai_like":
        from lightrag.llm.openai import openai_complete_if_cache

        llm_model = os.getenv("LR_LLM_MODEL", "qwen3-max")
        base_url = os.getenv("LR_LLM_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1")
        api_key = os.getenv("LR_LLM_API_KEY", os.getenv("DASHSCOPE_API_KEY", ""))
        if not api_key:
            raise ValueError("LR_LLM_API_KEY (or DASHSCOPE_API_KEY) is required for openai_like LLM provider")

        async def llm_model_func(prompt, system_prompt=None, history_messages=None, **kwargs):
            return await openai_complete_if_cache(
                llm_model,
                prompt,
                system_prompt=system_prompt,
                history_messages=history_messages or [],
                api_key=api_key,
                base_url=base_url,
                **kwargs,
            )

        return llm_model_func, llm_model

    if provider == "ollama":
        from lightrag.llm.ollama import ollama_model_complete

        llm_model = os.getenv("LR_LLM_MODEL", "qwen2:7b-instruct")
        llm_kwargs = _get_env_json("LR_LLM_KWARGS") or {}

        async def llm_model_func(prompt, system_prompt=None, history_messages=None, **kwargs):
            return await ollama_model_complete(
                llm_model,
                prompt,
                system_prompt=system_prompt,
                history_messages=history_messages or [],
                **{**llm_kwargs, **kwargs},
            )

        return llm_model_func, llm_model

    if provider == "hf":
        from lightrag.llm.hf import hf_model_complete

        llm_model = os.getenv("LR_LLM_MODEL", "meta-llama/Llama-3.2-3B-Instruct")

        async def llm_model_func(prompt, system_prompt=None, history_messages=None, **kwargs):
            return await hf_model_complete(
                llm_model,
                prompt,
                system_prompt=system_prompt,
                history_messages=history_messages or [],
                **kwargs,
            )

        return llm_model_func, llm_model

    raise ValueError(f"Unsupported LR_LLM_PROVIDER: {provider}")


def _build_prompt(query: str, context: str) -> str:
    return (
        "你现在是一个专业的合同分析助手。\n"
        "请你根据上下文做出详细的中文回答。\n"
        "请你使用严谨且严肃的口吻。\n"
        "适当使用markdown语法，使输出更加美观，但不要使用表情符号。\n"
        "请不要输出任何与合同分析无关的内容。\n"
        "如果上下文不足以提供足够的信息，请明确说明。\n\n"
        f"Context:\n{context}\n\n"
        f"Question: {query}\n"
        "Answer:"
    )


def _extract_context(result: Any) -> Optional[str]:
    if isinstance(result, dict):
        for key in ("context", "contexts", "source", "sources", "references"):
            if key in result and result[key]:
                if isinstance(result[key], str):
                    return result[key]
                if isinstance(result[key], list):
                    return "\n\n".join([str(x) for x in result[key]])
        if "result" in result and isinstance(result["result"], str):
            return result["result"]
    if isinstance(result, list):
        return "\n\n".join([str(x) for x in result])
    return None


def _extract_context_list(result: Any) -> Optional[list[str]]:
    if isinstance(result, dict):
        for key in ("contexts", "context", "sources", "source", "references"):
            if key in result and result[key]:
                if isinstance(result[key], list):
                    return [str(x) for x in result[key] if str(x).strip()]
                if isinstance(result[key], str):
                    return [x.strip() for x in result[key].split("\n\n") if x.strip()]
        if "result" in result and isinstance(result["result"], str):
            return [x.strip() for x in result["result"].split("\n\n") if x.strip()]
    if isinstance(result, list):
        return [str(x) for x in result if str(x).strip()]
    if isinstance(result, str):
        return [x.strip() for x in result.split("\n\n") if x.strip()]
    return None


def _parse_rerank_response(resp: dict) -> list[int]:
    # DashScope text rerank: resp["output"]["results"] -> [{"index": int, "relevance_score": float}, ...]
    if isinstance(resp, dict):
        if "output" in resp and isinstance(resp["output"], dict):
            results = resp["output"].get("results")
            if isinstance(results, list):
                return [int(r["index"]) for r in results if "index" in r]
        # compatible-api style may return "results" or "data"
        results = resp.get("results") or resp.get("data")
        if isinstance(results, list):
            indices = []
            for r in results:
                if isinstance(r, dict) and "index" in r:
                    indices.append(int(r["index"]))
                elif isinstance(r, dict) and "document" in r and "index" in r["document"]:
                    indices.append(int(r["document"]["index"]))
            if indices:
                return indices
    return []


def _format_output_content(result: Any) -> str:
    if isinstance(result, str):
        return result
    try:
        return json.dumps(result, ensure_ascii=False, indent=2)
    except TypeError:
        return str(result)


def _save_output(content: str) -> Path:
    output_dir = ROOT_DIR / "MDoutput"
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = output_dir / f"{timestamp}.md"
    output_path.write_text(content, encoding="utf-8")
    return output_path


def _normalize_working_dirs(multi_dirs: str | None, single_dir: str) -> list[Path]:
    if multi_dirs:
        parts = [p.strip() for p in multi_dirs.split(",") if p.strip()]
        if parts:
            return [Path(p) for p in parts]
    return [Path(single_dir)]


def _ensure_context_list(result: Any) -> list[str]:
    contexts = _extract_context_list(result)
    if not contexts:
        context = _extract_context(result) or str(result)
        contexts = [context]
    return contexts


async def _dashscope_rerank(
    query: str,
    documents: list[str],
    *,
    top_n: int,
    model: str,
    api_key: str,
    url: str,
    api_style: str = "dashscope",
    instruct: str = "",
    timeout: int = 30,
) -> list[int]:
    if not api_key:
        raise ValueError("DASHSCOPE_API_KEY is required for rerank")
    if api_style == "openai":
        payload = {
            "model": model,
            "query": query,
            "documents": documents,
            "top_n": top_n,
        }
        if instruct:
            payload["instruct"] = instruct
    else:
        payload = {
            "model": model,
            "input": {"query": query, "documents": documents},
            "parameters": {"top_n": top_n},
        }
    data = json.dumps(payload).encode("utf-8")
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

    def _post():
        req = urllib.request.Request(url, data=data, headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))

    resp = await asyncio.to_thread(_post)
    return _parse_rerank_response(resp)


async def main():
    load_dotenv(dotenv_path=ENV_PATH)
    parser = argparse.ArgumentParser(description="Query LightRAG (hybrid mode by default)")
    parser.add_argument("query", type=str, nargs="?", default=os.getenv("LR_QUERY", ""), help="user question")
    parser.add_argument("--mode", type=str, default=os.getenv("LR_QUERY_MODE", "hybrid"))
    parser.add_argument(
        "--working-dir",
        type=str,
        default=os.getenv("LR_WORKING_DIR", str(DEFAULT_WORKING_DIR)),
        help="LightRAG working directory (storage path)",
    )
    parser.add_argument(
        "--working-dirs",
        type=str,
        default=os.getenv("LR_WORKING_DIRS", ""),
        help="comma-separated working dirs for multi-store retrieval",
    )
    parser.add_argument("--only-context", action="store_true", default=os.getenv("LR_ONLY_CONTEXT", "") != "")
    parser.add_argument(
        "--use-built-prompt",
        action="store_true",
        default=os.getenv("LR_USE_BUILT_PROMPT", "") != "",
        help="use local _build_prompt to generate final answer",
    )
    args = parser.parse_args()
    if not args.query:
        if sys.stdin and sys.stdin.isatty():
            args.query = input("Query: ").strip()
        if not args.query:
            print("Missing query. Provide it as a positional arg or set LR_QUERY in .env.")
            return

    setup_logger("lightrag", level=os.getenv("LR_LOG_LEVEL", "INFO"))
    zh_system_prompt = os.getenv("LR_SYSTEM_PROMPT", DEFAULT_ZH_SYSTEM_PROMPT)

    llm_model_func, llm_model_name = _build_llm_func()
    embedding_func = _build_embedding_func()

    vector_storage = os.getenv("LR_VECTOR_STORAGE", "NanoVectorDBStorage")
    graph_storage = os.getenv("LR_GRAPH_STORAGE", "NetworkXStorage")
    vector_kwargs = _get_env_json("LR_VECTOR_DB_KWARGS") or {}
    graph_kwargs = _get_env_json("LR_GRAPH_DB_KWARGS") or {}
    max_parallel_insert = _get_env_int("LR_MAX_PARALLEL_INSERT", 2)

    # LightRAG constructor args vary by version. Only pass supported kwargs.
    rag_kwargs = dict(
        working_dir="",
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

    working_dirs = _normalize_working_dirs(args.working_dirs, args.working_dir)
    results: list[tuple[Path, Any]] = []

    for working_dir in working_dirs:
        rag_kwargs["working_dir"] = str(working_dir)
        rag = LightRAG(**rag_kwargs)
        await rag.initialize_storages()
        try:
            param = QueryParam(mode=args.mode)
            if hasattr(param, "system_prompt"):
                try:
                    param.system_prompt = zh_system_prompt
                except Exception:
                    pass
            if hasattr(param, "prompt"):
                try:
                    param.prompt = zh_system_prompt
                except Exception:
                    pass
            if hasattr(param, "response_language"):
                try:
                    param.response_language = "zh"
                except Exception:
                    pass
            # Disable LightRAG built-in rerank to avoid warnings; we use DashScope rerank here.
            if hasattr(param, "enable_rerank"):
                try:
                    param.enable_rerank = False
                except Exception:
                    pass

            result = await rag.aquery(args.query, param=param)
            results.append((working_dir, result))
        finally:
            await rag.finalize_storages()

    use_built_prompt = args.only_context or args.use_built_prompt or len(working_dirs) > 1
    if use_built_prompt:
        contexts_all: list[str] = []
        for working_dir, result in results:
            contexts = _ensure_context_list(result)
            if len(working_dirs) > 1:
                source = Path(working_dir).name
                meaningful = [
                    c for c in contexts if c and c.strip() and c.strip() not in ("{}", "[]", "None")
                ]
                if not meaningful:
                    meaningful = ["(未检索到相关内容)"]
                contexts_all.extend([f"来源：{source}\n{c}" for c in meaningful])
            else:
                contexts_all.extend(contexts)

        context = "\n\n".join(contexts_all)
        prompt = _build_prompt(args.query, context)
        answer = await llm_model_func(prompt, system_prompt=zh_system_prompt)
        output_text = _format_output_content(answer)
    else:
        output_text = _format_output_content(results[0][1])
    print(output_text)
    _save_output(output_text)


if __name__ == "__main__":
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        asyncio.run(main())
    else:
        loop.create_task(main())
