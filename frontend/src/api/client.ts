import axios from 'axios'
import type { UploadResponse, TaskStatus, ProcessRequest } from '../types'

const http = axios.create({ baseURL: '/api' })

// 响应拦截器：统一错误处理，将后端错误码转换为中文提示
http.interceptors.response.use(
  (res) => res,
  (error) => {
    const detail = error?.response?.data?.detail
    const status = error?.response?.status
    let message = '请求失败，请稍后重试'
    if (detail) {
      message = detail
    } else if (status === 413) {
      message = '文件大小超过 2GB 限制'
    } else if (status === 415) {
      message = '不支持的文件格式，请上传 MP4/AVI/MKV 视频或 JPG/PNG/WEBP/BMP 图片'
    } else if (status === 404) {
      message = '任务不存在或已过期'
    } else if (status === 410) {
      message = '下载链接已过期（超过24小时）'
    }
    return Promise.reject(new Error(message))
  }
)

export async function uploadVideo(file: File): Promise<UploadResponse> {
  const form = new FormData()
  form.append('file', file)
  const { data } = await http.post<UploadResponse>('/upload', form)
  return data
}

export async function startProcess(req: ProcessRequest): Promise<{ task_id: string; status: string }> {
  const { data } = await http.post<{ task_id: string; status: string }>('/process', req)
  return data
}

export async function getTaskStatus(taskId: string): Promise<TaskStatus> {
  const { data } = await http.get<TaskStatus>(`/status/${taskId}`)
  return data
}

export async function cancelTask(taskId: string): Promise<{ success: boolean }> {
  const { data } = await http.delete<{ success: boolean }>(`/task/${taskId}`)
  return data
}

export async function getDownloadUrl(taskId: string): Promise<string> {
  return `/api/download/${taskId}`
}
