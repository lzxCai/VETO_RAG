import os
from dotenv import load_dotenv
from supabase import create_client, Client

# 加载环境变量
load_dotenv()

# Supabase配置
url = os.getenv("SUPABASE_URL")
key = os.getenv("SUPABASE_KEY")

if not url or not key:
    raise ValueError("请设置 SUPABASE_URL 和 SUPABASE_KEY 环境变量")

# 创建Supabase客户端
supabase: Client = create_client(url, key)

def get_supabase() -> Client:
    """获取Supabase客户端实例"""
    return supabase