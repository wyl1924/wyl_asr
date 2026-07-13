<script setup lang="ts">
import { ref, computed } from 'vue'
import { Search, Download, DocumentCopy, FullScreen, ArrowUp, ArrowDown } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import VirtualTextViewer from './VirtualTextViewer.vue'

interface Props {
  content: string
  title?: string
  downloadFileName?: string
  maxHeight?: number
  showSearch?: boolean
  showDownload?: boolean
  showCopy?: boolean
  showFullscreen?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  title: '文本内容',
  downloadFileName: 'content.txt',
  maxHeight: 400,
  showSearch: true,
  showDownload: true,
  showCopy: true,
  showFullscreen: true
})

const searchKeyword = ref('')
const isFullscreen = ref(false)
const virtualViewerRef = ref<InstanceType<typeof VirtualTextViewer>>()

// 获取窗口高度
const windowHeight = computed(() => {
  return typeof window !== 'undefined' ? window.innerHeight : 800
})

// 计算文本统计信息
const textStats = computed(() => {
  if (!props.content) return { chars: 0, lines: 0, words: 0 }
  
  const chars = props.content.length
  const lines = props.content.split('\n').length
  const words = props.content.trim().split(/\s+/).filter(word => word.length > 0).length
  
  return { chars, lines, words }
})

// 搜索功能
const handleSearch = () => {
  if (virtualViewerRef.value) {
    virtualViewerRef.value.searchInContent(searchKeyword.value)
  }
}

const clearSearch = () => {
  searchKeyword.value = ''
  handleSearch()
}

// 下载功能
const handleDownload = () => {
  try {
    const blob = new Blob([props.content], { type: 'text/plain;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = props.downloadFileName
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    URL.revokeObjectURL(url)
    ElMessage.success('下载成功')
  } catch (error) {
    console.error('下载失败:', error)
    ElMessage.error('下载失败')
  }
}

// 复制功能
const handleCopy = async () => {
  try {
    await navigator.clipboard.writeText(props.content)
    ElMessage.success('复制成功')
  } catch (error) {
    console.error('复制失败:', error)
    ElMessage.error('复制失败')
  }
}

// 全屏功能
const toggleFullscreen = () => {
  isFullscreen.value = !isFullscreen.value
}

// 导航到搜索结果
const nextSearchResult = () => {
  if (virtualViewerRef.value) {
    virtualViewerRef.value.nextSearchResult()
  }
}

const prevSearchResult = () => {
  if (virtualViewerRef.value) {
    virtualViewerRef.value.prevSearchResult()
  }
}
</script>

<template>
  <div class="text-viewer" :class="{ 'fullscreen': isFullscreen }">
    <!-- 工具栏 -->
    <div class="toolbar">
      <div class="toolbar-left">
        <span class="title">{{ title }}</span>
        <div class="stats">
          <el-tag size="small" type="info">{{ textStats.chars }} 字符</el-tag>
          <el-tag size="small" type="info">{{ textStats.lines }} 行</el-tag>
          <el-tag size="small" type="info">{{ textStats.words }} 词</el-tag>
        </div>
      </div>
      
      <div class="toolbar-right">
        <!-- 搜索框 -->
        <div v-if="showSearch" class="search-box">
          <el-input
            v-model="searchKeyword"
            placeholder="搜索内容..."
            size="small"
            clearable
            @input="handleSearch"
            @clear="clearSearch"
          >
            <template #prefix>
              <el-icon><Search /></el-icon>
            </template>
          </el-input>
          <el-button-group v-if="searchKeyword" size="small">
            <el-button @click="prevSearchResult">
              <el-icon><ArrowUp /></el-icon>
            </el-button>
            <el-button @click="nextSearchResult">
              <el-icon><ArrowDown /></el-icon>
            </el-button>
          </el-button-group>
        </div>
        
        <!-- 操作按钮 -->
        <div class="action-buttons">
          <el-button v-if="showCopy" size="small" @click="handleCopy" :icon="DocumentCopy">复制</el-button>
          <el-button v-if="showDownload" size="small" @click="handleDownload" :icon="Download">下载</el-button>
          <el-button v-if="showFullscreen" size="small" @click="toggleFullscreen" :icon="FullScreen">
            {{ isFullscreen ? '退出全屏' : '全屏' }}
          </el-button>
        </div>
      </div>
    </div>
    
    <!-- 内容区域 -->
    <div class="content-area">
      <VirtualTextViewer
        ref="virtualViewerRef"
        :content="content"
        :container-height="isFullscreen ? windowHeight - 120 : maxHeight"
        :search-keyword="searchKeyword"
        :line-height="24"
      />
    </div>
  </div>
</template>

<style lang="scss" scoped>
.text-viewer {
  display: flex;
  flex-direction: column;
  border: 1px solid #e4e7ed;
  border-radius: 8px;
  background: #fff;
  box-shadow: 0 2px 12px 0 rgba(0, 0, 0, 0.1);
  
  &.fullscreen {
    position: fixed;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    z-index: 9999;
    border-radius: 0;
    border: none;
  }
}

.toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 16px;
  background: #f5f7fa;
  border-bottom: 1px solid #e4e7ed;
  border-radius: 8px 8px 0 0;
  
  .fullscreen & {
    border-radius: 0;
  }
}

.toolbar-left {
  display: flex;
  align-items: center;
  gap: 12px;
  
  .title {
    font-weight: 600;
    color: #303133;
    font-size: 16px;
  }
  
  .stats {
    display: flex;
    gap: 4px;
  }
}

.toolbar-right {
  display: flex;
  align-items: center;
  gap: 12px;
}

.search-box {
  display: flex;
  align-items: center;
  gap: 8px;
  
  .el-input {
    width: 200px;
  }
}

.action-buttons {
  display: flex;
  gap: 8px;
}

.content-area {
  flex: 1;
  overflow: hidden;
}

// 响应式设计
@media (max-width: 768px) {
  .toolbar {
    flex-direction: column;
    gap: 12px;
    align-items: stretch;
  }
  
  .toolbar-left,
  .toolbar-right {
    justify-content: center;
  }
  
  .search-box {
    .el-input {
      width: 150px;
    }
  }
  
  .stats {
    justify-content: center;
  }
}
</style>