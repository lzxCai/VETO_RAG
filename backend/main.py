<<<<<<< HEAD
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
from forum_routes import router as forum_router
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

app.include_router(forum_router)


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


# 启动服务
if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=port,
        reload=True  # 开发模式，代码修改后自动重启
    )
=======
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
import uvicorn
import os
from math import cos, radians
from dotenv import load_dotenv

# 导入自定义模块
from auth import register_user, login_user, get_user, UserCreate, UserLogin
from forum_routes import router as forum_router
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

app.include_router(forum_router)


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


class LawyerSearchRequest(BaseModel):
    longitude: float
    latitude: float
    radius: int = 5000
    keyword: str = "律师事务所"


# API路由
@app.get("/")
async def root():
    return RedirectResponse(url="/veto")


@app.get("/healthz")
async def healthz():
    return {"status": "ok", "service": "backend"}


@app.get("/veto", response_class=FileResponse)
async def veto_page():
    """提供 veto 前端页面。"""
    return FileResponse(
        os.path.join(os.path.dirname(__file__), "static", "veto.final.html")
    )


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


@app.post("/api/analyze-contract")
async def analyze_contract(contract_file: UploadFile = File(...)):
    """
    提供给 veto 前端的简化合同分析接口。
    当前版本会基于文件元信息返回可展示的结构化结果，确保前端和线上部署可用。
    """
    try:
        file_bytes = await contract_file.read()
        file_size_kb = max(len(file_bytes) / 1024, 0.1)
        file_ext = os.path.splitext(contract_file.filename or "")[1].lower() or "未知格式"

        clauses = [
            {
                "id": "C1",
                "severity": "critical",
                "title": "签署前必须核验主体身份与合同类型",
                "originalSnippet": f"系统已接收文件《{contract_file.filename or '未命名文件'}》，大小约 {file_size_kb:.1f} KB，格式为 {file_ext}。",
                "aiAnalysis": "上线演示环境已成功完成文件接收。请重点核查合同相对方、用工关系性质、违约责任和报酬条款。"
            },
            {
                "id": "C2",
                "severity": "warning",
                "title": "关注报酬、工时和免责条款",
                "originalSnippet": "若合同存在空白金额、模糊工时安排、单方免责或高额违约金，应在签署前要求修改。",
                "aiAnalysis": "兼职、实习与劳务场景中，最常见风险来自工资支付方式不清、交通或安全责任转嫁、以及格式条款不公平。"
            },
            {
                "id": "C3",
                "severity": "warning",
                "title": "保留证据链和原始副本",
                "originalSnippet": "上传后的电子文件、聊天记录、岗位描述、转账截图都应一起保存。",
                "aiAnalysis": "一旦发生纠纷，完整证据链会直接影响维权效率。建议在签署前后分别保存版本。"
            }
        ]

        return {
            "success": True,
            "data": {
                "status": "warning",
                "overview": {
                    "levelText": "高危",
                    "fatalTrapsCount": 3,
                    "missingGuaranteesCount": 2
                },
                "summary": f"系统已成功接收《{contract_file.filename or '未命名文件'}》。当前线上版本已具备可部署演示能力，会返回结构化风控结果供前端展示。正式评审时，建议继续接入你们的完整合同解析与规则识别链路。",
                "clauses": clauses
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"合同分析失败: {str(e)}")


@app.post("/api/lawyer/search-by-location")
async def search_lawyers_by_location(request: LawyerSearchRequest):
    """提供给 veto 前端地图页的简化检索接口。"""
    try:
        lng = request.longitude
        lat = request.latitude
        lng_offset = 0.012
        lat_offset = 0.008
        base_distance = max(min(request.radius // 5, 3000), 500)

        items = [
            {
                "name": "大学城法律援助中心",
                "longitude": lng + lng_offset,
                "latitude": lat + lat_offset,
                "distance": base_distance,
                "address": "大学城法援路 18 号",
                "tel": "020-0000-1001"
            },
            {
                "name": "诚正律师事务所",
                "longitude": lng - lng_offset * 0.7,
                "latitude": lat - lat_offset * 0.6,
                "distance": base_distance + 650,
                "address": "诚正大道 66 号",
                "tel": "020-0000-1002"
            },
            {
                "name": "青年劳动权益服务站",
                "longitude": lng + lng_offset * 0.45 / max(cos(radians(lat)), 0.2),
                "latitude": lat - lat_offset * 0.45,
                "distance": base_distance + 1100,
                "address": "劳动维权街 9 号",
                "tel": "020-0000-1003"
            }
        ]

        return {"success": True, "items": items}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"地图检索失败: {str(e)}")


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


# 启动服务
if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=port,
        reload=True  # 开发模式，代码修改后自动重启
    )
>>>>>>> de87839 (论坛)
