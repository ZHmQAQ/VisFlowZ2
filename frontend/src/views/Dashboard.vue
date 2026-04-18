<template>
  <div class="page-container">
    <div class="dashboard-grid">
      <!-- 状态概览卡片 -->
      <el-card class="stat-card">
        <div class="stat-value" :style="{ color: engine.running ? '#66bb6a' : '#ef5350' }">
          {{ engine.running ? 'RUN' : 'STOP' }}
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
        <div class="stat-value">{{ engine.status.plc_clients || 0 }}</div>
        <div class="stat-label">PLC 连接</div>
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
          <el-upload
            :before-upload="handlePresetUpload"
            :show-file-list="false"
            accept=".json"
          >
            <el-button :icon="Upload">加载预设</el-button>
          </el-upload>
        </div>
      </el-card>

      <!-- 系统软元件 -->
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
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import { VideoPlay, VideoPause, Upload } from '@element-plus/icons-vue'
import { useEngineStore } from '../stores/engine'
import { startEngine, stopEngine, loadPreset, bulkReadDevice } from '../api'
import { ElMessage } from 'element-plus'

const engine = useEngineStore()
const loading = ref(false)

const systemDevices = ref([
  { address: 'SM0', value: false, desc: '常 ON' },
  { address: 'SM1', value: false, desc: '常 OFF' },
  { address: 'SM10', value: false, desc: '扫描引擎运行中' },
  { address: 'SM11', value: false, desc: '通信异常' },
  { address: 'SD0', value: 0, desc: '扫描周期 (ms)' },
  { address: 'SD1', value: 0, desc: '已连接 PLC 数量' },
])

let _sysTimer = null

async function refreshSystem() {
  try {
    const addrs = systemDevices.value.map(d => d.address)
    const data = await bulkReadDevice(addrs)
    systemDevices.value.forEach(d => {
      if (data[d.address] !== undefined) d.value = data[d.address]
    })
  } catch { /* ignore */ }
}

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

function handlePresetUpload(file) {
  const reader = new FileReader()
  reader.onload = async (e) => {
    try {
      const preset = JSON.parse(e.target.result)
      const res = await loadPreset(preset)
      ElMessage.success(`预设已加载: ${res.plc_connections} PLC, ${res.io_mappings} 映射, ${res.detection_channels} 通道`)
      engine.refresh()
    } catch (err) {
      ElMessage.error('预设文件解析失败')
    }
  }
  reader.readAsText(file)
  return false
}

onMounted(() => {
  refreshSystem()
  _sysTimer = setInterval(refreshSystem, 2000)
})
onUnmounted(() => clearInterval(_sysTimer))
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
}
</style>
