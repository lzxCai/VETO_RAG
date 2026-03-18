# 2_parse_nodes.py
import os
from llama_index.core import Document
from llama_index.core.node_parser import MarkdownElementNodeParser
from llama_index.core.node_parser import MarkdownNodeParser
from config import MD_PATH, init_models

def get_parsed_nodes():
    # 1. 初始化大模型 (因为 Markdown 解析器内部需要 LLM 来总结表格)
    init_models()
    
    # 2. 读取准备好的 Markdown 文件
    if not os.path.exists(MD_PATH):
        print(f"❌ 找不到 MD 文件: {MD_PATH}，请先运行 1_convert_pdf.py")
        return[]
        
    with open(MD_PATH, "r", encoding="utf-8") as f:
        md_content = f.read()
        
    # 3. 封装为 LlamaIndex 的 Document 对象
    doc = Document(
        text=md_content, 
        metadata={"file_name": "labor_law.pdf", "category": "法律法规"}
    )
    
    # 4. 使用 Markdown 节点解析器
    print("✂️ 正在进行结构化切片 (提取层级和表格)...")
    node_parser = MarkdownNodeParser()
    nodes = node_parser.get_nodes_from_documents([doc])
    
    # 提取节点
    nodes = node_parser.get_nodes_from_documents([doc])
    print(f"✅ 切片完成！共生成了 {len(nodes)} 个结构化节点。")
    
    # 预览前两个节点，检查效果
    for i, node in enumerate(nodes[:10]):
        print(f"\n--- 节点 {i+1} 预览 ---")
        print(node.get_content() + "...")
        print("元数据:", node.metadata)
        
    return nodes

if __name__ == "__main__":
    nodes = get_parsed_nodes()