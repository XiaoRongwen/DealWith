<template>
  <ToolLayout title="处理完成" description="下载结果或继续处理。" current-step="download" compact>
    <div class="mx-auto max-w-2xl">
      <section class="rounded-[28px] border border-blue-100 bg-white/88 p-6 text-center shadow-[0_30px_80px_rgba(37,99,235,0.14)] backdrop-blur-[18px] sm:p-8">
        <div class="mx-auto flex h-16 w-16 items-center justify-center rounded-full bg-green-100 text-3xl text-green-600">
          ✓
        </div>
        <h2 class="mt-5 text-2xl font-semibold text-slate-900">处理完成</h2>
        <div class="mt-6 flex flex-col justify-center gap-3 sm:flex-row">
          <button
            class="inline-flex items-center justify-center gap-2 rounded-full bg-blue-600 px-4 py-1.5 text-sm font-semibold text-white shadow-sm transition-colors duration-200 hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-50"
            @click="handleDownload"
          >下载文件</button>
          <button
            class="inline-flex items-center justify-center gap-2 rounded-full border border-blue-200 bg-white px-4 py-1.5 text-sm font-semibold text-blue-700 shadow-sm transition-colors duration-200 hover:bg-blue-50 disabled:cursor-not-allowed disabled:opacity-50"
            @click="router.push('/upload')"
          >重新处理</button>
        </div>
      </section>
    </div>
  </ToolLayout>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import ToolLayout from '../components/ToolLayout.vue'

const route = useRoute()
const router = useRouter()
const taskId = computed(() => route.params.taskId as string)

function handleDownload() {
  const a = document.createElement('a')
  a.href = `/api/download/${taskId.value}`
  // 文件名由后端 Content-Disposition 决定，这里只做触发
  a.download = ''
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
}
</script>
