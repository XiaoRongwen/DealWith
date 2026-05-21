"""
FastAPI 应用入口。
- 配置 CORS（开发模式，允许所有来源）
- 挂载静态文件服务（/tmp → /static）
- 注册 REST 路由和 WebSocket 路由
- 全局异常处理（500 错误不暴露堆栈）
- 启动时创建 ./tmp 目录
"""
from __future__ import annotations

import os
import logging

from fastapi import FastAPI, HTTPException, Request
from fastapi.exception_handlers import http_exception_handler
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from backend.app.api.routes import router
from backend.app.api.websocket import ws_router

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
logger = logging.getLogger(__name__)

# ------------------------------------------------------------------
# 创建应用实例
# ------------------------------------------------------------------

app = FastAPI(
    title="视频水印去除 API",
    description="提供视频水印检测与去除的 REST API 和 WebSocket 接口",
    version="1.0.0",
)

# ------------------------------------------------------------------
# CORS 配置（开发模式，允许所有来源）
# ------------------------------------------------------------------

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ------------------------------------------------------------------
# 全局异常处理：捕获未处理异常，返回 500，不暴露堆栈信息
# ------------------------------------------------------------------

@app.exception_handler(HTTPException)
async def custom_http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    # 保持 HTTPException 原有行为，不吞掉正常错误响应
    return await http_exception_handler(request, exc)

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    # 只捕获非 HTTP 的意外异常
    logger.exception("Unhandled exception on %s: %s", request.url.path, exc)
    return JSONResponse(
        status_code=500,
        content={"detail": "服务器内部错误，请稍后重试"},
    )

# ------------------------------------------------------------------
# 启动事件：创建临时文件目录
# ------------------------------------------------------------------

@app.on_event("startup")
async def startup_event() -> None:
    os.makedirs("./tmp", exist_ok=True)

# ------------------------------------------------------------------
# 挂载静态文件服务（./tmp → /static）
# 注意：目录必须在挂载前存在，因此先确保创建
# ------------------------------------------------------------------

os.makedirs("./tmp", exist_ok=True)

app.mount("/static", StaticFiles(directory="./tmp"), name="static")

# ------------------------------------------------------------------
# 注册路由
# ------------------------------------------------------------------

app.include_router(router)          # REST API 路由
app.include_router(ws_router)       # WebSocket 路由
