import html
import json
import os
import re
import tempfile
import uuid
from datetime import datetime
from functools import partial
from pathlib import Path
from typing import List, Optional

import httpx
import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
from starlette.concurrency import run_in_threadpool

# 导入自定义模块
try:
    from backend.auth import register_user, login_user, get_user, UserCreate, UserLogin
    from backend.auth import send_password_reset as auth_send_reset
    from backend.auth import reset_password as auth_reset_pw
    from backend.contract_pipeline_bridge import run_contract_analysis_sync
    from backend.forum_routes import router as forum_router
    from backend.rag_wrapper import query_rag
    from backend.supabase_client import get_supabase
except ImportError:
    from auth import register_user, login_user, get_user, UserCreate, UserLogin
    from auth import send_password_reset as auth_send_reset
    from auth import reset_password as auth_reset_pw
    from contract_pipeline_bridge import run_contract_analysis_sync
    from forum_routes import router as forum_router
    from rag_wrapper import query_rag
    from supabase_client import get_supabase

# 加载环境变量
load_dotenv()

PROJECT_ROOT = Path(__file__).resolve().parent.parent
VETO_HTML_PATH = PROJECT_ROOT / "VETO web" / "legalhero" / "veto.final(3).html"
NEWS_DIR = PROJECT_ROOT / "法治新闻_markdown"

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

app.include_router(forum_router)


# ========== 请求/响应模型 ==========

class LawyerLocationQuery(BaseModel):
    longitude: float
    latitude: float
    radius: int = 5000
    keyword: str = "律师事务所"


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

def _status_payload() -> dict:
    return {
        "message": "法律助手API运行中",
        "version": "1.1.0",
        "endpoints": [
            "/veto - VETO web 页面",
            "/docs - API文档",
            "/register - 用户注册",
            "/login - 用户登录",
            "/forgot-password - 忘记密码",
            "/reset-password - 重置密码",
            "/chat - 聊天",
            "/history/{user_id} - 聊天历史",
            "/posts/{post_id} - 删除帖子",
            "/comments/{comment_id} - 删除评论",
            "/api/news - 法治资讯",
            "/api/analyze-contract - 合同分析",
            "/api/lawyer/search-by-location - 地图律师检索",
        ],
    }


def _strip_markdown(text: str) -> str:
    cleaned = re.sub(r"```.*?```", "", text, flags=re.S)
    cleaned = re.sub(r"!\[[^\]]*\]\([^)]+\)", "", cleaned)
    cleaned = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", cleaned)
    cleaned = re.sub(r"^\s{0,3}#{1,6}\s*", "", cleaned, flags=re.M)
    cleaned = re.sub(r"^\s*[-*+]\s+", "", cleaned, flags=re.M)
    cleaned = re.sub(r"^\s*\d+\.\s+", "", cleaned, flags=re.M)
    cleaned = re.sub(r"[>*_`#]", "", cleaned)
    cleaned = re.sub(r"\n{2,}", "\n\n", cleaned)
    return cleaned.strip()


def _guess_news_title(path: Path, text: str) -> str:
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        if line.startswith("#"):
            return line.lstrip("#").strip()
    stem = re.sub(r"^\d+[_-]?", "", path.stem)
    return stem.replace("_", " ").strip() or path.name


def _render_news_html(text: str) -> str:
    plain = _strip_markdown(text)
    blocks = [block.strip() for block in re.split(r"\n\s*\n", plain) if block.strip()]
    if not blocks:
        return "<p>暂无内容。</p>"
    rendered = []
    for block in blocks[:8]:
        safe = html.escape(block).replace("\n", "<br>")
        rendered.append(f"<p>{safe}</p>")
    return "".join(rendered)


def _load_news_items(limit: int = 8) -> list[dict]:
    if not NEWS_DIR.exists():
        return [
            {
                "id": "news-fallback-1",
                "title": "法治资讯目录未找到",
                "preview": "当前未发现本地法治资讯 Markdown 目录。",
                "content_html": "<p>当前未发现本地法治资讯目录，请检查“法治新闻_markdown”是否存在。</p>",
                "crawled_at": datetime.now().date().isoformat(),
            }
        ]

    items: list[dict] = []
    candidates = sorted(NEWS_DIR.glob("*.md"), key=lambda p: p.stat().st_mtime, reverse=True)
    for idx, path in enumerate(candidates[: max(limit, 1)]):
        text = path.read_text(encoding="utf-8", errors="ignore")
        title = _guess_news_title(path, text)
        plain = _strip_markdown(text)
        preview = next((line.strip() for line in plain.splitlines() if line.strip()), title)
        items.append(
            {
                "id": f"news-{idx + 1}",
                "title": title,
                "preview": preview[:180],
                "content_html": _render_news_html(text),
                "crawled_at": datetime.fromtimestamp(path.stat().st_mtime).date().isoformat(),
            }
        )
    return items


def _empty_lawyer_result(payload: LawyerLocationQuery, message: str) -> dict:
    return {
        "success": True,
        "query_mode": "location",
        "keyword": payload.keyword,
        "center": {
            "longitude": payload.longitude,
            "latitude": payload.latitude,
        },
        "count": 0,
        "items": [],
        "message": message,
    }


@app.get("/")
async def root():
    return _status_payload()


@app.get("/veto", include_in_schema=False)
async def veto_page():
    if not VETO_HTML_PATH.exists():
        raise HTTPException(status_code=404, detail="未找到 VETO web 页面文件。")
    return FileResponse(VETO_HTML_PATH)


@app.get("/api/news")
async def list_news(limit: int = 8):
    limit = max(1, min(limit, 20))
    return _load_news_items(limit)


@app.post("/api/lawyer/search-by-location")
async def search_lawyers_by_location(payload: LawyerLocationQuery):
    if payload.radius <= 0:
        raise HTTPException(status_code=400, detail="radius 必须为正整数")

    amap_api_key = (os.getenv("AMAP_API_KEY") or "").strip()
    if not amap_api_key:
        return _empty_lawyer_result(payload, "AMAP_API_KEY 未配置，暂未启用附近律师检索。")

    params = {
        "key": amap_api_key,
        "location": f"{payload.longitude},{payload.latitude}",
        "radius": payload.radius,
        "keywords": payload.keyword,
        "offset": 20,
        "page": 1,
    }

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get("https://restapi.amap.com/v3/place/around", params=params)
        resp.raise_for_status()
        data = resp.json()
    except Exception as exc:
        return _empty_lawyer_result(payload, f"律师检索暂时不可用：{exc}")

    if data.get("status") != "1":
        return _empty_lawyer_result(payload, f"高德接口返回异常：{data.get('info', '未知错误')}")

    items = []
    for poi in data.get("pois", []) or []:
        location = poi.get("location") or ""
        if "," not in location:
            continue
        lon_str, lat_str = location.split(",", 1)
        try:
            distance = int(float(poi.get("distance") or "0"))
        except ValueError:
            distance = 0
        items.append(
            {
                "name": poi.get("name", ""),
                "address": poi.get("address", "") or poi.get("adname", "") or "地址未知",
                "longitude": float(lon_str),
                "latitude": float(lat_str),
                "distance": distance,
                "tel": (poi.get("tel") or poi.get("telephone") or "") or None,
            }
        )

    return {
        "success": True,
        "query_mode": "location",
        "keyword": payload.keyword,
        "center": {
            "longitude": payload.longitude,
            "latitude": payload.latitude,
        },
        "count": len(items),
        "items": items,
        "message": None if items else "在指定范围内未找到律师事务所。",
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
    contract_file: UploadFile = File(...),
    parser: str = Query(
        "auto",
        description="解析器：auto | local | bailian | llamaparse；也可用环境变量 CONTRACT_PARSER",
    ),
    user_id: Optional[str] = Form(None),
):
    """
    与前端一致：表单字段名为 contract_file；user_id 可选，有则写入 conversations 供历史卷宗。
    返回 data 为前端解构页结构（overview / clauses / …），由 contract_pipeline_bridge 生成。
    """
    filename = contract_file.filename or "upload"
    ext = os.path.splitext(filename)[1].lower()
    allowed = {".pdf", ".jpg", ".jpeg", ".png", ".webp", ".bmp", ".docx"}
    if ext not in allowed:
        raise HTTPException(
            status_code=415,
            detail=f"暂不支持格式「{ext or '无扩展名'}」，请上传 PDF / 图片 / docx。",
        )
    file_bytes = await contract_file.read()
    if len(file_bytes) > 25 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="文件超过 25MB 上限。")

    parser_eff = (os.getenv("CONTRACT_PARSER") or "").strip() or parser
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
            tmp.write(file_bytes)
            tmp.flush()
            tmp_path = tmp.name

        payload = await run_in_threadpool(
            partial(
                run_contract_analysis_sync,
                tmp_path,
                parser=parser_eff,
                filename=filename,
            )
        )

        uid = (user_id or "").strip()
        if uid:
            try:
                if await get_user(uid):
                    supabase = get_supabase()
                    conv_data = {
                        "user_id": uid,
                        "question": f"卷宗审查：{filename}",
                        "answer": json.dumps(
                            {"veto_kind": "contract_analysis", "data": payload},
                            ensure_ascii=False,
                        ),
                        "mode": "contract",
                        "created_at": datetime.now().isoformat(),
                    }
                    supabase.table("conversations").insert(conv_data).execute()
            except Exception:
                pass

        return {"success": True, "data": payload}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"合同分析失败: {exc}") from exc
    finally:
        if tmp_path and os.path.isfile(tmp_path):
            try:
                os.unlink(tmp_path)
            except OSError:
                pass


# ========== 启动服务 ==========

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=port,
        reload=True
    )
