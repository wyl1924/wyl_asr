<script setup lang="ts">
import { ref, onMounted, computed, type Component } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import {
  ArrowLeft,
  CircleCheck,
  Clock,
  DataAnalysis,
  Document,
  Download,
  EditPen,
  Files,
  Microphone,
  Tickets,
  User,
  VideoPlay,
  VideoPause
} from '@element-plus/icons-vue'
import {
  meetingApi,
  type MeetingMinutesVersion,
  type UploadedMeetingTranscription,
  type UploadedMeetingTranscriptionSegment
} from '../api/meeting'
import { generateSummary, type BackendSummaryTask } from '../utils/summary'
import {
  SUMMARY_TEMPLATE_OPTIONS,
  buildSummaryOptionsFromLocalStorage,
  getSummaryTemplateIdFromLocalStorage,
  setSummaryTemplateIdToLocalStorage,
  stripTranslationsForSummary
} from '../utils/summaryRequest'
import { marked } from 'marked'
import { SERVER_CONFIG } from '../config/api'

const route = useRoute()
const router = useRouter()

interface MeetingDetail {
  id: number
  title: string
  start_time: string
  end_time?: string
  duration: string
  audioFiles: any[]
  transcriptionContent: string
  meetingMinutes: string
  recognitionMode?: string
  transcription_source?: 'realtime' | 'upload' | string
  uploadTaskId?: string
  emotionAnalysis?: string
  documents?: MeetingDocument[]
}

interface MeetingDocument {
  id?: number
  meeting_id?: number
  filename: string
  title?: string
  type: string
  file_path: string
  file_size?: number
  created_time?: string
  updated_time?: string
  download_url?: string
}

type ArtifactKind = 'media' | 'transcription' | 'minutes' | 'emotion' | 'document'
type ArtifactStatus = 'ready' | 'missing'
type DownloadType = 'audio' | 'transcription' | 'minutes' | 'emotion'

interface MeetingArtifact {
  id: string
  kind: ArtifactKind
  title: string
  subtitle: string
  meta: string
  status: ArtifactStatus
  icon: Component
  document?: MeetingDocument
  downloadType?: DownloadType
}

type SpeakerReviewTone = 'reviewed' | 'pending' | 'muted'

const meetingDetail = ref<MeetingDetail | null>(null)
const loading = ref(false)
const audioRef = ref<HTMLAudioElement | null>(null)
const isPlaying = ref(false)
const currentTime = ref(0)
const duration = ref(0)
const uploadedTranscription = ref<UploadedMeetingTranscription | null>(null)

const videoExtensions = new Set(['mp4', 'mov', 'mkv', 'avi', 'wmv', 'm4v', 'webm'])
const mediaExtensions = new Set([
  'wav', 'mp3', 'flac', 'm4a', 'aac', 'ogg', 'opus', 'wma', 'amr',
  ...videoExtensions
])

const getDocumentExtension = (doc: MeetingDocument) => {
  const name = doc.filename || doc.file_path || ''
  const ext = name.split('.').pop()?.toLowerCase()
  return ext || ''
}

const isMediaDocument = (doc: MeetingDocument) => {
  return ['audio', 'video', 'media'].includes(doc.type) || mediaExtensions.has(getDocumentExtension(doc))
}

const mediaDocument = computed(() => {
  return meetingDetail.value?.documents?.find(isMediaDocument) || null
})

const isVideoMedia = computed(() => {
  return mediaDocument.value ? videoExtensions.has(getDocumentExtension(mediaDocument.value)) : false
})

const transcriptionDocument = computed(() => {
  return meetingDetail.value?.documents?.find(doc => doc.type === 'transcription') || null
})

const isUploadedTranscription = computed(() => {
  const source = meetingDetail.value?.transcription_source || meetingDetail.value?.recognitionMode
  return source === 'upload' || Boolean(uploadedTranscription.value?.segments?.length)
})

const transcriptionSourceLabel = computed(() => {
  return isUploadedTranscription.value ? '上传转写' : '实时转写'
})

const uploadedTranscriptionSegmentCount = computed(() => {
  return uploadedTranscription.value?.segments?.length || 0
})

const minutesDocument = computed(() => {
  return meetingDetail.value?.documents?.find(doc => doc.type === 'minutes') || null
})

const emotionDocument = computed(() => {
  return meetingDetail.value?.documents?.find(doc => doc.type === 'emotion') || null
})

const otherDocuments = computed(() => {
  return meetingDetail.value?.documents?.filter(doc => (
    !isMediaDocument(doc) && doc.type !== 'transcription' && doc.type !== 'minutes' && doc.type !== 'emotion'
  )) || []
})

const selectedArtifactId = ref('')
const minutesVersions = ref<MeetingMinutesVersion[]>([])
const selectedMinutesVersionId = ref<number | null>(null)
const revisionInstruction = ref('')
const revisionLoading = ref(false)
const minutesGenerating = ref(false)
const minutesGenerationProgress = ref(0)
const minutesGenerationStage = ref('')
const selectedSummaryTemplate = ref(getSummaryTemplateIdFromLocalStorage())
const emotionGenerating = ref(false)
const speakerCorrectionDrawerVisible = ref(false)
const speakerCorrectionRows = ref<Array<{
  sourceName: string
  draftName: string
  count: number
}>>([])
const speakerCorrectionSaving = ref(false)

const formatFileSize = (size?: number) => {
  if (!size || size <= 0) return '文件大小未知'
  if (size < 1024) return `${size} B`
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`
  if (size < 1024 * 1024 * 1024) return `${(size / 1024 / 1024).toFixed(1)} MB`
  return `${(size / 1024 / 1024 / 1024).toFixed(1)} GB`
}

const formatTextMeta = (text?: string) => {
  const content = (text || '').trim()
  if (!content) return '暂无内容'
  const lines = content.split(/\n+/).filter(line => line.trim()).length
  return `${content.length} 字 / ${lines} 段`
}

const getDocumentTime = (doc?: MeetingDocument | null) => {
  return doc?.updated_time || doc?.created_time || ''
}

const displayMinutesVersions = computed<MeetingMinutesVersion[]>(() => {
  if (minutesVersions.value.length > 0) return minutesVersions.value
  const summary = meetingDetail.value?.meetingMinutes?.trim()
  if (!summary) return []
  return [{
    id: 0,
    meeting_id: meetingDetail.value?.id || 0,
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

const currentMinutesText = computed(() => {
  return selectedMinutesVersion.value?.summary || meetingDetail.value?.meetingMinutes || ''
})

const formatMinutesVersionLabel = (version: MeetingMinutesVersion) => {
  return `v${version.version}${version.is_current ? ' 当前' : ''}`
}

const isGenericSpeakerName = (name: string) => {
  const normalized = name.trim().replace(/\s+/g, '')
  return /^(说话人|发言人|讲话人|speaker|spk|role|角色)[_-]?\d+$/i.test(normalized)
    || /^SPEAKER[_-]?\d+$/i.test(normalized)
}

const transcriptionSpeakerAnalysis = computed(() => {
  const content = meetingDetail.value?.transcriptionContent || ''
  const rows = buildSpeakerCorrectionRows(content)
  const genericCount = rows.filter(row => isGenericSpeakerName(row.sourceName)).length
  const segmentCount = rows.reduce((total, row) => total + row.count, 0)

  return {
    speakerCount: rows.length,
    genericCount,
    segmentCount,
    hasSpeakers: rows.length > 0
  }
})

const transcriptionSpeakerReviewTone = computed<SpeakerReviewTone>(() => {
  if (!transcriptionSpeakerAnalysis.value.hasSpeakers) return 'muted'
  return transcriptionSpeakerAnalysis.value.genericCount > 0 ? 'pending' : 'reviewed'
})

const transcriptionSpeakerReviewLabel = computed(() => {
  const analysis = transcriptionSpeakerAnalysis.value
  if (!meetingDetail.value?.transcriptionContent?.trim()) return '无转录'
  if (!analysis.hasSpeakers) return '未分段'
  if (analysis.genericCount > 0) return `未校正 ${analysis.genericCount}/${analysis.speakerCount}`
  return '已校正'
})

const transcriptionSpeakerMeta = computed(() => {
  const analysis = transcriptionSpeakerAnalysis.value
  if (!analysis.hasSpeakers) return '未识别说话人标签'
  return `${analysis.speakerCount} 位说话人 / ${analysis.segmentCount} 段`
})

const artifactItems = computed<MeetingArtifact[]>(() => {
  if (!meetingDetail.value) return []

  const mediaDoc = mediaDocument.value
  const transcriptionDoc = transcriptionDocument.value
  const minutesDoc = minutesDocument.value
  const emotionDoc = emotionDocument.value
  const items: MeetingArtifact[] = [
    {
      id: 'media',
      kind: 'media',
      title: isVideoMedia.value ? '音视频源文件' : '音频源文件',
      subtitle: mediaDoc?.filename || '未关联音视频',
      meta: mediaDoc ? formatFileSize(mediaDoc.file_size) : '保存会议时会关联源文件',
      status: mediaDoc ? 'ready' : 'missing',
      icon: isVideoMedia.value ? VideoPlay : Microphone,
      document: mediaDoc || undefined,
      downloadType: mediaDoc ? 'audio' : undefined
    },
    {
      id: 'transcription',
      kind: 'transcription',
      title: `${transcriptionSourceLabel.value}稿`,
      subtitle: isUploadedTranscription.value
        ? (uploadedTranscription.value?.file_names?.join('、') || transcriptionDoc?.filename || '上传识别结果')
        : (transcriptionDoc?.filename || '暂无转录文档'),
      meta: meetingDetail.value.transcriptionContent
        ? `${formatTextMeta(meetingDetail.value.transcriptionContent)} · ${transcriptionSpeakerMeta.value}${isUploadedTranscription.value ? ` · 上传片段 ${uploadedTranscriptionSegmentCount.value} 段` : ''}`
        : formatTextMeta(meetingDetail.value.transcriptionContent),
      status: meetingDetail.value.transcriptionContent ? 'ready' : 'missing',
      icon: Document,
      document: transcriptionDoc || undefined,
      downloadType: transcriptionDoc ? 'transcription' : undefined
    },
    {
      id: 'minutes',
      kind: 'minutes',
      title: '会议纪要',
      subtitle: selectedMinutesVersion.value
        ? `${formatMinutesVersionLabel(selectedMinutesVersion.value)} · ${minutesDoc?.filename || '会议纪要'}`
        : minutesDoc?.filename || '暂无纪要文档',
      meta: formatTextMeta(currentMinutesText.value),
      status: currentMinutesText.value ? 'ready' : 'missing',
      icon: Tickets,
      document: minutesDoc || undefined,
      downloadType: minutesDoc ? 'minutes' : undefined
    },
    {
      id: 'emotion',
      kind: 'emotion',
      title: '情绪分析',
      subtitle: emotionDoc?.filename || '基于转录稿生成逐人情绪分析',
      meta: meetingDetail.value.emotionAnalysis
        ? formatTextMeta(meetingDetail.value.emotionAnalysis)
        : meetingDetail.value.transcriptionContent
          ? '可按每位说话人生成'
          : '需要先有转录稿',
      status: meetingDetail.value.emotionAnalysis ? 'ready' : 'missing',
      icon: DataAnalysis,
      document: emotionDoc || undefined,
      downloadType: emotionDoc ? 'emotion' : undefined
    }
  ]

  otherDocuments.value.forEach((doc, index) => {
    items.push({
      id: `document-${doc.id || index}`,
      kind: 'document',
      title: doc.title || doc.type || '会议文档',
      subtitle: doc.filename,
      meta: formatFileSize(doc.file_size),
      status: 'ready',
      icon: Files,
      document: doc
    })
  })

  return items
})

const selectedArtifact = computed(() => {
  return artifactItems.value.find(item => item.id === selectedArtifactId.value)
    || artifactItems.value.find(item => item.status === 'ready')
    || artifactItems.value[0]
    || null
})

const readyArtifactCount = computed(() => {
  return artifactItems.value.filter(item => item.status === 'ready').length
})

const selectedArtifactHtml = computed(() => {
  if (!selectedArtifact.value || selectedArtifact.value.status !== 'ready') return ''
  if (selectedArtifact.value.kind === 'transcription') return transcriptionHtml.value
  if (selectedArtifact.value.kind === 'minutes') return minutesHtml.value
  if (selectedArtifact.value.kind === 'emotion') return emotionHtml.value
  return ''
})

const selectedDocumentTime = computed(() => {
  if (selectedArtifact.value?.kind === 'minutes' && selectedMinutesVersion.value?.created_at) {
    return selectedMinutesVersion.value.created_at
  }
  return getDocumentTime(selectedArtifact.value?.document)
})

const hasTextPreview = computed(() => {
  return Boolean(selectedArtifactHtml.value)
})

const canDownloadSelectedArtifact = computed(() => {
  if (!selectedArtifact.value || selectedArtifact.value.status !== 'ready') return false
  if (selectedArtifact.value.downloadType) return true
  return selectedArtifact.value.kind === 'minutes'
    && Boolean(selectedMinutesVersion.value?.id && selectedMinutesVersion.value.id > 0)
})

const canCorrectTranscription = computed(() => {
  return Boolean(
    selectedArtifact.value?.kind === 'transcription' &&
    !isUploadedTranscription.value &&
    transcriptionDocument.value?.id &&
    meetingDetail.value?.transcriptionContent?.trim()
  )
})

const canGenerateEmotionAnalysis = computed(() => {
  return Boolean(
    selectedArtifact.value?.kind === 'emotion' &&
    meetingDetail.value?.transcriptionContent?.trim()
  )
})

const canGenerateEmotionFromDetail = computed(() => {
  return Boolean(meetingDetail.value?.transcriptionContent?.trim())
})

const canGenerateMinutes = computed(() => {
  return Boolean(
    selectedArtifact.value?.kind === 'minutes' &&
    meetingDetail.value?.transcriptionContent?.trim()
  )
})

const isArtifactGeneratable = (artifact?: MeetingArtifact | null) => {
  if (!artifact || artifact.status !== 'missing') return false
  return ['minutes', 'emotion'].includes(artifact.kind)
    && Boolean(meetingDetail.value?.transcriptionContent?.trim())
}

const getArtifactStatusLabel = (artifact?: MeetingArtifact | null) => {
  if (!artifact) return ''
  if (artifact.status === 'ready') return '已就绪'
  return isArtifactGeneratable(artifact) ? '可生成' : '待生成'
}

const speakerCorrectionChangedCount = computed(() => {
  return speakerCorrectionRows.value.filter(row => {
    const nextName = row.draftName.trim()
    return nextName && nextName !== row.sourceName
  }).length
})

const speakerCorrectionSegmentCount = computed(() => {
  return speakerCorrectionRows.value.reduce((total, row) => total + row.count, 0)
})

const selectArtifact = (artifact: MeetingArtifact) => {
  selectedArtifactId.value = artifact.id
}

const selectPreferredArtifact = () => {
  const preferred = artifactItems.value.find(item => item.kind === 'minutes' && item.status === 'ready')
    || artifactItems.value.find(item => item.status === 'ready')
    || artifactItems.value[0]
  selectedArtifactId.value = preferred?.id || ''
}

const selectPreferredMinutesVersion = () => {
  const preferred = displayMinutesVersions.value.find(version => version.is_current)
    || displayMinutesVersions.value[0]
  selectedMinutesVersionId.value = preferred?.id ?? null
}

const buildDocumentUrl = (doc: MeetingDocument, inline = false) => {
  const params = new URLSearchParams()
  if (doc.id) {
    params.append('document_id', String(doc.id))
  } else {
    params.append('file_path', doc.file_path)
    params.append('file_name', doc.filename)
  }
  if (inline) {
    params.append('inline', '1')
  }
  return `${SERVER_CONFIG.DB_BASE_URL}/api/meetings/documents/download?${params.toString()}`
}

const fetchDocumentText = async (doc: MeetingDocument) => {
  const response = await fetch(buildDocumentUrl(doc, true))
  if (!response.ok) {
    throw new Error(`HTTP ${response.status}`)
  }
  return await response.text()
}

const buildUploadedTranscriptionText = (segments: UploadedMeetingTranscriptionSegment[]) => {
  return segments
    .filter(segment => segment.text?.trim())
    .map((segment, index) => {
      const speaker = segment.speaker?.trim()
      const timeRange = segment.startTime && segment.endTime
        ? `${segment.startTime} - ${segment.endTime}`
        : ''
      const headerParts: string[] = []
      if (speaker) {
        headerParts.push(`**${speaker}**`)
      } else if (segments.length > 1) {
        headerParts.push(`**说话人${index + 1}**`)
      }
      if (timeRange) {
        headerParts.push(`[${timeRange}]`)
      }
      const translation = segment.translation?.trim()
      const body = translation
        ? `${segment.text.trim()}\n\n翻译：${translation}`
        : segment.text.trim()
      return headerParts.length ? `${headerParts.join(' ')}\n${body}` : body
    })
    .join('\n\n')
}

const fetchUploadedTranscriptionForMeeting = async (meeting: any) => {
  const source = meeting.transcription_source || meeting.recognitionMode
  if (source !== 'upload') {
    uploadedTranscription.value = null
    return
  }

  try {
    const response = await meetingApi.getMeetingUploadedTranscription(meeting.id)
    if (!response.success || !response.data) {
      throw new Error(response.error || '上传转写回显加载失败')
    }

    uploadedTranscription.value = response.data
    if (response.data.segments.length > 0) {
      meeting.transcription_source = 'upload'
      meeting.recognitionMode = 'upload'
      meeting.uploadTaskId = response.data.task_id || undefined
      meeting.transcriptionContent = response.data.text || buildUploadedTranscriptionText(response.data.segments)
    }
  } catch (error) {
    console.warn('加载上传转写回显失败，使用转录文档内容:', error)
  }
}

const fetchMinutesVersions = async (meetingId: number) => {
  try {
    const response = await meetingApi.getMeetingMinutesVersions(meetingId)
    if (response.success && response.data) {
      minutesVersions.value = response.data.versions || []
    } else {
      minutesVersions.value = []
    }
  } catch (error) {
    console.warn('获取会议纪要版本失败:', error)
    minutesVersions.value = []
  } finally {
    selectPreferredMinutesVersion()
  }
}

// 获取会议详情
const fetchMeetingDetail = async () => {
  const meetingId = route.query.id
  if (!meetingId) {
    ElMessage.error('会议ID不能为空')
    router.back()
    return
  }

  loading.value = true
  try {
    uploadedTranscription.value = null
    const response = await meetingApi.getMeeting(Number(meetingId))
    if (response.success && response.data) {
      const meeting = response.data as any
      
      // 获取会议的文档列表
       try {
         const docsResponse = await meetingApi.getMeetingDocuments({
           meeting_id: meeting.id
         })
        
        if (docsResponse.success && docsResponse.data) {
          meeting.documents = docsResponse.data.documents
          
          // 从文档中提取转录内容、会议纪要和情绪分析
          const transcriptionDoc = meeting.documents.find((doc: any) => doc.type === 'transcription')
          const minutesDoc = meeting.documents.find((doc: any) => doc.type === 'minutes')
          const emotionDoc = meeting.documents.find((doc: any) => doc.type === 'emotion')
          
          if (transcriptionDoc) {
            // 通过API获取转录文档内容
            try {
              meeting.transcriptionContent = await fetchDocumentText(transcriptionDoc)
            } catch (error) {
              console.error('加载转录内容失败:', error)
              meeting.transcriptionContent = '转录内容加载失败'
            }
          }
          
          if (minutesDoc) {
            // 通过API获取会议纪要文档内容
            try {
              meeting.meetingMinutes = await fetchDocumentText(minutesDoc)
            } catch (error) {
              console.error('加载会议纪要失败:', error)
              meeting.meetingMinutes = '会议纪要加载失败'
            }
          }

          if (emotionDoc) {
            try {
              meeting.emotionAnalysis = await fetchDocumentText(emotionDoc)
            } catch (error) {
              console.error('加载情绪分析失败:', error)
              meeting.emotionAnalysis = '情绪分析加载失败'
            }
          }
        }
      } catch (docError) {
        console.warn('获取会议文档失败:', docError)
        meeting.documents = []
      }

      await fetchUploadedTranscriptionForMeeting(meeting)
      
      meetingDetail.value = meeting
      await fetchMinutesVersions(meeting.id)
      selectPreferredArtifact()
    } else {
      ElMessage.error('获取会议详情失败')
      router.back()
    }
  } catch (error) {
    console.error('获取会议详情失败:', error)
    ElMessage.error('获取会议详情失败')
    router.back()
  } finally {
    loading.value = false
  }
}

const ignoredTranscriptLabels = new Set([
  '会议时间',
  '会议描述',
  '参与人员',
  '会议名称',
  '转录内容',
  '会议总结',
  '详细纪要',
  '关键要点',
  '行动项',
  '决策事项',
  '时间',
  '地点'
])

const parseTranscriptSpeakerLine = (line: string) => {
  const match = line.match(/^(\s*(?:[-*]\s*)?(?:\*\*)?)([^:\n：]{1,48})(\*\*)?([:：])/)
  if (!match) return null

  const rawName = match[2]
  const name = rawName.trim()
  if (!name || ignoredTranscriptLabels.has(name) || name.startsWith('#')) return null

  const nameOffset = rawName.indexOf(name)
  const start = match[1].length + (nameOffset >= 0 ? nameOffset : 0)
  return {
    name,
    start,
    end: start + name.length
  }
}

const buildSpeakerCorrectionRows = (content: string) => {
  const counts = new Map<string, number>()
  content.split(/\r?\n/).forEach(line => {
    const speaker = parseTranscriptSpeakerLine(line)
    if (speaker) {
      counts.set(speaker.name, (counts.get(speaker.name) || 0) + 1)
    }
  })

  return Array.from(counts.entries())
    .sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0], 'zh-CN'))
    .map(([sourceName, count]) => ({
      sourceName,
      draftName: sourceName,
      count
    }))
}

const openSpeakerCorrectionDrawer = () => {
  const content = meetingDetail.value?.transcriptionContent || ''
  speakerCorrectionRows.value = buildSpeakerCorrectionRows(content)
  selectedArtifactId.value = 'transcription'
  speakerCorrectionDrawerVisible.value = true
}

const setSpeakerMergeTarget = (
  row: { sourceName: string; draftName: string; count: number },
  targetName: string
) => {
  const target = speakerCorrectionRows.value.find(item => item.sourceName === targetName)
  if (!target) return
  row.draftName = target.draftName.trim() || target.sourceName
}

const applySpeakerCorrectionMap = (content: string, nameMap: Map<string, string>) => {
  return content.split('\n').map(line => {
    const speaker = parseTranscriptSpeakerLine(line)
    if (!speaker) return line
    const nextName = nameMap.get(speaker.name)
    if (!nextName || nextName === speaker.name) return line
    return `${line.slice(0, speaker.start)}${nextName}${line.slice(speaker.end)}`
  }).join('\n')
}

const updateLocalTranscriptionDocument = (updatedDocument: MeetingDocument) => {
  const documents = meetingDetail.value?.documents
  if (!documents) return
  const index = documents.findIndex(doc => doc.id === updatedDocument.id)
  if (index >= 0) {
    documents[index] = {
      ...documents[index],
      ...updatedDocument
    }
  }
}

const upsertLocalDocument = (updatedDocument: MeetingDocument) => {
  const meeting = meetingDetail.value
  if (!meeting) return
  if (!meeting.documents) {
    meeting.documents = [updatedDocument]
    return
  }
  const index = meeting.documents.findIndex(doc => doc.id === updatedDocument.id)
  if (index >= 0) {
    meeting.documents[index] = {
      ...meeting.documents[index],
      ...updatedDocument
    }
    return
  }
  meeting.documents.unshift(updatedDocument)
}

const saveSpeakerCorrections = async () => {
  const meeting = meetingDetail.value
  const document = transcriptionDocument.value
  if (!meeting || !document?.id) {
    ElMessage.warning('没有可保存的转录文档')
    return
  }

  const nameMap = new Map<string, string>()
  speakerCorrectionRows.value.forEach(row => {
    const nextName = row.draftName.trim()
    if (nextName && nextName !== row.sourceName) {
      nameMap.set(row.sourceName, nextName)
    }
  })
  if (nameMap.size === 0) {
    ElMessage.warning('没有需要保存的说话人修改')
    return
  }

  const nextContent = applySpeakerCorrectionMap(meeting.transcriptionContent || '', nameMap)
  if (nextContent === meeting.transcriptionContent) {
    ElMessage.warning('没有匹配到可替换的说话人标签')
    return
  }

  speakerCorrectionSaving.value = true
  try {
    const response = await meetingApi.updateMeetingDocumentText(meeting.id, document.id, nextContent)
    if (!response.success || !response.data) {
      throw new Error(response.error || '保存说话人校正失败')
    }

    meeting.transcriptionContent = response.data.content
    updateLocalTranscriptionDocument(response.data.document)
    speakerCorrectionRows.value = buildSpeakerCorrectionRows(response.data.content)
    ElMessage.success('说话人校正已保存')
  } catch (error) {
    console.error('保存说话人校正失败:', error)
    ElMessage.error(error instanceof Error ? error.message : '保存说话人校正失败')
  } finally {
    speakerCorrectionSaving.value = false
  }
}

// 返回上一页
const goBack = () => {
  router.back()
}

type TextDownloadFormat = 'docx' | 'pdf'

// 下载文件
const downloadFile = async (
  type: DownloadType,
  format?: TextDownloadFormat
) => {
  if (!meetingDetail.value || !meetingDetail.value.documents) return

  try {
    // 查找对应类型的文档
    let targetDoc: MeetingDocument | undefined
    const documents = meetingDetail.value.documents
    
    switch (type) {
      case 'audio':
        targetDoc = documents.find(isMediaDocument)
        if (!targetDoc) {
          ElMessage.warning('该会议没有音视频文件')
          return
        }
        break
      case 'transcription':
        targetDoc = documents.find(doc => doc.type === 'transcription')
        if (!targetDoc) {
          ElMessage.warning('该会议没有转录内容')
          return
        }
        break
      case 'minutes':
        targetDoc = documents.find(doc => doc.type === 'minutes')
        if (!targetDoc) {
          ElMessage.warning('该会议没有会议纪要')
          return
        }
        break
      case 'emotion':
        targetDoc = documents.find(doc => doc.type === 'emotion')
        if (!targetDoc) {
          ElMessage.warning('该会议没有情绪分析')
          return
        }
        break
    }
    
    if (!targetDoc) {
      ElMessage.error('未找到对应的文档文件')
      return
    }
    
    // 使用文档下载API
    try {
      const downloadFormat = type === 'audio' ? undefined : (format || 'docx')
      const downloadResponse = await meetingApi.downloadMeetingDocument(
        targetDoc.id ?? targetDoc.file_path,
        targetDoc.filename,
        downloadFormat
      )
      
      if (downloadResponse.success) {
        ElMessage.success('下载成功')
      } else {
        ElMessage.error('下载失败')
      }
    } catch (downloadError) {
      console.error('下载文件失败:', downloadError)
      ElMessage.error('下载失败')
    }
    
  } catch (error) {
    console.error('下载失败:', error)
    ElMessage.error('下载失败')
  }
}

const downloadSelectedArtifact = async (format?: TextDownloadFormat) => {
  if (
    selectedArtifact.value?.kind === 'minutes' &&
    meetingDetail.value &&
    selectedMinutesVersion.value?.id &&
    selectedMinutesVersion.value.id > 0
  ) {
    const response = await meetingApi.downloadMeetingMinutesVersion(
      meetingDetail.value.id,
      selectedMinutesVersion.value.id,
      format || 'docx'
    )
    if (response.success) {
      ElMessage.success('下载成功')
    } else {
      ElMessage.error(response.error || '下载失败')
    }
    return
  }

  const downloadType = selectedArtifact.value?.downloadType
  if (!downloadType) return
  downloadFile(downloadType, format)
}

const handleGenerateEmotionAnalysis = async () => {
  const meeting = meetingDetail.value
  if (!meeting) return

  const transcript = meeting.transcriptionContent?.trim()
  if (!transcript) {
    ElMessage.warning('没有可分析的转录稿')
    return
  }

  emotionGenerating.value = true
  try {
    const response = await meetingApi.generateEmotionAnalysis(meeting.id, transcript)
    if (!response.success || !response.data) {
      throw new Error(response.error || '情绪分析生成失败')
    }

    meeting.emotionAnalysis = response.data.content
    upsertLocalDocument(response.data.document)
    selectedArtifactId.value = 'emotion'
    ElMessage.success('逐人情绪分析已生成')
  } catch (error) {
    console.error('生成情绪分析失败:', error)
    ElMessage.error(error instanceof Error ? error.message : '情绪分析生成失败')
  } finally {
    emotionGenerating.value = false
  }
}

const handleGenerateEmotionFromDetail = async () => {
  selectedArtifactId.value = 'emotion'
  await handleGenerateEmotionAnalysis()
}

const updateMinutesGenerationProgress = (task: BackendSummaryTask) => {
  minutesGenerating.value = task.status === 'queued' || task.status === 'running'
  minutesGenerationProgress.value = task.progress ?? minutesGenerationProgress.value
  minutesGenerationStage.value = task.stage || minutesGenerationStage.value
}

const finishMinutesGenerationProgress = () => {
  minutesGenerating.value = false
  minutesGenerationProgress.value = 0
  minutesGenerationStage.value = ''
}

const handleSummaryTemplateChange = (templateId: string) => {
  selectedSummaryTemplate.value = setSummaryTemplateIdToLocalStorage(templateId)
}

const handleGenerateMinutes = async () => {
  const meeting = meetingDetail.value
  if (!meeting) return

  const transcript = stripTranslationsForSummary(meeting.transcriptionContent || '').trim()
  if (!transcript) {
    ElMessage.warning('没有可生成纪要的转录稿')
    return
  }

  minutesGenerating.value = true
  minutesGenerationProgress.value = 0
  minutesGenerationStage.value = '正在提交会议纪要生成任务...'
  try {
    const options = buildSummaryOptionsFromLocalStorage()
    options.templateId = selectedSummaryTemplate.value
    options.meetingId = meeting.id
    options.onSummaryProgress = updateMinutesGenerationProgress

    const summary = await generateSummary(transcript, options)
    meeting.meetingMinutes = summary
    await fetchMinutesVersions(meeting.id)
    selectedArtifactId.value = 'minutes'
    ElMessage.success('会议纪要已生成')
  } catch (error) {
    console.error('生成会议纪要失败:', error)
    ElMessage.error(error instanceof Error ? error.message : '会议纪要生成失败')
  } finally {
    finishMinutesGenerationProgress()
  }
}

const handleReviseMinutes = async () => {
  const meeting = meetingDetail.value
  if (!meeting) return

  const instruction = revisionInstruction.value.trim()
  if (!instruction) {
    ElMessage.warning('请输入改写要求')
    return
  }

  const baseSummary = currentMinutesText.value.trim()
  if (!baseSummary) {
    ElMessage.warning('没有可改写的会议纪要')
    return
  }

  revisionLoading.value = true
  try {
    const sourceVersionId = selectedMinutesVersion.value?.id && selectedMinutesVersion.value.id > 0
      ? selectedMinutesVersion.value.id
      : undefined
    const response = await meetingApi.reviseMeetingMinutes(meeting.id, {
      instruction,
      base_summary: baseSummary,
      source_version_id: sourceVersionId
    })

    if (!response.success || !response.data) {
      throw new Error(response.error || '会议纪要改写失败')
    }

    meeting.meetingMinutes = response.data.summary
    await fetchMinutesVersions(meeting.id)
    selectedMinutesVersionId.value = response.data.version.id
    selectedArtifactId.value = 'minutes'
    revisionInstruction.value = ''
    ElMessage.success('已生成新版会议纪要')
  } catch (error) {
    console.error('改写会议纪要失败:', error)
    ElMessage.error(error instanceof Error ? error.message : '会议纪要改写失败')
  } finally {
    revisionLoading.value = false
  }
}

// 音频播放控制
const togglePlay = () => {
  if (!audioRef.value) return
  
  if (isPlaying.value) {
    audioRef.value.pause()
  } else {
    audioRef.value.play()
  }
}

const onAudioPlay = () => {
  isPlaying.value = true
}

const onAudioPause = () => {
  isPlaying.value = false
}

const onAudioTimeUpdate = () => {
  if (audioRef.value) {
    currentTime.value = audioRef.value.currentTime
  }
}

const onAudioLoadedMetadata = () => {
  if (audioRef.value) {
    duration.value = audioRef.value.duration
  }
}

const formatTime = (time: number) => {
  const minutes = Math.floor(time / 60)
  const seconds = Math.floor(time % 60)
  return `${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}`
}

// 将Markdown转换为HTML
const transcriptionHtml = computed(() => {
  if (!meetingDetail.value?.transcriptionContent) return ''
  return marked(meetingDetail.value.transcriptionContent) as string
})

const minutesHtml = computed(() => {
  if (!currentMinutesText.value) return ''
  return marked(currentMinutesText.value) as string
})

const emotionHtml = computed(() => {
  if (!meetingDetail.value?.emotionAnalysis) return ''
  return marked(meetingDetail.value.emotionAnalysis) as string
})

// 获取音频URL
const getMediaUrl = () => {
  return mediaDocument.value ? buildDocumentUrl(mediaDocument.value, true) : ''
}

onMounted(() => {
  fetchMeetingDetail()
})
</script>

<template>
  <div class="meeting-detail-container" v-loading="loading">
    <div class="header">
      <el-button @click="goBack" :icon="ArrowLeft">返回</el-button>
      <h2 class="title">{{ meetingDetail?.title || '会议详情' }}</h2>
    </div>

    <div v-if="meetingDetail" class="content">
      <div class="detail-layout">
        <main class="detail-main">
          <el-card class="info-card">
            <template #header>
              <div class="card-header">
                <span>会议信息</span>
              </div>
            </template>
            <div class="info-grid">
              <div class="info-item">
                <label>会议名称：</label>
                <span>{{ meetingDetail.title }}</span>
              </div>
              <div class="info-item">
                <label>开始时间：</label>
                <span>{{ meetingDetail.start_time }}</span>
              </div>
              <div class="info-item">
                <label>结束时间：</label>
                <span>{{ meetingDetail.end_time || '进行中' }}</span>
              </div>
              <div class="info-item">
                <label>会议时长：</label>
                <span>{{ meetingDetail.duration }}</span>
              </div>
            </div>
          </el-card>

          <el-card v-if="mediaDocument" class="media-card">
            <template #header>
              <div class="card-header">
                <span>{{ isVideoMedia ? '音视频文件' : '音频文件' }}</span>
                <el-button size="small" @click="downloadFile('audio')" :icon="Download">下载音视频</el-button>
              </div>
            </template>
            <video
              v-if="isVideoMedia"
              class="video-player"
              :src="getMediaUrl()"
              controls
              preload="metadata"
            ></video>
            <div v-else class="audio-player">
              <audio
                ref="audioRef"
                :src="getMediaUrl()"
                @play="onAudioPlay"
                @pause="onAudioPause"
                @timeupdate="onAudioTimeUpdate"
                @loadedmetadata="onAudioLoadedMetadata"
                preload="metadata"
              ></audio>
              <div class="player-controls">
                <el-button
                  @click="togglePlay"
                  :icon="isPlaying ? VideoPause : VideoPlay"
                  circle
                  type="primary"
                  aria-label="播放或暂停"
                ></el-button>
                <div class="time-info">
                  <span>{{ formatTime(currentTime) }} / {{ formatTime(duration) }}</span>
                </div>
              </div>
              <div class="progress-bar">
                <el-slider
                  v-model="currentTime"
                  :max="duration"
                  :show-tooltip="false"
                  @change="(val: number) => audioRef && (audioRef.currentTime = val)"
                />
              </div>
            </div>
          </el-card>

          <el-card class="artifact-card">
            <template #header>
              <div class="card-header">
                <span>会议产物</span>
                <div class="artifact-card-actions">
                  <el-button
                    v-if="canGenerateEmotionFromDetail"
                    size="small"
                    type="primary"
                    plain
                    :icon="DataAnalysis"
                    :loading="emotionGenerating"
                    @click="handleGenerateEmotionFromDetail"
                  >
                    {{ meetingDetail.emotionAnalysis ? '重新生成情绪分析' : '生成情绪分析' }}
                  </el-button>
                  <el-tag size="small" type="success" effect="plain">{{ readyArtifactCount }}/{{ artifactItems.length }} 已就绪</el-tag>
                </div>
              </div>
            </template>
            <div class="artifact-timeline" role="list" aria-label="会议产物">
              <button
                v-for="artifact in artifactItems"
                :key="artifact.id"
                type="button"
                class="artifact-step"
                :class="{
                  'is-active': selectedArtifact?.id === artifact.id,
                  'is-missing': artifact.status === 'missing',
                  'is-generatable': isArtifactGeneratable(artifact)
                }"
                :aria-pressed="selectedArtifact?.id === artifact.id"
                @click="selectArtifact(artifact)"
              >
                <span class="artifact-icon">
                  <el-icon><component :is="artifact.icon" /></el-icon>
                </span>
                <span class="artifact-body">
                  <span class="artifact-title-row">
                    <span class="artifact-title">{{ artifact.title }}</span>
                    <span class="artifact-status">
                      <el-icon v-if="artifact.status === 'ready'"><CircleCheck /></el-icon>
                      <el-icon v-else><Clock /></el-icon>
                      {{ getArtifactStatusLabel(artifact) }}
                    </span>
                    <span
                      v-if="artifact.kind === 'transcription' && artifact.status === 'ready'"
                      class="artifact-review-status"
                      :class="`is-${transcriptionSpeakerReviewTone}`"
                    >
                      {{ transcriptionSpeakerReviewLabel }}
                    </span>
                  </span>
                  <span class="artifact-subtitle">{{ artifact.subtitle }}</span>
                  <span class="artifact-meta">{{ artifact.meta }}</span>
                </span>
              </button>
            </div>
          </el-card>
        </main>

        <aside class="preview-rail">
          <el-card class="preview-card">
            <template #header>
              <div class="preview-header">
                <div class="preview-heading">
                  <div class="preview-title">{{ selectedArtifact?.title || '产物预览' }}</div>
                  <div class="preview-subtitle">{{ selectedArtifact?.subtitle || '暂无会议产物' }}</div>
                </div>
                <div
                  v-if="canDownloadSelectedArtifact || canCorrectTranscription || canGenerateMinutes || canGenerateEmotionAnalysis"
                  class="preview-actions"
                >
                  <el-select
                    v-if="canGenerateMinutes"
                    v-model="selectedSummaryTemplate"
                    class="preview-template-select"
                    size="small"
                    :disabled="minutesGenerating"
                    @change="handleSummaryTemplateChange"
                  >
                    <el-option
                      v-for="template in SUMMARY_TEMPLATE_OPTIONS"
                      :key="template.id"
                      :label="template.label"
                      :value="template.id"
                    />
                  </el-select>
                  <el-button
                    v-if="canCorrectTranscription"
                    size="small"
                    :icon="User"
                    @click="openSpeakerCorrectionDrawer"
                  >
                    校正说话人
                  </el-button>
                  <el-button
                    v-if="canGenerateMinutes"
                    size="small"
                    type="primary"
                    plain
                    :icon="Tickets"
                    :loading="minutesGenerating"
                    @click="handleGenerateMinutes"
                  >
                    {{ selectedArtifact.status === 'ready' ? '重新生成' : '生成纪要' }}
                  </el-button>
                  <el-button
                    v-if="canGenerateEmotionAnalysis"
                    size="small"
                    type="primary"
                    plain
                    :icon="DataAnalysis"
                    :loading="emotionGenerating"
                    @click="handleGenerateEmotionAnalysis"
                  >
                    {{ selectedArtifact.status === 'ready' ? '重新生成' : '生成分析' }}
                  </el-button>
                  <template v-if="canDownloadSelectedArtifact">
                    <el-button
                      v-if="selectedArtifact.downloadType === 'audio'"
                      size="small"
                      :icon="Download"
                      @click="downloadSelectedArtifact()"
                    >
                      下载
                    </el-button>
                    <el-dropdown
                      v-else
                      @command="(format: TextDownloadFormat) => downloadSelectedArtifact(format)"
                      trigger="click"
                    >
                      <el-button size="small" :icon="Download">下载</el-button>
                      <template #dropdown>
                        <el-dropdown-menu>
                          <el-dropdown-item command="docx">Word</el-dropdown-item>
                          <el-dropdown-item command="pdf">PDF</el-dropdown-item>
                        </el-dropdown-menu>
                      </template>
                    </el-dropdown>
                  </template>
                </div>
              </div>
            </template>

            <div v-if="selectedArtifact" class="preview-content">
              <div class="preview-meta-grid">
                <div class="preview-meta-item">
                  <span>状态</span>
                  <strong>{{ getArtifactStatusLabel(selectedArtifact) }}</strong>
                </div>
                <div class="preview-meta-item">
                  <span>详情</span>
                  <strong>{{ selectedArtifact.meta }}</strong>
                </div>
                <div v-if="selectedDocumentTime" class="preview-meta-item">
                  <span>更新时间</span>
                  <strong>{{ selectedDocumentTime }}</strong>
                </div>
                <div
                  v-if="selectedArtifact.kind === 'transcription' && selectedArtifact.status === 'ready'"
                  class="preview-meta-item"
                >
                  <span>说话人校正</span>
                  <strong>{{ transcriptionSpeakerReviewLabel }} · {{ transcriptionSpeakerMeta }}</strong>
                </div>
              </div>

              <div v-if="selectedArtifact.kind === 'media' && selectedArtifact.status === 'ready'" class="media-summary">
                <el-icon><Microphone /></el-icon>
                <div>
                  <strong>{{ selectedArtifact.document?.filename }}</strong>
                  <span>{{ selectedArtifact.document ? formatFileSize(selectedArtifact.document.file_size) : '' }}</span>
                </div>
              </div>

              <div v-if="selectedArtifact.kind === 'minutes' && currentMinutesText" class="minutes-version-panel">
                <div class="version-row">
                  <el-select
                    v-model="selectedMinutesVersionId"
                    size="small"
                    class="version-select"
                    :disabled="displayMinutesVersions.length <= 1"
                    aria-label="会议纪要版本"
                  >
                    <el-option
                      v-for="version in displayMinutesVersions"
                      :key="version.id"
                      :label="formatMinutesVersionLabel(version)"
                      :value="version.id"
                    />
                  </el-select>
                  <el-tag
                    v-if="selectedMinutesVersion?.is_current"
                    size="small"
                    type="success"
                    effect="plain"
                  >
                    当前
                  </el-tag>
                </div>
                <div v-if="selectedMinutesVersion?.instruction" class="version-instruction">
                  {{ selectedMinutesVersion.instruction }}
                </div>
                <label class="revision-label" for="minutes-revision-input">改写要求</label>
                <el-input
                  id="minutes-revision-input"
                  v-model="revisionInstruction"
                  type="textarea"
                  :rows="3"
                  maxlength="500"
                  show-word-limit
                  resize="none"
                  aria-label="改写要求"
                />
                <el-button
                  type="primary"
                  :icon="EditPen"
                  :loading="revisionLoading"
                  :disabled="!revisionInstruction.trim()"
                  @click="handleReviseMinutes"
                >
                  生成新版
                </el-button>
              </div>

              <div
                v-else-if="selectedArtifact.kind === 'minutes' && selectedArtifact.status === 'missing'"
                class="artifact-generate-panel"
              >
                <el-icon><Tickets /></el-icon>
                <div>
                  <strong>生成会议纪要</strong>
                  <span>基于转录稿自动生成结构化纪要，生成后会保存为会议纪要版本。</span>
                </div>
                <div class="artifact-template-select">
                  <span>纪要模板</span>
                  <el-select
                    v-model="selectedSummaryTemplate"
                    size="small"
                    :disabled="minutesGenerating"
                    @change="handleSummaryTemplateChange"
                  >
                    <el-option
                      v-for="template in SUMMARY_TEMPLATE_OPTIONS"
                      :key="template.id"
                      :label="template.label"
                      :value="template.id"
                    >
                      <div class="summary-template-option">
                        <strong>{{ template.label }}</strong>
                        <span>{{ template.description }}</span>
                      </div>
                    </el-option>
                  </el-select>
                </div>
                <el-button
                  type="primary"
                  :loading="minutesGenerating"
                  :disabled="!meetingDetail.transcriptionContent?.trim()"
                  @click="handleGenerateMinutes"
                >
                  生成纪要
                </el-button>
                <div v-if="minutesGenerating" class="artifact-generate-progress">
                  <el-progress :percentage="minutesGenerationProgress" :show-text="false" />
                  <span>{{ minutesGenerationStage || '正在生成会议纪要...' }}</span>
                </div>
              </div>

              <div
                v-else-if="selectedArtifact.kind === 'emotion' && selectedArtifact.status === 'missing'"
                class="artifact-generate-panel"
              >
                <el-icon><DataAnalysis /></el-icon>
                <div>
                  <strong>生成情绪分析产物</strong>
                  <span>基于转录稿按每位说话人分析情绪基调、风险压力、不确定性和协作信号。</span>
                </div>
                <el-button
                  type="primary"
                  :loading="emotionGenerating"
                  :disabled="!meetingDetail.transcriptionContent?.trim()"
                  @click="handleGenerateEmotionAnalysis"
                >
                  生成分析
                </el-button>
              </div>

              <div v-else-if="hasTextPreview" class="scrollable-text preview-scroll">
                <div class="text-content markdown-content" v-html="selectedArtifactHtml"></div>
              </div>

              <el-empty v-else :image-size="96" description="暂无可预览内容" />
            </div>
          </el-card>
        </aside>
      </div>
    </div>

    <el-drawer
      v-model="speakerCorrectionDrawerVisible"
      title="说话人校正"
      direction="rtl"
      size="520px"
      class="meeting-speaker-drawer"
    >
      <div class="speaker-correction-panel">
        <div class="speaker-correction-summary">
          <div class="speaker-correction-stat">
            <span>说话人</span>
            <strong>{{ speakerCorrectionRows.length }}</strong>
          </div>
          <div class="speaker-correction-stat">
            <span>修改</span>
            <strong>{{ speakerCorrectionChangedCount }}</strong>
          </div>
          <div class="speaker-correction-stat">
            <span>段落</span>
            <strong>{{ speakerCorrectionSegmentCount }}</strong>
          </div>
        </div>

        <el-empty
          v-if="speakerCorrectionRows.length === 0"
          :image-size="92"
          description="未识别到说话人标签"
        />

        <div v-else class="speaker-correction-list">
          <article
            v-for="row in speakerCorrectionRows"
            :key="row.sourceName"
            class="speaker-correction-item"
          >
            <div class="speaker-correction-item-header">
              <div class="speaker-correction-identity">
                <span class="speaker-correction-avatar">
                  <el-icon><User /></el-icon>
                </span>
                <div>
                  <strong>{{ row.sourceName }}</strong>
                  <span>{{ row.count }} 段</span>
                </div>
              </div>
              <el-tag
                v-if="row.draftName.trim() && row.draftName.trim() !== row.sourceName"
                size="small"
                type="warning"
                effect="plain"
              >
                已修改
              </el-tag>
            </div>

            <label class="speaker-correction-field">
              <span>显示名称</span>
              <el-input
                v-model="row.draftName"
                size="small"
                maxlength="32"
                show-word-limit
              />
            </label>

            <div class="speaker-correction-merge">
              <span>合并到</span>
              <el-select
                size="small"
                clearable
                placeholder="选择目标"
                @change="setSpeakerMergeTarget(row, String($event || ''))"
              >
                <el-option
                  v-for="target in speakerCorrectionRows.filter(item => item.sourceName !== row.sourceName)"
                  :key="target.sourceName"
                  :label="target.draftName.trim() || target.sourceName"
                  :value="target.sourceName"
                />
              </el-select>
            </div>
          </article>
        </div>
      </div>

      <template #footer>
        <div class="speaker-correction-footer">
          <el-button @click="speakerCorrectionDrawerVisible = false">关闭</el-button>
          <el-button
            type="primary"
            :loading="speakerCorrectionSaving"
            :disabled="speakerCorrectionChangedCount === 0"
            @click="saveSpeakerCorrections"
          >
            保存校正
          </el-button>
        </div>
      </template>
    </el-drawer>
  </div>
</template>

<style lang="scss" scoped>
.meeting-detail-container {
  padding: 20px;
  max-width: 1200px;
  margin: 0 auto;
  background-color: #f5f7fa;
  min-height: 100vh;
}

.header {
  display: flex;
  align-items: center;
  margin-bottom: 20px;
  gap: 16px;

  .title {
    margin: 0;
    color: #303133;
    font-size: 24px;
    font-weight: 600;
  }
}

.content {
  position: relative;
}

.detail-layout {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 380px;
  gap: 20px;
  align-items: start;
}

.detail-main {
  display: flex;
  min-width: 0;
  flex-direction: column;
  gap: 20px;
}

.preview-rail {
  min-width: 0;
  position: sticky;
  top: 20px;
}

.info-card,
.media-card,
.artifact-card,
.preview-card,
.content-card {
  box-shadow: 0 2px 12px 0 rgba(0, 0, 0, 0.1);
  border-radius: 8px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  font-weight: 600;
  color: #303133;
}

.artifact-card-actions {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 8px;
}

.info-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
  gap: 16px;
}

.info-item {
  display: flex;
  align-items: center;
  
  label {
    font-weight: 600;
    color: #606266;
    margin-right: 8px;
    min-width: 80px;
  }
  
  span {
    color: #303133;
  }
}

.audio-player {
  .player-controls {
    display: flex;
    align-items: center;
    gap: 16px;
    margin-bottom: 16px;
    
    .time-info {
      font-size: 14px;
      color: #606266;
    }
  }
  
  .progress-bar {
    margin-top: 8px;
  }
}

.video-player {
  width: 100%;
  max-height: 520px;
  border-radius: 6px;
  background: #000;
  display: block;
}

.artifact-timeline {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.artifact-step {
  width: 100%;
  min-height: 86px;
  display: grid;
  grid-template-columns: 44px minmax(0, 1fr);
  gap: 12px;
  padding: 14px;
  border: 1px solid #e4e7ed;
  border-radius: 8px;
  background: #ffffff;
  color: #303133;
  text-align: left;
  cursor: pointer;
  transition: border-color 0.2s ease, background-color 0.2s ease, box-shadow 0.2s ease;

  &:hover,
  &:focus-visible {
    border-color: #409eff;
    background: #f5f9ff;
    outline: none;
  }

  &.is-active {
    border-color: #409eff;
    box-shadow: 0 0 0 2px rgba(64, 158, 255, 0.12);
  }

  &.is-missing {
    color: #909399;
    background: #fafafa;
  }

  &.is-generatable {
    background: #f5f9ff;
  }
}

.artifact-icon {
  width: 44px;
  height: 44px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 8px;
  color: #1f5f99;
  background: #e8f3ff;
  font-size: 20px;

  .is-missing & {
    color: #909399;
    background: #f0f2f5;
  }
}

.artifact-body {
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.artifact-title-row {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  align-items: center;
  justify-content: flex-start;
  min-width: 0;
}

.artifact-title {
  min-width: 0;
  flex: 1 1 140px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 15px;
  font-weight: 600;
}

.artifact-status {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  flex: 0 0 auto;
  margin-left: auto;
  color: #529b2e;
  font-size: 12px;

  .is-missing & {
    color: #909399;
  }

  .is-generatable & {
    color: #1f5f99;
  }
}

.artifact-review-status {
  display: inline-flex;
  align-items: center;
  min-height: 22px;
  padding: 0 8px;
  border-radius: 999px;
  border: 1px solid #dcdfe6;
  background: #f8fafc;
  color: #606266;
  font-size: 12px;
  line-height: 1;

  &.is-reviewed {
    border-color: #b7eb8f;
    background: #f6ffed;
    color: #389e0d;
  }

  &.is-pending {
    border-color: #ffd591;
    background: #fff7e6;
    color: #ad6800;
  }

  &.is-muted {
    border-color: #dcdfe6;
    background: #f5f7fa;
    color: #909399;
  }
}

.artifact-subtitle,
.artifact-meta {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: #606266;
  font-size: 13px;
  line-height: 1.35;
}

.artifact-meta {
  color: #909399;
}

.preview-card {
  overflow: hidden;
}

.preview-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 12px;
  min-width: 0;
}

.preview-heading {
  min-width: 0;
  flex: 1 1 170px;
}

.preview-title {
  min-width: 0;
  overflow: hidden;
  color: #303133;
  font-weight: 600;
  line-height: 1.4;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.preview-subtitle {
  max-width: 220px;
  margin-top: 3px;
  overflow: hidden;
  color: #909399;
  font-size: 12px;
  line-height: 1.35;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.preview-actions {
  min-width: 0;
  flex: 1 1 320px;
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  align-items: center;
  gap: 8px;

  :deep(.el-button) {
    margin-left: 0;
  }
}

.preview-template-select {
  width: 150px;
  flex: 0 1 150px;
}

.preview-content {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.preview-meta-grid {
  display: grid;
  grid-template-columns: 1fr;
  gap: 8px;
}

.preview-meta-item {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  padding: 10px 12px;
  border-radius: 8px;
  background: #f5f7fa;
  color: #606266;
  font-size: 13px;

  strong {
    min-width: 0;
    color: #303133;
    font-weight: 600;
    text-align: right;
    overflow-wrap: anywhere;
  }
}

.media-summary {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 14px;
  border: 1px solid #e4e7ed;
  border-radius: 8px;
  background: #ffffff;
  color: #606266;

  .el-icon {
    flex: 0 0 auto;
    color: #1f5f99;
    font-size: 24px;
  }

  div {
    min-width: 0;
    display: flex;
    flex-direction: column;
    gap: 4px;
  }

  strong,
  span {
    min-width: 0;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  strong {
    color: #303133;
    font-size: 14px;
  }

  span {
    font-size: 13px;
  }
}

.minutes-version-panel {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 12px;
  border: 1px solid #e4e7ed;
  border-radius: 8px;
  background: #ffffff;
}

.version-row {
  display: flex;
  align-items: center;
  gap: 8px;
}

.version-select {
  min-width: 0;
  flex: 1 1 auto;
}

.version-instruction {
  padding: 8px 10px;
  border-radius: 6px;
  background: #f5f7fa;
  color: #606266;
  font-size: 12px;
  line-height: 1.5;
  overflow-wrap: anywhere;
}

.revision-label {
  color: #303133;
  font-size: 13px;
  font-weight: 600;
}

.artifact-generate-panel {
  display: grid;
  grid-template-columns: 42px minmax(0, 1fr);
  gap: 12px;
  padding: 16px;
  border: 1px solid #d9ecff;
  border-radius: 8px;
  background: #f4f9ff;
  color: #606266;

  .el-icon {
    width: 42px;
    height: 42px;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    border-radius: 8px;
    background: #e8f3ff;
    color: #1f5f99;
    font-size: 22px;
  }

  div {
    min-width: 0;
    display: flex;
    flex-direction: column;
    gap: 4px;
  }

  strong {
    color: #303133;
    font-size: 14px;
  }

  span {
    color: #64748b;
    font-size: 13px;
    line-height: 1.5;
  }

  .el-button {
    grid-column: 1 / -1;
    justify-self: stretch;
  }
}

.artifact-template-select {
  grid-column: 1 / -1;
  display: grid !important;
  grid-template-columns: 72px minmax(0, 1fr);
  align-items: center;
  gap: 8px !important;

  > span {
    color: #606266;
    font-size: 13px;
  }
}

.summary-template-option {
  display: flex;
  min-width: 0;
  flex-direction: column;
  gap: 2px;

  strong {
    color: #303133;
    font-size: 13px;
    line-height: 1.3;
  }

  span {
    color: #909399;
    font-size: 12px;
    line-height: 1.3;
  }
}

.artifact-generate-progress {
  grid-column: 1 / -1;
  display: flex;
  min-width: 0;
  flex-direction: column;
  gap: 6px;

  span {
    color: #64748b;
    font-size: 12px;
    line-height: 1.4;
  }
}

.meeting-speaker-drawer :deep(.el-drawer__body) {
  padding: 0;
  background: #f8fafc;
}

.speaker-correction-panel {
  display: flex;
  flex-direction: column;
  gap: 14px;
  min-height: 100%;
  padding: 16px 18px 20px;
}

.speaker-correction-summary {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 10px;
}

.speaker-correction-stat {
  min-width: 0;
  padding: 10px 12px;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  background: #ffffff;

  span {
    display: block;
    color: #64748b;
    font-size: 12px;
  }

  strong {
    display: block;
    margin-top: 4px;
    color: #111827;
    font-size: 18px;
    line-height: 1.2;
  }
}

.speaker-correction-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.speaker-correction-item {
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 14px;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  background: #ffffff;
}

.speaker-correction-item-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}

.speaker-correction-identity {
  display: flex;
  gap: 10px;
  min-width: 0;

  div {
    min-width: 0;
    display: flex;
    flex-direction: column;
    gap: 4px;
  }

  strong {
    min-width: 0;
    color: #111827;
    font-size: 14px;
    overflow-wrap: anywhere;
  }

  span {
    color: #64748b;
    font-size: 12px;
  }
}

.speaker-correction-avatar {
  width: 34px;
  height: 34px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex: 0 0 auto;
  border-radius: 50%;
  background: #2563eb;
  color: #ffffff;
}

.speaker-correction-field {
  display: flex;
  flex-direction: column;
  gap: 6px;

  span {
    color: #64748b;
    font-size: 12px;
  }
}

.speaker-correction-merge {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr);
  align-items: center;
  gap: 8px;
  padding-top: 10px;
  border-top: 1px solid #f1f5f9;

  > span {
    color: #64748b;
    font-size: 13px;
  }
}

.speaker-correction-footer {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}

.preview-scroll {
  max-height: calc(100vh - 260px);
  min-height: 360px;
}

.scrollable-text {
  max-height: 400px;
  overflow-y: auto;
  border: 1px solid #e4e7ed;
  border-radius: 4px;
  background: #fafafa;
}

.text-content {
  margin: 0;
  padding: 16px;
  font-size: 14px;
  line-height: 1.6;
  color: #303133;
  background: transparent;
}

.markdown-content {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
  text-align: left;
  
  h1, h2, h3, h4, h5, h6 {
    margin: 16px 0 8px 0;
    font-weight: 600;
    color: #303133;
  }
  
  h1 { font-size: 24px; }
  h2 { font-size: 20px; }
  h3 { font-size: 18px; }
  h4 { font-size: 16px; }
  h5 { font-size: 14px; }
  h6 { font-size: 12px; }
  
  p {
    margin: 8px 0;
  }
  
  ul, ol {
    margin: 8px 0;
    padding-left: 24px;
  }
  
  li {
    margin: 4px 0;
  }
  
  blockquote {
    margin: 16px 0;
    padding: 8px 16px;
    border-left: 4px solid #409eff;
    background: #f0f9ff;
    color: #606266;
  }
  
  code {
    padding: 2px 4px;
    background: #f5f7fa;
    border-radius: 3px;
    font-family: 'Monaco', 'Menlo', 'Ubuntu Mono', monospace;
    font-size: 13px;
  }
  
  pre {
    margin: 16px 0;
    padding: 12px;
    background: #f5f7fa;
    border-radius: 6px;
    overflow-x: auto;
    
    code {
      padding: 0;
      background: transparent;
    }
  }
  
  table {
    width: 100%;
    border-collapse: collapse;
    margin: 16px 0;
  }
  
  th, td {
    padding: 8px 12px;
    border: 1px solid #e4e7ed;
    text-align: left;
  }
  
  th {
    background: #f5f7fa;
    font-weight: 600;
  }
  
  strong {
    font-weight: 600;
    color: #303133;
    display: block;
    text-align: left !important;
    margin: 12px 0 6px 0;
    padding: 6px 0;
    border-bottom: 1px solid #e4e7ed;
    width: 100%;
    float: left;
    clear: both;
    background: #f8f9fa;
    padding-left: 8px;
  }
  
  // 时间戳样式
  strong + br + em,
  em {
    display: block;
    font-style: normal;
    color: #909399;
    font-size: 12px;
    margin: 4px 0;
    padding: 2px 8px;
    background: #f0f2f5;
    border-radius: 3px;
    width: fit-content;
  }
  
  // 内容段落样式
  p {
    margin: 8px 0 16px 0;
    padding: 8px;
    line-height: 1.8;
    background: #ffffff;
    border-left: 3px solid #e4e7ed;
    padding-left: 12px;
  }
  
  em {
    font-style: italic;
  }
  
  a {
    color: #409eff;
    text-decoration: none;
    
    &:hover {
      text-decoration: underline;
    }
  }
}

// 滚动条样式
.scrollable-text::-webkit-scrollbar {
  width: 8px;
}

.scrollable-text::-webkit-scrollbar-track {
  background: #f1f1f1;
  border-radius: 4px;
}

.scrollable-text::-webkit-scrollbar-thumb {
  background: #c1c1c1;
  border-radius: 4px;
  
  &:hover {
    background: #a8a8a8;
  }
}

@media (max-width: 1024px) {
  .detail-layout {
    grid-template-columns: 1fr;
  }

  .preview-rail {
    position: static;
  }

  .preview-scroll {
    max-height: 520px;
    min-height: 260px;
  }
}

@media (max-width: 768px) {
  .meeting-detail-container {
    padding: 16px;
  }
  
  .header {
    align-items: flex-start;
    flex-direction: column;
    gap: 10px;

    .title {
      font-size: 20px;
    }
  }
  
  .info-grid {
    grid-template-columns: 1fr;
  }

  .info-item {
    align-items: flex-start;
    flex-direction: column;
    gap: 4px;

    label {
      min-width: 0;
    }
  }

  .artifact-step {
    grid-template-columns: 40px minmax(0, 1fr);
    min-height: 92px;
    padding: 12px;
  }

  .artifact-icon {
    width: 40px;
    height: 40px;
  }

  .artifact-title-row {
    align-items: flex-start;
    flex-direction: column;
    gap: 4px;
  }

  .artifact-status {
    margin-left: 0;
  }

  .preview-header {
    align-items: stretch;
    flex-direction: column;
  }

  .preview-actions {
    flex: 0 1 auto;
    justify-content: flex-start;
  }

  .preview-subtitle {
    max-width: none;
  }

  .meeting-speaker-drawer {
    width: 100% !important;
  }

  .speaker-correction-summary {
    grid-template-columns: 1fr;
  }

  .speaker-correction-merge {
    grid-template-columns: 1fr;
  }
}
</style>
