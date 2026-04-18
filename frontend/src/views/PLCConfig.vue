<template>
  <div class="page-container">
    <div class="page-header">
      <h2>PLC 连接管理</h2>
      <el-button type="primary" :icon="Plus" @click="openAdd">添加 PLC</el-button>
    </div>

    <el-table :data="plcList" stripe>
      <el-table-column prop="name" label="名称" width="140" />
      <el-table-column prop="host" label="IP 地址" width="160" />
      <el-table-column prop="port" label="端口" width="80" />
      <el-table-column label="状态" width="100">
        <template #default="{ row }">
          <span class="status-dot" :class="row.connected ? 'online' : 'offline'" />
          {{ row.connected ? '在线' : '离线' }}
        </template>
      </el-table-column>
      <el-table-column label="操作" width="240">
        <template #default="{ row }">
          <el-button v-if="!row.connected" size="small" type="success" text @click="doConnect(row.name)">连接</el-button>
          <el-button v-else size="small" type="warning" text @click="doDisconnect(row.name)">断开</el-button>
          <el-button size="small" type="primary" text @click="openEdit(row)">
            <el-icon><Edit /></el-icon>
          </el-button>
          <el-button size="small" type="danger" text @click="doRemove(row.name)">
            <el-icon><Delete /></el-icon>
          </el-button>
        </template>
      </el-table-column>
      <el-table-column />
    </el-table>

    <!-- 添加/编辑对话框 -->
    <el-dialog v-model="showDialog" :title="isEdit ? '编辑 PLC 配置' : '添加 PLC 连接'" width="460" :close-on-click-modal="false">
      <el-form :model="form" label-width="80px">
        <el-form-item label="名称">
          <el-input v-model="form.name" placeholder="如: PLC1" :disabled="isEdit" />
        </el-form-item>
        <el-form-item label="IP 地址">
          <el-input v-model="form.host" placeholder="192.168.1.10" />
        </el-form-item>
        <el-form-item label="端口">
          <el-input-number v-model="form.port" :min="1" :max="65535" />
        </el-form-item>
        <el-form-item label="从站号">
          <el-input-number v-model="form.unit_id" :min="0" :max="247" />
        </el-form-item>
        <el-form-item label="超时(s)">
          <el-input-number v-model="form.timeout" :min="0.1" :max="10" :step="0.1" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showDialog = false">取消</el-button>
        <el-button type="primary" :loading="loading" @click="doSubmit">
          {{ isEdit ? '保存' : '确认添加' }}
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { Plus, Delete, Edit } from '@element-plus/icons-vue'
import { addPLC, listPLC, removePLC, connectPLC, disconnectPLC, updatePLC } from '../api'
import { ElMessage, ElMessageBox } from 'element-plus'

const plcList = ref([])
const showDialog = ref(false)
const isEdit = ref(false)
const loading = ref(false)
const form = ref({ name: '', host: '', port: 502, unit_id: 1, timeout: 1.0 })

async function refresh() {
  try {
    const data = await listPLC()
    plcList.value = Object.entries(data).map(([name, info]) => ({ name, ...info }))
  } catch { /* ignore */ }
}

function openAdd() {
  isEdit.value = false
  form.value = { name: '', host: '', port: 502, unit_id: 1, timeout: 1.0 }
  showDialog.value = true
}

function openEdit(row) {
  isEdit.value = true
  form.value = { name: row.name, host: row.host, port: row.port, unit_id: row.unit_id, timeout: row.timeout }
  showDialog.value = true
}

async function doSubmit() {
  loading.value = true
  try {
    if (isEdit.value) {
      await updatePLC(form.value.name, form.value)
      ElMessage.success(`PLC [${form.value.name}] 配置已更新`)
    } else {
      await addPLC(form.value)
      ElMessage.success(`PLC [${form.value.name}] 已添加`)
    }
    showDialog.value = false
    refresh()
  } finally { loading.value = false }
}

async function doConnect(name) {
  try {
    await connectPLC(name)
    ElMessage.success(`PLC [${name}] 已连接`)
    refresh()
  } catch {}
}

async function doDisconnect(name) {
  try {
    await disconnectPLC(name)
    ElMessage.warning(`PLC [${name}] 已断开`)
    refresh()
  } catch {}
}

async function doRemove(name) {
  await ElMessageBox.confirm(`确认移除 PLC [${name}]？`, '警告', { type: 'warning' })
  await removePLC(name)
  ElMessage.success(`PLC [${name}] 已移除`)
  refresh()
}

onMounted(refresh)
</script>
