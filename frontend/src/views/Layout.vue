<template>
  <div class="layout">
    <aside class="sidebar" :class="{ collapsed: isCollapsed }">
      <div class="logo" @click="isCollapsed = !isCollapsed">
        <el-icon :size="28"><Cpu /></el-icon>
        <span v-show="!isCollapsed" class="logo-text">VModule</span>
      </div>
      <el-menu
        :default-active="route.path"
        :collapse="isCollapsed"
        background-color="#0f1640"
        text-color="#8892b0"
        active-text-color="#4fc3f7"
        router
      >
        <el-menu-item v-for="item in menuItems" :key="item.path" :index="item.path">
          <el-icon><component :is="item.icon" /></el-icon>
          <template #title>{{ item.title }}</template>
        </el-menu-item>
      </el-menu>
    </aside>

    <div class="main">
      <header class="header">
        <div class="header-left">
          <el-breadcrumb separator="/">
            <el-breadcrumb-item>VModule</el-breadcrumb-item>
            <el-breadcrumb-item>{{ currentTitle }}</el-breadcrumb-item>
          </el-breadcrumb>
        </div>
        <div class="header-right">
          <el-tag :type="engineStore.running ? 'success' : 'danger'" effect="dark" round size="small">
            <span class="status-dot" :class="engineStore.running ? 'online' : 'offline'" />
            {{ engineStore.running ? '\u8fd0\u884c\u4e2d' : '\u5df2\u505c\u6b62' }}
          </el-tag>
          <el-tag v-if="engineStore.running" effect="plain" round size="small" style="margin-left:8px;">
            {{ '\u5468\u671f' }} {{ engineStore.lastScanMs.toFixed(1) }}ms
          </el-tag>
          <el-tag effect="plain" round size="small" style="margin-left:8px;">
            {{ '\u626b\u63cf' }} {{ engineStore.scanCount.toLocaleString() }} {{ '\u6b21' }}
          </el-tag>
        </div>
      </header>

      <main class="content">
        <router-view />
      </main>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRoute } from 'vue-router'
import { useEngineStore } from '../stores/engine'
import {
  Camera,
  Connection,
  Cpu,
  Document,
  Monitor,
  Odometer,
  Operation,
  Setting,
  SetUp,
  Share,
  Switch,
  VideoCamera,
} from '@element-plus/icons-vue'

const route = useRoute()
const engineStore = useEngineStore()
const isCollapsed = ref(false)

const menuItems = [
  { path: '/dashboard', title: '\u4eea\u8868\u76d8', icon: Odometer },
  { path: '/plc', title: 'PLC \u8fde\u63a5', icon: Connection },
  { path: '/mappings', title: 'I/O \u6620\u5c04', icon: Switch },
  { path: '/detection', title: '\u68c0\u6d4b\u901a\u9053', icon: Camera },
  { path: '/topology', title: '\u7cfb\u7edf\u62d3\u6251', icon: Share },
  { path: '/ladder', title: '\u68af\u5f62\u56fe', icon: Connection },
  { path: '/monitor', title: '\u8f6f\u5143\u4ef6\u76d1\u63a7', icon: Monitor },
  { path: '/cameras', title: '\u76f8\u673a\u7ba1\u7406', icon: VideoCamera },
  { path: '/devices', title: '\u5916\u90e8\u8bbe\u5907', icon: Cpu },
  { path: '/event-actions', title: '\u4e8b\u4ef6\u52a8\u4f5c', icon: Operation },
  { path: '/rules', title: '\u89c4\u5219\u5f15\u64ce', icon: SetUp },
  { path: '/models', title: '\u6a21\u578b\u7ba1\u7406', icon: Cpu },
  { path: '/records', title: '\u68c0\u6d4b\u8bb0\u5f55', icon: Document },
  { path: '/settings', title: '\u7cfb\u7edf\u8bbe\u7f6e', icon: Setting },
]

const currentTitle = computed(() => {
  const item = menuItems.find(m => m.path === route.path)
  return item?.title || ''
})

onMounted(() => engineStore.startPolling(2000))
onUnmounted(() => engineStore.stopPolling())
</script>

<style scoped lang="scss">
.layout { display: flex; height: 100vh; width: 100vw; }
.sidebar { width: 220px; min-width: 220px; background: #0f1640; display: flex; flex-direction: column; transition: width 0.25s; border-right: 1px solid #2a3268; }
.sidebar.collapsed { width: 64px; min-width: 64px; }
.logo { height: 56px; display: flex; align-items: center; justify-content: center; gap: 10px; color: #4fc3f7; cursor: pointer; border-bottom: 1px solid #2a3268; }
.logo .logo-text { font-size: 20px; font-weight: 700; letter-spacing: 2px; }
.el-menu { flex: 1; overflow-y: auto; }
.main { flex: 1; display: flex; flex-direction: column; overflow: hidden; }
.header { height: 50px; min-height: 50px; padding: 0 20px; display: flex; align-items: center; justify-content: space-between; background: #111738; border-bottom: 1px solid #2a3268; }
.header-left :deep(.el-breadcrumb__inner) { color: #8892b0 !important; }
.header-left :deep(.el-breadcrumb__item:last-child .el-breadcrumb__inner) { color: #e0e6ff !important; }
.header-right { display: flex; align-items: center; }
.content { flex: 1; overflow: hidden; background: #0a0e27; }
</style>
