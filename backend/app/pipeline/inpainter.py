"""
图像修复模块：封装 LaMa / OpenCV 两类修复引擎，支持 CPU / GPU 并提供自动降级。
"""
from __future__ import annotations

import logging
from typing import Dict, List, Optional, Tuple

import cv2
import numpy as np

logger = logging.getLogger(__name__)

# LaMa 模型单例缓存（按 device 区分）
_lama_models: Dict[str, "_LamaWrapper"] = {}
_lama_failed: set = set()


# ------------------------------------------------------------------
# LaMa 模型加载
# ------------------------------------------------------------------

def _get_lama(device: str = "cpu") -> Optional["_LamaWrapper"]:
    """获取指定设备上的 LaMa 模型单例，加载失败则返回 None。"""
    if device in _lama_failed:
        return None
    if device in _lama_models:
        return _lama_models[device]
    try:
        import torch
        from simple_lama_inpainting.models.model import LAMA_MODEL_URL
        from simple_lama_inpainting.utils.util import download_model

        # GPU 可用性检查
        if device == "cuda" and not torch.cuda.is_available():
            logger.warning("CUDA requested but not available, marking as failed")
            _lama_failed.add(device)
            return None

        model_path = download_model(LAMA_MODEL_URL)
        model = torch.jit.load(model_path, map_location=device)
        model.eval()

        wrapper = _LamaWrapper(model, device)
        _lama_models[device] = wrapper
        logger.info("LaMa model loaded on %s", device.upper())
        return wrapper

    except Exception as e:
        _lama_failed.add(device)
        logger.warning("LaMa unavailable on %s: %s", device, e)
        return None


class _LamaWrapper:
    """LaMa TorchScript 模型封装，正确处理 GPU 张量生命周期与显存管理。"""

    def __init__(self, model, device: str = "cpu"):
        self.model = model
        self.device = device

    def __call__(self, image_rgb: np.ndarray, mask_gray: np.ndarray) -> np.ndarray:
        """
        执行 LaMa 修复。

        Parameters
        ----------
        image_rgb : np.ndarray
            RGB 格式图像，shape (H, W, 3)，dtype uint8。
        mask_gray : np.ndarray
            灰度掩码，shape (H, W)，dtype uint8，非零像素为待修复区域。

        Returns
        -------
        np.ndarray
            修复后的 RGB 图像，shape (H, W, 3)，dtype uint8。
        """
        import torch

        h, w = image_rgb.shape[:2]

        # 归一化到 [0, 1]
        img_f = image_rgb.astype(np.float32) / 255.0
        msk_f = (mask_gray.astype(np.float32) / 255.0)
        msk_f = (msk_f > 0.5).astype(np.float32)

        # 构建张量：image (1, 3, H, W)  mask (1, 1, H, W)
        img_t = torch.from_numpy(img_f).permute(2, 0, 1).unsqueeze(0)
        msk_t = torch.from_numpy(msk_f).unsqueeze(0).unsqueeze(0)

        # 移到目标设备
        img_t = img_t.to(self.device)
        msk_t = msk_t.to(self.device)

        try:
            with torch.no_grad():
                result = self.model(img_t, msk_t)

            # 取回 CPU 并转 numpy
            out = result.squeeze(0).permute(1, 2, 0).cpu().numpy()
            out = np.clip(out * 255.0, 0, 255).astype(np.uint8)

            # 裁回原始尺寸（模型可能输出 padded 尺寸）
            return out[:h, :w]

        finally:
            # 显式释放 GPU 张量，防止显存泄漏
            del img_t, msk_t
            if self.device == "cuda":
                torch.cuda.empty_cache()


# ------------------------------------------------------------------
# 工具函数
# ------------------------------------------------------------------

def _pad_to_multiple(img: np.ndarray, multiple: int = 8) -> Tuple[np.ndarray, int, int]:
    """
    将图像 pad 到 multiple 的整数倍尺寸。

    Returns
    -------
    (padded_image, original_h, original_w)
    """
    h, w = img.shape[:2]
    new_h = ((h + multiple - 1) // multiple) * multiple
    new_w = ((w + multiple - 1) // multiple) * multiple

    if new_h == h and new_w == w:
        return img, h, w

    if img.ndim == 3:
        padded = np.zeros((new_h, new_w, img.shape[2]), dtype=img.dtype)
    else:
        padded = np.zeros((new_h, new_w), dtype=img.dtype)

    padded[:h, :w] = img
    return padded, h, w


# ------------------------------------------------------------------
# 修复引擎
# ------------------------------------------------------------------

class InpaintingEngine:
    """图像修复引擎：优先 LaMa（CPU/GPU），不可用时回退 OpenCV。"""

    def __init__(self) -> None:
        self.algorithm: int = cv2.INPAINT_TELEA
        self.radius: int = 3
        self.engine: str = "lama_cpu"
        self.lama_context_pad: int = 30
        self.static_background: bool = False
        self._first_inpainted: Optional[np.ndarray] = None

    # --- 配置方法 ---

    def set_engine(self, engine: str) -> None:
        if engine not in ("lama_cpu", "lama_gpu", "opencv"):
            raise ValueError(f"Unsupported engine: {engine!r}")
        self.engine = engine

    def set_algorithm(self, algorithm: str) -> None:
        if algorithm == "telea":
            self.algorithm = cv2.INPAINT_TELEA
        elif algorithm == "navier_stokes":
            self.algorithm = cv2.INPAINT_NS
        else:
            raise ValueError(f"Unsupported algorithm: {algorithm!r}")

    def set_radius(self, radius: int) -> None:
        if radius < 1:
            raise ValueError(f"radius must be >= 1, got {radius}")
        self.radius = radius

    # --- 主入口 ---

    def inpaint(
        self,
        frame: np.ndarray,
        mask: np.ndarray,
        boxes: Optional[List[Tuple[int, int, int, int]]] = None,
    ) -> np.ndarray:
        """
        修复单帧。

        Parameters
        ----------
        frame : BGR 图像 (H, W, 3)
        mask  : 二值掩码 (H, W)，1 = 待修复
        boxes : 水印包围盒列表 [(x, y, w, h), ...]
        """
        if self.static_background:
            return self._inpaint_static(frame, mask, boxes)
        return self._dispatch(frame, mask, boxes)

    # --- 静态背景优化 ---

    def _inpaint_static(
        self,
        frame: np.ndarray,
        mask: np.ndarray,
        boxes: Optional[List[Tuple[int, int, int, int]]],
    ) -> np.ndarray:
        """静态背景模式：只修复第一帧，后续帧直接贴回修复区域。"""
        if self._first_inpainted is None:
            self._first_inpainted = self._dispatch(frame, mask, boxes).copy()
            return self._first_inpainted

        result = frame.copy()
        m = mask.astype(bool)
        if np.any(m):
            result[m] = self._first_inpainted[m]
        return result

    # --- 引擎分发 ---

    def _dispatch(
        self,
        frame: np.ndarray,
        mask: np.ndarray,
        boxes: Optional[List[Tuple[int, int, int, int]]],
    ) -> np.ndarray:
        """根据 engine 设置选择修复后端。"""
        if self.engine == "opencv":
            return self._inpaint_opencv(frame, mask, boxes)

        device = "cuda" if self.engine == "lama_gpu" else "cpu"
        lama = _get_lama(device)

        # GPU 加载失败时尝试 CPU 降级
        if lama is None and device == "cuda":
            logger.warning("GPU LaMa unavailable, trying CPU fallback")
            lama = _get_lama("cpu")

        if lama is not None:
            return self._inpaint_lama(lama, frame, mask, boxes)

        # LaMa 完全不可用，降级 OpenCV
        logger.warning("LaMa unavailable on all devices; fallback to OpenCV")
        return self._inpaint_opencv(frame, mask, boxes)

    # ------------------------------------------------------------------
    # LaMa 修复
    # ------------------------------------------------------------------

    def _inpaint_lama(
        self,
        lama: _LamaWrapper,
        frame: np.ndarray,
        mask: np.ndarray,
        boxes: Optional[List[Tuple[int, int, int, int]]],
    ) -> np.ndarray:
        """
        使用 LaMa 逐区域修复。

        对每个 bounding box 裁出 ROI（含 context padding），
        pad 到 8 的倍数后送入模型，再贴回原图。
        """
        if not boxes:
            boxes = [(0, 0, frame.shape[1], frame.shape[0])]

        result = frame.copy()
        h, w = frame.shape[:2]
        pad = self.lama_context_pad

        for (bx, by, bw, bh) in boxes:
            # 扩展 ROI 以提供上下文
            x1 = max(0, bx - pad)
            y1 = max(0, by - pad)
            x2 = min(w, bx + bw + pad)
            y2 = min(h, by + bh + pad)

            roi_bgr = frame[y1:y2, x1:x2]
            roi_mask = mask[y1:y2, x1:x2]

            if not np.any(roi_mask):
                continue

            try:
                result = self._lama_inpaint_roi(
                    lama, result, roi_bgr, roi_mask, x1, y1, x2, y2
                )
            except _CudaOOMError:
                # GPU 显存不足：释放显存，降级到 CPU 处理当前 ROI
                logger.warning("CUDA OOM on ROI (%d,%d,%d,%d); retrying on CPU", x1, y1, x2, y2)
                cpu_lama = _get_lama("cpu")
                if cpu_lama is not None:
                    try:
                        result = self._lama_inpaint_roi(
                            cpu_lama, result, roi_bgr, roi_mask, x1, y1, x2, y2
                        )
                        continue
                    except Exception as e2:
                        logger.warning("CPU LaMa also failed: %s", e2)
                # 最终降级 OpenCV
                self._opencv_inpaint_roi(result, roi_bgr, roi_mask, x1, y1, x2, y2)

            except Exception as e:
                logger.warning("LaMa inpaint failed on ROI; fallback OpenCV: %s", e)
                self._opencv_inpaint_roi(result, roi_bgr, roi_mask, x1, y1, x2, y2)

        return result

    def _lama_inpaint_roi(
        self,
        lama: _LamaWrapper,
        canvas: np.ndarray,
        roi_bgr: np.ndarray,
        roi_mask: np.ndarray,
        x1: int, y1: int, x2: int, y2: int,
    ) -> np.ndarray:
        """
        对单个 ROI 执行 LaMa 修复并贴回 canvas。
        如果遇到 CUDA OOM 则抛出 _CudaOOMError。
        """
        try:
            # Pad 到 8 的倍数
            roi_padded, orig_h, orig_w = _pad_to_multiple(roi_bgr, 8)
            mask_255 = (roi_mask * 255).astype(np.uint8)
            mask_padded, _, _ = _pad_to_multiple(mask_255, 8)

            # BGR -> RGB
            roi_rgb = cv2.cvtColor(roi_padded, cv2.COLOR_BGR2RGB)

            # 调用模型（返回 RGB numpy）
            result_rgb = lama(roi_rgb, mask_padded)

            # 裁回原始 ROI 尺寸，RGB -> BGR
            result_rgb = result_rgb[:orig_h, :orig_w]
            result_bgr = cv2.cvtColor(result_rgb, cv2.COLOR_RGB2BGR)

            canvas[y1:y2, x1:x2] = result_bgr
            return canvas

        except Exception as e:
            # 检测 CUDA OOM
            err_msg = str(e).lower()
            if "out of memory" in err_msg or "cuda" in err_msg:
                self._try_free_gpu_memory()
                raise _CudaOOMError(str(e)) from e
            raise

    def _opencv_inpaint_roi(
        self,
        canvas: np.ndarray,
        roi_bgr: np.ndarray,
        roi_mask: np.ndarray,
        x1: int, y1: int, x2: int, y2: int,
    ) -> None:
        """对单个 ROI 使用 OpenCV 修复并贴回 canvas（原地修改）。"""
        try:
            fixed = cv2.inpaint(roi_bgr, roi_mask, self.radius, self.algorithm)
            canvas[y1:y2, x1:x2] = fixed
        except Exception:
            pass

    @staticmethod
    def _try_free_gpu_memory() -> None:
        """尝试释放 GPU 显存。"""
        try:
            import torch
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
                torch.cuda.synchronize()
        except Exception:
            pass

    # ------------------------------------------------------------------
    # OpenCV 修复
    # ------------------------------------------------------------------

    def _inpaint_opencv(
        self,
        frame: np.ndarray,
        mask: np.ndarray,
        boxes: Optional[List[Tuple[int, int, int, int]]],
    ) -> np.ndarray:
        """OpenCV 修复：逐 ROI 或全图。"""
        if not boxes:
            return cv2.inpaint(frame, mask, self.radius, self.algorithm)

        result = frame.copy()
        pad = self.radius + 2
        h, w = frame.shape[:2]

        for (bx, by, bw, bh) in boxes:
            x1 = max(0, bx - pad)
            y1 = max(0, by - pad)
            x2 = min(w, bx + bw + pad)
            y2 = min(h, by + bh + pad)

            roi = frame[y1:y2, x1:x2]
            roi_mask = mask[y1:y2, x1:x2]

            if not np.any(roi_mask):
                continue

            try:
                fixed = cv2.inpaint(roi, roi_mask, self.radius, self.algorithm)
                result[y1:y2, x1:x2] = fixed
            except Exception:
                pass

        return result


# ------------------------------------------------------------------
# 内部异常
# ------------------------------------------------------------------

class _CudaOOMError(RuntimeError):
    """GPU 显存不足时的内部异常，用于触发降级逻辑。"""
    pass
