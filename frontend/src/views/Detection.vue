<template>
  <div class="page-container">
    <div class="page-header">
      <h2>检测通道</h2>
      <el-button type="primary" :icon="Plus" @click="showAdd = true">添加通道</el-button>
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
        <el-form-item label="相机 ID">
          <el-input v-model="form.camera_id" placeholder="如: cam1" />
        </el-form-item>
        <el-form-item label="模型 ID">
          <el-input v-model="form.model_id" placeholder="如: yolo_default" />
        </el-form-item>

        <el-divider content-position="left">软元件地址</el-divider>
        <el-form-item label="触发地址 (EX)">
          <el-input v-model="form.trigger_addr" placeholder="EX0" />
        </el-form-item>
        <el-form-item label="忙碌标志 (VM)">
          <el-input v-model="form.busy_addr" placeholder="VM100" />
        </el-form-item>
        <el-form-item label="完成信号 (EY)">
          <el-input v-model="form.done_addr" placeholder="EY0" />
        </el-form-item>
        <el-form-item label="OK/NG (EY)">
          <el-input v-model="form.result_addr" placeholder="EY1" />
        </el-form-item>
        <el-form-item label="缺陷数 (EW)">
          <el-input v-model="form.defect_count_addr" placeholder="EW0" />
        </el-form-item>
        <el-form-item label="推理耗时 (EW)">
          <el-input v-model="form.inference_time_addr" placeholder="EW1" />
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
import { ref, onMounted } from 'vue'
import { Plus } from '@element-plus/icons-vue'
import { addChannel, listChannels } from '../api'
import { ElMessage } from 'element-plus'

const channels = ref([])
const showAdd = ref(false)
const loading = ref(false)
const form = ref({
  name: '', camera_id: '', model_id: '',
  trigger_addr: 'EX0', busy_addr: 'VM100',
  done_addr: 'EY0', result_addr: 'EY1',
  defect_count_addr: 'EW0', inference_time_addr: 'EW1',
})

async function refresh() {
  try { channels.value = await listChannels() } catch {}
}

async function doAdd() {
  loading.value = true
  try {
    await addChannel(form.value)
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
</style>
