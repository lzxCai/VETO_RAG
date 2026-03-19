from fastapi import FastAPI, HTTPException, File, UploadFile, Form
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
import uvicorn
import os
import uuid
from dotenv import load_dotenv

# 导入自定义模块
from auth import register_user, login_user, get_user, UserCreate, UserLogin
from auth import send_password_reset as auth_send_reset
from auth import reset_password as auth_reset_pw
from supabase_client import get_supabase
from rag_wrapper import query_rag

# 导入合同分析模块（你们团队已经写好的）
from app.services.contract_pipeline import run_contract_parsing_pipeline
from app.services.risk_identifier import identify_contract_risks

# 加载环境变量
load_dotenv()

# 创建FastAPI应用
app = FastAPI(
    title="法律助手后端API",
    description="提供用户认证、聊天历史、RAG调用、论坛、合同分析等功能",
    version="1.1.0"
)

# 配置CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ========== 请求/响应模型 ==========

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


# ========== 基础路由 ==========

@app.get("/")
async def root():
    return {
        "message": "法律助手API运行中",
        "version": "1.1.0",
        "endpoints": [
            "/docs - API文档",
            "/register - 用户注册",
            "/login - 用户登录",
            "/forgot-password - 忘记密码",
            "/reset-password - 重置密码",
            "/chat - 聊天",
            "/history/{user_id} - 聊天历史",
            "/posts/{post_id} - 删除帖子",
            "/comments/{comment_id} - 删除评论",
            "/api/analyze-contract - 合同分析"
        ]
    }


# ========== 用户认证 ==========

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


# ========== 找回密码 ==========

@app.post("/forgot-password")
async def forgot_password(email: str):
    """忘记密码 - 发送重置邮件"""
    error = await auth_send_reset(email)
    if error:
        raise HTTPException(status_code=400, detail=error)
    return {"message": "重置密码邮件已发送，请查收"}


@app.post("/reset-password")
async def reset_password(token: str, new_password: str):
    """重置密码 - 用户点击邮件链接后调用"""
    user, error = await auth_reset_pw(token, new_password)
    if error:
        raise HTTPException(status_code=400, detail=error)
    return {"message": "密码重置成功", "user": user}


@app.get("/verify-reset-token/{token}")
async def verify_reset_token(token: str):
    """验证重置密码的token是否有效"""
    supabase = get_supabase()
    try:
        user = supabase.auth.api.get_user(token)
        return {"valid": True, "user": user}
    except:
        return {"valid": False}


# ========== 聊天相关 ==========

@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest, user_id: Optional[str] = None):
    """聊天接口（自动保存历史）"""
    try:
        answer = await query_rag(request.question)
        conversation_id = None

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

        return ChatResponse(answer=answer, conversation_id=conversation_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/history/{user_id}", response_model=HistoryResponse)
async def get_history(user_id: str, limit: int = 50):
    """获取用户的聊天历史"""
    supabase = get_supabase()
    user = await get_user(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")

    result = supabase.table("conversations") \
        .select("*") \
        .eq("user_id", user_id) \
        .order("created_at", desc=True) \
        .limit(limit) \
        .execute()

    return HistoryResponse(history=result.data or [])


@app.delete("/history/{conversation_id}")
async def delete_history(conversation_id: str, user_id: str):
    """删除单条聊天历史"""
    supabase = get_supabase()
    result = supabase.table("conversations") \
        .select("*") \
        .eq("id", conversation_id) \
        .eq("user_id", user_id) \
        .execute()

    if not result.data:
        raise HTTPException(status_code=404, detail="记录不存在或无权限")

    supabase.table("conversations").delete().eq("id", conversation_id).execute()
    return {"message": "删除成功"}


# ========== 论坛相关 ==========

@app.delete("/posts/{post_id}")
async def delete_post(post_id: str, user_id: str):
    """删除帖子（只能删自己的）"""
    supabase = get_supabase()
    result = supabase.table("forum_posts") \
        .select("*") \
        .eq("id", post_id) \
        .eq("user_id", user_id) \
        .execute()

    if not result.data:
        raise HTTPException(status_code=404, detail="帖子不存在或无权限")

    supabase.table("forum_posts").delete().eq("id", post_id).execute()
    return {"message": "帖子删除成功"}


@app.delete("/comments/{comment_id}")
async def delete_comment(comment_id: str, user_id: str):
    """删除评论（只能删自己的）"""
    supabase = get_supabase()
    result = supabase.table("forum_comments") \
        .select("*") \
        .eq("id", comment_id) \
        .eq("user_id", user_id) \
        .execute()

    if not result.data:
        raise HTTPException(status_code=404, detail="评论不存在或无权限")

    supabase.table("forum_comments").delete().eq("id", comment_id).execute()
    return {"message": "评论删除成功"}


# ========== 合同分析 ==========

@app.post("/api/analyze-contract")
async def analyze_contract(
        file: UploadFile = File(...),
        user_id: str = Form(...)
):
    """
    合同分析接口
    - 上传PDF合同
    - 调用合同解析和风险识别
    - 存入数据库
    - 返回分析结果和记录ID
    """
    temp_file = None
    try:
        # 1. 保存临时文件
        temp_file = f"temp_{uuid.uuid4()}.pdf"
        with open(temp_file, "wb") as f:
            content = await file.read()
            f.write(content)

        # 2. 调用合同解析
        parsed_result = run_contract_parsing_pipeline(
            input_source=temp_file,
            parser="auto",
            fallback_to_legacy=True,
            return_parse_meta=True
        )

        classified_contract = parsed_result["classified_contract"]

        # 3. 调用风险识别
        risk_result = identify_contract_risks(classified_contract)

        # 4. 存入 Supabase
        supabase = get_supabase()

        # 简单判断风险等级（可以根据实际需求调整）
        high_risk_count = risk_result["summary"].get("high_risk_records", 0)
        if high_risk_count > 0:
            risk_level = "高风险"
        elif risk_result["summary"].get("attention_records", 0) > 0:
            risk_level = "中风险"
        else:
            risk_level = "低风险"

        analysis_data = {
            "user_id": user_id,
            "file_name": file.filename,
            "analysis_result": risk_result,
            "risk_level": risk_level,
            "created_at": datetime.now().isoformat()
        }

        db_result = supabase.table("contract_analyses").insert(analysis_data).execute()

        # 5. 返回结果
        return {
            "success": True,
            "data": risk_result,
            "record_id": db_result.data[0]["id"] if db_result.data else None
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"分析失败: {str(e)}")
    finally:
        # 6. 清理临时文件
        if temp_file and os.path.exists(temp_file):
            os.remove(temp_file)


# ========== 启动服务 ==========

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=port,
        reload=True
    )