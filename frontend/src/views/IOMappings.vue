<template>
  <div class="page-container">
    <div class="page-header">
      <h2>I/O 映射配置</h2>
      <div>
        <el-button type="primary" :icon="Plus" @click="showAdd = true">添加映射</el-button>
        <el-button type="danger" @click="doClear">清空全部</el-button>
      </div>
    </div>

    <el-table :data="mappings" stripe>
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
    </el-table>

    <div style="margin-top:12px;color:#8892b0;font-size:13px;">
      共 {{ mappings.length }} 条映射 | ← 输入(PLC→VModule) | → 输出(VModule→PLC)
    </div>

    <!-- 添加对话框 -->
    <el-dialog v-model="showAdd" title="添加 I/O 映射" width="500" :close-on-click-modal="false">
      <el-form :model="form" label-width="110px">
        <el-form-item label="PLC 名称">
          <el-input v-model="form.plc_name" placeholder="PLC1" />
        </el-form-item>
        <el-form-item label="PLC 地址">
          <el-input v-model="form.plc_addr" placeholder="如 M100, D200, X0">
            <template #prepend>信捷</template>
          </el-input>
        </el-form-item>
        <el-form-item label="VModule 地址">
          <el-input v-model="form.vmodule_addr" placeholder="如 EX0, EY1, ED0, EW0">
            <template #prepend>VModule</template>
          </el-input>
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="form.description" placeholder="如: 拍照触发信号" />
        </el-form-item>
      </el-form>

      <el-divider content-position="left">快速参考</el-divider>
      <div style="font-size:12px;color:#8892b0;line-height:2;">
        <b>输入(PLC→VModule):</b> EX(位) / ED(字) &nbsp;
        <b>输出(VModule→PLC):</b> EY(位) / EW(字)<br>
        <b>PLC 地址:</b> M(辅助继电器) D(数据寄存器) X/Y(输入/输出)
      </div>

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
import { addMapping, listMappings, clearMappings } from '../api'
import { ElMessage, ElMessageBox } from 'element-plus'

const mappings = ref([])
const showAdd = ref(false)
const loading = ref(false)
const form = ref({ plc_name: 'PLC1', plc_addr: '', vmodule_addr: '', description: '' })

async function refresh() {
  try { mappings.value = await listMappings() } catch {}
}

async function doAdd() {
  loading.value = true
  try {
    await addMapping(form.value)
    ElMessage.success('映射已添加')
    showAdd.value = false
    form.value = { ...form.value, plc_addr: '', vmodule_addr: '', description: '' }
    refresh()
  } finally { loading.value = false }
}

async function doClear() {
  await ElMessageBox.confirm('确认清空所有映射？此操作不可撤销。', '警告', { type: 'warning' })
  await clearMappings()
  ElMessage.success('映射已清空')
  refresh()
}

onMounted(refresh)
</script>
