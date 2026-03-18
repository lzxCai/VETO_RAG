import os
import pathlib
from dotenv import load_dotenv
from llama_parse import LlamaParse
from config import PDF_PATH, MD_PATH

# 加载环境变量
load_dotenv()

def convert_pdf_to_md():
    if not os.path.exists(PDF_PATH):
        print(f"❌ 找不到文件: {PDF_PATH}")
        return

    print("☁️ 正在调用 LlamaParse 云端引擎解析 PDF，请稍候...")
    
    # 1. 初始化 LlamaParse
    parser = LlamaParse(
        result_type="markdown",  # 关键：要求输出 Markdown 格式
        language="ch_sim",       # 优化简体中文识别
        verbose=True
    )
    
    # 2. 上传并解析文档
    # LlamaParse 会返回一个 LlamaIndex Document 对象的列表（每一页是一个 Document）
    documents = parser.load_data(PDF_PATH)
    
    # 3. 将所有页面的 Markdown 文本合并
    md_text = "\n\n".join([doc.text for doc in documents])
    
    # 4. 写入本地缓存文件
    # 为什么要保存下来？为了省 API 额度和节省每次调试的时间！
    pathlib.Path(MD_PATH).write_bytes(md_text.encode("utf-8"))
    print(f"✅ LlamaParse 解析成功！Markdown 文件已保存至: {MD_PATH}")

if __name__ == "__main__":
    convert_pdf_to_md()