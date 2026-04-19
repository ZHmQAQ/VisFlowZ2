<template>
  <div class="page-container">
    <div class="page-header">
      <h2>相机管理</h2>
      <el-button type="primary" :icon="Plus" @click="openAddDialog">添加相机</el-button>
    </div>

    <div class="camera-layout">
      <!-- Left: camera list -->
      <div class="camera-list">
        <el-card v-for="cam in cameras" :key="cam.camera_id" class="cam-card" :class="{ active: cam.camera_id === selectedId }">
          <div class="cam-header" @click="selectedId = cam.camera_id">
            <div>
              <span class="status-dot" :class="cam.is_open ? 'online' : 'offline'" />
              <b>{{ cam.camera_id }}</b>
            </div>
            <el-tag size="small" effect="plain">{{ cam.camera_type || cam.type }}</el-tag>
          </div>
          <div class="cam-params">
            <span>曝光: {{ cam.exposure }}μs</span>
            <span>增益: {{ cam.gain }}</span>
          </div>
          <div v-if="cam.physical_key" class="cam-physical">
            <el-tag size="small" type="info" effect="plain">{{ cam.physical_key }}</el-tag>
          </div>
          <div class="cam-actions">
            <el-button v-if="!cam.is_open" size="small" type="success" @click="doOpen(cam.camera_id)">打开</el-button>
            <el-button v-else size="small" type="warning" @click="doClose(cam.camera_id)">关闭</el-button>
            <el-button size="small" type="primary" :disabled="!cam.is_open" @click="doCapture(cam.camera_id)">
              拍照
            </el-button>
            <el-button size="small" type="primary" text @click.stop="openEditDialog(cam)">
              <el-icon><Edit /></el-icon>
            </el-button>
            <el-button size="small" type="danger" text @click="doRemove(cam.camera_id)">
              <el-icon><Delete /></el-icon>
            </el-button>
          </div>
        </el-card>
        <el-empty v-if="cameras.length === 0" description="暂无相机" />
      </div>

      <!-- Right: live view -->
      <div class="camera-view">
        <el-card>
          <template #header>
            <div style="display:flex;justify-content:space-between;align-items:center">
              <span>{{ selectedId || '请选择相机' }}</span>
              <div v-if="selectedId">
                <el-switch v-model="autoCapture" active-text="自动" inactive-text="" @change="toggleAuto" style="margin-right:8px" />
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
            <el-empty v-else description="暂无画面" style="padding:60px 0" />
          </div>
          <div v-if="frameInfo" class="frame-meta">
            {{ frameInfo.shape ? `${frameInfo.shape[1]}x${frameInfo.shape[0]}` : '' }}
            &nbsp;|&nbsp; {{ frameInfo.size_kb || 0 }} KB
          </div>
        </el-card>
      </div>
    </div>

    <!-- Add dialog -->
    <el-dialog v-model="showAdd" title="添加相机" width="500" :close-on-click-modal="false">
      <el-form :model="form" label-width="100px">
        <el-form-item label="相机 ID">
          <el-input v-model="form.camera_id" placeholder="如: cam1-exp1" />
        </el-form-item>
        <el-form-item label="类型">
          <el-select v-model="form.camera_type" style="width:100%">
            <el-option label="USB 相机" value="usb" />
            <el-option label="RTSP 网络流" value="rtsp" />
            <el-option label="大恒 (GigE)" value="daheng" />
            <el-option label="海康威视" value="hikvision" />
          </el-select>
        </el-form-item>
        <el-form-item label="设备编号" v-if="form.camera_type === 'usb'">
          <el-input-number v-model="form.config.device_index" :min="0" />
          <div class="form-hint">相同编号 = 同一物理相机，可创建多个虚拟相机</div>
        </el-form-item>
        <el-form-item label="RTSP 地址" v-if="form.camera_type === 'rtsp'">
          <el-input v-model="form.config.url" placeholder="rtsp://..." />
        </el-form-item>
        <el-form-item label="序列号/IP" v-if="form.camera_type === 'daheng' || form.camera_type === 'hikvision'">
          <el-input v-model="form.config.serial_number" placeholder="序列号或IP地址" />
          <div class="form-hint">相同序列号 = 同一物理相机，可创建多个虚拟相机</div>
        </el-form-item>

        <el-divider content-position="left">拍照参数</el-divider>
        <div class="form-hint" style="margin-bottom:12px">
          每个虚拟相机有独立的拍照参数，触发时自动切换到对应参数再拍照
        </div>
        <el-form-item label="曝光时间">
          <el-input-number v-model="form.exposure" :min="1" :max="1000000" :step="1000" controls-position="right" style="width:200px" />
          <span style="margin-left:8px;color:#8892b0;font-size:12px">μs (微秒)</span>
        </el-form-item>
        <el-form-item label="增益">
          <el-input-number v-model="form.gain" :min="0" :max="30" :step="0.1" :precision="1" controls-position="right" style="width:200px" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showAdd = false">取消</el-button>
        <el-button type="primary" :loading="loading" @click="doAdd">添加</el-button>
      </template>
    </el-dialog>

    <!-- Edit dialog -->
    <el-dialog v-model="showEdit" title="编辑相机参数" width="420" :close-on-click-modal="false">
      <el-form :model="editForm" label-width="100px">
        <el-form-item label="相机 ID">
          <el-input :model-value="editForm.camera_id" disabled />
        </el-form-item>
        <el-form-item label="曝光时间">
          <el-input-number v-model="editForm.exposure" :min="1" :max="1000000" :step="1000" controls-position="right" style="width:200px" />
          <span style="margin-left:8px;color:#8892b0;font-size:12px">μs</span>
        </el-form-item>
        <el-form-item label="增益">
          <el-input-number v-model="editForm.gain" :min="0" :max="30" :step="0.1" :precision="1" controls-position="right" style="width:200px" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showEdit = false">取消</el-button>
        <el-button type="primary" :loading="editLoading" @click="doEditSave">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, watch } from 'vue'
import { Plus, Delete, Edit } from '@element-plus/icons-vue'
import {
  addCamera, removeCamera, listCameras,
  openCamera, closeCamera, captureFrame, getFrameUrl,
  updateCameraConfig,
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

const defaultForm = () => ({
  camera_id: '', camera_type: 'usb',
  config: { device_index: 0, url: '', serial_number: '' },
  exposure: 10000, gain: 1.0,
})
const form = ref(defaultForm())

const showEdit = ref(false)
const editLoading = ref(false)
const editForm = ref({ camera_id: '', exposure: 10000, gain: 1.0 })

function openAddDialog() {
  form.value = defaultForm()
  showAdd.value = true
}

function openEditDialog(cam) {
  editForm.value = {
    camera_id: cam.camera_id,
    exposure: cam.exposure || 10000,
    gain: cam.gain ?? 1.0,
  }
  showEdit.value = true
}

async function doEditSave() {
  editLoading.value = true
  try {
    await updateCameraConfig(editForm.value.camera_id, {
      exposure: editForm.value.exposure,
      gain: editForm.value.gain,
    })
    ElMessage.success(`相机 [${editForm.value.camera_id}] 参数已更新`)
    showEdit.value = false
    refresh()
  } finally { editLoading.value = false }
}

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
    ElMessage.success(`相机 [${form.value.camera_id}] 已添加`)
    showAdd.value = false
    refresh()
  } finally { loading.value = false }
}

async function doRemove(id) {
  await ElMessageBox.confirm(`确认移除相机 [${id}]？`, '确认', { type: 'warning' })
  await removeCamera(id)
  if (selectedId.value === id) { selectedId.value = ''; frameUrl.value = '' }
  refresh()
}

async function doOpen(id) {
  try {
    await openCamera(id)
    ElMessage.success(`相机 [${id}] 已打开`)
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
  margin-bottom: 4px;
}

.cam-params {
  font-size: 12px;
  color: #8892b0;
  display: flex;
  gap: 12px;
  margin-bottom: 4px;
}

.cam-physical {
  margin-bottom: 6px;
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

.form-hint {
  font-size: 12px;
  color: #8892b0;
  margin-top: 4px;
  line-height: 1.6;
}
</style>
