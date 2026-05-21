<template>
  <ToolLayout title="参数设置" description="预览和参数对齐显示。" current-step="process" compact>
    <template v-if="uploadResponse">
      <!-- 左右等高布局 -->
      <div class="grid gap-3 xl:grid-cols-[minmax(0,1fr)_380px]">

        <!-- 左侧：预览卡片 -->
        <section class="flex flex-col rounded-[24px] border border-blue-100 bg-white/88 p-4 shadow-[0_30px_80px_rgba(37,99,235,0.14)] backdrop-blur-[18px]">

          <!-- 标题行 -->
          <div class="mb-3 flex items-center gap-2">
            <h2 class="text-sm font-semibold text-slate-700">
              {{ mode === 'manual' ? '水印区域' : '预览画面' }}
            </h2>
            <button
              class="ml-auto text-xs text-slate-400 transition-colors hover:text-blue-600"
              @click="router.push('/upload')"
            >重新上传</button>
          </div>

          <!-- 手动框选 -->
          <div v-if="mode === 'manual'" class="flex-1">
            <ManualMaskInput
              :preview-frame-url="uploadResponse.preview_frame_url"
              :source-video-url="isVideo ? uploadResponse.source_video_url : undefined"
              :frame-width="uploadResponse.metadata.width"
              :frame-height="uploadResponse.metadata.height"
              @update:regions="onManualRegionsChange"
            />
          </div>

          <!-- 自动检测预览 -->
          <div v-else class="flex flex-1 flex-col gap-3">
            <div class="overflow-hidden rounded-[18px] border border-blue-100/50 bg-sky-50">
              <img
                :src="uploadResponse.preview_frame_url"
                :alt="isVideo ? '视频预览帧' : '图片预览'"
                class="w-full object-contain"
                :style="{ maxHeight: '52vh' }"
              />
            </div>
            <div class="rounded-[14px] bg-blue-50/60 px-3 py-2 text-xs text-slate-500">
              {{ isVideo ? '自动检测模式将扫描视频帧，自动识别水印位置，无需手动框选。' : '自动检测模式将扫描图片角落，自动识别水印位置，无需手动框选。' }}
            </div>
          </div>

          <!-- 媒体信息条 -->
          <div class="mt-3 grid gap-2" :class="isVideo ? 'grid-cols-4' : 'grid-cols-2'">
            <template v-if="isVideo">
              <div
                v-for="(item, i) in [
                  { label: '分辨率', value: `${uploadResponse.metadata.width} × ${uploadResponse.metadata.height}` },
                  { label: '时长', value: formatDuration((uploadResponse.metadata as any).duration) },
                  { label: '帧率', value: `${(uploadResponse.metadata as any).fps} fps` },
                  { label: '编码', value: (uploadResponse.metadata as any).codec },
                ]"
                :key="i"
                class="rounded-[12px] border border-blue-100/40 bg-white/70 px-2.5 py-2"
              >
                <div class="text-[10px] text-slate-400">{{ item.label }}</div>
                <div class="mt-0.5 text-xs font-semibold text-slate-800">{{ item.value }}</div>
              </div>
            </template>
            <template v-else>
              <div
                v-for="(item, i) in [
                  { label: '分辨率', value: `${uploadResponse.metadata.width} × ${uploadResponse.metadata.height}` },
                  { label: '格式', value: (uploadResponse.metadata as any).format },
                ]"
                :key="i"
                class="rounded-[12px] border border-blue-100/40 bg-white/70 px-2.5 py-2"
              >
                <div class="text-[10px] text-slate-400">{{ item.label }}</div>
                <div class="mt-0.5 text-xs font-semibold text-slate-800">{{ item.value }}</div>
              </div>
            </template>
          </div>
        </section>

        <!-- 右侧：参数卡片，与左侧等高 -->
        <aside class="flex flex-col rounded-[24px] border border-blue-100 bg-white/88 p-4 shadow-[0_30px_80px_rgba(37,99,235,0.14)] backdrop-blur-[18px] xl:sticky xl:top-24">
          <div class="mb-3 flex items-center justify-between">
            <h2 class="text-sm font-semibold text-slate-700">处理参数</h2>
            <!-- 模式切换 -->
            <div class="flex rounded-full border border-blue-100 bg-blue-50/60 p-0.5">
              <button
                type="button"
                class="rounded-full px-3 py-1 text-xs font-medium transition-all duration-150"
                :class="mode === 'manual' ? 'bg-white text-blue-600 shadow-sm ring-1 ring-blue-100' : 'text-slate-400 hover:text-slate-600'"
                @click="mode = 'manual'"
              >手动框选</button>
              <button
                type="button"
                class="rounded-full px-3 py-1 text-xs font-medium transition-all duration-150"
                :class="mode === 'auto' ? 'bg-white text-blue-600 shadow-sm ring-1 ring-blue-100' : 'text-slate-400 hover:text-slate-600'"
                @click="mode = 'auto'"
              >自动检测</button>
            </div>
          </div>

          <!-- 参数内容，flex-1 撑满剩余高度 -->
          <div class="flex-1 overflow-y-auto">
            <InpaintConfig v-model="config" :show-detection-options="mode === 'auto'" :is-image="!isVideo" />
          </div>

          <!-- 底部操作区 -->
          <div class="mt-3 space-y-2">
            <button
              class="inline-flex w-full items-center justify-center gap-2 rounded-full bg-blue-600 px-4 py-2 text-sm font-semibold text-white shadow-sm transition-colors duration-200 hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-50"
              :disabled="starting"
              @click="mode === 'manual' ? submitManual() : submitAuto()"
            >{{ starting ? '正在启动处理...' : '开始处理' }}</button>

            <p v-if="error" class="rounded-[12px] border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-600">
              {{ error }}
            </p>
          </div>
        </aside>

      </div>
    </template>
  </ToolLayout>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from "vue";
import { useRouter } from "vue-router";
import ManualMaskInput from "../components/ManualMaskInput.vue";
import InpaintConfig from "../components/InpaintConfig.vue";
import ToolLayout from "../components/ToolLayout.vue";
import { startProcess } from "../api/client";
import type { UploadResponse, BoundingBox, PipelineConfig } from "../types";

const router = useRouter();
const mode = ref<"manual" | "auto">("manual");
const error = ref("");
const starting = ref(false);
const uploadResponse = ref<UploadResponse | null>(null);

const isVideo = computed(() => uploadResponse.value?.media_type === 'video');

const config = ref<Partial<PipelineConfig>>({
  inpaint_engine: "lama_cpu",
  inpaint_algorithm: "telea",
  inpaint_radius: 3,
  output_codec: "h264",
  detection_threshold: 0.3,
  sample_frame_count: 100,
  corner_scan_w: 0.35,
  corner_scan_h: 0.2,
  color_sat_threshold: 60,
  color_val_threshold: 170,
  lama_context_pad: 30,
  static_background: false,
});

const pendingRegions = ref<BoundingBox[]>([]);

onMounted(() => {
  const state = (history.state as { uploadResponse?: UploadResponse })?.uploadResponse;
  if (!state) { router.replace("/upload"); return; }
  uploadResponse.value = state;
});

function onManualRegionsChange(regions: BoundingBox[]) { pendingRegions.value = regions; }

function formatDuration(seconds: number): string {
  const m = Math.floor(seconds / 60).toString().padStart(2, "0");
  const s = Math.floor(seconds % 60).toString().padStart(2, "0");
  return `${m}:${s}`;
}

async function submitManual() {
  if (!uploadResponse.value) return;
  if (pendingRegions.value.length === 0) { error.value = "请先框选水印区域。"; return; }
  error.value = "";
  starting.value = true;
  try {
    await startProcess({ task_id: uploadResponse.value.task_id, mode: "manual", manual_regions: pendingRegions.value, config: { ...config.value, detection_mode: "manual" } });
    router.push(`/progress/${uploadResponse.value.task_id}`);
  } catch (e: unknown) {
    error.value = e instanceof Error ? e.message : "启动处理失败，请稍后重试。";
  } finally { starting.value = false; }
}

async function submitAuto() {
  if (!uploadResponse.value) return;
  error.value = "";
  starting.value = true;
  try {
    await startProcess({ task_id: uploadResponse.value.task_id, mode: "auto", config: { ...config.value, detection_mode: "auto" } });
    router.push(`/progress/${uploadResponse.value.task_id}`);
  } catch (e: unknown) {
    error.value = e instanceof Error ? e.message : "启动处理失败，请稍后重试。";
  } finally { starting.value = false; }
}
</script>
