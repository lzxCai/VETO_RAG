from app.services.pdf_reader import read_pdf_text, pages_to_text

pdf_path = "data/P020210610345840579453.pdf"

pages = read_pdf_text(pdf_path)

print(f"总页数: {len(pages)}")
print("=" * 100)

# 1：逐页全部打印
for page in pages:
    print(f"\n===== 第 {page['page_no']} 页 =====")
    print(page["text"])

# 2：保存到 txt 文件
full_text = pages_to_text(pages)
with open("data/output/pdf_all_pages_raw.txt", "w", encoding="utf-8") as f:
    f.write(full_text)

print("\n已保存原始全文到 data/output/pdf_all_pages_raw.txt")