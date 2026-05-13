<template>
  <div class="page-container">
    <div class="page-header">
      <h2>检测通道</h2>
      <div class="header-actions">
        <el-button :icon="Plus" @click="openMfAdd">添加多帧通道</el-button>
        <el-button type="primary" :icon="Plus" @click="openAdd">添加单帧通道</el-button>
      </div>
    </div>

    <!-- 通道卡片 -->
    <div class="channel-grid">
      <el-card v-for="ch in channels" :key="ch.name" class="channel-card" @click="openEdit(ch)">
        <template #header>
          <div class="channel-header">
            <span>{{ ch.name }}</span>
            <div>
              <el-tag :type="ch.busy ? 'warning' : 'info'" size="small" effect="dark" style="margin-right:8px">
                {{ ch.busy ? '检测中' : '空闲' }}
              </el-tag>
              <el-button size="small" type="primary" text @click.stop="openEdit(ch)">
                <el-icon><Edit /></el-icon>
              </el-button>
              <el-button size="small" type="danger" text @click.stop="doDelete(ch.name)">
                <el-icon><Delete /></el-icon>
              </el-button>
            </div>
          </div>
        </template>
        <div class="channel-info">
          <div class="info-row">
            <span class="info-label">触发地址</span>
            <el-tag size="small" effect="plain">{{ ch.trigger_addr }}</el-tag>
          </div>
          <div class="info-row">
            <span class="info-label">相机</span>
            <span>{{ ch.camera_id || '未配置' }}</span>
          </div>
          <div class="info-row">
            <span class="info-label">模型</span>
            <span>{{ ch.model_id || '未配置' }}</span>
          </div>
          <div class="info-row">
            <span class="info-label">完成信号</span>
            <el-tag size="small" type="success" effect="plain">{{ ch.done_addr }}</el-tag>
          </div>
          <div class="info-row">
            <span class="info-label">结果输出</span>
            <el-tag size="small" type="success" effect="plain">{{ ch.result_addr }}</el-tag>
          </div>
        </div>
      </el-card>

      <!-- 空状态 -->
      <el-empty v-if="channels.length === 0" description="暂无检测通道" style="grid-column: span 3" />
    </div>

    <div class="section-header">
      <h3>多帧轮询通道</h3>
      <span>ED/EW · ACK 11/12 · RESULT 7/6/5</span>
    </div>
    <div class="channel-grid">
      <el-card v-for="mf in multiframeChannels" :key="mf.name" class="channel-card" @click="openMfEdit(mf)">
        <template #header>
          <div class="channel-header">
            <span>{{ mf.name }}</span>
            <div>
              <el-tag :type="mf.busy ? 'warning' : (mf.awaiting_reset ? 'success' : 'info')" size="small" effect="dark" style="margin-right:8px">
                {{ mf.busy ? '执行中' : (mf.awaiting_reset ? '等待复位' : '空闲') }}
              </el-tag>
              <el-button size="small" type="primary" text @click.stop="openMfEdit(mf)">
                <el-icon><Edit /></el-icon>
              </el-button>
              <el-button size="small" type="danger" text @click.stop="doMfDelete(mf.name)">
                <el-icon><Delete /></el-icon>
              </el-button>
            </div>
          </div>
        </template>
        <div class="channel-info">
          <div class="info-row">
            <span class="info-label">命令/状态</span>
            <span><el-tag size="small" effect="plain">{{ mf.cmd_addr }}</el-tag> -> <el-tag size="small" type="success" effect="plain">{{ mf.status_addr }}</el-tag></span>
          </div>
          <div class="info-row">
            <span class="info-label">相机</span>
            <span>{{ mf.camera_id || '未配置' }}</span>
          </div>
          <div class="info-row">
            <span class="info-label">进度</span>
            <span>{{ mf.frames_collected || 0 }} / {{ (mf.expected_commands || []).length || mf.frame_count || 0 }}</span>
          </div>
          <div class="info-row">
            <span class="info-label">当前命令</span>
            <span>{{ mf.last_cmd || 0 }}</span>
          </div>
          <div class="plan-tags">
            <el-tag v-for="item in mf.frame_plan || []" :key="item.command" size="small" effect="plain">
              {{ item.command }} -> {{ item.status_code }} / {{ item.model_id || mf.model_id || '无模型' }}
            </el-tag>
          </div>
        </div>
      </el-card>

      <el-empty v-if="multiframeChannels.length === 0" description="暂无多帧轮询通道" style="grid-column: span 3" />
    </div>

    <!-- 添加/编辑对话框 -->
    <el-dialog v-model="showDialog" :title="isEdit ? '编辑检测通道' : '添加检测通道'" width="560" :close-on-click-modal="false">
      <el-form :model="form" label-width="120px">
        <el-divider content-position="left">基本信息</el-divider>
        <el-form-item label="通道名称">
          <el-input v-model="form.name" placeholder="如: 工位1" :disabled="isEdit" />
        </el-form-item>
        <el-form-item label="相机">
          <el-select v-model="form.camera_id" style="width:100%"
                     :placeholder="cameras.length ? '选择相机' : '请先在「相机管理」中添加相机'">
            <el-option v-for="cam in cameras" :key="cam.camera_id"
                       :label="`${cam.camera_id} (${cam.camera_type})${cam.is_open ? '' : ' - 未打开'}`"
                       :value="cam.camera_id" />
          </el-select>
        </el-form-item>
        <el-form-item label="模型">
          <el-select v-model="form.model_id" style="width:100%"
                     :placeholder="models.length ? '选择模型' : '请先在「模型管理」中加载模型'">
            <el-option v-for="m in models" :key="m.model_id"
                       :label="`${m.model_id} (${(m.classes||[]).length}类)`"
                       :value="m.model_id" />
          </el-select>
        </el-form-item>

        <el-divider content-position="left">软元件地址</el-divider>
        <div class="addr-hint">
          EX = PLC&rarr;VModule (位输入) &nbsp;|&nbsp; EY = VModule&rarr;PLC (位输出)<br>
          ED = PLC&rarr;VModule (字输入) &nbsp;|&nbsp; EW = VModule&rarr;PLC (字输出) &nbsp;|&nbsp; VM/VD = 内部
        </div>

        <el-form-item label="触发地址">
          <div class="addr-input-row">
            <el-select v-model="form.trigger_prefix" style="width:90px" disabled>
              <el-option label="EX" value="EX" />
            </el-select>
            <el-input-number v-model="form.trigger_num" :min="0" :max="255" controls-position="right" style="flex:1" />
            <span v-if="isUsed('EX', form.trigger_num)" class="addr-warn">已占用</span>
          </div>
        </el-form-item>
        <el-form-item label="忙碌标志">
          <div class="addr-input-row">
            <el-select v-model="form.busy_prefix" style="width:90px" disabled>
              <el-option label="VM" value="VM" />
            </el-select>
            <el-input-number v-model="form.busy_num" :min="0" :max="4095" controls-position="right" style="flex:1" />
            <span v-if="isUsed('VM', form.busy_num)" class="addr-warn">已占用</span>
          </div>
        </el-form-item>
        <el-form-item label="完成信号">
          <div class="addr-input-row">
            <el-select v-model="form.done_prefix" style="width:90px" disabled>
              <el-option label="EY" value="EY" />
            </el-select>
            <el-input-number v-model="form.done_num" :min="0" :max="255" controls-position="right" style="flex:1" />
            <span v-if="isUsed('EY', form.done_num)" class="addr-warn">已占用</span>
          </div>
        </el-form-item>
        <el-form-item label="OK/NG 结果">
          <div class="addr-input-row">
            <el-select v-model="form.result_prefix" style="width:90px" disabled>
              <el-option label="EY" value="EY" />
            </el-select>
            <el-input-number v-model="form.result_num" :min="0" :max="255" controls-position="right" style="flex:1" />
            <span v-if="isUsed('EY', form.result_num)" class="addr-warn">已占用</span>
          </div>
        </el-form-item>
        <el-form-item label="缺陷数">
          <div class="addr-input-row">
            <el-select v-model="form.defect_prefix" style="width:90px" disabled>
              <el-option label="EW" value="EW" />
            </el-select>
            <el-input-number v-model="form.defect_num" :min="0" :max="255" controls-position="right" style="flex:1" />
            <span v-if="isUsed('EW', form.defect_num)" class="addr-warn">已占用</span>
          </div>
        </el-form-item>
        <el-form-item label="推理耗时">
          <div class="addr-input-row">
            <el-select v-model="form.time_prefix" style="width:90px" disabled>
              <el-option label="EW" value="EW" />
            </el-select>
            <el-input-number v-model="form.time_num" :min="0" :max="255" controls-position="right" style="flex:1" />
            <span v-if="isUsed('EW', form.time_num)" class="addr-warn">已占用</span>
          </div>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showDialog = false">取消</el-button>
        <el-button type="primary" :loading="loading" @click="doSubmit">
          {{ isEdit ? '保存' : '添加' }}
        </el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="showMfDialog" :title="mfIsEdit ? '编辑多帧轮询通道' : '添加多帧轮询通道'" width="720" :close-on-click-modal="false">
      <el-form :model="mfForm" label-width="120px">
        <el-divider content-position="left">基本信息</el-divider>
        <el-form-item label="通道名称">
          <el-input v-model="mfForm.name" placeholder="如: cam1_baseline" :disabled="mfIsEdit" />
        </el-form-item>
        <el-form-item label="相机">
          <el-select v-model="mfForm.camera_id" style="width:100%">
            <el-option v-for="cam in cameras" :key="cam.camera_id"
                       :label="`${cam.camera_id} (${cam.camera_type})${cam.is_open ? '' : ' - 未打开'}`"
                       :value="cam.camera_id" />
          </el-select>
        </el-form-item>
        <el-form-item label="默认模型">
          <el-select v-model="mfForm.model_id" clearable filterable style="width:100%" placeholder="仅作为帧计划未指定模型时的兜底">
            <el-option v-for="m in models" :key="m.model_id"
                       :label="`${m.model_id} (${(m.classes||[]).length}类)`"
                       :value="m.model_id" />
          </el-select>
        </el-form-item>

        <el-divider content-position="left">寄存器与时序</el-divider>
        <el-form-item label="命令地址">
          <el-input v-model="mfForm.cmd_addr" placeholder="ED0" />
        </el-form-item>
        <el-form-item label="状态/结果地址">
          <el-input v-model="mfForm.status_addr" placeholder="EW0" />
        </el-form-item>
        <el-form-item label="独立结果地址">
          <el-input v-model="mfForm.result_addr" placeholder="可为空；四寄存器基线留空" />
        </el-form-item>
        <el-form-item label="缺陷数/耗时">
          <div class="addr-input-row">
            <el-input v-model="mfForm.count_addr" placeholder="VD10，可为空" />
            <el-input v-model="mfForm.time_addr" placeholder="VD11，可为空" />
          </div>
        </el-form-item>
        <el-form-item label="最终结果延时">
          <el-input-number v-model="mfForm.finalize_delay_ms" :min="0" :max="5000" controls-position="right" />
          <span class="form-note">ms，给 PLC 留出读取最后一帧 ACK 的窗口</span>
        </el-form-item>

        <el-divider content-position="left">帧计划与策略</el-divider>
        <el-form-item label="帧计划 JSON">
          <el-input v-model="mfForm.frame_plan_text" type="textarea" :rows="7" class="json-editor" />
        </el-form-item>
        <el-form-item label="结果策略 JSON">
          <el-input v-model="mfForm.result_policy_text" type="textarea" :rows="6" class="json-editor" />
        </el-form-item>
        <el-form-item label="保存策略 JSON">
          <el-input v-model="mfForm.save_policy_text" type="textarea" :rows="3" class="json-editor" />
        </el-form-item>
        <el-form-item label="复位策略 JSON">
          <el-input v-model="mfForm.reset_policy_text" type="textarea" :rows="3" class="json-editor" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showMfDialog = false">取消</el-button>
        <el-button type="primary" :loading="loading" @click="doMfSubmit">
          {{ mfIsEdit ? '保存' : '添加' }}
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { Plus, Edit, Delete } from '@element-plus/icons-vue'
import {
  addChannel, listChannels, updateChannel, deleteChannel,
  addMultiframeChannel, listMultiframeChannels, updateMultiframeChannel, deleteMultiframeChannel,
  listCameras, listModels,
} from '../api'
import { ElMessage, ElMessageBox } from 'element-plus'

const channels = ref([])
const multiframeChannels = ref([])
const cameras = ref([])
const models = ref([])
const showDialog = ref(false)
const showMfDialog = ref(false)
const isEdit = ref(false)
const mfIsEdit = ref(false)
const editingName = ref('')
const editingMfName = ref('')
const loading = ref(false)

const defaultForm = () => ({
  name: '', camera_id: '', model_id: '',
  trigger_prefix: 'EX', trigger_num: 0,
  busy_prefix: 'VM', busy_num: 100,
  done_prefix: 'EY', done_num: 0,
  result_prefix: 'EY', result_num: 1,
  defect_prefix: 'EW', defect_num: 0,
  time_prefix: 'EW', time_num: 1,
})
const form = ref(defaultForm())

const defaultResultPolicy = () => ({
  defect_priority: ['CL', 'JS', 'HH', 'YW'],
  defect_code_map: { CL: 'ng_fatal', JS: 'ng_fatal', HH: 'ng_fatal', YW: 'ng_repairable' },
  result_codes: { ok: 7, ng_repairable: 6, ng_fatal: 5 },
})

const defaultMfForm = () => ({
  name: '',
  camera_id: '',
  model_id: '',
  cmd_addr: 'ED0',
  status_addr: 'EW0',
  result_addr: '',
  count_addr: '',
  time_addr: '',
  finalize_delay_ms: 50,
  frame_plan_text: prettyJson([
    { command: 1, model_id: '', status_code: 11 },
    { command: 2, model_id: '', status_code: 12 },
  ]),
  result_policy_text: prettyJson(defaultResultPolicy()),
  save_policy_text: prettyJson({ mode: 'all', image_format: 'jpg', save_json: true }),
  reset_policy_text: prettyJson({ mode: 'wait_plc_zero', clear_status_on_zero: false }),
})
const mfForm = ref(defaultMfForm())

function prettyJson(value) {
  return JSON.stringify(value ?? {}, null, 2)
}

function parseJsonField(text, fallback) {
  if (!text || !text.trim()) return fallback
  return JSON.parse(text)
}

function parseAddr(addr) {
  const m = addr.match(/^([A-Z]+)(\d+)$/)
  return m ? { prefix: m[1], num: parseInt(m[2]) } : { prefix: '', num: 0 }
}

// 收集所有已使用的地址（编辑时排除当前通道）
const usedAddresses = computed(() => {
  const set = new Set()
  channels.value.forEach(ch => {
    if (isEdit.value && ch.name === editingName.value) return
    for (const k of ['trigger_addr','busy_addr','done_addr','result_addr','defect_count_addr','inference_time_addr']) {
      if (ch[k]) set.add(ch[k].toUpperCase())
    }
  })
  multiframeChannels.value.forEach(ch => {
    if (mfIsEdit.value && ch.name === editingMfName.value) return
    for (const k of ['cmd_addr','status_addr','result_addr','count_addr','time_addr']) {
      if (ch[k]) set.add(ch[k].toUpperCase())
    }
  })
  return set
})

function isUsed(prefix, num) {
  return usedAddresses.value.has(`${prefix}${num}`)
}

async function refresh() {
  try { channels.value = await listChannels() } catch {}
  try { multiframeChannels.value = await listMultiframeChannels() } catch {}
  try { cameras.value = await listCameras() } catch {}
  try { models.value = await listModels() } catch {}
}

function openAdd() {
  isEdit.value = false
  editingName.value = ''
  form.value = defaultForm()
  showDialog.value = true
}

function openEdit(ch) {
  isEdit.value = true
  editingName.value = ch.name
  const t = parseAddr(ch.trigger_addr || 'EX0')
  const b = parseAddr(ch.busy_addr || 'VM100')
  const d = parseAddr(ch.done_addr || 'EY0')
  const r = parseAddr(ch.result_addr || 'EY1')
  const dc = parseAddr(ch.defect_count_addr || 'EW0')
  const it = parseAddr(ch.inference_time_addr || 'EW1')
  form.value = {
    name: ch.name, camera_id: ch.camera_id, model_id: ch.model_id,
    trigger_prefix: t.prefix || 'EX', trigger_num: t.num,
    busy_prefix: b.prefix || 'VM', busy_num: b.num,
    done_prefix: d.prefix || 'EY', done_num: d.num,
    result_prefix: r.prefix || 'EY', result_num: r.num,
    defect_prefix: dc.prefix || 'EW', defect_num: dc.num,
    time_prefix: it.prefix || 'EW', time_num: it.num,
  }
  showDialog.value = true
}

function buildPayload() {
  return {
    name: form.value.name,
    camera_id: form.value.camera_id,
    model_id: form.value.model_id,
    trigger_addr: form.value.trigger_prefix + form.value.trigger_num,
    busy_addr: form.value.busy_prefix + form.value.busy_num,
    done_addr: form.value.done_prefix + form.value.done_num,
    result_addr: form.value.result_prefix + form.value.result_num,
    defect_count_addr: form.value.defect_prefix + form.value.defect_num,
    inference_time_addr: form.value.time_prefix + form.value.time_num,
  }
}

async function doSubmit() {
  loading.value = true
  try {
    const payload = buildPayload()
    if (isEdit.value) {
      await updateChannel(editingName.value, payload)
      ElMessage.success(`通道 [${form.value.name}] 已更新`)
    } else {
      await addChannel(payload)
      ElMessage.success(`通道 [${form.value.name}] 已添加`)
    }
    showDialog.value = false
    refresh()
  } finally { loading.value = false }
}

async function doDelete(name) {
  await ElMessageBox.confirm(`确认删除通道 [${name}]？`, '警告', { type: 'warning' })
  await deleteChannel(name)
  ElMessage.success(`通道 [${name}] 已删除`)
  refresh()
}

function openMfAdd() {
  mfIsEdit.value = false
  editingMfName.value = ''
  mfForm.value = defaultMfForm()
  showMfDialog.value = true
}

function openMfEdit(ch) {
  mfIsEdit.value = true
  editingMfName.value = ch.name
  mfForm.value = {
    name: ch.name,
    camera_id: ch.camera_id || '',
    model_id: ch.model_id || '',
    cmd_addr: ch.cmd_addr || 'ED0',
    status_addr: ch.status_addr || 'EW0',
    result_addr: ch.result_addr || '',
    count_addr: ch.count_addr || '',
    time_addr: ch.time_addr || '',
    finalize_delay_ms: ch.finalize_delay_ms ?? 50,
    frame_plan_text: prettyJson(ch.frame_plan || []),
    result_policy_text: prettyJson(ch.result_policy || defaultResultPolicy()),
    save_policy_text: prettyJson(ch.save_policy || { mode: 'all', image_format: 'jpg', save_json: true }),
    reset_policy_text: prettyJson(ch.reset_policy || { mode: 'wait_plc_zero', clear_status_on_zero: false }),
  }
  showMfDialog.value = true
}

function buildMfPayload() {
  const framePlan = parseJsonField(mfForm.value.frame_plan_text, [])
  if (!Array.isArray(framePlan)) throw new Error('帧计划 JSON 必须是数组')
  return {
    name: mfForm.value.name,
    camera_id: mfForm.value.camera_id,
    model_id: mfForm.value.model_id,
    frame_count: framePlan.length || 0,
    cmd_addr: mfForm.value.cmd_addr,
    status_addr: mfForm.value.status_addr,
    result_addr: mfForm.value.result_addr,
    count_addr: mfForm.value.count_addr,
    time_addr: mfForm.value.time_addr,
    finalize_delay_ms: mfForm.value.finalize_delay_ms,
    frame_plan: framePlan,
    result_policy: parseJsonField(mfForm.value.result_policy_text, defaultResultPolicy()),
    save_policy: parseJsonField(mfForm.value.save_policy_text, { mode: 'all' }),
    reset_policy: parseJsonField(mfForm.value.reset_policy_text, {}),
  }
}

async function doMfSubmit() {
  loading.value = true
  try {
    const payload = buildMfPayload()
    if (mfIsEdit.value) {
      await updateMultiframeChannel(editingMfName.value, payload)
      ElMessage.success(`多帧通道 [${payload.name}] 已更新`)
    } else {
      await addMultiframeChannel(payload)
      ElMessage.success(`多帧通道 [${payload.name}] 已添加`)
    }
    showMfDialog.value = false
    refresh()
  } catch (e) {
    ElMessage.error(e?.message || '多帧通道配置保存失败')
  } finally { loading.value = false }
}

async function doMfDelete(name) {
  await ElMessageBox.confirm(`确认删除多帧通道 [${name}]？`, '警告', { type: 'warning' })
  await deleteMultiframeChannel(name)
  ElMessage.success(`多帧通道 [${name}] 已删除`)
  refresh()
}

onMounted(refresh)
</script>

<style scoped lang="scss">
.header-actions {
  display: flex;
  gap: 8px;
  align-items: center;
}

.section-header {
  display: flex;
  align-items: baseline;
  gap: 12px;
  margin: 22px 0 12px;

  h3 {
    font-size: 16px;
    font-weight: 600;
  }

  span {
    color: #8892b0;
    font-size: 12px;
    font-family: 'Consolas', 'Courier New', monospace;
  }
}

.channel-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 16px;
}

.channel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 8px;

  > span {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
}

.channel-info {
  .info-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 6px 0;
    border-bottom: 1px solid #2a3268;

    &:last-child { border-bottom: none; }

    .info-label {
      color: #8892b0;
      font-size: 13px;
    }
  }
}

.plan-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  padding-top: 8px;
}

.addr-hint {
  font-size: 12px;
  color: #8892b0;
  line-height: 1.8;
  margin-bottom: 12px;
  padding: 8px 12px;
  background: rgba(79, 195, 247, 0.05);
  border-radius: 4px;
  border-left: 3px solid #4fc3f7;
}

.addr-input-row {
  display: flex;
  align-items: center;
  gap: 8px;
  width: 100%;
}

.addr-warn {
  color: #ffa726;
  font-size: 12px;
  white-space: nowrap;
}

.form-note {
  margin-left: 10px;
  color: #8892b0;
  font-size: 12px;
}

.json-editor {
  font-family: 'Consolas', 'Courier New', monospace;
}

@media (max-width: 1280px) {
  .channel-grid {
    grid-template-columns: repeat(2, 1fr);
  }
}

@media (max-width: 860px) {
  .channel-grid {
    grid-template-columns: 1fr;
  }
}
</style>
