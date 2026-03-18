import subprocess
import sys
from pathlib import Path
import os
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# 获取项目根目录（backend的上一级）
ROOT_DIR = Path(__file__).parent.parent


async def query_rag(question: str) -> str:
    """
    调用队长的main.py查询RAG

    Args:
        question: 用户问题

    Returns:
        RAG回答内容
    """
    try:
        # 确保工作目录是项目根目录
        result = subprocess.run(
            [sys.executable, str(ROOT_DIR / "main.py"), question],
            cwd=ROOT_DIR,
            capture_output=True,
            text=True,
            timeout=60,  # 60秒超时
            env=os.environ.copy()  # 传递环境变量
        )

        if result.returncode != 0:
            error_msg = result.stderr.strip()
            return f"RAG调用失败: {error_msg}"

        # 清理输出
        output = result.stdout.strip()
        return output if output else "RAG返回空结果"

    except subprocess.TimeoutExpired:
        return "RAG查询超时，请稍后重试"
    except Exception as e:
        return f"发生错误: {str(e)}"


# 测试函数
if __name__ == "__main__":
    import asyncio


    async def test():
        answer = await query_rag("劳动法规定的工作时间是多少？")
        print("回答:", answer)


    asyncio.run(test())