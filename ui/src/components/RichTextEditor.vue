<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { marked } from 'marked'
import { useAsrStore } from '../stores/asr'
import { ElMessage } from 'element-plus'
import { generateSummary, resumeSummaryTask, SUMMARY_TASK_STORAGE_KEY, type BackendSummaryTask } from '../utils/summary'
import {
  SUMMARY_TEMPLATE_OPTIONS,
  buildSummaryOptionsFromLocalStorage,
  buildTranscriptForSummary,
  getSummaryCharCount,
  getSummaryTemplateIdFromLocalStorage,
  setSummaryTemplateIdToLocalStorage,
  stripTranslationsForSummary
} from '../utils/summaryRequest'

const props = defineProps<{
  content?: string
  currentFileName?: string
  meetingId?: number | null
  summaryTranscript?: string
}>()

const emit = defineEmits(['update:content', 'summary-generated'])

const valueHtml = ref('')
const store = useAsrStore()
const isGeneratingSummary = ref(false)
const summaryProgress = ref(0)
const summaryStage = ref('')
const selectedSummaryTemplate = ref(getSummaryTemplateIdFromLocalStorage())
const summaryContent = computed(() => store.meetingSummary || props.content || '')
const hasSummaryContent = computed(() => summaryContent.value.trim().length > 0)
const summaryCharCount = computed(() => summaryContent.value.trim().length)
const restoredSummaryTranscript = computed(() => stripTranslationsForSummary(props.summaryTranscript || '').trim())
const sourceCharCount = computed(() => {
  if (restoredSummaryTranscript.value) {
    return restoredSummaryTranscript.value.length
  }
  return getSummaryCharCount(store.transcript, store.speakerSegments)
})

const cleanHtmlForDisplay = (html: string): string => {
  if (typeof DOMParser === 'undefined') {
    return html.trim()
  }

  const parser = new DOMParser()
  const doc = parser.parseFromString(`<div id="summary-root">${html}</div>`, 'text/html')
  const root = doc.getElementById('summary-root')

  if (!root) {
    return html.trim()
  }

  const unwrapElement = (element: Element) => {
    const parent = element.parentNode
    if (!parent) return

    while (element.firstChild) {
      parent.insertBefore(element.firstChild, element)
    }
    parent.removeChild(element)
  }

  const replaceElement = (element: Element, tagName: string) => {
    const replacement = doc.createElement(tagName)
    while (element.firstChild) {
      replacement.appendChild(element.firstChild)
    }
    element.replaceWith(replacement)
  }

  const sanitizeNode = (node: Node) => {
    if (node.nodeType !== Node.ELEMENT_NODE) return

    const element = node as Element
    const tagName = element.tagName.toLowerCase()

    if (['script', 'style', 'iframe', 'object', 'embed'].includes(tagName)) {
      element.remove()
      return
    }

    Array.from(element.attributes).forEach(attribute => element.removeAttribute(attribute.name))
    Array.from(element.childNodes).forEach(sanitizeNode)

    if (tagName === 'b') {
      replaceElement(element, 'strong')
    } else if (tagName === 'i') {
      replaceElement(element, 'em')
    } else if (tagName === 'center' || tagName === 'span') {
      unwrapElement(element)
    }
  }

  Array.from(root.childNodes).forEach(sanitizeNode)
  return root.innerHTML.trim()
}

const renderSummary = async (summary: string) => {
  if (!summary || !summary.trim()) {
    valueHtml.value = ''
    return
  }

  marked.setOptions({
    breaks: true,
    gfm: true
  })

  const htmlContent = await Promise.resolve(marked(summary))
  valueHtml.value = cleanHtmlForDisplay(htmlContent)
}

watch(summaryContent, (summary) => {
  void renderSummary(summary)
}, { immediate: true })

const updateSummaryProgress = (task: BackendSummaryTask) => {
  isGeneratingSummary.value = task.status === 'queued' || task.status === 'running'
  summaryProgress.value = task.progress ?? summaryProgress.value
  summaryStage.value = task.stage || summaryStage.value
}

const finishSummaryProgress = () => {
  isGeneratingSummary.value = false
  summaryProgress.value = 0
  summaryStage.value = ''
}

const handleSummaryTemplateChange = (templateId: string) => {
  selectedSummaryTemplate.value = setSummaryTemplateIdToLocalStorage(templateId)
}

const restoreActiveSummaryTask = async () => {
  const taskId = localStorage.getItem(SUMMARY_TASK_STORAGE_KEY)
  if (!taskId || store.meetingSummary) return

  try {
    isGeneratingSummary.value = true
    summaryStage.value = '正在恢复上次会议纪要生成任务...'
    const summary = await resumeSummaryTask(taskId, {
      onSummaryProgress: updateSummaryProgress
    })
    store.meetingSummary = summary
    emit('update:content', summary)
    emit('summary-generated', summary)
    ElMessage.success('已恢复并完成会议纪要生成')
  } catch (error) {
    console.error('恢复会议纪要生成任务失败:', error)
    localStorage.removeItem(SUMMARY_TASK_STORAGE_KEY)
  } finally {
    finishSummaryProgress()
  }
}

// 生成会议纪要
const handleGenerateSummary = async () => {
  // 检查转写内容是否为空
  if (sourceCharCount.value === 0) {
    ElMessage.warning('请先获取转写内容后再生成会议纪要')
    return
  }
  
  try {
    const options = buildSummaryOptionsFromLocalStorage()
    options.templateId = selectedSummaryTemplate.value
    if (props.meetingId) {
      options.meetingId = props.meetingId
    }
    options.onSummaryProgress = updateSummaryProgress
    const transcriptContent = restoredSummaryTranscript.value ||
      buildTranscriptForSummary(store.transcript, store.speakerSegments)
    
    // 使用ASR store中的转写文本生成会议纪要
    isGeneratingSummary.value = true
    summaryStage.value = '正在提交会议纪要生成任务...'
    const summary = await generateSummary(transcriptContent, options)
    
    console.log('生成的会议纪要内容:', summary)
    store.meetingSummary = summary
    
    // 通知父组件内容已更新
    emit('update:content', summary)
    emit('summary-generated', summary)
    
    ElMessage.success('会议纪要生成成功')
  } catch (error) {
    console.error('生成会议纪要失败:', error)
    ElMessage.error(`生成会议纪要失败：${(error as Error).message || String(error)}`)
  } finally {
    finishSummaryProgress()
  }
}

onMounted(() => {
  void restoreActiveSummaryTask()
})
</script>

<template>
  <div class="rich-text-editor">
    <div class="summary-buttons">
      <div class="summary-actions">
        <el-button
          type="primary"
          size="default"
          :loading="isGeneratingSummary"
          :disabled="isGeneratingSummary"
          @click="handleGenerateSummary"
        >
          <el-icon><document /></el-icon>
          {{ isGeneratingSummary ? '生成中' : hasSummaryContent ? '重新生成会议纪要' : '生成会议纪要' }}
        </el-button>
        <el-select
          v-model="selectedSummaryTemplate"
          class="summary-template-select"
          size="default"
          :disabled="isGeneratingSummary"
          @change="handleSummaryTemplateChange"
        >
          <el-option
            v-for="template in SUMMARY_TEMPLATE_OPTIONS"
            :key="template.id"
            :label="template.label"
            :value="template.id"
          />
        </el-select>
        <el-tag v-if="hasSummaryContent" size="small" type="info">{{ summaryCharCount }} 字符</el-tag>
      </div>
      <div v-if="isGeneratingSummary" class="summary-progress">
        <el-progress :percentage="summaryProgress" :show-text="false" />
        <span>{{ summaryStage || '正在生成会议纪要...' }}</span>
      </div>
    </div>

    <div v-if="hasSummaryContent" class="summary-content-card">
      <div class="summary-content-header">
        <span>会议纪要</span>
        <el-tag size="small" type="success" effect="plain">已生成</el-tag>
      </div>
      <div class="summary-display" v-html="valueHtml"></div>
    </div>
    <div v-else class="summary-placeholder"></div>
  </div>
</template>

<style lang="scss" scoped>
$primary-color: #fff;
$background-color: #f5f7fa;

.rich-text-editor {
  height: 100%;
  display: flex;
  flex-direction: column;
  background: $primary-color;
  border-radius: 8px;
  overflow: hidden;
}

.summary-buttons {
  padding: 16px 20px;
  border-bottom: 1px solid #e4e7ed;
  background-color: $primary-color;
  flex-shrink: 0;
}

.summary-actions {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}

.summary-actions :deep(.el-button) {
  display: flex;
  align-items: center;
  gap: 4px;
  min-height: 44px;
  border-radius: 6px;
}

.summary-template-select {
  width: 180px;
}

.summary-actions :deep(.el-icon) {
  margin-right: 4px;
}

.summary-progress {
  display: flex;
  flex-direction: column;
  gap: 6px;
  margin-top: 10px;
  color: #606266;
  font-size: 12px;
}

.summary-content-card {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  margin: 12px;
  border: 1px solid #e4e7ed;
  border-radius: 8px;
  background: #fff;
  overflow: hidden;
}

.summary-content-header {
  min-height: 42px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 0 14px;
  border-bottom: 1px solid #e4e7ed;
  background: #f7f8fa;
  color: #303133;
  font-size: 13px;
  font-weight: 600;
}

.summary-display {
  flex: 1;
  min-height: 0;
  padding: 16px;
  overflow-y: auto;
  color: #303133;
  font-size: 14px;
  line-height: 1.6;
  text-align: left;
  word-break: break-word;
}

.summary-display :deep(p),
.summary-display :deep(li) {
  margin: 0 0 10px;
}

.summary-display :deep(h1),
.summary-display :deep(h2),
.summary-display :deep(h3),
.summary-display :deep(h4) {
  margin: 14px 0 10px;
  color: #303133;
  font-weight: 600;
  line-height: 1.4;
}

.summary-display :deep(h1) {
  font-size: 18px;
}

.summary-display :deep(h2) {
  font-size: 17px;
}

.summary-display :deep(h3),
.summary-display :deep(h4) {
  font-size: 15px;
}

.summary-display :deep(ul),
.summary-display :deep(ol) {
  margin: 8px 0 12px;
  padding-left: 22px;
}

.summary-display :deep(code) {
  padding: 2px 4px;
  border-radius: 3px;
  background: $background-color;
  font-family: 'Courier New', Courier, monospace;
}

.summary-placeholder {
  flex: 1;
  min-height: 0;
  background: #fff;
}
</style>
