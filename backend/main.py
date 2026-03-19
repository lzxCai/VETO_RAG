<<<<<<< HEAD
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
=======
import os
import tempfile
from datetime import datetime
from math import cos, radians
from typing import List, Optional

from dotenv import load_dotenv
from functools import partial

from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, RedirectResponse
from pydantic import BaseModel
from pathlib import Path
import re
import httpx
from starlette.concurrency import run_in_threadpool

try:
    from backend.auth import UserCreate, UserLogin, get_user, login_user, register_user
    from backend.contract_pipeline_bridge import run_contract_analysis_sync
    from backend.forum_routes import router as forum_router
    from backend.rag_wrapper import query_rag
    from backend.supabase_client import get_supabase
except ImportError:
    from auth import UserCreate, UserLogin, get_user, login_user, register_user
    from contract_pipeline_bridge import run_contract_analysis_sync
    from forum_routes import router as forum_router
    from rag_wrapper import query_rag
    from supabase_client import get_supabase


load_dotenv()

app = FastAPI(
    title="法律助手后端API",
    description="提供用户认证、聊天历史和 RAG 调用功能",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(forum_router)


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


class LawyerSearchRequest(BaseModel):
    longitude: float
    latitude: float
    radius: int = 5000
    keyword: str = "律师事务所"

class NewsItem(BaseModel):
    id: str
    title: str
    crawled_at: str = ""
    image_url: str = ""
    preview: str = ""
    content_html: str = ""

def _parse_front_matter(md_text: str) -> tuple[dict, str]:
    text = md_text.lstrip("\ufeff")
    if not text.startswith("---"):
        return {}, md_text
    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}, md_text
    _, raw_meta, rest = parts[0], parts[1], parts[2]
    meta: dict = {}
    for line in raw_meta.strip().splitlines():
        if ":" not in line:
            continue
        key, val = line.split(":", 1)
        meta[key.strip()] = val.strip()
    return meta, rest.lstrip()

def _markdown_to_html(md: str) -> str:
    lines = md.splitlines()
    out: list[str] = []
    for line in lines:
        if line.strip() == "---":
            out.append("<hr/>")
            continue
        m = re.match(r"^\!\[[^\]]*\]\(([^)]+)\)", line.strip())
        if m:
            url = m.group(1)
            out.append(f"<img src=\"{url}\" style=\"max-width:100%;border:1px solid #eee;\"/>")
            continue
        if line.startswith("# "):
            out.append(f"<h2>{line[2:].strip()}</h2>")
            continue
        if line.startswith("## "):
            out.append(f"<h3>{line[3:].strip()}</h3>")
            continue
        if not line.strip():
            out.append("")
            continue
        out.append(f"<p>{line}</p>")
    html = "\n".join(out)
    html = re.sub(r"\n{3,}", "\n\n", html)
    return html

def _build_news_item(md_path: Path) -> NewsItem:
    text = md_path.read_text(encoding="utf-8", errors="ignore")
    meta, body = _parse_front_matter(text)
    title = meta.get("title") or md_path.stem
    crawled_at = meta.get("crawled_at", "")
    image_url = meta.get("image_url", "")
    # preview：取正文里前 120 字的纯文本（粗略）
    preview_src = re.sub(r"!\[[^\]]*\]\([^)]+\)", "", body)
    preview_src = re.sub(r"^#+\s+", "", preview_src, flags=re.M)
    preview_src = re.sub(r"\s+", " ", preview_src).strip()
    preview = preview_src[:120]
    return NewsItem(
        id=str(meta.get("page_id") or md_path.stem.split("_", 1)[0] or md_path.stem),
        title=title,
        crawled_at=crawled_at,
        image_url=image_url,
        preview=preview,
        content_html=_markdown_to_html(body),
    )


@app.get("/")
async def root():
    return RedirectResponse(url="/veto")


@app.get("/healthz")
async def healthz():
    return {"status": "ok", "service": "backend"}


@app.get("/veto", response_class=FileResponse)
async def veto_page():
    # 优先使用更新版前端（同源直连后端接口）
    project_root = os.path.dirname(os.path.dirname(__file__))
    candidate = os.path.join(project_root, "VETO web", "legalhero", "veto.final(3).html")
    fallback = os.path.join(os.path.dirname(__file__), "static", "veto.final.html")
    return FileResponse(candidate if os.path.exists(candidate) else fallback)

@app.get("/api/news", response_model=list[NewsItem])
async def get_news(limit: int = 50):
    project_root = Path(__file__).resolve().parent.parent
    news_dir = project_root / "法治新闻_markdown"
    if not news_dir.exists():
        return []
    md_files = sorted(
        [p for p in news_dir.glob("*.md") if p.name not in {"README.md", "SUMMARY.md"}],
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    items: list[NewsItem] = []
    for p in md_files[: max(1, min(limit, 200))]:
        try:
            items.append(_build_news_item(p))
        except Exception:
            continue
    return items


@app.post("/register")
async def register(user: UserCreate):
    new_user, error = await register_user(user)
    if error:
        raise HTTPException(status_code=400, detail=error)
    return {"message": "注册成功", "user": new_user}


@app.post("/login")
async def login(user: UserLogin):
    user_data, error = await login_user(user)
    if error:
        raise HTTPException(status_code=401, detail=error)
    return {"message": "登录成功", "user": user_data}


@app.post("/api/analyze-contract")
async def analyze_contract(
    contract_file: UploadFile = File(...),
    parser: str = Query(
        "auto",
        description="合同解析器：auto | local | bailian | llamaparse（也可用环境变量 CONTRACT_PARSER 默认）",
    ),
):
    """
    调用项目内 `generate_report_context_for_contract` 全链路（解析→风险→法律依据检索），
    返回前端卷宗解构页所需结构；非演示数据。
    """
    filename = contract_file.filename or "upload"
    ext = os.path.splitext(filename)[1].lower()
    allowed = {".pdf", ".jpg", ".jpeg", ".png", ".webp", ".bmp"}
    if ext not in allowed:
        raise HTTPException(
            status_code=415,
            detail=f"暂不支持格式「{ext or '无扩展名'}」，请上传 PDF 或图片（jpg/png/webp/bmp）。",
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


@app.post("/api/lawyer/search-by-location")
async def search_lawyers_by_location(request: LawyerSearchRequest):
    """
    实时调用高德 Web 服务 POI 周边检索，返回地图上更准确的律所/法院/法援等点位。
    需要配置环境变量：AMAP_API_KEY（高德 Web 服务 Key）
    """
    amap_key = os.getenv("AMAP_API_KEY") or os.getenv("AMAP_WEB_KEY")
    if not amap_key:
        # 无 key 时降级为演示数据，避免前端完全不可用
        lng = request.longitude
        lat = request.latitude
        return {
            "success": True,
            "items": [
                {
                    "name": "（演示）未配置 AMAP_API_KEY",
                    "longitude": lng,
                    "latitude": lat,
                    "distance": 0,
                    "address": "请在环境变量中设置 AMAP_API_KEY（高德 Web 服务 Key）",
                    "tel": "",
                }
            ],
            "message": "未配置 AMAP_API_KEY，已降级为演示点位。",
        }

    keyword = (request.keyword or "").strip() or "律师事务所"
    radius = int(request.radius or 5000)
    radius = max(100, min(radius, 50000))

    # 高德周边搜索
    url = "https://restapi.amap.com/v3/place/around"
    params = {
        "key": amap_key,
        "location": f"{request.longitude},{request.latitude}",
        "radius": str(radius),
        "keywords": keyword,
        "sortrule": "distance",
        "extensions": "base",
        "offset": "25",
        "page": "1",
    }

    def _fallback_items(msg: str):
        lng = request.longitude
        lat = request.latitude
        return {
            "success": True,
            "items": [
                {
                    "name": "（降级）地图服务暂不可用",
                    "longitude": lng,
                    "latitude": lat,
                    "distance": 0,
                    "address": msg,
                    "tel": "",
                }
            ],
            "message": msg,
            "keyword": keyword,
            "radius": radius,
        }

    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            resp = await client.get(url, params=params)
        if resp.status_code != 200:
            return _fallback_items(f"高德接口请求失败: HTTP {resp.status_code}")
        data = resp.json()
        if data.get("status") != "1":
            return _fallback_items(f"高德接口返回错误: {data.get('info', '未知错误')}")

        pois = data.get("pois", []) or []
        items: list[dict] = []
        for poi in pois:
            loc = poi.get("location") or ""
            if "," not in loc:
                continue
            lon_str, lat_str = loc.split(",", 1)
            try:
                lon = float(lon_str)
                lat = float(lat_str)
            except ValueError:
                continue

            distance_raw = poi.get("distance") or "0"
            try:
                distance = int(float(distance_raw))
            except ValueError:
                distance = 0

            tel = poi.get("tel") or poi.get("telephone") or ""
            address = poi.get("address") or poi.get("adname") or ""

            items.append(
                {
                    "name": poi.get("name", ""),
                    "longitude": lon,
                    "latitude": lat,
                    "distance": distance,
                    "address": address,
                    "tel": tel,
                    # 额外字段（前端暂不强依赖）
                    "poi_id": poi.get("id") or "",
                    "type": poi.get("type") or "",
                    "typecode": poi.get("typecode") or "",
                }
            )

        return {"success": True, "items": items, "keyword": keyword, "radius": radius}
    except HTTPException as exc:
        return _fallback_items(f"地图检索异常: {exc.detail}")
    except Exception as exc:
        return _fallback_items(f"地图检索失败: {exc}")


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest, user_id: Optional[str] = Query(default=None)):
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
                "created_at": datetime.now().isoformat(),
            }
            result = supabase.table("conversations").insert(conv_data).execute()
            if result.data:
                conversation_id = result.data[0]["id"]

        return ChatResponse(answer=answer, conversation_id=conversation_id)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/history/{user_id}", response_model=HistoryResponse)
async def get_history(user_id: str, limit: int = 50):
    supabase = get_supabase()
    user = await get_user(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")

    result = (
        supabase.table("conversations")
        .select("*")
        .eq("user_id", user_id)
        .order("created_at", desc=True)
        .limit(limit)
        .execute()
    )
    return HistoryResponse(history=result.data or [])


@app.delete("/history/{conversation_id}")
async def delete_history(conversation_id: str, user_id: str):
    supabase = get_supabase()
    result = (
        supabase.table("conversations")
        .select("*")
        .eq("id", conversation_id)
        .eq("user_id", user_id)
        .execute()
    )

    if not result.data:
        raise HTTPException(status_code=404, detail="记录不存在或无权限")

    supabase.table("conversations").delete().eq("id", conversation_id).execute()
    return {"message": "删除成功"}


if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("PORT", 8000))
    uvicorn.run("backend.main:app", host="0.0.0.0", port=port, reload=True)
>>>>>>> 1bc2734 (chore: sync local changes from Cursor)
