"""
水印检测模块：从采样帧构建时序特征，并在角落区域检测疑似水印。
"""
from __future__ import annotations

import logging
from typing import List, Optional, Tuple

import cv2
import numpy as np

from backend.app.models.schemas import BoundingBox, WatermarkMask

logger = logging.getLogger(__name__)

class WatermarkDetector:
    """水印检测器：支持自动角落检测与手动区域转掩码。"""

    def __init__(self, threshold: float = 0.3):
        self.threshold = threshold

    def set_threshold(self, threshold: float) -> None:
        self.threshold = threshold

    def build_temporal_map(self, frames: List[np.ndarray]) -> np.ndarray:
        """中值帧差异图，作为辅助信号传给 detect。"""
        if len(frames) < 2:
            raise ValueError("At least 2 frames are required")
        gray_frames = [
            cv2.cvtColor(f, cv2.COLOR_BGR2GRAY).astype(np.float32)
            for f in frames
        ]
        stack = np.stack(gray_frames, axis=0)
        median_frame = np.median(stack, axis=0)
        diff_sum = np.zeros_like(median_frame)
        for g in gray_frames:
            diff_sum += np.abs(g - median_frame)
        return diff_sum / len(gray_frames)

    def analyze_sequence(self, frames: List[np.ndarray]) -> np.ndarray:
        return self.build_temporal_map(frames)

    def detect(
        self,
        variance_map: np.ndarray,
        mode: str,
        _manual_regions: Optional[List[BoundingBox]] = None,
        _metadata=None,
        sample_frames: Optional[List[np.ndarray]] = None,
        corner_scan_w: float = 0.35,
        corner_scan_h: float = 0.20,
        color_sat_threshold: int = 60,
        color_val_threshold: int = 170,
    ) -> Optional["MaskResult"]:
        if mode == "manual":
            return None

        if not sample_frames:
            return None

        h, w = sample_frames[0].shape[:2]
        mean_frame = self._mean_frame(sample_frames)

        scan_w = int(w * corner_scan_w)
        scan_h = int(h * corner_scan_h)

        corners = [
            (0, 0, "左上"),
            (w - scan_w, 0, "右上"),
            (0, h - scan_h, "左下"),
            (w - scan_w, h - scan_h, "右下"),
        ]

        all_boxes: List[Tuple[int, int, int, int]] = []
        full_mask = np.zeros((h, w), dtype=np.uint8)

        for ox, oy, name in corners:
            patch = mean_frame[oy:oy + scan_h, ox:ox + scan_w]
            diff_patch = variance_map[oy:oy + scan_h, ox:ox + scan_w]
            patch_frames = [f[oy:oy + scan_h, ox:ox + scan_w] for f in sample_frames]

            boxes, mask_patch = self._detect_white_text(
                patch,
                diff_patch,
                patch_frames=patch_frames,
                sat_threshold=color_sat_threshold,
                val_threshold=color_val_threshold,
            )
            if boxes:
                logger.info("Watermark detected at %s corner: %s regions", name, len(boxes))
                for bx, by, bw, bh in boxes:
                    all_boxes.append((ox + bx, oy + by, bw, bh))
                full_mask[oy:oy + scan_h, ox:ox + scan_w] = np.maximum(
                    full_mask[oy:oy + scan_h, ox:ox + scan_w], mask_patch
                )

        if not all_boxes:
            logger.info("No watermark detected in the four corners")
            return None

        # 合并重叠/相邻区域并小幅扩展掩码，减少文字边缘残留。
        merged_boxes = self._merge_boxes(all_boxes, expand=2, max_gap=6, frame_w=w, frame_h=h)
        expanded_mask = self._dilate_mask(full_mask, radius=2)
        return MaskResult(mask=expanded_mask, boxes=merged_boxes)

    # ------------------------------------------------------------------

    def _mean_frame(self, frames: List[np.ndarray]) -> np.ndarray:
        """多帧均值，减少运动物体干扰，保留固定水印特征。"""
        acc = np.zeros_like(frames[0], dtype=np.float32)
        for f in frames:
            acc += f.astype(np.float32)
        return (acc / len(frames)).astype(np.uint8)

    def _detect_white_text(
        self,
        patch_bgr: np.ndarray,
        diff_patch: np.ndarray,
        patch_frames: Optional[List[np.ndarray]] = None,
        sat_threshold: int = 60,
        val_threshold: int = 170,
    ) -> Tuple[List[Tuple[int, int, int, int]], np.ndarray]:
        """在角落 patch 里检测白色半透明文字水印。

        豆包水印特征：
        - 白色/浅灰色文字，RGB 三通道值接近且偏高
        - 半透明叠加，不会是纯白（通常 R/G/B 在 180~255 之间）
        - 三通道差异小（低饱和度）

        策略：
        1. 提取低饱和度 + 高亮度的像素（白色文字候选）
        2. 用时序差异图过滤掉静态背景中的白色区域（如白墙）
        3. 形态学连接文字笔画，提取轮廓
        """
        ph, pw = patch_bgr.shape[:2]
        mask_out = np.zeros((ph, pw), dtype=np.uint8)

        # --- 颜色特征：低饱和度 + 高亮度 ---
        hsv = cv2.cvtColor(patch_bgr, cv2.COLOR_BGR2HSV).astype(np.float32)
        sat = hsv[:, :, 1]   # 0~255
        val = hsv[:, :, 2]   # 0~255

        color_mask = ((sat < float(sat_threshold)) & (val > float(val_threshold))).astype(np.uint8)

        if not np.any(color_mask):
            return [], mask_out

        # --- 时序一致性：在多帧里“持续出现”的像素更可能是水印 ---
        combined = color_mask
        if patch_frames and len(patch_frames) >= 3:
            stable_mask = self._stable_white_mask(
                patch_frames=patch_frames,
                sat_threshold=sat_threshold,
                val_threshold=val_threshold,
            )
            # 优先使用稳定像素，结果更接近手动框选。
            if np.any(stable_mask):
                combined = cv2.bitwise_and(color_mask, stable_mask)
                if not np.any(combined):
                    combined = stable_mask

        # --- 运动辅助：排除明显运动背景区域 ---
        diff_norm = diff_patch.copy().astype(np.float32)
        d_max = float(diff_norm.max())
        if d_max > 0:
            diff_norm = diff_norm / d_max
            low_motion = (diff_norm < 0.25).astype(np.uint8)
            low_motion_filtered = cv2.bitwise_and(combined, low_motion)
            if np.any(low_motion_filtered):
                combined = low_motion_filtered

        # --- 形态学处理：连接文字笔画 ---
        k = max(3, int(min(ph, pw) * 0.035))
        kernel_c = cv2.getStructuringElement(cv2.MORPH_RECT, (k, k))
        kernel_o = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
        closed = cv2.morphologyEx(combined, cv2.MORPH_CLOSE, kernel_c)
        refined = cv2.morphologyEx(closed, cv2.MORPH_OPEN, kernel_o)

        contours, _ = cv2.findContours(refined, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        total = ph * pw
        min_area = total * 0.0015  # 降低下限，避免小字号水印被漏检
        max_area = total * 0.50    # 不超过 50%（防止整个角落都是白色背景）

        valid = [c for c in contours if min_area < cv2.contourArea(c) < max_area]
        if not valid:
            return [], mask_out

        for c in valid:
            cv2.drawContours(mask_out, [c], -1, 1, thickness=cv2.FILLED)

        return [cv2.boundingRect(c) for c in valid], mask_out

    def _stable_white_mask(
        self,
        patch_frames: List[np.ndarray],
        sat_threshold: int,
        val_threshold: int,
    ) -> np.ndarray:
        """统计多帧白色候选出现频率，输出稳定像素掩码。"""
        h, w = patch_frames[0].shape[:2]
        hit_count = np.zeros((h, w), dtype=np.float32)
        total = 0

        for frame in patch_frames:
            hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV).astype(np.float32)
            sat = hsv[:, :, 1]
            val = hsv[:, :, 2]
            white = ((sat < float(sat_threshold)) & (val > float(val_threshold))).astype(np.uint8)
            hit_count += white
            total += 1

        if total == 0:
            return np.zeros((h, w), dtype=np.uint8)

        freq = hit_count / float(total)
        # self.threshold 默认 0.3；这里做下限保护，避免误检过多。
        keep_ratio = max(0.45, min(0.9, float(self.threshold)))
        stable = (freq >= keep_ratio).astype(np.uint8)
        return stable

    def _dilate_mask(self, mask: np.ndarray, radius: int = 2) -> np.ndarray:
        """轻微膨胀掩码，覆盖字符边缘抗锯齿像素。"""
        if radius <= 0:
            return mask
        k = radius * 2 + 1
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k, k))
        return cv2.dilate(mask, kernel, iterations=1)

    def _merge_boxes(
        self,
        boxes: List[Tuple[int, int, int, int]],
        expand: int,
        max_gap: int,
        frame_w: int,
        frame_h: int,
    ) -> List[Tuple[int, int, int, int]]:
        """合并重叠或近邻包围盒，并做边界内外扩。"""
        if not boxes:
            return []

        def _to_xyxy(b: Tuple[int, int, int, int]) -> Tuple[int, int, int, int]:
            x, y, bw, bh = b
            x1 = max(0, x - expand)
            y1 = max(0, y - expand)
            x2 = min(frame_w, x + bw + expand)
            y2 = min(frame_h, y + bh + expand)
            return (x1, y1, x2, y2)

        rects = [_to_xyxy(b) for b in boxes]
        changed = True
        while changed:
            changed = False
            merged: List[Tuple[int, int, int, int]] = []
            for rect in rects:
                rx1, ry1, rx2, ry2 = rect
                hit = False
                for i, (mx1, my1, mx2, my2) in enumerate(merged):
                    intersects_or_close = not (
                        rx2 < mx1 - max_gap
                        or rx1 > mx2 + max_gap
                        or ry2 < my1 - max_gap
                        or ry1 > my2 + max_gap
                    )
                    if intersects_or_close:
                        merged[i] = (
                            min(mx1, rx1),
                            min(my1, ry1),
                            max(mx2, rx2),
                            max(my2, ry2),
                        )
                        hit = True
                        changed = True
                        break
                if not hit:
                    merged.append(rect)
            rects = merged

        return [(x1, y1, x2 - x1, y2 - y1) for (x1, y1, x2, y2) in rects]

    # ------------------------------------------------------------------
    # 手动模式
    # ------------------------------------------------------------------

    def regions_to_mask_array(
        self,
        regions: List[BoundingBox],
        frame_width: int,
        frame_height: int,
    ) -> "MaskResult":
        for r in regions:
            if r.x < 0 or r.y < 0 or r.w <= 0 or r.h <= 0:
                raise ValueError(f"Region out of bounds: {r}")
            if r.x + r.w > frame_width or r.y + r.h > frame_height:
                raise ValueError(f"Region out of bounds: {r}")

        mask = np.zeros((frame_height, frame_width), dtype=np.uint8)
        boxes = []
        for r in regions:
            mask[r.y: r.y + r.h, r.x: r.x + r.w] = 1
            boxes.append((r.x, r.y, r.w, r.h))

        return MaskResult(mask=mask, boxes=boxes)

    def regions_to_mask(
        self,
        regions: List[BoundingBox],
        frame_width: int,
        frame_height: int,
    ) -> WatermarkMask:
        result = self.regions_to_mask_array(regions, frame_width, frame_height)
        return WatermarkMask(
            regions=regions,
            pixel_mask=result.mask.tolist(),
            confidence=1.0,
            mask_type="static",
        )


class MaskResult:
    """检测结果：二值掩码 + 包围盒列表。"""

    def __init__(self, mask: np.ndarray, boxes: List[Tuple[int, int, int, int]]):
        self.mask = mask
        self.boxes = boxes
        self.confidence = 0.7
