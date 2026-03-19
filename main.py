"""
统一报告导出入口（Markdown / PDF）。

说明：
- 项目内真正的后端服务入口在 `backend/main.py`，而不是这里。
- `app/main.py`、`backend/rag_wrapper.py` 会调用本文件：
  - `python main.py --report-context <path>`：根据 report_context 生成正式审查报告（Markdown），并尽可能导出 PDF。
  - `python main.py "<question>"`：执行检索问答（供后端 /chat 使用）。
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent
LIGHTRAG_QUERY = PROJECT_ROOT / "ragmain" / "lightrag_query.py"
REPORT_CSS = PROJECT_ROOT / "report_style.css"
MD_OUTPUT_DIR = PROJECT_ROOT / "MDoutput"
PDF_OUTPUT_DIR = PROJECT_ROOT / "PDFoutput"


def _run(cmd: list[str]) -> int:
    result = subprocess.run(cmd, cwd=str(PROJECT_ROOT))
    return result.returncode


def _find_latest_md() -> Path | None:
    if not MD_OUTPUT_DIR.exists():
        return None
    candidates = sorted(MD_OUTPUT_DIR.glob("*.md"), key=lambda p: p.stat().st_mtime, reverse=True)
    return candidates[0] if candidates else None


def _export_pdf_from_md(md_path: Path) -> int:
    PDF_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    out_pdf = PDF_OUTPUT_DIR / (md_path.stem + ".pdf")

    pandoc = shutil.which("pandoc")
    if pandoc:
        cmd = [
            pandoc,
            str(md_path),
            "-o",
            str(out_pdf),
            "--standalone",
            "-f",
            "markdown",
        ]
        # 若可用，注入 CSS（与网页黑白绿主题一致的正式报告版式）
        if REPORT_CSS.exists():
            cmd.extend(["--css", str(REPORT_CSS)])
        wk = shutil.which("wkhtmltopdf")
        if wk:
            cmd.extend(["--pdf-engine", wk])
            # A4 边距对齐常见合同报告 PDF
            cmd.extend(
                [
                    "--pdf-engine-opt=--margin-top",
                    "--pdf-engine-opt=12mm",
                    "--pdf-engine-opt=--margin-bottom",
                    "--pdf-engine-opt=12mm",
                    "--pdf-engine-opt=--margin-left",
                    "--pdf-engine-opt=14mm",
                    "--pdf-engine-opt=--margin-right",
                    "--pdf-engine-opt=14mm",
                    "--pdf-engine-opt=--encoding",
                    "--pdf-engine-opt=utf-8",
                ]
            )
        return _run(cmd)

    # 没有 pandoc 时不强求 PDF
    print("未检测到 pandoc，跳过 PDF 导出（已生成 Markdown）。")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="生成劳动合同风险审查报告（Markdown/PDF）或执行检索问答。")
    parser.add_argument("query", nargs="?", default="", help="用户问题（用于检索问答）")
    parser.add_argument("--report-context", default="", help="report_context.json 路径")
    parser.add_argument("--no-pdf", action="store_true", help="只生成 Markdown，不导出 PDF")
    args = parser.parse_args()

    if args.report_context:
        cmd = [sys.executable, str(LIGHTRAG_QUERY), "--report-context", args.report_context]
        code = _run(cmd)
        if code != 0:
            return code

        latest_md = _find_latest_md()
        if not latest_md:
            print("已生成报告，但未找到 MDoutput 下的 markdown 文件。")
            return 1

        if args.no_pdf:
            print(f"Markdown 已生成：{latest_md}")
            return 0

        pdf_code = _export_pdf_from_md(latest_md)
        if pdf_code == 0:
            print(f"PDF 已导出：{(PDF_OUTPUT_DIR / (latest_md.stem + '.pdf'))}")
        return pdf_code

    # query mode
    if not args.query:
        print("缺少 query 或 --report-context。")
        return 2
    cmd = [sys.executable, str(LIGHTRAG_QUERY), args.query]
    return _run(cmd)


if __name__ == "__main__":
    raise SystemExit(main())