<template>
  <ToolLayout title="进入去水印工具" description="确认授权后开始。" current-step="access" compact>
    <div class="mx-auto max-w-3xl">
      <section class="rounded-[28px] border border-blue-100 bg-white/88 p-6 shadow-[0_30px_80px_rgba(37,99,235,0.14)] backdrop-blur-[18px] sm:p-8">
        <div class="space-y-5">
          <div>
            <h2 class="text-2xl font-semibold text-slate-900">使用前确认</h2>
            <p class="mt-2 text-sm leading-7 text-slate-400">
              仅处理你有合法权限的视频内容，不要用于移除他人版权标识或受保护信息。
            </p>
          </div>

          <label class="flex cursor-pointer items-start gap-3 rounded-[20px] border border-blue-100/50 bg-white/80 p-4">
            <input
              id="compliance"
              v-model="agreed"
              type="checkbox"
              class="mt-1 h-4 w-4 rounded border-slate-300 accent-blue-600"
            />
            <span class="text-sm leading-7 text-slate-700">我确认只处理我有权使用的视频内容。</span>
          </label>

          <button
            class="inline-flex w-full items-center justify-center gap-2 rounded-full bg-blue-600 px-4 py-1.5 text-sm font-semibold text-white shadow-sm transition-colors duration-200 hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-50"
            :disabled="!agreed"
            @click="handleAgree"
          >开始使用</button>
        </div>
      </section>
    </div>
  </ToolLayout>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import ToolLayout from '../components/ToolLayout.vue'

const router = useRouter()
const agreed = ref(false)

function handleAgree() {
  localStorage.setItem('compliance_agreed', 'true')
  router.push('/upload')
}
</script>
