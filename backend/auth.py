from pydantic import BaseModel

try:
    from backend.supabase_client import get_supabase
except ImportError:
    from supabase_client import get_supabase

# 数据模型
class UserCreate(BaseModel):
    username: str
    password: str
    email: str = ""

class UserLogin(BaseModel):
    username: str
    password: str

class UserResponse(BaseModel):
    id: str
    username: str
    email: str
    created_at: str

# 临时简化版密码处理（不加密）
def hash_password(password: str) -> str:
    """临时：直接返回密码（仅用于测试）"""
    return password

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """临时：直接比较密码"""
    return plain_password == hashed_password

async def register_user(user_data: UserCreate):
    """用户注册"""
    supabase = get_supabase()
    
    # 检查用户名是否已存在
    existing = supabase.table("users").select("*").eq("username", user_data.username).execute()
    if existing.data:
        return None, "用户名已存在"
    
    # 创建新用户
    new_user = {
        "username": user_data.username,
        "email": user_data.email,
        "password_hash": hash_password(user_data.password)  # 现在直接存明文
    }
    
    result = supabase.table("users").insert(new_user).execute()
    
    if result.data:
        user = result.data[0]
        user.pop("password_hash", None)
        return user, None
    return None, "注册失败"

async def login_user(login_data: UserLogin):
    """用户登录"""
    supabase = get_supabase()
    
    # 查找用户
    result = supabase.table("users").select("*").eq("username", login_data.username).execute()
    
    if not result.data:
        return None, "用户名或密码错误"
    
    user = result.data[0]
    
    # 验证密码（直接比较）
    if not verify_password(login_data.password, user["password_hash"]):
        return None, "用户名或密码错误"
    
    # 更新最后登录时间
    supabase.table("users").update({"last_login": "now()"}).eq("id", user["id"]).execute()
    
    # 不返回密码哈希
    user.pop("password_hash", None)
    return user, None

async def get_user(user_id: str):
    """获取用户信息"""
    supabase = get_supabase()
    result = supabase.table("users").select("*").eq("id", user_id).execute()
    
    if result.data:
        user = result.data[0]
        user.pop("password_hash", None)
        return user
    return None
