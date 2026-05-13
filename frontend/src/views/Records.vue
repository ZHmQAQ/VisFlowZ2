<template>
  <div class="page-container">
    <div class="page-header">
      <h2>检测记录</h2>
      <div style="display:flex;gap:12px;align-items:center">
        <el-select v-model="filter.is_ok" placeholder="全部" clearable style="width:100px" @change="load">
          <el-option label="OK" value="ok" />
          <el-option label="NG" value="ng" />
        </el-select>
        <el-input v-model="filter.camera_id" placeholder="相机ID" clearable style="width:140px" @clear="load" @keyup.enter="load" />
        <el-input v-model="filter.channel_name" placeholder="通道名" clearable style="width:140px" @clear="load" @keyup.enter="load" />
        <el-button type="primary" @click="load">查询</el-button>
      </div>
    </div>

    <div style="display:flex;gap:12px;margin-bottom:16px">
      <el-card shadow="never" style="width:160px">
        <div style="font-size:24px;font-weight:700;color:#4fc3f7">{{ stats.total_count || 0 }}</div>
        <div style="font-size:12px;color:#8892b0">今日总数</div>
      </el-card>
      <el-card shadow="never" style="width:160px">
        <div style="font-size:24px;font-weight:700;color:#66bb6a">{{ stats.ok_count || 0 }}</div>
        <div style="font-size:12px;color:#8892b0">OK</div>
      </el-card>
      <el-card shadow="never" style="width:160px">
        <div style="font-size:24px;font-weight:700;color:#ef5350">{{ stats.ng_count || 0 }}</div>
        <div style="font-size:12px;color:#8892b0">NG</div>
      </el-card>
      <el-card shadow="never" style="width:160px">
        <div style="font-size:24px;font-weight:700;color:#e0e6ff">{{ stats.ok_rate || 0 }}%</div>
        <div style="font-size:12px;color:#8892b0">OK 率</div>
      </el-card>
    </div>

    <el-table :data="records" stripe style="width:100%">
      <el-table-column prop="created_at" label="时间" width="180">
        <template #default="{ row }">{{ formatTime(row.created_at) }}</template>
      </el-table-column>
      <el-table-column prop="channel_name" label="通道" width="120" />
      <el-table-column prop="camera_id" label="相机" width="120" />
      <el-table-column label="结果" width="80">
        <template #default="{ row }">
          <el-tag :type="row.is_ok ? 'success' : 'danger'" size="small" effect="dark">
            {{ row.is_ok ? 'OK' : 'NG' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="defect_count" label="缺陷数" width="80" />
      <el-table-column prop="inference_ms" label="耗时(ms)" width="100" />
      <el-table-column label="图片" width="80">
        <template #default="{ row }">
          <el-button v-if="row.image_path" size="small" text type="primary" @click="viewImage(row)">查看</el-button>
          <span v-else style="color:#666">-</span>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="80">
        <template #default="{ row }">
          <el-button size="small" text type="danger" @click="remove(row)">删除</el-button>
        </template>
      </el-table-column>
      <el-table-column />
    </el-table>

    <div style="display:flex;justify-content:center;margin-top:16px">
      <el-pagination
        v-model:current-page="page"
        :page-size="pageSize"
        :total="total"
        layout="prev, pager, next, total"
        @current-change="load"
      />
    </div>

    <!-- 图片预览 -->
    <el-dialog v-model="showImage" title="检测图片" width="640">
      <img :src="imageUrl" style="width:100%;border-radius:4px" />
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { deleteRecord, getRecords, getRecordStatistics } from '../api'
import { ElMessageBox, ElMessage } from 'element-plus'

const records = ref([])
const page = ref(1)
const pageSize = 20
const total = ref(0)
const stats = ref({})
const filter = ref({ is_ok: '', camera_id: '', channel_name: '' })
const showImage = ref(false)
const imageUrl = ref('')

async function load() {
  try {
    const data = await getRecords({
      page: page.value,
      page_size: pageSize,
      ...filter.value,
    })
    records.value = data.items
    total.value = data.total
    stats.value = await getRecordStatistics({
      camera_id: filter.value.camera_id,
    })
  } catch {}
}

function formatTime(iso) {
  if (!iso) return '-'
  const d = new Date(iso)
  return d.toLocaleString('zh-CN')
}

function viewImage(row) {
  imageUrl.value = `/data/${row.image_path}`
  showImage.value = true
}

async function remove(row) {
  await ElMessageBox.confirm(`确认删除记录 #${row.id}？`, '确认', { type: 'warning' })
  await deleteRecord(row.id)
  ElMessage.success('记录已删除')
  load()
}

onMounted(load)
</script>
