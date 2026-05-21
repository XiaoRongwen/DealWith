<script setup lang="ts">
import { computed } from 'vue'
import { RouterLink, useRoute } from 'vue-router'

interface StepItem {
  id: string
  label: string
  to?: string
}

const props = withDefaults(defineProps<{
  title?: string
  description?: string
  steps?: StepItem[]
  currentStep?: string
  compact?: boolean
}>(), {
  title: '',
  description: '',
  compact: false,
})

const route = useRoute()

const defaultSteps: StepItem[] = [
  { id: 'upload', label: '上传', to: '/upload' },
  { id: 'process', label: '参数设置' },
  { id: 'progress', label: '处理中' },
  { id: 'download', label: '下载' },
]

const steps = computed(() => props.steps ?? defaultSteps)

const currentIndex = computed(() =>
  steps.value.findIndex((item) => item.id === props.currentStep)
)

function getStatus(index: number) {
  if (index === currentIndex.value) return 'current'
  if (currentIndex.value !== -1 && index < currentIndex.value) return 'done'
  return 'upcoming'
}
</script>

<template>
  <!-- app-shell -->
  <div class="relative min-h-screen overflow-hidden">
    <!-- 背景装饰球 -->
    <div class="pointer-events-none absolute -top-36 -right-28 h-80 w-80 rounded-full bg-blue-500/[0.18] blur-[22px]" />
    <div class="pointer-events-none absolute -bottom-6 -left-28 h-72 w-72 rounded-full bg-sky-400/[0.14] blur-[22px]" />

    <!-- app-grid -->
    <div class="relative z-10 mx-auto w-full max-w-[1280px] px-5 pt-7 pb-14 max-md:pt-[18px] max-md:pb-9">

      <!-- Header -->
      <header class="sticky top-4 z-20 mb-7 rounded-[20px] border border-white/70 bg-white/75 px-4 py-2 shadow-[0_18px_50px_rgba(37,99,235,0.12)] backdrop-blur-[18px] sm:px-5 max-md:top-2.5 max-md:mb-5">
        <div class="flex flex-wrap items-center justify-between gap-3">
          <div class="flex items-center gap-3">
            <div class="flex h-9 w-9 items-center justify-center rounded-lg bg-gradient-to-br from-blue-600 to-sky-400 text-xs font-black text-white shadow-lg shadow-blue-500/20">
              DW
            </div>
            <div>
              <div class="text-xs font-semibold text-slate-900">DealWith</div>
              <div class="text-[10px] text-slate-400">去水印</div>
            </div>
          </div>

          <nav class="flex items-center gap-2">
            <RouterLink
              to="/"
              class="inline-flex items-center gap-2 rounded-full px-4 py-2.5 text-sm font-bold text-slate-500 no-underline transition-colors duration-200 hover:bg-blue-600/10 hover:text-blue-700"
              :class="(route.path.startsWith('/upload') || route.path.startsWith('/process') || route.path.startsWith('/progress') || route.path.startsWith('/download'))
                ? 'bg-blue-600/10 text-blue-700'
                : ''"
            >
              去水印
            </RouterLink>
          </nav>
        </div>
      </header>

      <!-- 步骤条 -->
      <section class="mb-3 flex items-center gap-1.5">
        <div
          v-for="(step, index) in steps"
          :key="step.id"
          class="flex items-center gap-1"
        >
          <!-- 步骤点 -->
          <component
            :is="step.to && index <= currentIndex ? RouterLink : 'div'"
            :to="step.to && index <= currentIndex ? step.to : undefined"
            class="flex h-4 w-4 items-center justify-center rounded-full text-[10px]"
            :class="{
              'bg-gray-200 text-gray-400': getStatus(index) === 'upcoming',
              'bg-blue-600 text-white': getStatus(index) === 'current',
              'bg-green-500 text-white': getStatus(index) === 'done',
            }"
          >
            <span v-if="getStatus(index) !== 'done'">{{ index + 1 }}</span>
            <span v-else>✓</span>
          </component>

          <!-- 步骤文字 -->
          <span
            class="whitespace-nowrap text-[11px]"
            :class="{
              'text-gray-400': getStatus(index) === 'upcoming',
              'font-semibold text-blue-600': getStatus(index) === 'current',
              'text-green-500': getStatus(index) === 'done',
            }"
          >{{ step.label }}</span>

          <!-- 连接线 -->
          <div
            v-if="index !== steps.length - 1"
            class="h-px w-5"
            :class="index < currentIndex ? 'bg-green-500' : 'bg-gray-200'"
          />
        </div>
      </section>

      <!-- 标题 -->
      <section
        v-if="(title || description) && !compact"
        class="mb-2 flex flex-wrap items-end justify-between gap-2"
      >
        <div>
          <h1 v-if="title" class="text-base font-semibold text-slate-900">{{ title }}</h1>
          <p v-if="description" class="text-xs text-slate-400">{{ description }}</p>
        </div>
      </section>

      <!-- 内容插槽 -->
      <main class="min-w-0">
        <slot />
      </main>

    </div>
  </div>
</template>
