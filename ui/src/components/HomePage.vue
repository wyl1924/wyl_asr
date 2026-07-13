<script setup lang="ts">
import { useRouter } from 'vue-router'
import { ref, onMounted, onUnmounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Search, ArrowDown, Share, Delete, Document, Microphone, User, Collection, Setting, ChatDotRound, MoreFilled, Upload } from '@element-plus/icons-vue'
import { meetingApi } from '../api/meeting'
import ShareDialog from './ShareDialog.vue'
import SettingsDialog from './SettingsDialog.vue'

const router = useRouter()

// 生成默认的会议标题
function generateDefaultMeetingTitle() {
  const now = new Date()
  const year = now.getFullYear()
  const month = now.getMonth() + 1
  const day = now.getDate()
  const hours = now.getHours()
  const minutes = now.getMinutes()
  const seconds = now.getSeconds()
  return `${year}年${month}月${day}日${hours}时${minutes}分${seconds}秒会议`
}

// 生成默认的文件名
function generateDefaultFileName() {
  const now = new Date()
  const year = now.getFullYear()
  const month = String(now.getMonth() + 1).padStart(2, '0')
  const day = String(now.getDate()).padStart(2, '0')
  return `${year}${month}${day}01`
}

// 开始录音，同时传递会议名称和文件名
const startRecording = () => {
  const meetingTitle = generateDefaultMeetingTitle()
  const fileName = generateDefaultFileName()
  router.push({
    path: '/record',
    query: {
      title: meetingTitle,
      fileName: fileName
    }
  })
}

const startUploadRecognition = () => {
  const fileName = generateDefaultFileName()
  router.push({
    path: '/record',
    query: {
      mode: 'upload',
      title: `${fileName}上传音视频识别`,
      fileName
    }
  })
}

interface MeetingData {
  id: number
  title: string
  start_time: string
  duration: string
  hasAudio: boolean
  hasTranscription: boolean
  hasMinutes: boolean
  recognitionMode?: string
  transcriptionSource?: string
  uploadTaskId?: string | null
}

const searchText = ref('')
const allTableData = ref<MeetingData[]>([])
const loading = ref(false)
const isActualMobile = ref(false)

// 分页相关
const currentPage = ref(1)
const pageSize = ref(10)
const total = ref(0)

// 存储过滤后的数据
const filteredData = ref<MeetingData[]>([])
const tableData = ref<MeetingData[]>([])

// 分享相关
const shareDialogVisible = ref(false)
const shareUrl = ref('')
const shareFileName = ref('')

// 字幕设置对话框
const subtitleSettingsVisible = ref(false)

const isMediaDocument = (doc: any) => ['audio', 'video', 'media'].includes(doc.type)
const isUploadMeeting = (row: MeetingData) => (
  row.transcriptionSource === 'upload' ||
  row.recognitionMode === 'upload' ||
  Boolean(row.uploadTaskId) ||
  row.title.includes('上传')
)

const inferRecordFileName = (row: MeetingData) => {
  const titlePrefix = row.title.match(/^(\d{8,})/)
  if (titlePrefix?.[1]) return titlePrefix[1]
  return row.title.replace(/\s+/g, '').slice(0, 24) || String(row.id)
}

// 获取会议列表
const fetchMeetings = async () => {
  loading.value = true
  try {
    const response = await meetingApi.getMeetingList()
    if (response.success && response.data) {
      const meetingsWithDocs = await Promise.all(
        response.data.map(async (meeting: any) => {
          try {
            const [docsResponse, detailResponse] = await Promise.all([
              meetingApi.getMeetingDocuments({
                meeting_id: meeting.id
              }),
              meetingApi.getMeeting(meeting.id)
            ])
            let hasAudio = false
            let hasTranscription = false
            let hasMinutes = false
            if (docsResponse.success && docsResponse.data) {
              const documents = docsResponse.data.documents
              hasAudio = documents.some(isMediaDocument)
              hasTranscription = documents.some((doc: any) => doc.type === 'transcription')
              hasMinutes = documents.some((doc: any) => doc.type === 'minutes')
            }
            const detail = detailResponse.success ? (detailResponse.data as any) : meeting
            return {
              id: meeting.id,
              title: meeting.title,
              start_time: meeting.start_time,
              duration: meeting.duration || '未知',
              hasAudio,
              hasTranscription,
              hasMinutes,
              recognitionMode: detail?.recognitionMode || detail?.recognition_mode || meeting.recognitionMode || meeting.recognition_mode,
              transcriptionSource: detail?.transcription_source || meeting.transcription_source,
              uploadTaskId: detail?.uploadTaskId || detail?.upload_task_id || meeting.uploadTaskId || meeting.upload_task_id || null
            }
          } catch (error) {
            console.warn(`获取会议 ${meeting.id} 的文档信息失败:`, error)
            return {
              id: meeting.id,
              title: meeting.title,
              start_time: meeting.start_time,
              duration: meeting.duration || '未知',
              hasAudio: false,
              hasTranscription: false,
              hasMinutes: false,
              recognitionMode: meeting.recognitionMode || meeting.recognition_mode,
              transcriptionSource: meeting.transcription_source,
              uploadTaskId: meeting.uploadTaskId || meeting.upload_task_id || null
            }
          }
        })
      )
      allTableData.value = meetingsWithDocs
      filteredData.value = [...allTableData.value]
      total.value = allTableData.value.length
      updateTableData()
    } else {
      ElMessage.error('获取会议列表失败，检查服务是否启动')
    }
  } catch (error) {
    console.error('获取会议列表失败:', error)
    ElMessage.error('无法连接到服务器')
  } finally {
    loading.value = false
  }
}

const updateTableData = () => {
  const startIndex = (currentPage.value - 1) * pageSize.value
  const endIndex = startIndex + pageSize.value
  tableData.value = filteredData.value.slice(startIndex, endIndex)
}

const handleCurrentChange = (val: number) => {
  currentPage.value = val
  updateTableData()
}

const updateLayoutMode = () => {
  const screenWidth = window.screen?.width || window.innerWidth
  const pointerCoarse = window.matchMedia('(pointer: coarse)').matches
  const hoverNone = window.matchMedia('(hover: none)').matches
  isActualMobile.value = screenWidth <= 820 && (pointerCoarse || hoverNone)
}

onMounted(() => {
  updateLayoutMode()
  window.addEventListener('resize', updateLayoutMode)
  fetchMeetings()
})

onUnmounted(() => {
  window.removeEventListener('resize', updateLayoutMode)
})

const handleSearch = () => {
  const keyword = searchText.value.trim()
  if (!keyword) {
    filteredData.value = allTableData.value
  } else {
    filteredData.value = allTableData.value.filter(item =>
      item.title.includes(keyword) ||
      item.start_time.includes(keyword)
    )
  }
  total.value = filteredData.value.length
  currentPage.value = 1
  updateTableData()
}

const handleSettings = () => {
  router.push('/settings')
}

const handleSubtitleSettings = () => {
  subtitleSettingsVisible.value = true
}

const handleSpeakerRegistration = () => {
  router.push('/speaker-registration')
}

const handleHotwords = () => {
  router.push('/hotwords')
}

const handleView = (row: MeetingData) => {
  if (isUploadMeeting(row)) {
    router.push({
      path: '/record',
      query: {
        mode: 'upload',
        meetingId: String(row.id),
        title: row.title,
        fileName: inferRecordFileName(row)
      }
    })
    return
  }

  router.push({
    path: '/meeting-detail',
    query: { id: row.id }
  })
}

const handleDetail = (row: MeetingData) => {
  router.push({
    path: '/meeting-detail',
    query: { id: row.id }
  })
}

type HeaderCommand = 'speaker' | 'hotwords' | 'subtitle' | 'settings'
type DownloadCommand = 'audio' | 'transcription:docx' | 'transcription:pdf' | 'minutes:docx' | 'minutes:pdf'
type MeetingActionCommand = DownloadCommand | 'detail' | 'share' | 'delete'
type DownloadType = 'audio' | 'transcription' | 'minutes'
type TextDownloadFormat = 'docx' | 'pdf'

const handleHeaderCommand = (command: HeaderCommand) => {
  switch (command) {
    case 'speaker':
      handleSpeakerRegistration()
      break
    case 'hotwords':
      handleHotwords()
      break
    case 'subtitle':
      handleSubtitleSettings()
      break
    case 'settings':
      handleSettings()
      break
  }
}

const parseDownloadCommand = (command: DownloadCommand): {
  type: DownloadType
  format?: TextDownloadFormat
} => {
  if (command === 'audio') {
    return { type: 'audio' }
  }

  const [type, format] = command.split(':') as [DownloadType, TextDownloadFormat]
  return { type, format }
}

const handleDownload = async (row: MeetingData, command: DownloadCommand) => {
  const { type, format } = parseDownloadCommand(command)

  try {
    switch (type) {
      case 'audio':
        if (!row.hasAudio) { ElMessage.warning('该会议没有音频文件'); return }
        break
      case 'transcription':
        if (!row.hasTranscription) { ElMessage.warning('该会议没有转录内容'); return }
        break
      case 'minutes':
        if (!row.hasMinutes) { ElMessage.warning('该会议没有会议纪要'); return }
        break
    }
    const docsResponse = await meetingApi.getMeetingDocuments({ meeting_id: row.id })
    if (!docsResponse.success || !docsResponse.data) {
      ElMessage.error('获取文档列表失败'); return
    }
    let targetDoc = null
    const documents = docsResponse.data.documents
    switch (type) {
      case 'audio': targetDoc = documents.find(isMediaDocument); break
      case 'transcription': targetDoc = documents.find((doc: any) => doc.type === 'transcription'); break
      case 'minutes': targetDoc = documents.find((doc: any) => doc.type === 'minutes'); break
    }
    if (!targetDoc) { ElMessage.error('未找到对应的文档文件'); return }
    const downloadResponse = await meetingApi.downloadMeetingDocument(
      targetDoc.id ?? targetDoc.file_path,
      targetDoc.filename,
      type === 'audio' ? undefined : format
    )
    if (downloadResponse.success) {
      ElMessage.success('下载成功')
    } else {
      ElMessage.error('下载失败')
    }
  } catch (error) {
    console.error('下载失败:', error)
    ElMessage.error('下载失败')
  }
}

const handleShare = (row: MeetingData) => {
  const baseUrl = window.location.origin
  shareUrl.value = `${baseUrl}/meeting-detail?id=${row.id}`
  shareFileName.value = row.title
  shareDialogVisible.value = true
}

const handleDelete = async (row: MeetingData) => {
  try {
    await ElMessageBox.confirm(
      `确定要删除会议 "${row.title}" 吗？此操作不可恢复。`,
      '确认删除',
      {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'warning',
      }
    )
    const response = await meetingApi.deleteMeeting(row.id)
    if (response.success) {
      ElMessage.success('删除成功')
      await fetchMeetings()
    } else {
      ElMessage.error('删除失败')
    }
  } catch (error) {
    if (error !== 'cancel') {
      console.error('删除失败:', error)
      ElMessage.error('删除失败')
    }
  }
}

const handleCardAction = (row: MeetingData, command: MeetingActionCommand) => {
  switch (command) {
    case 'detail':
      handleDetail(row)
      break
    case 'share':
      handleShare(row)
      break
    case 'delete':
      handleDelete(row)
      break
    default:
      handleDownload(row, command)
  }
}
</script>

<template>
  <div class="home-container" :class="{ 'mobile-layout': isActualMobile }">
    <header class="home-header">
      <div class="logo-wrap">
        <img src="/icons/smart-meeting-logo.svg" alt="智能会议" class="logo-icon" />
        <div class="logo-text">
          <span class="logo-title">智能会议</span>
          <span class="logo-sub">实时转写与音视频识别</span>
        </div>
      </div>

      <div class="header-actions">
        <el-dropdown
          trigger="click"
          @command="(cmd: HeaderCommand) => handleHeaderCommand(cmd)"
        >
          <button type="button" class="settings-btn">
            <el-icon><Setting /></el-icon>
            设置
          </button>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item command="speaker">
                <el-icon><User /></el-icon>
                说话人注册
              </el-dropdown-item>
              <el-dropdown-item command="hotwords">
                <el-icon><Collection /></el-icon>
                热词管理
              </el-dropdown-item>
              <el-dropdown-item command="subtitle">
                <el-icon><ChatDotRound /></el-icon>
                字幕设置
              </el-dropdown-item>
              <el-dropdown-item command="settings" divided>
                <el-icon><Setting /></el-icon>
                系统设置
              </el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
      </div>
    </header>

    <main class="main-content">
      <section class="workspace-hero" aria-label="识别入口">
        <div class="hero-copy">
          <p class="eyebrow">WYL ASR Workspace</p>
          <h1>选择识别方式</h1>
          <p>现场会议走实时识别，已有录音或视频走上传识别。两种流程分开，后续页面也会显示对应内容。</p>
        </div>

        <div class="workflow-grid">
          <button type="button" class="workflow-card live-card" @click="startRecording">
            <span class="workflow-icon">
              <el-icon><Microphone /></el-icon>
            </span>
            <span class="workflow-content">
              <span class="workflow-title">实时识别</span>
              <span class="workflow-desc">连接麦克风或服务器采集，边说边转写，适合现场会议。</span>
              <span class="workflow-meta">进入实时转录工作台</span>
            </span>
          </button>

          <button type="button" class="workflow-card upload-card" @click="startUploadRecognition">
            <span class="workflow-icon">
              <el-icon><Upload /></el-icon>
            </span>
            <span class="workflow-content">
              <span class="workflow-title">上传音视频</span>
              <span class="workflow-desc">上传已有音频或视频文件，离线生成转写、说话人识别和纪要。</span>
              <span class="workflow-meta">进入上传识别工作台</span>
            </span>
          </button>
        </div>
      </section>

      <section class="history-panel" aria-label="会议记录">
        <div class="list-toolbar">
          <div class="title-block">
            <h2 class="section-title">最近记录</h2>
            <span class="record-count">共 {{ total }} 条</span>
          </div>
          <div class="search-wrap">
            <el-input
              v-model="searchText"
              placeholder="搜索会议名称或时间"
              class="search-input"
              @input="handleSearch"
              @clear="handleSearch"
              clearable
            >
              <template #prefix>
                <el-icon><Search /></el-icon>
              </template>
            </el-input>
          </div>
        </div>

        <div class="list-container" v-loading="loading">
          <div v-if="tableData.length === 0 && !loading" class="empty-state">
            <div class="empty-title">暂无会议记录</div>
            <div class="empty-sub">从上方选择一种识别方式，完成后记录会出现在这里。</div>
          </div>

          <article
            v-for="row in tableData"
            :key="row.id"
            class="meeting-card"
            role="button"
            tabindex="0"
            @click="handleView(row)"
            @keydown.enter="handleView(row)"
            @keydown.space.prevent="handleView(row)"
          >
            <div class="card-info">
              <div class="card-title">{{ row.title }}</div>
              <div class="card-meta">
                <span>{{ row.start_time }}</span>
                <span>{{ row.duration }}</span>
              </div>
              <div class="card-tags">
                <span v-if="isUploadMeeting(row)" class="badge badge-upload">上传识别</span>
                <span v-if="row.hasAudio" class="badge badge-audio">音视频</span>
                <span v-if="row.hasTranscription" class="badge badge-trans">转录</span>
                <span v-if="row.hasMinutes" class="badge badge-minutes">纪要</span>
              </div>
            </div>

            <div class="card-actions" @click.stop>
              <el-dropdown
                @command="(cmd: MeetingActionCommand) => handleCardAction(row, cmd)"
                trigger="click"
              >
                <button
                  type="button"
                  class="action-btn more-btn"
                  aria-label="更多操作"
                  title="更多操作"
                  @click.stop
                  @keydown.enter.stop
                  @keydown.space.stop
                >
                  <el-icon><MoreFilled /></el-icon>
                </button>
                <template #dropdown>
                  <el-dropdown-menu>
                    <el-dropdown-item command="detail">
                      <el-icon><Document /></el-icon>
                      查看详情
                    </el-dropdown-item>
                    <el-dropdown-item command="share">
                      <el-icon><Share /></el-icon>
                      分享
                    </el-dropdown-item>
                    <el-dropdown-item command="audio" :disabled="!row.hasAudio">
                      <el-icon><ArrowDown /></el-icon>
                      下载音频文件
                    </el-dropdown-item>
                    <el-dropdown-item command="transcription:docx" :disabled="!row.hasTranscription">
                      <el-icon><ArrowDown /></el-icon>
                      转录内容 Word
                    </el-dropdown-item>
                    <el-dropdown-item command="transcription:pdf" :disabled="!row.hasTranscription">
                      <el-icon><ArrowDown /></el-icon>
                      转录内容 PDF
                    </el-dropdown-item>
                    <el-dropdown-item command="minutes:docx" :disabled="!row.hasMinutes">
                      <el-icon><ArrowDown /></el-icon>
                      会议纪要 Word
                    </el-dropdown-item>
                    <el-dropdown-item command="minutes:pdf" :disabled="!row.hasMinutes">
                      <el-icon><ArrowDown /></el-icon>
                      会议纪要 PDF
                    </el-dropdown-item>
                    <el-dropdown-item command="delete" divided>
                      <el-icon><Delete /></el-icon>
                      删除
                    </el-dropdown-item>
                  </el-dropdown-menu>
                </template>
              </el-dropdown>
            </div>
          </article>
        </div>

        <div class="pagination-wrap" v-if="total > pageSize">
          <el-pagination
            v-model:current-page="currentPage"
            :page-size="pageSize"
            layout="prev, pager, next"
            :total="total"
            @current-change="handleCurrentChange"
          />
        </div>
      </section>
    </main>

    <!-- 分享对话框 -->
    <ShareDialog
      v-model:visible="shareDialogVisible"
      :share-url="shareUrl"
      :file-name="shareFileName"
    />

    <!-- 字幕设置对话框 -->
    <SettingsDialog
      v-model:visible="subtitleSettingsVisible"
      @settings-saved="() => ElMessage.success('字幕设置已保存并广播到所有客户端')"
    />
  </div>
</template>

<style lang="scss" scoped>
$bg: #f7faf9;
$surface: #ffffff;
$surface-soft: #f3f7f6;
$text-primary: #10201d;
$text-secondary: #60716d;
$border: #dce7e4;
$primary: #0f766e;
$primary-soft: #e6f5f2;
$accent: #c2410c;
$accent-soft: #fff1e8;
$blue: #2563eb;
$amber: #b45309;

.home-container {
  min-height: 100dvh;
  display: flex;
  flex-direction: column;
  gap: 24px;
  padding: 24px clamp(24px, 5vw, 72px) 32px;
  background: $bg;
  color: $text-primary;
  font-family: -apple-system, BlinkMacSystemFont, 'PingFang SC', 'Microsoft YaHei', sans-serif;
}

.home-container:not(.mobile-layout) {
  min-width: 960px;
}

.home-header,
.main-content {
  width: 100%;
  max-width: 1440px;
  margin: 0 auto;
}

.home-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  flex-wrap: wrap;
}

.logo-wrap {
  display: flex;
  align-items: center;
  gap: 12px;
}

.logo-icon {
  width: 36px;
  height: 36px;
  border-radius: 8px;
  background: $surface;
  border: 1px solid $border;
  padding: 5px;
  flex-shrink: 0;
}

.logo-text {
  display: flex;
  flex-direction: column;
  line-height: 1.2;
}

.logo-title {
  font-size: 17px;
  font-weight: 700;
  color: $text-primary;
}

.logo-sub {
  margin-top: 3px;
  font-size: 12px;
  color: $text-secondary;
}

.header-actions {
  display: flex;
  align-items: center;
  justify-content: flex-end;
}

.settings-btn,
.action-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border: 1px solid $border;
  background: $surface;
  color: $text-primary;
  cursor: pointer;
  transition: background-color 0.18s ease, border-color 0.18s ease, color 0.18s ease, box-shadow 0.18s ease;

  &:focus-visible {
    outline: 3px solid rgba($primary, 0.18);
    outline-offset: 2px;
  }
}

.settings-btn {
  min-height: 40px;
  gap: 7px;
  padding: 0 14px;
  border-radius: 8px;
  font-size: 14px;
  font-weight: 600;

  &:hover {
    border-color: #cbd5e1;
    background: $surface-soft;
  }
}

.main-content {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 24px;
  min-height: 0;
}

.workspace-hero {
  display: grid;
  grid-template-columns: minmax(320px, 0.62fr) minmax(560px, 1fr);
  gap: 24px;
  align-items: stretch;
}

.hero-copy {
  display: flex;
  flex-direction: column;
  justify-content: center;
  padding: 8px 0;

  h1 {
    margin: 0;
    max-width: 520px;
    font-size: 40px;
    line-height: 1.15;
    font-weight: 800;
    letter-spacing: 0;
    color: $text-primary;
  }

  p:last-child {
    max-width: 520px;
    margin: 16px 0 0;
    color: $text-secondary;
    font-size: 16px;
    line-height: 1.7;
  }
}

.eyebrow {
  margin: 0 0 12px;
  color: $primary;
  font-size: 13px;
  font-weight: 700;
}

.workflow-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 14px;
}

.workflow-card {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  min-height: 188px;
  padding: 20px;
  border: 1px solid $border;
  border-radius: 8px;
  background: $surface;
  color: $text-primary;
  text-align: left;
  cursor: pointer;
  transition: border-color 0.18s ease, background-color 0.18s ease, transform 0.18s ease;

  &:hover {
    transform: translateY(-2px);
    border-color: rgba($primary, 0.42);
    background: #fbfdfc;
  }

  &:focus-visible {
    outline: 3px solid rgba($primary, 0.18);
    outline-offset: 2px;
  }
}

.workflow-icon {
  width: 44px;
  height: 44px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 8px;
  font-size: 22px;
  background: $primary-soft;
  color: $primary;
}

.upload-card .workflow-icon {
  background: $accent-soft;
  color: $accent;
}

.workflow-content {
  display: flex;
  flex: 1;
  flex-direction: column;
  margin-top: 18px;
}

.workflow-title {
  font-size: 22px;
  line-height: 1.2;
  font-weight: 800;
}

.workflow-desc {
  margin-top: 10px;
  color: $text-secondary;
  font-size: 14px;
  line-height: 1.65;
}

.workflow-meta {
  margin-top: auto;
  padding-top: 18px;
  color: $primary;
  font-size: 13px;
  font-weight: 700;
}

.upload-card .workflow-meta {
  color: $accent;
}

.history-panel {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 0;
}

.list-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 14px;
}

.title-block {
  display: flex;
  align-items: baseline;
  gap: 12px;
  min-width: 0;
}

.section-title {
  margin: 0;
  font-size: 22px;
  line-height: 1.25;
  font-weight: 800;
  color: $text-primary;
  letter-spacing: 0;
}

.record-count {
  font-size: 13px;
  color: $text-secondary;
  white-space: nowrap;
}

.search-wrap {
  width: min(360px, 100%);
}

.search-input {
  width: 100%;

  :deep(.el-input__wrapper) {
    min-height: 40px;
    border-radius: 8px;
    background: $surface;
    box-shadow: none;
    border: 1px solid $border;
    padding: 0 12px;
    transition: border-color 0.18s ease, box-shadow 0.18s ease;

    &:hover,
    &.is-focus {
      border-color: rgba($primary, 0.7);
      box-shadow: 0 0 0 3px rgba($primary, 0.1);
    }
  }
}

.list-container {
  flex: 1;
  min-height: clamp(260px, 34vh, 520px);
  display: flex;
  flex-direction: column;
  gap: 10px;

  &::-webkit-scrollbar {
    width: 6px;
  }

  &::-webkit-scrollbar-track {
    background: transparent;
  }

  &::-webkit-scrollbar-thumb {
    background: #cbd5e1;
    border-radius: 999px;
  }
}

.empty-state {
  flex: 1;
  min-height: 260px;
  display: flex;
  flex-direction: column;
  justify-content: center;
  border: 1px dashed #bfd0cc;
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.72);
  padding: 20px;
  color: $text-secondary;
}

.empty-title {
  margin-bottom: 8px;
  font-size: 18px;
  font-weight: 700;
  color: $text-primary;
}

.empty-sub {
  font-size: 14px;
  color: $text-secondary;
}

.meeting-card {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  align-items: center;
  gap: 16px;
  min-height: 88px;
  padding: 16px;
  background: $surface;
  border: 1px solid $border;
  border-radius: 8px;
  box-shadow: none;
  cursor: pointer;
  transition: border-color 0.18s ease, background-color 0.18s ease;

  &:hover {
    border-color: rgba($primary, 0.4);
    background: #fbfdfc;
  }

  &:focus-visible {
    outline: 3px solid rgba($primary, 0.22);
    outline-offset: 2px;
  }
}

.card-info {
  min-width: 0;
}

.card-title {
  max-width: 100%;
  overflow: hidden;
  color: $text-primary;
  font-size: 16px;
  font-weight: 700;
  line-height: 1.4;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.card-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 8px 12px;
  margin-top: 6px;
  color: $text-secondary;
  font-size: 13px;
  line-height: 1.4;
}

.card-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 10px;
}

.badge {
  display: inline-flex;
  align-items: center;
  min-height: 22px;
  padding: 0 8px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 600;

  &.badge-audio {
    background: rgba($primary, 0.1);
    color: $primary;
  }

  &.badge-upload {
    background: rgba($accent, 0.1);
    color: $accent;
  }

  &.badge-trans {
    background: rgba($blue, 0.1);
    color: $blue;
  }

  &.badge-minutes {
    background: rgba($amber, 0.12);
    color: $amber;
  }
}

.card-actions {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
}

.action-btn {
  width: 40px;
  height: 40px;
  border-radius: 8px;
  font-size: 16px;
  color: $text-secondary;

  &:hover {
    background: $surface-soft;
  }

  &.more-btn:hover {
    border-color: rgba($primary, 0.35);
    color: $primary;
  }
}

.pagination-wrap {
  display: flex;
  justify-content: flex-end;
  padding-top: 16px;
  flex-shrink: 0;

  :deep(.el-pagination) {
    .el-pager li,
    .btn-prev,
    .btn-next {
      border-radius: 8px;
    }
  }
}

.home-container.mobile-layout {
  gap: 22px;
  padding: 16px;
  
  .main-content {
    gap: 18px;
  }

  .home-header {
    align-items: flex-start;
  }

  .workspace-hero {
    grid-template-columns: 1fr;
    gap: 18px;
  }

  .hero-copy h1 {
    font-size: 30px;
  }

  .workflow-grid {
    grid-template-columns: 1fr;
  }

  .workflow-card {
    min-height: 0;
  }

  .list-container,
  .empty-state {
    min-height: 180px;
  }

  .list-toolbar {
    align-items: flex-start;
    flex-direction: column;
  }

  .title-block {
    width: 100%;
    justify-content: space-between;
  }

  .search-wrap {
    width: 100%;
  }
}

.home-container.mobile-layout {
  .meeting-card {
    grid-template-columns: 1fr;
    align-items: start;
  }

  .card-actions {
    width: 100%;
    justify-content: flex-start;
  }

  .card-meta {
    flex-direction: column;
  }
}

@media (prefers-reduced-motion: reduce) {
  .settings-btn,
  .workflow-card,
  .action-btn,
  .search-input :deep(.el-input__wrapper),
  .meeting-card {
    transition: none;
  }
}
</style>
