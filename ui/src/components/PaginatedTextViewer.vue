<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { Search, Download, DocumentCopy, ArrowLeft, ArrowRight } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'

interface Props {
  content: string
  title?: string
  downloadFileName?: string
  linesPerPage?: number
  showSearch?: boolean
  showDownload?: boolean
  showCopy?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  title: '文本内容',
  downloadFileName: 'content.txt',
  linesPerPage: 100,
  showSearch: true,
  showDownload: true,
  showCopy: true
})

const searchKeyword = ref('')
const currentPage = ref(1)
const searchResults = ref<number[]>([])
const currentSearchIndex = ref(-1)

// 将文本按行分割
const lines = computed(() => {
  if (!props.content) return []
  return props.content.split('\n')
})

// 计算总页数
const totalPages = computed(() => {
  return Math.ceil(lines.value.length / props.linesPerPage)
})

// 当前页的内容
const currentPageLines = computed(() => {
  const startIndex = (currentPage.value - 1) * props.linesPerPage
  const endIndex = startIndex + props.linesPerPage
  return lines.value.slice(startIndex, endIndex)
})

// 当前页的起始行号
const currentPageStartLine = computed(() => {
  return (currentPage.value - 1) * props.linesPerPage + 1
})

// 文本统计信息
const textStats = computed(() => {
  if (!props.content) return { chars: 0, lines: 0, words: 0 }
  
  const chars = props.content.length
  const linesCount = lines.value.length
  const words = props.content.trim().split(/\s+/).filter(word => word.length > 0).length
  
  return { chars, lines: linesCount, words }
})

// 高亮搜索关键词
const highlightText = (text: string, lineIndex: number) => {
  if (!searchKeyword.value) return text
  
  const globalLineIndex = (currentPage.value - 1) * props.linesPerPage + lineIndex
  const isSearchResult = searchResults.value.includes(globalLineIndex)
  const isCurrentResult = searchResults.value[currentSearchIndex.value] === globalLineIndex
  
  let highlightedText = text
  if (searchKeyword.value) {
    const regex = new RegExp(`(${escapeRegExp(searchKeyword.value)})`, 'gi')
    highlightedText = text.replace(regex, '<mark>$1</mark>')
  }
  
  if (isCurrentResult) {
    return `<span class="current-search-line">${highlightedText}</span>`
  } else if (isSearchResult) {
    return `<span class="search-result-line">${highlightedText}</span>`
  }
  
  return highlightedText
}

// 转义正则表达式特殊字符
const escapeRegExp = (string: string) => {
  return string.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
}

// 搜索功能
const handleSearch = () => {
  if (!searchKeyword.value) {
    searchResults.value = []
    currentSearchIndex.value = -1
    return
  }
  
  const results: number[] = []
  const keyword = searchKeyword.value.toLowerCase()
  
  lines.value.forEach((line, index) => {
    if (line.toLowerCase().includes(keyword)) {
      results.push(index)
    }
  })
  
  searchResults.value = results
  currentSearchIndex.value = results.length > 0 ? 0 : -1
  
  // 跳转到第一个搜索结果
  if (results.length > 0) {
    jumpToLine(results[0] + 1)
  }
}

// 清除搜索
const clearSearch = () => {
  searchKeyword.value = ''
  searchResults.value = []
  currentSearchIndex.value = -1
}

// 下一个搜索结果
const nextSearchResult = () => {
  if (searchResults.value.length === 0) return
  
  currentSearchIndex.value = (currentSearchIndex.value + 1) % searchResults.value.length
  jumpToLine(searchResults.value[currentSearchIndex.value] + 1)
}

// 上一个搜索结果
const prevSearchResult = () => {
  if (searchResults.value.length === 0) return
  
  currentSearchIndex.value = currentSearchIndex.value <= 0 
    ? searchResults.value.length - 1 
    : currentSearchIndex.value - 1
  jumpToLine(searchResults.value[currentSearchIndex.value] + 1)
}

// 跳转到指定行
const jumpToLine = (lineNumber: number) => {
  const targetPage = Math.ceil(lineNumber / props.linesPerPage)
  currentPage.value = Math.max(1, Math.min(targetPage, totalPages.value))
}

// 页面导航
const goToPage = (page: number) => {
  currentPage.value = Math.max(1, Math.min(page, totalPages.value))
}

const prevPage = () => {
  if (currentPage.value > 1) {
    currentPage.value--
  }
}

const nextPage = () => {
  if (currentPage.value < totalPages.value) {
    currentPage.value++
  }
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

// 监听搜索关键词变化
watch(searchKeyword, () => {
  handleSearch()
})
</script>

<template>
  <div class="paginated-text-viewer">
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
            @clear="clearSearch"
          >
            <template #prefix>
              <el-icon><Search /></el-icon>
            </template>
          </el-input>
          <div v-if="searchKeyword" class="search-results">
            <span class="search-info">
              {{ searchResults.length > 0 ? `${currentSearchIndex + 1}/${searchResults.length}` : '0/0' }}
            </span>
            <el-button-group size="small">
              <el-button @click="prevSearchResult" :disabled="searchResults.length === 0">
                <el-icon><ArrowLeft /></el-icon>
              </el-button>
              <el-button @click="nextSearchResult" :disabled="searchResults.length === 0">
                <el-icon><ArrowRight /></el-icon>
              </el-button>
            </el-button-group>
          </div>
        </div>
        
        <!-- 操作按钮 -->
        <div class="action-buttons">
          <el-button v-if="showCopy" size="small" @click="handleCopy" :icon="DocumentCopy">复制</el-button>
          <el-button v-if="showDownload" size="small" @click="handleDownload" :icon="Download">下载</el-button>
        </div>
      </div>
    </div>
    
    <!-- 内容区域 -->
    <div class="content-area">
      <div class="text-content">
        <div class="line-numbers">
          <div 
            v-for="(_, index) in currentPageLines"
            :key="currentPageStartLine + index"
            class="line-number"
          >
            {{ currentPageStartLine + index }}
          </div>
        </div>
        <div class="text-lines">
          <div 
            v-for="(line, index) in currentPageLines"
            :key="currentPageStartLine + index"
            class="text-line"
            v-html="highlightText(line || ' ', index)"
          >
          </div>
        </div>
      </div>
    </div>
    
    <!-- 分页器 -->
    <div class="pagination-area">
      <div class="page-info">
        <span>第 {{ currentPage }} 页，共 {{ totalPages }} 页</span>
        <span>显示第 {{ currentPageStartLine }} - {{ Math.min(currentPageStartLine + props.linesPerPage - 1, textStats.lines) }} 行</span>
      </div>
      <el-pagination
        v-model:current-page="currentPage"
        :page-size="linesPerPage"
        :total="textStats.lines"
        layout="prev, pager, next, jumper"
        small
        @current-change="goToPage"
      />
    </div>
  </div>
</template>

<style lang="scss" scoped>
.paginated-text-viewer {
  display: flex;
  flex-direction: column;
  border: 1px solid #e4e7ed;
  border-radius: 8px;
  background: #fff;
  box-shadow: 0 2px 12px 0 rgba(0, 0, 0, 0.1);
  min-height: 400px;
  max-height: 600px;
  position: relative;
  z-index: 1;
  margin-bottom: 20px;
}

.toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 16px;
  background: #f5f7fa;
  border-bottom: 1px solid #e4e7ed;
  border-radius: 8px 8px 0 0;
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
  
  .search-results {
    display: flex;
    align-items: center;
    gap: 8px;
    
    .search-info {
      font-size: 12px;
      color: #606266;
      white-space: nowrap;
    }
  }
}

.action-buttons {
  display: flex;
  gap: 8px;
}

.content-area {
  flex: 1;
  overflow: hidden;
  padding: 16px;
}

.text-content {
  display: flex;
  height: 100%;
  font-family: 'Monaco', 'Menlo', 'Ubuntu Mono', monospace;
  font-size: 14px;
  line-height: 1.6;
}

.line-numbers {
  width: 60px;
  background: #f8f9fa;
  border-right: 1px solid #e4e7ed;
  padding: 8px;
  text-align: right;
  color: #909399;
  font-size: 12px;
  user-select: none;
}

.line-number {
  height: 22.4px; // 14px * 1.6 line-height
  line-height: 22.4px;
}

.text-lines {
  flex: 1;
  padding: 8px 12px;
  overflow-y: auto;
  background: #fff;
}

.text-line {
  height: 22.4px;
  line-height: 22.4px;
  color: #303133;
  white-space: pre-wrap;
  word-wrap: break-word;
  
  &:hover {
    background-color: #f5f7fa;
  }
  
  :deep(mark) {
    background-color: #ffeb3b;
    color: #333;
    padding: 0 2px;
    border-radius: 2px;
  }
  
  :deep(.search-result-line) {
    background-color: #fff3cd;
  }
  
  :deep(.current-search-line) {
    background-color: #ffeaa7;
    border-left: 3px solid #fdcb6e;
    padding-left: 8px;
  }
}

.pagination-area {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 16px;
  background: #f5f7fa;
  border-top: 1px solid #e4e7ed;
  border-radius: 0 0 8px 8px;
}

.page-info {
  display: flex;
  flex-direction: column;
  gap: 2px;
  font-size: 12px;
  color: #606266;
}

// 滚动条样式
.text-lines::-webkit-scrollbar {
  width: 8px;
}

.text-lines::-webkit-scrollbar-track {
  background: #f1f1f1;
  border-radius: 4px;
}

.text-lines::-webkit-scrollbar-thumb {
  background: #c1c1c1;
  border-radius: 4px;
  
  &:hover {
    background: #a8a8a8;
  }
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
    flex-direction: column;
    gap: 8px;
    
    .el-input {
      width: 100%;
    }
  }
  
  .pagination-area {
    flex-direction: column;
    gap: 8px;
  }
  
  .line-numbers {
    width: 40px;
  }
}
</style>