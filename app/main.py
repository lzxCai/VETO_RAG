from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import List, Sequence, Union


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SAMPLE_INPUT = PROJECT_ROOT / "module_1_2" / "data" / "P020210610345840579453.pdf"
DEFAULT_REPORT_CONTEXT_PATH = PROJECT_ROOT / "data" / "output" / "report_context.json"
ROOT_MAIN_PATH = PROJECT_ROOT / "main.py"

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.services.risk_report_pipeline import (  # noqa: E402
    generate_report_context_for_contract,
    save_report_context,
)


DocumentInput = Union[str, List[str]]


def _resolve_input_source(raw_input: str) -> DocumentInput:
    value = (raw_input or "").strip()
    if not value:
        if DEFAULT_SAMPLE_INPUT.exists():
            return str(DEFAULT_SAMPLE_INPUT)
        raise FileNotFoundError("未提供输入文件，且默认样例文件不存在。")

    if "," in value:
        parts = [part.strip() for part in value.split(",") if part.strip()]
        if not parts:
            raise ValueError("输入路径为空。")
        return parts
    return value


def _validate_input_source(input_source: DocumentInput) -> None:
    paths: Sequence[str]
    if isinstance(input_source, list):
        paths = input_source
    else:
        paths = [input_source]

    missing = [path for path in paths if not Path(path).exists()]
    if missing:
        raise FileNotFoundError(f"以下输入文件不存在: {missing}")


def _run_report_export(report_context_path: Path) -> int:
    cmd = [
        sys.executable,
        str(ROOT_MAIN_PATH),
        "--report-context",
        str(report_context_path),
    ]
    result = subprocess.run(cmd, cwd=str(PROJECT_ROOT), text=True)
    return result.returncode


def _print_summary(report_context: dict, report_context_path: Path) -> None:
    summary = report_context.get("summary", {})
    parse_meta = report_context.get("parse_meta", {})
    output = {
        "contract_source": report_context.get("contract_source"),
        "report_context_path": str(report_context_path),
        "summary": summary,
        "parse_meta": {
            "parser_used": parse_meta.get("parser_used"),
            "quality_flag": parse_meta.get("quality_flag"),
            "metrics": parse_meta.get("metrics", {}),
        },
        "risk_item_count": len(report_context.get("risk_items", [])),
    }
    print(json.dumps(output, ensure_ascii=False, indent=2))


def main() -> int:
    parser = argparse.ArgumentParser(
        description="统一执行合同解析、风险识别、法律依据检索与 Markdown/PDF 报告导出。"
    )
    parser.add_argument(
        "input_source",
        nargs="?",
        default="",
        help="合同输入路径；支持单个 PDF/图片，或逗号分隔的多图路径。",
    )
    parser.add_argument(
        "--parser",
        default="auto",
        choices=["auto", "bailian", "llamaparse", "local"],
        help="合同解析器选择。",
    )
    parser.add_argument(
        "--top-k-per-kb",
        type=int,
        default=3,
        help="每个法律知识库最多保留的法律依据条数。",
    )
    parser.add_argument(
        "--report-context-out",
        default=str(DEFAULT_REPORT_CONTEXT_PATH),
        help="report_context.json 输出路径。",
    )
    parser.add_argument(
        "--enable-image-preprocess",
        action="store_true",
        help="是否启用图片预处理入口。",
    )
    parser.add_argument(
        "--no-pdf",
        action="store_true",
        help="只生成 report_context，不继续导出 Markdown/PDF。",
    )
    args = parser.parse_args()

    try:
        input_source = _resolve_input_source(args.input_source)
        _validate_input_source(input_source)

        report_context = generate_report_context_for_contract(
            contract_source=input_source,
            parser=args.parser,
            fallback_to_legacy=True,
            enable_image_preprocess=args.enable_image_preprocess,
            top_k_per_kb=args.top_k_per_kb,
        )
        report_context_path = Path(
            save_report_context(report_context, args.report_context_out)
        )

        _print_summary(report_context, report_context_path)

        if args.no_pdf:
            print("已生成 report_context，跳过 Markdown/PDF 导出。")
            return 0

        export_code = _run_report_export(report_context_path)
        if export_code != 0:
            print("报告导出失败。report_context 已生成，可单独排查根目录 main.py 的导出阶段。")
            return export_code

        print("主链路执行完成。Markdown/PDF 报告已导出。")
        return 0
    except Exception as exc:  # noqa: BLE001
        print(f"主链路执行失败: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
