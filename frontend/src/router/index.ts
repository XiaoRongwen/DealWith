import { createRouter, createWebHistory } from 'vue-router'
import type { RouteRecordRaw } from 'vue-router'

const routes: RouteRecordRaw[] = [
  {
    path: '/',
    component: () => import('../views/UploadPage.vue')
  },
  {
    path: '/upload',
    component: () => import('../views/UploadPage.vue')
  },
  {
    path: '/process/:taskId',
    component: () => import('../views/ProcessPage.vue')
  },
  {
    path: '/progress/:taskId',
    component: () => import('../views/ProgressPage.vue')
  },
  {
    path: '/download/:taskId',
    component: () => import('../views/DownloadPage.vue')
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

const protectedPaths = ['/process', '/progress', '/download']

router.beforeEach((to) => {
  const isProtected = protectedPaths.some((p) => to.path.startsWith(p))
  if (isProtected && localStorage.getItem('compliance_agreed') !== 'true') {
    return '/upload'
  }
})

export default router
