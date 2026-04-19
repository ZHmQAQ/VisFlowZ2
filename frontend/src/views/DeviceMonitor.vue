<template>
  <div class="page-container">
    <div class="page-header">
      <h2>变量监控</h2>
      <div class="header-actions">
        <el-switch v-model="autoRefresh" active-text="自动刷新" @change="toggleAuto" style="margin-right:12px" />
        <el-button :icon="Refresh" @click="refreshValues" :loading="loading">刷新</el-button>
        <el-button type="primary" :icon="Plus" @click="openAdd">添加变量</el-button>
      </div>
    </div>

    <el-table :data="variables" stripe size="small">
      <el-table-column prop="name" label="变量名" width="160" />
      <el-table-column label="地址" width="100">
        <template #default="{ row }">
          <el-tag size="small" effect="plain">{{ row.prefix }}{{ row.num }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="类型" width="80">
        <template #default="{ row }">
          {{ isBit(row.prefix) ? '位' : '字' }}
        </template>
      </el-table-column>
      <el-table-column label="当前值" width="180">
        <template #default="{ row }">
          <!-- 位变量：ON/OFF 开关 -->
          <template v-if="isBit(row.prefix)">
            <el-switch
              :model-value="!!row._value"
              @change="(val) => doWrite(row, val)"
              active-text="ON"
              inactive-text="OFF"
              size="small"
            />
          </template>
          <!-- 字变量：数值 + 写入 -->
          <template v-else>
            <span class="word-value">{{ row._value ?? '—' }}</span>
            <span v-if="row._value != null" class="word-hex">
              (0x{{ ((row._value < 0 ? row._value + 65536 : row._value) & 0xFFFF).toString(16).toUpperCase().padStart(4, '0') }})
            </span>
          </template>
        </template>
      </el-table-column>
      <el-table-column label="写入" width="200" v-if="hasWordVars">
        <template #default="{ row }">
          <template v-if="!isBit(row.prefix)">
            <div style="display:flex;gap:4px;align-items:center">
              <el-input-number v-model="row._newValue" size="small" style="width:120px" :min="-32768" :max="32767" controls-position="right" />
              <el-button size="small" type="primary" text @click="doWrite(row, row._newValue)">写入</el-button>
            </div>
          </template>
        </template>
      </el-table-column>
      <el-table-column prop="comment" label="备注" min-width="120" />
      <el-table-column label="操作" width="100">
        <template #default="{ row, $index }">
          <el-button size="small" type="primary" text @click="openEdit($index)">
            <el-icon><Edit /></el-icon>
          </el-button>
          <el-button size="small" type="danger" text @click="doRemove($index)">
            <el-icon><Delete /></el-icon>
          </el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-empty v-if="variables.length === 0" description="暂无变量，点击「添加变量」开始定义" />

    <!-- 添加/编辑对话框 -->
    <el-dialog v-model="showDialog" :title="editIndex >= 0 ? '编辑变量' : '添加变量'" width="440" :close-on-click-modal="false">
      <el-form :model="varForm" label-width="80px">
        <el-form-item label="变量名">
          <el-input v-model="varForm.name" placeholder="如: 拍照触发" />
        </el-form-item>
        <el-form-item label="地址">
          <div style="display:flex;gap:8px;width:100%">
            <el-select v-model="varForm.prefix" style="width:140px">
              <el-option label="EX (位入)" value="EX" />
              <el-option label="EY (位出)" value="EY" />
              <el-option label="VM (内部位)" value="VM" />
              <el-option label="SM (系统位)" value="SM" />
              <el-option label="ED (字入)" value="ED" />
              <el-option label="EW (字出)" value="EW" />
              <el-option label="VD (内部字)" value="VD" />
              <el-option label="SD (系统字)" value="SD" />
            </el-select>
            <el-input-number v-model="varForm.num" :min="0" :max="varForm.prefix === 'VM' || varForm.prefix === 'VD' ? 4095 : 255"
                             controls-position="right" style="flex:1" />
          </div>
          <div style="font-size:12px;color:#8892b0;margin-top:4px">
            {{ isBit(varForm.prefix) ? '位设备 — 可点击切换 ON/OFF' : '字设备 — 可输入数值写入' }}
          </div>
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="varForm.comment" placeholder="如: 工位1拍照触发信号" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showDialog = false">取消</el-button>
        <el-button type="primary" @click="doSaveVar">{{ editIndex >= 0 ? '保存' : '添加' }}</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { Plus, Refresh, Edit, Delete } from '@element-plus/icons-vue'
import { bulkReadDevice, writeDevice, listMappings, listChannels, listMultiframeChannels } from '../api'
import { ElMessage } from 'element-plus'

const STORAGE_KEY = 'vmodule_variables'
const BIT_PREFIXES = ['EX', 'EY', 'VM', 'SM']

const variables = ref([])
const showDialog = ref(false)
const editIndex = ref(-1)
const loading = ref(false)
const autoRefresh = ref(false)
let _timer = null

const defaultVar = () => ({ name: '', prefix: 'EX', num: 0, comment: '', _value: null, _newValue: 0 })
const varForm = ref(defaultVar())

const hasWordVars = computed(() => variables.value.some(v => !isBit(v.prefix)))

function isBit(prefix) {
  return BIT_PREFIXES.includes(prefix)
}

function loadFromStorage() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (raw) {
      const arr = JSON.parse(raw)
      variables.value = arr.map(v => ({ ...v, _value: null, _newValue: 0 }))
    }
  } catch {}
}

function saveToStorage() {
  const data = variables.value.map(({ name, prefix, num, comment }) => ({ name, prefix, num, comment }))
  localStorage.setItem(STORAGE_KEY, JSON.stringify(data))
}

async function refreshValues() {
  if (variables.value.length === 0) return
  loading.value = true
  try {
    const addrs = variables.value.map(v => `${v.prefix}${v.num}`)
    const data = await bulkReadDevice(addrs)
    variables.value.forEach(v => {
      const key = `${v.prefix}${v.num}`
      if (data[key] !== undefined && !data[key]?.error) {
        v._value = data[key]
      }
    })
  } catch {} finally { loading.value = false }
}

function openAdd() {
  editIndex.value = -1
  varForm.value = defaultVar()
  showDialog.value = true
}

function openEdit(idx) {
  editIndex.value = idx
  const v = variables.value[idx]
  varForm.value = { name: v.name, prefix: v.prefix, num: v.num, comment: v.comment }
  showDialog.value = true
}

function doSaveVar() {
  if (!varForm.value.name.trim()) {
    ElMessage.warning('请输入变量名')
    return
  }
  if (editIndex.value >= 0) {
    const v = variables.value[editIndex.value]
    v.name = varForm.value.name
    v.prefix = varForm.value.prefix
    v.num = varForm.value.num
    v.comment = varForm.value.comment
    v._value = null
  } else {
    variables.value.push({ ...varForm.value, _value: null, _newValue: 0 })
  }
  saveToStorage()
  showDialog.value = false
  refreshValues()
}

function doRemove(idx) {
  variables.value.splice(idx, 1)
  saveToStorage()
}

async function doWrite(row, val) {
  const addr = `${row.prefix}${row.num}`
  try {
    await writeDevice({ address: addr, value: val })
    row._value = val
    ElMessage.success(`${addr} = ${val}`)
  } catch {}
}

function toggleAuto(val) {
  if (_timer) { clearInterval(_timer); _timer = null }
  if (val) {
    _timer = setInterval(refreshValues, 500)
  }
}

function parseAddr(addr) {
  const match = addr.match(/^([A-Z]+)(\d+)$/)
  if (!match) return null
  return { prefix: match[1], num: parseInt(match[2]) }
}

async function autoInitFromSystem() {
  // 如果 localStorage 已有变量，不覆盖
  if (variables.value.length > 0) return

  const vars = []
  const seen = new Set()

  function addVar(name, addr, comment) {
    const p = parseAddr(addr)
    if (!p || seen.has(addr)) return
    seen.add(addr)
    vars.push({ name, prefix: p.prefix, num: p.num, comment, _value: null, _newValue: 0 })
  }

  try {
    const [mappings, channels, mfChannels] = await Promise.all([
      listMappings().catch(() => []),
      listChannels().catch(() => []),
      listMultiframeChannels().catch(() => []),
    ])

    // 从 I/O 映射中添加
    for (const m of mappings) {
      addVar(m.description || m.vmodule_addr, m.vmodule_addr, `${m.plc_name}:${m.plc_addr}`)
    }

    // 从检测通道中添加（补充映射中没有的地址，如 busy_addr）
    for (const ch of channels) {
      addVar(`${ch.name} 触发`, ch.trigger_addr, `检测通道 ${ch.name}`)
      addVar(`${ch.name} 完成`, ch.done_addr, `检测通道 ${ch.name}`)
      addVar(`${ch.name} 结果`, ch.result_addr, `检测通道 ${ch.name}`)
      if (ch.defect_count_addr) addVar(`${ch.name} 缺陷数`, ch.defect_count_addr, `检测通道 ${ch.name}`)
      if (ch.inference_time_addr) addVar(`${ch.name} 耗时`, ch.inference_time_addr, `检测通道 ${ch.name}`)
    }

    // 从多帧通道
    for (const mf of mfChannels) {
      addVar(`${mf.name} 命令`, mf.cmd_addr, `多帧通道 ${mf.name}`)
      addVar(`${mf.name} 状态`, mf.status_addr, `多帧通道 ${mf.name}`)
      addVar(`${mf.name} 结果`, mf.result_addr, `多帧通道 ${mf.name}`)
    }

    if (vars.length > 0) {
      variables.value = vars
      saveToStorage()
    }
  } catch {}
}

onMounted(async () => {
  loadFromStorage()
  await autoInitFromSystem()
  refreshValues()
})
onUnmounted(() => { if (_timer) clearInterval(_timer) })
</script>

<style scoped lang="scss">
.header-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.word-value {
  font-weight: 600;
  font-size: 14px;
}

.word-hex {
  color: #8892b0;
  font-size: 12px;
  margin-left: 4px;
}
</style>
