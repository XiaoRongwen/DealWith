from __future__ import annotations

from typing import List, Optional, Union

from pydantic import BaseModel


class BoundingBox(BaseModel):
    """矩形区域，单位为像素。"""
    x: int
    y: int
    w: int
    h: int


class VideoMetadata(BaseModel):
    """视频基础元数据。"""
    duration: float
    fps: float
    total_frames: int
    width: int
    height: int
    codec: str
    bitrate: int


class ImageMetadata(BaseModel):
    """图片基础元数据。"""
    width: int
    height: int
    format: str
    file_size: int


class WatermarkMask(BaseModel):
    """水印掩码描述（可选包含逐像素 mask）。"""
    regions: List[BoundingBox]
    pixel_mask: Optional[List[List[int]]] = None
    confidence: float = 1.0
    mask_type: str = "static"


class PipelineConfig(BaseModel):
    """处理流水线参数。"""
    detection_mode: str = "auto"
    manual_regions: Optional[List[BoundingBox]] = None

    # 检测参数
    detection_threshold: float = 0.3       # 自动检测灵敏度
    sample_frame_count: int = 100          # 自动检测采样帧数
    corner_scan_w: float = 0.35            # 角落扫描宽度比例 (0.1~0.5)
    corner_scan_h: float = 0.20            # 角落扫描高度比例 (0.1~0.4)
    color_sat_threshold: int = 60          # 白色水印饱和度上限 (0~120)
    color_val_threshold: int = 170         # 白色水印亮度下限 (100~255)

    # 修复参数
    inpaint_engine: str = "lama_cpu"       # lama_cpu / lama_gpu / opencv
    inpaint_algorithm: str = "telea"       # opencv: telea / navier_stokes
    inpaint_radius: int = 3                # opencv 修复半径
    lama_context_pad: int = 30             # LaMa 上下文 padding (px)
    static_background: bool = False         # 静态背景模式：复用第一帧修复结果

    # 输出参数
    use_gpu: bool = False
    output_codec: str = "h264"
    output_bitrate: Optional[int] = None


class ProgressEvent(BaseModel):
    """内部实时进度事件。percent 使用 0~100。"""
    task_id: str
    percent: float
    fps: float = 0.0
    status: str
    message: Optional[str] = None


class ProcessResult(BaseModel):
    """流水线执行结果。"""
    task_id: str
    success: bool
    output_path: Optional[str] = None
    watermark_detected: bool = False
    warning_frames: List[int] = []
    message: Optional[str] = None


class TaskStatus(BaseModel):
    """对外状态查询结果。percent 使用 0~100。"""
    task_id: str
    status: str
    percent: float = 0.0
    fps: float = 0.0
    download_url: Optional[str] = None
    error: Optional[str] = None
    message: Optional[str] = None


class UploadResponse(BaseModel):
    """上传接口响应。"""
    task_id: str
    preview_frame_url: str
    source_video_url: str
    metadata: Union[VideoMetadata, ImageMetadata]
    media_type: str = "video"  # "video" | "image"


class ProcessRequest(BaseModel):
    """启动处理请求。"""
    task_id: str
    mode: str = "auto"
    manual_regions: Optional[List[BoundingBox]] = None
    config: Optional[PipelineConfig] = None
