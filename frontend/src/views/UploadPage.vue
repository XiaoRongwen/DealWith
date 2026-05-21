<template>
  <ToolLayout title="上传视频" description="先上传源视频，再进入参数设置。" current-step="upload" compact>
    <div class="grid gap-5 sm:grid-cols-[1.45fr_0.55fr]">

      <section class="rounded-[28px] border border-blue-100 bg-white/88 p-2 shadow-[0_30px_80px_rgba(37,99,235,0.14)] backdrop-blur-[18px] sm:p-6">
        <div
          class="relative flex h-100 items-center justify-center overflow-hidden rounded-[24px] border border-dashed p-1 text-center transition-all duration-300"
          :class="isDragging
            ? 'border-blue-500 bg-blue-50'
            : 'border-blue-200 bg-white/78 hover:border-blue-300 hover:bg-white'"
          @dragover.prevent="isDragging = true"
          @dragleave.prevent="isDragging = false"
          @drop.prevent="onDrop"
          @click="fileInput?.click()"
        >
          <input ref="fileInput" type="file" accept=".mp4,.avi,.mkv,.jpg,.jpeg,.png,.webp,.bmp" class="hidden" @change="onFileChange" />

          <template v-if="!uploading && !result">
            <div class="space-y-4 py-8">
              <div class="mx-auto flex h-16 w-16 items-center justify-center rounded-[20px] bg-blue-100 text-2xl text-blue-700">
                上传
              </div>
              <div class="space-y-2">
                <p class="text-lg font-semibold text-slate-900">拖拽文件到这里，或点击选择文件</p>
                <p class="text-sm text-slate-400">视频：MP4 / AVI / MKV &nbsp;|&nbsp; 图片：JPG / PNG / WEBP / BMP</p>
              </div>
            </div>
          </template>

          <template v-if="uploading">
            <div class="mx-auto max-w-md space-y-4 py-8" @click.stop>
              <div class="mx-auto h-14 w-14 animate-pulse rounded-full bg-blue-100" />
              <p class="text-lg font-semibold text-slate-900">正在上传</p>
              <div class="h-3 overflow-hidden rounded-full bg-slate-100">
                <div
                  class="h-full rounded-full bg-gradient-to-r from-blue-600 to-sky-400 transition-all duration-300"
                  :style="{ width: `${progress}%` }"
                />
              </div>
              <p class="text-sm text-slate-400">{{ progress }}%</p>
            </div>
          </template>

          <template v-if="result && !uploading">
            <div class="grid gap-5 text-left md:grid-cols-[240px_1fr]" @click.stop>
              <img
                v-if="result.preview_frame_url"
                :src="result.preview_frame_url"
                class="h-44 w-full rounded-[20px] border border-blue-100/50 object-cover shadow-sm"
                alt="上传预览"
              />
              <div class="space-y-4">
                <div class="inline-flex rounded-full bg-blue-50 px-3 py-1 text-xs font-semibold text-blue-700">
                  上传完成
                </div>
                <!-- 视频元数据 -->
                <template v-if="result.media_type === 'video'">
                  <div class="grid gap-3 sm:grid-cols-2">
                    <div class="rounded-[18px] border border-blue-100/50 bg-white/90 px-4 py-3 text-sm">
                      <div class="text-xs text-slate-400">时长</div>
                      <div class="mt-1 font-semibold text-slate-900">{{ formatDuration((result.metadata as any).duration) }}</div>
                    </div>
                    <div class="rounded-[18px] border border-blue-100/50 bg-white/90 px-4 py-3 text-sm">
                      <div class="text-xs text-slate-400">分辨率</div>
                      <div class="mt-1 font-semibold text-slate-900">{{ result.metadata.width }} × {{ result.metadata.height }}</div>
                    </div>
                    <div class="rounded-[18px] border border-blue-100/50 bg-white/90 px-4 py-3 text-sm">
                      <div class="text-xs text-slate-400">帧率</div>
                      <div class="mt-1 font-semibold text-slate-900">{{ (result.metadata as any).fps }} fps</div>
                    </div>
                    <div class="rounded-[18px] border border-blue-100/50 bg-white/90 px-4 py-3 text-sm">
                      <div class="text-xs text-slate-400">编码</div>
                      <div class="mt-1 font-semibold text-slate-900">{{ (result.metadata as any).codec }}</div>
                    </div>
                  </div>
                </template>
                <!-- 图片元数据 -->
                <template v-else>
                  <div class="grid gap-3 sm:grid-cols-2">
                    <div class="rounded-[18px] border border-blue-100/50 bg-white/90 px-4 py-3 text-sm">
                      <div class="text-xs text-slate-400">分辨率</div>
                      <div class="mt-1 font-semibold text-slate-900">{{ result.metadata.width }} × {{ result.metadata.height }}</div>
                    </div>
                    <div class="rounded-[18px] border border-blue-100/50 bg-white/90 px-4 py-3 text-sm">
                      <div class="text-xs text-slate-400">格式</div>
                      <div class="mt-1 font-semibold text-slate-900">{{ (result.metadata as any).format }}</div>
                    </div>
                    <div class="rounded-[18px] border border-blue-100/50 bg-white/90 px-4 py-3 text-sm col-span-2">
                      <div class="text-xs text-slate-400">文件大小</div>
                      <div class="mt-1 font-semibold text-slate-900">{{ formatFileSize((result.metadata as any).file_size) }}</div>
                    </div>
                  </div>
                </template>
                <button
                  class="inline-flex items-center justify-center gap-2 rounded-full border border-blue-200 bg-white px-4 py-1.5 text-sm font-semibold text-blue-700 shadow-sm transition-colors duration-200 hover:bg-blue-50 disabled:cursor-not-allowed disabled:opacity-50"
                  @click.stop="reset"
                >重新上传</button>
              </div>
            </div>
          </template>
        </div>

        <transition name="fade">
          <div v-if="error" class="mt-4 rounded-[18px] border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-600">
            {{ error }}
          </div>
        </transition>
      </section>

      <aside class="flex h-full flex-col justify-between gap-3">
        <div class="rounded-[20px] border border-blue-100/50 bg-white/88 p-4 shadow-[0_16px_40px_rgba(15,23,42,0.05)]">
          <div class="text-sm font-semibold text-slate-900">关于我们</div>
          <div class="mt-3 text-xs leading-6 text-slate-400">
            <p class="mb-2"><strong>DealWith</strong> 是一款专业的去水印解决方案，采用先进的深度学习技术，能够精准检测并去除视频和图片中的各类水印。</p>
            <p><strong>智能特性：</strong>自动识别水印位置、支持批量处理、一键操作，完美保持画质。</p>
          </div>
        </div>
        <div class="rounded-[20px] border border-blue-100/50 bg-white/88 p-4 shadow-[0_16px_40px_rgba(15,23,42,0.05)]">
          <div class="text-sm font-semibold text-slate-900">支持格式</div>
          <div class="mt-2 text-xs text-slate-400">
            <div>视频：MP4 / AVI / MKV</div>
            <div class="mt-1">图片：JPG / PNG / WEBP / BMP</div>
          </div>
        </div>
        <div class="rounded-[20px] border border-blue-100/50 bg-white/88 p-4 shadow-[0_16px_40px_rgba(15,23,42,0.05)]">
          <div class="text-sm font-semibold text-slate-900">大小限制</div>
          <div class="mt-2 text-xs text-slate-400">单文件最大 2GB</div>
        </div>
      </aside>
    </div>
  </ToolLayout>
</template>

<script setup lang="ts">
import { ref } from "vue";
import axios from "axios";
import { useRouter, type HistoryState } from "vue-router";
import ToolLayout from "../components/ToolLayout.vue";
import type { UploadResponse } from "../types";

const router = useRouter();
const fileInput = ref<HTMLInputElement | null>(null);
const isDragging = ref(false);
const uploading = ref(false);
const progress = ref(0);
const error = ref("");
const result = ref<UploadResponse | null>(null);

const MAX_SIZE = 2 * 1024 * 1024 * 1024;
const ALLOWED_EXT = [".mp4", ".avi", ".mkv", ".jpg", ".jpeg", ".png", ".webp", ".bmp"];

function validate(file: File): string {
  const ext = file.name.slice(file.name.lastIndexOf(".")).toLowerCase();
  if (!ALLOWED_EXT.includes(ext)) return "不支持的文件格式，请上传 MP4/AVI/MKV 视频或 JPG/PNG/WEBP/BMP 图片。";
  if (file.size > MAX_SIZE) return "文件大小超过 2GB 限制，请压缩后再试。";
  return "";
}

async function upload(file: File) {
  error.value = "";
  result.value = null;
  const msg = validate(file);
  if (msg) { error.value = msg; return; }
  uploading.value = true;
  progress.value = 0;
  const form = new FormData();
  form.append("file", file);
  try {
    const { data } = await axios.post<UploadResponse>("/api/upload", form, {
      onUploadProgress(e) {
        if (e.total) progress.value = Math.round((e.loaded / e.total) * 100);
      },
    });
    result.value = data;
    router.push({ path: `/process/${data.task_id}`, state: { uploadResponse: data } as unknown as HistoryState });
  } catch (e: unknown) {
    error.value = axios.isAxiosError(e) && e.response?.data?.detail ? e.response.data.detail : "上传失败，请稍后重试。";
  } finally {
    uploading.value = false;
  }
}

function onFileChange(e: Event) {
  const file = (e.target as HTMLInputElement).files?.[0];
  if (file) upload(file);
}

function onDrop(e: DragEvent) {
  isDragging.value = false;
  const file = e.dataTransfer?.files?.[0];
  if (file) upload(file);
}

function reset() {
  result.value = null;
  progress.value = 0;
  error.value = "";
}

function formatDuration(seconds: number): string {
  const m = Math.floor(seconds / 60).toString().padStart(2, "0");
  const s = Math.floor(seconds % 60).toString().padStart(2, "0");
  return `${m}:${s}`;
}

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}
</script>

<style scoped>
.fade-enter-active, .fade-leave-active { transition: opacity 0.2s ease; }
.fade-enter-from, .fade-leave-to { opacity: 0; }
</style>
