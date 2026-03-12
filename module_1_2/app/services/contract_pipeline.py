#第一模块合同解析流程，第二模块可直接使用这个个函数，输入PDF路径，输出分类结果用于后续处理。

from app.services.pdf_reader import read_pdf_text
from app.services.text_cleaner import clean_pages, merge_pages
from app.services.clause_splitter import split_contract
from app.services.clause_classifier import classify_contract_parts


def run_contract_parsing_pipeline(pdf_path: str):
    pages = read_pdf_text(pdf_path)
    cleaned_pages = clean_pages(pages)
    full_text = merge_pages(cleaned_pages)
    split_result = split_contract(full_text)
    classified_result = classify_contract_parts(split_result)
    return classified_result