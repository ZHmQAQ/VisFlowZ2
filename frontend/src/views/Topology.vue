<template>
  <div class="page-container">
    <div class="page-header">
      <h2>系统拓扑</h2>
      <el-button size="small" :icon="Refresh" @click="refresh" :loading="loading">刷新</el-button>
    </div>

    <div class="topo-container" ref="topoRef">
      <!-- 4 列布局 -->
      <div class="topo-column">
        <div class="topo-col-title">PLC 连接</div>
        <div v-for="plc in plcList" :key="plc.name"
             :data-topo="'plc:'+plc.name"
             class="topo-node plc-node" @click="$router.push('/plc')">
          <div class="topo-node-title">
            <span class="status-dot" :class="plc.connected ? 'online' : 'offline'" />
            {{ plc.name }}
          </div>
          <div class="topo-node-detail">{{ plc.host }}:{{ plc.port }}</div>
        </div>
        <div v-if="plcList.length === 0" class="topo-empty">无 PLC</div>
      </div>

      <div class="topo-column">
        <div class="topo-col-title">I/O 映射</div>
        <div v-for="(group, plcName) in mappingGroups" :key="plcName"
             :data-topo="'mapping:'+plcName"
             class="topo-node mapping-node" @click="$router.push('/mappings')">
          <div class="topo-node-title">{{ plcName }}</div>
          <div v-for="m in group.slice(0, 6)" :key="m.vmodule_addr" class="topo-mapping-line">
            <span class="mapping-addr">{{ m.vmodule_addr }}</span>
            <span class="mapping-arrow">{{ isInput(m.vmodule_addr) ? '&larr;' : '&rarr;' }}</span>
            <span class="mapping-addr">{{ m.plc_addr }}</span>
          </div>
          <div v-if="group.length > 6" class="topo-node-detail">... 共 {{ group.length }} 条</div>
        </div>
        <div v-if="Object.keys(mappingGroups).length === 0" class="topo-empty">无映射</div>
      </div>

      <div class="topo-column">
        <div class="topo-col-title">检测通道</div>
        <div v-for="ch in channels" :key="ch.name"
             :data-topo="'channel:'+ch.name"
             class="topo-node channel-node" @click="$router.push('/detection')">
          <div class="topo-node-title">{{ ch.name }}</div>
          <div class="topo-node-detail">触发: {{ ch.trigger_addr }}</div>
          <div class="topo-node-detail">相机: {{ ch.camera_id }}</div>
          <div class="topo-node-detail">模型: {{ ch.model_id }}</div>
        </div>
        <div v-for="mf in multiframeChannels" :key="'mf-'+mf.name"
             :data-topo="'channel:mf-'+mf.name"
             class="topo-node channel-node mf" @click="$router.push('/detection')">
          <div class="topo-node-title">{{ mf.name }} <el-tag size="small" type="warning">多帧</el-tag></div>
          <div class="topo-node-detail">命令: {{ mf.cmd_addr }}</div>
          <div class="topo-node-detail">相机: {{ mf.camera_id }}</div>
          <div class="topo-node-detail">模型: {{ mf.model_id }}</div>
        </div>
        <div v-if="channels.length === 0 && multiframeChannels.length === 0" class="topo-empty">无通道</div>
      </div>

      <div class="topo-column">
        <div class="topo-col-title">相机 / 模型</div>
        <div v-for="cam in cameras" :key="cam.camera_id"
             :data-topo="'camera:'+cam.camera_id"
             class="topo-node camera-node" @click="$router.push('/cameras')">
          <div class="topo-node-title">
            <span class="status-dot" :class="cam.is_open ? 'online' : 'offline'" />
            {{ cam.camera_id }}
          </div>
          <div class="topo-node-detail">{{ cam.camera_type }} | {{ cam.exposure }}μs</div>
        </div>
        <div v-for="model in models" :key="model.model_id"
             :data-topo="'model:'+model.model_id"
             class="topo-node model-node" @click="$router.push('/models')">
          <div class="topo-node-title">{{ model.model_id }}</div>
          <div class="topo-node-detail">{{ model.engine || '推理引擎' }}</div>
        </div>
        <div v-if="cameras.length === 0 && models.length === 0" class="topo-empty">无设备</div>
      </div>

      <!-- SVG 连线层 -->
      <svg class="topo-svg" ref="svgRef">
        <path v-for="(line, i) in lines" :key="i"
              :d="line.d" :stroke="line.color" stroke-width="2" fill="none"
              stroke-dasharray="6,3" opacity="0.6" />
      </svg>
    </div>

    <div style="margin-top:12px;color:#8892b0;font-size:12px;">
      <span style="display:inline-block;width:12px;height:3px;background:#4fc3f7;margin-right:4px;vertical-align:middle"></span>PLC↔映射 &nbsp;
      <span style="display:inline-block;width:12px;height:3px;background:#66bb6a;margin-right:4px;vertical-align:middle"></span>映射→通道 &nbsp;
      <span style="display:inline-block;width:12px;height:3px;background:#ffa726;margin-right:4px;vertical-align:middle"></span>多帧通道 &nbsp;
      <span style="display:inline-block;width:12px;height:3px;background:#ab47bc;margin-right:4px;vertical-align:middle"></span>通道→模型 &nbsp;
      共 {{ lines.length }} 条连线
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, nextTick } from 'vue'
import { Refresh } from '@element-plus/icons-vue'
import {
  listPLC, listMappings, listChannels, listMultiframeChannels,
  listCameras, listModels,
} from '../api'

const loading = ref(false)
const plcList = ref([])
const mappings = ref([])
const channels = ref([])
const multiframeChannels = ref([])
const cameras = ref([])
const models = ref([])

const mappingGroups = ref({})

const topoRef = ref(null)
const svgRef = ref(null)
const lines = ref([])

function isInput(addr) {
  return addr.startsWith('EX') || addr.startsWith('ED')
}

function getNode(topoId) {
  if (!topoRef.value) return null
  return topoRef.value.querySelector(`[data-topo="${topoId}"]`)
}

async function refresh() {
  loading.value = true
  try {
    const [plcs, maps, chs, mfs, cams, mods] = await Promise.all([
      listPLC(), listMappings(), listChannels(),
      listMultiframeChannels(), listCameras(), listModels(),
    ])

    plcList.value = Object.entries(plcs).map(([name, info]) => ({ name, ...info }))
    mappings.value = maps
    channels.value = chs
    multiframeChannels.value = mfs
    cameras.value = cams
    models.value = mods

    // 按 PLC 名称分组映射
    const groups = {}
    for (const m of maps) {
      if (!groups[m.plc_name]) groups[m.plc_name] = []
      groups[m.plc_name].push(m)
    }
    mappingGroups.value = groups

    await nextTick()
    // 额外延迟确保布局完成
    setTimeout(drawLines, 150)
  } catch {}
  loading.value = false
}

function getCenter(el) {
  if (!el || !topoRef.value) return null
  const containerRect = topoRef.value.getBoundingClientRect()
  const rect = el.getBoundingClientRect()
  if (rect.width === 0 || rect.height === 0) return null
  return {
    x: rect.left - containerRect.left + rect.width / 2,
    y: rect.top - containerRect.top + rect.height / 2,
    right: rect.right - containerRect.left,
    left: rect.left - containerRect.left,
  }
}

function drawLines() {
  const result = []
  if (!topoRef.value) return

  // 更新 SVG 尺寸
  const containerRect = topoRef.value.getBoundingClientRect()
  if (svgRef.value) {
    svgRef.value.setAttribute('width', containerRect.width)
    svgRef.value.setAttribute('height', containerRect.height)
  }

  // PLC -> Mapping groups (by plc_name)
  for (const plc of plcList.value) {
    const fromEl = getNode(`plc:${plc.name}`)
    const toEl = getNode(`mapping:${plc.name}`)
    const from = getCenter(fromEl)
    const to = getCenter(toEl)
    if (from && to) {
      result.push({ d: bezier(from.right, from.y, to.left, to.y), color: '#4fc3f7' })
    }
  }

  // Mapping groups -> Channels (by vmodule_addr match)
  for (const ch of channels.value) {
    for (const [plcName, group] of Object.entries(mappingGroups.value)) {
      const match = group.some(m => m.vmodule_addr.toUpperCase() === ch.trigger_addr.toUpperCase())
      if (match) {
        const fromEl = getNode(`mapping:${plcName}`)
        const toEl = getNode(`channel:${ch.name}`)
        const from = getCenter(fromEl)
        const to = getCenter(toEl)
        if (from && to) {
          result.push({ d: bezier(from.right, from.y, to.left, to.y), color: '#66bb6a' })
        }
        break
      }
    }
  }

  for (const mf of multiframeChannels.value) {
    for (const [plcName, group] of Object.entries(mappingGroups.value)) {
      const match = group.some(m => m.vmodule_addr.toUpperCase() === mf.cmd_addr.toUpperCase())
      if (match) {
        const fromEl = getNode(`mapping:${plcName}`)
        const toEl = getNode(`channel:mf-${mf.name}`)
        const from = getCenter(fromEl)
        const to = getCenter(toEl)
        if (from && to) {
          result.push({ d: bezier(from.right, from.y, to.left, to.y), color: '#ffa726' })
        }
        break
      }
    }
  }

  // Channels -> Cameras / Models
  const allChs = [
    ...channels.value.map(c => ({ key: `channel:${c.name}`, camera_id: c.camera_id, model_id: c.model_id })),
    ...multiframeChannels.value.map(c => ({ key: `channel:mf-${c.name}`, camera_id: c.camera_id, model_id: c.model_id })),
  ]
  for (const ch of allChs) {
    const fromEl = getNode(ch.key)
    const from = getCenter(fromEl)
    if (!from) continue
    const toCamEl = getNode(`camera:${ch.camera_id}`)
    const toCam = getCenter(toCamEl)
    if (toCam) {
      result.push({ d: bezier(from.right, from.y, toCam.left, toCam.y), color: '#4fc3f7' })
    }
    const toModelEl = getNode(`model:${ch.model_id}`)
    const toModel = getCenter(toModelEl)
    if (toModel) {
      result.push({ d: bezier(from.right, from.y, toModel.left, toModel.y), color: '#ab47bc' })
    }
  }

  lines.value = result
}

function bezier(x1, y1, x2, y2) {
  const cx = (x1 + x2) / 2
  return `M${x1},${y1} C${cx},${y1} ${cx},${y2} ${x2},${y2}`
}

let _resizeObserver = null

onMounted(() => {
  refresh()
  // 监听容器尺寸变化
  if (topoRef.value && typeof ResizeObserver !== 'undefined') {
    _resizeObserver = new ResizeObserver(() => drawLines())
    _resizeObserver.observe(topoRef.value)
  }
})

onUnmounted(() => {
  if (_resizeObserver) _resizeObserver.disconnect()
})
</script>

<style scoped lang="scss">
.topo-container {
  position: relative;
  display: flex;
  gap: 24px;
  min-height: calc(100vh - 200px);
  padding: 16px 0;
}

.topo-svg {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  pointer-events: none;
  z-index: 0;
  overflow: visible;
}

.topo-column {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 10px;
  z-index: 1;
}

.topo-col-title {
  font-size: 13px;
  font-weight: 600;
  color: #8892b0;
  text-align: center;
  padding-bottom: 8px;
  border-bottom: 1px solid #2a3268;
  margin-bottom: 4px;
}

.topo-node {
  background: #161d45;
  border: 1px solid #2a3268;
  border-radius: 8px;
  padding: 10px 12px;
  cursor: pointer;
  transition: border-color 0.15s, box-shadow 0.15s;

  &:hover {
    border-color: #4fc3f7;
    box-shadow: 0 0 8px rgba(79, 195, 247, 0.2);
  }
}

.topo-node-title {
  font-size: 14px;
  font-weight: 600;
  color: #e0e6ff;
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 4px;
}

.topo-node-detail {
  font-size: 12px;
  color: #8892b0;
  line-height: 1.6;
}

.plc-node { border-left: 3px solid #4fc3f7; }
.mapping-node { border-left: 3px solid #66bb6a; }
.channel-node { border-left: 3px solid #ffa726; }
.channel-node.mf { border-left-color: #ffa726; }
.camera-node { border-left: 3px solid #4fc3f7; }
.model-node { border-left: 3px solid #ab47bc; }

.topo-mapping-line {
  font-size: 11px;
  color: #8892b0;
  display: flex;
  gap: 4px;
  line-height: 1.8;
}

.mapping-addr {
  font-family: 'Consolas', 'Courier New', monospace;
  color: #e0e6ff;
}

.mapping-arrow {
  color: #66bb6a;
}

.topo-empty {
  text-align: center;
  color: #555;
  font-size: 13px;
  padding: 20px 0;
}
</style>
