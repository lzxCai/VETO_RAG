# lightrag_main.py
import asyncio
import re
from lightrag import LightRAG, QueryParam
from config import WORKING_DIR, MD_PATH, llm_model_func, embedding_func

# 自定义切片函数：按 Markdown 的二级标题 (##) 切分法条
def split_markdown_by_articles(file_path):
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()
    
    # 法律 MD 通常结构是：# 第一章 / ## 第一条
    # 我们按照 "## " 进行切分，因为 "##" 通常对应的是具体的法条
    # 如果你的 MD 是用 "###" 表示法条，请修改下方的正则
    articles = re.split(r'\n(?=# )', content)
    
    # 过滤掉空字符串，并去除多余的首尾空格
    articles = [a.strip() for a in articles if a.strip()]
    
    print(f"检测到 {len(articles)} 个法条节点。")
    return articles

async def build_and_query():
    # 1. 初始化 LightRAG
    rag = LightRAG(
        working_dir=WORKING_DIR,
        llm_model_func=llm_model_func,
        embedding_func=embedding_func,
        # 即使我们手动切了，也可以把内部参数调小，防止它在极个别超长法条里再次切分
        chunk_token_size=1500 
    )

    # 2. 获取按标题切分后的法条列表
    # 这里的 articles 是一个 List[str]
    articles_list = split_markdown_by_articles(MD_PATH)

    # 3. 插入列表（关键：传列表则 LightRAG 会尊重你的切分）
    print("🚀 正在构建 LightRAG 知识图谱（按法条级索引）...")
    # 注意：LightRAG 的 insert 接收列表
    await rag.ainsert(articles_list)

    # 4. 执行查询
    print("\n🔍 正在查询...")
    query_text = "兼职不签合同有哪些风险？请结合劳动法给出条文依据。"
    response = await rag.aquery(
        query_text,
        param=QueryParam(mode="hybrid") 
    )
    print(f"\n✨ AI 回答：\n{response}")

if __name__ == "__main__":
    asyncio.run(build_and_query())