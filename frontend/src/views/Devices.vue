<template>
  <div class="page-container">
    <div class="page-header">
      <h2>&#x8BBE;&#x5907;&#x7BA1;&#x7406;</h2>
      <el-button type="primary" @click="openAdd">&#x6DFB;&#x52A0;&#x8BBE;&#x5907;</el-button>
    </div>

    <el-table :data="devices" stripe>
      <el-table-column prop="device_id" label="ID" width="150" />
      <el-table-column prop="name" label="&#x540D;&#x79F0;" width="160" />
      <el-table-column prop="type" label="&#x7C7B;&#x578B;" width="120">
        <template #default="{ row }"><el-tag size="small">{{ typeLabel(row.type) }}</el-tag></template>
      </el-table-column>
      <el-table-column label="&#x8FDE;&#x63A5;" min-width="220">
        <template #default="{ row }">
          <span v-if="row.type === 'serial'">{{ row.connection?.port || row.port }} @ {{ row.connection?.baudrate || row.baudrate }}</span>
          <span v-else>{{ row.connection?.host || row.host }}:{{ row.connection?.port || row.port }}</span>
        </template>
      </el-table-column>
      <el-table-column label="&#x72B6;&#x6001;" width="110">
        <template #default="{ row }">
          <el-tag :type="row.is_connected ? 'success' : 'info'" size="small" effect="dark">
            {{ row.is_connected ? '\u5df2\u8fde\u63a5' : '\u672a\u8fde\u63a5' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="&#x64CD;&#x4F5C;" width="320">
        <template #default="{ row }">
          <el-button size="small" type="success" text @click="connect(row)" :disabled="row.is_connected">&#x8FDE;&#x63A5;</el-button>
          <el-button size="small" type="warning" text @click="disconnect(row)" :disabled="!row.is_connected">&#x65AD;&#x5F00;</el-button>
          <el-button size="small" text @click="openSend(row)">&#x53D1;&#x9001;</el-button>
          <el-button size="small" text @click="openEdit(row)">&#x7F16;&#x8F91;</el-button>
          <el-button size="small" type="danger" text @click="remove(row)">&#x5220;&#x9664;</el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-dialog v-model="showForm" :title="editing ? '\u7f16\u8f91\u8bbe\u5907' : '\u6dfb\u52a0\u8bbe\u5907'" width="520">
      <el-form :model="form" label-width="90px">
        <el-form-item label="&#x8BBE;&#x5907; ID"><el-input v-model="form.device_id" :disabled="editing" /></el-form-item>
        <el-form-item label="&#x540D;&#x79F0;"><el-input v-model="form.name" /></el-form-item>
        <el-form-item label="&#x7C7B;&#x578B;">
          <el-select v-model="form.type" style="width:100%">
            <el-option label="TCP 客户端" value="tcp" />
            <el-option label="TCP 服务端" value="tcp_server" />
            <el-option label="串口设备" value="serial" />
          </el-select>
        </el-form-item>
        <template v-if="form.type === 'serial'">
          <el-form-item label="&#x4E32;&#x53E3;"><el-input v-model="form.connection.port" /></el-form-item>
          <el-form-item label="&#x6CE2;&#x7279;&#x7387;"><el-input-number v-model="form.connection.baudrate" :min="1200" :step="1200" /></el-form-item>
        </template>
        <template v-else>
          <el-form-item label="&#x4E3B;&#x673A;"><el-input v-model="form.connection.host" /></el-form-item>
          <el-form-item label="&#x7AEF;&#x53E3;"><el-input-number v-model="form.connection.port" :min="1" :max="65535" /></el-form-item>
        </template>
        <el-form-item label="&#x534F;&#x8BAE;"><el-input v-model="form.protocol" placeholder="如 raw / modbus" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showForm = false">&#x53D6;&#x6D88;</el-button>
        <el-button type="primary" @click="save">&#x4FDD;&#x5B58;</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="showSend" :title="'\u53d1\u9001\u6570\u636e'" width="460">
      <el-form label-width="90px">
        <el-form-item label="&#x8BBE;&#x5907;">{{ sendTarget?.device_id }}</el-form-item>
        <el-form-item label="HEX"><el-switch v-model="sendForm.hex" /></el-form-item>
        <el-form-item label="&#x6570;&#x636E;"><el-input v-model="sendForm.data" type="textarea" :rows="4" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showSend = false">&#x53D6;&#x6D88;</el-button>
        <el-button type="primary" @click="send">&#x53D1;&#x9001;</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import {
  addDevice, connectDevice, deleteDevice, disconnectDevice,
  listDevices, sendDevice, updateDevice,
} from '../api'
import { ElMessage, ElMessageBox } from 'element-plus'

const devices = ref([])
const showForm = ref(false)
const showSend = ref(false)
const editing = ref(false)
const sendTarget = ref(null)
const sendForm = ref({ data: '', hex: true })
const form = ref(defaultForm())

function typeLabel(type) {
  return ({ tcp: 'TCP \u5ba2\u6237\u7aef', tcp_server: 'TCP \u670d\u52a1\u7aef', serial: '\u4e32\u53e3' })[type] || type
}

function defaultForm() {
  return {
    device_id: '',
    name: '',
    type: 'tcp',
    connection: { host: '127.0.0.1', port: 502, baudrate: 9600 },
    protocol: 'raw',
    enabled: true,
  }
}

async function refresh() { devices.value = await listDevices() }
function openAdd() { editing.value = false; form.value = defaultForm(); showForm.value = true }
function openEdit(row) {
  editing.value = true
  form.value = {
    device_id: row.device_id,
    name: row.name,
    type: row.type,
    connection: { ...(row.connection || {}) },
    protocol: row.protocol || 'raw',
    enabled: row.enabled !== false,
  }
  showForm.value = true
}

async function save() {
  if (editing.value) await updateDevice(form.value.device_id, form.value)
  else await addDevice(form.value)
  ElMessage.success('\u8bbe\u5907\u5df2\u4fdd\u5b58')
  showForm.value = false
  refresh()
}

async function connect(row) {
  await connectDevice(row.device_id)
  ElMessage.success('\u8bbe\u5907\u5df2\u8fde\u63a5')
  refresh()
}

async function disconnect(row) {
  await disconnectDevice(row.device_id)
  ElMessage.warning('\u8bbe\u5907\u5df2\u65ad\u5f00')
  refresh()
}

async function remove(row) {
  await ElMessageBox.confirm(`\u786e\u8ba4\u5220\u9664\u8bbe\u5907 [${row.device_id}]\uff1f`, '\u786e\u8ba4', { type: 'warning' })
  await deleteDevice(row.device_id)
  ElMessage.success('\u8bbe\u5907\u5df2\u5220\u9664')
  refresh()
}

function openSend(row) {
  sendTarget.value = row
  sendForm.value = { data: '', hex: true }
  showSend.value = true
}

async function send() {
  await sendDevice(sendTarget.value.device_id, sendForm.value)
  ElMessage.success('\u6570\u636e\u5df2\u53d1\u9001')
  showSend.value = false
}

onMounted(refresh)
</script>
