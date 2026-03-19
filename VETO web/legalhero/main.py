from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import lawyer_search


def create_app() -> FastAPI:
    app = FastAPI(title="VETO Backend", version="0.1.0")

    # 允许本机与局域网页面调用后端接口（开发环境）
    app.add_middleware(
        CORSMiddleware,
        allow_origin_regex=r"^https?://([a-zA-Z0-9\.-]+)(:\d+)?$",
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # 挂载律师检索路由
    app.include_router(lawyer_search.router)

    return app


app = create_app()

