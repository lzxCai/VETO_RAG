import argparse
import subprocess
import sys
import shutil
from datetime import datetime
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parent
MD_DIR = ROOT_DIR / "MDoutput"
PDF_DIR = ROOT_DIR / "PDFoutput"
QUERY_SCRIPT = ROOT_DIR / "ragmain" / "lightrag_query.py"


def _latest_md_file(exclude: set[Path]) -> Path | None:
    if not MD_DIR.exists():
        return None
    candidates = [p for p in MD_DIR.glob("*.md") if p not in exclude]
    if not candidates:
        return None
    return max(candidates, key=lambda p: p.stat().st_mtime)


def _run_query(content: str) -> int:
    cmd = [sys.executable, str(QUERY_SCRIPT), content, "--use-built-prompt"]
    return subprocess.call(cmd)


def _convert_md_to_pdf(md_path: Path, pdf_path: Path) -> bool:
    pandoc = shutil.which("pandoc")
    if not pandoc:
        print("未找到 pandoc，无法转换 PDF。请先安装：brew install pandoc")
        return False

    engine = None
    for candidate in ("wkhtmltopdf", "weasyprint", "xelatex", "pdflatex"):
        if shutil.which(candidate):
            engine = candidate
            break

    if not engine:
        print("未找到可用的 PDF 引擎。你可以选择安装其中一个：")
        print("- wkhtmltopdf: brew install wkhtmltopdf")
        print("- TeX（xelatex/pdflatex）: brew install --cask mactex-no-gui")
        print("- weasyprint: pip install weasyprint")
        return False

    cmd = [pandoc, str(md_path), "-o", str(pdf_path), f"--pdf-engine={engine}"]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print("PDF 转换失败。")
        if result.stderr:
            print(result.stderr.strip())
        return False
    return True


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run lightrag_query and convert the latest MDoutput markdown to PDFoutput."
    )
    parser.add_argument("content", nargs="?", default="", help="query content")
    args = parser.parse_args()

    content = args.content.strip()
    if not content:
        try:
            content = input("请输入内容: ").strip()
        except EOFError:
            content = ""
    if not content:
        print("缺少输入内容。")
        return 1

    before = set(MD_DIR.glob("*.md")) if MD_DIR.exists() else set()
    ret = _run_query(content)
    if ret != 0:
        print("查询失败，未生成 MD 文件。")
        return ret

    md_path = _latest_md_file(before)
    if not md_path:
        print("未找到新生成的 MD 文件。")
        return 1

    PDF_DIR.mkdir(parents=True, exist_ok=True)
    pdf_path = PDF_DIR / f"{md_path.stem}.pdf"
    if not _convert_md_to_pdf(md_path, pdf_path):
        return 1

    print(f"PDF 已生成: {pdf_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
