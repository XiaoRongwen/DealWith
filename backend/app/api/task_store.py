"""
任务状态内存存储模块。
使用 threading.Lock 保护并发访问，存储每个任务的状态、进度、输出路径等信息。
"""
from __future__ import annotations

import threading
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Dict, Optional

from backend.app.models.schemas import ProgressEvent, TaskStatus

if TYPE_CHECKING:
    from backend.app.pipeline.pipeline import WatermarkPipeline


class TaskInfo:
    """单个任务的完整信息。"""

    def __init__(
        self,
        task_id: str,
        input_path: str,
        preview_frame_url: str,
        metadata: dict,
        media_type: str = "video",
    ) -> None:
        self.task_id = task_id
        self.input_path = input_path
        self.preview_frame_url = preview_frame_url
        self.metadata = metadata
        self.media_type: str = media_type  # "video" | "image"
        self.status: str = "pending"
        self.percent: float = 0.0
        self.fps: float = 0.0
        self.output_path: Optional[str] = None
        self.error: Optional[str] = None
        self.message: Optional[str] = None
        self.created_at: datetime = datetime.utcnow()
        self.pipeline: Optional["WatermarkPipeline"] = None
        self.original_filename: str = ""


class TaskStore:
    """线程安全的内存任务状态存储。"""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._tasks: Dict[str, TaskInfo] = {}

    # ------------------------------------------------------------------
    # 写操作
    # ------------------------------------------------------------------

    def create_task(
        self,
        task_id: str,
        input_path: str,
        preview_frame_url: str,
        metadata: dict,
        original_filename: str = "",
        media_type: str = "video",
    ) -> None:
        """创建新任务记录。"""
        info = TaskInfo(
            task_id=task_id,
            input_path=input_path,
            preview_frame_url=preview_frame_url,
            metadata=metadata,
            media_type=media_type,
        )
        info.original_filename = original_filename
        with self._lock:
            self._tasks[task_id] = info

    def update_progress(self, task_id: str, event: ProgressEvent) -> None:
        """根据 ProgressEvent 更新任务进度和状态。"""
        with self._lock:
            info = self._tasks.get(task_id)
            if info is None:
                return
            info.percent = event.percent
            info.fps = event.fps
            info.status = event.status
            info.message = event.message
            if event.status != "error":
                info.error = None

    def set_output(self, task_id: str, output_path: str) -> None:
        """设置任务输出文件路径，并将状态置为 done。"""
        with self._lock:
            info = self._tasks.get(task_id)
            if info is None:
                return
            info.output_path = output_path
            info.status = "done"
            info.percent = 100.0
            info.message = "处理完成"

    def set_error(self, task_id: str, error: str) -> None:
        """记录任务错误信息，并将状态置为 error。"""
        with self._lock:
            info = self._tasks.get(task_id)
            if info is None:
                return
            info.error = error
            info.status = "error"
            info.message = error

    def set_pipeline(self, task_id: str, pipeline: "WatermarkPipeline") -> None:
        """关联流水线实例（用于取消操作）。"""
        with self._lock:
            info = self._tasks.get(task_id)
            if info is None:
                return
            info.pipeline = pipeline

    # ------------------------------------------------------------------
    # 读操作
    # ------------------------------------------------------------------

    def get_status(self, task_id: str) -> Optional[TaskStatus]:
        """返回任务的精简状态（供 /status 端点使用）。"""
        with self._lock:
            info = self._tasks.get(task_id)
            if info is None:
                return None
            download_url = (
                f"/download/{task_id}" if info.status == "done" else None
            )
            return TaskStatus(
                task_id=task_id,
                status=info.status,
                percent=info.percent,
                fps=info.fps,
                download_url=download_url,
                error=info.error,
                message=info.message,
            )

    def get_task(self, task_id: str) -> Optional[dict]:
        """返回任务的完整信息字典。"""
        with self._lock:
            info = self._tasks.get(task_id)
            if info is None:
                return None
            return {
                "task_id": info.task_id,
                "input_path": info.input_path,
                "preview_frame_url": info.preview_frame_url,
                "metadata": info.metadata,
                "media_type": info.media_type,
                "status": info.status,
                "percent": info.percent,
                "fps": info.fps,
                "output_path": info.output_path,
                "error": info.error,
                "message": info.message,
                "created_at": info.created_at,
                "original_filename": info.original_filename,
            }

    def get_pipeline(self, task_id: str) -> Optional["WatermarkPipeline"]:
        """返回关联的流水线实例。"""
        with self._lock:
            info = self._tasks.get(task_id)
            if info is None:
                return None
            return info.pipeline

    # ------------------------------------------------------------------
    # 清理
    # ------------------------------------------------------------------

    def cleanup_expired(self, max_age_hours: int = 24) -> None:
        """清理超过指定时长的任务记录（不删除磁盘文件）。"""
        cutoff = datetime.utcnow() - timedelta(hours=max_age_hours)
        with self._lock:
            expired = [
                tid
                for tid, info in self._tasks.items()
                if info.created_at < cutoff
            ]
            for tid in expired:
                del self._tasks[tid]


# 全局单例，供路由模块直接导入使用
task_store = TaskStore()
