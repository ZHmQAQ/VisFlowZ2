<template>
  <div class="page-container">
    <div class="page-header">
      <h2>I/O 映射配置</h2>
      <div>
        <el-button type="primary" :icon="Plus" @click="openAdd">添加映射</el-button>
        <el-button type="danger" @click="doClear">清空全部</el-button>
      </div>
    </div>

    <el-table :data="mappings" stripe @row-click="openEdit" :row-class-name="rowClass">
      <el-table-column label="启用" width="70" align="center">
        <template #default="{ row }">
          <el-switch :model-value="row.enabled" size="small"
                     @click.stop @change="doToggle(row)" />
        </template>
      </el-table-column>
      <el-table-column prop="vmodule_addr" label="VModule 地址" width="140">
        <template #default="{ row }">
          <el-tag effect="dark" :type="row.vmodule_addr.startsWith('EX') || row.vmodule_addr.startsWith('ED') ? 'warning' : 'success'" size="small">
            {{ row.vmodule_addr }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="方向" width="60" align="center">
        <template #default="{ row }">
          {{ row.vmodule_addr.startsWith('EX') || row.vmodule_addr.startsWith('ED') ? '←' : '→' }}
        </template>
      </el-table-column>
      <el-table-column prop="plc_addr" label="PLC 地址" width="120" />
      <el-table-column prop="plc_name" label="PLC 名称" width="120" />
      <el-table-column prop="description" label="描述" />
      <el-table-column label="操作" width="80" align="center">
        <template #default="{ row }">
          <el-button size="small" type="danger" text @click.stop="doDelete(row)">
            <el-icon><Delete /></el-icon>
          </el-button>
        </template>
      </el-table-column>
    </el-table>

    <div style="margin-top:12px;color:#8892b0;font-size:13px;">
      共 {{ mappings.length }} 条映射 | ← 输入(PLC→VModule) | → 输出(VModule→PLC) | 点击行可编辑 | 支持一对多映射
    </div>

    <!-- 添加/编辑对话框 -->
    <el-dialog v-model="showDialog" :title="isEdit ? '编辑 I/O 映射' : '添加 I/O 映射'" width="500" :close-on-click-modal="false">
      <el-form :model="form" label-width="110px">
        <el-form-item label="PLC 名称">
          <el-select v-model="form.plc_name" style="width:100%"
                     :placeholder="plcOptions.length ? '选择PLC' : '请先在「PLC连接」中添加PLC'">
            <el-option v-for="p in plcOptions" :key="p.name"
                       :label="`${p.name} (${p.host})`" :value="p.name" />
          </el-select>
        </el-form-item>
        <el-form-item label="PLC 地址">
          <el-input v-model="form.plc_addr" placeholder="如 M100, D200, X0">
            <template #prepend>信捷</template>
          </el-input>
        </el-form-item>
        <el-form-item label="VModule 地址">
          <div class="addr-input-row">
            <el-select v-model="form.vmodule_prefix" style="width:130px">
              <el-option label="EX (位入)" value="EX" />
              <el-option label="EY (位出)" value="EY" />
              <el-option label="ED (字入)" value="ED" />
              <el-option label="EW (字出)" value="EW" />
            </el-select>
            <el-input-number v-model="form.vmodule_num" :min="0" :max="255" controls-position="right" style="flex:1" />
          </div>
          <div class="addr-direction-hint">
            {{ ['EX','ED'].includes(form.vmodule_prefix)
               ? '← 输入方向：PLC 写入 → VModule 读取'
               : '→ 输出方向：VModule 写入 → PLC 读取' }}
          </div>
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="form.description" placeholder="如: 拍照触发信号" />
        </el-form-item>
      </el-form>

      <el-divider content-position="left">快速参考</el-divider>
      <div style="font-size:12px;color:#8892b0;line-height:2;">
        <b>输入(PLC→VModule):</b> EX(位) / ED(字) &nbsp;
        <b>输出(VModule→PLC):</b> EY(位) / EW(字)<br>
        <b>PLC 地址:</b> M(辅助继电器) D(数据寄存器) X/Y(输入/输出)<br>
        同一 VModule 地址可映射到多个 PLC 地址（一对多）
      </div>

      <template #footer>
        <el-button @click="showDialog = false">取消</el-button>
        <el-button type="primary" :loading="loading" @click="doSubmit">{{ isEdit ? '保存' : '添加' }}</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { Plus, Delete } from '@element-plus/icons-vue'
import { addMapping, listMappings, clearMappings, deleteMapping, updateMapping, toggleMapping, listPLC } from '../api'
import { ElMessage, ElMessageBox } from 'element-plus'

const mappings = ref([])
const plcOptions = ref([])
const showDialog = ref(false)
const loading = ref(false)
const isEdit = ref(false)
const editingId = ref(null)

const defaultForm = () => ({
  plc_name: '', plc_addr: '',
  vmodule_prefix: 'EX', vmodule_num: 0,
  description: '',
})
const form = ref(defaultForm())

async function refresh() {
  try { mappings.value = await listMappings() } catch {}
  try {
    const data = await listPLC()
    plcOptions.value = Object.entries(data).map(([name, info]) => ({ name, host: info.host }))
  } catch {}
}

function parseAddr(addr) {
  const match = addr.match(/^(EX|EY|ED|EW)(\d+)$/i)
  if (match) return { prefix: match[1].toUpperCase(), num: parseInt(match[2]) }
  return { prefix: 'EX', num: 0 }
}

function openAdd() {
  isEdit.value = false
  editingId.value = null
  const f = defaultForm()
  if (plcOptions.value.length) f.plc_name = plcOptions.value[0].name
  form.value = f
  showDialog.value = true
}

function openEdit(row) {
  isEdit.value = true
  editingId.value = row.id
  const parsed = parseAddr(row.vmodule_addr)
  form.value = {
    plc_name: row.plc_name,
    plc_addr: row.plc_addr,
    vmodule_prefix: parsed.prefix,
    vmodule_num: parsed.num,
    description: row.description,
  }
  showDialog.value = true
}

async function doSubmit() {
  loading.value = true
  try {
    const payload = {
      plc_name: form.value.plc_name,
      plc_addr: form.value.plc_addr,
      vmodule_addr: form.value.vmodule_prefix + form.value.vmodule_num,
      description: form.value.description,
    }
    if (isEdit.value) {
      await updateMapping(editingId.value, payload)
      ElMessage.success('映射已更新')
    } else {
      await addMapping(payload)
      ElMessage.success('映射已添加')
    }
    showDialog.value = false
    refresh()
  } finally { loading.value = false }
}

async function doToggle(row) {
  try {
    const res = await toggleMapping(row.id)
    row.enabled = res.enabled
  } catch {}
}

function rowClass({ row }) {
  return row.enabled === false ? 'row-disabled' : ''
}

async function doDelete(row) {
  await ElMessageBox.confirm(`确认删除映射 [${row.vmodule_addr} ↔ ${row.plc_addr}]？`, '确认', { type: 'warning' })
  await deleteMapping(row.id)
  ElMessage.success('映射已删除')
  refresh()
}

async function doClear() {
  await ElMessageBox.confirm('确认清空所有映射？此操作不可撤销。', '警告', { type: 'warning' })
  await clearMappings()
  ElMessage.success('映射已清空')
  refresh()
}

onMounted(refresh)
</script>

<style scoped lang="scss">
.addr-input-row {
  display: flex;
  align-items: center;
  gap: 8px;
  width: 100%;
}

.addr-direction-hint {
  font-size: 12px;
  color: #8892b0;
  margin-top: 4px;
}

:deep(.el-table__row) {
  cursor: pointer;
}

:deep(.row-disabled) {
  opacity: 0.45;
}
</style>
