from pydantic import BaseModel

try:
    from backend.supabase_client import get_supabase
except ImportError:
    from supabase_client import get_supabase


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


def hash_password(password: str) -> str:
    return password


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return plain_password == hashed_password


async def register_user(user_data: UserCreate):
    supabase = get_supabase()
    existing = supabase.table("users").select("*").eq("username", user_data.username).execute()
    if existing.data:
        return None, "用户名已存在"

    new_user = {
        "username": user_data.username,
        "email": user_data.email,
        "password_hash": hash_password(user_data.password),
    }

    result = supabase.table("users").insert(new_user).execute()
    if result.data:
        user = result.data[0]
        user.pop("password_hash", None)
        return user, None
    return None, "注册失败"


async def login_user(login_data: UserLogin):
    supabase = get_supabase()
    result = supabase.table("users").select("*").eq("username", login_data.username).execute()

    if not result.data:
        return None, "用户名或密码错误"

    user = result.data[0]
    if not verify_password(login_data.password, user["password_hash"]):
        return None, "用户名或密码错误"

    supabase.table("users").update({"last_login": "now()"}).eq("id", user["id"]).execute()
    user.pop("password_hash", None)
    return user, None


async def get_user(user_id: str):
    supabase = get_supabase()
    result = supabase.table("users").select("*").eq("id", user_id).execute()

    if result.data:
        user = result.data[0]
        user.pop("password_hash", None)
        return user
    return None
