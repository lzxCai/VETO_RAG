import json
import os
import sys
from typing import Any, Dict, List, Union

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from app.services.contract_pipeline import run_contract_parsing_pipeline
from app.services.risk_identifier import identify_contract_risks


DEFAULT_PDF = "data/P020210610345840579453.pdf"
OUTPUT_CLASSIFIED = "data/output/classified_contract_from_bailian.json"
OUTPUT_RISK = "data/output/risk_identified_from_bailian.json"


def resolve_input_source() -> Union[str, List[str]]:
    """
    默认使用 PDF。
    如需测试图片，可设置环境变量 CONTRACT_IMAGE_INPUT：
    - 单张图片路径
    - 图片目录
    - 多图用英文逗号分隔：img1.jpg,img2.jpg,img3.png
    """
    image_input = os.getenv("CONTRACT_IMAGE_INPUT", "").strip()
    if not image_input:
        return DEFAULT_PDF

    if "," in image_input:
        return [item.strip() for item in image_input.split(",") if item.strip()]

    return image_input


def main() -> None:
    input_source = resolve_input_source()

    result: Dict[str, Any] = run_contract_parsing_pipeline(
        input_source=input_source,
        parser="auto",  # 优先百炼，PDF 可回退到 LlamaParse
        fallback_to_legacy=True,
        enable_image_preprocess=False,
        return_parse_meta=True,
    )

    classified_contract = result["classified_contract"]
    parse_meta = result["parse_meta"]

    print("=" * 100)
    print("解析器元信息")
    print(json.dumps(parse_meta, ensure_ascii=False, indent=2))

    os.makedirs(os.path.dirname(OUTPUT_CLASSIFIED), exist_ok=True)
    with open(OUTPUT_CLASSIFIED, "w", encoding="utf-8") as f:
        json.dump(classified_contract, f, ensure_ascii=False, indent=2)
    print(f"已保存结构化结果：{OUTPUT_CLASSIFIED}")

    risk_result = identify_contract_risks(classified_contract)
    with open(OUTPUT_RISK, "w", encoding="utf-8") as f:
        json.dump(risk_result, f, ensure_ascii=False, indent=2)
    print(f"已保存风险识别结果：{OUTPUT_RISK}")

    print("=" * 100)
    print("风险识别汇总")
    print(json.dumps(risk_result.get("summary", {}), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
