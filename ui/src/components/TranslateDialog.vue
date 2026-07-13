<script setup lang="ts">
import { ref, watch } from 'vue'
import { ElMessage } from 'element-plus'

const props = defineProps<{
  visible: boolean
  text: string
}>()

const emit = defineEmits(['update:visible', 'update:text'])

const sourceLanguage = ref('zh') // 默认源语言为中文
const targetLanguage = ref('en') // 默认目标语言为英语
const sourceText = ref('') // 存储原文
const translatedText = ref('') // 存储翻译后的文本

const languages = [
  { label: '中文', value: 'zh' },
  { label: '英语', value: 'en' }
]

const handleClose = () => {
  emit('update:visible', false)
}

const handleTranslate = async () => {
  try {
    if (!sourceText.value) {
      ElMessage.warning('请输入需要翻译的内容')
      return
    }
    // TODO: 实现翻译逻辑
    translatedText.value = '这里是翻译后的内容' // 模拟翻译结果
    ElMessage.success('翻译成功')
  } catch (error) {
    ElMessage.error('翻译失败：' + error)
  }
}

// 监听props.text的变化，自动更新原文内容
watch(() => props.text, (newValue) => {
  sourceText.value = newValue
}, { immediate: true })
</script>

<template>
  <el-dialog
    :model-value="visible"
    @update:model-value="emit('update:visible', $event)"
    width="1000px"
    :show-close="true"
    @close="handleClose"
  >
    <div class="translate-content">
      <div class="language-bar">
        <el-select v-model="sourceLanguage" class="language-select">
          <el-option
            v-for="lang in languages"
            :key="lang.value"
            :label="lang.label"
            :value="lang.value"
          />
        </el-select>
        <el-icon class="language-arrow"><ArrowRight /></el-icon>
        <el-select v-model="targetLanguage" class="language-select">
          <el-option
            v-for="lang in languages"
            :key="lang.value"
            :label="lang.label"
            :value="lang.value"
          />
        </el-select>
      </div>
      <div class="translate-container">
        <div class="text-panel">
          <div class="panel-header">
            <span class="panel-title">原文</span>
          </div>
          <el-input
            v-model="sourceText"
            type="textarea"
            :rows="15"
            resize="none"
            placeholder="请输入需要翻译的内容"
          />
        </div>
        <div class="text-panel">
          <div class="panel-header">
            <span class="panel-title">译文</span>
          </div>
          <el-input
            v-model="translatedText"
            type="textarea"
            :rows="15"
            readonly
            resize="none"
            placeholder="翻译结果将在这里显示"
          />
        </div>
      </div>
    </div>
    
    <template #footer>
      <div class="dialog-footer">
        <el-button @click="handleClose">关闭</el-button>
        <el-button type="primary" @click="handleTranslate">翻译</el-button>
      </div>
    </template>
  </el-dialog>
</template>

<style lang="scss" scoped>
// 变量定义
$primary-color: #fff;
$border-color: #e4e7ed;
$background-color: #f5f7fa;
$text-color: #606266;
$text-secondary: #909399;
$spacing-md: 12px;
$spacing-lg: 16px;
$spacing-xl: 20px;
$spacing-xxl: 24px;

.translate-dialog :deep(.el-dialog__header) {
  display: none;
}

.translate-content {
  padding: $spacing-xl;
  max-height: 80vh;
  overflow-y: auto;
}

.translate-container {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: $spacing-xxl;
}

.text-panel {
  background: $primary-color;
  border: 1px solid $border-color;
  overflow: hidden;
  
  .el-input {
    height: 100%;
  }
  
  .el-textarea__inner {
    border: none;
    border-radius: 0;
    padding: $spacing-lg;
  }
}

.panel-header {
  padding: $spacing-md $spacing-lg;
  background-color: $background-color;
  border-bottom: 1px solid $border-color;
}

.panel-title {
  font-size: 14px;
  font-weight: 500;
  color: $text-color;
}

.language-bar {
  display: flex;
  align-items: center;
  gap: $spacing-lg;
  margin-bottom: $spacing-xxl;
}

.language-select {
  width: 120px;
}

.language-arrow {
  color: $text-secondary;
  font-size: 16px;
  display: flex;
  align-items: center;
  justify-content: center;
}
</style>