"""
视频编码模块：基于 imageio-ffmpeg 启动 FFmpeg 子进程编码输出视频。
"""
from __future__ import annotations

import subprocess
from typing import Optional

import imageio_ffmpeg
import numpy as np

from backend.app.models.schemas import VideoMetadata  # noqa: F401 (optional type hint)

# 使用 imageio-ffmpeg 内置的 FFmpeg 二进制，无需系统安装
_FFMPEG_BIN = imageio_ffmpeg.get_ffmpeg_exe()


class VideoEncoder:
    """将修复后的帧序列通过 FFmpeg 编码为目标视频格式。"""

    CODEC_MAP = {
        "h264": "libx264",
        "h265": "libx265",
    }

    def __init__(self) -> None:
        self._process: Optional[subprocess.Popen] = None
        self._output_path: Optional[str] = None

    # ------------------------------------------------------------------
    # Context manager support
    # ------------------------------------------------------------------

    def __enter__(self) -> "VideoEncoder":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def open(
        self,
        output_path: str,
        codec: str,
        fps: float,
        width: int,
        height: int,
        bitrate: Optional[int] = None,
        audio_source: Optional[str] = None,
    ) -> None:
        """启动 FFmpeg 进程，准备接收原始帧数据。

        Args:
            output_path: 输出视频文件路径。
            codec: 目标编码器名称（"h264"、"h265" 或 FFmpeg 原生名称）。
            fps: 帧率。
            width: 帧宽度（像素）。
            height: 帧高度（像素）。
            bitrate: 目标码率（kbps），None 表示不指定。
            audio_source: 音频源文件路径，None 表示无音频。

        Raises:
            RuntimeError: FFmpeg 进程启动失败。
        """
        vcodec = self.CODEC_MAP.get(codec, codec)

        cmd = [
            _FFMPEG_BIN, "-y",
            "-f", "rawvideo",
            "-vcodec", "rawvideo",
            "-pix_fmt", "bgr24",
            "-s", f"{width}x{height}",
            "-r", str(fps),
            "-i", "pipe:0",
        ]

        if audio_source:
            cmd += ["-i", audio_source, "-c:a", "copy"]

        cmd += ["-vcodec", vcodec, "-pix_fmt", "yuv420p", "-movflags", "+faststart"]

        if bitrate is not None:
            cmd += ["-b:v", f"{bitrate}k"]

        cmd.append(output_path)

        try:
            self._process = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,  # 避免 stderr 管道缓冲区满导致 FFmpeg 阻塞
            )
        except (FileNotFoundError, OSError) as exc:
            raise RuntimeError(f"Failed to start FFmpeg: {exc}") from exc

        self._output_path = output_path

    def write_frame(self, frame: np.ndarray) -> None:
        """将一帧 BGR numpy 数组写入 FFmpeg stdin。

        Args:
            frame: BGR 格式的 numpy 数组。

        Raises:
            RuntimeError: 进程未启动，或写入失败（磁盘满/权限不足）。
        """
        if self._process is None or self._process.stdin is None:
            raise RuntimeError("Encoder is not open. Call open() first.")

        try:
            self._process.stdin.write(frame.tobytes())
        except (BrokenPipeError, OSError) as exc:
            raise RuntimeError("Write failed: disk full or permission denied") from exc

    def finalize(self) -> str:
        """关闭 stdin，等待 FFmpeg 完成编码，返回输出文件路径。

        Returns:
            输出视频文件路径。

        Raises:
            RuntimeError: 编码器未启动，或 FFmpeg 返回非零退出码。
        """
        if self._process is None:
            raise RuntimeError("Encoder is not open. Call open() first.")

        if self._process.stdin is not None:
            self._process.stdin.close()

        returncode = self._process.wait()

        if returncode != 0:
            # 重新运行一次获取错误信息（stderr 之前被丢弃）
            raise RuntimeError(
                f"FFmpeg exited with code {returncode}"
            )

        return self._output_path  # type: ignore[return-value]

    def close(self) -> None:
        """强制终止 FFmpeg 进程（如果仍在运行），清理资源。"""
        if self._process is None:
            return

        # Close stdin gracefully first
        try:
            if self._process.stdin is not None:
                self._process.stdin.close()
        except OSError:
            pass

        # Terminate if still running
        if self._process.poll() is None:
            self._process.terminate()
            try:
                self._process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._process.kill()
                self._process.wait()

        self._process = None
