<template>
  <div class="page-container">
    <div class="page-header">
      <h2>I/O 映射配置</h2>
      <div>
        <el-button type="primary" :icon="Plus" @click="openAdd">添加映射</el-button>
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
          <span v-if="usedVModuleAddrs.has(form.vmodule_prefix + form.vmodule_num)" class="addr-warn">
            该VModule地址已被映射
          </span>
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
import { ref, computed, onMounted } from 'vue'
import { Plus } from '@element-plus/icons-vue'
import { addMapping, listMappings, clearMappings, listPLC } from '../api'
import { ElMessage, ElMessageBox } from 'element-plus'

const mappings = ref([])
const plcOptions = ref([])
const showAdd = ref(false)
const loading = ref(false)

const defaultForm = () => ({
  plc_name: '', plc_addr: '',
  vmodule_prefix: 'EX', vmodule_num: 0,
  description: '',
})
const form = ref(defaultForm())

const usedVModuleAddrs = computed(() =>
  new Set(mappings.value.map(m => m.vmodule_addr.toUpperCase()))
)

async function refresh() {
  try { mappings.value = await listMappings() } catch {}
  try {
    const data = await listPLC()
    plcOptions.value = Object.entries(data).map(([name, info]) => ({ name, host: info.host }))
    if (plcOptions.value.length && !form.value.plc_name) {
      form.value.plc_name = plcOptions.value[0].name
    }
  } catch {}
}

function openAdd() {
  const f = defaultForm()
  if (plcOptions.value.length) f.plc_name = plcOptions.value[0].name
  form.value = f
  showAdd.value = true
}

async function doAdd() {
  loading.value = true
  try {
    const payload = {
      plc_name: form.value.plc_name,
      plc_addr: form.value.plc_addr,
      vmodule_addr: form.value.vmodule_prefix + form.value.vmodule_num,
      description: form.value.description,
    }
    await addMapping(payload)
    ElMessage.success('映射已添加')
    showAdd.value = false
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

.addr-warn {
  color: #ffa726;
  font-size: 12px;
}
</style>
