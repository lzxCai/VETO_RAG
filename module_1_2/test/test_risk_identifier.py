import json
import os
from typing import Any, Dict

from app.services.risk_identifier import identify_contract_risks


INPUT_PATH = "data/output/classified_contract.json"
OUTPUT_PATH = "data/output/risk_identified_contract.json"


def build_mock_contract() -> Dict[str, Any]:
    """当第一模块输出不存在时，构造最小可运行样例。"""
    return {
        "main_body": [
            {
                "clause_id": "C1",
                "section_title": "一、劳动合同期限",
                "section": "第一条",
                "title": "试用期约定",
                "text": "试用期为8个月，公司可根据表现单方延长试用期。",
                "clause_type": "合同期限",
                "part": "main_body",
            },
            {
                "clause_id": "C2",
                "section_title": "四、劳动报酬",
                "section": "第六条",
                "title": "工资发放",
                "text": "工资由公司酌情发放，如经营困难可延期支付。",
                "clause_type": "劳动报酬",
                "part": "main_body",
            },
            {
                "clause_id": "C3",
                "section_title": "五、社会保险和福利待遇",
                "section": "第九条",
                "title": "社保约定",
                "text": "乙方自愿放弃社保，由乙方自行承担全部费用。",
                "clause_type": "社会保险和福利待遇",
                "part": "main_body",
            },
        ],
        "attachments": [],
    }


def load_contract_input() -> Dict[str, Any]:
    if os.path.exists(INPUT_PATH):
        with open(INPUT_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return build_mock_contract()


def main() -> None:
    contract_data = load_contract_input()
    risk_result = identify_contract_risks(contract_data)

    print("=" * 100)
    print("风险识别汇总")
    print(json.dumps(risk_result["summary"], ensure_ascii=False, indent=2))

    preview = risk_result["key_risk_clauses"][:12]
    print("=" * 100)
    print(f"重点风险条款预览（前 {len(preview)} 条）")
    for item in preview:
        print("-" * 100)
        print(f"clause_id: {item.get('clause_id')}")
        print(f"clause_type: {item.get('clause_type')}")
        print(f"risk_type: {item.get('risk_type')}")
        print(f"risk_level_preliminary: {item.get('risk_level_preliminary')}")
        print(f"trigger_phrases: {item.get('trigger_phrases')}")

    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(risk_result, f, ensure_ascii=False, indent=2)

    print("=" * 100)
    print(f"已保存风险识别结果到：{OUTPUT_PATH}")


if __name__ == "__main__":
    main()
