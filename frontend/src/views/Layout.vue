<template>
  <div class="layout">
    <!-- 侧边栏 -->
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

    <!-- 主区域 -->
    <div class="main">
      <!-- 顶栏 -->
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
            {{ engineStore.running ? '运行中' : '已停止' }}
          </el-tag>
          <el-tag effect="plain" round size="small" style="margin-left:8px;" v-if="engineStore.running">
            周期 {{ engineStore.lastScanMs.toFixed(1) }}ms
          </el-tag>
          <el-tag effect="plain" round size="small" style="margin-left:8px;">
            扫描 {{ engineStore.scanCount.toLocaleString() }}
          </el-tag>
        </div>
      </header>

      <!-- 内容 -->
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

const route = useRoute()
const engineStore = useEngineStore()
const isCollapsed = ref(false)

const menuItems = [
  { path: '/dashboard', title: '仪表盘', icon: 'Odometer' },
  { path: '/plc', title: 'PLC 连接', icon: 'Connection' },
  { path: '/mappings', title: 'I/O 映射', icon: 'Switch' },
  { path: '/detection', title: '检测通道', icon: 'Camera' },
  { path: '/monitor', title: '软元件监控', icon: 'Monitor' },
  { path: '/cameras', title: '相机管理', icon: 'VideoCamera' },
  { path: '/models', title: '模型管理', icon: 'Cpu' },
  { path: '/settings', title: '系统设置', icon: 'Setting' },
]

const currentTitle = computed(() => {
  const item = menuItems.find(m => m.path === route.path)
  return item?.title || ''
})

onMounted(() => engineStore.startPolling(1000))
onUnmounted(() => engineStore.stopPolling())
</script>

<style scoped lang="scss">
.layout {
  display: flex;
  height: 100vh;
  width: 100vw;
}

.sidebar {
  width: 220px;
  min-width: 220px;
  background: #0f1640;
  display: flex;
  flex-direction: column;
  transition: width 0.25s;
  border-right: 1px solid #2a3268;

  &.collapsed {
    width: 64px;
    min-width: 64px;
  }
}

.logo {
  height: 56px;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
  color: #4fc3f7;
  cursor: pointer;
  border-bottom: 1px solid #2a3268;

  .logo-text {
    font-size: 20px;
    font-weight: 700;
    letter-spacing: 2px;
  }
}

.el-menu {
  flex: 1;
  overflow-y: auto;
}

.main {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.header {
  height: 50px;
  min-height: 50px;
  padding: 0 20px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: #111738;
  border-bottom: 1px solid #2a3268;
}

.header-left {
  :deep(.el-breadcrumb__inner) {
    color: #8892b0 !important;
  }
  :deep(.el-breadcrumb__item:last-child .el-breadcrumb__inner) {
    color: #e0e6ff !important;
  }
}

.header-right {
  display: flex;
  align-items: center;
}

.content {
  flex: 1;
  overflow: hidden;
  background: #0a0e27;
}
</style>
