from app.services.pdf_reader import read_pdf_text
from app.services.text_cleaner import clean_pages, merge_pages
from app.services.clause_splitter import split_contract

pdf_path = "data/P020210610345840579453.pdf"

pages = read_pdf_text(pdf_path)
cleaned_pages = clean_pages(pages)
full_text = merge_pages(cleaned_pages)

result = split_contract(full_text)

main_body = result["main_body"]
attachments = result["attachments"]

print(f"正文共切分出 {len(main_body)} 个条款")
print(f"附件共识别出 {len(attachments)} 个\n")

print("=" * 100)
print("【正文前 8 条预览】")
for clause in main_body[:8]:
    print("-" * 100)
    print(f"clause_id: {clause['clause_id']}")
    print(f"section_title: {clause['section_title']}")
    print(f"section: {clause['section']}")
    print(f"title: {clause['title']}")
    print("text预览:")
    print(clause["text"][:250])
    print()

print("=" * 100)
print("【附件预览】")
for att in attachments:
    print("-" * 100)
    print(f"attachment_id: {att['attachment_id']}")
    print(f"title: {att['title']}")
    print("text预览:")
    print(att["text"][:250])
    print()