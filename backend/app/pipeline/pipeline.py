"""
处理主流水线：解码 -> 检测 -> 修复 -> 编码，并持续上报进度。
"""
from __future__ import annotations

import os
import time
import logging
from collections import deque
from typing import Callable, Optional

import numpy as np

from backend.app.models.schemas import (
    PipelineConfig,
    ProcessResult,
    ProgressEvent,
)
from backend.app.pipeline.decoder import VideoDecoder
from backend.app.pipeline.detector import WatermarkDetector
from backend.app.pipeline.encoder import VideoEncoder
from backend.app.pipeline.inpainter import InpaintingEngine

_PROGRESS_INTERVAL = 10   # 每处理多少帧推送一次进度
_WINDOW_SIZE = 30         # 滑动窗口帧数（用于计算 fps）
logger = logging.getLogger(__name__)


class WatermarkPipeline:
    """主处理流水线：解码 → 检测 → 修复 → 编码。"""

    def __init__(
        self,
        task_id: str = "",
        on_progress: Optional[Callable[[ProgressEvent], None]] = None,
    ) -> None:
        self._task_id = task_id
        self._on_progress = on_progress
        self._cancelled = False
        self._current_progress = ProgressEvent(
            task_id=task_id,
            percent=0.0,
            fps=0.0,
            status="idle",
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def process(
        self,
        input_path: str,
        output_path: str,
        config: PipelineConfig,
    ) -> ProcessResult:
        """同步逐帧处理视频，返回处理结果。"""
        self._cancelled = False

        decoder = VideoDecoder()
        encoder = VideoEncoder()
        detector = WatermarkDetector(threshold=config.detection_threshold)
        inpainter = InpaintingEngine()
        inpainter.set_algorithm(config.inpaint_algorithm)
        inpainter.set_radius(config.inpaint_radius)
        inpainter.set_engine(getattr(config, 'inpaint_engine', 'lama_cpu'))
        inpainter.lama_context_pad = getattr(config, 'lama_context_pad', 30)
        inpainter.static_background = getattr(config, 'static_background', False)

        try:
            # 1. 打开视频，获取元数据
            metadata = decoder.open(input_path)
            total_frames = metadata.total_frames

            # 2. 根据检测模式准备掩码
            mask_result = None

            if config.detection_mode == "manual":
                regions = config.manual_regions or []
                mask_result = detector.regions_to_mask_array(
                    regions, metadata.width, metadata.height
                )
            else:
                sample_count = min(config.sample_frame_count, total_frames)
                sample_frames = []
                # 全片均匀采样，比只采样开头更容易捕捉中后段出现的水印。
                if sample_count > 0 and total_frames > 0:
                    if sample_count == 1:
                        target_indices = [0]
                    else:
                        target_indices = [
                            int(round(i * (total_frames - 1) / (sample_count - 1)))
                            for i in range(sample_count)
                        ]
                    # 去重后保序，避免浮点四舍五入造成重复采样
                    seen = set()
                    unique_indices = [idx for idx in target_indices if not (idx in seen or seen.add(idx))]

                    fps = metadata.fps if metadata.fps > 0 else 1.0
                    for idx in unique_indices:
                        decoder.seek(idx / fps)
                        frame = decoder.next_frame()
                        if frame is not None:
                            sample_frames.append(frame)

                mask_result = None
                if len(sample_frames) >= 2:
                    variance_map = detector.build_temporal_map(sample_frames)
                    mask_result = detector.detect(
                        variance_map,
                        mode="auto",
                        sample_frames=sample_frames,
                        corner_scan_w=config.corner_scan_w,
                        corner_scan_h=config.corner_scan_h,
                        color_sat_threshold=config.color_sat_threshold,
                        color_val_threshold=config.color_val_threshold,
                    )

                decoder.close()
                decoder = VideoDecoder()
                decoder.open(input_path)

            # 3. 打开编码器
            encoder.open(
                output_path=output_path,
                codec=config.output_codec,
                fps=metadata.fps,
                width=metadata.width,
                height=metadata.height,
                bitrate=config.output_bitrate,
                audio_source=input_path,
            )

            logger.info("Pipeline start: total_frames=%s mode=%s", total_frames, config.detection_mode)
            if mask_result is not None:
                nonzero = int(np.count_nonzero(mask_result.mask))
                logger.info(
                    "Mask ready: regions=%s nonzero_pixels=%s",
                    len(mask_result.boxes),
                    nonzero,
                )
            else:
                logger.info("No watermark mask detected; passthrough enabled")

            # 4. 逐帧处理
            processed_frames = 0
            watermark_detected = False
            warning_frames: list[int] = []
            timestamps: deque[float] = deque(maxlen=_WINDOW_SIZE)

            while True:
                if self._cancelled:
                    break

                frame = decoder.next_frame()
                if frame is None:
                    break

                # 修复（只处理 bounding box 区域）
                if mask_result is not None:
                    watermark_detected = True
                    try:
                        frame = inpainter.inpaint(frame, mask_result.mask, mask_result.boxes)
                    except Exception as e:
                        logger.warning("Inpaint failed at frame %s: %s", processed_frames, e)
                        warning_frames.append(processed_frames)

                encoder.write_frame(frame)
                processed_frames += 1
                timestamps.append(time.monotonic())

                # 每 N 帧推送一次进度
                if processed_frames % _PROGRESS_INTERVAL == 0:
                    fps_val = _calc_fps(timestamps)
                    pct = processed_frames / total_frames * 100 if total_frames > 0 else 0
                    logger.info(
                        "Progress: %.1f%% (%s/%s) | %.1f fps",
                        pct,
                        processed_frames,
                        total_frames,
                        fps_val,
                    )
                    self._emit_progress(
                        processed_frames, total_frames, timestamps, "processing"
                    )

            # 5. 取消处理
            if self._cancelled:
                encoder.close()
                decoder.close()
                _try_remove(output_path)
                return ProcessResult(
                    task_id=self._task_id,
                    success=False,
                    message="Cancelled",
                )

            # 6. 完成编码
            encoder.finalize()
            decoder.close()
            logger.info("Pipeline done: frames=%s output=%s", processed_frames, output_path)

            # 推送完成事件
            self._emit_progress(
                processed_frames, total_frames, timestamps, "done"
            )

            return ProcessResult(
                task_id=self._task_id,
                success=True,
                output_path=output_path,
                watermark_detected=watermark_detected,
                warning_frames=warning_frames,
            )

        except Exception as exc:
            logger.exception("Pipeline failed: %s", exc)
            encoder.close()
            decoder.close()
            _try_remove(output_path)
            self._current_progress = ProgressEvent(
                task_id=self._task_id,
                percent=self._current_progress.percent,
                fps=0.0,
                status="error",
                message=str(exc),
            )
            return ProcessResult(
                task_id=self._task_id,
                success=False,
                message=str(exc),
            )

    def process_image(
        self,
        input_path: str,
        output_path: str,
        config: PipelineConfig,
    ) -> ProcessResult:
        """处理单张图片：检测 → 修复 → 保存。"""
        import cv2 as _cv2

        self._cancelled = False
        detector = WatermarkDetector(threshold=config.detection_threshold)
        inpainter = InpaintingEngine()
        inpainter.set_algorithm(config.inpaint_algorithm)
        inpainter.set_radius(config.inpaint_radius)
        inpainter.set_engine(getattr(config, 'inpaint_engine', 'lama_cpu'))
        inpainter.lama_context_pad = getattr(config, 'lama_context_pad', 30)

        try:
            self._emit_image_progress(10, "processing")

            frame = _cv2.imread(input_path)
            if frame is None:
                raise ValueError(f"无法读取图片：{input_path}")

            h, w = frame.shape[:2]
            mask_result = None

            if config.detection_mode == "manual":
                regions = config.manual_regions or []
                mask_result = detector.regions_to_mask_array(regions, w, h)
            else:
                # 自动检测：单帧模式，直接扫描角落
                import numpy as np
                variance_map = np.zeros((h, w), dtype=np.float32)
                mask_result = detector.detect(
                    variance_map,
                    mode="auto",
                    sample_frames=[frame],
                    corner_scan_w=config.corner_scan_w,
                    corner_scan_h=config.corner_scan_h,
                    color_sat_threshold=config.color_sat_threshold,
                    color_val_threshold=config.color_val_threshold,
                )

            self._emit_image_progress(50, "processing")

            watermark_detected = False
            if mask_result is not None:
                watermark_detected = True
                frame = inpainter.inpaint(frame, mask_result.mask, mask_result.boxes)

            self._emit_image_progress(90, "processing")

            success = _cv2.imwrite(output_path, frame)
            if not success:
                raise RuntimeError(f"图片保存失败：{output_path}")

            self._emit_image_progress(100, "done")
            logger.info("Image pipeline done: output=%s", output_path)

            return ProcessResult(
                task_id=self._task_id,
                success=True,
                output_path=output_path,
                watermark_detected=watermark_detected,
            )

        except Exception as exc:
            logger.exception("Image pipeline failed: %s", exc)
            _try_remove(output_path)
            self._current_progress = ProgressEvent(
                task_id=self._task_id,
                percent=self._current_progress.percent,
                fps=0.0,
                status="error",
                message=str(exc),
            )
            return ProcessResult(
                task_id=self._task_id,
                success=False,
                message=str(exc),
            )

    def _emit_image_progress(self, percent: float, status: str) -> None:
        event = ProgressEvent(
            task_id=self._task_id,
            percent=percent,
            fps=0.0,
            status=status,
        )
        self._current_progress = event
        if self._on_progress is not None:
            self._on_progress(event)

    def cancel(self) -> None:
        """设置取消标志，process 循环检测到后会停止并清理。"""
        self._cancelled = True

    def get_progress(self) -> ProgressEvent:
        """返回当前进度快照。"""
        return self._current_progress

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _emit_progress(
        self,
        processed: int,
        total: int,
        timestamps: deque,
        status: str,
    ) -> None:
        percent = (processed / total * 100) if total > 0 else 0.0
        fps = _calc_fps(timestamps)
        event = ProgressEvent(
            task_id=self._task_id,
            percent=percent,
            fps=fps,
            status=status,
        )
        self._current_progress = event
        if self._on_progress is not None:
            self._on_progress(event)


# ------------------------------------------------------------------
# Module-level helpers
# ------------------------------------------------------------------

def _calc_fps(timestamps: deque) -> float:
    """用滑动窗口内的时间戳计算帧率。"""
    if len(timestamps) < 2:
        return 0.0
    elapsed = timestamps[-1] - timestamps[0]
    if elapsed <= 0:
        return 0.0
    return (len(timestamps) - 1) / elapsed


def _try_remove(path: str) -> None:
    """尝试删除文件，忽略错误。"""
    try:
        if path and os.path.exists(path):
            os.remove(path)
    except OSError:
        pass
