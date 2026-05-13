<template>
  <div class="page-container ladder-page">
    <div class="page-header">
      <h2>&#x68AF;&#x5F62;&#x56FE;</h2>
      <div class="header-actions">
        <el-button :icon="Refresh" @click="loadData" :loading="loading">&#x5237;&#x65B0;</el-button>
        <el-button @click="runSelfCheck" :loading="checking">&#x4E1A;&#x52A1;&#x81EA;&#x68C0;</el-button>
        <el-button :icon="Refresh" @click="refreshLive" :loading="liveLoading">&#x8BFB;&#x503C;</el-button>
        <el-switch
          v-model="autoRefresh"
          inline-prompt
          :active-text="'\u5b9e\u65f6'"
          :inactive-text="'\u624b\u52a8'"
          @change="toggleLive"
        />
      </div>
    </div>

    <div class="legend-row">
      <el-tag effect="plain">&#x89E6;&#x70B9;&#xFF1A;PLC &#x547D;&#x4EE4;</el-tag>
      <el-tag effect="plain" type="success">&#x529F;&#x80FD;&#x5757;&#xFF1A;&#x91C7;&#x56FE;/&#x63A8;&#x7406;</el-tag>
      <el-tag effect="plain" type="warning">&#x7EBF;&#x5708;&#xFF1A;ACK/&#x7ED3;&#x679C;&#x56DE;&#x5199;</el-tag>
      <el-tag effect="plain" type="info">&#x7EDF;&#x8BA1;&#xFF1A;&#x7F3A;&#x9677;&#x6570;/&#x8017;&#x65F6;</el-tag>
    </div>

    <el-alert
      v-if="selfCheck"
      class="check-alert"
      :title="selfCheckTitle"
      :type="selfCheck.ok ? 'success' : 'warning'"
      :closable="false"
      show-icon
    >
      <div class="check-grid">
        <span v-for="item in selfCheck.items" :key="item.key" :class="{ ok: item.ok, fail: !item.ok }">
          <b>{{ item.ok ? 'OK' : 'NG' }}</b>{{ item.label }}<small>{{ item.detail }}</small>
        </span>
      </div>
    </el-alert>

    <el-empty
      v-if="!loading && diagrams.length === 0"
      :description="'\u6682\u65e0\u68c0\u6d4b\u901a\u9053\uff0c\u8bf7\u5148\u5bfc\u5165\u9884\u8bbe\u6216\u521b\u5efa\u68c0\u6d4b\u901a\u9053'"
    />

    <div v-else class="diagram-list">
      <section v-for="diagram in diagrams" :key="diagram.key" class="diagram-section">
        <div class="diagram-head">
          <div>
            <h3>{{ diagram.title }}</h3>
            <p>{{ diagram.subtitle }}</p>
          </div>
          <div class="head-badges">
            <el-tag type="success" effect="dark">{{ diagram.camera }}</el-tag>
            <el-tag effect="dark">{{ diagram.model }}</el-tag>
          </div>
        </div>

        <div class="ladder-card">
          <div class="rail left-rail" />
          <div class="rail right-rail" />
          <div v-for="rung in diagram.rungs" :key="rung.key" class="rung-row">
            <div class="wire" />
            <div class="rung-label">{{ rung.label }}</div>
            <div class="contact" :class="{ active: isLiveActive(rung.liveTrigger) }">
              <span class="symbol">| |</span>
              <strong>{{ rung.trigger }}</strong>
              <small>{{ rung.triggerPlc }}</small>
              <em v-if="rung.liveTrigger">{{ liveDisplay(rung.liveTrigger) }}</em>
            </div>
            <div class="function-block">
              <strong>{{ rung.action }}</strong>
              <small>{{ rung.detail }}</small>
            </div>
            <div class="coil" :class="[rung.kind, { active: isLiveActive(rung.liveOutput) }]">
              <span class="symbol">{{ rung.symbol }}</span>
              <strong>{{ rung.output }}</strong>
              <small>{{ rung.outputPlc }}</small>
              <em v-if="rung.liveOutput">{{ liveDisplay(rung.liveOutput) }}</em>
            </div>
          </div>
        </div>

        <div class="metric-row">
          <span v-for="metric in diagram.metrics" :key="metric.label">
            <b>{{ metric.addr }}</b>{{ metric.label }}
            <em v-if="metric.liveAddr">{{ liveDisplay(metric.liveAddr) }}</em>
          </span>
        </div>
      </section>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { Refresh } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import {
  bulkReadDevice,
  getVisflowzSelfCheck,
  listCameras,
  listChannels,
  listMappings,
  listModels,
  listMultiframeChannels,
} from '../api'

const loading = ref(false)
const liveLoading = ref(false)
const checking = ref(false)
const autoRefresh = ref(false)
const mappings = ref([])
const channels = ref([])
const multiframeChannels = ref([])
const cameras = ref([])
const models = ref([])
const liveValues = ref({})
const selfCheck = ref(null)
let liveTimer = null
let _liveRefreshing = false

function plcFor(vmoduleAddr) {
  const hit = mappings.value.find(m => m.vmodule_addr === vmoduleAddr)
  return hit ? hit.plc_addr : '-'
}

function modelLabel(id) {
  const hit = models.value.find(m => m.model_id === id)
  return hit ? `${id} - \u5df2\u52a0\u8f7d` : (id || '\u672a\u7ed1\u5b9a\u6a21\u578b')
}

function cameraLabel(id) {
  const hit = cameras.value.find(c => c.camera_id === id)
  if (!hit) return id || '\u672a\u7ed1\u5b9a\u76f8\u673a'
  return `${id} - ${hit.is_open ? '\u5df2\u6253\u5f00' : '\u672a\u6253\u5f00'}`
}

function statusText(code) {
  if (code === undefined || code === null) return '-'
  return `${code} / 0x${Number(code).toString(16).toUpperCase().padStart(2, '0')}`
}

function liveDisplay(addr) {
  if (!addr) return '-'
  const value = liveValues.value[addr]
  if (value && typeof value === 'object' && value.error) return 'ERR'
  if (value === undefined || value === null) return '--'
  if (typeof value === 'boolean') return value ? 'ON' : 'OFF'
  return String(value)
}

function isLiveActive(addr) {
  const value = liveValues.value[addr]
  return value === true || Number(value) > 0
}

function framePlan(ch) {
  if (Array.isArray(ch.frame_plan) && ch.frame_plan.length) return ch.frame_plan
  const count = ch.frame_count || 1
  return Array.from({ length: count }, (_, index) => ({
    command: index + 1,
    status_code: 10 + index + 1,
    model_id: ch.model_id,
    exposure: null,
  }))
}

const diagrams = computed(() => {
  const single = channels.value.map((ch, idx) => ({
    key: `single:${ch.name || idx}`,
    title: ch.name || `\u5355\u5e27\u901a\u9053 ${idx + 1}`,
    subtitle: '\u0050\u004c\u0043 \u4f4d\u89e6\u53d1\u540e\u5b8c\u6210\u91c7\u56fe\u3001\u63a8\u7406\uff0c\u5e76\u56de\u5199\u5b8c\u6210\u8109\u51b2\u4e0e\u7ed3\u679c\u3002',
    camera: cameraLabel(ch.camera_id),
    model: modelLabel(ch.model_id),
    rungs: [
      {
        key: 'single-main',
        label: '\u68c0\u6d4b\u6267\u884c',
        trigger: ch.trigger_addr || '-',
        triggerPlc: plcFor(ch.trigger_addr),
        liveTrigger: ch.trigger_addr,
        action: '\u91c7\u56fe + \u63a8\u7406',
        detail: ch.camera_id ? `\u76f8\u673a ${ch.camera_id}` : '\u672a\u7ed1\u5b9a\u76f8\u673a',
        output: ch.done_addr || '-',
        outputPlc: plcFor(ch.done_addr),
        liveOutput: ch.done_addr,
        symbol: '( )',
        kind: 'ack',
      },
      {
        key: 'single-result',
        label: '\u7ed3\u679c\u56de\u5199',
        trigger: ch.done_addr || '-',
        triggerPlc: plcFor(ch.done_addr),
        liveTrigger: ch.done_addr,
        action: 'OK/NG \u5224\u5b9a',
        detail: '\u5199\u5165\u7ed3\u679c\u4e0e\u7edf\u8ba1',
        output: ch.result_addr || '-',
        outputPlc: plcFor(ch.result_addr),
        liveOutput: ch.result_addr,
        symbol: '[W]',
        kind: 'result',
      },
    ],
    metrics: [
      { label: '\u7f3a\u9677\u6570', addr: ch.defect_count_addr || '-', liveAddr: ch.defect_count_addr },
      { label: '\u8017\u65f6', addr: ch.inference_time_addr || '-', liveAddr: ch.inference_time_addr },
      { label: '\u603b\u6570', addr: ch.total_count_addr || '-', liveAddr: ch.total_count_addr },
      { label: 'NG \u6570', addr: ch.ng_count_addr || '-', liveAddr: ch.ng_count_addr },
    ],
  }))

  const multi = multiframeChannels.value.map((ch, idx) => {
    const policy = ch.result_policy || {}
    const resultCodes = { ok: 7, ng_repairable: 6, ng_fatal: 5, ...(policy.result_codes || {}) }
    const errorCode = policy.error_code ?? 255
    const plan = framePlan(ch)
    return {
      key: `multi:${ch.name || idx}`,
      title: ch.name || `\u591a\u5e27\u901a\u9053 ${idx + 1}`,
      subtitle: `\u547d\u4ee4\u5bc4\u5b58\u5668 ${ch.cmd_addr || '-'} \u9010\u5e27\u89e6\u53d1\uff0c\u72b6\u6001/\u7ed3\u679c\u5bc4\u5b58\u5668 ${ch.status_addr || '-'} \u56de\u5199 ACK \u4e0e\u6700\u7ec8\u7ed3\u679c\u3002`,
      camera: cameraLabel(ch.camera_id),
      model: modelLabel(ch.model_id),
      rungs: [
        ...plan.map((frame, frameIdx) => ({
          key: `frame:${frame.command}`,
          label: `\u7b2c ${frameIdx + 1} \u5e27`,
          trigger: `${ch.cmd_addr || '-'} = ${frame.command}`,
          triggerPlc: plcFor(ch.cmd_addr),
          liveTrigger: ch.cmd_addr,
          action: '\u91c7\u56fe + \u63a8\u7406',
          detail: `${frame.model_id || ch.model_id || '\u672a\u7ed1\u5b9a\u6a21\u578b'}${frame.exposure ? ` / \u66dd\u5149 ${frame.exposure}` : ''}`,
          output: `${ch.status_addr || '-'} = ${statusText(frame.status_code ?? (16 + frameIdx + 1))}`,
          outputPlc: plcFor(ch.status_addr),
          liveOutput: ch.status_addr,
          symbol: 'ACK',
          kind: 'ack',
        })),
        {
          key: 'final-result',
          label: '\u6700\u7ec8\u7ed3\u679c',
          trigger: plan.map(frame => frame.command).join(' + '),
          triggerPlc: ch.cmd_addr || '-',
          liveTrigger: ch.cmd_addr,
          action: '\u6c47\u603b\u7f3a\u9677\u4f18\u5148\u7ea7',
          detail: `OK=${resultCodes.ok} / \u53ef\u8fd4\u4fee=${resultCodes.ng_repairable} / \u81f4\u547d=${resultCodes.ng_fatal} / \u9519\u8bef=${errorCode}`,
          output: `${ch.result_addr || ch.status_addr || '-'} = 7/6/5/255`,
          outputPlc: plcFor(ch.result_addr || ch.status_addr),
          liveOutput: ch.result_addr || ch.status_addr,
          symbol: '[W]',
          kind: 'result',
        },
      ],
      metrics: [
        { label: '\u7f3a\u9677\u6570', addr: ch.count_addr || '-', liveAddr: ch.count_addr },
        { label: '\u8017\u65f6', addr: ch.time_addr || '-', liveAddr: ch.time_addr },
        { label: '\u590d\u4f4d\u7b56\u7565', addr: ch.reset_policy?.mode || 'wait_plc_zero' },
        { label: '\u4fdd\u5b58\u7b56\u7565', addr: ch.save_policy?.mode || 'all' },
      ],
    }
  })

  return [...multi, ...single]
})

const liveAddresses = computed(() => {
  const addresses = new Set()
  for (const ch of channels.value) {
    ;[
      ch.trigger_addr,
      ch.done_addr,
      ch.result_addr,
      ch.defect_count_addr,
      ch.inference_time_addr,
      ch.total_count_addr,
      ch.ng_count_addr,
    ].filter(Boolean).forEach(addr => addresses.add(addr))
  }
  for (const ch of multiframeChannels.value) {
    ;[
      ch.cmd_addr,
      ch.status_addr,
      ch.result_addr,
      ch.count_addr,
      ch.time_addr,
    ].filter(Boolean).forEach(addr => addresses.add(addr))
  }
  return [...addresses]
})

const selfCheckTitle = computed(() => {
  if (!selfCheck.value) return ''
  return selfCheck.value.ok
    ? '\u5f53\u524d\u914d\u7f6e\u5df2\u8986\u76d6\u53c2\u8003\u9879\u76ee\u4e3b\u6d41\u7a0b'
    : '\u5f53\u524d\u914d\u7f6e\u4e0e\u53c2\u8003\u9879\u76ee\u4e3b\u6d41\u7a0b\u4ecd\u6709\u5dee\u5f02'
})

async function loadData() {
  loading.value = true
  try {
    const [mapRes, chRes, mfRes, camRes, modelRes] = await Promise.all([
      listMappings(),
      listChannels(),
      listMultiframeChannels(),
      listCameras(),
      listModels(),
    ])
    mappings.value = mapRes || []
    channels.value = chRes || []
    multiframeChannels.value = mfRes || []
    cameras.value = camRes || []
    models.value = modelRes || []
    if (autoRefresh.value) await refreshLive()
  } catch {
    ElMessage.error('\u68af\u5f62\u56fe\u6570\u636e\u52a0\u8f7d\u5931\u8d25')
  } finally {
    loading.value = false
  }
}

async function refreshLive() {
  if (!liveAddresses.value.length) {
    liveValues.value = {}
    return
  }
  if (document.hidden || _liveRefreshing) return
  _liveRefreshing = true
  liveLoading.value = true
  try {
    liveValues.value = await bulkReadDevice(liveAddresses.value)
  } catch {
    ElMessage.error('\u8f6f\u5143\u4ef6\u5b9e\u65f6\u503c\u8bfb\u53d6\u5931\u8d25')
  } finally {
    liveLoading.value = false
    _liveRefreshing = false
  }
}

function startLive() {
  stopLive()
  refreshLive()
  liveTimer = window.setInterval(refreshLive, 2000)
}

function stopLive() {
  if (liveTimer) {
    window.clearInterval(liveTimer)
    liveTimer = null
  }
}

function toggleLive(enabled) {
  if (enabled) startLive()
  else stopLive()
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

watch(liveAddresses, () => {
  if (autoRefresh.value) refreshLive()
})

onMounted(loadData)
onUnmounted(stopLive)
</script>

<style scoped lang="scss">
.ladder-page { height: 100%; overflow: auto; }
.header-actions { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; justify-content: flex-end; }
.legend-row { display: flex; gap: 8px; margin-bottom: 12px; flex-wrap: wrap; }
.check-alert { margin-bottom: 14px; }
.check-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap: 8px; margin-top: 8px; }
.check-grid span { display: flex; align-items: center; gap: 7px; min-height: 30px; padding: 6px 8px; border-radius: 6px; background: rgba(255, 255, 255, 0.04); color: #a7b1d6; }
.check-grid span.ok b { color: #66bb6a; }
.check-grid span.fail b { color: #ffa726; }
.check-grid small { margin-left: auto; color: #8892b0; font-size: 12px; }
.diagram-list { display: flex; flex-direction: column; gap: 18px; padding-bottom: 24px; }
.diagram-section { border: 1px solid #26305f; border-radius: 8px; background: #101735; overflow: hidden; }
.diagram-head { display: flex; justify-content: space-between; align-items: flex-start; gap: 16px; padding: 14px 18px; border-bottom: 1px solid #26305f; }
.diagram-head h3 { margin: 0; color: #e0e6ff; font-size: 17px; }
.diagram-head p { margin: 4px 0 0; color: #8892b0; font-size: 13px; }
.head-badges { display: flex; gap: 8px; flex-wrap: wrap; justify-content: flex-end; }
.ladder-card { position: relative; padding: 18px 36px 18px 46px; background: #0b102a; }
.rail { position: absolute; top: 14px; bottom: 14px; width: 3px; background: #7b86b8; }
.left-rail { left: 20px; }
.right-rail { right: 20px; }
.rung-row { position: relative; min-height: 74px; display: grid; grid-template-columns: 94px minmax(130px, 1fr) minmax(210px, 1.3fr) minmax(170px, 1fr); gap: 18px; align-items: center; }
.wire { position: absolute; left: -26px; right: -16px; top: 50%; height: 2px; background: #445080; }
.rung-label { position: relative; z-index: 1; color: #a7b1d6; font-size: 13px; }
.contact, .function-block, .coil { position: relative; z-index: 1; min-height: 54px; display: flex; flex-direction: column; justify-content: center; align-items: center; text-align: center; padding: 6px 10px; border-radius: 6px; background: #10183b; border: 1px solid #354070; color: #e0e6ff; }
.function-block { border-color: #2f7d5b; }
.coil.ack { border-color: #2f7d5b; }
.coil.result { border-color: #b88732; }
.contact.active, .coil.active { border-color: #66bb6a; box-shadow: 0 0 0 1px rgba(102, 187, 106, 0.28), 0 0 14px rgba(102, 187, 106, 0.18); }
.symbol { color: #4fc3f7; font-weight: 700; line-height: 1; }
.contact small, .function-block small, .coil small { color: #8892b0; font-size: 12px; margin-top: 3px; }
.contact em, .coil em { margin-top: 4px; min-width: 34px; padding: 2px 6px; border-radius: 999px; background: #0b102a; color: #e0e6ff; font-size: 12px; font-style: normal; }
.metric-row { display: flex; flex-wrap: wrap; gap: 8px; padding: 12px 18px 14px; background: #101735; }
.metric-row span { display: inline-flex; align-items: center; gap: 6px; padding: 5px 9px; border: 1px solid #26305f; border-radius: 6px; background: #0f1640; color: #a7b1d6; font-size: 12px; }
.metric-row b { margin-right: 6px; color: #e0e6ff; }
.metric-row em { min-width: 30px; padding: 1px 6px; border-radius: 999px; background: #0b102a; color: #4fc3f7; font-style: normal; text-align: center; }
@media (max-width: 900px) {
  .diagram-head { flex-direction: column; }
  .rung-row { grid-template-columns: 1fr; gap: 8px; padding: 12px 0; }
  .wire { display: none; }
  .rung-label { font-weight: 700; }
  .check-grid { grid-template-columns: 1fr; }
  .check-grid span { align-items: flex-start; flex-direction: column; gap: 3px; }
  .check-grid small { margin-left: 0; }
}
</style>
