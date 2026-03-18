from app.services.pdf_reader import read_pdf_text
from app.services.text_cleaner import clean_pages, merge_pages
from app.services.clause_splitter import split_contract
from app.services.clause_classifier import classify_contract_parts
import json

pdf_path = "data/P020210610345840579453.pdf"

# 1. 读取 PDF
pages = read_pdf_text(pdf_path)

# 2. 清洗
cleaned_pages = clean_pages(pages)
full_text = merge_pages(cleaned_pages)

# 3. 切分
split_result = split_contract(full_text)

# 4. 分类
classified_result = classify_contract_parts(split_result)

main_body = classified_result["main_body"]
attachments = classified_result["attachments"]

print(f"正文共分类 {len(main_body)} 个条款")
print(f"附件共分类 {len(attachments)} 个\n")

print("=" * 100)
print("【正文前 12 条分类结果】")
for clause in main_body[:12]:
    print("-" * 100)
    print(f"clause_id: {clause['clause_id']}")
    print(f"section_title: {clause['section_title']}")
    print(f"section: {clause['section']}")
    print(f"title: {clause['title']}")
    print(f"clause_type: {clause['clause_type']}")
    print()

print("=" * 100)
print("【附件分类结果】")
for att in attachments:
    print("-" * 100)
    print(f"attachment_id: {att['attachment_id']}")
    print(f"title: {att['title']}")
    print(f"attachment_type: {att['attachment_type']}")
    print()

with open("data/output/classified_contract.json", "w", encoding="utf-8") as f:
    json.dump(classified_result, f, ensure_ascii=False, indent=2)

print("已保存分类结果到 data/output/classified_contract.json")