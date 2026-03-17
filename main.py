import argparse
import re
import shutil
import subprocess
import sys
import textwrap
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent
MD_DIR = ROOT_DIR / "MDoutput"
PDF_DIR = ROOT_DIR / "PDFoutput"
QUERY_SCRIPT = ROOT_DIR / "ragmain" / "lightrag_query.py"
REPORT_STYLE_PATH = ROOT_DIR / "report_style.css"
LOCAL_WKHTMLTOPDF = ROOT_DIR / "tools" / "wkhtmltox" / "wkhtmltox" / "bin" / "wkhtmltopdf.exe"


def _latest_md_file(exclude: set[Path]) -> Path | None:
    if not MD_DIR.exists():
        return None
    candidates = [p for p in MD_DIR.glob("*.md") if p not in exclude]
    if not candidates:
        return None
    return max(candidates, key=lambda p: p.stat().st_mtime)


def _run_query(content: str, report_context: str = "") -> int:
    cmd = [sys.executable, str(QUERY_SCRIPT)]
    if report_context:
        cmd.extend(["--report-context", report_context])
    else:
        cmd.extend([content, "--use-built-prompt"])
    return subprocess.call(cmd)


def _find_pandoc() -> str | None:
    pandoc = shutil.which("pandoc")
    if pandoc:
        return pandoc
    try:
        import pypandoc

        pandoc_path = pypandoc.get_pandoc_path()
        if pandoc_path and Path(pandoc_path).exists():
            return pandoc_path
        package_root = Path(pypandoc.__file__).resolve().parent
        bundled_candidates = [
            package_root / "files" / "pandoc.exe",
            package_root / "files" / "pandoc",
        ]
        for candidate in bundled_candidates:
            if candidate.exists():
                return str(candidate)
    except Exception:
        return None
    return None


def _find_weasyprint_engine() -> str | None:
    engine = shutil.which("weasyprint")
    if engine:
        return engine

    python_dir = Path(sys.executable).resolve().parent
    candidates = [
        python_dir / "Scripts" / "weasyprint.exe",
        python_dir / "weasyprint.exe",
    ]
    for candidate in candidates:
        if candidate.exists():
            return str(candidate)
    return None


def _find_wkhtmltopdf_engine() -> str | None:
    if LOCAL_WKHTMLTOPDF.exists():
        return str(LOCAL_WKHTMLTOPDF)
    engine = shutil.which("wkhtmltopdf")
    if engine:
        return engine
    return None


def _markdown_to_plain_text(md_text: str) -> str:
    text = md_text.replace("\r\n", "\n")
    text = re.sub(r"```.*?```", lambda m: m.group(0).replace("```", ""), text, flags=re.S)
    text = re.sub(r"^\s{0,3}#{1,6}\s*", "", text, flags=re.M)
    text = re.sub(r"\*\*(.*?)\*\*", r"\1", text)
    text = re.sub(r"\*(.*?)\*", r"\1", text)
    text = re.sub(r"`([^`]*)`", r"\1", text)
    text = re.sub(r"^\s*[-*+]\s+", "• ", text, flags=re.M)
    text = re.sub(r"\|", "  |  ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _wrap_text_for_pdf(text: str, width: int = 48) -> list[str]:
    lines: list[str] = []
    for paragraph in text.split("\n"):
        paragraph = paragraph.rstrip()
        if not paragraph:
            lines.append("")
            continue
        indent = ""
        content = paragraph
        if paragraph.startswith("• "):
            indent = "  "
            content = paragraph[2:]
            wrapped = textwrap.wrap(content, width=max(12, width - 2), break_long_words=False, break_on_hyphens=False)
            if not wrapped:
                lines.append("•")
                continue
            lines.append(f"• {wrapped[0]}")
            for extra in wrapped[1:]:
                lines.append(f"{indent}{extra}")
            continue

        wrapped = textwrap.wrap(content, width=width, break_long_words=False, break_on_hyphens=False)
        if wrapped:
            lines.extend(wrapped)
        else:
            lines.append(content)
    return lines


def _convert_md_to_pdf_with_pymupdf(md_path: Path, pdf_path: Path) -> bool:
    try:
        import fitz
    except ImportError as exc:
        print(f"PyMuPDF 导出依赖不可用：{exc}")
        return False

    font_path = Path(r"C:\Windows\Fonts\msyh.ttc")
    if not font_path.exists():
        font_path = Path(r"C:\Windows\Fonts\simsun.ttc")
    if not font_path.exists():
        print("未找到可用的中文字体文件，无法导出 PDF。")
        return False

    md_text = md_path.read_text(encoding="utf-8")
    plain_text = _markdown_to_plain_text(md_text)
    lines = _wrap_text_for_pdf(plain_text, width=48)

    try:
        doc = fitz.open()
        rect = fitz.paper_rect("a4")
        margin = 40
        line_height = 18
        max_lines = max(1, int((rect.height - margin * 2) // line_height))

        for start in range(0, len(lines), max_lines):
            page = doc.new_page(width=rect.width, height=rect.height)
            page.insert_font(fontname="F0", fontfile=str(font_path))
            chunk = "\n".join(lines[start : start + max_lines])
            text_rect = fitz.Rect(margin, margin, rect.width - margin, rect.height - margin)
            page.insert_textbox(
                text_rect,
                chunk,
                fontsize=11,
                fontname="F0",
                lineheight=1.5,
                color=(0, 0, 0),
                align=fitz.TEXT_ALIGN_LEFT,
            )

        doc.save(pdf_path)
        doc.close()
        return True
    except Exception as exc:
        print(f"PyMuPDF PDF 导出失败：{exc}")
        return False


def _convert_md_to_pdf(md_path: Path, pdf_path: Path) -> bool:
    pandoc = _find_pandoc()
    if pandoc:
        engine = _find_wkhtmltopdf_engine()
        if not engine:
            engine = _find_weasyprint_engine()
        if not engine:
            for candidate in ("xelatex", "pdflatex"):
                located = shutil.which(candidate)
                if located:
                    engine = located
                    break

        if engine:
            cmd = [
                pandoc,
                str(md_path),
                "-o",
                str(pdf_path),
                f"--pdf-engine={engine}",
                "--standalone",
            ]
            if REPORT_STYLE_PATH.exists():
                cmd.extend(["--css", REPORT_STYLE_PATH.resolve().as_uri()])
            if "wkhtmltopdf" in str(engine).lower():
                cmd.extend(
                    [
                        "--pdf-engine-opt=--enable-local-file-access",
                        "--pdf-engine-opt=--encoding",
                        "--pdf-engine-opt=utf-8",
                        "--pdf-engine-opt=--margin-top",
                        "--pdf-engine-opt=18mm",
                        "--pdf-engine-opt=--margin-bottom",
                        "--pdf-engine-opt=18mm",
                        "--pdf-engine-opt=--margin-left",
                        "--pdf-engine-opt=16mm",
                        "--pdf-engine-opt=--margin-right",
                        "--pdf-engine-opt=16mm",
                        "--pdf-engine-opt=--footer-right",
                        "--pdf-engine-opt=[page]/[toPage]",
                        "--pdf-engine-opt=--footer-font-name",
                        "--pdf-engine-opt=Microsoft YaHei",
                        "--pdf-engine-opt=--footer-font-size",
                        "--pdf-engine-opt=9",
                        "--pdf-engine-opt=--footer-spacing",
                        "--pdf-engine-opt=6",
                    ]
                )
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode == 0:
                return True
            print("Pandoc PDF 转换失败，改用 PyMuPDF 纯 Python 导出。")
            if result.stderr:
                print(result.stderr.strip())
        else:
            print("未找到可用的 pandoc PDF 引擎，改用 PyMuPDF 纯 Python 导出。")
    else:
        print("未找到 pandoc，改用 PyMuPDF 纯 Python 导出。")

    return _convert_md_to_pdf_with_pymupdf(md_path, pdf_path)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run lightrag_query and convert the latest MDoutput markdown to PDFoutput."
    )
    parser.add_argument("content", nargs="?", default="", help="query content")
    parser.add_argument("--report-context", default="", help="prebuilt report context json path")
    args = parser.parse_args()

    content = args.content.strip()
    report_context = args.report_context.strip()
    if not content and not report_context:
        try:
            content = input("请输入内容：").strip()
        except EOFError:
            content = ""
    if not content and not report_context:
        print("缺少输入内容。")
        return 1

    before = set(MD_DIR.glob("*.md")) if MD_DIR.exists() else set()
    ret = _run_query(content, report_context=report_context)
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

    print(f"PDF 已生成：{pdf_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
