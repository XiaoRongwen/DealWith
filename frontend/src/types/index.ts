export interface BoundingBox {
  x: number
  y: number
  w: number
  h: number
}

export interface VideoMetadata {
  duration: number
  fps: number
  total_frames: number
  width: number
  height: number
  codec: string
  bitrate: number
}

export interface ImageMetadata {
  width: number
  height: number
  format: string
  file_size: number
}

export type MediaMetadata = VideoMetadata | ImageMetadata

export function isVideoMetadata(m: MediaMetadata): m is VideoMetadata {
  return 'fps' in m
}

export interface ProgressEvent {
  task_id: string
  percent: number
  fps: number
  status: 'processing' | 'done' | 'error'
  message?: string
}

export interface TaskStatus {
  task_id: string
  status: string
  percent: number
  download_url?: string
  error?: string
}

export interface UploadResponse {
  task_id: string
  preview_frame_url: string
  source_video_url: string
  metadata: MediaMetadata
  media_type: 'video' | 'image'
}

export interface PipelineConfig {
  detection_mode: 'auto' | 'manual'
  manual_regions?: BoundingBox[]
  detection_threshold: number
  sample_frame_count: number
  /** 自动检测：角落扫描宽度占画面宽度比例，约 0.1~0.5 */
  corner_scan_w: number
  /** 自动检测：角落扫描高度占画面高度比例，约 0.1~0.4 */
  corner_scan_h: number
  /** 白色水印 HSV 饱和度上限（0~120） */
  color_sat_threshold: number
  /** 白色水印 HSV 亮度下限（100~255） */
  color_val_threshold: number
  inpaint_engine: 'lama_cpu' | 'lama_gpu' | 'opencv'
  inpaint_algorithm: 'telea' | 'navier_stokes'
  inpaint_radius: number
  /** LaMa 裁剪区域外扩像素 */
  lama_context_pad: number
  /** 静态水印：复用第一帧修复结果，更快；动态背景请关闭 */
  static_background: boolean
  use_gpu?: boolean
  output_codec: string
  output_bitrate?: number
}

export interface ProcessRequest {
  task_id: string
  mode: 'auto' | 'manual'
  manual_regions?: BoundingBox[]
  config?: Partial<PipelineConfig>
}
