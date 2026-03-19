import argparse
import asyncio
import json
import os
import inspect
import re
from pathlib import Path
from typing import Iterable, List, Optional

from lightrag import LightRAG
from lightrag.utils import setup_logger, wrap_embedding_func_with_attrs
from dotenv import load_dotenv


ROOT_DIR = Path(__file__).resolve().parent.parent
ENV_PATH = Path(__file__).resolve().parent / ".env"
load_dotenv(dotenv_path=ENV_PATH)
DEFAULT_MD_PATH = ROOT_DIR / "dataset" / "labor_law.md"
DEFAULT_WORKING_DIR = ROOT_DIR / "rag_storage" / "civil_code"


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


_FENCE_RE = re.compile(r"^\s*(```|~~~)")
_HEADING_RE = re.compile(r"^(#{1,6})\s+.+")
_TABLE_SEP_RE = re.compile(r"^\s*\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)+\|?\s*$")


def _split_markdown_sections(text: str, max_heading_level: int = 3) -> List[str]:
    sections: List[str] = []
    buf: List[str] = []
    in_code = False
    for line in text.splitlines():
        if _FENCE_RE.match(line):
            in_code = not in_code
        if not in_code:
            m = _HEADING_RE.match(line)
            if m and len(m.group(1)) <= max_heading_level:
                if buf:
                    section = "\n".join(buf).strip()
                    if section:
                        sections.append(section)
                    buf = []
                buf.append(line)
                continue
        buf.append(line)
    if buf:
        section = "\n".join(buf).strip()
        if section:
            sections.append(section)
    return sections or [text.strip()]


def _is_table_line(line: str) -> bool:
    return line.count("|") >= 2


def _split_section_into_blocks(section: str) -> List[str]:
    blocks: List[str] = []
    buf: List[str] = []
    in_code = False

    def flush():
        nonlocal buf
        if buf:
            block = "\n".join(buf).strip()
            if block:
                blocks.append(block)
            buf = []

    for line in section.splitlines():
        if _FENCE_RE.match(line):
            if not in_code:
                flush()
                in_code = True
                buf.append(line)
                continue
            in_code = False
            buf.append(line)
            flush()
            continue

        if in_code:
            buf.append(line)
            continue

        if not line.strip():
            flush()
            continue

        if _is_table_line(line):
            if buf and not _is_table_line(buf[-1]):
                flush()
            buf.append(line)
            continue

        if buf and _is_table_line(buf[-1]):
            flush()
        buf.append(line)

    flush()
    return blocks


def _is_protected_block(block: str) -> bool:
    stripped = block.lstrip()
    if stripped.startswith("```") or stripped.startswith("~~~"):
        return True
    lines = block.splitlines()
    if len(lines) >= 2 and any(_TABLE_SEP_RE.match(l) for l in lines):
        return True
    return False


def _chunk_blocks(blocks: List[str], max_chars: int, overlap: int) -> List[str]:
    chunks: List[str] = []
    buf: List[str] = []
    buf_len = 0

    def flush():
        nonlocal buf, buf_len
        if buf:
            chunk = "\n\n".join(buf).strip()
            if chunk:
                chunks.append(chunk)
            buf = []
            buf_len = 0

    for block in blocks:
        if not block:
            continue
        block_len = len(block)
        protected = _is_protected_block(block)

        if buf_len + block_len + 2 > max_chars and buf:
            flush()
            if overlap > 0 and chunks:
                tail = chunks[-1][-overlap:]
                buf = [tail]
                buf_len = len(tail)

        if protected and block_len > max_chars:
            # Keep tables/code fences intact even if they exceed max_chars.
            if buf:
                flush()
            chunks.append(block)
            continue

        buf.append(block)
        buf_len += block_len + 2

    flush()
    return chunks


def _chunk_text(text: str, max_chars: int = 1000, overlap: int = 100) -> List[str]:
    # Heading-aware Markdown chunking with structure protection.
    sections = _split_markdown_sections(text, max_heading_level=3)
    chunks: List[str] = []
    for section in sections:
        section = section.strip()
        if not section:
            continue
        if len(section) <= max_chars:
            chunks.append(section)
            continue
        blocks = _split_section_into_blocks(section)
        if not blocks:
            blocks = [section]
        chunks.extend(_chunk_blocks(blocks, max_chars=max_chars, overlap=overlap))
    return [c for c in chunks if c.strip()]


def _load_chunks_from_file(path: Path) -> List[str]:
    if not path.exists():
        raise FileNotFoundError(f"chunks file not found: {path}")
    if path.suffix.lower() == ".json":
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, list):
            if all(isinstance(x, str) for x in data):
                return data
            # Accept list of objects with text/content fields
            chunks = []
            for item in data:
                if isinstance(item, dict):
                    text = item.get("text") or item.get("content")
                    if text:
                        chunks.append(text)
            return chunks
        raise ValueError("chunks json must be a list")
    if path.suffix.lower() == ".jsonl":
        chunks = []
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            obj = json.loads(line)
            if isinstance(obj, dict):
                text = obj.get("text") or obj.get("content")
                if text:
                    chunks.append(text)
            elif isinstance(obj, str):
                chunks.append(obj)
        return chunks
    # Fallback: one chunk per non-empty line
    return [line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


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
        )
        async def embedding_func(texts: list[str]):
            return model.encode(texts, convert_to_numpy=True)

        return embedding_func

    raise ValueError(f"Unsupported LR_EMBED_PROVIDER: {provider}")


def _build_llm_func():
    provider = os.getenv("LR_LLM_PROVIDER", "openai_like").lower()
    if provider == "openai_like":
        from lightrag.llm.openai import openai_complete_if_cache

        llm_model = os.getenv("LR_LLM_MODEL", "qwen-plus")
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


async def main():
    parser = argparse.ArgumentParser(description="Embed documents with LightRAG")
    parser.add_argument("--input", type=str, default=str(DEFAULT_MD_PATH))
    parser.add_argument("--chunks", type=str, default=os.getenv("LR_CHUNKS_PATH", ""))
    parser.add_argument("--chunk-size", type=int, default=_get_env_int("LR_CHUNK_SIZE", 1000))
    parser.add_argument("--chunk-overlap", type=int, default=_get_env_int("LR_CHUNK_OVERLAP", 100))
    args = parser.parse_args()

    setup_logger("lightrag", level=os.getenv("LR_LOG_LEVEL", "INFO"))

    input_path = Path(args.input)
    if not input_path.exists():
        raise FileNotFoundError(f"input file not found: {input_path}")

    if args.chunks:
        chunks = _load_chunks_from_file(Path(args.chunks))
    else:
        chunks = _chunk_text(_read_text(input_path), max_chars=args.chunk_size, overlap=args.chunk_overlap)

    if not chunks:
        raise ValueError("no chunks to insert")

    llm_model_func, llm_model_name = _build_llm_func()
    embedding_func = _build_embedding_func()

    vector_storage = os.getenv("LR_VECTOR_STORAGE", "NanoVectorDBStorage")
    graph_storage = os.getenv("LR_GRAPH_STORAGE", "NetworkXStorage")
    vector_kwargs = _get_env_json("LR_VECTOR_DB_KWARGS") or {}
    graph_kwargs = _get_env_json("LR_GRAPH_DB_KWARGS") or {}
    max_parallel_insert = _get_env_int("LR_MAX_PARALLEL_INSERT", 2)

    # LightRAG constructor args vary by version. Only pass supported kwargs.
    rag_kwargs = dict(
        working_dir=str(Path(os.getenv("LR_WORKING_DIR", str(DEFAULT_WORKING_DIR)))),
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

    rag = LightRAG(**rag_kwargs)

    await rag.initialize_storages()

    file_paths = [str(input_path)] * len(chunks)
    await rag.ainsert(chunks, file_paths=file_paths)
    print(f"Inserted {len(chunks)} chunks into LightRAG storage.")


if __name__ == "__main__":
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        asyncio.run(main())
    else:
        loop.create_task(main())
