<script setup lang="ts">
import { ref } from 'vue'
import { ElMessage } from 'element-plus'

defineProps<{
  visible: boolean
  fileName: string
}>()

const emit = defineEmits(['update:visible'])

const downloadContent = ref(['original']) // 可多选：原文、会议纪要、音频
const downloadFormat = ref('pdf') // 默认pdf

const handleClose = () => {
  emit('update:visible', false)
}

const handleDownload = async () => {
  try {
    // TODO: 实现下载逻辑
    ElMessage.success('下载成功')
    handleClose()
  } catch (error) {
    ElMessage.error('下载失败：' + error)
  }
}
</script>

<template>
  <el-dialog
    :model-value="visible"
    title="下载内容"
    width="400px"
    :show-close="true"
    @close="handleClose"
    @update:model-value="emit('update:visible', $event)"
    destroy-on-close
  >
    <div class="download-content">
      <div class="file-info">
        <div class="info-item">
          <span class="label">文件名称：</span>
          <span class="value">{{ fileName }}</span>
        </div>
      </div>
      
      <div class="download-options">
        <div class="option-section">
          <div class="option-label">下载内容：</div>
          <div class="option-group">
            <el-checkbox-group v-model="downloadContent">
              <el-checkbox label="original">原文</el-checkbox>
              <el-checkbox label="summary">会议纪要</el-checkbox>
              <el-checkbox label="audio">音频</el-checkbox>
            </el-checkbox-group>
          </div>
        </div>
        
        <div class="option-section">
          <div class="option-label">下载格式：</div>
          <div class="option-group">
            <el-radio-group v-model="downloadFormat">
              <el-radio label="pdf">PDF</el-radio>
              <el-radio label="txt">TXT</el-radio>
            </el-radio-group>
          </div>
        </div>
      </div>
    </div>
    
    <template #footer>
      <div class="dialog-footer">
        <el-button @click="handleClose">取消</el-button>
        <el-button type="primary" @click="handleDownload">下载</el-button>
      </div>
    </template>
  </el-dialog>
</template>

<style lang="scss" scoped>
// 颜色变量
$background-light: #f5f7fa;
$background-white: #fff;
$border-color: #e4e7ed;
$text-primary: #303133;
$text-secondary: #606266;
$text-tertiary: #909399;

// 间距变量
$spacing-sm: 4px;
$spacing-md: 8px;
$spacing-lg: 12px;
$spacing-xl: 16px;
$spacing-xxl: 24px;
$spacing-xxxl: 32px;

// 边框变量
$border-radius: 8px;

.download-content {
  padding: $spacing-xxl;
  max-height: 60vh;
  overflow-y: auto;
}

.file-info {
  margin-bottom: $spacing-xxxl;
  padding: $spacing-xl;
  background-color: $background-light;
  border-radius: $border-radius;
}

.info-item {
  margin-bottom: $spacing-lg;
  display: flex;
  align-items: center;
  
  &:last-child {
    margin-bottom: 0;
  }
  
  .label {
    color: $text-tertiary;
    margin-right: $spacing-lg;
    min-width: 70px;
  }
  
  .value {
    color: $text-primary;
    flex: 1;
  }
}

.download-options {
  display: flex;
  flex-direction: column;
  gap: $spacing-xl;
}

.option-section {
  display: flex;
  flex-direction: column;
  gap: $spacing-lg;
  text-align: left;
  
  .option-group {
    padding: $spacing-lg;
    background-color: $background-white;
    border-radius: $border-radius;
    border: 1px solid $border-color;
  }
  
  .option-label {
    font-size: 14px;
    text-align: left;
    color: $text-secondary;
    font-weight: 500;
    margin-bottom: $spacing-sm;
  }
}

.dialog-footer {
  text-align: right;
  padding-top: $spacing-xl;
  border-top: 1px solid $border-color;
}

:deep(.el-checkbox-group) {
  display: flex;
  gap: $spacing-xl;
}

:deep(.el-radio-group) {
  display: flex;
  gap: $spacing-xl;
}
</style>