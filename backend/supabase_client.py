import os

from dotenv import load_dotenv
from supabase import Client, create_client

load_dotenv()

_supabase: Client | None = None


def get_supabase() -> Client:
    """延迟初始化 Supabase，避免应用启动时因缺少环境变量直接崩溃。"""
    global _supabase

    if _supabase is not None:
        return _supabase

    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_KEY")
    if not url or not key:
        raise ValueError("请设置 SUPABASE_URL 和 SUPABASE_KEY 环境变量")

    _supabase = create_client(url, key)
    return _supabase
