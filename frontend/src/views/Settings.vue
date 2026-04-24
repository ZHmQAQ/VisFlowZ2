<template>
  <div class="page-container">
    <div class="page-header">
      <h2>系统设置</h2>
    </div>

    <el-card style="max-width:600px">
      <template #header>扫描引擎参数</template>
      <el-form label-width="140px">
        <el-form-item label="目标扫描周期">
          <el-input-number v-model="config.target_cycle_ms" :min="5" :max="1000" :step="5" />
          <span style="margin-left:8px;color:#8892b0">ms</span>
        </el-form-item>
        <el-form-item label="Modbus 超时">
          <el-input-number v-model="config.modbus_timeout" :min="0.1" :max="10" :step="0.1" :precision="1" />
          <span style="margin-left:8px;color:#8892b0">秒</span>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :loading="saving" @click="save">保存</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <el-card style="max-width:600px;margin-top:16px">
      <template #header>持久化 & 自动保存</template>
      <el-form label-width="140px">
        <el-form-item label="配置自动保存">
          <el-tag type="success" effect="dark" size="small">已启用</el-tag>
          <span style="margin-left:8px;color:#8892b0;font-size:12px">修改配置后 2 秒自动保存到数据库</span>
        </el-form-item>
        <el-form-item>
          <el-button type="warning" @click="manualSave" :loading="manualSaving">立即保存</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <el-card style="max-width:600px;margin-top:16px">
      <template #header>图片存储</template>
      <el-form label-width="140px">
        <el-form-item label="保存 OK 图片">
          <el-switch v-model="imgSettings.save_ok_images" @change="updateImgSettings" />
        </el-form-item>
        <el-form-item label="保存 NG 图片">
          <el-switch v-model="imgSettings.save_ng_images" @change="updateImgSettings" />
        </el-form-item>
      </el-form>
    </el-card>

    <el-card style="max-width:600px;margin-top:16px">
      <template #header>日志管理</template>
      <el-form label-width="140px">
        <el-form-item label="日志级别">
          <el-select v-model="logLevel" @change="changeLogLevel" style="width:160px">
            <el-option v-for="l in logLevels" :key="l" :label="l" :value="l" />
          </el-select>
        </el-form-item>
      </el-form>
    </el-card>

    <el-card style="max-width:600px;margin-top:16px">
      <template #header>系统信息</template>
      <el-descriptions :column="1" border>
        <el-descriptions-item label="版本">VModule v1.0.0</el-descriptions-item>
        <el-descriptions-item label="API 端口">8100</el-descriptions-item>
        <el-descriptions-item label="Python">{{ sysInfo.python || '-' }}</el-descriptions-item>
        <el-descriptions-item label="API 文档">
          <a href="/docs" target="_blank" style="color:#4fc3f7">http://localhost:8100/docs</a>
        </el-descriptions-item>
      </el-descriptions>
    </el-card>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import {
  getHealth, getEngineStatus, updateEngineConfig,
  getLogLevel, setLogLevel, getSystemSettings, updateSystemSettings, saveNow
} from '../api'
import { ElMessage } from 'element-plus'

const config = ref({ target_cycle_ms: 20, modbus_timeout: 1.0 })
const sysInfo = ref({})
const saving = ref(false)
const manualSaving = ref(false)
const logLevel = ref('INFO')
const logLevels = ['TRACE', 'DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']
const imgSettings = ref({ save_ok_images: false, save_ng_images: true })

async function save() {
  saving.value = true
  try {
    await updateEngineConfig(config.value)
    ElMessage.success('设置已保存')
  } catch {
    ElMessage.error('保存失败')
  } finally {
    saving.value = false
  }
}

async function manualSave() {
  manualSaving.value = true
  try {
    await saveNow()
    ElMessage.success('配置已手动保存')
  } catch {} finally {
    manualSaving.value = false
  }
}

async function changeLogLevel(level) {
  try {
    await setLogLevel(level)
    ElMessage.success(`日志级别已切换为 ${level}`)
  } catch {}
}

async function updateImgSettings() {
  try {
    await updateSystemSettings(imgSettings.value)
    ElMessage.success('图片存储设置已更新')
  } catch {}
}

onMounted(async () => {
  try {
    const data = await getHealth()
    sysInfo.value = data
  } catch {}
  try {
    const st = await getEngineStatus()
    if (st.target_cycle_ms) config.value.target_cycle_ms = st.target_cycle_ms
  } catch {}
  try {
    const ll = await getLogLevel()
    logLevel.value = ll.level
  } catch {}
  try {
    const s = await getSystemSettings()
    if (s.save_ok_images !== undefined) imgSettings.value.save_ok_images = s.save_ok_images
    if (s.save_ng_images !== undefined) imgSettings.value.save_ng_images = s.save_ng_images
  } catch {}
})
</script>
