"""
REST API 路由模块。
提供视频/图片上传、处理启动、状态查询、取消、下载、预览等端点。
"""
from __future__ import annotations

import mimetypes
import threading
import uuid
import logging
from pathlib import Path

import cv2
from fastapi import APIRouter, HTTPException, UploadFile
from fastapi.responses import FileResponse

from backend.app.api.task_store import task_store
from backend.app.models.schemas import (
    BoundingBox,
    ImageMetadata,
    PipelineConfig,
    ProcessRequest,
    ProgressEvent,
    UploadResponse,
)
from backend.app.pipeline.decoder import VideoDecoder
from backend.app.pipeline.pipeline import WatermarkPipeline

router = APIRouter()
logger = logging.getLogger(__name__)

# 允许的视频扩展名
_ALLOWED_VIDEO_EXT = {".mp4", ".avi", ".mkv"}
# 允许的图片扩展名
_ALLOWED_IMAGE_EXT = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}
_ALLOWED_EXT = _ALLOWED_VIDEO_EXT | _ALLOWED_IMAGE_EXT

# 最大文件大小：2 GB
_MAX_FILE_SIZE = 2 * 1024 * 1024 * 1024

# 临时文件根目录
_TMP_ROOT = Path("./tmp")


def _safe_task_dir(task_id: str) -> Path:
    """返回规范化后的任务目录，防止路径遍历。"""
    task_dir = (_TMP_ROOT / task_id).resolve()
    tmp_root_resolved = _TMP_ROOT.resolve()
    if not str(task_dir).startswith(str(tmp_root_resolved)):
        raise HTTPException(status_code=400, detail="非法的 task_id")
    return task_dir


# ------------------------------------------------------------------
# POST /upload
# ------------------------------------------------------------------

@router.post("/upload", response_model=UploadResponse)
async def upload_video(file: UploadFile):
    """
    接收视频或图片文件上传，保存到临时目录，提取元数据和预览帧。
    返回 task_id、预览帧 URL 和元数据。
    """
    original_name = file.filename or "file"
    ext = Path(original_name).suffix.lower()
    if ext not in _ALLOWED_EXT:
        raise HTTPException(
            status_code=415,
            detail="不支持的文件格式，请上传 MP4/AVI/MKV 视频或 JPG/PNG/WEBP/BMP 图片",
        )

    is_image = ext in _ALLOWED_IMAGE_EXT

    # 生成任务 ID 并创建目录
    task_id = str(uuid.uuid4())
    task_dir = _safe_task_dir(task_id)
    task_dir.mkdir(parents=True, exist_ok=True)

    input_path = task_dir / f"input{ext}"

    # 读取并保存文件，同时统计大小
    total_size = 0
    chunk_size = 1024 * 1024  # 1 MB
    try:
        with open(input_path, "wb") as f:
            while True:
                chunk = await file.read(chunk_size)
                if not chunk:
                    break
                total_size += len(chunk)
                if total_size > _MAX_FILE_SIZE:
                    f.close()
                    input_path.unlink(missing_ok=True)
                    raise HTTPException(
                        status_code=413,
                        detail="文件大小超过 2GB 限制",
                    )
                f.write(chunk)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"文件保存失败：{exc}")
    finally:
        await file.close()

    preview_path = task_dir / "preview.jpg"

    if is_image:
        # 图片：直接读取元数据，复制为预览
        img = cv2.imread(str(input_path))
        if img is None:
            input_path.unlink(missing_ok=True)
            raise HTTPException(status_code=422, detail="无法解析图片文件")
        h, w = img.shape[:2]
        cv2.imwrite(str(preview_path), img)
        metadata = ImageMetadata(
            width=w,
            height=h,
            format=ext.lstrip(".").upper(),
            file_size=total_size,
        )
        source_url = f"/static/{task_id}/input{ext}"
        task_store.create_task(
            task_id=task_id,
            input_path=str(input_path),
            preview_frame_url=f"/static/{task_id}/preview.jpg",
            metadata=metadata.model_dump(),
            original_filename=Path(original_name).stem,
            media_type="image",
        )
        return UploadResponse(
            task_id=task_id,
            preview_frame_url=f"/static/{task_id}/preview.jpg",
            source_video_url=source_url,
            metadata=metadata,
            media_type="image",
        )

    # 视频处理逻辑（原有）
    decoder = VideoDecoder()
    try:
        metadata = decoder.open(str(input_path))
    except (FileNotFoundError, ValueError) as exc:
        input_path.unlink(missing_ok=True)
        raise HTTPException(status_code=422, detail=f"无法解析视频文件：{exc}")

    try:
        decoder.seek(1.0)
        frame = decoder.next_frame()
        if frame is None:
            decoder.seek(0.0)
            frame = decoder.next_frame()
        if frame is not None:
            cv2.imwrite(str(preview_path), frame)
    except Exception as exc:
        logger.warning("Preview extraction failed for %s: %s", task_id, exc)
    finally:
        decoder.close()

    preview_frame_url = f"/static/{task_id}/preview.jpg"
    source_video_url = f"/static/{task_id}/input{ext}"

    task_store.create_task(
        task_id=task_id,
        input_path=str(input_path),
        preview_frame_url=preview_frame_url,
        metadata=metadata.model_dump(),
        original_filename=Path(original_name).stem,
        media_type="video",
    )

    return UploadResponse(
        task_id=task_id,
        preview_frame_url=preview_frame_url,
        source_video_url=source_video_url,
        metadata=metadata,
        media_type="video",
    )


# ------------------------------------------------------------------
# POST /process
# ------------------------------------------------------------------

@router.post("/process")
def start_process(req: ProcessRequest):
    """
    启动视频/图片处理任务（后台线程）。
    Manual 模式需提供合法的 manual_regions。
    """
    task = task_store.get_task(req.task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="任务不存在")
    if task["status"] == "processing":
        raise HTTPException(status_code=409, detail="任务正在处理中，请勿重复启动")

    metadata = task["metadata"]
    frame_width: int = metadata["width"]
    frame_height: int = metadata["height"]
    media_type: str = task.get("media_type", "video")

    # 构建流水线配置
    config = req.config or PipelineConfig()
    config.detection_mode = req.mode

    if req.mode == "manual":
        if not req.manual_regions:
            raise HTTPException(
                status_code=400,
                detail="manual 模式下 manual_regions 不能为空",
            )
        for idx, box in enumerate(req.manual_regions):
            if box.x < 0 or box.y < 0 or box.w <= 0 or box.h <= 0:
                raise HTTPException(
                    status_code=400,
                    detail=f"第 {idx} 个区域坐标非法（x/y 不能为负，w/h 必须大于 0）",
                )
            if box.x + box.w > frame_width:
                raise HTTPException(
                    status_code=400,
                    detail=f"第 {idx} 个区域超出宽度（{box.x}+{box.w} > {frame_width}）",
                )
            if box.y + box.h > frame_height:
                raise HTTPException(
                    status_code=400,
                    detail=f"第 {idx} 个区域超出高度（{box.y}+{box.h} > {frame_height}）",
                )
        config.manual_regions = req.manual_regions

    input_path = task["input_path"]
    ext = Path(input_path).suffix
    task_dir = _safe_task_dir(req.task_id)
    output_path = str(task_dir / f"output{ext}")

    pipeline = WatermarkPipeline(
        task_id=req.task_id,
        on_progress=lambda event: task_store.update_progress(req.task_id, event),
    )
    task_store.set_pipeline(req.task_id, pipeline)

    task_store.update_progress(
        req.task_id,
        ProgressEvent(task_id=req.task_id, percent=0.0, fps=0.0, status="processing"),
    )

    def _run():
        if media_type == "image":
            result = pipeline.process_image(input_path, output_path, config)
        else:
            result = pipeline.process(input_path, output_path, config)
        if result.success and result.output_path:
            task_store.set_output(req.task_id, result.output_path)
        else:
            task_store.set_error(req.task_id, result.message or "处理失败")

    thread = threading.Thread(target=_run, daemon=True)
    thread.start()

    return {"task_id": req.task_id, "status": "queued"}


# ------------------------------------------------------------------
# GET /status/{task_id}
# ------------------------------------------------------------------

@router.get("/status/{task_id}")
def get_status(task_id: str):
    """查询任务处理状态。"""
    status = task_store.get_status(task_id)
    if status is None:
        raise HTTPException(status_code=404, detail="任务不存在")
    return status


# ------------------------------------------------------------------
# DELETE /task/{task_id}
# ------------------------------------------------------------------

@router.delete("/task/{task_id}")
def cancel_task(task_id: str):
    """取消正在处理的任务。"""
    task = task_store.get_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="任务不存在")

    pipeline = task_store.get_pipeline(task_id)
    if pipeline is not None:
        pipeline.cancel()

    return {"success": True}


# ------------------------------------------------------------------
# GET /download/{task_id}
# ------------------------------------------------------------------

@router.get("/download/{task_id}")
def download_result(task_id: str):
    """
    下载处理完成的视频文件。
    校验任务状态、文件存在性及创建时间（24小时内有效）。
    """
    from datetime import datetime, timedelta

    task = task_store.get_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="任务不存在")

    if task["status"] != "done":
        raise HTTPException(status_code=400, detail="任务尚未完成")

    output_path = task.get("output_path")
    if not output_path or not Path(output_path).exists():
        raise HTTPException(status_code=404, detail="输出文件不存在")

    # 校验任务创建时间在 24 小时内
    created_at = task["created_at"]
    if datetime.utcnow() - created_at > timedelta(hours=24):
        raise HTTPException(status_code=410, detail="下载链接已过期（超过24小时）")

    ext = Path(output_path).suffix
    original_stem = task.get("original_filename") or "video"
    download_filename = f"{original_stem}_no_watermark{ext}"

    media_type = mimetypes.guess_type(output_path)[0] or "application/octet-stream"
    return FileResponse(
        path=output_path,
        media_type=media_type,
        filename=download_filename,
    )


# ------------------------------------------------------------------
# GET /preview/{task_id}
# ------------------------------------------------------------------

@router.get("/preview/{task_id}")
def get_preview(task_id: str):
    """返回任务对应的预览帧图片。"""
    task = task_store.get_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="任务不存在")

    task_dir = _safe_task_dir(task_id)
    preview_path = task_dir / "preview.jpg"

    if not preview_path.exists():
        raise HTTPException(status_code=404, detail="预览帧不存在")

    return FileResponse(path=str(preview_path), media_type="image/jpeg")
