<template>
  <div class="page-container">
    <div class="page-header">
      <h2>相机管理</h2>
      <el-button type="primary" :icon="Plus" @click="showAdd = true">添加相机</el-button>
    </div>

    <el-empty v-if="cameras.length === 0" description="暂无相机，请添加" />

    <div class="camera-grid">
      <el-card v-for="cam in cameras" :key="cam.id">
        <template #header>
          <div style="display:flex;justify-content:space-between;align-items:center">
            <span>{{ cam.id }}</span>
            <el-tag :type="cam.status === 'open' ? 'success' : 'info'" size="small" effect="dark">
              {{ cam.status === 'open' ? '已连接' : '未连接' }}
            </el-tag>
          </div>
        </template>
        <div style="font-size:13px;color:#8892b0;line-height:2;">
          <div>类型: {{ cam.type }}</div>
          <div v-if="cam.resolution">分辨率: {{ cam.resolution }}</div>
        </div>
      </el-card>
    </div>

    <el-dialog v-model="showAdd" title="添加相机" width="460">
      <el-form :model="form" label-width="80px">
        <el-form-item label="相机 ID">
          <el-input v-model="form.camera_id" placeholder="如: cam1" />
        </el-form-item>
        <el-form-item label="类型">
          <el-select v-model="form.camera_type" style="width:100%">
            <el-option label="USB 相机" value="usb" />
            <el-option label="RTSP 流" value="rtsp" />
            <el-option label="大恒相机" value="daheng" />
            <el-option label="海康相机" value="hikvision" />
          </el-select>
        </el-form-item>
        <el-form-item label="设备号" v-if="form.camera_type === 'usb'">
          <el-input-number v-model="form.config.device_index" :min="0" />
        </el-form-item>
        <el-form-item label="RTSP URL" v-if="form.camera_type === 'rtsp'">
          <el-input v-model="form.config.url" placeholder="rtsp://..." />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showAdd = false">取消</el-button>
        <el-button type="primary" @click="doAdd">添加</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { Plus } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'

// 当前相机管理 API 尚未在后端实现完整的 REST 端点
// 此页面为 UI 骨架，后续对接
const cameras = ref([])
const showAdd = ref(false)
const form = ref({
  camera_id: '', camera_type: 'usb', config: { device_index: 0, url: '' },
})

function doAdd() {
  ElMessage.info('相机管理 API 对接中...')
  showAdd.value = false
}
</script>

<style scoped>
.camera-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px; }
</style>
