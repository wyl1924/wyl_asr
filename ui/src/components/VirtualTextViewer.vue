<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import { ArrowUp, ArrowDown } from '@element-plus/icons-vue'

interface Props {
  content: string
  lineHeight?: number
  containerHeight?: number
  searchKeyword?: string
}

const props = withDefaults(defineProps<Props>(), {
  lineHeight: 24,
  containerHeight: 400,
  searchKeyword: ''
})

const containerRef = ref<HTMLElement>()
const scrollTop = ref(0)
const containerWidth = ref(0)

// 将文本按行分割
const lines = computed(() => {
  if (!props.content) return []
  return props.content.split('\n')
})

// 计算可见区域的行数
const visibleLineCount = computed(() => {
  return Math.ceil(props.containerHeight / props.lineHeight) + 2 // 多渲染2行作为缓冲
})

// 计算当前滚动位置对应的起始行
const startIndex = computed(() => {
  return Math.floor(scrollTop.value / props.lineHeight)
})

// 计算结束行
const endIndex = computed(() => {
  return Math.min(startIndex.value + visibleLineCount.value, lines.value.length)
})

// 当前可见的行
const visibleLines = computed(() => {
  return lines.value.slice(startIndex.value, endIndex.value)
})

// 总高度
const totalHeight = computed(() => {
  return lines.value.length * props.lineHeight
})

// 上方占位高度
const offsetY = computed(() => {
  return startIndex.value * props.lineHeight
})

// 高亮搜索关键词
const highlightText = (text: string) => {
  if (!props.searchKeyword) return text
  const regex = new RegExp(`(${props.searchKeyword})`, 'gi')
  return text.replace(regex, '<mark>$1</mark>')
}

// 滚动事件处理
const handleScroll = (event: Event) => {
  const target = event.target as HTMLElement
  scrollTop.value = target.scrollTop
}

// 跳转到指定行
const scrollToLine = (lineNumber: number) => {
  if (!containerRef.value) return
  const targetScrollTop = (lineNumber - 1) * props.lineHeight
  containerRef.value.scrollTop = targetScrollTop
}

// 搜索功能
const searchResults = ref<number[]>([])
const currentSearchIndex = ref(-1)

const searchInContent = (keyword: string) => {
  if (!keyword) {
    searchResults.value = []
    currentSearchIndex.value = -1
    return
  }
  
  const results: number[] = []
  lines.value.forEach((line, index) => {
    if (line.toLowerCase().includes(keyword.toLowerCase())) {
      results.push(index)
    }
  })
  
  searchResults.value = results
  currentSearchIndex.value = results.length > 0 ? 0 : -1
  
  // 跳转到第一个搜索结果
  if (results.length > 0) {
    scrollToLine(results[0] + 1)
  }
}

// 下一个搜索结果
const nextSearchResult = () => {
  if (searchResults.value.length === 0) return
  currentSearchIndex.value = (currentSearchIndex.value + 1) % searchResults.value.length
  scrollToLine(searchResults.value[currentSearchIndex.value] + 1)
}

// 上一个搜索结果
const prevSearchResult = () => {
  if (searchResults.value.length === 0) return
  currentSearchIndex.value = currentSearchIndex.value <= 0 
    ? searchResults.value.length - 1 
    : currentSearchIndex.value - 1
  scrollToLine(searchResults.value[currentSearchIndex.value] + 1)
}

// 监听搜索关键词变化
watch(() => props.searchKeyword, (newKeyword) => {
  searchInContent(newKeyword)
})

// 获取容器宽度
const updateContainerWidth = () => {
  if (containerRef.value) {
    containerWidth.value = containerRef.value.clientWidth
  }
}

onMounted(() => {
  updateContainerWidth()
  window.addEventListener('resize', updateContainerWidth)
})

onUnmounted(() => {
  window.removeEventListener('resize', updateContainerWidth)
})

// 暴露方法给父组件
defineExpose({
  scrollToLine,
  searchInContent,
  nextSearchResult,
  prevSearchResult,
  searchResults,
  currentSearchIndex
})
</script>

<template>
  <div class="virtual-text-viewer">
    <!-- 搜索工具栏 -->
    <div v-if="searchKeyword" class="search-toolbar">
      <span class="search-info">
        {{ searchResults.length > 0 ? `${currentSearchIndex + 1}/${searchResults.length}` : '0/0' }}
      </span>
      <el-button-group>
        <el-button size="small" @click="prevSearchResult" :disabled="searchResults.length === 0">
          <el-icon><ArrowUp /></el-icon>
        </el-button>
        <el-button size="small" @click="nextSearchResult" :disabled="searchResults.length === 0">
          <el-icon><ArrowDown /></el-icon>
        </el-button>
      </el-button-group>
    </div>
    
    <!-- 虚拟滚动容器 -->
    <div 
      ref="containerRef"
      class="scroll-container"
      :style="{ height: `${containerHeight}px` }"
      @scroll="handleScroll"
    >
      <!-- 总高度占位 -->
      <div :style="{ height: `${totalHeight}px`, position: 'relative' }">
        <!-- 可见内容 -->
        <div 
          class="visible-content"
          :style="{ transform: `translateY(${offsetY}px)` }"
        >
          <div 
            v-for="(line, index) in visibleLines"
            :key="startIndex + index"
            class="text-line"
            :class="{
              'search-highlight': searchResults.includes(startIndex + index),
              'current-search': searchResults[currentSearchIndex] === startIndex + index
            }"
            :style="{ height: `${lineHeight}px`, lineHeight: `${lineHeight}px` }"
            v-html="highlightText(line || ' ')"
          >
          </div>
        </div>
      </div>
    </div>
    
    <!-- 统计信息 -->
    <div class="stats-bar">
      <span>总行数: {{ lines.length }}</span>
      <span>当前显示: {{ startIndex + 1 }}-{{ endIndex }}</span>
    </div>
  </div>
</template>

<style lang="scss" scoped>
.virtual-text-viewer {
  display: flex;
  flex-direction: column;
  border: 1px solid #e4e7ed;
  border-radius: 4px;
  background: #fff;
}

.search-toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 12px;
  background: #f5f7fa;
  border-bottom: 1px solid #e4e7ed;
  
  .search-info {
    font-size: 12px;
    color: #606266;
  }
}

.scroll-container {
  flex: 1;
  overflow-y: auto;
  overflow-x: hidden;
  position: relative;
}

.visible-content {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
}

.text-line {
  padding: 0 12px;
  font-family: 'Monaco', 'Menlo', 'Ubuntu Mono', monospace;
  font-size: 14px;
  color: #303133;
  white-space: pre-wrap;
  word-wrap: break-word;
  border-bottom: 1px solid transparent;
  
  &:hover {
    background-color: #f5f7fa;
  }
  
  &.search-highlight {
    background-color: #fff3cd;
  }
  
  &.current-search {
    background-color: #ffeaa7;
    border-color: #fdcb6e;
  }
  
  :deep(mark) {
    background-color: #ffeb3b;
    color: #333;
    padding: 0 2px;
    border-radius: 2px;
  }
}

.stats-bar {
  display: flex;
  justify-content: space-between;
  padding: 4px 12px;
  background: #f5f7fa;
  border-top: 1px solid #e4e7ed;
  font-size: 12px;
  color: #909399;
}

// 滚动条样式
.scroll-container::-webkit-scrollbar {
  width: 8px;
}

.scroll-container::-webkit-scrollbar-track {
  background: #f1f1f1;
  border-radius: 4px;
}

.scroll-container::-webkit-scrollbar-thumb {
  background: #c1c1c1;
  border-radius: 4px;
  
  &:hover {
    background: #a8a8a8;
  }
}
</style>