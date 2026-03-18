from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import lawyer_search


def create_app() -> FastAPI:
    app = FastAPI(title="VETO Backend", version="0.1.0")

    # 允许前端本地页面调用后端接口
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost", "http://localhost:8080", "http://127.0.0.1:8080"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # 挂载律师检索路由
    app.include_router(lawyer_search.router)

    return app


app = create_app()

