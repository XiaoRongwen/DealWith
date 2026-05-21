<script setup lang="ts">
import { ref, watch } from 'vue'
import { useDebounceFn } from '@vueuse/core'
import type { PipelineConfig } from '../types'

const props = defineProps<{
  modelValue: Partial<PipelineConfig>
  showDetectionOptions?: boolean
  isImage?: boolean
}>()

const emit = defineEmits<{
  'update:modelValue': [config: Partial<PipelineConfig>]
}>()

const engine = ref(props.modelValue.inpaint_engine ?? 'lama_cpu')
const algorithm = ref(props.modelValue.inpaint_algorithm ?? 'telea')
const radius = ref(props.modelValue.inpaint_radius ?? 3)
const codec = ref(props.modelValue.output_codec ?? 'h264')
const threshold = ref(props.modelValue.detection_threshold ?? 0.3)
const sampleCount = ref(props.modelValue.sample_frame_count ?? 100)
const cornerScanW = ref(props.modelValue.corner_scan_w ?? 0.35)
const cornerScanH = ref(props.modelValue.corner_scan_h ?? 0.2)
const colorSat = ref(props.modelValue.color_sat_threshold ?? 60)
const colorVal = ref(props.modelValue.color_val_threshold ?? 170)
const lamaPad = ref(props.modelValue.lama_context_pad ?? 30)
const staticBg = ref(props.modelValue.static_background ?? false)
const outputBitrateStr = ref(
  props.modelValue.output_bitrate != null ? String(props.modelValue.output_bitrate) : ''
)

function emitUpdate() {
  const next: Partial<PipelineConfig> = {
    ...props.modelValue,
    inpaint_engine: engine.value,
    inpaint_algorithm: algorithm.value,
    inpaint_radius: radius.value,
    output_codec: codec.value,
    detection_threshold: threshold.value,
    sample_frame_count: sampleCount.value,
    corner_scan_w: cornerScanW.value,
    corner_scan_h: cornerScanH.value,
    color_sat_threshold: colorSat.value,
    color_val_threshold: colorVal.value,
    lama_context_pad: lamaPad.value,
    static_background: staticBg.value,
  }
  const raw = outputBitrateStr.value.trim()
  const br = Number.parseInt(raw, 10)
  if (raw !== '' && !Number.isNaN(br) && br > 0) next.output_bitrate = br
  else delete (next as { output_bitrate?: number }).output_bitrate
  emit('update:modelValue', next)
}

const emitDebounced = useDebounceFn(emitUpdate, 200)

watch([engine, algorithm, radius, codec, threshold, sampleCount, cornerScanW, cornerScanH, colorSat, colorVal, lamaPad, staticBg, outputBitrateStr], emitDebounced)
</script>

<template>
  <div class="space-y-2">

    <!-- 修复引擎 -->
    <section class="rounded-[18px] border border-blue-100/50 bg-blue-50/50 px-3 py-2.5">
      <h3 class="mb-2 text-xs font-semibold text-slate-500 uppercase tracking-wide">修复引擎</h3>

      <div class="space-y-1">
        <label
          v-for="item in [
            { val: 'lama_cpu', name: 'LaMa CPU', desc: '稳定' },
            { val: 'lama_gpu', name: 'LaMa GPU', desc: '更快' },
            { val: 'opencv', name: 'OpenCV', desc: '轻量' },
          ]"
          :key="item.val"
          class="flex cursor-pointer items-center gap-2 rounded-[10px] border px-2.5 py-1.5 transition-colors duration-150"
          :class="engine === item.val ? 'border-blue-200 bg-blue-50' : 'border-transparent bg-white/70 hover:bg-white'"
        >
          <input v-model="engine" type="radio" :value="item.val" class="accent-blue-600" />
          <span class="text-sm font-medium text-slate-900">{{ item.name }}</span>
          <span class="text-xs text-slate-400">{{ item.desc }}</span>
        </label>
      </div>

      <!-- OpenCV 选项 -->
      <template v-if="engine === 'opencv'">
        <div class="mt-2 space-y-2 rounded-[12px] border border-blue-100/50 bg-white/80 px-2.5 py-2">
          <div>
            <label class="text-xs font-medium text-slate-900">修复算法</label>
            <select v-model="algorithm" class="mt-1 w-full rounded-[10px] border border-blue-100/50 bg-white px-2.5 py-1.5 text-xs outline-none focus:border-blue-400">
              <option value="telea">Telea</option>
              <option value="navier_stokes">Navier-Stokes</option>
            </select>
          </div>
          <div class="flex items-center justify-between gap-3">
            <label class="text-xs font-medium text-slate-900">修复半径</label>
            <span class="text-xs text-blue-700">{{ radius }} px</span>
          </div>
          <input v-model.number="radius" type="range" min="1" max="20" class="w-full accent-blue-600" />
        </div>
      </template>

      <!-- LaMa 选项 -->
      <template v-if="engine.includes('lama')">
        <div class="mt-2 rounded-[12px] border border-blue-100/50 bg-white/80 px-2.5 py-2">
          <div class="flex items-center justify-between gap-3">
            <label class="text-xs font-medium text-slate-900">上下文边距</label>
            <span class="text-xs text-blue-700">{{ lamaPad }} px</span>
          </div>
          <input v-model.number="lamaPad" type="range" min="8" max="120" class="mt-1 w-full accent-blue-600" />
        </div>
      </template>

      <!-- 静态背景（仅视频） -->
      <label v-if="!props.isImage" class="mt-2 flex cursor-pointer items-center gap-2 rounded-[10px] border border-blue-100/50 bg-white/80 px-2.5 py-1.5">
        <input v-model="staticBg" type="checkbox" class="accent-blue-600" />
        <span class="text-sm font-medium text-slate-900">静态背景优化</span>
        <span class="text-xs text-slate-400">适合固定背景</span>
      </label>
    </section>

    <!-- 输出设置（仅视频） -->
    <section v-if="!props.isImage" class="rounded-[18px] border border-blue-100/50 bg-blue-50/50 px-3 py-2.5">
      <h3 class="mb-2 text-xs font-semibold text-slate-500 uppercase tracking-wide">输出设置</h3>

      <div class="flex gap-2">
        <label
          v-for="c in ['h264', 'h265']"
          :key="c"
          class="flex flex-1 cursor-pointer items-center justify-center gap-1.5 rounded-[10px] border px-3 py-1.5 transition-colors duration-150"
          :class="codec === c ? 'border-blue-200 bg-blue-50' : 'border-blue-100/50 bg-white/80 hover:bg-white'"
        >
          <input v-model="codec" type="radio" :value="c" class="hidden" />
          <span class="text-xs text-slate-400">Codec</span>
          <span class="text-sm font-semibold text-slate-900">{{ c.toUpperCase() }}</span>
        </label>
      </div>

      <div class="mt-2">
        <label class="text-xs font-medium text-slate-900">输出码率（kbps）</label>
        <input
          v-model="outputBitrateStr"
          class="mt-1 w-full rounded-[10px] border border-blue-100/50 bg-white/90 px-2.5 py-1.5 text-xs outline-none focus:border-blue-400"
          placeholder="例如 8000"
        />
      </div>
    </section>

    <!-- 检测设置 -->
    <section v-if="showDetectionOptions" class="rounded-[18px] border border-blue-100/50 bg-blue-50/50 px-3 py-2.5">
      <h3 class="mb-2 text-xs font-semibold text-slate-500 uppercase tracking-wide">检测设置</h3>

      <div class="space-y-2">
        <div>
          <div class="flex items-center justify-between text-xs">
            <label class="font-medium text-slate-900">采样帧数</label>
            <span class="text-blue-700">{{ sampleCount }}</span>
          </div>
          <input v-model.number="sampleCount" type="range" min="10" max="300" step="10" class="mt-1 w-full accent-blue-600" />
        </div>
        <div>
          <div class="flex items-center justify-between text-xs">
            <label class="font-medium text-slate-900">检测灵敏度</label>
            <span class="text-blue-700">{{ threshold.toFixed(2) }}</span>
          </div>
          <input v-model.number="threshold" type="range" min="0.01" max="1" step="0.01" class="mt-1 w-full accent-blue-600" />
        </div>

        <details class="rounded-[12px] border border-blue-100/50 bg-white/80 px-2.5 py-2">
          <summary class="cursor-pointer text-xs font-semibold text-slate-900">高级参数</summary>
          <div class="mt-2 grid gap-2 sm:grid-cols-2">
            <label v-for="(field, i) in [
              { label: '扫描宽度', model: 'cornerScanW', step: 0.05 },
              { label: '扫描高度', model: 'cornerScanH', step: 0.05 },
              { label: '饱和度阈值', model: 'colorSat', step: 1 },
              { label: '亮度阈值', model: 'colorVal', step: 1 },
            ]" :key="i" class="text-xs">
              <div class="mb-1 font-medium text-slate-900">{{ field.label }}</div>
              <input
                v-if="field.model === 'cornerScanW'" v-model.number="cornerScanW" type="number" :step="field.step"
                class="w-full rounded-[10px] border border-blue-100/50 bg-white/90 px-2.5 py-1.5 text-xs outline-none focus:border-blue-400"
              />
              <input
                v-else-if="field.model === 'cornerScanH'" v-model.number="cornerScanH" type="number" :step="field.step"
                class="w-full rounded-[10px] border border-blue-100/50 bg-white/90 px-2.5 py-1.5 text-xs outline-none focus:border-blue-400"
              />
              <input
                v-else-if="field.model === 'colorSat'" v-model.number="colorSat" type="number"
                class="w-full rounded-[10px] border border-blue-100/50 bg-white/90 px-2.5 py-1.5 text-xs outline-none focus:border-blue-400"
              />
              <input
                v-else-if="field.model === 'colorVal'" v-model.number="colorVal" type="number"
                class="w-full rounded-[10px] border border-blue-100/50 bg-white/90 px-2.5 py-1.5 text-xs outline-none focus:border-blue-400"
              />
            </label>
          </div>
        </details>
      </div>
    </section>

  </div>
</template>
