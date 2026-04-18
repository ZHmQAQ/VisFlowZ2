<template>
  <div class="page-container">
    <div class="page-header">
      <h2>Model Management</h2>
      <el-button type="primary" :icon="Plus" @click="showLoad = true">Load Model</el-button>
    </div>

    <!-- Loaded models -->
    <div class="model-grid">
      <el-card v-for="m in models" :key="m.model_id" class="model-card">
        <template #header>
          <div style="display:flex;justify-content:space-between;align-items:center">
            <b>{{ m.model_id }}</b>
            <el-tag type="success" size="small" effect="dark">Loaded</el-tag>
          </div>
        </template>
        <div class="model-info">
          <div class="info-row"><span>Engine</span><span>{{ m.engine_type || 'yolo' }}</span></div>
          <div class="info-row"><span>Classes</span><span>{{ (m.classes || []).length }}</span></div>
          <div class="info-row" v-if="m.classes && m.classes.length">
            <span>Names</span>
            <div>
              <el-tag v-for="c in m.classes" :key="c" size="small" style="margin:2px" effect="plain">{{ c }}</el-tag>
            </div>
          </div>
        </div>

        <!-- Strategy mapping -->
        <el-divider content-position="left" style="margin:12px 0 8px">Strategy Map</el-divider>
        <div class="strategy-section">
          <div v-for="(code, cls) in (m.strategy_map || {})" :key="cls" class="strategy-row">
            <el-tag size="small" effect="plain">{{ cls }}</el-tag>
            <span style="margin:0 6px">&rarr;</span>
            <el-tag :type="code===1?'success':code===2?'warning':'danger'" size="small" effect="dark">
              {{ code===1?'OK(1)':code===2?'Repairable(2)':'Unrepairable(3)' }}
            </el-tag>
          </div>
          <el-button size="small" text type="primary" @click="openStrategy(m)">
            {{ Object.keys(m.strategy_map||{}).length ? 'Edit' : 'Configure' }} Strategy
          </el-button>
        </div>

        <div style="margin-top:12px">
          <el-button type="danger" size="small" @click="doUnload(m.model_id)">Unload</el-button>
        </div>
      </el-card>
      <el-empty v-if="models.length === 0" description="No models loaded" style="grid-column:span 3" />
    </div>

    <!-- Available weights -->
    <el-card style="margin-top:20px">
      <template #header>Available Weight Files (backend/data/weights/)</template>
      <el-table :data="weights" size="small" stripe>
        <el-table-column prop="filename" label="Filename" />
        <el-table-column prop="size_mb" label="Size (MB)" width="100" />
        <el-table-column label="Action" width="120">
          <template #default="{ row }">
            <el-button size="small" type="primary" text @click="quickLoad(row.filename)">Load</el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-empty v-if="weights.length === 0" description="No .pt files in weights directory" />
    </el-card>

    <!-- Load dialog -->
    <el-dialog v-model="showLoad" title="Load Model" width="460">
      <el-form :model="loadForm" label-width="90px">
        <el-form-item label="Model ID">
          <el-input v-model="loadForm.model_id" placeholder="e.g. yolo_default" />
        </el-form-item>
        <el-form-item label="Weight File">
          <el-select v-model="loadForm.filename" style="width:100%" placeholder="Select weight file">
            <el-option v-for="w in weights" :key="w.filename" :label="`${w.filename} (${w.size_mb}MB)`" :value="w.filename" />
          </el-select>
        </el-form-item>
        <el-form-item label="Engine">
          <el-select v-model="loadForm.engine_type" style="width:100%">
            <el-option label="YOLO (ultralytics)" value="yolo" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showLoad = false">Cancel</el-button>
        <el-button type="primary" :loading="loading" @click="doLoad">Load</el-button>
      </template>
    </el-dialog>

    <!-- Strategy dialog -->
    <el-dialog v-model="showStrategy" title="Strategy Mapping" width="520">
      <p style="color:#8892b0;margin-bottom:12px">
        Map each detection class to a PLC strategy code:<br>
        <b>1</b> = OK &nbsp; <b>2</b> = Repairable &nbsp; <b>3</b> = Unrepairable
      </p>
      <el-table :data="strategyRows" size="small">
        <el-table-column prop="cls" label="Class Name" width="200" />
        <el-table-column label="Strategy Code">
          <template #default="{ row }">
            <el-radio-group v-model="row.code" size="small">
              <el-radio-button :value="1">OK(1)</el-radio-button>
              <el-radio-button :value="2">Repair(2)</el-radio-button>
              <el-radio-button :value="3">Scrap(3)</el-radio-button>
            </el-radio-group>
          </template>
        </el-table-column>
      </el-table>
      <template #footer>
        <el-button @click="showStrategy = false">Cancel</el-button>
        <el-button type="primary" @click="saveStrategy">Save</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { Plus } from '@element-plus/icons-vue'
import { listWeights, loadModel, unloadModel, listModels, setStrategy } from '../api'
import { ElMessage, ElMessageBox } from 'element-plus'

const models = ref([])
const weights = ref([])
const showLoad = ref(false)
const showStrategy = ref(false)
const loading = ref(false)
const loadForm = ref({ model_id: '', filename: '', engine_type: 'yolo' })
const strategyModelId = ref('')
const strategyRows = ref([])

async function refresh() {
  try { models.value = await listModels() } catch {}
  try { weights.value = await listWeights() } catch {}
}

async function doLoad() {
  loading.value = true
  try {
    await loadModel(loadForm.value)
    ElMessage.success(`Model [${loadForm.value.model_id}] loaded`)
    showLoad.value = false
    refresh()
  } finally { loading.value = false }
}

function quickLoad(filename) {
  const id = filename.replace(/\.(pt|onnx|engine|pth)$/, '')
  loadForm.value = { model_id: id, filename, engine_type: 'yolo' }
  showLoad.value = true
}

async function doUnload(id) {
  await ElMessageBox.confirm(`Unload model [${id}]?`, 'Confirm', { type: 'warning' })
  await unloadModel(id)
  ElMessage.success(`Model [${id}] unloaded`)
  refresh()
}

function openStrategy(model) {
  strategyModelId.value = model.model_id
  const existing = model.strategy_map || {}
  const classes = model.classes || []
  strategyRows.value = classes.map(cls => ({
    cls,
    code: existing[cls] || 1,
  }))
  // If no classes detected yet, allow manual entry
  if (strategyRows.value.length === 0) {
    strategyRows.value = [
      { cls: 'ok', code: 1 },
      { cls: 'repairable', code: 2 },
      { cls: 'unrepairable', code: 3 },
    ]
  }
  showStrategy.value = true
}

async function saveStrategy() {
  const map = {}
  strategyRows.value.forEach(r => { map[r.cls] = r.code })
  await setStrategy({ model_id: strategyModelId.value, strategy_map: map })
  ElMessage.success('Strategy saved')
  showStrategy.value = false
  refresh()
}

onMounted(refresh)
</script>

<style scoped lang="scss">
.model-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 16px;
}

.model-info .info-row {
  display: flex;
  justify-content: space-between;
  padding: 4px 0;
  font-size: 13px;
  border-bottom: 1px solid #2a3268;
  span:first-child { color: #8892b0; }
}

.strategy-row {
  display: flex;
  align-items: center;
  margin-bottom: 4px;
}
</style>
