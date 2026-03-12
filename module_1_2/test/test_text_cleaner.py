from app.services.pdf_reader import read_pdf_text
from app.services.text_cleaner import clean_pages, merge_pages

pdf_path = "data/P020210610345840579453.pdf"

pages = read_pdf_text(pdf_path)
cleaned_pages = clean_pages(pages)
full_text = merge_pages(cleaned_pages)

print(f"总页数: {len(cleaned_pages)}")
print("=" * 100)

# 打印全部清洗后的页内容
for page in cleaned_pages:
    print(f"\n===== 清洗后第 {page['page_no']} 页 =====")
    print(page["text"])

print("\n" + "=" * 100)
print("===== 合并后全文 =====")
print(full_text)

# 保存结果
with open("data/output/pdf_cleaned_pages.txt", "w", encoding="utf-8") as f:
    for page in cleaned_pages:
        f.write(f"\n===== 清洗后第 {page['page_no']} 页 =====\n")
        f.write(page["text"])
        f.write("\n")

with open("data/output/pdf_cleaned_full_text.txt", "w", encoding="utf-8") as f:
    f.write(full_text)

print("\n已保存:")
print("1. data/output/pdf_cleaned_pages.txt")
print("2. data/output/pdf_cleaned_full_text.txt")