"""
视频解码模块：基于 OpenCV 提供打开、读帧、跳转和资源管理能力。
"""
from __future__ import annotations

import os
import struct
from typing import Optional

import cv2
import numpy as np

from backend.app.models.schemas import VideoMetadata


class VideoDecoder:
    """OpenCV-based video decoder."""

    def __init__(self) -> None:
        self._cap: Optional[cv2.VideoCapture] = None
        self._metadata: Optional[VideoMetadata] = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def open(self, file_path: str) -> VideoMetadata:
        """Open a video file and return its metadata.

        Raises:
            FileNotFoundError: if the file does not exist.
            ValueError: if the file format is unsupported or the file is corrupt.
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Video file not found: {file_path}")

        cap = cv2.VideoCapture(file_path)
        if not cap.isOpened():
            raise ValueError(f"Cannot open video file (unsupported format or corrupt): {file_path}")

        fps = cap.get(cv2.CAP_PROP_FPS) or 0.0
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

        if fps <= 0 or width <= 0 or height <= 0:
            cap.release()
            raise ValueError(f"Video file appears to be corrupt or has invalid properties: {file_path}")

        duration = total_frames / fps if fps > 0 else 0.0

        # Codec: decode the FOURCC integer into a 4-character string
        fourcc_int = int(cap.get(cv2.CAP_PROP_FOURCC))
        codec = "".join(chr((fourcc_int >> (8 * i)) & 0xFF) for i in range(4)).strip("\x00")

        # Bitrate: OpenCV doesn't expose it directly, so we estimate
        bitrate = int(fps * width * height * 3 * 8 / 1000)

        # Release any previously opened capture
        if self._cap is not None:
            self._cap.release()

        self._cap = cap
        self._metadata = VideoMetadata(
            duration=duration,
            fps=fps,
            total_frames=total_frames,
            width=width,
            height=height,
            codec=codec,
            bitrate=bitrate,
        )
        return self._metadata

    def next_frame(self) -> Optional[np.ndarray]:
        """Read the next frame.

        Returns:
            BGR numpy array, or None when the video has ended.
        """
        if self._cap is None:
            return None
        ret, frame = self._cap.read()
        if not ret:
            return None
        return frame

    def seek(self, timestamp: float) -> None:
        """Seek to the given timestamp (seconds)."""
        if self._cap is None:
            return
        if self._metadata is not None and self._metadata.fps > 0:
            frame_index = int(timestamp * self._metadata.fps)
            self._cap.set(cv2.CAP_PROP_POS_FRAMES, frame_index)
        else:
            self._cap.set(cv2.CAP_PROP_POS_MSEC, timestamp * 1000)

    def close(self) -> None:
        """Release the underlying VideoCapture resource."""
        if self._cap is not None:
            self._cap.release()
            self._cap = None

    # ------------------------------------------------------------------
    # Context manager support
    # ------------------------------------------------------------------

    def __enter__(self) -> "VideoDecoder":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()
