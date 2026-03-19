from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
import uvicorn
import os
from dotenv import load_dotenv

# 导入自定义模块
from auth import register_user, login_user, get_user, UserCreate, UserLogin
from supabase_client import get_supabase
from rag_wrapper import query_rag

# 加载环境变量
load_dotenv()

# 创建FastAPI应用
app = FastAPI(
    title="法律助手后端API",
    description="提供用户认证、聊天历史和RAG调用功能",
    version="1.0.0"
)

# 配置CORS（允许前端调用）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 生产环境需要限制
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# 请求/响应模型
class ChatRequest(BaseModel):
    question: str
    mode: str = "hybrid"
    use_rerank: bool = False


class ChatResponse(BaseModel):
    answer: str
    conversation_id: Optional[str] = None


class HistoryItem(BaseModel):
    id: str
    question: str
    answer: str
    created_at: str
    mode: str = "hybrid"


class HistoryResponse(BaseModel):
    history: List[HistoryItem]


# API路由
@app.get("/")
async def root():
    return {
        "message": "法律助手API运行中",
        "version": "1.0.0",
        "endpoints": [
            "/docs - API文档",
            "/register - 用户注册",
            "/login - 用户登录",
            "/chat - 聊天",
            "/history/{user_id} - 聊天历史"
        ]
    }


@app.post("/register")
async def register(user: UserCreate):
    """用户注册"""
    new_user, error = await register_user(user)
    if error:
        raise HTTPException(status_code=400, detail=error)
    return {"message": "注册成功", "user": new_user}


@app.post("/login")
async def login(user: UserLogin):
    """用户登录"""
    user_data, error = await login_user(user)
    if error:
        raise HTTPException(status_code=401, detail=error)
    return {"message": "登录成功", "user": user_data}


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest, user_id: Optional[str] = None):
    """
    聊天接口
    - 如果提供user_id，会保存聊天历史
    - 如果不提供user_id，只返回回答不保存
    """
    try:
        # 1. 调用RAG
        answer = await query_rag(request.question)

        conversation_id = None

        # 2. 如果提供了user_id，保存到数据库
        if user_id:
            supabase = get_supabase()
            conv_data = {
                "user_id": user_id,
                "question": request.question,
                "answer": answer,
                "mode": request.mode,
                "created_at": datetime.now().isoformat()
            }
            result = supabase.table("conversations").insert(conv_data).execute()
            if result.data:
                conversation_id = result.data[0]["id"]

        return ChatResponse(
            answer=answer,
            conversation_id=conversation_id
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/history/{user_id}", response_model=HistoryResponse)
async def get_history(user_id: str, limit: int = 50):
    """获取用户的聊天历史"""
    supabase = get_supabase()

    # 验证用户存在
    user = await get_user(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")

    # 查询历史
    result = supabase.table("conversations") \
        .select("*") \
        .eq("user_id", user_id) \
        .order("created_at", desc=True) \
        .limit(limit) \
        .execute()

    return HistoryResponse(history=result.data or [])


@app.delete("/history/{conversation_id}")
async def delete_history(conversation_id: str, user_id: str):
    """删除单条历史记录（需要验证用户）"""
    supabase = get_supabase()

    # 验证这条记录属于该用户
    result = supabase.table("conversations") \
        .select("*") \
        .eq("id", conversation_id) \
        .eq("user_id", user_id) \
        .execute()

    if not result.data:
        raise HTTPException(status_code=404, detail="记录不存在或无权限")

    # 删除
    supabase.table("conversations").delete().eq("id", conversation_id).execute()

    return {"message": "删除成功"}

@app.delete("/posts/{post_id}")
async def delete_post(post_id: str, user_id: str):
    """删除帖子（只能删自己的）"""
    supabase = get_supabase()

    # 验证帖子存在且属于该用户
    result = supabase.table("forum_posts") \
        .select("*") \
        .eq("id", post_id) \
        .eq("user_id", user_id) \
        .execute()

    if not result.data:
        raise HTTPException(status_code=404, detail="帖子不存在或无权限")

    # 删除帖子（关联的评论会自动删，因为有 ON DELETE CASCADE）
    supabase.table("forum_posts").delete().eq("id", post_id).execute()

    return {"message": "帖子删除成功"}


@app.delete("/comments/{comment_id}")
async def delete_comment(comment_id: str, user_id: str):
    """删除评论（只能删自己的）"""
    supabase = get_supabase()

    # 验证评论存在且属于该用户
    result = supabase.table("forum_comments") \
        .select("*") \
        .eq("id", comment_id) \
        .eq("user_id", user_id) \
        .execute()

    if not result.data:
        raise HTTPException(status_code=404, detail="评论不存在或无权限")

    supabase.table("forum_comments").delete().eq("id", comment_id).execute()

    return {"message": "评论删除成功"}


# 启动服务
if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=port,
        reload=True  # 开发模式，代码修改后自动重启
    )