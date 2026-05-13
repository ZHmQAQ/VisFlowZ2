<template>
  <div class="page-container">
    <div class="page-header">
      <h2>&#x89C4;&#x5219;&#x5F15;&#x64CE;</h2>
      <div class="header-actions"><el-button @click="openEvaluate">&#x8BC4;&#x4F30;</el-button><el-button type="primary" @click="openAdd">&#x6DFB;&#x52A0;&#x89C4;&#x5219;</el-button></div>
    </div>

    <el-table :data="rules" stripe>
      <el-table-column prop="rule_id" label="ID" width="160" />
      <el-table-column prop="name" label="&#x540D;&#x79F0;" min-width="170" />
      <el-table-column prop="trigger_source" label="&#x89E6;&#x53D1;&#x6E90;" min-width="180"><template #default="{ row }"><el-tag size="small">{{ row.trigger_source }}</el-tag></template></el-table-column>
      <el-table-column label="&#x6761;&#x4EF6;" min-width="220"><template #default="{ row }"><el-tag v-for="(condition, idx) in row.conditions || []" :key="idx" size="small" class="inline-tag">{{ condition.field }} {{ condition.operator }} {{ condition.value }}</el-tag></template></el-table-column>
      <el-table-column label="&#x52A8;&#x4F5C;" min-width="180"><template #default="{ row }"><el-tag v-for="(action, idx) in row.actions || []" :key="idx" size="small" type="success" class="inline-tag">{{ action.type }} {{ action.target || '' }}</el-tag></template></el-table-column>
      <el-table-column prop="priority" label="&#x4F18;&#x5148;&#x7EA7;" width="90" />
      <el-table-column label="&#x542F;&#x7528;" width="100"><template #default="{ row }"><el-switch v-model="row.enabled" @change="toggle(row)" /></template></el-table-column>
      <el-table-column label="&#x64CD;&#x4F5C;" width="230"><template #default="{ row }"><el-button size="small" text @click="quickEvaluate(row)">&#x6D4B;&#x8BD5;</el-button><el-button size="small" text @click="openEdit(row)">&#x7F16;&#x8F91;</el-button><el-button size="small" type="danger" text @click="remove(row)">&#x5220;&#x9664;</el-button></template></el-table-column>
    </el-table>
    <el-empty v-if="rules.length === 0" :description="'\u6682\u65e0\u89c4\u5219'" />

    <el-dialog v-model="showForm" :title="editing ? '\u7f16\u8f91\u89c4\u5219' : '\u6dfb\u52a0\u89c4\u5219'" width="760" :close-on-click-modal="false">
      <el-form :model="form" label-width="120px">
        <el-form-item label="&#x89C4;&#x5219; ID"><el-input v-model="form.rule_id" :disabled="editing" /></el-form-item>
        <el-form-item label="&#x540D;&#x79F0;"><el-input v-model="form.name" /></el-form-item>
        <el-form-item label="&#x89E6;&#x53D1;&#x6E90;"><el-input v-model="form.trigger_source" placeholder="camera_1.capture_done or *" /></el-form-item>
        <el-form-item label="&#x4F18;&#x5148;&#x7EA7;"><el-input-number v-model="form.priority" :min="0" :max="1000" /></el-form-item>
        <el-form-item label="&#x63CF;&#x8FF0;"><el-input v-model="form.description" type="textarea" :rows="2" /></el-form-item>
        <el-form-item label="&#x542F;&#x7528;"><el-switch v-model="form.enabled" /></el-form-item>
        <el-divider content-position="left">&#x6761;&#x4EF6;</el-divider>
        <div v-for="(condition, idx) in form.conditions" :key="idx" class="edit-row"><el-input v-model="condition.field" :placeholder="'\u5b57\u6bb5'" /><el-select v-model="condition.operator" style="width:120px"><el-option v-for="op in operators" :key="op" :label="op" :value="op" /></el-select><el-input v-model="condition.value" :placeholder="'\u503c\u6216 JSON'" /><el-button type="danger" text @click="form.conditions.splice(idx, 1)">&#x5220;&#x9664;</el-button></div>
        <el-button text type="primary" @click="addCondition">&#x6DFB;&#x52A0;&#x6761;&#x4EF6;</el-button>
        <el-divider content-position="left">&#x52A8;&#x4F5C;</el-divider>
        <div v-for="(action, idx) in form.actions" :key="idx" class="edit-row"><el-select v-model="action.type" style="width:160px"><el-option label="&#x53D1;&#x9001;&#x547D;&#x4EE4;" value="send_command" /><el-option label="&#x4FDD;&#x5B58;&#x56FE;&#x50CF;" value="save_image" /><el-option label="&#x89E6;&#x53D1;&#x62A5;&#x8B66;" value="trigger_alarm" /><el-option label="&#x8BB0;&#x5F55;&#x65E5;&#x5FD7;" value="log" /></el-select><el-input v-model="action.target" :placeholder="'\u76ee\u6807\u8bbe\u5907'" /><el-input v-model="action.params.data" placeholder="params.data" /><el-button type="danger" text @click="form.actions.splice(idx, 1)">&#x5220;&#x9664;</el-button></div>
        <el-button text type="primary" @click="addAction">&#x6DFB;&#x52A0;&#x52A8;&#x4F5C;</el-button>
      </el-form>
      <template #footer><el-button @click="showForm = false">&#x53D6;&#x6D88;</el-button><el-button type="primary" @click="save">&#x4FDD;&#x5B58;</el-button></template>
    </el-dialog>

    <el-dialog v-model="showEvaluate" :title="'\u8bc4\u4f30\u89c4\u5219'" width="640">
      <el-form label-width="120px"><el-form-item label="&#x89E6;&#x53D1;&#x6E90;"><el-input v-model="evalForm.trigger_source" /></el-form-item><el-form-item label="&#x6267;&#x884C;&#x52A8;&#x4F5C;"><el-switch v-model="evalForm.execute" /></el-form-item><el-form-item label="&#x4E0A;&#x4E0B;&#x6587; JSON"><el-input v-model="evalContextText" type="textarea" :rows="8" /></el-form-item></el-form>
      <el-alert v-if="evalResult" type="success" :closable="false" style="margin-top:12px"><pre>{{ evalResult }}</pre></el-alert>
      <template #footer><el-button @click="showEvaluate = false">&#x53D6;&#x6D88;</el-button><el-button type="primary" @click="evaluate">&#x8BC4;&#x4F30;</el-button></template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { addRule, deleteRule, disableRule, enableRule, evaluateRules, listRules, updateRule } from '../api'
import { ElMessage, ElMessageBox } from 'element-plus'

const operators = ['==', '!=', '>', '<', '>=', '<=', 'in', 'not_in', 'contains']
const rules = ref([])
const showForm = ref(false)
const showEvaluate = ref(false)
const editing = ref(false)
const form = ref(defaultForm())
const evalForm = ref({ trigger_source: '*', execute: false })
const evalContextText = ref('{"defect_count":1,"is_ok":false,"result":{"count":1}}')
const evalResult = ref('')

function defaultForm() { return { rule_id: '', name: '', description: '', trigger_source: '*', conditions: [{ field: 'defect_count', operator: '>', value: '0' }], actions: [{ type: 'log', target: '', params: { data: 'rule matched' } }], priority: 0, enabled: true } }
async function refresh() { rules.value = await listRules() }
function openAdd() { editing.value = false; form.value = defaultForm(); showForm.value = true }
function openEdit(row) { editing.value = true; form.value = { ...row, conditions: (row.conditions || []).map(item => ({ ...item })), actions: (row.actions || []).map(item => ({ ...item, params: { ...(item.params || {}) } })) }; showForm.value = true }
function addCondition() { form.value.conditions.push({ field: '', operator: '==', value: '' }) }
function addAction() { form.value.actions.push({ type: 'log', target: '', params: { data: '' } }) }
async function save() { const payload = { ...form.value, conditions: form.value.conditions.filter(item => item.field), actions: form.value.actions.filter(item => item.type) }; if (editing.value) await updateRule(payload.rule_id, payload); else await addRule(payload); ElMessage.success('\u89c4\u5219\u5df2\u4fdd\u5b58'); showForm.value = false; refresh() }
async function toggle(row) { if (row.enabled) await enableRule(row.rule_id); else await disableRule(row.rule_id); ElMessage.success('\u89c4\u5219\u5df2\u66f4\u65b0') }
async function remove(row) { await ElMessageBox.confirm(`\u786e\u8ba4\u5220\u9664\u89c4\u5219 [${row.rule_id}]?`, '\u786e\u8ba4', { type: 'warning' }); await deleteRule(row.rule_id); ElMessage.success('\u89c4\u5219\u5df2\u5220\u9664'); refresh() }
function openEvaluate() { evalResult.value = ''; showEvaluate.value = true }
async function quickEvaluate(row) { const result = await evaluateRules({ trigger_source: row.trigger_source, execute: false, context: { defect_count: 1, is_ok: false, result: { count: 1 } } }); ElMessage.success(`\u547d\u4e2d ${result.matched} \u4e2a\u52a8\u4f5c`) }
async function evaluate() { let context; try { context = JSON.parse(evalContextText.value || '{}') } catch { ElMessage.error('\u4e0a\u4e0b\u6587 JSON \u65e0\u6548'); return } const result = await evaluateRules({ ...evalForm.value, context }); evalResult.value = JSON.stringify(result, null, 2) }
onMounted(refresh)
</script>

<style scoped lang="scss">
.header-actions { display: flex; gap: 8px; }
.inline-tag { margin: 2px; }
.edit-row { display: grid; grid-template-columns: minmax(140px, 1fr) auto minmax(140px, 1fr) auto; gap: 8px; margin-bottom: 8px; align-items: center; }
pre { margin: 0; white-space: pre-wrap; max-height: 220px; overflow: auto; }
</style>
