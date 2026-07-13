<script setup lang="ts">
import QrcodeVue from 'qrcode.vue'
import { ElMessage } from 'element-plus'

const props = defineProps<{
  visible: boolean
  shareUrl: string
  fileName: string
}>()

const emit = defineEmits(['update:visible'])

const handleClose = () => {
  emit('update:visible', false)
}

const copyLink = async () => {
  try {
    await navigator.clipboard.writeText(props.shareUrl)
    ElMessage.success('链接已复制')
  } catch (error) {
    ElMessage.error('复制失败：' + error)
  }
}
</script>

<template>
  <el-dialog
    :model-value="visible"
    title="分享内容"
    width="400px"
    :show-close="true"
    @close="handleClose"
    @update:model-value="emit('update:visible', $event)"
    destroy-on-close
  >
    <div class="share-content">
      <div class="qrcode-container">
        <qrcode-vue :value="shareUrl" :size="200" level="H" /></div>
      <p class="scan-tip">扫描二维码，查看文件内容</p>
      <div class="file-info">
        <div class="info-item">
          <span class="label">文件名称：</span>
          <span class="value">{{ fileName }}</span>
        </div>
        <div class="info-item">
          <span class="label">访问链接：</span>
          <div class="link-container">
            <span class="value link">{{ shareUrl }}</span>
            <el-button type="primary" link @click="copyLink">复制链接</el-button>
          </div>
        </div>
      </div>
      <p class="expire-tip">获得链接的人都可以访问（仅支持查看，链接90天内有效）</p>
    </div>
  </el-dialog>
</template>

<style lang="scss" scoped>
// 变量定义
$text-primary: #303133;
$text-secondary: #606266;
$text-tertiary: #909399;
$spacing-sm: 8px;
$spacing-md: 12px;
$spacing-lg: 16px;
$spacing-xl: 20px;
$spacing-xxl: 24px;

.share-content {
  padding: $spacing-xl;
  text-align: center;
}

.qrcode-container {
  display: flex;
  justify-content: center;
  margin-bottom: $spacing-lg;
}

.scan-tip {
  color: $text-secondary;
  margin-bottom: $spacing-xxl;
}

.file-info {
  text-align: left;
  margin-bottom: $spacing-xxl;
}

.info-item {
  margin-bottom: $spacing-md;
  
  &:last-child {
    margin-bottom: 0;
  }
}

.label {
  color: $text-tertiary;
  margin-right: $spacing-sm;
}

.value {
  color: $text-primary;
}

.link-container {
  display: flex;
  align-items: center;
  gap: $spacing-sm;
}

.link {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.expire-tip {
  color: $text-tertiary;
  font-size: 12px;
  margin: 0;
}
</style>