<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, nextTick } from 'vue'
import type { BoundingBox } from '../types'

interface Props {
  previewFrameUrl: string
  sourceVideoUrl?: string
  frameWidth: number
  frameHeight: number
  maxRegions?: number
}

const props = withDefaults(defineProps<Props>(), { maxRegions: 10 })
const emit = defineEmits<{ 'update:regions': [regions: BoundingBox[]] }>()

// ── refs ───────────────────────────────────────────────────────────
const videoCanvasRef = ref<HTMLCanvasElement | null>(null)  // 视频模式专用 canvas
const imageCanvasRef = ref<HTMLCanvasElement | null>(null)  // 图片模式专用 canvas
const videoRef       = ref<HTMLVideoElement | null>(null)
const imageRef       = ref<HTMLImageElement | null>(null)

const regions       = ref<BoundingBox[]>([])
const selectedIndex = ref(-1)
const statusMsg     = ref('')
const statusType    = ref<'info' | 'warn' | 'error'>('info')
const playing       = ref(false)
const currentTime   = ref(0)
const duration      = ref(0)
const isSeeking     = ref(false)

const isVideo = computed(() => !!props.sourceVideoUrl)

let isDrawing = false
let sx = 0, sy = 0, cx = 0, cy = 0
let ro: ResizeObserver | null = null

// ── active canvas (根据模式选择) ───────────────────────────────────
const canvasRef = computed(() => isVideo.value ? videoCanvasRef.value : imageCanvasRef.value)

// ── toast ──────────────────────────────────────────────────────────
function toast(msg: string, type: 'info' | 'warn' | 'error' = 'info') {
  statusMsg.value = msg; statusType.value = type
  setTimeout(() => { statusMsg.value = '' }, 3000)
}

// ── 坐标转换 ───────────────────────────────────────────────────────
function getPos(e: MouseEvent) {
  const c = canvasRef.value!
  const r = c.getBoundingClientRect()
  return { x: e.clientX - r.left, y: e.clientY - r.top }
}
function toFrame(x: number, y: number) {
  const c = canvasRef.value!
  return {
    x: Math.round((x / c.width) * props.frameWidth),
    y: Math.round((y / c.height) * props.frameHeight),
  }
}
function toCanvas(fx: number, fy: number) {
  const c = canvasRef.value!
  return {
    x: (fx / props.frameWidth) * c.width,
    y: (fy / props.frameHeight) * c.height,
  }
}

// ── draw ───────────────────────────────────────────────────────────
function draw() {
  const c = canvasRef.value
  if (!c || c.width === 0 || c.height === 0) return
  const ctx = c.getContext('2d')!
  ctx.clearRect(0, 0, c.width, c.height)

  regions.value.forEach((r, i) => {
    const tl = toCanvas(r.x, r.y), br = toCanvas(r.x + r.w, r.y + r.h)
    const w = br.x - tl.x, h = br.y - tl.y
    const sel = i === selectedIndex.value
    ctx.fillStyle   = sel ? 'rgba(56,189,248,0.28)' : 'rgba(37,99,235,0.18)'
    ctx.strokeStyle = sel ? '#0ea5e9' : '#2563eb'
    ctx.lineWidth   = sel ? 2.5 : 1.5
    ctx.fillRect(tl.x, tl.y, w, h)
    ctx.strokeRect(tl.x, tl.y, w, h)
    ctx.fillStyle = sel ? '#0369a1' : '#1d4ed8'
    ctx.font = 'bold 13px Segoe UI'
    ctx.fillText(String(i + 1), tl.x + 6, tl.y + 16)
  })

  if (isDrawing) {
    const x = Math.min(sx, cx), y = Math.min(sy, cy)
    const w = Math.abs(cx - sx), h = Math.abs(cy - sy)
    ctx.fillStyle = 'rgba(37,99,235,0.14)'
    ctx.fillRect(x, y, w, h)
    ctx.strokeStyle = '#2563eb'; ctx.lineWidth = 2
    ctx.setLineDash([5, 3]); ctx.strokeRect(x, y, w, h); ctx.setLineDash([])
  }
}

// ── 视频模式：canvas 尺寸 = 视频实际渲染尺寸 ──────────────────────
// video 元素用 object-contain，实际渲染区域需要手动计算
function syncVideoCanvas() {
  const c = videoCanvasRef.value
  const v = videoRef.value
  if (!c || !v || !props.frameWidth || !props.frameHeight) return

  const containerW = v.clientWidth
  const containerH = v.clientHeight
  if (containerW === 0 || containerH === 0) return

  // object-contain 实际渲染尺寸
  const frameRatio = props.frameWidth / props.frameHeight
  const containerRatio = containerW / containerH
  let renderW: number, renderH: number
  if (frameRatio > containerRatio) {
    renderW = containerW
    renderH = Math.round(containerW / frameRatio)
  } else {
    renderH = containerH
    renderW = Math.round(containerH * frameRatio)
  }

  // canvas 精确覆盖视频渲染区域，居中定位
  const offsetX = Math.round((containerW - renderW) / 2)
  const offsetY = Math.round((containerH - renderH) / 2)

  c.style.left   = `${offsetX}px`
  c.style.top    = `${offsetY}px`
  c.style.width  = `${renderW}px`
  c.style.height = `${renderH}px`

  if (c.width !== renderW || c.height !== renderH) {
    c.width  = renderW
    c.height = renderH
  }
  draw()
}

// ── 图片模式：canvas 尺寸 = img 实际渲染尺寸 ──────────────────────
function syncImageCanvas() {
  const c = imageCanvasRef.value
  const img = imageRef.value
  if (!c || !img) return

  // img 用 max-h / w-auto，getBoundingClientRect 拿到实际渲染尺寸
  const rect = img.getBoundingClientRect()
  const w = Math.round(rect.width)
  const h = Math.round(rect.height)
  if (w === 0 || h === 0) return

  c.style.width  = `${w}px`
  c.style.height = `${h}px`
  if (c.width !== w || c.height !== h) {
    c.width  = w
    c.height = h
  }
  draw()
}

function syncSize() {
  if (isVideo.value) syncVideoCanvas()
  else syncImageCanvas()
}

// ── 视频事件 ───────────────────────────────────────────────────────
function readDuration() {
  const v = videoRef.value; if (!v) return
  let d = v.duration
  if (!Number.isFinite(d) && v.seekable.length > 0) d = v.seekable.end(v.seekable.length - 1)
  if (Number.isFinite(d) && d > 0) duration.value = d
}
function onLoadedMetadata() { readDuration(); nextTick(syncVideoCanvas) }
function onDurationChange()  { readDuration() }
function onTimeUpdate()      { if (!isSeeking.value) currentTime.value = videoRef.value?.currentTime ?? 0 }

// ── 图片事件 ───────────────────────────────────────────────────────
function onImageLoad() { nextTick(syncImageCanvas) }

// ── 时间轴 ─────────────────────────────────────────────────────────
function formatSec(s: number) {
  const t = Math.max(0, Math.floor(s || 0))
  return `${String(Math.floor(t / 60)).padStart(2, '0')}:${String(t % 60).padStart(2, '0')}`
}
function togglePlay() {
  const v = videoRef.value; if (!v) return
  v.paused ? (v.play().catch(() => {}), playing.value = true) : (v.pause(), playing.value = false)
}
function onSliderInput(e: Event) {
  const val = +(e.target as HTMLInputElement).value
  isSeeking.value = true; currentTime.value = val
  if (videoRef.value) videoRef.value.currentTime = val
}
function onSliderChange(e: Event) {
  const val = +(e.target as HTMLInputElement).value
  if (videoRef.value) videoRef.value.currentTime = val
  isSeeking.value = false
}

// ── 鼠标交互 ───────────────────────────────────────────────────────
function hitTest(x: number, y: number) {
  for (let i = regions.value.length - 1; i >= 0; i--) {
    const r = regions.value[i]
    const tl = toCanvas(r.x, r.y), br = toCanvas(r.x + r.w, r.y + r.h)
    if (x >= tl.x && x <= br.x && y >= tl.y && y <= br.y) return i
  }
  return -1
}
function onMouseDown(e: MouseEvent) {
  const p = getPos(e), hit = hitTest(p.x, p.y)
  if (hit !== -1) { selectedIndex.value = hit; draw(); return }
  selectedIndex.value = -1
  if (regions.value.length >= props.maxRegions) { toast(`最多 ${props.maxRegions} 个区域`, 'warn'); return }
  isDrawing = true; sx = p.x; sy = p.y; cx = p.x; cy = p.y
}
function onMouseMove(e: MouseEvent) {
  if (!isDrawing) return
  const p = getPos(e); cx = p.x; cy = p.y; draw()
}
function onMouseUp(e: MouseEvent) {
  if (!isDrawing) return
  isDrawing = false; const p = getPos(e); cx = p.x; cy = p.y
  if (Math.abs(cx - sx) < 4 || Math.abs(cy - sy) < 4) { draw(); return }
  const f1 = toFrame(Math.min(sx, cx), Math.min(sy, cy))
  const f2 = toFrame(Math.max(sx, cx), Math.max(sy, cy))
  const box: BoundingBox = {
    x: Math.max(0, f1.x), y: Math.max(0, f1.y),
    w: Math.min(f2.x - f1.x, props.frameWidth - Math.max(0, f1.x)),
    h: Math.min(f2.y - f1.y, props.frameHeight - Math.max(0, f1.y)),
  }
  if (box.w > 0 && box.h > 0) { regions.value.push(box); emit('update:regions', [...regions.value]) }
  draw()
}
function onKeyDown(e: KeyboardEvent) {
  if (e.key === 'Delete' && selectedIndex.value !== -1) deleteSelected()
}
function deleteSelected() {
  if (selectedIndex.value === -1) return
  regions.value.splice(selectedIndex.value, 1); selectedIndex.value = -1
  emit('update:regions', [...regions.value]); draw()
}
function clearAll() {
  regions.value = []; selectedIndex.value = -1; emit('update:regions', []); draw()
}

// ── lifecycle ──────────────────────────────────────────────────────
onMounted(() => {
  globalThis.addEventListener('keydown', onKeyDown)
  nextTick(() => {
    ro = new ResizeObserver(syncSize)
    const target = isVideo.value ? videoRef.value : imageRef.value
    if (target) ro.observe(target)
    syncSize()
  })
})
onUnmounted(() => { globalThis.removeEventListener('keydown', onKeyDown); ro?.disconnect() })
</script>

<template>
  <div class="space-y-4">

    <!-- ══ 视频模式 ══════════════════════════════════════════════════ -->
    <div v-if="isVideo" class="relative overflow-hidden rounded-[28px] border border-blue-100/50 bg-black shadow-sm" style="max-height: 52vh;">
      <video
        ref="videoRef"
        class="block w-full"
        style="max-height: 52vh; object-fit: contain;"
        :src="sourceVideoUrl"
        preload="auto"
        @loadedmetadata="onLoadedMetadata"
        @durationchange="onDurationChange"
        @timeupdate="onTimeUpdate"
        @play="playing = true"
        @pause="playing = false"
      />
      <!-- canvas 通过 syncVideoCanvas 精确定位到视频渲染区域 -->
      <canvas
        ref="videoCanvasRef"
        class="absolute cursor-crosshair select-none"
        style="top: 0; left: 0;"
        @mousedown="onMouseDown"
        @mousemove="onMouseMove"
        @mouseup="onMouseUp"
        @mouseleave="onMouseUp"
      />
    </div>

    <!-- ══ 图片模式 ══════════════════════════════════════════════════ -->
    <div v-else class="relative flex justify-center rounded-[28px] border border-blue-100/50 bg-sky-50 shadow-sm">
      <div class="relative inline-block">
        <img
          ref="imageRef"
          :src="previewFrameUrl"
          class="block w-auto max-w-full"
          style="max-height: 52vh; display: block;"
          alt="预览图"
          draggable="false"
          @load="onImageLoad"
        />
        <!-- canvas 通过 syncImageCanvas 精确覆盖 img 渲染区域 -->
        <canvas
          ref="imageCanvasRef"
          class="absolute cursor-crosshair select-none"
          style="top: 0; left: 0;"
          @mousedown="onMouseDown"
          @mousemove="onMouseMove"
          @mouseup="onMouseUp"
          @mouseleave="onMouseUp"
        />
      </div>
    </div>

    <!-- ══ 控制栏 ═════════════════════════════════════════════════════ -->
    <div class="flex flex-wrap items-center gap-2 rounded-[20px] border border-blue-100/50 bg-white/85 px-3 py-2">
      <button
        v-if="isVideo"
        class="inline-flex items-center justify-center rounded-full border border-blue-200 bg-white px-3 py-1 text-xs font-semibold text-blue-700 shadow-sm transition-colors hover:bg-blue-50"
        @click="togglePlay"
      >{{ playing ? '暂停' : '播放' }}</button>

      <template v-if="isVideo">
        <input
          class="h-1.5 min-w-[80px] flex-1 appearance-none rounded-full bg-slate-200 accent-blue-600"
          type="range" min="0" :max="duration" :step="0.1" :value="currentTime"
          @input="onSliderInput" @change="onSliderChange"
        />
        <span class="text-xs text-slate-400 tabular-nums">{{ formatSec(currentTime) }}/{{ formatSec(duration) }}</span>
      </template>

      <span class="text-xs text-slate-400 mr-auto">{{ regions.length }}/{{ maxRegions }}</span>

      <span
        v-if="statusMsg"
        class="rounded-full px-2 py-0.5 text-xs"
        :class="{ 'bg-sky-100 text-sky-700': statusType === 'info', 'bg-amber-100 text-amber-700': statusType === 'warn', 'bg-rose-100 text-rose-700': statusType === 'error' }"
      >{{ statusMsg }}</span>

      <button
        class="inline-flex items-center justify-center rounded-full bg-red-500 px-3 py-1 text-xs font-semibold text-white shadow-sm transition-colors hover:bg-red-600 disabled:opacity-40"
        :disabled="selectedIndex === -1"
        @click="deleteSelected"
      >删除</button>
      <button
        class="inline-flex items-center justify-center rounded-full border border-blue-200 bg-white px-3 py-1 text-xs font-semibold text-blue-700 shadow-sm transition-colors hover:bg-blue-50"
        @click="clearAll"
      >清空</button>
    </div>

  </div>
</template>
