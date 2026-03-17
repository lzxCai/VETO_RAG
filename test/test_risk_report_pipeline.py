import json
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.services.risk_report_pipeline import (
    generate_report_context_for_contract,
    save_report_context,
)


PDF_PATH = PROJECT_ROOT / "module_1_2" / "data" / "P020210610345840579453.pdf"
REPORT_CONTEXT_PATH = PROJECT_ROOT / "data" / "output" / "report_context.json"


def main() -> None:
    if not PDF_PATH.exists():
        raise FileNotFoundError(f"未找到测试 PDF: {PDF_PATH}")

    report_context = generate_report_context_for_contract(str(PDF_PATH))
    save_report_context(report_context, str(REPORT_CONTEXT_PATH))

    print("=" * 100)
    print("report_context 摘要")
    print(
        json.dumps(
            {
                "contract_source": report_context.get("contract_source"),
                "summary": report_context.get("summary", {}),
                "risk_item_count": len(report_context.get("risk_items", [])),
            },
            ensure_ascii=False,
            indent=2,
        )
    )

    for item in report_context.get("risk_items", [])[:5]:
        preview = {
            "clause_id": item.get("clause_id"),
            "risk_type": item.get("risk_type"),
            "clause_title": item.get("clause_title"),
            "legal_basis_count": len(item.get("legal_basis_results", [])),
            "retrieval_notes": item.get("retrieval_notes", []),
            "legal_basis_titles": [
                basis.get("title", "") for basis in item.get("legal_basis_results", [])[:3]
            ],
        }
        print(json.dumps(preview, ensure_ascii=False, indent=2))

    print("=" * 100)
    print(f"已保存 report_context: {REPORT_CONTEXT_PATH}")

    cmd = [sys.executable, str(PROJECT_ROOT / "main.py"), "--report-context", str(REPORT_CONTEXT_PATH)]
    result = subprocess.run(cmd, cwd=str(PROJECT_ROOT), text=True)

    print("=" * 100)
    print(f"main.py 退出码: {result.returncode}")
    if result.returncode != 0:
        print("若当前机器未安装 pandoc / PDF 引擎，Markdown 已生成但 PDF 可能不会成功导出。")


if __name__ == "__main__":
    main()
