"""
WebSocket 进度推送模块。
客户端连接后，每 0.5 秒查询一次任务状态并推送 ProgressEvent JSON。
任务完成或出错后推送最终状态并关闭连接。
"""
from __future__ import annotations

import asyncio
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from backend.app.api.task_store import task_store

ws_router = APIRouter()
logger = logging.getLogger(__name__)


@ws_router.websocket("/ws/progress/{task_id}")
async def websocket_progress(websocket: WebSocket, task_id: str):
    """
    WebSocket 端点：实时推送指定任务的处理进度。
    - 每 0.5 秒查询一次任务状态
    - 任务完成（done）或出错（error）后推送最终状态并关闭连接
    - 客户端断开时优雅退出
    """
    await websocket.accept()
    should_close = True

    try:
        while True:
            status = task_store.get_status(task_id)

            if status is None:
                # 任务不存在，推送错误并关闭
                await websocket.send_json({
                    "task_id": task_id,
                    "percent": 0.0,
                    "fps": 0.0,
                    "status": "error",
                    "message": "任务不存在",
                })
                break

            # 推送当前状态
            await websocket.send_json(status.model_dump())

            # 任务终态：完成或出错，推送后关闭连接
            if status.status in ("done", "error"):
                break

            # 等待 0.5 秒后再次查询
            await asyncio.sleep(0.5)

    except WebSocketDisconnect:
        # 客户端主动断开，静默处理
        should_close = False
    except Exception:
        # 其他异常，尝试推送错误后关闭
        logger.exception("WebSocket progress stream failed for task %s", task_id)
        try:
            await websocket.send_json({
                "task_id": task_id,
                "percent": 0.0,
                "fps": 0.0,
                "status": "error",
                "message": "服务器内部错误",
            })
        except Exception:
            pass
    finally:
        if should_close:
            try:
                await websocket.close()
            except Exception:
                pass
