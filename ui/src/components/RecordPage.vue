<script setup lang="ts">
import { ref, onMounted, watch, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import AsrPanel from './AsrPanel.vue'
import RichTextEditor from './RichTextEditor.vue'


import TranslateDialog from './TranslateDialog.vue'
import { ElMessage } from 'element-plus'
import { Upload, VideoCamera } from '@element-plus/icons-vue'
import { useAsrStore } from '../stores/asr'
import { uploadApi } from '../api/upload'
import {
  buildMeetingDocumentUrl,
  meetingApi,
  type MeetingDocumentInfo,
  type MeetingMinutesVersion
} from '../api/meeting'

const route = useRoute()
const router = useRouter()
const store = useAsrStore()
const translateDialogVisible = ref(false)
const fileName = ref('')
const meetingTitle = ref('')
const translateText = ref('')
const editorContent = ref('')
const isEditingTitle = ref(false)
const titleInputRef = ref<HTMLInputElement | null>(null)
const recordingCounter = ref(1)
const fileNameHistory = ref<string[]>([])
const isSaving = ref(false)
const shareDialogVisible = ref(false)
const shareUrl = ref('')
const showMinutesPanel = ref(true)
const recognitionMode = computed(() => route.query.mode === 'upload' ? 'upload' : 'realtime')
const isUploadMode = computed(() => recognitionMode.value === 'upload')
const pageStatusText = computed(() => isUploadMode.value ? '上传识别结果可保存' : '实时识别结果可保存')
const saveButtonText = computed(() => isUploadMode.value ? '保存识别结果' : '保存会议')
const restoredMeetingId = computed(() => {
  const rawValue = route.query.meetingId || route.query.id
  const value = Array.isArray(rawValue) ? rawValue[0] : rawValue
  const meetingId = Number(value)
  return Number.isInteger(meetingId) && meetingId > 0 ? meetingId : null
})
const restoredAudioUrl = ref('')
const restoredTranscriptionText = ref('')
const isRestoringMeeting = ref(false)
const minutesVersions = ref<MeetingMinutesVersion[]>([])
const selectedMinutesVersionId = ref<number | null>(null)
const restoredMinutesDocumentText = ref('')

const getRouteQueryText = (value: unknown) => Array.isArray(value) ? value[0] : value

const rememberFileName = (nextFileName: string) => {
  fileName.value = nextFileName
  const countStr = fileName.value.slice(-2)
  const nextCounter = parseInt(countStr, 10)
  if (Number.isFinite(nextCounter)) {
    recordingCounter.value = nextCounter
  }
  if (!fileNameHistory.value.includes(fileName.value)) {
    fileNameHistory.value.push(fileName.value)
  }
}

const initializeRecordNamesFromRoute = () => {
  if (route.query.title) {
    meetingTitle.value = getRouteQueryText(route.query.title) as string
  } else {
    meetingTitle.value = isUploadMode.value ? formatDefaultUploadTitle() : formatDefaultTitle()
  }
  
  if (route.query.fileName) {
    rememberFileName(getRouteQueryText(route.query.fileName) as string)
  } else {
    rememberFileName(generateDefaultFileName())
  }
}

const isMediaDocument = (doc: MeetingDocumentInfo) => ['audio', 'video', 'media'].includes(doc.type)

const getDocumentBaseName = (doc?: MeetingDocumentInfo | null) => {
  if (!doc?.filename) return ''
  return doc.filename
    .replace(/\.[^.]+$/, '')
    .replace(/_(转录内容|会议纪要|情绪分析)$/, '')
}

const inferFileNameFromMeeting = (meeting: any, documents: MeetingDocumentInfo[]) => {
  const title = String(meeting?.title || '')
  const titlePrefix = title.match(/^(\d{8,})/)
  if (titlePrefix?.[1]) return titlePrefix[1]

  const mediaDoc = documents.find(isMediaDocument)
  const transcriptionDoc = documents.find(doc => doc.type === 'transcription')
  return getDocumentBaseName(mediaDoc) || getDocumentBaseName(transcriptionDoc) || generateDefaultFileName()
}

const fetchDocumentText = async (doc?: MeetingDocumentInfo | null) => {
  if (!doc) return ''
  const response = await fetch(buildMeetingDocumentUrl(doc, { inline: true }))
  if (!response.ok) {
    throw new Error(`HTTP ${response.status}`)
  }
  return await response.text()
}

const displayMinutesVersions = computed<MeetingMinutesVersion[]>(() => {
  if (minutesVersions.value.length > 0) return minutesVersions.value

  const summary = restoredMinutesDocumentText.value.trim()
  if (!summary) return []

  return [{
    id: 0,
    meeting_id: restoredMeetingId.value || 0,
    version: 1,
    summary,
    instruction: '原始纪要',
    source_version_id: null,
    is_current: true
  }]
})

const selectedMinutesVersion = computed(() => {
  const versions = displayMinutesVersions.value
  if (!versions.length) return null
  return versions.find(version => version.id === selectedMinutesVersionId.value)
    || versions.find(version => version.is_current)
    || versions[0]
})

const formatMinutesVersionLabel = (version: MeetingMinutesVersion) => {
  const labelParts = [`v${version.version}`]
  if (version.is_current) labelParts.push('当前')
  if (version.instruction && version.instruction !== '原始纪要') {
    labelParts.push(version.instruction)
  }
  return labelParts.join(' · ')
}

const applySelectedMinutesVersion = () => {
  const summary = selectedMinutesVersion.value?.summary || restoredMinutesDocumentText.value || ''
  store.meetingSummary = summary
  editorContent.value = summary
}

const selectPreferredMinutesVersion = () => {
  const preferred = displayMinutesVersions.value.find(version => version.is_current)
    || displayMinutesVersions.value[0]
  selectedMinutesVersionId.value = preferred?.id ?? null
  applySelectedMinutesVersion()
}

const handleMinutesVersionChange = () => {
  applySelectedMinutesVersion()
}

const resetRestoredMinutes = () => {
  minutesVersions.value = []
  selectedMinutesVersionId.value = null
  restoredMinutesDocumentText.value = ''
}

const fetchMinutesVersions = async (meetingId: number) => {
  try {
    const response = await meetingApi.getMeetingMinutesVersions(meetingId)
    minutesVersions.value = response.success && response.data
      ? response.data.versions || []
      : []
  } catch (error) {
    console.warn('历史会议纪要版本加载失败:', error)
    minutesVersions.value = []
  }
}

const loadRestoredMeeting = async (meetingId: number) => {
  isRestoringMeeting.value = true
  restoredAudioUrl.value = ''
  restoredTranscriptionText.value = ''
  resetRestoredMinutes()

  try {
    const [meetingResponse, docsResponse] = await Promise.all([
      meetingApi.getMeeting(meetingId),
      meetingApi.getMeetingDocuments({ meeting_id: meetingId })
    ])

    if (!meetingResponse.success || !meetingResponse.data) {
      throw new Error(meetingResponse.error || '会议记录不存在')
    }

    const meeting = meetingResponse.data as any
    const documents = docsResponse.success && docsResponse.data
      ? docsResponse.data.documents as MeetingDocumentInfo[]
      : []

    meetingTitle.value = meeting.title || meetingTitle.value || formatDefaultUploadTitle()
    rememberFileName(inferFileNameFromMeeting(meeting, documents))

    const transcriptionDoc = documents.find(doc => doc.type === 'transcription')
    const minutesDoc = documents.find(doc => doc.type === 'minutes')
    const mediaDoc = documents.find(isMediaDocument)

    if (mediaDoc) {
      restoredAudioUrl.value = buildMeetingDocumentUrl(mediaDoc, { inline: true })
    }

    try {
      restoredTranscriptionText.value = await fetchDocumentText(transcriptionDoc)
    } catch (error) {
      console.warn('历史转录文档加载失败，将优先使用上传分段回显:', error)
      restoredTranscriptionText.value = ''
    }

    try {
      const minutes = await fetchDocumentText(minutesDoc)
      restoredMinutesDocumentText.value = minutes
    } catch (error) {
      if (minutesDoc) {
        console.warn('历史会议纪要加载失败:', error)
      }
      restoredMinutesDocumentText.value = ''
    }

    await fetchMinutesVersions(meetingId)
    selectPreferredMinutesVersion()
  } catch (error) {
    console.error('加载历史会议失败:', error)
    ElMessage.error(`加载历史会议失败：${(error as Error).message || String(error)}`)
  } finally {
    isRestoringMeeting.value = false
  }
}

const initializeRecordPage = async () => {
  initializeRecordNamesFromRoute()

  if (restoredMeetingId.value) {
    await loadRestoredMeeting(restoredMeetingId.value)
    return
  }

  restoredAudioUrl.value = ''
  restoredTranscriptionText.value = ''
  resetRestoredMinutes()
  store.meetingSummary = ''
  editorContent.value = ''
}

onMounted(() => {
  void initializeRecordPage()
})

watch(() => route.fullPath, () => {
  void initializeRecordPage()
})

function formatDefaultTitle() {
  const now = new Date()
  const year = now.getFullYear()
  const month = now.getMonth() + 1
  const day = now.getDate()
  const hours = now.getHours()
  const minutes = now.getMinutes()
  const seconds = now.getSeconds()
  return `${year}年${month}月${day}日${hours}时${minutes}分${seconds}秒录音`
}

function formatDefaultUploadTitle() {
  const now = new Date()
  const year = now.getFullYear()
  const month = now.getMonth() + 1
  const day = now.getDate()
  const hours = now.getHours()
  const minutes = now.getMinutes()
  const seconds = now.getSeconds()
  return `${year}年${month}月${day}日${hours}时${minutes}分${seconds}秒上传识别`
}

function generateDefaultFileName() {
  const now = new Date()
  const year = now.getFullYear()
  const month = String(now.getMonth() + 1).padStart(2, '0')
  const day = String(now.getDate()).padStart(2, '0')
  const count = String(recordingCounter.value).padStart(2, '0')
  return `${year}${month}${day}${count}`
}

function incrementRecordingCounter() {
  recordingCounter.value++
  const newFileName = generateDefaultFileName()
  fileName.value = newFileName
  
  // 将新文件名添加到历史记录
  if (!fileNameHistory.value.includes(newFileName)) {
    fileNameHistory.value.push(newFileName)
  }
}

const handleShare = async () => {
  try {
    shareDialogVisible.value = true
    shareUrl.value = 'http://zst.asr.com/' + Date.now()
  } catch (error) {
    ElMessage.error('生成分享链接失败：' + error)
  }
}

const nextFileName = computed(() => {
  // 生成下一个文件名预览
  const nextCounter = recordingCounter.value + 1
  const now = new Date()
  const year = now.getFullYear()
  const month = String(now.getMonth() + 1).padStart(2, '0')
  const day = String(now.getDate()).padStart(2, '0')
  const count = String(nextCounter).padStart(2, '0')
  return `${year}${month}${day}${count}`
})

// 用于显示在下拉框中的所有文件名，包括下一个预测文件名
const displayFileNames = computed(() => {
  const result = [...fileNameHistory.value]
  if (nextFileName.value && !result.includes(nextFileName.value)) {
    result.push(nextFileName.value)
  }
  return result
})



const handleTranslate = () => {
  translateDialogVisible.value = true
  translateText.value = editorContent.value
}

const handleSummary = (summary: string) => {
  editorContent.value = summary
}

const handleSummaryGenerated = async (summary: string) => {
  editorContent.value = summary

  if (!restoredMeetingId.value) return

  await fetchMinutesVersions(restoredMeetingId.value)
  const preferred = minutesVersions.value.find(version => version.is_current)
    || minutesVersions.value.find(version => version.summary === summary)
    || minutesVersions.value[0]

  if (preferred) {
    selectedMinutesVersionId.value = preferred.id
    applySelectedMinutesVersion()
    return
  }

  restoredMinutesDocumentText.value = summary
  selectPreferredMinutesVersion()
}

const handleToggleMinutesPanel = (visible: boolean) => {
  showMinutesPanel.value = visible
}

const visibleMinutesPanel = computed(() => showMinutesPanel.value)

const buildTranscriptionContent = () => {
  if (store.speakerSegments && store.speakerSegments.length > 0) {
    return store.speakerSegments.map((segment, index) => {
      const speaker = segment.speaker || `说话人${index + 1}`
      let timeRange = '00:00:00 - 00:00:00'
      if (segment.startTime && segment.endTime) {
        timeRange = `${segment.startTime} - ${segment.endTime}`
      } else if (segment.timestamp && Array.isArray(segment.timestamp) && segment.timestamp.length > 0) {
        const startMs = segment.timestamp[0][0]
        const endMs = segment.timestamp[segment.timestamp.length - 1][1]
        const formatMs = (ms: number) => {
          const totalSeconds = Math.floor(ms / 1000)
          const hours = Math.floor(totalSeconds / 3600)
          const minutes = Math.floor((totalSeconds % 3600) / 60)
          const seconds = totalSeconds % 60
          return `${hours.toString().padStart(2, '0')}:${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}`
        }
        timeRange = `${formatMs(startMs)} - ${formatMs(endMs)}`
      }

      const cleanText = segment.text.includes('<mark')
        ? segment.text.replace(/<mark class="[^"]*">(.*?)<\/mark>/g, '$1')
        : segment.text
      const translation = store.enableTranslation ? segment.translation?.trim() : ''

      return translation
        ? `**${speaker}** [${timeRange}]\n${cleanText}\n\n翻译：${translation}`
        : `**${speaker}** [${timeRange}]\n${cleanText}`
    }).join('\n\n')
  }

  return store.transcript || ''
}

const summaryTranscriptForEditor = computed(() => {
  return restoredTranscriptionText.value.trim() || buildTranscriptionContent()
})

// 创建会议并保存所有内容
const saveMeeting = async () => {
  if (isSaving.value) return
  
  try {
    isSaving.value = true
    
    // 检查必要的内容
    if (!meetingTitle.value.trim()) {
      ElMessage.warning('请输入会议标题')
      return
    }
    
    const hasTranscription = (store.speakerSegments && store.speakerSegments.length > 0) || store.transcript.trim()
    
    if (!hasTranscription) {
      ElMessage.warning('请先进行语音转录，获取转录内容')
      return
    }

    // 保存前清理所有说话人分段中可能残留的HTML标记
    if (store.speakerSegments && store.speakerSegments.length > 0) {
      store.speakerSegments.forEach(segment => {
        if (segment.text.includes('<mark')) {
          segment.text = segment.text.replace(/<mark class="[^"]*">(.*?)<\/mark>/g, '$1')
        }
      })
      console.log('✅ 保存前已清理所有HTML标记')
    }

    const fullTranscriptionContent = buildTranscriptionContent()
    const generatedMeetingMinutes = editorContent.value.trim()

    // 准备会议数据
    const meetingData: any = {
      title: meetingTitle.value.trim(),
      description: `会议记录 - ${fileName.value}`,
      transcriptionContent: fullTranscriptionContent,
      language: 'zh-CN',
      recognitionMode: recognitionMode.value,
      transcriptionSource: isUploadMode.value ? 'upload' : 'realtime',
      endTime: new Date().toISOString() // 添加会议结束时间
    }
    if (generatedMeetingMinutes) {
      meetingData.meetingMinutes = generatedMeetingMinutes
      meetingData.summary = generatedMeetingMinutes
    }
    if (store.uploadedMediaTaskId) {
      meetingData.uploadTaskId = store.uploadedMediaTaskId
      meetingData.audioFileName = store.uploadedMediaFileName || `${fileName.value}.wav`
    }

    // 处理音频文件
    if (store.audioUrl && !store.uploadedMediaTaskId) {
      try {
        const response = await fetch(store.audioUrl)
        const audioBlob = await response.blob()
        
        // 将Blob转换为base64格式
        const reader = new FileReader()
        const audioBase64 = await new Promise<string>((resolve, reject) => {
          reader.onload = () => resolve(reader.result as string)
          reader.onerror = reject
          reader.readAsDataURL(audioBlob)
        })
        
        // 添加音频文件到请求数据
        meetingData.audioFile = audioBase64
        meetingData.audioFileName = `${fileName.value}.wav`
        meetingData.audioFormat = 'wav'
        meetingData.sampleRate = 16000
        meetingData.channels = 1
        meetingData.audioFileSize = audioBlob.size
        
        console.log('音频文件准备完成:', {
          fileName: meetingData.audioFileName,
          size: meetingData.audioFileSize,
          format: meetingData.audioFormat
        })
      } catch (error) {
        console.warn('处理音频文件失败:', error)
        ElMessage.warning('音频文件处理失败，将仅保存文本内容')
      }
    }
    
    // 始终使用saveMeetingDocuments API来保存文档文件
    console.log('开始保存会议文档，数据:', meetingData)
    const result = await meetingApi.saveMeetingDocuments(meetingData)
    
    if (result.success) {
      ElMessage.success(isUploadMode.value ? '上传识别结果保存成功!' : '会议保存成功!')
      console.log('会议保存成功:', result.data)
      const savedMeetingId = (result.data as any)?.meeting_id || (result.data as any)?.id
      if (savedMeetingId) {
        router.push({
          name: 'meeting-detail',
          query: { id: String(savedMeetingId) }
        })
      }
      
      // 注释掉本地备份文件保存，直接上传到服务器
      // await saveLocalBackupFiles()
    } else {
      throw new Error(result.error || '保存失败')
    }
    
  } catch (error) {
    console.error('保存会议失败:', error)
    ElMessage.error('保存会议失败: ' + ((error as Error).message || '未知错误'))
  } finally {
    isSaving.value = false
  }
}

// 保存本地备份文件（可选功能）
const saveLocalBackupFiles = async () => {
  try {
    // 保存转录内容为 Markdown 文件
    const transcriptionContent = buildTranscriptionContent()
    if (transcriptionContent) {
      const transcriptionFileName = `${fileName.value}_转录内容.md`
      const transcriptionMarkdown = `# ${meetingTitle.value} - 转录内容\n\n${transcriptionContent}`
      const transcriptionBlob = new Blob([transcriptionMarkdown], { type: 'text/markdown' })
      await saveFileToLocal(transcriptionBlob, '', transcriptionFileName)
    }
    
    // 保存会议纪要为 Markdown 文件
    if (store.meetingSummary) {
      const minutesFileName = `${fileName.value}_会议纪要.md`
      const minutesContent = `# ${meetingTitle.value} - 会议纪要\n\n${store.meetingSummary}`
      const minutesBlob = new Blob([minutesContent], { type: 'text/markdown' })
      await saveFileToLocal(minutesBlob, '', minutesFileName)
    }
    
    // 保存音频文件
    if (store.audioUrl) {
      const response = await fetch(store.audioUrl)
      const audioBlob = await response.blob()
      const audioFileName = `${fileName.value}.wav`
      await saveFileToLocal(audioBlob, '', audioFileName)
    }
    
    console.log('本地备份文件保存完成')
  } catch (error) {
    console.warn('保存本地备份文件失败:', error)
  }
}

// 保存文件到本地的辅助函数
const saveFileToLocal = async (blob: Blob, filePath: string, fileName: string) => {
  try {
    // 直接创建下载链接，不弹出路径选择对话框
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = fileName
    // 设置为隐藏状态，避免用户看到链接
    link.style.display = 'none'
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    URL.revokeObjectURL(url)
    
    console.log(`文件已保存: ${fileName}`)
  } catch (error) {
    console.error('保存文件失败:', error)
    throw error
  }
}

// 文件保存和上传函数（保留原有功能）
const saveAndUploadFiles = async () => {
  try {
    // 如果用户手动选择了一个历史文件名，使用这个文件名
    const currentFileName = fileName.value
    
    // 保存文本内容到txt文件
    const textBlob = new Blob([editorContent.value], { type: 'text/plain' })
    const textUrl = URL.createObjectURL(textBlob)
    const textLink = document.createElement('a')
    textLink.href = textUrl
    textLink.download = `${currentFileName}.txt`
    textLink.click()
    URL.revokeObjectURL(textUrl)

    // 上传文本文件
    await uploadApi.uploadText(textBlob)

    // 如果有录音文件，保存并上传
    if (store.audioUrl) {
      const response = await fetch(store.audioUrl)
      const audioBlob = await response.blob()
      
      // 保存录音文件
      const audioLink = document.createElement('a')
      audioLink.href = store.audioUrl
      audioLink.download = `${currentFileName}.wav`
      audioLink.click()

      // 上传录音文件
      await uploadApi.uploadAudio(audioBlob)

      ElMessage.success('文件保存和上传成功')
    }
  } catch (error) {
    console.error('文件保存和上传失败:', error)
    ElMessage.error(`文件保存和上传失败：${error}`)
  }
}

function startEditTitle() {
  isEditingTitle.value = true
  // 下一个 tick 等 DOM 更新后再聚焦
  setTimeout(() => {
    if (titleInputRef.value) {
      titleInputRef.value.focus()
    }
  }, 0)
}

// 监控录音状态，在停止录音后自动递增计数器
watch(() => store.isRecording, (newVal, oldVal) => {
  // 如果从录音状态变为非录音状态，则增加计数器
  if (oldVal === true && newVal === false) {
    incrementRecordingCounter()
  }
})

watch(() => store.meetingSummary, (summary) => {
  editorContent.value = summary || ''
}, { immediate: true })
</script>

<template>
  <div class="app-container" v-loading="isRestoringMeeting">
    <header class="header">
      <div class="meeting-info-section">
        <div class="meeting-title-container">
          <template v-if="!isEditingTitle">
            <el-icon class="meeting-icon">
              <Upload v-if="isUploadMode" />
              <VideoCamera v-else />
            </el-icon>
            <h1 @click="startEditTitle" class="clickable-title">{{ meetingTitle }}</h1>
          </template>
          <template v-else>
            <el-icon class="meeting-icon">
              <Upload v-if="isUploadMode" />
              <VideoCamera v-else />
            </el-icon>
            <el-input 
              v-model="meetingTitle" 
              size="small" 
              class="title-input"
              ref="titleInputRef"
              @blur="isEditingTitle = false"
              @keyup.enter="isEditingTitle = false"
            />
          </template>
        </div>
        
        <div class="filename-container">
          <el-select v-model="fileName" size="small" class="filename-select">
            <el-option 
              v-for="name in displayFileNames" 
              :key="name" 
              :value="name" 
              :label="name" 
            />
          </el-select>
        </div>
        

        <div class="status-info">
          <span class="status-text">{{ pageStatusText }}</span>
          <span class="status-divider"></span>
        </div>
      </div>
      
      <div class="header-right">
        <div class="button-group">

          <el-tooltip content="保存会议记录到数据库" placement="top" popper-class="custom-tooltip">
            <el-button type="success" size="small" @click="saveMeeting" :loading="isSaving">
              <el-icon><document-add /></el-icon>{{ saveButtonText }}
            </el-button>
          </el-tooltip>
        </div>
      </div>
    </header>
    <div class="main-content">
      <div class="left-panel" :class="{ 'full-width': !visibleMinutesPanel }">
        <AsrPanel 
          @update:content="handleSummary" 
          @summary-generated="handleSummaryGenerated"
          @translate="handleTranslate" 
          @toggle-minutes-panel="handleToggleMinutesPanel"
          :recognition-mode="recognitionMode"
          :current-file-name="fileName" 
          :restored-meeting-id="restoredMeetingId"
          :restored-audio-url="restoredAudioUrl"
          :restored-transcription-text="restoredTranscriptionText"
        />
      </div>
      <transition name="slide-fade">
        <div class="right-panel" v-if="visibleMinutesPanel">
          <div class="editor-container">
            <div v-if="displayMinutesVersions.length > 0" class="minutes-version-bar">
              <div class="minutes-version-title">
                <span>会议纪要</span>
                <small>共 {{ displayMinutesVersions.length }} 个版本</small>
              </div>
              <el-select
                v-model="selectedMinutesVersionId"
                size="small"
                class="minutes-version-select"
                :disabled="displayMinutesVersions.length <= 1"
                @change="handleMinutesVersionChange"
              >
                <el-option
                  v-for="version in displayMinutesVersions"
                  :key="version.id"
                  :label="formatMinutesVersionLabel(version)"
                  :value="version.id"
                />
              </el-select>
            </div>
            <div class="editor-content">
              <RichTextEditor
                v-model:content="editorContent"
                :meeting-id="restoredMeetingId"
                :summary-transcript="summaryTranscriptForEditor"
                @summary-generated="handleSummaryGenerated"
              />
            </div>
          </div>
        </div>
      </transition>
    </div>

    <TranslateDialog
      v-model:visible="translateDialogVisible"
      :text="translateText"
    />
  </div>
</template>

<style lang="scss" scoped>
// 变量定义
$primary-color: #fff;
$background-color: #f5f7fa;
$border-color: #e4e7ed;
$text-color: #303133;
$text-secondary: #909399;
$success-color: #67c23a;
$shadow-color: rgba(0, 0, 0, 0.1);
$border-radius: 8px;
$spacing-xs: 4px;
$spacing-sm: 8px;
$spacing-md: 12px;
$spacing-lg: 16px;
$spacing-xl: 20px;

// 全局覆盖Element Plus选择器样式
.meeting-info-section {
  .el-select,
  .el-select *,
  .el-input,
  .el-input *,
  .el-input__wrapper,
  .el-input__inner {
    background: transparent !important;
    background-color: transparent !important;
    border: none !important;
    box-shadow: none !important;
    outline: none !important;
    color: white !important;
  }
  
  .el-input__inner {
    color: white !important;
    
    &::placeholder {
      color: rgba(255, 255, 255, 0.6) !important;
    }
  }
  
  .el-select__caret,
  .el-select .el-select__caret,
  .el-input__suffix,
  .el-input__suffix-inner,
  .el-select__suffix,
  .el-icon {
    display: none !important;
    visibility: hidden !important;
    opacity: 0 !important;
  }
  
  .el-select__selected-item {
    color: white !important;
  }
  
  .el-select__tags {
    color: white !important;
  }
  
  input {
    color: white !important;
  }
}

.app-container {
  height: 100vh;
  width: 100%;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  display: flex;
  flex-direction: column;
  overflow: hidden;
  padding: 0;
  margin: 0;
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
}

.header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  background: transparent;
  border-bottom: none;
  height: 60px;
  padding: 0 $spacing-xl;
  flex-shrink: 0;
}

.meeting-info-section {
  display: flex;
  align-items: center;
  gap: 20px;
  background: transparent;
  padding: 12px 20px;
  border-radius: 8px;
  margin-right: 20px;
}

.meeting-title-container {
  display: flex;
  align-items: center;
  gap: 8px;
  background: transparent;
  border: none;
  border-radius: 5px;
  padding: 6px 12px;
  min-width: 180px;
  max-width: 300px;
  
  .meeting-icon {
    color: white;
    font-size: 18px;
    flex-shrink: 0;
  }
  
  h1 {
    color: white;
    font-weight: 600;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    flex: 1;
  }
  
  .clickable-title {
    cursor: pointer;
    transition: all 0.2s ease;
    padding: 4px 8px;
    border-radius: 4px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    flex: 1;
    
    &:hover {
      background-color: rgba(255, 255, 255, 0.1);
      transform: scale(1.02);
    }
  }
  
  .title-input {
    flex: 1;
  }
}

.filename-container {
  display: flex;
  align-items: center;
}

.filename-select {
  width: 160px;
  
  :deep(.el-select),
  :deep(.el-select *) {
    background: transparent !important;
    background-color: transparent !important;
    border: none !important;
    box-shadow: none !important;
    outline: none !important;
  }
  
  :deep(.el-select) {
    .el-input,
    .el-input *,
    .el-input__wrapper,
    .el-input__wrapper *,
    .el-input__inner {
      background: transparent !important;
      background-color: transparent !important;
      border: none !important;
      box-shadow: none !important;
      outline: none !important;
    }
    
    .el-input__inner {
      color: white !important;
      
      &::placeholder {
        color: rgba(255, 255, 255, 0.6) !important;
      }
    }
    
    .el-select__caret {
      color: rgba(255, 255, 255, 0.8) !important;
    }
  }
  
  :deep(.el-select:hover) {
    .el-input__wrapper {
      background-color: rgba(255, 255, 255, 0.1) !important;
      border-radius: 4px;
    }
  }
}



.status-info {
  display: flex;
  align-items: center;
  gap: 16px;
  margin-left: 10px;
}

.status-text {
  color: #67c23a;
  font-size: 14px;
  font-weight: 500;
}

.status-divider {
  width: 1px;
  height: 14px;
  background-color: rgba(255, 255, 255, 0.3);
}



h1 {
  font-size: 20px;
  font-weight: 600;
  color: #333;
  margin: 0;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.meeting-title-container h1 {
  color: white !important;
  font-weight: 600;
}

.header-right {
  display: flex;
  align-items: center;
  gap: $spacing-sm;
  flex-shrink: 0;
}

.button-group {
  display: flex;
  gap: 12px;
  align-items: center;
}

.button-group .el-button {
  display: flex;
  align-items: center;
  gap: 4px;
  min-width: 90px;
  justify-content: center;
  padding: 8px 16px;
  height: 32px;
  background: rgba(255, 255, 255, 0.2) !important;
  border: 1px solid rgba(255, 255, 255, 0.3) !important;
  color: white !important;
  
  &:hover {
    background: rgba(255, 255, 255, 0.3) !important;
    border-color: rgba(255, 255, 255, 0.5) !important;
  }
}

.button-group .el-button .el-icon {
  margin-right: 4px;
  color: white !important;
}

// 自定义tooltip样式
:deep(.custom-tooltip) {
  background-color: #34495e !important;
  padding: 8px 12px !important;
  border-radius: 6px !important;
  font-size: 13px !important;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.1) !important;
}

:deep(.custom-tooltip .el-popper__arrow::before) {
  background-color: #34495e !important;
  border: none !important;
}

.main-content {
  flex: 1;
  display: flex;
  width: 100%;
  min-height: 0;
  overflow: hidden;
  gap: $spacing-lg;
  background-color: $background-color;
  padding: $spacing-lg;
  box-sizing: border-box;
}

.left-panel,
.right-panel {
  flex: 1;
  min-width: 0;
  height: 100%;
  display: flex;
  flex-direction: column;
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}

.left-panel.full-width {
  flex: 1;
  max-width: 100%;
}

.editor-container {
  height: 100%;
  background: $primary-color;
  border-radius: $border-radius;
  box-shadow: 0 2px $spacing-md 0 $shadow-color;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.minutes-version-bar {
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: $spacing-md;
  min-height: 52px;
  padding: 10px $spacing-lg;
  border-bottom: 1px solid $border-color;
  background: $primary-color;
}

.minutes-version-title {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;

  span {
    color: $text-color;
    font-size: 15px;
    font-weight: 600;
    line-height: 1.3;
  }

  small {
    color: $text-secondary;
    font-size: 12px;
    line-height: 1.3;
  }
}

.minutes-version-select {
  width: 180px;
  flex-shrink: 0;
}

.editor-content {
  flex: 1;
  min-height: 0;
  background: $background-color;
  overflow: auto;
}

@media screen and (max-width: 768px) {
  .main-content {
    flex-direction: column;
  }

  .minutes-version-bar {
    align-items: stretch;
    flex-direction: column;
  }

  .minutes-version-select {
    width: 100%;
  }
  
  .header-left {
    gap: $spacing-sm;
  }
}

.title-input {
  width: 200px;
}

/* 会议纪要区域显示/隐藏动画 */
.slide-fade-enter-active {
  transition: all 0.4s cubic-bezier(0.4, 0, 0.2, 1);
}

.slide-fade-leave-active {
  transition: all 0.3s cubic-bezier(0.4, 0, 0.6, 1);
}

.slide-fade-enter-from {
  transform: translateX(100%);
  opacity: 0;
}

.slide-fade-leave-to {
  transform: translateX(100%);
  opacity: 0;
}

.slide-fade-enter-to,
.slide-fade-leave-from {
  transform: translateX(0);
  opacity: 1;
}
</style>
