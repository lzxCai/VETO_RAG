# config.py
import os
from dotenv import load_dotenv
from llama_index.core import Settings
from llama_index.llms.openai_like import OpenAILike
from llama_index.core import Settings
from llama_index.embeddings.dashscope import DashScopeEmbedding

# 加载 .env 文件中的环境变量
load_dotenv()

# 全局变量定义
DATA_DIR = "dataset"
PDF_PATH = os.path.join(DATA_DIR, "labor_law.pdf")
MD_PATH = os.path.join(DATA_DIR, "labor_law.md")

# 初始化模型的函数
def init_models():
    """初始化全局 LLM 和 Embedding 模型"""
    
    # 1. 配置 DeepSeek (用于提取知识图谱关系)
    Settings.llm = OpenAILike(
        model="qwen-plus",
        api_base="https://dashscope.aliyuncs.com/compatible-mode/v1",
        api_key=os.getenv("DASHSCOPE_API_KEY"),
        is_chat_model=True
    )
    
    # 2. 配置 Qwen Embedding (用于向量检索)
    Settings.embed_model = DashScopeEmbedding(
        model_name="text-embedding-v3"
    )
    
    # 3. 设置切片基础参数
    Settings.chunk_size = 512
    Settings.chunk_overlap = 100
    
    print("✅ 模型初始化完成！")