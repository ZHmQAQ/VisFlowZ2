<template>
  <div class="page-container">
    <div class="page-header">
      <h2>Camera Management</h2>
      <el-button type="primary" :icon="Plus" @click="showAdd = true">Add Camera</el-button>
    </div>

    <div class="camera-layout">
      <!-- Left: camera list -->
      <div class="camera-list">
        <el-card v-for="cam in cameras" :key="cam.camera_id" class="cam-card" :class="{ active: cam.camera_id === selectedId }">
          <div class="cam-header" @click="selectedId = cam.camera_id">
            <div>
              <span class="status-dot" :class="cam.status === 'open' ? 'online' : 'offline'" />
              <b>{{ cam.camera_id }}</b>
            </div>
            <el-tag size="small" effect="plain">{{ cam.camera_type || cam.type }}</el-tag>
          </div>
          <div class="cam-actions">
            <el-button v-if="cam.status !== 'open'" size="small" type="success" @click="doOpen(cam.camera_id)">Open</el-button>
            <el-button v-else size="small" type="warning" @click="doClose(cam.camera_id)">Close</el-button>
            <el-button size="small" type="primary" :disabled="cam.status !== 'open'" @click="doCapture(cam.camera_id)">
              Capture
            </el-button>
            <el-button size="small" type="danger" text @click="doRemove(cam.camera_id)">
              <el-icon><Delete /></el-icon>
            </el-button>
          </div>
        </el-card>
        <el-empty v-if="cameras.length === 0" description="No cameras" />
      </div>

      <!-- Right: live view -->
      <div class="camera-view">
        <el-card>
          <template #header>
            <div style="display:flex;justify-content:space-between;align-items:center">
              <span>{{ selectedId || 'Select a camera' }}</span>
              <div v-if="selectedId">
                <el-switch v-model="autoCapture" active-text="Auto" inactive-text="" @change="toggleAuto" style="margin-right:8px" />
                <el-select v-model="autoInterval" size="small" style="width:90px" :disabled="!autoCapture">
                  <el-option :value="200" label="200ms" />
                  <el-option :value="500" label="500ms" />
                  <el-option :value="1000" label="1s" />
                  <el-option :value="2000" label="2s" />
                </el-select>
              </div>
            </div>
          </template>
          <div class="frame-container">
            <img v-if="frameUrl" :src="frameUrl" class="frame-img" @error="frameUrl = ''" />
            <el-empty v-else description="No frame" style="padding:60px 0" />
          </div>
          <div v-if="frameInfo" class="frame-meta">
            {{ frameInfo.shape ? `${frameInfo.shape[1]}x${frameInfo.shape[0]}` : '' }}
            &nbsp;|&nbsp; {{ frameInfo.size_kb || 0 }} KB
          </div>
        </el-card>
      </div>
    </div>

    <!-- Add dialog -->
    <el-dialog v-model="showAdd" title="Add Camera" width="460">
      <el-form :model="form" label-width="90px">
        <el-form-item label="Camera ID">
          <el-input v-model="form.camera_id" placeholder="e.g. cam1" />
        </el-form-item>
        <el-form-item label="Type">
          <el-select v-model="form.camera_type" style="width:100%">
            <el-option label="USB Camera" value="usb" />
            <el-option label="RTSP Stream" value="rtsp" />
            <el-option label="Daheng (GigE)" value="daheng" />
            <el-option label="Hikvision" value="hikvision" />
          </el-select>
        </el-form-item>
        <el-form-item label="Device #" v-if="form.camera_type === 'usb'">
          <el-input-number v-model="form.config.device_index" :min="0" />
        </el-form-item>
        <el-form-item label="RTSP URL" v-if="form.camera_type === 'rtsp'">
          <el-input v-model="form.config.url" placeholder="rtsp://..." />
        </el-form-item>
        <el-form-item label="SN / IP" v-if="form.camera_type === 'daheng' || form.camera_type === 'hikvision'">
          <el-input v-model="form.config.sn" placeholder="Serial number or IP (optional)" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showAdd = false">Cancel</el-button>
        <el-button type="primary" :loading="loading" @click="doAdd">Add</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, watch } from 'vue'
import { Plus, Delete } from '@element-plus/icons-vue'
import {
  addCamera, removeCamera, listCameras,
  openCamera, closeCamera, captureFrame, getFrameUrl,
} from '../api'
import { ElMessage, ElMessageBox } from 'element-plus'

const cameras = ref([])
const selectedId = ref('')
const showAdd = ref(false)
const loading = ref(false)
const frameUrl = ref('')
const frameInfo = ref(null)
const autoCapture = ref(false)
const autoInterval = ref(500)
let _timer = null
let _frameCounter = 0

const form = ref({
  camera_id: '', camera_type: 'usb',
  config: { device_index: 0, url: '', sn: '' },
})

async function refresh() {
  try {
    cameras.value = await listCameras()
    if (cameras.value.length && !selectedId.value) {
      selectedId.value = cameras.value[0].camera_id
    }
  } catch {}
}

async function doAdd() {
  loading.value = true
  try {
    await addCamera(form.value)
    ElMessage.success(`Camera [${form.value.camera_id}] added`)
    showAdd.value = false
    form.value = { camera_id: '', camera_type: 'usb', config: { device_index: 0, url: '', sn: '' } }
    refresh()
  } finally { loading.value = false }
}

async function doRemove(id) {
  await ElMessageBox.confirm(`Remove camera [${id}]?`, 'Confirm', { type: 'warning' })
  await removeCamera(id)
  if (selectedId.value === id) { selectedId.value = ''; frameUrl.value = '' }
  refresh()
}

async function doOpen(id) {
  try {
    await openCamera(id)
    ElMessage.success(`Camera [${id}] opened`)
    refresh()
  } catch {}
}

async function doClose(id) {
  try {
    await closeCamera(id)
    autoCapture.value = false
    refresh()
  } catch {}
}

async function doCapture(id) {
  try {
    const res = await captureFrame(id || selectedId.value)
    frameInfo.value = res
    _frameCounter++
    frameUrl.value = getFrameUrl(id || selectedId.value) + '?t=' + _frameCounter
  } catch {}
}

function toggleAuto(val) {
  if (_timer) { clearInterval(_timer); _timer = null }
  if (val && selectedId.value) {
    _timer = setInterval(() => doCapture(selectedId.value), autoInterval.value)
  }
}

watch(autoInterval, () => {
  if (autoCapture.value) { toggleAuto(false); toggleAuto(true) }
})

watch(selectedId, () => {
  frameUrl.value = ''
  frameInfo.value = null
  if (autoCapture.value) { autoCapture.value = false; toggleAuto(false) }
})

onMounted(refresh)
onUnmounted(() => { if (_timer) clearInterval(_timer) })
</script>

<style scoped lang="scss">
.camera-layout {
  display: flex;
  gap: 16px;
  height: calc(100vh - 140px);
}

.camera-list {
  width: 280px;
  min-width: 280px;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.cam-card {
  cursor: pointer;
  transition: border-color 0.15s;
  &.active { border-color: #4fc3f7 !important; }
}

.cam-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.cam-actions {
  display: flex;
  gap: 4px;
  flex-wrap: wrap;
}

.camera-view {
  flex: 1;
  overflow: hidden;
}

.frame-container {
  background: #000;
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: 400px;
  border-radius: 4px;
}

.frame-img {
  max-width: 100%;
  max-height: 60vh;
  object-fit: contain;
}

.frame-meta {
  text-align: center;
  color: #8892b0;
  font-size: 12px;
  margin-top: 8px;
}
</style>
