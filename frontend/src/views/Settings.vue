<template>
  <div class="page-container">
    <div class="page-header">
      <h2>&#x7CFB;&#x7EDF;&#x8BBE;&#x7F6E;</h2>
      <div class="header-actions">
        <el-button @click="exportCurrentConfig">&#x5BFC;&#x51FA;&#x914D;&#x7F6E;</el-button>
        <el-upload :before-upload="importConfigFile" :show-file-list="false" accept=".json">
          <el-button type="primary">&#x5BFC;&#x5165;&#x914D;&#x7F6E;</el-button>
        </el-upload>
      </div>
    </div>

    <div class="settings-grid">
      <el-card class="wide-card">
        <template #header>&#x914D;&#x7F6E;&#x4E0E;&#x9884;&#x8BBE;</template>
        <div class="config-actions">
          <el-button type="primary" @click="exportCurrentConfig">&#x5BFC;&#x51FA;&#x5B8C;&#x6574;&#x914D;&#x7F6E;</el-button>
          <el-upload :before-upload="importConfigFile" :show-file-list="false" accept=".json">
            <el-button type="warning">&#x5BFC;&#x5165;&#x5B8C;&#x6574;&#x914D;&#x7F6E;</el-button>
          </el-upload>
          <el-button @click="exportCurrentPreset">&#x5BFC;&#x51FA;&#x5F53;&#x524D;&#x9884;&#x8BBE;</el-button>
          <el-upload :before-upload="importPresetFile" :show-file-list="false" accept=".json">
            <el-button>&#x5BFC;&#x5165;&#x9884;&#x8BBE; JSON</el-button>
          </el-upload>
        </div>
        <div class="hint-line">
          &#x5B8C;&#x6574;&#x914D;&#x7F6E;&#x5305;&#x542B;&#x7CFB;&#x7EDF;&#x8BBE;&#x7F6E;&#xFF1B;&#x9884;&#x8BBE;&#x53EA;&#x5305;&#x542B; PLC&#x3001;I/O&#x3001;&#x76F8;&#x673A;&#x3001;&#x8BBE;&#x5907;&#x3001;&#x89C4;&#x5219;&#x3001;&#x4E8B;&#x4EF6;&#x52A8;&#x4F5C;&#x548C;&#x68C0;&#x6D4B;&#x901A;&#x9053;&#x3002;
        </div>
      </el-card>

      <el-card class="wide-card">
        <template #header>&#x4E1A;&#x52A1;&#x81EA;&#x68C0;</template>
        <div class="check-toolbar">
          <el-button type="primary" :loading="checking" @click="runSelfCheck">&#x68C0;&#x67E5;&#x5F53;&#x524D;&#x914D;&#x7F6E;</el-button>
          <span class="hint-line">&#x5BF9;&#x7167;&#x53C2;&#x8003;&#x9879;&#x76EE;&#x4E3B;&#x6D41;&#x7A0B;&#x68C0;&#x67E5;&#x5F53;&#x524D; VModule &#x914D;&#x7F6E;&#x3002;</span>
        </div>
        <el-alert
          v-if="selfCheck"
          :title="selfCheck.ok ? '\u5f53\u524d\u914d\u7f6e\u5df2\u8986\u76d6\u53c2\u8003\u4e3b\u6d41\u7a0b' : '\u5f53\u524d\u914d\u7f6e\u4ecd\u5b58\u5728\u8986\u76d6\u7f3a\u53e3'"
          :type="selfCheck.ok ? 'success' : 'warning'"
          :closable="false"
          show-icon
        >
          <div class="check-summary">
            <span><b>{{ selfCheck.summary?.required_passed || 0 }}/{{ selfCheck.summary?.required_total || 0 }}</b>&#x5FC5;&#x9009;&#x9879;</span>
            <span><b>{{ selfCheck.summary?.warning_passed || 0 }}/{{ selfCheck.summary?.warning_total || 0 }}</b>&#x53C2;&#x8003;&#x9879;</span>
          </div>
        </el-alert>
        <div v-if="selfCheck" class="check-sections">
          <div class="check-block">
            <h4>&#x5DEE;&#x5F02;&#x9879;</h4>
            <el-empty v-if="failedItems.length === 0" :description="'\u65e0\u5dee\u5f02'" />
            <div v-else class="check-list">
              <div v-for="item in failedItems" :key="item.key" class="check-item fail">
                <div class="check-main">
                  <strong>{{ item.label }}</strong>
                  <span>{{ item.detail }}</span>
                </div>
                <small>{{ item.advice }}</small>
              </div>
            </div>
          </div>
          <div class="check-block">
            <h4>&#x5DF2;&#x901A;&#x8FC7;</h4>
            <div class="check-list compact">
              <div v-for="item in passedItems" :key="item.key" class="check-item ok">
                <div class="check-main">
                  <strong>{{ item.label }}</strong>
                  <span>{{ item.detail }}</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </el-card>

      <el-card>
        <template #header>&#x8FD0;&#x884C;&#x53C2;&#x6570;</template>
        <el-form label-width="150px">
          <el-form-item label="&#x626B;&#x63CF;&#x5468;&#x671F;">
            <el-input-number v-model="config.target_cycle_ms" :min="5" :max="1000" :step="5" />
            <span class="unit">ms</span>
          </el-form-item>
          <el-form-item label="Modbus &#x8D85;&#x65F6;">
            <el-input-number v-model="config.modbus_timeout" :min="0.1" :max="10" :step="0.1" :precision="1" />
            <span class="unit">s</span>
          </el-form-item>
          <el-form-item>
            <el-button type="primary" :loading="saving" @click="save">&#x4FDD;&#x5B58;&#x8FD0;&#x884C;&#x53C2;&#x6570;</el-button>
          </el-form-item>
        </el-form>
      </el-card>

      <el-card>
        <template #header>&#x5185;&#x7F6E;&#x9884;&#x8BBE;</template>
        <el-form label-width="150px">
          <el-form-item label="&#x9884;&#x8BBE;">
            <el-select v-model="selectedPreset" filterable style="width:100%">
              <el-option v-for="item in presets" :key="item.id" :label="item.name" :value="item.id">
                <div class="preset-option">
                  <span>{{ item.name }}</span>
                  <span>{{ presetStats(item) }}</span>
                </div>
              </el-option>
            </el-select>
          </el-form-item>
          <el-form-item>
            <el-button type="warning" :disabled="!selectedPreset" :loading="presetLoading" @click="loadSelectedPreset">
              &#x52A0;&#x8F7D;&#x5185;&#x7F6E;&#x9884;&#x8BBE;
            </el-button>
          </el-form-item>
        </el-form>
      </el-card>

      <el-card>
        <template #header>&#x6301;&#x4E45;&#x5316;</template>
        <el-form label-width="150px">
          <el-form-item label="&#x81EA;&#x52A8;&#x4FDD;&#x5B58;">
            <el-tag type="success" effect="dark" size="small">&#x5DF2;&#x542F;&#x7528;</el-tag>
            <span class="hint">&#x914D;&#x7F6E;&#x53D8;&#x5316;&#x4F1A;&#x5728;&#x77ED;&#x6682;&#x9632;&#x6296;&#x540E;&#x81EA;&#x52A8;&#x4FDD;&#x5B58;&#x3002;</span>
          </el-form-item>
          <el-form-item>
            <el-button type="warning" @click="manualSave" :loading="manualSaving">&#x7ACB;&#x5373;&#x4FDD;&#x5B58;</el-button>
          </el-form-item>
        </el-form>
      </el-card>

      <el-card>
        <template #header>&#x56FE;&#x7247;&#x5B58;&#x50A8;</template>
        <el-form label-width="150px">
          <el-form-item label="&#x4FDD;&#x5B58; OK &#x56FE;&#x7247;">
            <el-switch v-model="imgSettings.save_ok_images" @change="updateImgSettings" />
          </el-form-item>
          <el-form-item label="&#x4FDD;&#x5B58; NG &#x56FE;&#x7247;">
            <el-switch v-model="imgSettings.save_ng_images" @change="updateImgSettings" />
          </el-form-item>
        </el-form>
      </el-card>

      <el-card>
        <template #header>&#x65E5;&#x5FD7;</template>
        <el-form label-width="150px">
          <el-form-item label="&#x65E5;&#x5FD7;&#x7EA7;&#x522B;">
            <el-select v-model="logLevel" @change="changeLogLevel" style="width:160px">
              <el-option v-for="level in logLevels" :key="level" :label="level" :value="level" />
            </el-select>
          </el-form-item>
        </el-form>
      </el-card>

      <el-card>
        <template #header>&#x7CFB;&#x7EDF;&#x4FE1;&#x606F;</template>
        <el-descriptions :column="1" border>
          <el-descriptions-item label="&#x7248;&#x672C;">{{ sysInfo.version ? `VModule v${sysInfo.version}` : 'VModule' }}</el-descriptions-item>
          <el-descriptions-item label="API &#x7AEF;&#x53E3;">8100</el-descriptions-item>
          <el-descriptions-item label="Python">{{ sysInfo.python || '-' }}</el-descriptions-item>
          <el-descriptions-item label="GPU">
            <span v-if="gpuInfo.available">{{ gpuInfo.name || '已检测到 GPU' }}</span>
            <span v-else>&#x4E0D;&#x53EF;&#x7528;</span>
          </el-descriptions-item>
          <el-descriptions-item label="API &#x6587;&#x6863;">
            <a href="/docs" target="_blank" style="color:#4fc3f7">http://localhost:8100/docs</a>
          </el-descriptions-item>
        </el-descriptions>
      </el-card>
    </div>
  </div>
</template>

<script setup>
import { computed, ref, onMounted } from 'vue'
import {
  exportConfig,
  getEngineStatus,
  getGpuInfo,
  getHealth,
  getLogLevel,
  getSystemSettings,
  getVisflowzSelfCheck,
  importConfig,
  listPresets,
  loadPreset,
  loadNamedPreset,
  savePreset,
  saveNow,
  setLogLevel,
  updateEngineConfig,
  updateSystemSettings,
} from '../api'
import { ElMessage, ElMessageBox } from 'element-plus'

const config = ref({ target_cycle_ms: 20, modbus_timeout: 1.0 })
const sysInfo = ref({})
const saving = ref(false)
const manualSaving = ref(false)
const presetLoading = ref(false)
const logLevel = ref('INFO')
const logLevels = ['TRACE', 'DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']
const imgSettings = ref({ save_ok_images: false, save_ng_images: true })
const presets = ref([])
const selectedPreset = ref('')
const gpuInfo = ref({ available: false })
const checking = ref(false)
const selfCheck = ref(null)

const failedItems = computed(() => (selfCheck.value?.items || []).filter(item => !item.ok))
const passedItems = computed(() => (selfCheck.value?.items || []).filter(item => item.ok))

function presetStats(item) {
  return `${item.plc_connections || 0} PLC / ${item.io_mappings || 0} IO / ${(item.detection_channels || 0) + (item.multiframe_channels || 0)} \u901a\u9053 / ${item.rules || 0} \u89c4\u5219`
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

async function save() {
  saving.value = true
  try {
    await updateEngineConfig(config.value)
    ElMessage.success('\u8fd0\u884c\u53c2\u6570\u5df2\u4fdd\u5b58')
  } finally {
    saving.value = false
  }
}

async function manualSave() {
  manualSaving.value = true
  try {
    await saveNow()
    ElMessage.success('\u914d\u7f6e\u5df2\u5b89\u6392\u4fdd\u5b58')
  } finally {
    manualSaving.value = false
  }
}

async function changeLogLevel(level) {
  await setLogLevel(level)
  ElMessage.success(`\u65e5\u5fd7\u7ea7\u522b\u5df2\u5207\u6362\u4e3a ${level}`)
}

async function updateImgSettings() {
  await updateSystemSettings(imgSettings.value)
  ElMessage.success('\u56fe\u7247\u5b58\u50a8\u8bbe\u7f6e\u5df2\u66f4\u65b0')
}

async function exportCurrentConfig() {
  const data = await exportConfig()
  downloadJson(data, `vmodule_config_${new Date().toISOString().slice(0, 10)}.json`)
  ElMessage.success('\u5b8c\u6574\u914d\u7f6e\u5df2\u5bfc\u51fa')
}

async function exportCurrentPreset() {
  const data = await savePreset()
  downloadJson(data, `vmodule_preset_${new Date().toISOString().slice(0, 10)}.json`)
  ElMessage.success('\u5f53\u524d\u9884\u8bbe\u5df2\u5bfc\u51fa')
}

function importConfigFile(file) {
  const reader = new FileReader()
  reader.onload = async (event) => {
    try {
      const data = JSON.parse(event.target.result)
      const result = await importConfig(data)
      ElMessage.success(`\u5b8c\u6574\u914d\u7f6e\u5df2\u5bfc\u5165\uff1a${JSON.stringify(result.stats || {})}`)
      await loadInitial()
      await runSelfCheck()
    } catch {
      ElMessage.error('\u5bfc\u5165\u5931\u8d25\uff0c\u8bf7\u9009\u62e9\u6709\u6548\u7684 VModule \u914d\u7f6e JSON')
    }
  }
  reader.readAsText(file)
  return false
}

function importPresetFile(file) {
  const reader = new FileReader()
  reader.onload = async (event) => {
    try {
      const data = JSON.parse(event.target.result)
      const result = await loadPreset(data)
      ElMessage.success(`\u9884\u8bbe\u5df2\u5bfc\u5165\uff1a${result.plc_connections} PLC, ${result.io_mappings} IO, ${result.rules || 0} \u89c4\u5219`)
      await loadInitial()
      await runSelfCheck()
    } catch {
      ElMessage.error('\u5bfc\u5165\u5931\u8d25\uff0c\u8bf7\u9009\u62e9\u6709\u6548\u7684 VModule \u9884\u8bbe JSON')
    }
  }
  reader.readAsText(file)
  return false
}

async function loadSelectedPreset() {
  if (!selectedPreset.value) return
  await ElMessageBox.confirm('\u52a0\u8f7d\u9884\u8bbe\u4f1a\u8986\u76d6\u5f53\u524d\u8fd0\u884c\u914d\u7f6e\u3002', '\u52a0\u8f7d\u9884\u8bbe', {
    type: 'warning',
  })
  presetLoading.value = true
  try {
    const result = await loadNamedPreset(selectedPreset.value)
    ElMessage.success(`\u9884\u8bbe\u5df2\u52a0\u8f7d\uff1a${result.plc_connections} PLC, ${result.io_mappings} IO, ${result.rules || 0} \u89c4\u5219`)
    await runSelfCheck()
  } finally {
    presetLoading.value = false
  }
}

async function runSelfCheck() {
  checking.value = true
  try {
    selfCheck.value = await getVisflowzSelfCheck()
    if (selfCheck.value.ok) ElMessage.success('\u4e1a\u52a1\u81ea\u68c0\u901a\u8fc7')
    else ElMessage.warning('\u4e1a\u52a1\u81ea\u68c0\u53d1\u73b0\u5dee\u5f02')
  } catch {
    ElMessage.error('\u4e1a\u52a1\u81ea\u68c0\u5931\u8d25')
  } finally {
    checking.value = false
  }
}

async function loadInitial() {
  try { sysInfo.value = await getHealth() } catch {}
  try { gpuInfo.value = await getGpuInfo() } catch {}
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
  try {
    presets.value = await listPresets()
    if (!selectedPreset.value && presets.value.length) selectedPreset.value = presets.value[0].id
  } catch {}
  try { selfCheck.value = await getVisflowzSelfCheck() } catch {}
}

onMounted(loadInitial)
</script>

<style scoped lang="scss">
.header-actions { display: flex; gap: 8px; }
.settings-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(420px, 1fr)); gap: 16px; }
.wide-card { grid-column: 1 / -1; }
.config-actions { display: flex; gap: 10px; flex-wrap: wrap; align-items: center; }
.hint-line { margin-top: 10px; color: #8892b0; font-size: 13px; }
.unit, .hint { margin-left: 8px; color: #8892b0; }
.preset-option { display: flex; justify-content: space-between; gap: 12px; }
.preset-option span:last-child { color: #8892b0; font-size: 12px; }
.check-toolbar { display: flex; gap: 12px; align-items: center; flex-wrap: wrap; margin-bottom: 12px; }
.check-summary { display: flex; gap: 18px; margin-top: 8px; flex-wrap: wrap; }
.check-summary b { color: #e0e6ff; margin-right: 4px; }
.check-sections { display: grid; grid-template-columns: minmax(320px, 1fr) minmax(320px, 1fr); gap: 16px; margin-top: 14px; }
.check-block h4 { margin: 0 0 10px; font-size: 14px; color: #e0e6ff; }
.check-list { display: flex; flex-direction: column; gap: 10px; }
.check-list.compact { max-height: 320px; overflow: auto; padding-right: 4px; }
.check-item { border: 1px solid #26305f; border-radius: 8px; padding: 10px 12px; background: #0f1640; }
.check-item.ok { border-color: #2f7d5b; }
.check-item.fail { border-color: #b88732; }
.check-main { display: flex; justify-content: space-between; gap: 12px; align-items: flex-start; }
.check-main strong { color: #e0e6ff; font-size: 13px; }
.check-main span { color: #a7b1d6; font-size: 12px; text-align: right; }
.check-item small { display: block; margin-top: 8px; color: #8892b0; line-height: 1.5; }
@media (max-width: 900px) {
  .check-sections { grid-template-columns: 1fr; }
  .check-main { flex-direction: column; }
  .check-main span { text-align: left; }
}
</style>
