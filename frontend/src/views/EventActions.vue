<template>
  <div class="page-container">
    <div class="page-header">
      <h2>&#x4E8B;&#x4EF6;&#x52A8;&#x4F5C;</h2>
      <div class="header-actions">
        <el-button @click="openGenerate">&#x4ECE;&#x6A21;&#x677F;&#x751F;&#x6210;</el-button>
        <el-button type="primary" @click="openAdd">&#x6DFB;&#x52A0;&#x6620;&#x5C04;</el-button>
      </div>
    </div>

    <el-table :data="mappings" stripe>
      <el-table-column prop="mapping_id" label="ID" width="170" />
      <el-table-column prop="name" label="&#x540D;&#x79F0;" min-width="180" />
      <el-table-column label="&#x4E8B;&#x4EF6;" min-width="180">
        <template #default="{ row }">
          <el-tag size="small">{{ labelOf(meta.events, row.event_type) }}</el-tag>
          <span class="source">{{ row.event_source || '*' }}</span>
        </template>
      </el-table-column>
      <el-table-column label="&#x52A8;&#x4F5C;" min-width="190">
        <template #default="{ row }">
          <el-tag size="small" type="success">{{ labelOf(meta.actions, row.action_type) }}</el-tag>
          <span class="source">{{ row.action_target || '-' }}</span>
        </template>
      </el-table-column>
      <el-table-column prop="order_index" label="&#x987A;&#x5E8F;" width="90" />
      <el-table-column label="&#x542F;&#x7528;" width="100">
        <template #default="{ row }"><el-switch v-model="row.enabled" @change="toggle(row)" /></template>
      </el-table-column>
      <el-table-column label="&#x64CD;&#x4F5C;" width="250">
        <template #default="{ row }">
          <el-button size="small" text @click="test(row)">&#x6D4B;&#x8BD5;</el-button>
          <el-button size="small" text @click="openEdit(row)">&#x7F16;&#x8F91;</el-button>
          <el-button size="small" type="danger" text @click="remove(row)">&#x5220;&#x9664;</el-button>
        </template>
      </el-table-column>
    </el-table>
    <el-empty v-if="mappings.length === 0" :description="'\u6682\u65e0\u4e8b\u4ef6\u52a8\u4f5c\u6620\u5c04'" />

    <el-dialog v-model="showForm" :title="editing ? '\u7f16\u8f91\u6620\u5c04' : '\u6dfb\u52a0\u6620\u5c04'" width="640" :close-on-click-modal="false">
      <el-form :model="form" label-width="120px">
        <el-form-item label="&#x6620;&#x5C04; ID"><el-input v-model="form.mapping_id" :disabled="editing" /></el-form-item>
        <el-form-item label="&#x540D;&#x79F0;"><el-input v-model="form.name" /></el-form-item>
        <el-form-item label="&#x4E8B;&#x4EF6;"><el-select v-model="form.event_type" style="width:100%"><el-option v-for="item in meta.events" :key="item.value" :label="item.label" :value="item.value" /></el-select></el-form-item>
        <el-form-item label="&#x6765;&#x6E90;"><el-input v-model="form.event_source" :placeholder="'\u002a \u6216\u76f8\u673a/\u8bbe\u5907 ID'" /></el-form-item>
        <el-form-item label="&#x52A8;&#x4F5C;"><el-select v-model="form.action_type" style="width:100%"><el-option v-for="item in meta.actions" :key="item.value" :label="item.label" :value="item.value" /></el-select></el-form-item>
        <el-form-item label="&#x76EE;&#x6807;"><el-input v-model="form.action_target" :placeholder="'\u8bbe\u5907 ID\u3001\u76f8\u673a ID \u6216\u5730\u5740'" /></el-form-item>
        <el-form-item label="&#x53C2;&#x6570; JSON"><el-input v-model="paramsText" type="textarea" :rows="5" /></el-form-item>
        <el-form-item label="&#x987A;&#x5E8F;"><el-input-number v-model="form.order_index" :min="0" /></el-form-item>
        <el-form-item label="&#x542F;&#x7528;"><el-switch v-model="form.enabled" /></el-form-item>
      </el-form>
      <template #footer><el-button @click="showForm = false">&#x53D6;&#x6D88;</el-button><el-button type="primary" @click="save">&#x4FDD;&#x5B58;</el-button></template>
    </el-dialog>

    <el-dialog v-model="showGenerate" :title="'\u4ece\u6a21\u677f\u751f\u6210'" width="620">
      <el-form label-width="120px">
        <el-form-item label="&#x6A21;&#x677F;"><el-select v-model="generateForm.template" style="width:100%"><el-option v-for="tpl in templates" :key="tpl.name" :label="tpl.label" :value="tpl.name" /></el-select></el-form-item>
        <el-form-item label="&#x76F8;&#x673A; ID"><el-input v-model="generateForm.camera_id" placeholder="camera_1" /></el-form-item>
        <el-form-item label="&#x54CD;&#x5E94;&#x8BBE;&#x5907;"><el-input v-model="generateForm.response_device" :placeholder="'\u8bbe\u5907\u6216 PLC \u6620\u5c04\u76ee\u6807'" /></el-form-item>
        <el-form-item label="&#x66FF;&#x6362;&#x73B0;&#x6709;"><el-switch v-model="generateForm.replace" /></el-form-item>
      </el-form>
      <template #footer><el-button @click="showGenerate = false">&#x53D6;&#x6D88;</el-button><el-button type="primary" @click="generate">&#x751F;&#x6210;</el-button></template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { addEventAction, deleteEventAction, generateEventActions, getEventActionMeta, listEventActions, listEventActionTemplates, testEventAction, updateEventAction } from '../api'
import { ElMessage, ElMessageBox } from 'element-plus'

const mappings = ref([])
const templates = ref([])
const meta = ref({ events: [], actions: [], value_types: [] })
const showForm = ref(false)
const showGenerate = ref(false)
const editing = ref(false)
const paramsText = ref('{"value_type":"ack"}')
const form = ref(defaultForm())
const generateForm = ref({ template: 'standard_inspection', camera_id: '', response_device: '', replace: true })

function defaultForm() { return { mapping_id: '', name: '', event_type: 'on_cam_ok', event_source: '*', event_filter: {}, action_type: 'write_register', action_target: '', action_params: { value_type: 'ack' }, order_index: 10, enabled: true } }
function labelOf(items, value) { return items.find(item => item.value === value)?.label || value }
async function refresh() { mappings.value = await listEventActions() }
function openAdd() { editing.value = false; form.value = defaultForm(); paramsText.value = JSON.stringify(form.value.action_params, null, 2); showForm.value = true }
function openEdit(row) { editing.value = true; form.value = { ...row, event_filter: row.event_filter || {}, action_params: row.action_params || {} }; paramsText.value = JSON.stringify(form.value.action_params, null, 2); showForm.value = true }
async function save() { let params; try { params = JSON.parse(paramsText.value || '{}') } catch { ElMessage.error('\u53c2\u6570 JSON \u65e0\u6548'); return } const payload = { ...form.value, action_params: params }; if (editing.value) await updateEventAction(payload.mapping_id, payload); else await addEventAction(payload); ElMessage.success('\u6620\u5c04\u5df2\u4fdd\u5b58'); showForm.value = false; refresh() }
async function toggle(row) { await updateEventAction(row.mapping_id, { enabled: row.enabled }); ElMessage.success('\u6620\u5c04\u5df2\u66f4\u65b0') }
async function remove(row) { await ElMessageBox.confirm(`\u786e\u8ba4\u5220\u9664\u6620\u5c04 [${row.mapping_id}]?`, '\u786e\u8ba4', { type: 'warning' }); await deleteEventAction(row.mapping_id); ElMessage.success('\u6620\u5c04\u5df2\u5220\u9664'); refresh() }
async function test(row) { const res = await testEventAction({ event_type: row.event_type, event_source: row.event_source || '*', context: { frame_index: 0, ack_base: 16, result_code: 1 } }); ElMessage.success(`\u547d\u4e2d ${res.matched} \u6761\u6620\u5c04`) }
function openGenerate() { showGenerate.value = true }
async function generate() { await generateEventActions({ template: generateForm.value.template, replace: generateForm.value.replace, cameras: [{ camera_id: generateForm.value.camera_id, response_device: generateForm.value.response_device }] }); ElMessage.success('\u6620\u5c04\u5df2\u751f\u6210'); showGenerate.value = false; refresh() }
onMounted(async () => { meta.value = await getEventActionMeta(); templates.value = await listEventActionTemplates(); refresh() })
</script>

<style scoped lang="scss">
.header-actions { display: flex; gap: 8px; }
.source { margin-left: 8px; color: #8892b0; font-size: 12px; }
</style>
