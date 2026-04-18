<template>
  <div class="page-container">
    <div class="page-header">
      <h2>检测通道</h2>
      <el-button type="primary" :icon="Plus" @click="openAdd">添加通道</el-button>
    </div>

    <!-- 通道卡片 -->
    <div class="channel-grid">
      <el-card v-for="ch in channels" :key="ch.name" class="channel-card">
        <template #header>
          <div class="channel-header">
            <span>{{ ch.name }}</span>
            <el-tag :type="ch.busy ? 'warning' : 'info'" size="small" effect="dark">
              {{ ch.busy ? '检测中' : '空闲' }}
            </el-tag>
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

    <!-- 添加对话框 -->
    <el-dialog v-model="showAdd" title="添加检测通道" width="560" :close-on-click-modal="false">
      <el-form :model="form" label-width="120px">
        <el-divider content-position="left">基本信息</el-divider>
        <el-form-item label="通道名称">
          <el-input v-model="form.name" placeholder="如: 工位1" />
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
        <el-button @click="showAdd = false">取消</el-button>
        <el-button type="primary" :loading="loading" @click="doAdd">添加</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { Plus } from '@element-plus/icons-vue'
import { addChannel, listChannels, listCameras, listModels } from '../api'
import { ElMessage } from 'element-plus'

const channels = ref([])
const cameras = ref([])
const models = ref([])
const showAdd = ref(false)
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

// 收集所有已使用的地址
const usedAddresses = computed(() => {
  const set = new Set()
  channels.value.forEach(ch => {
    for (const k of ['trigger_addr','busy_addr','done_addr','result_addr','defect_count_addr','inference_time_addr']) {
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
  try { cameras.value = await listCameras() } catch {}
  try { models.value = await listModels() } catch {}
}

function openAdd() {
  form.value = defaultForm()
  showAdd.value = true
}

async function doAdd() {
  loading.value = true
  try {
    const payload = {
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
    await addChannel(payload)
    ElMessage.success(`通道 [${form.value.name}] 已添加`)
    showAdd.value = false
    refresh()
  } finally { loading.value = false }
}

onMounted(refresh)
</script>

<style scoped lang="scss">
.channel-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 16px;
}

.channel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
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
</style>
