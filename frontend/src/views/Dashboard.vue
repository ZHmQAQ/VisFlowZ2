<template>
  <div class="page-container">
    <div class="dashboard-grid">
      <!-- 状态概览卡片 -->
      <el-card class="stat-card">
        <div class="stat-value" :style="{ color: engine.running ? '#66bb6a' : '#ef5350' }">
          {{ engine.running ? '运行中' : '已停止' }}
        </div>
        <div class="stat-label">扫描引擎</div>
      </el-card>
      <el-card class="stat-card">
        <div class="stat-value">{{ engine.lastScanMs.toFixed(1) }}</div>
        <div class="stat-label">扫描周期 (ms)</div>
      </el-card>
      <el-card class="stat-card">
        <div class="stat-value">{{ engine.scanCount.toLocaleString() }}</div>
        <div class="stat-label">累计扫描</div>
      </el-card>
      <el-card class="stat-card">
        <div class="stat-value">{{ plcSummary }}</div>
        <div class="stat-label">PLC 在线/总数</div>
      </el-card>
      <el-card class="stat-card">
        <div class="stat-value">{{ engine.status.io_mappings || 0 }}</div>
        <div class="stat-label">I/O 映射点</div>
      </el-card>
      <el-card class="stat-card">
        <div class="stat-value">{{ engine.status.program_blocks || 0 }}</div>
        <div class="stat-label">程序块</div>
      </el-card>

      <!-- 快速操作 -->
      <el-card class="action-card" style="grid-column: span 3">
        <template #header>
          <span>引擎控制</span>
        </template>
        <div class="action-row">
          <el-button type="success" :icon="VideoPlay" :disabled="engine.running" @click="doStart" :loading="loading">
            启动
          </el-button>
          <el-button type="danger" :icon="VideoPause" :disabled="!engine.running" @click="doStop" :loading="loading">
            停止
          </el-button>
          <el-divider direction="vertical" />
          <el-select
            v-model="selectedPreset"
            placeholder="内置预设"
            filterable
            clearable
            style="width: 220px"
          >
            <el-option
              v-for="item in presetOptions"
              :key="item.id"
              :label="item.name"
              :value="item.id"
            >
              <div style="display:flex;justify-content:space-between;gap:12px">
                <span>{{ item.name }}</span>
                <span style="color:#8892b0;font-size:12px">{{ presetStats(item) }}</span>
              </div>
            </el-option>
          </el-select>
          <el-button type="warning" :icon="Upload" :disabled="!selectedPreset" @click="doLoadNamedPreset" :loading="presetLoading">
            应用预设
          </el-button>
          <el-upload
            :before-upload="handlePresetUpload"
            :show-file-list="false"
            accept=".json"
          >
            <el-button :icon="Upload">导入预设 JSON</el-button>
          </el-upload>
          <el-button :icon="Download" @click="doSavePreset" :loading="saving">保存预设</el-button>
          <el-divider direction="vertical" />
          <el-upload
            :before-upload="handleConfigUpload"
            :show-file-list="false"
            accept=".json"
          >
            <el-button :icon="Upload">导入完整配置</el-button>
          </el-upload>
          <el-button :icon="Download" @click="doExportConfig">导出完整配置</el-button>
        </div>
      </el-card>

      <!-- 预设操作提示 -->
      <el-card style="grid-column: span 3">
        <template #header>
          <span>系统软元件 (SM/SD)</span>
        </template>
        <el-table :data="systemDevices" size="small" stripe>
          <el-table-column prop="address" label="地址" width="80" />
          <el-table-column prop="value" label="值" width="100">
            <template #default="{ row }">
              <el-tag v-if="typeof row.value === 'boolean'" :type="row.value ? 'success' : 'info'" size="small">
                {{ row.value ? 'ON' : 'OFF' }}
              </el-tag>
              <span v-else>{{ row.value }}</span>
            </template>
          </el-table-column>
          <el-table-column prop="desc" label="说明" />
        </el-table>
      </el-card>

      <!-- 实时监控 -->
      <el-card style="grid-column: span 6">
        <template #header>
          <div style="display:flex;justify-content:space-between;align-items:center">
            <span>实时监控</span>
            <div>
              <el-switch v-model="camAutoRefresh" active-text="自动刷新" style="margin-right:8px" @change="toggleCamRefresh" />
              <el-button size="small" text @click="refreshCameras">
                <el-icon><Refresh /></el-icon>
              </el-button>
            </div>
          </div>
        </template>
        <div v-if="openCameras.length === 0" style="text-align:center;color:#8892b0;padding:20px 0">
          暂无已打开的相机，请前往
          <router-link to="/cameras" style="color:#4fc3f7">相机管理</router-link>
          添加并打开相机
        </div>
        <div v-else class="cam-grid">
          <div v-for="cam in openCameras" :key="cam.camera_id" class="cam-thumb"
               @click="$router.push('/cameras')">
            <img v-if="camFrames[cam.camera_id]"
                 :src="camFrames[cam.camera_id]"
                 class="cam-thumb-img" />
            <div v-else class="cam-thumb-placeholder">无画面</div>
            <div class="cam-thumb-label">
              <span class="status-dot online" />
              {{ cam.camera_id }}
            </div>
          </div>
        </div>
      </el-card>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { VideoPlay, VideoPause, Upload, Download, Refresh } from '@element-plus/icons-vue'
import { useEngineStore } from '../stores/engine'
import {
  exportConfig,
  importConfig,
  startEngine, stopEngine, loadPreset, savePreset,
  listPresets, loadNamedPreset,
  bulkReadDevice, listCameras, captureFrame, getFrameUrl,
} from '../api'
import { ElMessage } from 'element-plus'

const engine = useEngineStore()
const loading = ref(false)
const saving = ref(false)
const presetLoading = ref(false)
const presetOptions = ref([])
const selectedPreset = ref('')
const plcSummary = computed(() => {
  const total = Number(engine.plcConnectionCount || 0)
  const online = Number(engine.plcConnectedCount || 0)
  return total ? `${online}/${total}` : '0'
})

// ---- 系统软元件 ----
const systemDevices = ref([
  { address: 'SM0', value: false, desc: '常 ON' },
  { address: 'SM1', value: false, desc: '常 OFF' },
  { address: 'SM10', value: false, desc: '扫描引擎运行中' },
  { address: 'SM11', value: false, desc: '通信异常' },
  { address: 'SD0', value: 0, desc: '扫描周期 (ms)' },
  { address: 'SD1', value: 0, desc: '已连接 PLC 数量' },
])

let _sysTimer = null
let _systemRefreshing = false

async function refreshSystem() {
  if (document.hidden || _systemRefreshing) return
  _systemRefreshing = true
  try {
    const addrs = systemDevices.value.map(d => d.address)
    const data = await bulkReadDevice(addrs)
    systemDevices.value.forEach(d => {
      if (data[d.address] !== undefined) d.value = data[d.address]
    })
  } catch {} finally {
    _systemRefreshing = false
  }
}

// ---- 引擎控制 ----
async function doStart() {
  loading.value = true
  try {
    await startEngine()
    ElMessage.success('扫描引擎已启动')
    engine.refresh()
  } finally { loading.value = false }
}

async function doStop() {
  loading.value = true
  try {
    await stopEngine()
    ElMessage.warning('扫描引擎已停止')
    engine.refresh()
  } finally { loading.value = false }
}

// ---- 预设 ----
function presetStats(item) {
  return `${item.plc_connections} PLC / ${item.io_mappings} IO / ${item.detection_channels + item.multiframe_channels} 通道`
}

async function refreshPresets() {
  try {
    presetOptions.value = await listPresets()
    if (!selectedPreset.value && presetOptions.value.length) {
      selectedPreset.value = presetOptions.value[0].id
    }
  } catch {
    presetOptions.value = []
  }
}

function presetSuccessMessage(res) {
  return `预设已加载: ${res.plc_connections} PLC, ${res.io_mappings} 映射, ${res.detection_channels + res.multiframe_channels} 通道, ${res.cameras} 相机`
}

function configSuccessMessage(result) {
  const stats = result?.stats || {}
  const countOf = (name) => stats[name]?.added || 0
  return `配置已导入: ${countOf('plc_connections')} PLC, ${countOf('io_mappings')} 映射, ${countOf('detection_channels') + countOf('multiframe_channels')} 通道`
}

function downloadJson(data, filename) {
  const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}

async function doLoadNamedPreset() {
  if (!selectedPreset.value) return
  presetLoading.value = true
  try {
    const res = await loadNamedPreset(selectedPreset.value)
    ElMessage.success(presetSuccessMessage(res))
    engine.refresh()
    refreshCameras()
  } catch {
    ElMessage.error('加载预设失败')
  } finally {
    presetLoading.value = false
  }
}

function handlePresetUpload(file) {
  const reader = new FileReader()
  reader.onload = async (e) => {
    try {
      const preset = JSON.parse(e.target.result)
      const res = await loadPreset(preset)
      ElMessage.success(presetSuccessMessage(res))
      engine.refresh()
      refreshCameras()
    } catch {
      ElMessage.error('预设文件解析失败')
    }
  }
  reader.readAsText(file)
  return false
}

async function doSavePreset() {
  saving.value = true
  try {
    const data = await savePreset()
    downloadJson(data, `vmodule_preset_${new Date().toISOString().slice(0, 10)}.json`)
    ElMessage.success('预设已保存')
  } catch {
    ElMessage.error('保存预设失败')
  } finally {
    saving.value = false
  }
}

async function doExportConfig() {
  try {
    const data = await exportConfig()
    downloadJson(data, `vmodule_config_${new Date().toISOString().slice(0, 10)}.json`)
    ElMessage.success('完整配置已导出')
  } catch {
    ElMessage.error('导出完整配置失败')
  }
}

function handleConfigUpload(file) {
  const reader = new FileReader()
  reader.onload = async (e) => {
    try {
      const config = JSON.parse(e.target.result)
      const res = await importConfig(config)
      ElMessage.success(configSuccessMessage(res))
      await Promise.allSettled([
        engine.refresh(),
        refreshPresets(),
        refreshSystem(),
        refreshCameras(),
      ])
    } catch {
      ElMessage.error('完整配置文件解析失败')
    }
  }
  reader.readAsText(file)
  return false
}

// ---- 实时监控 ----
const cameras = ref([])
const camFrames = ref({})
const camAutoRefresh = ref(false)
let _camTimer = null
let _frameCounter = 0
let _cameraRefreshing = false

const openCameras = computed(() => cameras.value.filter(c => c.is_open))

async function refreshCameras() {
  if (document.hidden || _cameraRefreshing) return
  _cameraRefreshing = true
  try {
    cameras.value = await listCameras()
  } catch {}
  // 对已打开的相机拍照并刷新画面
  for (const cam of openCameras.value) {
    try {
      await captureFrame(cam.camera_id)
      _frameCounter++
      camFrames.value[cam.camera_id] = getFrameUrl(cam.camera_id) + '?t=' + _frameCounter
    } catch {}
  }
  _cameraRefreshing = false
}

function toggleCamRefresh(val) {
  if (_camTimer) { clearInterval(_camTimer); _camTimer = null }
  if (val) {
    _camTimer = setInterval(refreshCameras, 3000)
  }
}

// ---- 生命周期 ----
onMounted(() => {
  refreshPresets()
  refreshSystem()
  _sysTimer = setInterval(refreshSystem, 5000)
  // 实时监控:进页面无条件拉一次相机列表(否则永远显示"暂无已打开的相机")
  refreshCameras()
  if (camAutoRefresh.value) {
    _camTimer = setInterval(refreshCameras, 3000)
  }
})

onUnmounted(() => {
  clearInterval(_sysTimer)
  if (_camTimer) clearInterval(_camTimer)
})
</script>

<style scoped lang="scss">
.dashboard-grid {
  display: grid;
  grid-template-columns: repeat(6, 1fr);
  gap: 16px;
}

.stat-card {
  text-align: center;
  .stat-value { font-size: 28px; font-weight: 700; color: #4fc3f7; }
  .stat-label { font-size: 12px; color: #8892b0; margin-top: 4px; }
}

.action-row {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}

.cam-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
  gap: 12px;
}

.cam-thumb {
  position: relative;
  background: #000;
  border-radius: 6px;
  overflow: hidden;
  cursor: pointer;
  transition: border-color 0.15s;
  border: 1px solid #2a3268;

  &:hover { border-color: #4fc3f7; }
}

.cam-thumb-img {
  width: 100%;
  height: 180px;
  object-fit: contain;
  display: block;
}

.cam-thumb-placeholder {
  width: 100%;
  height: 180px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #555;
  font-size: 13px;
}

.cam-thumb-label {
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  background: rgba(0,0,0,0.7);
  color: #e0e6ff;
  font-size: 12px;
  padding: 4px 8px;
  display: flex;
  align-items: center;
}
</style>
