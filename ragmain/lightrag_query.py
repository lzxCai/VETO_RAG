import argparse
import asyncio
import inspect
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from dotenv import load_dotenv
from lightrag import LightRAG, QueryParam
from lightrag.utils import setup_logger, wrap_embedding_func_with_attrs


ROOT_DIR = Path(__file__).resolve().parent.parent
ENV_PATH = Path(__file__).resolve().parent / '.env'
DEFAULT_WORKING_DIR = ROOT_DIR / 'rag_storage' / 'civil_code'
DEFAULT_ZH_SYSTEM_PROMPT = '你是一个只使用中文回答的劳动合同审查报告助手，必须基于提供的材料严谨作答。'


def _get_env_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if not value:
        return default
    try:
        return int(value)
    except ValueError as exc:
        raise ValueError(f'{name} must be int, got: {value}') from exc


def _get_env_json(name: str) -> Optional[dict]:
    value = os.getenv(name)
    if not value:
        return None
    return json.loads(value)


def _build_embedding_func():
    provider = os.getenv('LR_EMBED_PROVIDER', 'openai_like').lower()
    if provider == 'openai_like':
        from lightrag.llm.openai import openai_embed

        embed_model = os.getenv('LR_EMBED_MODEL', 'text-embedding-v3')
        embed_dim = _get_env_int('LR_EMBED_DIM', 1024)
        base_url = os.getenv(
            'LR_EMBED_BASE_URL',
            os.getenv('LR_LLM_BASE_URL', 'https://dashscope.aliyuncs.com/compatible-mode/v1'),
        )
        api_key = os.getenv(
            'LR_EMBED_API_KEY',
            os.getenv('LR_LLM_API_KEY', os.getenv('DASHSCOPE_API_KEY', '')),
        )
        if not api_key:
            raise ValueError('LR_EMBED_API_KEY is required for openai_like embedding provider')

        @wrap_embedding_func_with_attrs(
            embedding_dim=embed_dim,
            max_token_size=_get_env_int('LR_EMBED_MAX_TOKENS', 8192),
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

    raise ValueError(f'Unsupported LR_EMBED_PROVIDER: {provider}')


def _build_llm_func():
    provider = os.getenv('LR_LLM_PROVIDER', 'openai_like').lower()
    if provider == 'openai_like':
        from lightrag.llm.openai import openai_complete_if_cache

        llm_model = os.getenv('LR_LLM_MODEL', 'qwen3-max')
        base_url = os.getenv('LR_LLM_BASE_URL', 'https://dashscope.aliyuncs.com/compatible-mode/v1')
        api_key = os.getenv('LR_LLM_API_KEY', os.getenv('DASHSCOPE_API_KEY', ''))
        if not api_key:
            raise ValueError('LR_LLM_API_KEY (or DASHSCOPE_API_KEY) is required for openai_like LLM provider')

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

    raise ValueError(f'Unsupported LR_LLM_PROVIDER: {provider}')


def _build_prompt(query: str, context: str) -> str:
    return (
        '你现在是一名专业的劳动合同与法律依据分析助手。\n'
        '请基于提供的上下文，用中文给出严谨、清晰、结构化的回答。\n'
        '如果上下文不足以支持明确结论，请直接说明证据不足，不要补充未提供的法条。\n\n'
        f'Context:\n{context}\n\n'
        f'Question: {query}\n'
        'Answer:'
    )


def _build_report_prompt(report_context: dict) -> str:
    contract_source = report_context.get('contract_source', '')
    summary = report_context.get('summary', {})
    risk_items = report_context.get('risk_items', [])

    risk_sections: list[str] = []
    for idx, item in enumerate(risk_items, start=1):
        legal_basis = item.get('legal_basis_results', [])
        retrieval_notes = ', '.join(item.get('retrieval_notes', []))
        legal_basis_text = '\n'.join(
            [
                f"- [{basis.get('kb_name', '')}] {basis.get('title', '')}\n  {basis.get('content', '')}"
                for basis in legal_basis[:4]
            ]
        )
        risk_sections.append(
            (
                f"### 风险条款 {idx}\n"
                f"- clause_id: {item.get('clause_id', '')}\n"
                f"- 风险类型: {item.get('risk_type', '')}\n"
                f"- 条款标题: {item.get('clause_title', '')}\n"
                f"- 所属章节: {item.get('section_title', '')}\n"
                f"- 条款正文:\n{item.get('clause_text', '')}\n\n"
                f"- 检索说明: {retrieval_notes or '未提供'}\n"
                f"- 法律依据:\n{legal_basis_text or '未检索到明确法律依据，建议人工复核。'}"
            )
        )

    body = '\n\n'.join(risk_sections)
    summary_json = json.dumps(summary, ensure_ascii=False)
    return (
        '你是一名劳动合同风险审查报告撰写助手。请根据提供的风险条款和法律依据，生成一份正式、专业、适合交付的中文 Markdown 报告。\n'
        '必须严格遵守以下要求：\n'
        '1. 报告必须包含以下一级章节：封面信息、摘要、风险总览、逐条风险分析、结论与签约建议、说明。\n'
        '2. 报告正文只能依据提供的 risk_items 与 legal_basis_results 撰写，不得引用未提供的法律依据。\n'
        '3. 若某条风险的法律依据不足或检索结果不够精确，必须明确写出“法律依据待补充/建议人工复核”。\n'
        '4. 不要输出 Knowledge Graph、检索原始噪声、JSON、代码块或系统说明。\n'
        '5. 报告语气正式、克制、专业，适合法律审查与项目交付。\n'
        '6. 风险总览部分请用 Markdown 表格。逐条风险分析请统一使用小标题、风险类型、条款内容、法律依据、风险说明、修改建议的结构。\n'
        '7. 首页顶部请输出报告标题、副标题、合同来源、生成日期。\n'
        '8. 不要写“基于常识性劳动合规要求”“虽未提供仍保留分析”等说明；如果依据不足，只能写“法律依据待补充/建议人工复核”。\n'
        '9. “说明”章节只保留这一句：本报告不构成正式法律意见，具体签约决策应结合专业律师意见作出。\n\n'
        f'合同来源：{contract_source}\n'
        f'合同摘要：{summary_json}\n\n'
        f'风险条款明细：\n{body}\n'
    )


def _extract_context(result: Any) -> Optional[str]:
    if isinstance(result, dict):
        for key in ('context', 'contexts', 'source', 'sources', 'references'):
            if key in result and result[key]:
                if isinstance(result[key], str):
                    return result[key]
                if isinstance(result[key], list):
                    return '\n\n'.join([str(x) for x in result[key]])
        if 'result' in result and isinstance(result['result'], str):
            return result['result']
    if isinstance(result, list):
        return '\n\n'.join([str(x) for x in result])
    return None


def _extract_context_list(result: Any) -> Optional[list[str]]:
    if isinstance(result, dict):
        for key in ('contexts', 'context', 'sources', 'source', 'references'):
            if key in result and result[key]:
                if isinstance(result[key], list):
                    return [str(x) for x in result[key] if str(x).strip()]
                if isinstance(result[key], str):
                    return [x.strip() for x in result[key].split('\n\n') if x.strip()]
        if 'result' in result and isinstance(result['result'], str):
            return [x.strip() for x in result['result'].split('\n\n') if x.strip()]
    if isinstance(result, list):
        return [str(x) for x in result if str(x).strip()]
    if isinstance(result, str):
        return [x.strip() for x in result.split('\n\n') if x.strip()]
    return None


def _format_output_content(result: Any) -> str:
    if isinstance(result, str):
        return result
    try:
        return json.dumps(result, ensure_ascii=False, indent=2)
    except TypeError:
        return str(result)


def _save_output(content: str) -> Path:
    output_dir = ROOT_DIR / 'MDoutput'
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    output_path = output_dir / f'{timestamp}.md'
    output_path.write_text(content, encoding='utf-8')
    return output_path


def _normalize_working_dirs(multi_dirs: str | None, single_dir: str) -> list[Path]:
    if multi_dirs:
        parts = [p.strip() for p in multi_dirs.split(',') if p.strip()]
        if parts:
            return [Path(p) for p in parts]
    return [Path(single_dir)]


def _ensure_context_list(result: Any) -> list[str]:
    contexts = _extract_context_list(result)
    if not contexts:
        context = _extract_context(result) or str(result)
        contexts = [context]
    return contexts


def _load_report_context(report_context_path: str) -> dict:
    path = Path(report_context_path)
    if not path.exists():
        raise FileNotFoundError(f'report context not found: {path}')
    return json.loads(path.read_text(encoding='utf-8'))


async def main():
    if ENV_PATH.exists():
        load_dotenv(dotenv_path=ENV_PATH)
    parser = argparse.ArgumentParser(description='Query LightRAG or generate a report from prebuilt context')
    parser.add_argument('query', type=str, nargs='?', default=os.getenv('LR_QUERY', ''), help='user question')
    parser.add_argument('--report-context', type=str, default='', help='prebuilt report context json path')
    parser.add_argument('--mode', type=str, default=os.getenv('LR_QUERY_MODE', 'hybrid'))
    parser.add_argument(
        '--working-dir',
        type=str,
        default=os.getenv('LR_WORKING_DIR', str(DEFAULT_WORKING_DIR)),
        help='LightRAG working directory (storage path)',
    )
    parser.add_argument(
        '--working-dirs',
        type=str,
        default=os.getenv('LR_WORKING_DIRS', ''),
        help='comma-separated working dirs for multi-store retrieval',
    )
    parser.add_argument('--only-context', action='store_true', default=os.getenv('LR_ONLY_CONTEXT', '') != '')
    parser.add_argument(
        '--use-built-prompt',
        action='store_true',
        default=os.getenv('LR_USE_BUILT_PROMPT', '') != '',
        help='use local _build_prompt to generate final answer',
    )
    args = parser.parse_args()

    if not args.query and not args.report_context:
        if sys.stdin and sys.stdin.isatty():
            args.query = input('Query: ').strip()
        if not args.query:
            print('Missing query. Provide it as a positional arg or set LR_QUERY in .env.')
            return

    setup_logger('lightrag', level=os.getenv('LR_LOG_LEVEL', 'INFO'))
    zh_system_prompt = os.getenv('LR_SYSTEM_PROMPT', DEFAULT_ZH_SYSTEM_PROMPT)
    llm_model_func, llm_model_name = _build_llm_func()

    if args.report_context:
        report_context = _load_report_context(args.report_context)
        prompt = _build_report_prompt(report_context)
        output_text = _format_output_content(await llm_model_func(prompt, system_prompt=zh_system_prompt))
        print(output_text)
        _save_output(output_text)
        return

    embedding_func = _build_embedding_func()
    vector_storage = os.getenv('LR_VECTOR_STORAGE', 'NanoVectorDBStorage')
    graph_storage = os.getenv('LR_GRAPH_STORAGE', 'NetworkXStorage')
    vector_kwargs = _get_env_json('LR_VECTOR_DB_KWARGS') or {}
    graph_kwargs = _get_env_json('LR_GRAPH_DB_KWARGS') or {}
    max_parallel_insert = _get_env_int('LR_MAX_PARALLEL_INSERT', 2)

    rag_kwargs = dict(
        working_dir='',
        llm_model_func=llm_model_func,
        llm_model_name=llm_model_name,
        embedding_func=embedding_func,
        vector_storage=vector_storage,
        graph_storage=graph_storage,
        max_parallel_insert=max_parallel_insert,
    )
    sig = inspect.signature(LightRAG.__init__).parameters
    if vector_kwargs:
        for key in ('vector_db_storage_cls_kwargs', 'vector_storage_cls_kwargs'):
            if key in sig:
                rag_kwargs[key] = vector_kwargs
                break
    if graph_kwargs:
        for key in ('graph_storage_cls_kwargs', 'graph_db_storage_cls_kwargs'):
            if key in sig:
                rag_kwargs[key] = graph_kwargs
                break

    working_dirs = _normalize_working_dirs(args.working_dirs, args.working_dir)
    results: list[tuple[Path, Any]] = []

    for working_dir in working_dirs:
        rag_kwargs['working_dir'] = str(working_dir)
        rag = LightRAG(**rag_kwargs)
        await rag.initialize_storages()
        try:
            param = QueryParam(mode=args.mode)
            if hasattr(param, 'system_prompt'):
                try:
                    param.system_prompt = zh_system_prompt
                except Exception:
                    pass
            if hasattr(param, 'prompt'):
                try:
                    param.prompt = zh_system_prompt
                except Exception:
                    pass
            if hasattr(param, 'response_language'):
                try:
                    param.response_language = 'zh'
                except Exception:
                    pass
            if hasattr(param, 'enable_rerank'):
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
                    c for c in contexts if c and c.strip() and c.strip() not in ('{}', '[]', 'None')
                ]
                if not meaningful:
                    meaningful = ['(未检索到相关内容)']
                contexts_all.extend([f'来源：{source}\n{c}' for c in meaningful])
            else:
                contexts_all.extend(contexts)

        context = '\n\n'.join(contexts_all)
        prompt = _build_prompt(args.query, context)
        answer = await llm_model_func(prompt, system_prompt=zh_system_prompt)
        output_text = _format_output_content(answer)
    else:
        output_text = _format_output_content(results[0][1])
    print(output_text)
    _save_output(output_text)


if __name__ == '__main__':
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        asyncio.run(main())
    else:
        loop.create_task(main())
