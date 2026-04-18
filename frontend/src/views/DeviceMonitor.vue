<template>
  <div class="page-container">
    <div class="page-header">
      <h2>软元件监控</h2>
      <div class="monitor-controls">
        <el-select v-model="selectedPrefix" style="width:120px" @change="refresh">
          <el-option v-for="p in prefixes" :key="p.value" :label="p.label" :value="p.value" />
        </el-select>
        <el-input-number v-model="startAddr" :min="0" :max="4095" size="small" style="width:120px" />
        <span style="color:#8892b0;margin:0 4px">~</span>
        <el-input-number v-model="count" :min="1" :max="256" size="small" style="width:100px" />
        <el-button :icon="Refresh" @click="refresh" :loading="loading">刷新</el-button>
        <el-switch v-model="autoRefresh" active-text="自动" @change="toggleAuto" />
      </div>
    </div>

    <!-- 位设备监控 -->
    <el-card v-if="isBitDevice">
      <template #header>{{ selectedPrefix }} 位监控 ({{ startAddr }}~{{ startAddr + count - 1 }})</template>
      <div class="bit-grid">
        <div
          v-for="(val, idx) in bitData"
          :key="idx"
          class="bit-cell"
          :class="{ on: val }"
          @click="toggleBit(idx)"
        >
          <div class="bit-addr">{{ selectedPrefix }}{{ startAddr + idx }}</div>
          <div class="bit-value">{{ val ? 'ON' : 'OFF' }}</div>
        </div>
      </div>
    </el-card>

    <!-- 字设备监控 -->
    <el-card v-else>
      <template #header>{{ selectedPrefix }} 字监控 ({{ startAddr }}~{{ startAddr + count - 1 }})</template>
      <el-table :data="wordData" stripe size="small">
        <el-table-column prop="address" label="地址" width="100" />
        <el-table-column prop="value" label="值 (DEC)" width="120" />
        <el-table-column prop="hex" label="值 (HEX)" width="120" />
        <el-table-column label="操作" width="200">
          <template #default="{ row }">
            <el-input-number
              v-model="row.newValue"
              size="small"
              style="width:110px"
              :min="-32768"
              :max="32767"
            />
            <el-button size="small" type="primary" text @click="writeWord(row)">写入</el-button>
          </template>
        </el-table-column>
        <el-table-column />
      </el-table>
    </el-card>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { Refresh } from '@element-plus/icons-vue'
import { dumpDevice, writeDevice } from '../api'
import { ElMessage } from 'element-plus'

const prefixes = [
  { value: 'EX', label: 'EX 输入位' },
  { value: 'EY', label: 'EY 输出位' },
  { value: 'VM', label: 'VM 内部位' },
  { value: 'ED', label: 'ED 输入字' },
  { value: 'EW', label: 'EW 输出字' },
  { value: 'VD', label: 'VD 内部字' },
  { value: 'SM', label: 'SM 系统位' },
  { value: 'SD', label: 'SD 系统字' },
]

const BIT_PREFIXES = ['EX', 'EY', 'VM', 'SM']

const selectedPrefix = ref('EX')
const startAddr = ref(0)
const count = ref(32)
const loading = ref(false)
const autoRefresh = ref(false)
const bitData = ref([])
const wordData = ref([])
let _timer = null

const isBitDevice = computed(() => BIT_PREFIXES.includes(selectedPrefix.value))

async function refresh() {
  loading.value = true
  try {
    const raw = await dumpDevice(selectedPrefix.value, startAddr.value, count.value)
    if (isBitDevice.value) {
      // dump 返回的是字符串或对象，按实际 API 解析
      if (Array.isArray(raw)) {
        bitData.value = raw
      } else if (typeof raw === 'string') {
        bitData.value = raw.split('').map(c => c === '1')
      } else {
        bitData.value = Array(count.value).fill(false)
      }
    } else {
      if (Array.isArray(raw)) {
        wordData.value = raw.map((v, i) => ({
          address: `${selectedPrefix.value}${startAddr.value + i}`,
          value: v,
          hex: '0x' + ((v < 0 ? v + 65536 : v) & 0xFFFF).toString(16).toUpperCase().padStart(4, '0'),
          newValue: v,
        }))
      } else {
        wordData.value = []
      }
    }
  } catch { /* ignore */ } finally { loading.value = false }
}

async function toggleBit(idx) {
  const addr = `${selectedPrefix.value}${startAddr.value + idx}`
  const current = bitData.value[idx]
  try {
    await writeDevice({ address: addr, value: !current })
    bitData.value[idx] = !current
  } catch { /* handled by interceptor */ }
}

async function writeWord(row) {
  try {
    await writeDevice({ address: row.address, value: row.newValue })
    row.value = row.newValue
    ElMessage.success(`${row.address} = ${row.newValue}`)
  } catch { /* handled */ }
}

function toggleAuto(val) {
  if (val) {
    _timer = setInterval(refresh, 500)
  } else {
    clearInterval(_timer)
    _timer = null
  }
}

onMounted(refresh)
onUnmounted(() => { if (_timer) clearInterval(_timer) })
</script>

<style scoped lang="scss">
.monitor-controls {
  display: flex;
  align-items: center;
  gap: 8px;
}

.bit-grid {
  display: grid;
  grid-template-columns: repeat(16, 1fr);
  gap: 4px;
}

.bit-cell {
  text-align: center;
  padding: 6px 2px;
  border: 1px solid #2a3268;
  border-radius: 4px;
  cursor: pointer;
  transition: all 0.15s;

  &:hover { border-color: #4fc3f7; }

  &.on {
    background: rgba(102, 187, 106, 0.2);
    border-color: #66bb6a;
  }

  .bit-addr {
    font-size: 10px;
    color: #8892b0;
  }
  .bit-value {
    font-size: 11px;
    font-weight: 600;
  }
}
</style>
