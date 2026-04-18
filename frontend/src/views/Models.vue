<template>
  <div class="page-container">
    <div class="page-header">
      <h2>模型管理</h2>
      <el-button type="primary" :icon="Upload">上传模型</el-button>
    </div>

    <el-empty v-if="models.length === 0" description="暂无模型，请将 .pt 文件放入 backend/data/weights/" />

    <div class="model-grid">
      <el-card v-for="m in models" :key="m.id">
        <template #header>
          <div style="display:flex;justify-content:space-between;align-items:center">
            <span>{{ m.id }}</span>
            <el-tag :type="m.loaded ? 'success' : 'info'" size="small" effect="dark">
              {{ m.loaded ? '已加载' : '未加载' }}
            </el-tag>
          </div>
        </template>
        <div style="font-size:13px;color:#8892b0;line-height:2;">
          <div>引擎: {{ m.engine }}</div>
          <div>类别数: {{ m.classes }}</div>
        </div>
      </el-card>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { Upload } from '@element-plus/icons-vue'

// 模型管理 API 尚未完整实现，此为 UI 骨架
const models = ref([])
</script>

<style scoped>
.model-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px; }
</style>
