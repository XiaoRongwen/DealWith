<template>
  <ToolLayout title="处理中" description="实时查看进度。" current-step="progress" compact>
    <div class="mx-auto max-w-4xl space-y-5">
      <section class="rounded-[28px] border border-blue-100 bg-white/88 p-6 shadow-[0_30px_80px_rgba(37,99,235,0.14)] backdrop-blur-[18px] sm:p-8">

        <template v-if="status !== 'error'">
          <div class="space-y-5">
            <div class="flex items-center justify-between gap-4">
              <h2 class="text-2xl font-semibold text-slate-900">任务执行中</h2>
              <div class="rounded-full bg-blue-50 px-4 py-1.5 text-xs font-semibold text-blue-700">
                {{ percent >= 100 ? '即将完成' : '处理中' }}
              </div>
            </div>

            <div class="rounded-[24px] border border-blue-100/50 bg-white/85 p-5">
              <div class="mb-3 flex items-center justify-between gap-4">
                <span class="text-sm font-semibold text-slate-900">总体进度</span>
                <span class="text-2xl font-semibold text-slate-900">{{ percent.toFixed(1) }}%</span>
              </div>
              <div class="h-4 overflow-hidden rounded-full bg-slate-100">
                <div
                  class="h-full rounded-full bg-gradient-to-r from-blue-600 to-sky-400 transition-all duration-300"
                  :style="{ width: `${percent}%` }"
                />
              </div>
            </div>

            <div class="grid gap-4 sm:grid-cols-3">
              <div
                v-for="(item, i) in [
                  { label: '进度', value: `${percent.toFixed(1)}%` },
                  { label: '处理帧率', value: fps > 0 ? `${fps.toFixed(1)} fps` : '计算中...' },
                  { label: '预计剩余', value: remainingTime },
                ]"
                :key="i"
                class="rounded-[18px] border border-blue-100/50 bg-white/90 px-4 py-4"
              >
                <div class="text-xs text-slate-400">{{ item.label }}</div>
                <div class="mt-2 text-xl font-semibold text-slate-900">{{ item.value }}</div>
              </div>
            </div>

            <div class="flex flex-wrap gap-3">
              <button
                class="inline-flex items-center justify-center gap-2 rounded-full border border-blue-200 bg-white px-4 py-1.5 text-sm font-semibold text-blue-700 shadow-sm transition-colors duration-200 hover:bg-blue-50 disabled:cursor-not-allowed disabled:opacity-50"
                @click="router.push('/upload')"
              >重新上传视频</button>
              <button
                class="inline-flex items-center justify-center gap-2 rounded-full bg-red-600 px-4 py-1.5 text-sm font-semibold text-white shadow-sm transition-colors duration-200 hover:bg-red-700 disabled:cursor-not-allowed disabled:opacity-50"
                @click="handleCancel"
              >取消任务</button>
            </div>
          </div>
        </template>

        <template v-else>
          <div class="space-y-4 rounded-[24px] border border-red-200 bg-red-50 p-6">
            <h2 class="text-2xl font-semibold text-slate-900">处理失败</h2>
            <p class="text-sm leading-7 text-red-600">{{ errorMsg }}</p>
            <button
              class="inline-flex items-center justify-center gap-2 rounded-full border border-blue-200 bg-white px-4 py-1.5 text-sm font-semibold text-blue-700 shadow-sm transition-colors duration-200 hover:bg-blue-50"
              @click="handleRetry"
            >返回重新上传</button>
          </div>
        </template>

      </section>
    </div>
  </ToolLayout>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import ToolLayout from '../components/ToolLayout.vue'
import { cancelTask, getTaskStatus } from '../api/client'

const route = useRoute()
const router = useRouter()
const taskId = computed(() => route.params.taskId as string)

const percent = ref(0)
const fps = ref(0)
const totalFrames = ref(0)
const errorMsg = ref('')
const status = ref<'processing' | 'done' | 'error' | 'idle'>('idle')

let ws: WebSocket | null = null
let retryCount = 0
const MAX_RETRIES = 5
const RETRY_DELAY = 2000
let retryTimer: ReturnType<typeof setTimeout> | null = null

const remainingTime = computed(() => {
  if (fps.value <= 0) return '计算中...'
  const remaining = totalFrames.value * (1 - percent.value / 100)
  const seconds = Math.ceil(remaining / fps.value)
  if (seconds < 60) return `${seconds} 秒`
  const m = Math.floor(seconds / 60)
  const s = seconds % 60
  return `${m} 分 ${s} 秒`
})

function connect() {
  const wsProtocol = location.protocol === 'https:' ? 'wss:' : 'ws:'
  ws = new WebSocket(`${wsProtocol}//${location.host}/ws/progress/${taskId.value}`)
  ws.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data)
      if (data.percent !== undefined) percent.value = data.percent
      if (data.fps !== undefined) fps.value = data.fps
      if (data.total_frames !== undefined) totalFrames.value = data.total_frames
      if (data.status) status.value = data.status
      if (data.status === 'done') router.push(`/download/${taskId.value}`)
      else if (data.status === 'error') errorMsg.value = data.message || '处理任务出错，请稍后重试。'
    } catch { /* ignore */ }
  }
  ws.onclose = () => {
    if (status.value === 'done' || status.value === 'error') return
    if (retryCount < MAX_RETRIES) {
      retryCount++
      retryTimer = setTimeout(async () => {
        try {
          const s = await getTaskStatus(taskId.value)
          if (s.percent !== undefined) percent.value = s.percent
          if (s.status === 'done') { router.push(`/download/${taskId.value}`); return }
          if (s.status === 'error') { errorMsg.value = s.error || '处理任务出错，请稍后重试。'; status.value = 'error'; return }
        } catch { /* ignore */ }
        connect()
      }, RETRY_DELAY)
    }
  }
  ws.onerror = () => ws?.close()
}

async function handleCancel() {
  await cancelTask(taskId.value)
  status.value = 'error'
  errorMsg.value = '任务已取消。'
}

function handleRetry() { window.location.href = '/' }

onMounted(() => connect())
onUnmounted(() => { if (retryTimer) clearTimeout(retryTimer); ws?.close() })
</script>
