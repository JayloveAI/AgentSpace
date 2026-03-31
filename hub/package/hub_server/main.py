"""
Agent Universal Hub - FastAPI 主入口
=====================================
撮合中枢服务器，提供 REST API 供 Agent 注册和匹配
"""
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from .config import (
    DEBUG, CORS_ORIGINS, API_V1_PREFIX,
    DATABASE_URL, OPENAI_API_KEY
)
from .api.routes import router as api_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 启动时
    print("[START] Agent Universal Hub is starting...")
    print(f"   API URL: http://localhost:8000")
    print(f"   API Docs: http://localhost:8000/docs")

    if not OPENAI_API_KEY:
        print("[WARNING] OPENAI_API_KEY not configured, vector search unavailable")

    # TODO: 初始化数据库连接池
    # await init_database()

    yield

    # 关闭时
    print("[STOP] Agent Universal Hub is shutting down...")


# 创建 FastAPI 应用
app = FastAPI(
    title="Agent Universal Hub",
    description="去中心化 AI 智能体撮合中枢 - 基于向量语义匹配 + JWT 门票机制",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS 中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================================
# 健康检查端点
# ============================================================================

@app.get("/health")
async def health_check():
    """健康检查"""
    return {
        "status": "healthy",
        "service": "Agent Universal Hub",
        "version": "1.0.0"
    }


@app.get("/")
async def root():
    """根路径"""
    return {
        "message": "Agent Universal Hub V1.0",
        "docs": "/docs",
        "health": "/health"
    }


# ============================================================================
# API 路由
# ============================================================================

app.include_router(
    api_router,
    prefix=API_V1_PREFIX,
    tags=["v1"]
)


# ============================================================================
# 全局异常处理
# ============================================================================

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """统一 HTTP 异常处理"""
    return {
        "error": exc.status_code,
        "message": exc.detail,
        "path": str(request.url)
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "hub_server.main:app",
        host="0.0.0.0",
        port=8000,
        reload=False  # 禁用 reload 以避免潜在问题
    )
