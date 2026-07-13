<script setup lang="ts">
import { useAsrStore } from '../stores/asr'
import { computed, ref, nextTick, onBeforeUnmount, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox, ElLoading } from 'element-plus'
import { Microphone, QuestionFilled, Setting, VideoPause, VideoPlay, Download, User, ChatDotRound, Upload } from '@element-plus/icons-vue'
import { generateSummary, type BackendSummaryTask } from '../utils/summary'
import {
  SUMMARY_TEMPLATE_OPTIONS,
  buildSummaryOptionsFromSettings,
  buildTranscriptForSummary,
  getSummaryTemplateIdFromLocalStorage,
  setSummaryTemplateIdToLocalStorage
} from '../utils/summaryRequest'
import { processText } from '../utils/textProcessor'
import TranslateDialog from './TranslateDialog.vue'
import hotwordsConfig from '../config/hotwords.json'
import type { IndustryType } from '../interface/hotwords'
import { registerSpeaker, registerSpeakerFromUploadedSegment, blobToBase64, listSpeakers, type SpeakerInfo } from '../api/speaker'
import {
  uploadApi,
  type AudioRecognitionData,
  type AudioRecognitionTask,
  type UploadedAudioSegment,
  type UploadedAudioRegistrationRef,
  type UploadedSpeakerCandidate,
  type UploadedSpeakerSample
} from '../api/upload'
import {
  meetingApi,
  type UploadedMeetingTranscription
} from '../api/meeting'
import { hotwordApi, type HotwordAsset } from '../api/hotwords'
import { API_ENDPOINTS } from '../config/api'

const props = withDefaults(defineProps<{
  currentFileName?: string
  recognitionMode?: string
  restoredMeetingId?: number | null
  restoredAudioUrl?: string
  restoredTranscriptionText?: string
}>(), {
  currentFileName: '',
  recognitionMode: 'realtime',
  restoredMeetingId: null,
  restoredAudioUrl: '',
  restoredTranscriptionText: ''
})

const hotwordDialogVisible = ref(false)
const hotwordInput = ref('')
const selectedIndustry = ref<IndustryType | ''>('')
const batchEditDialogVisible = ref(false)
const originalContent = ref('')
const modifiedContent = ref('')
const currentMatchIndex = ref(0)  // 当前匹配项索引
const totalMatches = ref(0)       // 总匹配数量
const matchedSegments = ref<Array<{segmentIndex: number, matchIndex: number}>>([])  // 匹配项列表
const translateDialogVisible = ref(false)
const translateInput = ref('')
const settingsPopoverVisible = ref(false)
const route = useRoute()
const router = useRouter()
const meetingTitle = ref('')
const isEditingTitle = ref(false)
const titleInputRef = ref<HTMLInputElement | null>(null)
const manualSpeakerDialogVisible = ref(false)
const manualSpeakerOptions = ref<SpeakerInfo[]>([])
const manualSpeakerLoading = ref(false)
const selectedManualSpeaker = ref('')
const activeManualSpeaker = ref('')
const pendingManualSpeaker = ref('')
const manualSpeakerResetTimer = ref<number | null>(null)
const isGeneratingSummary = ref(false)
const summaryProgress = ref(0)
const summaryStage = ref('')
const audioUploadInputRef = ref<HTMLInputElement | null>(null)
const isUploadingAudio = ref(false)
const isUploadSetupVisible = ref(true)
const uploadedRegistrationAudio = ref<UploadedAudioRegistrationRef | null>(null)
const uploadedRecognitionData = ref<AudioRecognitionData | null>(null)
const activeUploadTaskId = ref('')
const uploadTaskProgress = ref(0)
const uploadTaskStage = ref('')
const uploadAbortController = ref<AbortController | null>(null)
const uploadCancelRequested = ref(false)
const isCancellingUpload = ref(false)
const expectedUploadSpeakers = ref(localStorage.getItem('upload_expected_speakers') || '')
const speakerReviewDialogVisible = ref(false)
const speakerReviewLoading = ref(false)
const uploadedSpeakerCandidates = ref<UploadedSpeakerCandidate[]>([])
const speakerMergeTargets = ref<Record<string, string>>({})
const isLoadingRestoredUpload = ref(false)
const restoredUploadDataLoaded = ref(false)
const hotwordAssets = ref<HotwordAsset[]>([])
const selectedHotwordCategories = ref<string[]>(loadSelectedHotwordCategories())
const isLoadingHotwordAssets = ref(false)
const hotwordAssetsLastSync = ref('')
const hotwordAssetsError = ref('')
let uploadedSegmentAudio: HTMLAudioElement | null = null
const isUploadMode = computed(() => props.recognitionMode === 'upload')
const transcriptTitle = computed(() => isUploadMode.value ? '上传识别结果' : '实时转录')
const uploadTaskStageLabels: Record<string, string> = {
  prepare: '准备音视频',
  asr: '语音识别中',
  speaker: '说话人整理中',
  translation: '翻译中'
}

const formatUploadTaskStage = (stage?: string) => {
  const normalizedStage = (stage || '').trim()
  if (!normalizedStage) return '正在识别音视频'
  return uploadTaskStageLabels[normalizedStage.toLowerCase()] || normalizedStage
}
const transcriptPlaceholder = computed(() => {
  if (isUploadMode.value && isUploadingAudio.value) {
    return '正在识别音视频，结果会显示在这里。'
  }
  return isUploadMode.value ? '上传音视频后，识别结果会显示在这里。' : '等待语音输入...'
})
const protectedHotwordAssetCount = computed(() => hotwordAssets.value.filter(item => item.protected).length)
const hotwordAssetCategories = computed(() => {
  return Array.from(new Set(hotwordAssets.value.map(item => item.category || '通用')))
    .sort((a, b) => a.localeCompare(b, 'zh-CN'))
})
const activeHotwordAssets = computed(() => {
  if (selectedHotwordCategories.value.length === 0) {
    return hotwordAssets.value
  }
  const selected = new Set(selectedHotwordCategories.value)
  return hotwordAssets.value.filter(item => selected.has(item.category || '通用'))
})
const activeHotwordAssetCount = computed(() => activeHotwordAssets.value.length)
const hotwordAssetScopeText = computed(() => {
  if (selectedHotwordCategories.value.length === 0) return '全部分类'
  return selectedHotwordCategories.value.join('、')
})
const hotwordAssetsStatusText = computed(() => {
  if (hotwordAssetsError.value) return '同步失败'
  if (isLoadingHotwordAssets.value) return '同步中'
  if (hotwordAssets.value.length > 0) {
    return activeHotwordAssetCount.value === hotwordAssets.value.length
      ? `${hotwordAssets.value.length} 个`
      : `${activeHotwordAssetCount.value}/${hotwordAssets.value.length} 个`
  }
  return '未加载'
})
const formatDurationMs = (durationMs?: number) => {
  const totalSeconds = Math.round(Math.max(0, Number(durationMs || 0)) / 1000)
  if (totalSeconds <= 0) return '0 秒'
  if (totalSeconds < 60) return `${totalSeconds} 秒`
  const minutes = Math.floor(totalSeconds / 60)
  const seconds = totalSeconds % 60
  return seconds ? `${minutes} 分 ${seconds} 秒` : `${minutes} 分`
}
const speakerReviewCandidateCount = computed(() => uploadedSpeakerCandidates.value.length)
const speakerReviewSegmentCount = computed(() => {
  return uploadedSpeakerCandidates.value.reduce((total, candidate) => total + candidate.segment_count, 0)
})
const speakerReviewTotalDurationMs = computed(() => {
  return uploadedSpeakerCandidates.value.reduce((total, candidate) => {
    return total + Number(candidate.total_duration_ms || 0)
  }, 0)
})
const speakerReviewTotalDurationLabel = computed(() => formatDurationMs(speakerReviewTotalDurationMs.value))

function loadSelectedHotwordCategories() {
  try {
    const saved = localStorage.getItem('hotword_asset_categories')
    const parsed = saved ? JSON.parse(saved) : []
    return Array.isArray(parsed) ? parsed.filter(item => typeof item === 'string') : []
  } catch {
    return []
  }
}

type FrontendSpeakerSegment = {
  speaker: string
  text: string
  timestamp?: number[][] | string
  mode: string
  startTime?: string
  endTime?: string
  startMs?: number
  endMs?: number
  translation?: string
  registrationAudio?: UploadedAudioRegistrationRef
  segmentIndex?: number
}

type FrontendSpeakerSegmentGroup = FrontendSpeakerSegment & {
  segments: FrontendSpeakerSegment[]
  groupIndex: number
}

// LLM服务配置
const serviceType = ref('xinference')
const selectedSummaryTemplate = ref(getSummaryTemplateIdFromLocalStorage())

// Ollama配置
const ollamaEndpoint = ref('https://10.1.0.27/ollama/api/chat')
const ollamaModel = ref('qwen3:30b-a3b-q4_K_M')

// Xinference配置
const xinferenceEndpoint = ref('http://10.1.0.26:9997/v1/chat/completions')
const xinferenceModel = ref('DeepSeek-R1-671B-1')
const xinferenceApiKey = ref('')
const xinferenceHasApiKey = ref(false)

// vLLM配置
const vllmEndpoint = ref('http://localhost:8000/v1/chat/completions')
const vllmModel = ref('meta-llama/Llama-2-7b-chat-hf')
const vllmApiKey = ref('')
const vllmHasApiKey = ref(false)

// SGLang配置
const sglangEndpoint = ref('http://localhost:30000/v1/chat/completions')
const sglangModel = ref('meta-llama/Llama-2-7b-chat-hf')
const sglangApiKey = ref('')
const sglangHasApiKey = ref(false)

// 说话人识别配置
const enableSpeakerDiarization = ref(localStorage.getItem('enable_speaker_diarization') === 'false' ? false : true)
const enableUploadedVoiceprintMatching = ref(localStorage.getItem('enable_uploaded_voiceprint_matching') === 'true')

// 翻译功能配置
const enableTranslation = ref(localStorage.getItem('enable_translation') === 'true')

// 会议纪要区域显示控制
const showMinutesPanel = ref(localStorage.getItem('show_minutes_panel') === 'false' ? false : true)

// 初始化store
const store = useAsrStore()

interface BackendLLMServiceConfig {
  endpoint?: string
  model?: string
  hasApiKey?: boolean
}

interface BackendLLMConfig {
  activeServiceType?: string
  services?: Record<string, BackendLLMServiceConfig>
}

let llmConfigSaveTimer: number | null = null
const isApplyingBackendLLMConfig = ref(false)

const clearLegacyLLMLocalStorage = () => {
  [
    'llm_service_type',
    'ollama_endpoint',
    'ollama_model',
    'xinference_endpoint',
    'xinference_model',
    'xinference_api_key',
    'vllm_endpoint',
    'vllm_model',
    'vllm_api_key',
    'sglang_endpoint',
    'sglang_model',
    'sglang_api_key'
  ].forEach(key => localStorage.removeItem(key))
}

const applyBackendLLMConfig = (config: BackendLLMConfig) => {
  isApplyingBackendLLMConfig.value = true
  try {
    serviceType.value = config.activeServiceType || 'xinference'

    const services = config.services || {}
    const ollamaConfig = services.ollama || {}
    const xinferenceConfig = services.xinference || {}
    const vllmConfig = services.vllm || {}
    const sglangConfig = services.sglang || {}

    ollamaEndpoint.value = ollamaConfig.endpoint || 'https://10.1.0.27/ollama/api/chat'
    ollamaModel.value = ollamaConfig.model || 'qwen3:30b-a3b-q4_K_M'
    xinferenceEndpoint.value = xinferenceConfig.endpoint || 'http://10.1.0.26:9997/v1/chat/completions'
    xinferenceModel.value = xinferenceConfig.model || 'DeepSeek-R1-671B-1'
    xinferenceHasApiKey.value = Boolean(xinferenceConfig.hasApiKey)
    vllmEndpoint.value = vllmConfig.endpoint || 'http://localhost:8000/v1/chat/completions'
    vllmModel.value = vllmConfig.model || 'meta-llama/Llama-2-7b-chat-hf'
    vllmHasApiKey.value = Boolean(vllmConfig.hasApiKey)
    sglangEndpoint.value = sglangConfig.endpoint || 'http://localhost:30000/v1/chat/completions'
    sglangModel.value = sglangConfig.model || 'meta-llama/Llama-2-7b-chat-hf'
    sglangHasApiKey.value = Boolean(sglangConfig.hasApiKey)
  } finally {
    setTimeout(() => {
      isApplyingBackendLLMConfig.value = false
    }, 0)
  }
}

const readApiData = async <T,>(response: Response): Promise<T> => {
  const text = await response.text()
  const payload = text ? JSON.parse(text) : null

  if (!response.ok) {
    throw new Error(payload?.message || payload?.error || text || `HTTP ${response.status}`)
  }

  return (payload?.data ?? payload) as T
}

const buildBackendLLMConfigPayload = () => ({
  activeServiceType: serviceType.value,
  services: {
    ollama: {
      endpoint: ollamaEndpoint.value,
      model: ollamaModel.value
    },
    xinference: {
      endpoint: xinferenceEndpoint.value,
      model: xinferenceModel.value,
      apiKey: xinferenceApiKey.value.trim() || undefined
    },
    vllm: {
      endpoint: vllmEndpoint.value,
      model: vllmModel.value,
      apiKey: vllmApiKey.value.trim() || undefined
    },
    sglang: {
      endpoint: sglangEndpoint.value,
      model: sglangModel.value,
      apiKey: sglangApiKey.value.trim() || undefined
    }
  }
})

const saveBackendLLMConfig = async (showMessage = false) => {
  if (llmConfigSaveTimer) {
    clearTimeout(llmConfigSaveTimer)
    llmConfigSaveTimer = null
  }

  const hadNewApiKey = Boolean(
    xinferenceApiKey.value.trim() ||
    vllmApiKey.value.trim() ||
    sglangApiKey.value.trim()
  )

  const response = await fetch(API_ENDPOINTS.LLM.CONFIG, {
    method: 'PUT',
    headers: {
      'Content-Type': 'application/json'
    },
    body: JSON.stringify(buildBackendLLMConfigPayload())
  })
  const config = await readApiData<BackendLLMConfig>(response)
  applyBackendLLMConfig(config)

  if (hadNewApiKey) {
    xinferenceApiKey.value = ''
    vllmApiKey.value = ''
    sglangApiKey.value = ''
  }

  if (showMessage) {
    ElMessage.success('会议纪要模型配置已保存')
  }
}

const scheduleSaveBackendLLMConfig = () => {
  if (isApplyingBackendLLMConfig.value) return
  if (llmConfigSaveTimer) {
    clearTimeout(llmConfigSaveTimer)
  }
  llmConfigSaveTimer = window.setTimeout(() => {
    saveBackendLLMConfig().catch(error => {
      console.error('保存LLM配置失败:', error)
      ElMessage.error(`保存LLM配置失败：${(error as Error).message || String(error)}`)
    })
    llmConfigSaveTimer = null
  }, 800)
}

const loadBackendLLMConfig = async () => {
  try {
    clearLegacyLLMLocalStorage()
    const response = await fetch(API_ENDPOINTS.LLM.CONFIG)
    const config = await readApiData<BackendLLMConfig>(response)
    applyBackendLLMConfig(config)
  } catch (error) {
    console.warn('加载后端LLM配置失败，将使用默认配置:', error)
  }
}

const buildCurrentSummaryOptions = () => {
  const options = buildSummaryOptionsFromSettings({
    serviceType: serviceType.value,
    templateId: selectedSummaryTemplate.value,
    ollamaEndpoint: ollamaEndpoint.value,
    ollamaModel: ollamaModel.value,
    xinferenceEndpoint: xinferenceEndpoint.value,
    xinferenceModel: xinferenceModel.value,
    xinferenceApiKey: xinferenceApiKey.value,
    vllmEndpoint: vllmEndpoint.value,
    vllmModel: vllmModel.value,
    vllmApiKey: vllmApiKey.value,
    sglangEndpoint: sglangEndpoint.value,
    sglangModel: sglangModel.value,
    sglangApiKey: sglangApiKey.value
  })

  if (props.restoredMeetingId) {
    options.meetingId = props.restoredMeetingId
  }

  return options
}

const handleSummaryTemplateChange = (templateId: string) => {
  selectedSummaryTemplate.value = setSummaryTemplateIdToLocalStorage(templateId)
}

const getCurrentSummaryTranscript = () => buildTranscriptForSummary(store.transcript, store.speakerSegments, {
  useSpeakerSegments: enableSpeakerDiarization.value,
  formatTimeRange
})

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

// 音频采集模式配置
const audioCaptureMode = computed({
  get: () => store.audioCaptureMode,
  set: (value) => {
    store.audioCaptureMode = value
  }
})

// 监听LLM配置变化并保存到后端，避免API Key长期保存在浏览器localStorage
watch([
  serviceType,
  ollamaEndpoint,
  ollamaModel,
  xinferenceEndpoint,
  xinferenceModel,
  xinferenceApiKey,
  vllmEndpoint,
  vllmModel,
  vllmApiKey,
  sglangEndpoint,
  sglangModel,
  sglangApiKey
], scheduleSaveBackendLLMConfig)

watch(enableSpeakerDiarization, (newVal) => {
  localStorage.setItem('enable_speaker_diarization', newVal.toString())
  const settingName = '说话人识别'
  console.log(`${settingName}设置已更新:`, newVal)

  // 如果正在录音，通过WebSocket发送配置更新消息
  if (store.isRecording && store.wsConnection?.isConnected) {
    const updateConfig = {
      type: 'update_config',
      enable_speaker_diarization: newVal
    }
    store.wsConnection.send(JSON.stringify(updateConfig))
    ElMessage.success(`${settingName}设置已实时更新`)
  } else {
    ElMessage.success(`${settingName}设置已更新`)
  }
})

watch(enableUploadedVoiceprintMatching, (newVal) => {
  localStorage.setItem('enable_uploaded_voiceprint_matching', newVal.toString())
  console.log('上传声纹匹配设置已更新:', newVal)
  ElMessage.success(`声纹匹配已${newVal ? '启用' : '禁用'}`)
})

watch(enableTranslation, (newVal) => {
  localStorage.setItem('enable_translation', newVal.toString())
  store.enableTranslation = newVal
  console.log('翻译功能设置已更新:', newVal)

  if (store.isRecording && store.wsConnection?.isConnected) {
    const updateConfig = {
      type: 'update_config',
      enable_translation: newVal
    }
    store.wsConnection.send(JSON.stringify(updateConfig))
    ElMessage.success(`翻译功能已实时${newVal ? '启用' : '禁用'}`)
  } else {
    ElMessage.success(`翻译功能已${newVal ? '启用' : '禁用'}`)
  }
})

watch(expectedUploadSpeakers, (newVal) => {
  localStorage.setItem('upload_expected_speakers', newVal)
})

watch(selectedHotwordCategories, () => {
  localStorage.setItem('hotword_asset_categories', JSON.stringify(selectedHotwordCategories.value))
  applyHotwordAssetsToStore()
}, { deep: true })

watch(showMinutesPanel, (newVal) => {
  localStorage.setItem('show_minutes_panel', newVal.toString())
  emit('toggle-minutes-panel', newVal)
  // 关闭设置弹出框，避免布局变化时位置错乱
  settingsPopoverVisible.value = false
  ElMessage.success(newVal ? '会议纪要区域已显示' : '会议纪要区域已隐藏')
})

// 音频采集模式监听器
watch(audioCaptureMode, async (newVal) => {
  localStorage.setItem('audio_capture_mode', newVal)
  console.log('音频采集模式已更新:', newVal)
  
  // 切换模式后重新获取音频设备列表
  try {
    await store.getAudioDevices()
    const modeNames = {
      browser: '浏览器采集音频',
      server: '服务器采集音频'
    }
    ElMessage.success(`已切换到${modeNames[newVal]}模式`)
  } catch (error) {
    ElMessage.error(`切换模式失败：${(error as Error).message || String(error)}`)
  }
})



// 语言参数监听器
watch(() => store.language, (newVal) => {
  localStorage.setItem('asr_language', newVal)
  
  if (store.isRecording && store.wsConnection?.isConnected) {
    const updateConfig = {
      type: 'update_config',
      language: newVal
    }
    store.wsConnection.send(JSON.stringify(updateConfig))
    
    const languageNames: Record<string, string> = {
      'auto': '自动检测',
      'zh': '中文',
      'en': '英文',
      'yue': '粤语',
      'ja': '日语',
      'ko': '韩语'
    }
    ElMessage.success(`识别语言已更新为: ${languageNames[newVal] || newVal}`)
  }
})

// 音频设备监听器
watch(() => store.audioSource, (newVal, oldVal) => {
  if (newVal !== oldVal && oldVal) {
    const deviceName = store.audioDevices.find(d => d.deviceId === newVal)?.label || '未知设备'
    
    if (store.isRecording && audioCaptureMode.value === 'browser') {
      ElMessage.warning({
        message: `音频设备已切换到"${deviceName}"，需要重新开始录音才能生效`,
        duration: 5000
      })
    } else {
      ElMessage.success(`音频设备已切换到"${deviceName}"`)
    }
    
    console.log(`音频设备已切换: ${oldVal} -> ${newVal}`)
  }
})

// 测试LLM服务连接并生成会议纪要
const testLLMConnection = async () => {
  const serviceNames = {
    ollama: 'Ollama',
    xinference: 'Xinference',
    vllm: 'vLLM',
    sglang: 'SGLang'
  }
  
  // 检查转写内容是否为空（兼容说话人识别模式）
  if (actualCharCount.value === 0) {
    ElMessage.warning('当前没有转写内容。建议先进行语音录制后再测试，以获得更真实的效果。')
    return
  }
  
  const loadingMessage = ElMessage({
    message: `正在测试${serviceNames[serviceType.value as keyof typeof serviceNames]}连接并生成会议纪要...`,
    type: 'info',
    duration: 0,
    showClose: false
  })
  
  try {
    await saveBackendLLMConfig()
    const options = buildCurrentSummaryOptions()
    options.onSummaryProgress = updateSummaryProgress
    const transcriptContent = getCurrentSummaryTranscript()
    
    // 使用语音转录文本框中的实际内容进行测试
    isGeneratingSummary.value = true
    summaryStage.value = '正在提交测试生成任务...'
    const summary = await generateSummary(transcriptContent, options)
    
    loadingMessage.close()
    
    // 将生成的纪要发送给父组件显示
    store.meetingSummary = summary
    emit('update:content', summary)
    emit('summary-generated', summary)
    
    ElMessage.success(`${serviceNames[serviceType.value as keyof typeof serviceNames]}连接成功！会议纪要已生成`)
    
  } catch (error) {
    loadingMessage.close()
    
    console.error('测试连接失败:', error)
    ElMessage.error(`测试失败：${(error as Error).message || String(error)}`)
  } finally {
    finishSummaryProgress()
  }
}

// 保持向后兼容
const testOllamaConnection = testLLMConnection

// 音频播放器相关
const audioRef = ref<HTMLAudioElement | null>(null)
const transcriptContentRef = ref<HTMLElement | null>(null)
const isPlaying = ref(false)
const currentTime = ref(0)
const duration = ref(0)
const progressWidth = ref(0)
const activeSeekSegmentIndex = ref<number | null>(null)
let lastAutoScrolledSegmentIndex: number | null = null
let transcriptFollowFrame = 0

// 录音时长相关
const recordingDuration = ref(0)
const recordingTimer = ref<number | null>(null)

const formatTime = (time: number) => {
  const minutes = Math.floor(time / 60)
  const seconds = Math.floor(time % 60)
  return `${minutes}:${seconds.toString().padStart(2, '0')}`
}

const togglePlay = () => {
  if (!audioRef.value) return
  
  if (isPlaying.value) {
    audioRef.value.pause()
  } else {
    audioRef.value.play().catch(error => {
      console.error('音频播放失败:', error)
      ElMessage.error('音频播放失败，请稍后重试')
    })
  }
}

const updateProgress = (forceFollowTranscript = false) => {
  if (!audioRef.value) return
  const nextDuration = Number.isFinite(audioRef.value.duration) ? audioRef.value.duration : 0
  currentTime.value = audioRef.value.currentTime || 0
  duration.value = nextDuration
  progressWidth.value = nextDuration > 0
    ? Math.min(100, Math.max(0, (currentTime.value / nextDuration) * 100))
    : 0
  syncActiveSegmentWithPlayback({ forceScroll: forceFollowTranscript })
}

const handleProgressClick = (event: MouseEvent) => {
  if (!audioRef.value || duration.value <= 0) return
  const progressBar = event.currentTarget as HTMLElement
  const rect = progressBar.getBoundingClientRect()
  const percent = Math.min(1, Math.max(0, (event.clientX - rect.left) / rect.width))
  audioRef.value.currentTime = percent * duration.value
  updateProgress(true)
}

const handleAudioPlay = () => {
  isPlaying.value = true
  updateProgress(true)
}

const handleAudioPause = () => {
  isPlaying.value = false
}

const handleAudioEnded = () => {
  isPlaying.value = false
  updateProgress()
  activeSeekSegmentIndex.value = null
  lastAutoScrolledSegmentIndex = null
}

onMounted(() => {
  // 尝试从路由参数获取标题
  if (route.query.title) {
    meetingTitle.value = route.query.title as string
  } else {
    meetingTitle.value = formatDefaultTitle()
  }

  nextTick(() => {
    if (audioRef.value?.readyState && audioRef.value.readyState >= 1) {
      updateProgress(true)
    }
  })
})

onBeforeUnmount(() => {
  if (transcriptFollowFrame) {
    cancelAnimationFrame(transcriptFollowFrame)
    transcriptFollowFrame = 0
  }
  if (isUploadingAudio.value) {
    uploadCancelRequested.value = true
    uploadAbortController.value?.abort()
    const taskId = activeUploadTaskId.value
    if (taskId) {
      void uploadApi.cancelAudioTask(taskId).catch(() => {})
    }
  }
})

function resetUploadRecognitionWorkspace(showSetup = true) {
  store.clearTranscript()
  isUploadSetupVisible.value = showSetup
  uploadedRegistrationAudio.value = null
  uploadedRecognitionData.value = null
  activeUploadTaskId.value = ''
  uploadTaskProgress.value = 0
  uploadTaskStage.value = ''
  uploadCancelRequested.value = false
  isCancellingUpload.value = false
  uploadedSpeakerCandidates.value = []
  speakerMergeTargets.value = {}
  restoredUploadDataLoaded.value = false
  activeSeekSegmentIndex.value = null
  lastAutoScrolledSegmentIndex = null
  currentTime.value = 0
  duration.value = 0
  progressWidth.value = 0
  isPlaying.value = false

  if (audioRef.value) {
    audioRef.value.pause()
    audioRef.value.removeAttribute('src')
    audioRef.value.load()
  }
  if (store.audioUrl?.startsWith('blob:')) {
    URL.revokeObjectURL(store.audioUrl)
  }
  store.audioUrl = ''
}

const emit = defineEmits(['update:content', 'translate', 'toggle-minutes-panel', 'summary-generated'])

const industries = Object.entries(hotwordsConfig).map(([key, value]) => ({
  value: key,
  label: value.label
}))

const handleIndustryChange = () => {
  if (selectedIndustry.value) {
    const industry = hotwordsConfig[selectedIndustry.value]
    hotwordInput.value = industry.words.join('\n')
  }
}

const handleApplyHotwords = () => {
  store.hotWords = hotwordInput.value
  hotwordDialogVisible.value = false
  ElMessage.success('热词设置已应用')
}

const applyHotwordAssetsToStore = () => {
  store.hotWords = hotwordApi.toHotwordText(activeHotwordAssets.value)
}

const syncHotwordAssets = async (options: { silent?: boolean } = {}) => {
  isLoadingHotwordAssets.value = true
  hotwordAssetsError.value = ''
  try {
    const assets = await hotwordApi.listHotwords()
    hotwordAssets.value = assets
    const validCategories = new Set(assets.map(item => item.category || '通用'))
    selectedHotwordCategories.value = selectedHotwordCategories.value.filter(category => validCategories.has(category))
    applyHotwordAssetsToStore()
    hotwordAssetsLastSync.value = new Date().toLocaleString()
    if (!options.silent) {
      ElMessage.success(`已应用 ${activeHotwordAssetCount.value} 个资产热词`)
    }
  } catch (error) {
    hotwordAssetsError.value = (error as Error).message || String(error)
    if (!options.silent) {
      ElMessage.error(`热词资产同步失败：${hotwordAssetsError.value}`)
    }
  } finally {
    isLoadingHotwordAssets.value = false
  }
}

const openHotwordManager = () => {
  router.push('/hotwords')
}

const loadManualSpeakerOptions = async () => {
  manualSpeakerLoading.value = true
  try {
    const result = await listSpeakers()
    manualSpeakerOptions.value = result.speakers || []
  } catch (error) {
    manualSpeakerOptions.value = []
    ElMessage.warning(`加载已注册参会人失败，可直接输入姓名：${(error as Error).message || String(error)}`)
  } finally {
    manualSpeakerLoading.value = false
  }
}

const openManualSpeakerDialog = async () => {
  selectedManualSpeaker.value = activeManualSpeaker.value || pendingManualSpeaker.value || store.currentSpeaker || ''
  manualSpeakerDialogVisible.value = true
  await loadManualSpeakerOptions()
}

const openSpeakerSettings = () => {
  settingsPopoverVisible.value = false
  manualSpeakerDialogVisible.value = false
  router.push({
    name: 'speaker-registration',
    query: {
      from: 'record'
    }
  })
}

const applyManualSpeaker = () => {
  const speakerName = selectedManualSpeaker.value.trim()
  if (!speakerName) {
    ElMessage.warning('请输入参会人姓名')
    return
  }

  pendingManualSpeaker.value = speakerName

  if (store.isRecording && store.wsConnection?.isConnected) {
    store.wsConnection.send(JSON.stringify({
      manual_speaker_name: speakerName
    }))
    activeManualSpeaker.value = speakerName
  } else {
    activeManualSpeaker.value = ''
  }

  manualSpeakerDialogVisible.value = false
  ElMessage.success(
    store.isRecording && store.wsConnection?.isConnected
      ? `当前录音已指定参会人为“${speakerName}”`
      : `已预设参会人为“${speakerName}”，开始录音后自动生效`
  )
}

const restoreAutoSpeaker = () => {
  pendingManualSpeaker.value = ''

  if (store.wsConnection?.isConnected) {
    store.wsConnection.send(JSON.stringify({
      clear_manual_speaker: true
    }))
  }

  activeManualSpeaker.value = ''
  selectedManualSpeaker.value = ''
  manualSpeakerDialogVisible.value = false
  ElMessage.success('已恢复串口自动判断参会人')
}

// 查找所有匹配项
const findMatches = () => {
  if (!originalContent.value.trim()) {
    ElMessage.warning('请输入要查找的内容')
    return
  }
  
  matchedSegments.value = []
  totalMatches.value = 0
  currentMatchIndex.value = 0
  
  const searchText = originalContent.value
  
  // 在说话人分段中查找
  if (store.speakerSegments && store.speakerSegments.length > 0) {
    store.speakerSegments.forEach((segment, segmentIndex) => {
      let matchCount = 0
      const regex = new RegExp(searchText.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'), 'g')
      const matches = segment.text.match(regex)
      
      if (matches) {
        matchCount = matches.length
        for (let i = 0; i < matchCount; i++) {
          matchedSegments.value.push({ segmentIndex, matchIndex: i })
        }
      }
    })
  }
  
  totalMatches.value = matchedSegments.value.length
  
  if (totalMatches.value > 0) {
    highlightCurrentMatch()
    ElMessage.success(`找到 ${totalMatches.value} 处匹配`)
  } else {
    ElMessage.warning('未找到匹配内容')
  }
}

// 查找下一个
const findNext = () => {
  if (totalMatches.value === 0) {
    findMatches()
    return
  }
  
  currentMatchIndex.value = (currentMatchIndex.value + 1) % totalMatches.value
  highlightCurrentMatch()
  ElMessage.info(`${currentMatchIndex.value + 1} / ${totalMatches.value}`)
}

// 替换当前项
const replaceCurrent = () => {
  if (totalMatches.value === 0) {
    ElMessage.warning('请先查找要替换的内容')
    return
  }
  
  if (!modifiedContent.value.trim()) {
    ElMessage.warning('请输入替换内容')
    return
  }
  
  const match = matchedSegments.value[currentMatchIndex.value]
  const segment = store.speakerSegments[match.segmentIndex]
  const searchText = originalContent.value
  
  // 替换第一个匹配项
  segment.text = segment.text.replace(searchText, modifiedContent.value)
  
  // 重新查找（因为替换后位置变了）
  findMatches()
  
  ElMessage.success('替换成功')
}

// 全部替换
const replaceAll = () => {
  if (!originalContent.value.trim()) {
    ElMessage.warning('请输入原始内容')
    return
  }
  if (!modifiedContent.value.trim()) {
    ElMessage.warning('请输入修改内容')
    return
  }
  
  let replacedCount = 0
  const originalText = originalContent.value
  const modifiedText = modifiedContent.value
  
  // 在说话人分段中查找并替换
  if (store.speakerSegments && store.speakerSegments.length > 0) {
    store.speakerSegments.forEach(segment => {
      if (segment.text.includes(originalText)) {
        const regex = new RegExp(originalText.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'), 'g')
        const matches = segment.text.match(regex)
        if (matches) {
          replacedCount += matches.length
          segment.text = segment.text.replace(regex, modifiedText)
        }
      }
    })
  }
  
  // 在转录文本中查找并替换
  if (store.transcript.includes(originalText)) {
    const regex = new RegExp(originalText.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'), 'g')
    const matches = store.transcript.match(regex)
    if (matches) {
      replacedCount += matches.length
    }
    store.transcript = store.transcript.replace(regex, modifiedText)
  }
  
  // 显示结果
  if (replacedCount > 0) {
    ElMessage.success(`内容修改成功，共替换 ${replacedCount} 处`)
    clearHighlight()
    closeBatchEditDialog()
  } else {
    ElMessage.warning('在转录文本中未找到指定的原始内容')
  }
}

// 高亮当前匹配项
const highlightCurrentMatch = () => {
  // 清除之前的高亮
  clearHighlight()
  
  if (matchedSegments.value.length === 0) return
  
  const currentMatch = matchedSegments.value[currentMatchIndex.value]
  const segment = store.speakerSegments[currentMatch.segmentIndex]
  const searchText = originalContent.value
  
  // 添加高亮标记，当前项使用特殊class
  const escapedSearch = searchText.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
  let matchCount = 0
  segment.text = segment.text.replace(
    new RegExp(`(${escapedSearch})`, 'g'),
    (matchText) => {
      const className = matchCount === currentMatch.matchIndex ? 'search-highlight-current' : 'search-highlight'
      matchCount++
      return `<mark class="${className}">${matchText}</mark>`
    }
  )
  
  // 滚动到当前匹配项
  setTimeout(() => {
    const currentHighlight = document.querySelector('.search-highlight-current')
    if (currentHighlight) {
      currentHighlight.scrollIntoView({ behavior: 'smooth', block: 'center' })
    }
  }, 100)
}

// 清除高亮
const clearHighlight = () => {
  if (store.speakerSegments && store.speakerSegments.length > 0) {
    store.speakerSegments.forEach(segment => {
      // 清除所有可能的mark标签，使用更健壮的正则表达式
      if (segment.text.includes('<mark')) {
        segment.text = segment.text.replace(/<mark class="[^"]*">(.*?)<\/mark>/g, '$1')
      }
    })
  }
  console.log('🧹 已清除所有高亮标记')
}

// 关闭批量编辑对话框
const closeBatchEditDialog = () => {
  clearHighlight()
  originalContent.value = ''
  modifiedContent.value = ''
  currentMatchIndex.value = 0
  totalMatches.value = 0
  matchedSegments.value = []
  batchEditDialogVisible.value = false
}

const buttonType = computed(() => store.isRecording ? 'danger' : 'primary')
const buttonText = computed(() => store.isRecording ? '停止录音' : '开始录音')

onMounted(async () => {
  try {
    await loadBackendLLMConfig()
    await syncHotwordAssets({ silent: true })
    if (!isUploadMode.value) {
      await store.getAudioDevices()
    }
    store.asrMode = '2pass' // 设置默认选中的ASR模式
    
    // 初始化语言设置，优先从 localStorage 读取，否则使用默认中文
    const savedLanguage = localStorage.getItem('asr_language')
    if (savedLanguage && ['zh', 'auto', 'en', 'yue', 'ja', 'ko'].includes(savedLanguage)) {
      store.language = savedLanguage
    } else {
      store.language = 'zh' // 默认中文
      localStorage.setItem('asr_language', 'zh')
    }
    
    // 通知父组件初始的会议纪要面板显示状态
    emit('toggle-minutes-panel', showMinutesPanel.value)
    
    if (!isUploadMode.value) {
      ElMessage.success('音频设备加载成功')
    }
  } catch (error) {
    ElMessage.error((isUploadMode.value ? '识别配置加载失败：' : '音频设备加载失败：') + error)
  }
})

// 监听录音状态变化
watch(() => store.isRecording, (newVal) => {
  if (manualSpeakerResetTimer.value) {
    clearTimeout(manualSpeakerResetTimer.value)
    manualSpeakerResetTimer.value = null
  }

  if (newVal) {
    if (pendingManualSpeaker.value && store.wsConnection?.isConnected) {
      store.wsConnection.send(JSON.stringify({
        manual_speaker_name: pendingManualSpeaker.value
      }))
      activeManualSpeaker.value = pendingManualSpeaker.value
    } else {
      activeManualSpeaker.value = ''
    }

    manualSpeakerDialogVisible.value = false

    // 开始录音，启动计时器
    recordingDuration.value = 0
    recordingTimer.value = window.setInterval(() => {
      recordingDuration.value++
    }, 1000)
  } else if (recordingTimer.value) {
    // 停止录音，清除计时器
    clearInterval(recordingTimer.value)
    recordingTimer.value = null

    manualSpeakerResetTimer.value = window.setTimeout(() => {
      if (!store.isRecording) {
        activeManualSpeaker.value = ''
        pendingManualSpeaker.value = ''
        selectedManualSpeaker.value = ''
        manualSpeakerDialogVisible.value = false
      }
      manualSpeakerResetTimer.value = null
    }, 3200)
  }
})

const toggleRecording = () => {
  try {
    if (!store.audioSource) {
      ElMessage.warning('请先选择音频输入设备')
      return
    }

    if (store.isRecording) {
      store.stopRecording()
      if (audioCaptureMode.value === 'browser') {
        ElMessage.success('录音已停止')
      } else {
        ElMessage.success('服务器音频采集已停止')
      }
    } else {
      uploadedRegistrationAudio.value = null
      uploadedRecognitionData.value = null
      activeUploadTaskId.value = ''
      uploadTaskProgress.value = 0
      uploadTaskStage.value = ''
      uploadedSpeakerCandidates.value = []
      store.startRecording()
      if (audioCaptureMode.value === 'browser') {
        ElMessage.success('录音已开始')
      } else {
        ElMessage.success('服务器音频采集已开始')
      }
    }
  } catch (error) {
    ElMessage.error('操作失败：' + error)
  }
}

const handleClear = () => {
  resetUploadRecognitionWorkspace()
  ElMessage.success('内容已清空')
}

const handleGenerateSummary = async () => {
  // 检查转写内容是否为空（兼容说话人识别模式）
  if (actualCharCount.value === 0) {
    ElMessage.warning(isUploadMode.value ? '请先上传音视频，获取识别结果后再生成会议纪要' : '请先进行语音录制，获取转写内容后再生成会议纪要')
    return
  }
  
  try {
    await saveBackendLLMConfig()
    const options = buildCurrentSummaryOptions()
    options.onSummaryProgress = updateSummaryProgress
    const transcriptContent = getCurrentSummaryTranscript()
    
    isGeneratingSummary.value = true
    summaryStage.value = '正在提交会议纪要生成任务...'
    const summary = await generateSummary(transcriptContent, options)
    store.meetingSummary = summary
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

const openSettings = () => {
  settingsPopoverVisible.value = !settingsPopoverVisible.value
}

const handleTranslate = () => {
  // 翻译功能已隐藏，但保留代码以备将来重新启用
  translateDialogVisible.value = true
  translateInput.value = store.transcript
}

const handleProcessText = async () => {
  try {
    const processedText = await processText(store.transcript)
    store.transcript = processedText
    ElMessage.success('文本处理成功')
  } catch (error) {
    console.error('文本处理失败:', error)
    ElMessage.error(`文本处理失败：${(error as Error).message || String(error)}`)
  }
}

function formatDefaultTitle() {
  const now = new Date()
  const month = now.getMonth() + 1
  const day = now.getDate()
  return `${month}月${day}日录音`
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

const buildUploadedTranscriptFromSegments = (segments: FrontendSpeakerSegment[]) => {
  return segments
    .filter(segment => segment.text?.trim())
    .map(segment => {
      const text = segment.speaker ? `${segment.speaker}: ${segment.text}` : segment.text
      if (enableTranslation.value && segment.translation?.trim()) {
        return `${text}\n${segment.translation}`
      }
      return text
    })
    .join('\n')
}

const buildUploadedTranscript = (data: AudioRecognitionData, segments = normalizeUploadedSegments(data)) => {
  // 上传识别始终会做人声分离，声纹匹配开关只影响后台命名匹配，不影响前端说话人展示。
  if (segments.some(segment => segment.speaker)) {
    return buildUploadedTranscriptFromSegments(segments)
  }
  const text = data.plain_text || data.text || ''
  const translation = data.plain_translation || data.translation || ''
  if (enableTranslation.value && translation.trim()) {
    return text ? `${text}\n\n${translation}` : translation
  }
  return text
}

watch(enableTranslation, () => {
  if (!isUploadMode.value) return

  if (store.speakerSegments.length > 0) {
    store.transcript = buildUploadedTranscriptFromSegments(store.speakerSegments)
    return
  }

  if (uploadedRecognitionData.value) {
    store.transcript = buildUploadedTranscript(uploadedRecognitionData.value, [])
  }
})

const toUploadedMs = (value: unknown) => {
  const numberValue = Number(value)
  return Number.isFinite(numberValue) ? numberValue : undefined
}

const normalizeUploadedTimestamp = (segment: UploadedAudioSegment) => {
  const timestamp = segment.timestamp || segment.asr_timestamp
  if (Array.isArray(timestamp) && timestamp.length > 0) {
    return timestamp
  }

  const startMs = toUploadedMs(segment.startMs)
  const endMs = toUploadedMs(segment.endMs)
  if (startMs !== undefined && endMs !== undefined && endMs >= startMs) {
    return [[startMs, endMs]]
  }

  return undefined
}

const normalizeUploadedSegment = (
  segment: UploadedAudioSegment,
  registrationAudio?: UploadedAudioRegistrationRef | null,
  segmentIndex?: number
): FrontendSpeakerSegment => {
  const timestamp = normalizeUploadedTimestamp(segment)
  const startMs = toUploadedMs(segment.startMs) ?? (timestamp ? toUploadedMs(timestamp[0]?.[0]) : undefined)
  const endMs = toUploadedMs(segment.endMs) ?? (timestamp ? toUploadedMs(timestamp[timestamp.length - 1]?.[1]) : undefined)

  return {
    speaker: segment.speaker || '',
    text: segment.text || '',
    translation: segment.translation || '',
    timestamp,
    mode: segment.mode || 'uploaded-audio',
    startTime: segment.startTime,
    endTime: segment.endTime,
    startMs,
    endMs,
    registrationAudio: registrationAudio || undefined,
    segmentIndex
  }
}

const normalizeUploadedSegments = (data: AudioRecognitionData): FrontendSpeakerSegment[] => {
  return (data.segments || [])
    .map((segment, index) => normalizeUploadedSegment(segment, data.registration_audio, index))
    .filter(segment => segment.text.trim())
}

const applyUploadedRecognitionResult = (data: AudioRecognitionData, audioFile?: File) => {
  store.clearTranscript()
  isUploadSetupVisible.value = false
  uploadedRecognitionData.value = data
  const taskId = data.task_id || activeUploadTaskId.value
  activeUploadTaskId.value = taskId
  uploadedRegistrationAudio.value = data.registration_audio || null
  if (taskId) {
    store.setUploadedMediaContext(
      taskId,
      data.source_audio?.file_name || data.file_name || audioFile?.name || ''
    )
  }

  if (audioFile) {
    if (store.audioUrl?.startsWith('blob:')) {
      URL.revokeObjectURL(store.audioUrl)
    }
    store.audioUrl = URL.createObjectURL(audioFile)
  }

  const uploadedSegments = normalizeUploadedSegments(data)

  store.speakerSegments = uploadedSegments
  store.transcript = buildUploadedTranscript(data, uploadedSegments)
  activeSeekSegmentIndex.value = null

  const lastSpeakerSegment = uploadedSegments.slice().reverse().find(segment => segment.speaker)
  store.currentSpeaker = lastSpeakerSegment?.speaker || ''
  store.lastSpeaker = lastSpeakerSegment?.speaker || ''

  currentTime.value = 0
  progressWidth.value = 0
  isPlaying.value = false
}

const setRestoredAudioSource = (audioUrl: string) => {
  if (store.audioUrl?.startsWith('blob:') && store.audioUrl !== audioUrl) {
    URL.revokeObjectURL(store.audioUrl)
  }
  store.audioUrl = audioUrl
  currentTime.value = 0
  progressWidth.value = 0
  isPlaying.value = false
  nextTick(() => updateProgress(true))
}

const buildRestoredAudioRecognitionData = (data: UploadedMeetingTranscription): AudioRecognitionData => {
  const taskId = data.task_id || data.task_ids?.[0] || ''
  const fileName = data.file_names?.[0] || props.currentFileName || '上传识别结果'
  const segments: UploadedAudioSegment[] = (data.segments || []).map(segment => ({
    speaker: segment.speaker || '',
    speaker_type: segment.speaker_type,
    speaker_confidence: segment.speaker_confidence,
    text: segment.text || '',
    translation: segment.translation || '',
    mode: segment.mode || 'uploaded-audio',
    timestamp: segment.timestamp || undefined,
    startTime: segment.startTime,
    endTime: segment.endTime,
    startMs: segment.startMs,
    endMs: segment.endMs
  }))

  return {
    task_id: taskId || undefined,
    file_name: fileName,
    mode: 'uploaded-audio',
    text: data.text || data.plain_text || '',
    plain_text: data.plain_text || data.text || '',
    language: store.language || 'zh',
    segments
  }
}

const applyRestoredTranscriptionFallback = () => {
  if (!isUploadMode.value || !props.restoredMeetingId || restoredUploadDataLoaded.value) return
  const fallbackText = props.restoredTranscriptionText?.trim()
  if (!fallbackText) return

  store.clearTranscript()
  uploadedRecognitionData.value = null
  activeUploadTaskId.value = ''
  uploadedRegistrationAudio.value = null
  store.transcript = fallbackText
  isUploadSetupVisible.value = false
  setRestoredAudioSource(props.restoredAudioUrl || '')
  restoredUploadDataLoaded.value = true
}

const loadRestoredUploadedMeeting = async (meetingId: number | null) => {
  if (!isUploadMode.value || !meetingId) return

  isLoadingRestoredUpload.value = true
  restoredUploadDataLoaded.value = false
  uploadTaskStage.value = '正在加载历史上传识别结果...'

  try {
    const response = await meetingApi.getMeetingUploadedTranscription(meetingId)
    if (!response.success || !response.data) {
      throw new Error(response.error || '上传识别回显加载失败')
    }

    const restoredData = buildRestoredAudioRecognitionData(response.data)
    if ((restoredData.segments?.length || 0) > 0 || restoredData.text.trim() || restoredData.plain_text.trim()) {
      applyUploadedRecognitionResult(restoredData)
      isUploadSetupVisible.value = false
      uploadTaskProgress.value = 100
      uploadTaskStage.value = ''
      setRestoredAudioSource(props.restoredAudioUrl || '')
      restoredUploadDataLoaded.value = true
      return
    }

    applyRestoredTranscriptionFallback()
  } catch (error) {
    console.warn('加载历史上传识别结果失败，尝试使用转录文档兜底:', error)
    applyRestoredTranscriptionFallback()
  } finally {
    isLoadingRestoredUpload.value = false
    uploadTaskStage.value = ''
  }
}

watch(() => props.restoredMeetingId, (meetingId) => {
  if (!meetingId) {
    if (isUploadMode.value) {
      resetUploadRecognitionWorkspace()
    } else {
      restoredUploadDataLoaded.value = false
    }
    return
  }
  void loadRestoredUploadedMeeting(meetingId)
}, { immediate: true })

watch(() => props.recognitionMode, () => {
  if (!isUploadMode.value) {
    restoredUploadDataLoaded.value = false
    return
  }
  if (props.restoredMeetingId) {
    void loadRestoredUploadedMeeting(props.restoredMeetingId)
    return
  }
  resetUploadRecognitionWorkspace()
})

watch(() => route.fullPath, () => {
  if (!isUploadMode.value || props.restoredMeetingId) return
  resetUploadRecognitionWorkspace()
})

watch(() => props.restoredAudioUrl, (audioUrl) => {
  if (!isUploadMode.value || !props.restoredMeetingId) return
  setRestoredAudioSource(audioUrl || '')
})

watch(() => props.restoredTranscriptionText, () => {
  applyRestoredTranscriptionFallback()
})

const updateUploadTaskProgress = (task: AudioRecognitionTask) => {
  activeUploadTaskId.value = task.task_id
  uploadTaskProgress.value = task.progress || 0
  if (task.status === 'queued' && task.queue_position) {
    uploadTaskStage.value = task.queue_position > 1
      ? `排队中，前面还有 ${task.queue_position - 1} 个任务`
      : '排队中，等待开始识别'
  } else {
    uploadTaskStage.value = formatUploadTaskStage(task.stage)
  }
}

const resetCancelledUploadState = () => {
  activeUploadTaskId.value = ''
  uploadTaskProgress.value = 0
  uploadTaskStage.value = ''
  isUploadSetupVisible.value = true
}

const cancelActiveUploadTask = async () => {
  if (!isUploadingAudio.value || isCancellingUpload.value) return

  uploadCancelRequested.value = true
  uploadTaskStage.value = '正在取消上传识别...'
  uploadAbortController.value?.abort()

  const taskId = activeUploadTaskId.value
  if (!taskId) return

  isCancellingUpload.value = true
  try {
    const task = await uploadApi.cancelAudioTask(taskId)
    updateUploadTaskProgress(task)
    resetCancelledUploadState()
  } catch (error) {
    ElMessage.warning(`取消上传识别失败：${(error as Error).message || String(error)}`)
  } finally {
    isCancellingUpload.value = false
  }
}

const parseExpectedUploadSpeakers = () => {
  const numbers = (expectedUploadSpeakers.value.match(/\d+/g) || [])
    .map(value => Number(value))
    .filter(value => Number.isFinite(value) && value >= 2 && value <= 50)

  if (numbers.length === 1) {
    return {
      expectedSpeakers: numbers[0],
      minSpeakers: null,
      maxSpeakers: null
    }
  }

  if (numbers.length >= 2) {
    const minSpeakers = Math.min(numbers[0], numbers[1])
    const maxSpeakers = Math.max(numbers[0], numbers[1])
    return {
      expectedSpeakers: null,
      minSpeakers,
      maxSpeakers
    }
  }

  return {
    expectedSpeakers: null,
    minSpeakers: null,
    maxSpeakers: null
  }
}

const triggerAudioUpload = () => {
  if (store.isRecording) {
    ElMessage.warning('请先停止录音，再上传音频文件识别')
    return
  }
  audioUploadInputRef.value?.click()
}

const restoreUploadWorkspace = () => {
  isUploadSetupVisible.value = true
}

const handleAudioUploadChange = async (event: Event) => {
  const input = event.target as HTMLInputElement
  const audioFile = input.files?.[0]
  if (!audioFile) return

  resetUploadRecognitionWorkspace(false)
  isUploadingAudio.value = true
  uploadCancelRequested.value = false
  isCancellingUpload.value = false
  uploadTaskProgress.value = 0
  uploadTaskStage.value = '正在上传音频并识别...'
  uploadAbortController.value = new AbortController()

  try {
    const speakerBounds = parseExpectedUploadSpeakers()
    const result = await uploadApi.recognizeAudio(audioFile, {
      language: store.language,
      enableSpeakerDiarization: true,
      enableVoiceprintMatching: enableUploadedVoiceprintMatching.value,
      enableTranslation: enableTranslation.value,
      speakerTopK: 3,
      expectedSpeakers: speakerBounds.expectedSpeakers,
      minSpeakers: speakerBounds.minSpeakers,
      maxSpeakers: speakerBounds.maxSpeakers,
      hotwords: store.hotWords,
      includeDefaultHotwords: hotwordAssets.value.length > 0 ? false : undefined,
      signal: uploadAbortController.value.signal,
      onTaskProgress: (task) => {
        updateUploadTaskProgress(task)
      }
    })

    if (uploadCancelRequested.value || result.task?.status === 'cancelled') {
      resetCancelledUploadState()
      ElMessage.info('已取消上传识别')
      return
    }

    if (!result.success || !result.data) {
      throw new Error(result.error || '上传音频识别失败')
    }

    applyUploadedRecognitionResult(result.data, audioFile)
    if (result.task) {
      updateUploadTaskProgress(result.task)
    }
    ElMessage.success('上传音频识别完成')
  } catch (error) {
    if (uploadCancelRequested.value || ((error as Error).name === 'AbortError')) {
      resetCancelledUploadState()
      ElMessage.info('已取消上传识别')
      return
    }
    console.error('上传音频识别失败:', error)
    ElMessage.error(`上传音频识别失败：${(error as Error).message || String(error)}`)
    if (actualCharCount.value === 0 && !store.audioUrl) {
      isUploadSetupVisible.value = true
    }
  } finally {
    isUploadingAudio.value = false
    uploadAbortController.value = null
    uploadCancelRequested.value = false
    isCancellingUpload.value = false
    uploadTaskStage.value = ''
    input.value = ''
  }
}

const loadUploadedSpeakerCandidates = async () => {
  if (!activeUploadTaskId.value) {
    ElMessage.warning('请先完成一次上传识别')
    return
  }
  speakerReviewLoading.value = true
  try {
    uploadedSpeakerCandidates.value = await uploadApi.fetchSpeakerCandidates(activeUploadTaskId.value)
    speakerMergeTargets.value = Object.fromEntries(
      uploadedSpeakerCandidates.value.map(candidate => {
        const target = uploadedSpeakerCandidates.value.find(item => item.speaker !== candidate.speaker)?.speaker || ''
        return [candidate.speaker, target]
      })
    )
  } catch (error) {
    console.error('加载上传识别说话人候选失败:', error)
    ElMessage.error(`加载说话人候选失败：${(error as Error).message || String(error)}`)
  } finally {
    speakerReviewLoading.value = false
  }
}

const openSpeakerReviewDialog = async () => {
  speakerReviewDialogVisible.value = true
  await loadUploadedSpeakerCandidates()
}

const playUploadedSpeakerSample = (sample: UploadedSpeakerSample) => {
  if (uploadedSegmentAudio) {
    uploadedSegmentAudio.pause()
  }
  uploadedSegmentAudio = new Audio(uploadApi.segmentAudioUrl(sample))
  uploadedSegmentAudio.play().catch(error => {
    console.error('试听上传片段失败:', error)
    ElMessage.error('试听失败')
  })
}

const uploadedSampleQualityLabel = (quality?: UploadedSpeakerSample['quality']) => {
  if (quality === 'good') return '推荐'
  if (quality === 'usable') return '可用'
  if (quality === 'short') return '偏短'
  return ''
}

const uploadedSampleQualityTagType = (quality?: UploadedSpeakerSample['quality']) => {
  if (quality === 'good') return 'success'
  if (quality === 'usable') return 'warning'
  return 'info'
}

const findRegisteredSpeakerByName = async (speakerName: string): Promise<SpeakerInfo | null> => {
  try {
    const response = await listSpeakers()
    return response.speakers.find(speaker => speaker.speaker_name === speakerName) || null
  } catch (error) {
    console.warn('查询已注册说话人失败，将按未注册处理:', error)
    return null
  }
}

const resolveSpeakerRegistrationDecision = async (speakerName: string) => {
  const registeredSpeaker = await findRegisteredSpeakerByName(speakerName)
  if (!registeredSpeaker) {
    return {
      registeredSpeaker: null,
      shouldRegister: true,
      overwrite: false,
      canceled: false
    }
  }

  try {
    await ElMessageBox.confirm(
      `“${speakerName}” 已经有声纹。请选择使用已有声纹，或用当前片段更新该声纹样本。`,
      '声纹已存在',
      {
        confirmButtonText: '更新声纹',
        cancelButtonText: '使用已有',
        distinguishCancelAndClose: true,
        type: 'warning'
      }
    )
    return {
      registeredSpeaker,
      shouldRegister: true,
      overwrite: true,
      canceled: false
    }
  } catch (action) {
    if (action === 'cancel') {
      return {
        registeredSpeaker,
        shouldRegister: false,
        overwrite: false,
        canceled: false
      }
    }
    return {
      registeredSpeaker,
      shouldRegister: false,
      overwrite: false,
      canceled: true
    }
  }
}

const renameUploadedSpeakerCandidate = async (candidate: UploadedSpeakerCandidate) => {
  if (!activeUploadTaskId.value) return
  try {
    const { value } = await ElMessageBox.prompt('请输入新的说话人名字', '修改上传识别说话人', {
      confirmButtonText: '保存',
      cancelButtonText: '取消',
      inputValue: candidate.display_name || candidate.speaker,
      inputPattern: /^.+$/,
      inputErrorMessage: '名字不能为空'
    })
    const result = await uploadApi.renameUploadedSpeaker(activeUploadTaskId.value, candidate.speaker, value)
    applyUploadedRecognitionResult(result)
    await loadUploadedSpeakerCandidates()
    ElMessage.success('说话人已更名')
  } catch (error) {
    if (error === 'cancel') return
    console.error('上传识别说话人更名失败:', error)
    ElMessage.error(`更名失败：${(error as Error).message || String(error)}`)
  }
}

const mergeUploadedSpeakerCandidate = async (candidate: UploadedSpeakerCandidate) => {
  if (!activeUploadTaskId.value) return
  const target = speakerMergeTargets.value[candidate.speaker]
  if (!target || target === candidate.speaker) {
    ElMessage.warning('请选择要合并到的说话人')
    return
  }
  try {
    const result = await uploadApi.mergeUploadedSpeakers(activeUploadTaskId.value, candidate.speaker, target)
    applyUploadedRecognitionResult(result)
    await loadUploadedSpeakerCandidates()
    ElMessage.success(`已合并到 ${target}`)
  } catch (error) {
    console.error('上传识别说话人合并失败:', error)
    ElMessage.error(`合并失败：${(error as Error).message || String(error)}`)
  }
}

const registerUploadedSpeakerCandidate = async (candidate: UploadedSpeakerCandidate) => {
  try {
    const { value } = await ElMessageBox.prompt('请输入要注册的参会人名字', '注册说话人声纹', {
      confirmButtonText: '注册',
      cancelButtonText: '取消',
      inputValue: candidate.display_name || candidate.speaker,
      inputPattern: /^.+$/,
      inputErrorMessage: '名字不能为空'
    })
    const targetSpeakerName = value.trim()
    const decision = await resolveSpeakerRegistrationDecision(targetSpeakerName)
    if (decision.canceled) return

    const segments = candidate.sample_segments
      .filter(sample => sample.start_ms !== undefined && sample.end_ms !== undefined)
      .map(sample => ({
        start_ms: sample.start_ms as number,
        end_ms: sample.end_ms as number
      }))

    if (decision.shouldRegister) {
      if (!uploadedRegistrationAudio.value) {
        ElMessage.warning('缺少上传识别音频引用，请重新上传识别后再注册')
        return
      }

      await registerSpeakerFromUploadedSegment({
        speaker_name: targetSpeakerName,
        description: `从上传识别候选片段注册 (${candidate.segment_count} 段)`,
        overwrite: decision.overwrite,
        registration_audio: uploadedRegistrationAudio.value,
        segments,
        max_duration_ms: 15000
      })
    }

    if (activeUploadTaskId.value && targetSpeakerName !== candidate.speaker) {
      const result = await uploadApi.renameUploadedSpeaker(activeUploadTaskId.value, candidate.speaker, targetSpeakerName)
      applyUploadedRecognitionResult(result)
    }
    await loadUploadedSpeakerCandidates()
    if (decision.shouldRegister) {
      ElMessage.success(decision.overwrite ? `已更新 ${targetSpeakerName} 的声纹` : `已注册 ${targetSpeakerName} 的声纹`)
    } else {
      ElMessage.success(`已使用已注册声纹 ${targetSpeakerName}`)
    }
  } catch (error) {
    if (error === 'cancel') return
    console.error('上传识别候选声纹注册失败:', error)
    ElMessage.error(`注册失败：${(error as Error).message || String(error)}`)
  }
}

// 文件保存和上传的代码 - 使用传入的文件名
const handleDownloadAudio = () => {
  if (!store.audioUrl) return
  
  // 创建下载链接
  const link = document.createElement('a')
  link.href = store.audioUrl
  link.download = `${props.currentFileName || 'recording'}.wav`
  
  // 触发下载
  document.body.appendChild(link)
  link.click()
  
  // 清理
  document.body.removeChild(link)
  
  ElMessage.success('音频文件保存成功')
}

// 说话人样式相关方法
const speakerColors = ['#409eff', '#67c23a', '#e6a23c', '#f56c6c', '#909399', '#c71585', '#ff6347', '#32cd32']

const getSpeakerClass = (speaker: string, index: number) => {
  if (!speaker) return 'empty-speaker-segment'
  const speakerIndex = getSpeakerIndex(speaker)
  return `speaker-${speakerIndex % speakerColors.length}`
}

const getSpeakerAvatarClass = (speaker: string) => {
  if (!speaker) return 'empty'
  const speakerIndex = getSpeakerIndex(speaker)
  return `speaker-avatar-${speakerIndex % speakerColors.length}`
}

// 格式化时间范围显示
const getSegmentTimeLabel = (segment: any) => {
  // 优先使用后端返回的格式化时间
  if (segment.startTime && segment.endTime) {
    return `${segment.startTime} - ${segment.endTime}`
  }
  
  // 备用：从 timestamp 数组计算
  if (segment.timestamp && Array.isArray(segment.timestamp) && segment.timestamp.length > 0) {
    const startMs = segment.timestamp[0][0]
    const endMs = segment.timestamp[segment.timestamp.length - 1][1]
    const formatMs = (ms: number) => {
      const totalSeconds = Math.floor(ms / 1000)
      const hours = Math.floor(totalSeconds / 3600)
      const minutes = Math.floor((totalSeconds % 3600) / 60)
      const seconds = totalSeconds % 60
      return `${hours.toString().padStart(2, '0')}:${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}`
    }
    return `${formatMs(startMs)} - ${formatMs(endMs)}`
  }
  
  if (typeof segment.timestamp === 'string' && segment.timestamp.trim() && segment.timestamp !== 'undefined') {
    return segment.timestamp
  }

  return ''
}

const formatTimeRange = (segment: any) => {
  return getSegmentTimeLabel(segment) || '00:00'
}

const parseTimeStringToMs = (time?: string) => {
  if (!time) return undefined
  const parts = time.split(':').map(part => parseInt(part, 10))
  if (parts.length !== 3 || parts.some(part => Number.isNaN(part))) {
    return undefined
  }
  const [hours, minutes, seconds] = parts
  return (hours * 3600 + minutes * 60 + seconds) * 1000
}

const getSegmentStartMs = (segment: any) => {
  if (segment.startMs !== undefined && segment.startMs !== null) {
    return Number(segment.startMs)
  }
  if (segment.timestamp && Array.isArray(segment.timestamp) && segment.timestamp.length > 0) {
    return Number(segment.timestamp[0][0])
  }
  return parseTimeStringToMs(segment.startTime)
}

const canSeekToSegment = (segment: any) => {
  const startMs = getSegmentStartMs(segment)
  return typeof startMs === 'number' && Number.isFinite(startMs)
}

const getSegmentEndMs = (segment: any) => {
  if (segment.endMs !== undefined && segment.endMs !== null) {
    return Number(segment.endMs)
  }
  if (segment.timestamp && Array.isArray(segment.timestamp) && segment.timestamp.length > 0) {
    return Number(segment.timestamp[segment.timestamp.length - 1][1])
  }
  return parseTimeStringToMs(segment.endTime)
}

const buildDisplaySpeakerGroup = (
  segments: FrontendSpeakerSegment[],
  groupIndex: number
): FrontendSpeakerSegmentGroup => {
  const first = segments[0]
  const startValues = segments
    .map(segment => getSegmentStartMs(segment))
    .filter((value): value is number => typeof value === 'number' && Number.isFinite(value))
  const endValues = segments
    .map(segment => getSegmentEndMs(segment))
    .filter((value): value is number => typeof value === 'number' && Number.isFinite(value))
  const startMs = startValues.length ? Math.min(...startValues) : undefined
  const endMs = endValues.length ? Math.max(...endValues) : undefined

  return {
    speaker: first.speaker,
    text: segments.map(segment => segment.text || '').join(''),
    translation: segments.map(segment => segment.translation || '').filter(Boolean).join(' '),
    timestamp: startMs !== undefined && endMs !== undefined && endMs > startMs ? [[startMs, endMs]] : undefined,
    mode: first.mode,
    startMs,
    endMs,
    registrationAudio: first.registrationAudio,
    segments,
    groupIndex
  }
}

const displaySpeakerGroups = computed<FrontendSpeakerSegmentGroup[]>(() => {
  const groups: FrontendSpeakerSegment[][] = []
  for (const segment of store.speakerSegments) {
    const lastGroup = groups[groups.length - 1]
    const lastSegment = lastGroup?.[lastGroup.length - 1]
    if (lastGroup && (lastSegment?.speaker || '') === (segment.speaker || '')) {
      lastGroup.push(segment)
    } else {
      groups.push([segment])
    }
  }
  return groups.map((segments, index) => buildDisplaySpeakerGroup(segments, index))
})

const getSegmentDisplayIndex = (segment: FrontendSpeakerSegment) => {
  if (typeof segment.segmentIndex === 'number') {
    return segment.segmentIndex
  }
  const index = store.speakerSegments.indexOf(segment)
  return index >= 0 ? index : null
}

const isActiveSpeakerSegment = (segment: FrontendSpeakerSegment) => {
  const index = getSegmentDisplayIndex(segment)
  return index !== null && activeSeekSegmentIndex.value === index
}

const findActiveSegmentIndexAtTime = (timeSeconds: number) => {
  const currentMs = Math.max(0, timeSeconds * 1000)

  for (let index = 0; index < store.speakerSegments.length; index++) {
    const segment = store.speakerSegments[index]
    const startMs = getSegmentStartMs(segment)
    if (typeof startMs !== 'number' || !Number.isFinite(startMs)) continue

    const rawEndMs = getSegmentEndMs(segment)
    let endMs = typeof rawEndMs === 'number' && Number.isFinite(rawEndMs) && rawEndMs > startMs
      ? rawEndMs
      : undefined

    if (endMs === undefined) {
      const nextTimedSegment = store.speakerSegments.slice(index + 1).find(item => {
        const nextStartMs = getSegmentStartMs(item)
        return typeof nextStartMs === 'number' && Number.isFinite(nextStartMs) && nextStartMs > startMs
      })
      const nextStartMs = nextTimedSegment ? getSegmentStartMs(nextTimedSegment) : undefined
      endMs = typeof nextStartMs === 'number' && Number.isFinite(nextStartMs)
        ? nextStartMs
        : startMs + 1000
    }

    if (currentMs >= startMs && currentMs <= endMs) {
      return getSegmentDisplayIndex(segment)
    }
  }

  return null
}

const scrollActiveSegmentIntoView = (segmentIndex: number, forceScroll = false) => {
  if (transcriptFollowFrame) {
    cancelAnimationFrame(transcriptFollowFrame)
  }

  transcriptFollowFrame = requestAnimationFrame(() => {
    transcriptFollowFrame = 0

    const root = transcriptContentRef.value
    if (!root) return

    const selector = `[data-segment-index="${segmentIndex}"]`
    const target = (
      root.querySelector<HTMLElement>(`.message-part${selector}`) ||
      root.querySelector<HTMLElement>(`.translation-part${selector}`) ||
      root.querySelector<HTMLElement>(`.speaker-segment${selector}`)
    )
    if (!target) return

    const scrollContainer = target.closest('.speaker-segments') as HTMLElement | null
    if (!scrollContainer) return

    const containerRect = scrollContainer.getBoundingClientRect()
    const targetRect = target.getBoundingClientRect()
    const comfortablePadding = Math.min(120, containerRect.height * 0.24)
    const isComfortablyVisible =
      targetRect.top >= containerRect.top + comfortablePadding &&
      targetRect.bottom <= containerRect.bottom - comfortablePadding

    if (!forceScroll && isComfortablyVisible) return

    const nextTop = scrollContainer.scrollTop +
      targetRect.top -
      containerRect.top -
      (containerRect.height / 2) +
      (targetRect.height / 2)
    const prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches

    scrollContainer.scrollTo({
      top: Math.max(0, nextTop),
      behavior: prefersReducedMotion ? 'auto' : 'smooth'
    })
  })
}

const syncActiveSegmentWithPlayback = (options: { forceScroll?: boolean } = {}) => {
  if (!shouldShowSpeakerSegments.value || store.speakerSegments.length === 0) {
    activeSeekSegmentIndex.value = null
    lastAutoScrolledSegmentIndex = null
    return
  }

  const nextIndex = findActiveSegmentIndexAtTime(currentTime.value)
  const changedSegment = nextIndex !== activeSeekSegmentIndex.value
  activeSeekSegmentIndex.value = nextIndex

  if (nextIndex === null) {
    lastAutoScrolledSegmentIndex = null
    return
  }

  const shouldFollow =
    options.forceScroll ||
    (isPlaying.value && (changedSegment || lastAutoScrolledSegmentIndex !== nextIndex))

  if (shouldFollow) {
    scrollActiveSegmentIntoView(nextIndex, Boolean(options.forceScroll))
    lastAutoScrolledSegmentIndex = nextIndex
  }
}

const getSpeakerIndex = (speaker: string) => {
  // 根据说话人名称生成一个稳定的索引
  let hash = 0
  for (let i = 0; i < speaker.length; i++) {
    const char = speaker.charCodeAt(i)
    hash = ((hash << 5) - hash) + char
    hash = hash & hash // 转换为32位整数
  }
  return Math.abs(hash)
}

// 检查是否所有说话人都为空
const hasValidSpeakers = computed(() => {
  return store.speakerSegments.some(segment => segment.speaker && segment.speaker.trim() !== '')
})

const shouldShowSpeakerSegments = computed(() => {
  if (store.speakerSegments.length === 0 || !hasValidSpeakers.value) {
    return false
  }
  return isUploadMode.value || enableSpeakerDiarization.value
})

// 计算实际字符数（兼容说话人识别模式和普通模式）
const actualCharCount = computed(() => {
  // 如果启用了说话人识别且有分段内容，统计所有分段的文本长度
  if (shouldShowSpeakerSegments.value) {
    return store.speakerSegments.reduce((total, segment) => {
      // 移除HTML标签（如高亮标记）来计算真实文本长度
      const textWithoutTags = segment.text.replace(/<[^>]*>/g, '')
      return total + textWithoutTags.length
    }, 0)
  }
  // 否则使用transcript的长度
  return store.transcript.length
})

const hasUploadResult = computed(() => {
  return isUploadMode.value && (
    actualCharCount.value > 0 ||
    Boolean(activeUploadTaskId.value) ||
    Boolean(store.audioUrl)
  )
})

const showUploadWorkspace = computed(() => {
  return isUploadMode.value && isUploadSetupVisible.value && !isUploadingAudio.value
})

const uploadWorkspaceStatusText = computed(() => {
  if (actualCharCount.value > 0) return '已有内容'
  return '等待上传'
})

const uploadWorkspaceStatusType = computed(() => {
  return actualCharCount.value > 0 ? 'success' : 'info'
})

const uploadActionText = computed(() => {
  if (isUploadingAudio.value) return uploadTaskStage.value || '上传识别中'
  return hasUploadResult.value ? '重新上传' : '上传音视频识别'
})

const uploadActionTitle = computed(() => {
  return hasUploadResult.value
    ? '重新选择本地音视频文件进行识别'
    : '上传本地音视频文件进行语音识别和声纹说话人识别'
})

// 点击时间标签，跳转到音频对应位置
const seekToTimestamp = (segment: any) => {
  if (!audioRef.value || !store.audioUrl) {
    ElMessage.warning('请先停止录音以生成音频文件')
    return
  }
  
  const startTimeMs = getSegmentStartMs(segment)
  if (typeof startTimeMs !== 'number' || !Number.isFinite(startTimeMs)) {
    ElMessage.warning('该段没有可跳转的时间戳')
    return
  }
  
  // 将毫秒转换为秒
  const startTimeSeconds = startTimeMs / 1000
  
  // 设置音频播放位置
  audioRef.value.currentTime = startTimeSeconds
  activeSeekSegmentIndex.value = getSegmentDisplayIndex(segment)
  updateProgress(true)
  
  // 如果音频未在播放，开始播放
  if (!isPlaying.value) {
    audioRef.value.play().catch(error => {
      console.error('音频播放失败:', error)
      ElMessage.error('音频播放失败，请稍后重试')
    })
  }
  
  ElMessage.success(`已跳转到 ${getSegmentTimeLabel(segment).split(' - ')[0]}`)
}

// 截取音频片段（从指定时间开始截取指定秒数）
const extractAudioSegment = async (startTimeMs: number, durationSeconds: number = 15): Promise<Blob> => {
  if (!audioRef.value || !store.audioUrl) {
    throw new Error('音频未加载')
  }

  // 获取音频数据
  const audioContext = new AudioContext({ sampleRate: 16000 })
  const response = await fetch(store.audioUrl)
  const arrayBuffer = await response.arrayBuffer()
  const audioBuffer = await audioContext.decodeAudioData(arrayBuffer)

  // 计算截取位置
  const startTimeSec = startTimeMs / 1000
  const sampleRate = audioBuffer.sampleRate
  const startSample = Math.floor(startTimeSec * sampleRate)
  const durationSamples = Math.floor(durationSeconds * sampleRate)
  const endSample = Math.min(startSample + durationSamples, audioBuffer.length)
  
  // 创建新的AudioBuffer用于截取的音频
  const channels = audioBuffer.numberOfChannels
  const newBuffer = audioContext.createBuffer(channels, endSample - startSample, sampleRate)
  
  // 复制音频数据
  for (let channel = 0; channel < channels; channel++) {
    const oldData = audioBuffer.getChannelData(channel)
    const newData = newBuffer.getChannelData(channel)
    for (let i = 0; i < newBuffer.length; i++) {
      newData[i] = oldData[startSample + i]
    }
  }
  
  // 将AudioBuffer转换为WAV格式的Blob
  const wavBlob = await audioBufferToWav(newBuffer)
  await audioContext.close()
  
  return wavBlob
}

// 将AudioBuffer转换为WAV格式的Blob
const audioBufferToWav = (buffer: AudioBuffer): Promise<Blob> => {
  return new Promise((resolve) => {
    const length = buffer.length * buffer.numberOfChannels * 2
    const arrayBuffer = new ArrayBuffer(44 + length)
    const view = new DataView(arrayBuffer)
    
    // WAV文件头
    const writeString = (offset: number, string: string) => {
      for (let i = 0; i < string.length; i++) {
        view.setUint8(offset + i, string.charCodeAt(i))
      }
    }
    
    const sampleRate = buffer.sampleRate
    const numChannels = buffer.numberOfChannels
    
    // RIFF标识符
    writeString(0, 'RIFF')
    view.setUint32(4, 36 + length, true)
    writeString(8, 'WAVE')
    
    // fmt子块
    writeString(12, 'fmt ')
    view.setUint32(16, 16, true) // fmt chunk size
    view.setUint16(20, 1, true) // audio format (PCM)
    view.setUint16(22, numChannels, true)
    view.setUint32(24, sampleRate, true)
    view.setUint32(28, sampleRate * numChannels * 2, true) // byte rate
    view.setUint16(32, numChannels * 2, true) // block align
    view.setUint16(34, 16, true) // bits per sample
    
    // data子块
    writeString(36, 'data')
    view.setUint32(40, length, true)
    
    // 写入音频数据
    const offset = 44
    const channels: Float32Array[] = []
    for (let i = 0; i < numChannels; i++) {
      channels.push(buffer.getChannelData(i))
    }
    
    let pos = 0
    for (let i = 0; i < buffer.length; i++) {
      for (let channel = 0; channel < numChannels; channel++) {
        const sample = Math.max(-1, Math.min(1, channels[channel][i]))
        view.setInt16(offset + pos, sample < 0 ? sample * 0x8000 : sample * 0x7FFF, true)
        pos += 2
      }
    }
    
    resolve(new Blob([arrayBuffer], { type: 'audio/wav' }))
  })
}

// 点击说话人名字，弹出修改对话框并注册
const handleSpeakerNameClick = async (segment: any, index: number) => {
  const oldSpeakerName = segment.speaker || `说话人${index + 1}`
  
  // 弹出输入框
  ElMessageBox.prompt('请输入新的说话人名字', '修改说话人', {
    confirmButtonText: '注册并修改',
    cancelButtonText: '取消',
    inputValue: oldSpeakerName,
    inputPattern: /^.+$/,
    inputErrorMessage: '名字不能为空'
  }).then(async ({ value: newSpeakerName }) => {
    const targetSpeakerName = String(newSpeakerName || '').trim()
    if (!targetSpeakerName || targetSpeakerName === oldSpeakerName) {
      return
    }

    const decision = await resolveSpeakerRegistrationDecision(targetSpeakerName)
    if (decision.canceled) {
      return
    }
    
    const loading = ElLoading.service({
      lock: true,
      text: decision.shouldRegister ? '正在按时间戳截取音频并注册说话人...' : '正在使用已有声纹更新说话人...',
      background: 'rgba(0, 0, 0, 0.7)'
    })
    
    try {
      const startTimeMs = getSegmentStartMs(segment)
      const endTimeMs = getSegmentEndMs(segment)
      const currentRange = (
        typeof startTimeMs === 'number' &&
        typeof endTimeMs === 'number' &&
        Number.isFinite(startTimeMs) &&
        Number.isFinite(endTimeMs) &&
        endTimeMs > startTimeMs
      ) ? [{ start_ms: startTimeMs, end_ms: endTimeMs }] : []
      const registrationAudio = segment.registrationAudio || (segment.mode === 'uploaded-audio' ? uploadedRegistrationAudio.value : null)
      const description = `从录音中自动注册 (${getSegmentTimeLabel(segment).split(' - ')[0] || '无时间戳'})`

      if (decision.shouldRegister) {
        if (registrationAudio?.file_name || registrationAudio?.source_file_name) {
          if (currentRange.length === 0) {
            throw new Error('当前片段没有有效时间戳，请重新上传识别后再注册说话人')
          }

          await registerSpeakerFromUploadedSegment({
            speaker_name: targetSpeakerName,
            description,
            overwrite: decision.overwrite,
            registration_audio: registrationAudio,
            segments: currentRange,
            start_ms: currentRange[0].start_ms,
            end_ms: currentRange[0].end_ms,
            duration_ms: 15000
          })
        } else {
          if (!audioRef.value || !store.audioUrl) {
            throw new Error('请先停止录音以生成音频文件后再注册说话人')
          }

          // 实时录音没有后端转码基准，保留浏览器本地截取作为兜底。
          const audioBlob = await extractAudioSegment(startTimeMs || 0, 15)
          const audioBase64 = await blobToBase64(audioBlob)

          await registerSpeaker({
            speaker_name: targetSpeakerName,
            description,
            overwrite: decision.overwrite,
            audio_data: audioBase64
          })
        }
      }
      
      if (activeUploadTaskId.value && segment.mode === 'uploaded-audio') {
        const result = await uploadApi.renameUploadedSegmentSpeaker(activeUploadTaskId.value, index, targetSpeakerName)
        applyUploadedRecognitionResult(result)
      } else {
        segment.speaker = targetSpeakerName
      }
      
      loading.close()
      if (decision.shouldRegister) {
        ElMessage.success(
          decision.overwrite
            ? `说话人 "${oldSpeakerName}" 已更名，并更新 "${targetSpeakerName}" 的声纹`
            : `说话人 "${oldSpeakerName}" 已成功注册并更名为 "${targetSpeakerName}"`
        )
      } else {
        ElMessage.success(`说话人 "${oldSpeakerName}" 已更名，并使用已有声纹 "${targetSpeakerName}"`)
      }
      
    } catch (error) {
      loading.close()
      console.error('注册说话人失败:', error)
      ElMessage.error(`注册失败：${(error as Error).message || String(error)}`)
    }
  }).catch(() => {
    // 用户取消
  })
}

</script>

<template>
  <div class="asr-panel">
    <div v-if="isUploadMode && isUploadingAudio" class="upload-task-modal" role="dialog" aria-modal="true">
      <div class="upload-task-panel">
        <div class="upload-task-spinner"></div>
        <div class="upload-task-title">{{ uploadTaskStage || '上传识别中' }}</div>
        <el-progress
          class="upload-task-progress"
          :percentage="Math.max(0, Math.min(100, uploadTaskProgress))"
          :show-text="false"
        />
        <el-button
          size="small"
          type="danger"
          plain
          :loading="isCancellingUpload"
          @click="cancelActiveUploadTask"
        >
          取消并舍弃
        </el-button>
      </div>
    </div>


    <div class="transcript-panel">
      <div class="transcript-header">
        <span class="transcript-title">{{ transcriptTitle }}</span>
        <div class="transcript-stats">
          <el-tag v-if="!isUploadMode && activeManualSpeaker" size="small" type="warning">手动参会人: {{ activeManualSpeaker }}</el-tag>
          <el-tag v-else-if="!isUploadMode && pendingManualSpeaker" size="small" type="info">待生效参会人: {{ pendingManualSpeaker }}</el-tag>
          <el-tag v-if="!isUploadMode && store.isRecording" size="small" type="danger">录音中: {{ formatTime(recordingDuration) }}</el-tag>
          <el-tag v-if="isUploadMode && isLoadingRestoredUpload" size="small" type="info">加载历史中</el-tag>
          <el-tag v-if="isUploadMode && isUploadingAudio" size="small" type="warning">{{ uploadTaskStage || '上传识别中' }}</el-tag>
          <el-tag size="small" type="info">{{ actualCharCount }} 字符</el-tag>
        </div>
      </div>
      <div ref="transcriptContentRef" class="transcript-content">
        <div v-if="showUploadWorkspace" class="upload-workspace">
          <div class="upload-setup-card">
            <div class="upload-setup-main">
              <div class="upload-dropzone-icon">
                <el-icon><Upload /></el-icon>
              </div>
              <div class="upload-dropzone-copy">
                <h3>上传音视频文件</h3>
                <p>选择已有音频或视频文件，生成转写、说话人识别和会议纪要。</p>
              </div>
            </div>
            <div class="upload-settings-grid">
              <label class="upload-setting-field">
                <span>预计人数</span>
                <el-input
                  v-model="expectedUploadSpeakers"
                  class="upload-speaker-input"
                  placeholder="自动/2-4"
                />
              </label>
              <label class="upload-setting-field upload-hotword-field">
                <span>热词范围 · {{ activeHotwordAssetCount }} 个</span>
                <el-select
                  v-model="selectedHotwordCategories"
                  multiple
                  collapse-tags
                  collapse-tags-tooltip
                  clearable
                  size="small"
                  :loading="isLoadingHotwordAssets"
                  :disabled="hotwordAssetCategories.length === 0"
                  placeholder="全部分类"
                >
                  <el-option
                    v-for="category in hotwordAssetCategories"
                    :key="category"
                    :label="category"
                    :value="category"
                  />
                </el-select>
              </label>
              <div class="upload-setting-toggle">
                <span>声纹匹配</span>
                <el-switch v-model="enableUploadedVoiceprintMatching" size="small" />
              </div>
              <div class="upload-setting-toggle">
                <span>中英翻译</span>
                <el-switch v-model="enableTranslation" size="small" />
              </div>
              <el-button
                type="primary"
                class="upload-primary-btn"
                :loading="isUploadingAudio"
                :disabled="store.isRecording || isUploadingAudio"
                @click="triggerAudioUpload"
              >
                <el-icon><Upload /></el-icon>
                {{ hasUploadResult ? '重新选择文件' : '选择文件' }}
              </el-button>
            </div>
          </div>
          <div class="upload-empty-content">
            <div class="upload-empty-content-header">
              <span>当前内容</span>
              <el-tag size="small" :type="uploadWorkspaceStatusType" effect="plain">{{ uploadWorkspaceStatusText }}</el-tag>
            </div>
            <div v-if="shouldShowSpeakerSegments" class="speaker-segments upload-speaker-segments">
              <div 
                v-for="(group, index) in displaySpeakerGroups" 
                :key="`upload-group-${index}`" 
                class="speaker-segment"
                :class="[getSpeakerClass(group.speaker, index), { 'active-speaker-segment': group.segments.some(isActiveSpeakerSegment) }]"
                :data-segment-index="getSegmentDisplayIndex(group.segments[0])"
              >
                <div class="chat-message">
                  <div class="message-header">
                    <div class="speaker-avatar" :class="getSpeakerAvatarClass(group.speaker)">
                      <el-icon><user /></el-icon>
                    </div>
                    <div class="message-info">
                      <span class="speaker-name clickable-speaker" @click="handleSpeakerNameClick(group.segments[0], getSegmentDisplayIndex(group.segments[0]) ?? index)" :title="'点击修改当前段说话人'">
                        {{ group.speaker || `说话人${index + 1}` }}
                      </span>
                      <span
                        v-if="getSegmentTimeLabel(group)"
                        class="message-time"
                        :class="{ clickable: canSeekToSegment(group.segments[0]) }"
                        :title="canSeekToSegment(group.segments[0]) ? '点击跳转到 ' + getSegmentTimeLabel(group.segments[0]).split(' - ')[0] : '该段没有可跳转时间戳'"
                        @click="canSeekToSegment(group.segments[0]) && seekToTimestamp(group.segments[0])"
                      >
                        {{ getSegmentTimeLabel(group) }}
                      </span>
                    </div>
                  </div>
                  <div
                    class="message-bubble grouped-message-bubble"
                  >
                    <span
                      v-for="child in group.segments"
                      :key="`upload-part-${child.segmentIndex ?? child.startMs ?? child.text}`"
                      class="message-part"
                      :class="{ 'seekable-content': canSeekToSegment(child), 'active-message-part': isActiveSpeakerSegment(child) }"
                      :data-segment-index="getSegmentDisplayIndex(child)"
                      :title="canSeekToSegment(child) ? '点击跳转到 ' + getSegmentTimeLabel(child).split(' - ')[0] : ''"
                      @click.stop="canSeekToSegment(child) && seekToTimestamp(child)"
                      v-html="child.text"
                    ></span>
                  </div>
                  <div
                    v-if="enableTranslation && group.translation"
                    class="message-translation grouped-message-translation"
                  >
                    <el-icon class="translation-icon"><ChatDotRound /></el-icon>
                    <span
                      v-for="child in group.segments.filter(item => item.translation)"
                      :key="`upload-translation-${child.segmentIndex ?? child.startMs ?? child.translation}`"
                      class="translation-part"
                      :class="{ 'seekable-content': canSeekToSegment(child), 'active-message-part': isActiveSpeakerSegment(child) }"
                      :data-segment-index="getSegmentDisplayIndex(child)"
                      :title="canSeekToSegment(child) ? '点击跳转到 ' + getSegmentTimeLabel(child).split(' - ')[0] : ''"
                      @click.stop="canSeekToSegment(child) && seekToTimestamp(child)"
                    >
                      {{ child.translation }}
                    </span>
                  </div>
                </div>
              </div>
            </div>
            <el-input
              v-else
              v-model="store.transcript"
              type="textarea"
              :placeholder="transcriptPlaceholder"
              class="editable-transcript upload-empty-transcript"
            />
          </div>
        </div>
        <div class="speaker-segments" v-else-if="shouldShowSpeakerSegments">
          <div 
            v-for="(group, index) in displaySpeakerGroups" 
            :key="`group-${index}`" 
            class="speaker-segment"
            :class="[getSpeakerClass(group.speaker, index), { 'active-speaker-segment': group.segments.some(isActiveSpeakerSegment) }]"
            :data-segment-index="getSegmentDisplayIndex(group.segments[0])"
          >
            <div class="chat-message">
              <div class="message-header">
                <div class="speaker-avatar" :class="getSpeakerAvatarClass(group.speaker)">
                  <el-icon><user /></el-icon>
                </div>
                <div class="message-info">
                  <span class="speaker-name clickable-speaker" @click="handleSpeakerNameClick(group.segments[0], getSegmentDisplayIndex(group.segments[0]) ?? index)" :title="'点击修改当前段说话人'">
                    {{ group.speaker || `说话人${index + 1}` }}
                  </span>
                  <span
                    v-if="getSegmentTimeLabel(group)"
                    class="message-time"
                    :class="{ clickable: canSeekToSegment(group.segments[0]) }"
                    :title="canSeekToSegment(group.segments[0]) ? '点击跳转到 ' + getSegmentTimeLabel(group.segments[0]).split(' - ')[0] : '该段没有可跳转时间戳'"
                    @click="canSeekToSegment(group.segments[0]) && seekToTimestamp(group.segments[0])"
                  >
                    {{ getSegmentTimeLabel(group) }}
                  </span>
                </div>
              </div>
              <div
                class="message-bubble grouped-message-bubble"
              >
                <span
                  v-for="child in group.segments"
                  :key="`part-${child.segmentIndex ?? child.startMs ?? child.text}`"
                  class="message-part"
                  :class="{ 'seekable-content': canSeekToSegment(child), 'active-message-part': isActiveSpeakerSegment(child) }"
                  :data-segment-index="getSegmentDisplayIndex(child)"
                  :title="canSeekToSegment(child) ? '点击跳转到 ' + getSegmentTimeLabel(child).split(' - ')[0] : ''"
                  @click.stop="canSeekToSegment(child) && seekToTimestamp(child)"
                  v-html="child.text"
                ></span>
              </div>
              <div
                v-if="enableTranslation && group.translation"
                class="message-translation grouped-message-translation"
              >
                <el-icon class="translation-icon"><ChatDotRound /></el-icon>
                <span
                  v-for="child in group.segments.filter(item => item.translation)"
                  :key="`translation-${child.segmentIndex ?? child.startMs ?? child.translation}`"
                  class="translation-part"
                  :class="{ 'seekable-content': canSeekToSegment(child), 'active-message-part': isActiveSpeakerSegment(child) }"
                  :data-segment-index="getSegmentDisplayIndex(child)"
                  :title="canSeekToSegment(child) ? '点击跳转到 ' + getSegmentTimeLabel(child).split(' - ')[0] : ''"
                  @click.stop="canSeekToSegment(child) && seekToTimestamp(child)"
                >
                  {{ child.translation }}
                </span>
              </div>
            </div>
          </div>
        </div>
        <div class="simple-text-viewer" v-else>
          <el-input
            v-model="store.transcript"
            type="textarea"
            :placeholder="transcriptPlaceholder"
            class="editable-transcript"
          />
        </div>
      </div>
    </div>

    <input
      ref="audioUploadInputRef"
      class="hidden-audio-upload"
      type="file"
      accept="audio/*,video/*,.wav,.mp3,.flac,.m4a,.aac,.ogg,.webm,.mp4,.mov,.mkv,.avi,.wmv,.m4v,.amr,.opus,.wma"
      @change="handleAudioUploadChange"
    />

    <!-- 底部控制面板 -->
    <div :class="['bottom-controls', { 'upload-mode-controls': isUploadMode, 'has-upload-media': isUploadMode && (store.audioUrl || actualCharCount > 0) }]">
      <div class="left-bottom-controls">
        <div class="bottom-control-group content-actions">
          <el-button 
            class="control-btn batch-edit-btn mixed-style"
            @click="batchEditDialogVisible = true"
          >
            <span class="btn-icon orange-icon">批</span>
            批量修改转换内容
          </el-button>

          <el-button
            v-if="isUploadMode && activeUploadTaskId && store.speakerSegments.length > 0"
            class="control-btn speaker-review-btn mixed-style"
            :loading="speakerReviewLoading"
            title="整理上传识别的说话人，可试听、合并、注册声纹"
            @click="openSpeakerReviewDialog"
          >
            <el-icon class="upload-control-icon"><User /></el-icon>
            说话人整理
          </el-button>
        </div>
        
        <!-- 音频采集模式按钮 - 互斥显示 -->
        <el-button 
          v-if="!isUploadMode && audioCaptureMode === 'browser'"
          class="control-btn mode-switch-btn mixed-style"
          @click="audioCaptureMode = 'server'"
          title="点击切换到服务器采集"
        >
          <span class="btn-icon blue-icon">浏</span>
          浏览器采集
        </el-button>
        
        <el-button 
          v-else-if="!isUploadMode"
          class="control-btn mode-switch-btn mixed-style"
          @click="audioCaptureMode = 'browser'"
          title="点击切换到浏览器采集"
        >
          <span class="btn-icon purple-icon">服</span>
          服务器采集
        </el-button>

        <el-button
          v-if="!isUploadMode"
          class="control-btn manual-speaker-btn mixed-style"
          :title="store.isRecording ? '指定当前录音会话的参会人' : '可提前指定，开始录音后自动生效'"
          @click="openManualSpeakerDialog"
        >
          <span class="btn-icon green-icon">人</span>
          {{ activeManualSpeaker || pendingManualSpeaker ? '切换参会人' : '指定参会人' }}
        </el-button>

        <div v-if="isUploadMode" class="bottom-control-group upload-file-actions">
          <el-button
            class="control-btn upload-audio-btn mixed-style"
            :loading="isUploadingAudio"
            :disabled="store.isRecording || isUploadingAudio"
            :title="uploadActionTitle"
            @click="triggerAudioUpload"
          >
            <el-icon class="upload-control-icon"><Upload /></el-icon>
            {{ uploadActionText }}
          </el-button>

          <el-button
            v-if="!showUploadWorkspace && !isUploadingAudio"
            class="control-btn upload-restore-btn mixed-style"
            title="恢复上方上传配置区域"
            @click="restoreUploadWorkspace"
          >
            <el-icon class="upload-control-icon"><Upload /></el-icon>
            恢复上传
          </el-button>
        </div>

        <el-button
          v-if="!isUploadMode && (activeManualSpeaker || pendingManualSpeaker)"
          class="control-btn restore-speaker-btn mixed-style"
          title="恢复串口自动判断"
          @click="restoreAutoSpeaker"
        >
          <span class="btn-icon gray-icon">复</span>
          恢复串口
        </el-button>

      </div>
      
      <div class="right-controls">
        <div v-if="!isUploadMode || store.audioUrl || actualCharCount > 0" class="audio-player-compact">
          <div class="player-controls" @click="togglePlay">
            <el-icon class="play-icon">
              <video-play v-if="!isPlaying"/>
              <video-pause v-else />
            </el-icon>
          </div>
          <div class="player-progress-compact">
            <div class="time">{{ formatTime(currentTime || 0) }}</div>
            <div class="progress-bar" @click="handleProgressClick">
              <div class="progress-bg" :style="{ width: progressWidth + '%' }"></div>
              <div class="progress-handle" :style="{ left: progressWidth + '%' }"></div>
            </div>
            <div class="time">{{ formatTime(duration || 0) }}</div>
          </div>
          <div class="player-download" @click="handleDownloadAudio" v-if="store.audioUrl">
            <el-icon class="download-icon">
              <Download />
            </el-icon>
          </div>
          <audio 
            ref="audioRef" 
            :src="store.audioUrl" 
            style="display: none;" 
            @loadeddata="updateProgress(true)"
            @loadedmetadata="updateProgress(true)"
            @timeupdate="updateProgress()"
            @play="handleAudioPlay"
            @pause="handleAudioPause"
            @ended="handleAudioEnded"
            preload="metadata"
          />
        </div>

        
        <el-popover
          v-model:visible="settingsPopoverVisible"
          placement="top-end"
          width="320"
          trigger="click"
          :offset="10"
        >
          <template #reference>
            <el-button 
              class="control-btn icon-only mixed-style"
              circle
              title="系统设置"
              aria-label="系统设置"
            >
              <el-icon class="btn-icon">
                <setting />
              </el-icon>
            </el-button>
          </template>
          <div class="settings-content">
            <div class="setting-item">
              <span class="setting-label">识别模式</span>
              <el-select v-model="store.asrMode" size="small" style="width: 100px;">
                <el-option label="双通道模式" value="2pass" />
                <el-option label="在线模式" value="online" />
                <el-option label="离线模式" value="soffline" />
              </el-select>
            </div>
            <div class="setting-item">
              <span class="setting-label">识别语言</span>
              <el-select v-model="store.language" size="small" style="width: 100px;">
                <el-option label="中文" value="zh" />
                <el-option label="自动检测" value="auto" />
                <el-option label="英文" value="en" />
                <el-option label="粤语" value="yue" />
                <el-option label="日语" value="ja" />
                <el-option label="韩语" value="ko" />
              </el-select>
            </div>
            <div class="setting-item hotword-asset-setting">
              <span class="setting-label">资产热词</span>
              <div class="hotword-asset-control">
                <el-tag
                  size="small"
                  :type="hotwordAssetsError ? 'danger' : hotwordAssets.length > 0 ? 'success' : 'info'"
                  effect="plain"
                >
                  {{ hotwordAssetsStatusText }}
                </el-tag>
                <el-button
                  size="small"
                  :loading="isLoadingHotwordAssets"
                  @click="syncHotwordAssets()"
                >
                  刷新
                </el-button>
                <el-button size="small" type="primary" plain @click="openHotwordManager">
                  管理
                </el-button>
                <el-select
                  v-model="selectedHotwordCategories"
                  multiple
                  collapse-tags
                  collapse-tags-tooltip
                  clearable
                  size="small"
                  class="hotword-category-select"
                  placeholder="全部分类"
                >
                  <el-option
                    v-for="category in hotwordAssetCategories"
                    :key="category"
                    :label="category"
                    :value="category"
                  />
                </el-select>
              </div>
            </div>
            <div v-if="hotwordAssets.length > 0 || hotwordAssetsError" class="setting-help hotword-asset-help">
              <div class="help-content" v-if="!hotwordAssetsError">
                本次应用 {{ activeHotwordAssetCount }} 个热词；范围：{{ hotwordAssetScopeText }}；受保护 {{ protectedHotwordAssetCount }} 个；最后同步：{{ hotwordAssetsLastSync || '本次会话' }}
              </div>
              <div class="help-content warning" v-else>
                {{ hotwordAssetsError }}
              </div>
            </div>
            <div v-if="!isUploadMode" class="setting-item">
              <span class="setting-label">音频设备</span>
              <el-select v-model="store.audioSource" size="small" style="width: 100px;">
                <el-option
                  v-for="device in store.audioDevices"
                  :key="device.deviceId"
                  :label="device.label"
                  :value="device.deviceId"
                />
              </el-select>
            </div>
            <div class="setting-help" v-if="!isUploadMode && audioCaptureMode === 'server'">
              <div class="help-title">
                <el-icon style="margin-right: 4px;"><QuestionFilled /></el-icon>
                服务器采集说明：
              </div>
              <div class="help-content">
                • 音频设备列表来自服务器<br>
                • 浏览器不传输音频数据<br>
                • 服务器直接采集音频并识别
              </div>
            </div>
            <div v-if="isUploadMode" class="setting-item">
              <span class="setting-label">声纹匹配</span>
              <el-switch
                v-model="enableUploadedVoiceprintMatching"
                size="small"
                active-text="启用"
                inactive-text="禁用"
              />
            </div>
            <div v-else class="setting-item">
              <span class="setting-label">说话人识别</span>
              <el-switch
                v-model="enableSpeakerDiarization"
                size="small"
                active-text="启用"
                inactive-text="禁用"
              />
            </div>
            <div v-if="isUploadMode" class="setting-item">
              <span class="setting-label">上传预计人数</span>
              <el-input
                v-model="expectedUploadSpeakers"
                size="small"
                style="width: 100px;"
                placeholder="自动/2-4"
              />
            </div>
            <div class="setting-item setting-item-action">
              <span class="setting-label">说话人设置</span>
              <el-button
                link
                type="primary"
                class="setting-action-btn"
                @click="openSpeakerSettings"
              >
                去配置
              </el-button>
            </div>
            <div class="setting-item">
              <span class="setting-label">中英翻译</span>
              <el-switch
                v-model="enableTranslation"
                size="small"
                active-text="启用"
                inactive-text="禁用"
              />
            </div>
            <div class="setting-item">
              <span class="setting-label">会议纪要区域</span>
              <el-switch 
                v-model="showMinutesPanel" 
                size="small"
                active-text="显示" 
                inactive-text="隐藏"
              />
            </div>

            <!-- 会议纪要模型服务配置区域 - 仅在显示会议纪要区域时显示 -->
            <template v-if="showMinutesPanel">
              <div class="setting-divider"></div>
              <div class="setting-section-title">会议纪要模型服务配置</div>
              <div class="setting-item">
                <span class="setting-label">服务类型</span>
                <el-select v-model="serviceType" size="small" style="width: 100px;">
                  <el-option label="Ollama" value="ollama" />
                  <el-option label="Xinference" value="xinference" />
                  <el-option label="vLLM" value="vllm" />
                  <el-option label="SGLang" value="sglang" />
                </el-select>
              </div>
              <div class="setting-item">
                <span class="setting-label">纪要模板</span>
                <el-select
                  v-model="selectedSummaryTemplate"
                  size="small"
                  style="width: 180px;"
                  @change="handleSummaryTemplateChange"
                >
                  <el-option
                    v-for="template in SUMMARY_TEMPLATE_OPTIONS"
                    :key="template.id"
                    :label="template.label"
                    :value="template.id"
                  />
                </el-select>
              </div>
            
            <!-- Ollama配置 -->
            <template v-if="serviceType === 'ollama'">
              <div class="setting-item">
                <span class="setting-label">服务端点</span>
                <el-input v-model="ollamaEndpoint" size="small" style="width: 300px;" placeholder="https://10.1.0.27/ollama/api/chat" />
              </div>
              <div class="setting-item">
                <span class="setting-label">模型名称</span>
                <el-input v-model="ollamaModel" size="small" style="width: 100px;" placeholder="qwen3:30b-a3b-q4_K_M" />
              </div>
            </template>
            
            <!-- Xinference配置 -->
            <template v-if="serviceType === 'xinference'">
              <div class="setting-item">
                <span class="setting-label">API端点</span>
                <el-input v-model="xinferenceEndpoint" size="small" style="width: 100px;" placeholder="http://10.1.0.26:9997/v1/chat/completions" />
              </div>
              <div class="setting-item">
                <span class="setting-label">模型名称</span>
                <el-input v-model="xinferenceModel" size="small" style="width: 100px;" placeholder="DeepSeek-R1-671B-1" />
              </div>
              <div class="setting-item">
                <span class="setting-label">API密钥</span>
                <el-input v-model="xinferenceApiKey" size="small" style="width: 100px;" :placeholder="xinferenceHasApiKey ? '已保存，留空不变' : '可选'" type="password" show-password />
              </div>
            </template>
            
            <!-- vLLM配置 -->
              <template v-if="serviceType === 'vllm'">
                <div class="setting-item">
                  <span class="setting-label">API端点</span>
                  <el-input v-model="vllmEndpoint" size="small" style="width: 100px;" placeholder="http://localhost:8000/v1/chat/completions" />
                </div>
                <div class="setting-item">
                  <span class="setting-label">模型名称</span>
                  <el-input v-model="vllmModel" size="small" style="width: 100px;" placeholder="meta-llama/Llama-2-7b-chat-hf" />
                </div>
                <div class="setting-item">
                  <span class="setting-label">API密钥</span>
                  <el-input v-model="vllmApiKey" size="small" style="width: 100px;" :placeholder="vllmHasApiKey ? '已保存，留空不变' : '可选'" type="password" show-password />
                </div>
              </template>
              
              <!-- SGLang配置 -->
              <template v-if="serviceType === 'sglang'">
                <div class="setting-item">
                  <span class="setting-label">API端点</span>
                  <el-input v-model="sglangEndpoint" size="small" style="width: 100px;" placeholder="http://localhost:30000/v1/chat/completions" />
                </div>
                <div class="setting-item">
                  <span class="setting-label">模型名称</span>
                  <el-input v-model="sglangModel" size="small" style="width: 100px;" placeholder="meta-llama/Llama-2-7b-chat-hf" />
                </div>
                <div class="setting-item">
                  <span class="setting-label">API密钥</span>
                  <el-input v-model="sglangApiKey" size="small" style="width: 100px;" :placeholder="sglangHasApiKey ? '已保存，留空不变' : '可选'" type="password" show-password />
                </div>
              </template>
            
            <div class="setting-item">
              <el-button 
                type="success" 
                size="small" 
                @click="saveBackendLLMConfig(true)"
                style="width: 100%;"
              >
                保存模型配置
              </el-button>
            </div>

            <div class="setting-item">
              <el-button 
                type="primary" 
                size="small" 
                @click="testLLMConnection"
                :loading="isGeneratingSummary"
                :disabled="isGeneratingSummary"
                style="width: 100%;"
              >
                {{ isGeneratingSummary ? '生成中' : '测试生成纪要' }}
              </el-button>
            </div>
            <div v-if="isGeneratingSummary" class="setting-item summary-task-progress">
              <el-progress :percentage="summaryProgress" :show-text="false" />
              <span>{{ summaryStage || '正在生成会议纪要...' }}</span>
            </div>
             <div class="setting-help">
               <div class="help-title">连接说明：</div>
               <div class="help-content" v-if="serviceType === 'ollama'">
                 • 开发环境会自动使用代理避免CORS问题<br>
                 • 确保Ollama服务已启动：<code>ollama serve</code><br>
                 • 确保模型已下载：<code>ollama pull 模型名</code>
               </div>
               <div class="help-content" v-if="serviceType === 'xinference'">
                 • 确保Xinference服务已启动<br>
                 • API端点格式：<code>http://host:port/v1/chat/completions</code><br>
                 • 支持OpenAI兼容的API格式<br>
                 • API密钥为可选项，根据服务配置决定
               </div>
               <div class="help-content" v-if="serviceType === 'vllm'">
                 • 确保vLLM服务已启动：<code>python -m vllm.entrypoints.openai.api_server</code><br>
                 • 默认端口：8000，API格式兼容OpenAI<br>
                 • 支持高性能推理和批处理<br>
                 • API密钥为可选项，根据服务配置决定
               </div>
               <div class="help-content" v-if="serviceType === 'sglang'">
                 • 确保SGLang服务已启动：<code>python -m sglang.launch_server</code><br>
                 • 默认端口：30000，支持结构化生成<br>
                 • 提供高效的语言模型推理服务<br>
                 • API密钥为可选项，根据服务配置决定
               </div>
             </div>
            </template>
            <!-- 会议纪要模型服务配置区域结束 -->
          </div>
        </el-popover>
        <el-button 
          v-if="!isUploadMode"
          :class="['control-btn', 'record-control-btn', 'icon-only', { 'recording': store.isRecording }]"
          @click="toggleRecording"
          circle
        >
          <el-icon class="btn-icon">
            <microphone v-if="!store.isRecording" />
            <video-pause v-else />
          </el-icon>
        </el-button>
      </div>
    </div>

    <!-- 热词优化弹窗 -->
    <!-- 热词对话框已注释 - 改用直接API调用方式
    <el-dialog
      v-model="hotwordDialogVisible"
      title="热词优化"
      width="500px"
    >
      <div class="hotword-content">
        <el-select
          v-model="selectedIndustry"
          placeholder="选择行业分类"
          style="width: 100%; margin-bottom: 15px"
          @change="handleIndustryChange"
        >
          <el-option
            v-for="item in industries"
            :key="item.value"
            :label="item.label"
            :value="item.value"
          />
        </el-select>
        <el-input
          v-model="hotwordInput"
          type="textarea"
          :rows="10"
          placeholder="请输入热词和权重，每行一个热词，格式为：热词 权重（1-100的整数）\n例如：真视通 80"
        />
      </div>
      <template #footer>
        <span class="dialog-footer">
          <el-button @click="hotwordDialogVisible = false">取消</el-button>
          <el-button type="primary" @click="handleApplyHotwords">应用</el-button>
        </span>
      </template>
    </el-dialog>
    -->

    <el-dialog
      v-model="manualSpeakerDialogVisible"
      title="指定参会人"
      width="420px"
    >
      <div class="manual-speaker-dialog">
        <div class="manual-speaker-tip">
          当前仍保留串口自动判断。这里的指定只覆盖当前录音会话，恢复后会继续使用串口自动判断。
        </div>
        <el-select
          v-model="selectedManualSpeaker"
          filterable
          allow-create
          clearable
          default-first-option
          :loading="manualSpeakerLoading"
          placeholder="请选择或输入参会人姓名"
          style="width: 100%;"
        >
          <el-option
            v-for="speaker in manualSpeakerOptions"
            :key="speaker.speaker_id"
            :label="speaker.speaker_name"
            :value="speaker.speaker_name"
          />
        </el-select>
        <div class="manual-speaker-hint">
          {{ manualSpeakerOptions.length > 0 ? `已加载 ${manualSpeakerOptions.length} 位已注册参会人` : '没有已注册参会人时，也可以直接输入姓名' }}
        </div>
        <div class="manual-speaker-actions">
          <el-button link type="primary" @click="openSpeakerSettings">
            没有合适参会人？去说话人设置
          </el-button>
        </div>
      </div>
      <template #footer>
        <span class="dialog-footer">
          <el-button v-if="activeManualSpeaker" @click="restoreAutoSpeaker">恢复串口自动</el-button>
          <el-button @click="manualSpeakerDialogVisible = false">取消</el-button>
          <el-button type="primary" @click="applyManualSpeaker">确认指定</el-button>
        </span>
      </template>
    </el-dialog>

    <el-drawer
      v-model="speakerReviewDialogVisible"
      direction="rtl"
      size="560px"
      :modal="false"
      :with-header="false"
      class="speaker-review-drawer"
    >
      <section class="speaker-review-workbench" aria-label="上传识别说话人整理">
        <header class="speaker-review-header">
          <div class="speaker-review-heading">
            <div class="speaker-review-icon">
              <el-icon><User /></el-icon>
            </div>
            <div>
              <h3>说话人整理</h3>
              <p>试听片段，修正姓名，合并误分的说话人，并补齐声纹。</p>
            </div>
          </div>
          <div class="speaker-review-header-actions">
            <el-button size="small" :loading="speakerReviewLoading" @click="loadUploadedSpeakerCandidates">刷新</el-button>
            <el-button size="small" @click="speakerReviewDialogVisible = false">关闭</el-button>
          </div>
        </header>

        <div class="speaker-review-summary">
          <div class="speaker-review-stat">
            <span>候选</span>
            <strong>{{ speakerReviewCandidateCount }}</strong>
          </div>
          <div class="speaker-review-stat">
            <span>片段</span>
            <strong>{{ speakerReviewSegmentCount }}</strong>
          </div>
          <div class="speaker-review-stat">
            <span>可用时长</span>
            <strong>{{ speakerReviewTotalDurationLabel }}</strong>
          </div>
        </div>

        <div v-loading="speakerReviewLoading" class="speaker-review-list">
          <el-empty
            v-if="uploadedSpeakerCandidates.length === 0 && !speakerReviewLoading"
            description="暂无可整理的说话人"
          />
          <article
            v-for="candidate in uploadedSpeakerCandidates"
            :key="candidate.speaker"
            class="speaker-review-item"
          >
            <div class="speaker-review-item-header">
              <div class="speaker-review-identity">
                <div class="speaker-review-avatar" :class="getSpeakerAvatarClass(candidate.display_name || candidate.speaker)">
                  <el-icon><User /></el-icon>
                </div>
                <div class="speaker-review-title">
                  <span>{{ candidate.display_name || candidate.speaker }}</span>
                  <el-tag size="small" type="info" effect="plain">
                    {{ candidate.segment_count }} 段 · {{ candidate.total_duration_label }}
                  </el-tag>
                </div>
              </div>
              <div class="speaker-review-actions">
                <el-button size="small" @click="renameUploadedSpeakerCandidate(candidate)">更名</el-button>
                <el-button size="small" type="primary" @click="registerUploadedSpeakerCandidate(candidate)">注册声纹</el-button>
              </div>
            </div>

            <div class="speaker-review-samples">
              <button
                v-for="sample in candidate.sample_segments"
                :key="sample.index"
                type="button"
                class="sample-play-btn"
                @click="playUploadedSpeakerSample(sample)"
              >
                <span>{{ sample.start_label || '片段' }}</span>
                <el-tag
                  v-if="sample.quality"
                  size="small"
                  effect="plain"
                  :type="uploadedSampleQualityTagType(sample.quality)"
                >
                  {{ uploadedSampleQualityLabel(sample.quality) }}
                </el-tag>
              </button>
            </div>

            <div class="speaker-merge-control">
              <span>合并到</span>
              <el-select
                v-model="speakerMergeTargets[candidate.speaker]"
                size="small"
                placeholder="选择目标"
              >
                <el-option
                  v-for="target in uploadedSpeakerCandidates.filter(item => item.speaker !== candidate.speaker)"
                  :key="target.speaker"
                  :label="target.display_name || target.speaker"
                  :value="target.speaker"
                />
              </el-select>
              <el-button size="small" @click="mergeUploadedSpeakerCandidate(candidate)">合并</el-button>
            </div>
          </article>
        </div>

        <footer class="speaker-review-footer">
          <el-button text type="primary" @click="openSpeakerSettings">管理已注册声纹</el-button>
          <span>整理结果会立即回写到当前上传转写内容。</span>
        </footer>
      </section>
    </el-drawer>

    <!-- 批量修改转换内容对话框 -->
    <el-dialog
      v-model="batchEditDialogVisible"
      title="查找和替换"
      width="450px"
      draggable
      @close="closeBatchEditDialog"
    >
      <div class="batch-edit-content">
        <div class="search-section">
          <div class="input-group">
            <label>查找内容：</label>
            <el-input
              v-model="originalContent"
              placeholder="请输入要查找的内容..."
              @keyup.enter="findMatches"
            />
          </div>
          <div class="input-group">
            <label>替换为：</label>
            <el-input
              v-model="modifiedContent"
              placeholder="请输入替换后的内容..."
              @keyup.enter="replaceCurrent"
            />
          </div>
          
          <!-- 匹配计数显示 -->
          <div v-if="totalMatches > 0" class="match-info">
            <el-tag type="success" size="small">
              第 {{ currentMatchIndex + 1 }} / {{ totalMatches }} 处匹配
            </el-tag>
          </div>
        </div>
      </div>
      
      <template #footer>
        <div class="dialog-footer-custom">
          <el-button size="small" type="primary" @click="findMatches" icon="Search">查找</el-button>
          <el-button size="small" type="info" @click="findNext" icon="ArrowRight">下一个</el-button>
          <el-button size="small" type="warning" @click="replaceCurrent" icon="Edit">替换</el-button>
          <el-button size="small" type="danger" @click="replaceAll" icon="Select">全部</el-button>
          <el-button size="small" @click="closeBatchEditDialog">关闭</el-button>
        </div>
      </template>
    </el-dialog>

    <TranslateDialog
      v-model:visible="translateDialogVisible"
      :text="translateInput"
    />
  </div>
</template>

<style scoped>
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

:deep(.mode-popover) {
  padding: 12px !important;
  border-radius: 8px !important;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.1) !important;
}

:deep(.mode-popover .el-radio-group) {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

:deep(.mode-popover .el-radio-button) {
  margin-right: 0 !important;
}

:deep(.mode-popover .el-radio-button__inner) {
  border-radius: 4px !important;
  width: 100%;
  text-align: center;
  border: 1px solid #dcdfe6;
}
.asr-panel {
  height: 100%;
  background: #fff;
  border-radius: 8px;
  box-shadow: 0 2px 12px 0 rgba(0, 0, 0, 0.1);
  display: flex;
  flex-direction: column;
  position: relative;
}

.upload-task-modal {
  position: fixed;
  inset: 0;
  z-index: 3000;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 20px;
  background: rgba(17, 24, 39, 0.62);
}

.upload-task-panel {
  position: relative;
  display: flex;
  width: min(360px, 100%);
  flex-direction: column;
  align-items: stretch;
  gap: 12px;
  padding: 22px 20px 18px;
  border-radius: 8px;
  background: #fff;
  box-shadow: 0 18px 42px rgba(15, 23, 42, 0.28);
}

.upload-task-spinner {
  width: 34px;
  height: 34px;
  margin: 2px auto 0;
  border: 3px solid #e5e7eb;
  border-top-color: #2563eb;
  border-radius: 50%;
  animation: upload-task-spin 0.8s linear infinite;
}

.upload-task-title {
  color: #111827;
  font-size: 14px;
  font-weight: 600;
  line-height: 1.5;
  text-align: center;
  word-break: break-word;
}

.upload-task-progress {
  width: 100%;
}

@keyframes upload-task-spin {
  to {
    transform: rotate(360deg);
  }
}



.transcript-panel {
  flex: 1;
  display: flex;
  flex-direction: column;
  margin: 8px 16px;
  background: #fff;
  border-radius: 8px;
  border: none;
  overflow: hidden;
  min-height: 0;
}

.transcript-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 12px;
  background: #f5f7fa;
  border-radius: 4px;
  border: none;
  flex-shrink: 0;
  
  .transcript-title {
    font-weight: 600;
    color: #303133;
    font-size: 14px;
  }
  
  .transcript-stats {
    display: flex;
    gap: 4px;
  }
}

.transcript-content {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 0;
  padding: 12px;
}

.upload-workspace {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 12px;
  min-height: 0;
}

.upload-setup-card {
  display: flex;
  flex-direction: column;
  gap: 14px;
  padding: 16px;
  border: 1px dashed #b6d7d2;
  border-radius: 8px;
  background: #f7fbfa;

  &.uploading {
    border-style: solid;
    background: #f9fbff;
  }
}

.upload-setup-main {
  display: flex;
  align-items: center;
  gap: 14px;
  min-width: 0;
}

.upload-empty-content {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  border: 1px solid #e4e7ed;
  border-radius: 8px;
  background: #fff;
  overflow: hidden;
}

.upload-empty-content-header {
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

.upload-dropzone-icon {
  width: 44px;
  height: 44px;
  flex: 0 0 auto;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 8px;
  background: #e6f5f2;
  color: #0f766e;
  font-size: 28px;
}

.upload-dropzone-copy {
  min-width: 0;
  flex: 1 1 auto;
  text-align: left;

  h3 {
    margin: 0;
    color: #10201d;
    font-size: 16px;
    line-height: 1.3;
  }

  p {
    margin: 4px 0 0;
    color: #60716d;
    font-size: 14px;
    line-height: 1.5;
  }
}

.upload-settings-grid {
  display: grid;
  grid-template-columns: minmax(130px, 0.8fr) minmax(180px, 1fr) auto auto;
  align-items: end;
  gap: 10px;
}

.upload-setting-field,
.upload-setting-toggle {
  min-height: 40px;
  display: flex;
  align-items: center;
  gap: 8px;
}

.upload-setting-field {
  flex-direction: column;
  align-items: stretch;

  span {
    color: #606266;
    font-size: 12px;
    line-height: 1;
  }
}

.upload-setting-toggle {
  padding: 0 10px;
  border: 1px solid #e4e7ed;
  border-radius: 8px;
  background: #fff;
  color: #606266;
  font-size: 13px;
  white-space: nowrap;
}

.upload-speaker-input {
  min-width: 0;
}

.upload-hotword-field {
  min-width: 0;
}

.upload-hotword-field :deep(.el-select) {
  width: 100%;
}

.upload-primary-btn {
  grid-column: 1 / -1;
  min-height: 44px;
  border-radius: 8px;
}

.upload-empty-transcript {
  min-height: 0;
}

.upload-speaker-segments {
  min-height: 0;
  padding: 16px;
}

.simple-text-viewer {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 0;
}

.editable-transcript {
  flex: 1;
  min-height: 300px;
}

.editable-transcript :deep(.el-textarea__inner) {
  font-size: 14px;
  line-height: 1.6;
  color: #303133;
  background: #fff;
  border: none !important;
  border-radius: 8px;
  padding: 16px;
  white-space: pre-wrap;
  word-wrap: break-word;
  text-align: left;
  direction: ltr;
  writing-mode: horizontal-tb;
  resize: none;
  font-family: inherit;
  height: 100% !important;
  max-height: none !important;
  min-height: 300px !important;
  overflow-y: auto;
  outline: none !important;
  box-shadow: none !important;
}

.editable-transcript :deep(.el-textarea__inner):focus {
  border: none !important;
  box-shadow: none !important;
  outline: none !important;
}

.editable-transcript :deep(.el-textarea__inner):hover {
  border: none !important;
  box-shadow: none !important;
}

.transcript-textarea :deep(.el-textarea__inner) {
  height: 100% !important;
  max-height: none;
  min-height: 0;
  overflow-y: auto;
  border: none;
  background: #f5f7fa;
  border-radius: 4px;
  padding: 12px;
  font-size: 14px;
  line-height: 1.6;
  box-sizing: border-box;
}

/* 说话人分段显示样式 */
.speaker-segments {
  flex: 1;
  overflow-y: auto;
  padding: 16px;
  background: #fff;
}

.speaker-segment {
  margin-bottom: 20px;
  scroll-margin: 96px;
  transition: filter 0.18s ease;
}

.speaker-segment:last-child {
  margin-bottom: 0;
}

.speaker-segment.active-speaker-segment .message-header {
  filter: saturate(1.08);
}

.speaker-segment.active-speaker-segment .message-bubble {
  box-shadow: 0 0 0 2px rgba(64, 158, 255, 0.22), 0 6px 16px rgba(64, 158, 255, 0.08);
}

.chat-message {
  display: flex;
  flex-direction: column;
  gap: 8px;
  align-items: stretch;
  text-align: left;
}

.message-header {
  display: flex;
  align-items: center;
  gap: 8px;
}

.speaker-avatar {
  width: 24px;
  height: 24px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
  font-size: 12px;
  flex-shrink: 0;
}

.message-info {
  display: flex;
  align-items: center;
  gap: 8px;
}

.speaker-name {
  font-size: 14px;
  font-weight: 500;
  color: #303133;
}

.speaker-name.clickable-speaker {
  cursor: pointer;
  transition: color 0.2s ease, background-color 0.2s ease, border-color 0.2s ease;
  padding: 3px 9px;
  border: 1px solid #d9ecff;
  border-radius: 6px;
  background: #ecf5ff;
  color: #1f5fbf;
  font-weight: 600;
}

.speaker-name.clickable-speaker:hover {
  color: #0b5cad;
  background: #dcefff;
  border-color: #a8d3ff;
}

.message-time {
  font-size: 12px;
  color: #909399;
}

.message-time.clickable {
  cursor: pointer;
  transition: all 0.3s ease;
  padding: 2px 8px;
  border-radius: 4px;
  background: transparent;
}

.message-time.clickable:hover {
  color: #409eff;
  background: #e1f3ff;
  transform: translateY(-1px);
}

.message-bubble {
  background: #e8f4fd;
  border-radius: 12px;
  padding: 12px 16px;
  margin-left: 0;
  font-size: 14px;
  line-height: 1.5;
  color: #303133;
  word-wrap: break-word;
  white-space: pre-wrap;
  text-align: left;
  direction: ltr;
}

.message-bubble.seekable-content,
.message-translation.seekable-content {
  cursor: pointer;
}

.message-bubble.seekable-content:hover,
.message-translation.seekable-content:hover {
  filter: brightness(0.98);
}

.grouped-message-bubble {
  cursor: default;
}

.message-part {
  border-radius: 4px;
  padding: 1px 2px;
  transition: background-color 0.18s ease, box-shadow 0.18s ease;
}

.message-part.seekable-content {
  cursor: pointer;
}

.message-part.seekable-content:hover {
  background: rgba(64, 158, 255, 0.12);
}

.message-part.active-message-part,
.translation-part.active-message-part {
  background: #fff3bf;
  box-shadow: 0 0 0 1px rgba(230, 162, 60, 0.45) inset;
}

@media (prefers-reduced-motion: reduce) {
  .speaker-segment,
  .message-part,
  .translation-part {
    transition: none;
  }
}

.grouped-message-translation {
  cursor: default;
}

.translation-part {
  border-radius: 4px;
  padding: 1px 2px;
  transition: background-color 0.18s ease, box-shadow 0.18s ease;
}

.translation-part + .translation-part::before {
  content: " ";
}

.translation-part.seekable-content {
  cursor: pointer;
}

.translation-part.seekable-content:hover {
  background: rgba(64, 158, 255, 0.12);
}

.message-translation {
  margin-top: 8px;
  margin-left: 0;
  padding: 8px 12px;
  background: #f5f7fa;
  border-left: 3px solid #409eff;
  border-radius: 4px;
  font-size: 13px;
  line-height: 1.5;
  color: #606266;
  font-style: italic;
  text-align: left;
}

.translation-icon {
  margin-right: 6px;
  color: #409eff;
  vertical-align: middle;
}

/* 不同说话人的头像颜色样式 */
.speaker-avatar-0 { background-color: #409eff; }
.speaker-avatar-1 { background-color: #67c23a; }
.speaker-avatar-2 { background-color: #e6a23c; }
.speaker-avatar-3 { background-color: #f56c6c; }
.speaker-avatar-4 { background-color: #909399; }
.speaker-avatar-5 { background-color: #c71585; }
.speaker-avatar-6 { background-color: #ff6347; }
.speaker-avatar-7 { background-color: #32cd32; }

/* 不同说话人的消息气泡颜色样式 */
.speaker-0 .message-bubble { background-color: #e1f3ff; }
.speaker-1 .message-bubble { background-color: #f0f9ff; }
.speaker-2 .message-bubble { background-color: #fef7e0; }
.speaker-3 .message-bubble { background-color: #fef0f0; }
.speaker-4 .message-bubble { background-color: #f4f4f5; }
.speaker-5 .message-bubble { background-color: #fce4ec; }
.speaker-6 .message-bubble { background-color: #fff3e0; }
.speaker-7 .message-bubble { background-color: #e8f5e8; }


.bottom-tools {
  padding: 12px 16px;
  border-top: 1px solid #e4e7ed;
  background-color: #fff;
}

.audio-player {
  margin: 8px 16px;
  background-color: #f0f7ff;
  border-radius: 8px;
  padding: 8px;
}

.player-container {
  display: flex;
  align-items: center;
  gap: 16px;
  background: white;
  padding: 8px;
  border-radius: 6px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.05);
}

.player-controls {
  display: flex;
  align-items: center;
  cursor: pointer;
}

.play-icon {
  font-size: 20px;
  color: #409EFF;
}

.player-progress {
  flex: 1;
  display: flex;
  align-items: center;
  gap: 12px;
}

.progress-bar {
  flex: 1;
  height: 4px;
  background: #E4E7ED;
  border-radius: 2px;
  position: relative;
  cursor: pointer;
}

.progress-bg {
  position: absolute;
  left: 0;
  top: 0;
  height: 100%;
  width: 30%;
  background: #409EFF;
  border-radius: 2px;
}

.progress-handle {
  position: absolute;
  width: 12px;
  height: 12px;
  background: white;
  border: 2px solid #409EFF;
  border-radius: 50%;
  top: 50%;
  left: 30%;
  transform: translate(-50%, -50%);
}

.time {
  font-size: 12px;
  color: #909399;
  min-width: 40px;
}

.player-volume {
  color: #909399;
  font-size: 18px;
  cursor: pointer;
}

.player-options {
  color: #909399;
  font-size: 18px;
  cursor: pointer;
  display: flex;
  gap: 12px;
}

.download-icon {
  color: #909399;
  transition: color 0.3s;
}

.download-icon:hover {
  color: #409EFF;
}







/* 底部控制面板样式 */
.hidden-audio-upload {
  display: none;
}

.bottom-controls {
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 16px;
  padding: 16px 20px;
  border-top: 1px solid #e9ecef;
  background: #fff;
}

.left-bottom-controls {
  display: flex;
  gap: 12px;
  align-items: center;
  flex: 1 1 520px;
  min-width: 0;
  flex-wrap: wrap;
}

.bottom-control-group {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}

/* 模式切换按钮样式 */
.mode-switch-btn {
  transition: all 0.3s ease;
}

.mode-switch-btn:hover {
  transform: scale(1.02);
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.15);
}

.upload-audio-btn {
  gap: 6px;
}

.upload-control-icon {
  margin-right: 2px;
  font-size: 16px;
}

.right-controls {
  display: flex;
  align-items: center;
  gap: 12px;
  flex: 1 1 320px;
  min-width: 0;
  justify-content: flex-end;
  flex-wrap: wrap;
}

.bottom-controls.upload-mode-controls {
  align-items: center;
  flex-wrap: nowrap;
}

.bottom-controls.upload-mode-controls.has-upload-media {
  display: grid;
  grid-template-columns: max-content minmax(0, 1fr);
  align-items: center;
  gap: 20px;
  padding: 12px 20px;
}

.upload-mode-controls .left-bottom-controls {
  flex: 1 1 auto;
}

.upload-mode-controls.has-upload-media .left-bottom-controls {
  flex: 0 0 auto;
  flex-direction: column;
  align-items: flex-start;
  gap: 8px;
}

.upload-mode-controls.has-upload-media .bottom-control-group {
  gap: 16px;
}

.upload-mode-controls .right-controls {
  flex: 0 0 auto;
  justify-content: flex-end;
}

.upload-mode-controls.has-upload-media .right-controls {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 44px;
  align-items: center;
  gap: 12px;
  min-width: 0;
  width: 100%;
}

.upload-mode-controls .audio-player-compact {
  flex: 0 1 360px;
}

.upload-mode-controls.has-upload-media .audio-player-compact {
  width: 100%;
  min-width: 0;
  max-width: none;
  height: 48px;
  padding: 0 12px;
  border: 1px solid #e5e7eb;
  border-radius: 24px;
  background: #f8fafc;
}

.upload-mode-controls.has-upload-media .control-btn {
  margin-bottom: 0;
}

.control-btn {
  padding: 8px 16px !important;
  border: 2px solid #000000 !important;
  background: white !important;
  color: #000000 !important;
  border-radius: 20px !important;
  font-size: 14px !important;
  height: auto !important;
  transition: all 0.3s ease !important;
  white-space: nowrap !important;
  flex-shrink: 0;
}

.control-btn:hover {
  background: #000000 !important;
  color: white !important;
}

.record-control-btn {
  background: #1890ff !important;
  border-color: #1890ff !important;
  color: white !important;
}

.record-control-btn:hover {
  background: #40a9ff !important;
  border-color: #40a9ff !important;
  color: white !important;
}

.record-control-btn.recording {
  background: #ff4d4f !important;
  border-color: #ff4d4f !important;
  animation: recording-pulse 2s infinite;
}

.record-control-btn.recording:hover {
  background: #ff7875 !important;
  border-color: #ff7875 !important;
}

@keyframes recording-pulse {
  0%, 100% { box-shadow: 0 2px 8px rgba(255, 77, 79, 0.3); }
  50% { box-shadow: 0 2px 12px rgba(255, 77, 79, 0.6); }
}

.btn-icon {
  margin-right: 6px;
  font-size: 14px;
  display: inline-flex;
  align-items: center;
}

.control-btn .btn-icon {
  color: inherit;
}

.mixed-style {
  background: white !important;
  border: none !important;
  color: #000000 !important;
}

.mixed-style:hover {
  background: rgba(0, 0, 0, 0.1) !important;
  border: none !important;
  color: #000000 !important;
}

.orange-icon {
  background: #ff9500 !important;
  color: white !important;
  padding: 2px 6px !important;
  border-radius: 4px !important;
  margin-right: 6px !important;
}

.blue-icon {
  background: #409eff !important;
  color: white !important;
  padding: 2px 6px !important;
  border-radius: 4px !important;
  margin-right: 6px !important;
}

.purple-icon {
  background: #9f5fb0 !important;
  color: white !important;
  padding: 2px 6px !important;
  border-radius: 4px !important;
  margin-right: 6px !important;
}

.green-icon {
  background: #52c41a !important;
  color: white !important;
  padding: 2px 6px !important;
  border-radius: 4px !important;
  margin-right: 6px !important;
}

.gray-icon {
  background: #8c8c8c !important;
  color: white !important;
  padding: 2px 6px !important;
  border-radius: 4px !important;
  margin-right: 6px !important;
}

.manual-speaker-dialog {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.manual-speaker-tip {
  font-size: 13px;
  line-height: 1.6;
  color: #606266;
  background: #f5f7fa;
  border-radius: 8px;
  padding: 10px 12px;
}

.manual-speaker-hint {
  font-size: 12px;
  color: #909399;
}

.manual-speaker-actions {
  display: flex;
  justify-content: flex-end;
}

.icon-only {
  width: 40px !important;
  height: 40px !important;
  padding: 0 !important;
  display: flex !important;
  align-items: center !important;
  justify-content: center !important;
  border-radius: 50% !important;
}

.icon-only .btn-icon {
  margin: 0 !important;
  font-size: 18px !important;
}

.no-border {
  border: none !important;
  background: transparent !important;
}

.no-border:hover {
  background: rgba(0, 0, 0, 0.1) !important;
  border: none !important;
}

.language-select {
  width: 120px;
}

.language-select :deep(.el-input__wrapper) {
  border: 2px solid #000000;
  border-radius: 20px;
  background: white;
}

.language-select.no-border :deep(.el-input__wrapper) {
  border: none;
  border-radius: 20px;
  background: transparent;
}

.language-select :deep(.el-input__inner) {
  color: #000000;
  font-weight: 500;
}

.language-select :deep(.el-select__caret) {
  color: #000000;
}

.language-select :deep(.el-input__prefix) {
  color: #000000;
  margin-right: 8px;
}

.language-select.no-border:hover :deep(.el-input__wrapper) {
  background: rgba(0, 0, 0, 0.1);
  border: none;
}

.language-selector, .mode-selector {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  border: none;
  border-radius: 20px;
  background: transparent;
  transition: all 0.3s ease;
}

.language-selector:hover, .mode-selector:hover {
  background: rgba(0, 0, 0, 0.1);
}

.language-icon, .mode-icon {
  color: #000000;
  width: 16px;
  height: 16px;
  flex-shrink: 0;
  cursor: pointer;
}

.language-select-custom, .mode-select-custom {
  border: none !important;
  background: transparent !important;
  min-width: 80px;
}

.language-select-custom :deep(.el-input__wrapper), .mode-select-custom :deep(.el-input__wrapper) {
  border: none !important;
  background: transparent !important;
  box-shadow: none !important;
  padding: 0 !important;
}

.language-select-custom :deep(.el-input__inner), .mode-select-custom :deep(.el-input__inner) {
  color: #000000;
  font-weight: 500;
  background: transparent !important;
  border: none !important;
  padding: 0 !important;
}

.language-select-custom :deep(.el-select__caret), .mode-select-custom :deep(.el-select__caret) {
  color: #000000;
}

.no-border-selector {
  border: none !important;
  background: transparent !important;
}

.no-border-selector:hover {
  background: rgba(0, 0, 0, 0.1) !important;
  border: none !important;
}

/* 下拉菜单无边框样式 */
.language-select-custom :deep(.el-select-dropdown) {
  border: none !important;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.1) !important;
}

.language-select-custom :deep(.el-select-dropdown__item) {
  border: none !important;
}

.language-select-custom :deep(.el-popper) {
  border: none !important;
}

/* 设置气泡框样式 */
.settings-content {
  padding: 8px 0;
  max-width: 280px;
}

.setting-item {
  display: flex;
  align-items: center;
  padding: 8px 0;
  border-bottom: 1px solid #f0f0f0;
  gap: 8px;
}

.setting-item:last-child {
  border-bottom: none;
}

.setting-item-action {
  justify-content: space-between;
}

.setting-label {
  font-size: 14px;
  color: #303133;
  font-weight: 500;
  width: 80px;
  flex-shrink: 0;
}

.setting-action-btn {
  margin-left: auto;
}

.hotword-asset-setting {
  align-items: flex-start;
}

.hotword-asset-control {
  min-width: 0;
  flex: 1;
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 6px;
}

.hotword-category-select {
  width: 100%;
}

.hotword-asset-help {
  margin-top: 4px;
}

.help-content.warning {
  color: #b88230;
}

.setting-divider {
  height: 1px;
  background: #e4e7ed;
  margin: 12px 0;
}

.setting-section-title {
  font-size: 13px;
  color: #909399;
  font-weight: 600;
  margin-bottom: 8px;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.setting-help {
  margin-top: 12px;
  padding: 8px;
  background: #f8f9fa;
  border-radius: 4px;
  border-left: 3px solid #409eff;
}

.help-title {
  font-size: 12px;
  font-weight: 600;
  color: #409eff;
  margin-bottom: 4px;
}

.help-content {
  font-size: 11px;
  color: #666;
  line-height: 1.4;
}

.help-content code {
  background: #e6f7ff;
  padding: 1px 4px;
  border-radius: 2px;
  font-family: 'Monaco', 'Menlo', monospace;
  font-size: 10px;
  color: #1890ff;
}

/* 紧凑版音频播放器样式 */
.audio-player-compact {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-right: 0;
  flex: 1 1 280px;
  min-width: 220px;
  max-width: 420px;
}

.audio-player-compact .player-controls {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  background: #f0f0f0;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: all 0.3s ease;
}

.audio-player-compact .player-controls:hover {
  background: #e0e0e0;
}

.audio-player-compact .play-icon {
  font-size: 16px;
  color: #333;
}

.audio-player-compact .player-download {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  background: #f0f0f0;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: all 0.3s ease;
  margin-left: 4px;
}

.audio-player-compact .player-download:hover {
  background: #e0e0e0;
}

.audio-player-compact .download-icon {
  font-size: 16px;
  color: #333;
  transition: color 0.3s ease;
}

.audio-player-compact .player-download:hover .download-icon {
  color: #409eff;
}

.player-progress-compact {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
  flex: 1 1 auto;
}

.player-progress-compact .time {
  font-size: 12px;
  color: #666;
  min-width: 35px;
  text-align: center;
}

.player-progress-compact .progress-bar {
  flex: 1;
  min-width: 72px;
  height: 4px;
  background: #e0e0e0;
  border-radius: 2px;
  position: relative;
  cursor: pointer;
}

@media (max-width: 1280px) {
  .upload-settings-grid {
    grid-template-columns: 1fr 1fr;
  }

  .upload-primary-btn {
    grid-column: 1 / -1;
  }

  .bottom-controls {
    align-items: stretch;
  }

  .left-bottom-controls {
    flex: 1 1 100%;
  }

  .right-controls {
    flex: 1 1 100%;
    justify-content: space-between;
  }

  .audio-player-compact {
    max-width: none;
  }

  .bottom-controls.upload-mode-controls {
    align-items: center;
    flex-wrap: nowrap;
  }

  .upload-mode-controls .left-bottom-controls {
    flex: 1 1 auto;
  }

  .upload-mode-controls .right-controls {
    flex: 0 0 auto;
    justify-content: flex-end;
  }

  .upload-mode-controls .audio-player-compact {
    max-width: 360px;
  }

  .bottom-controls.upload-mode-controls.has-upload-media {
    grid-template-columns: max-content minmax(0, 1fr);
    gap: 16px;
  }

  .upload-mode-controls.has-upload-media .right-controls {
    grid-template-columns: minmax(0, 1fr) 44px;
  }

  .upload-mode-controls.has-upload-media .audio-player-compact {
    min-width: 0;
    max-width: none;
  }
}

@media (max-width: 768px) {
  .upload-setup-main {
    align-items: flex-start;
  }

  .upload-settings-grid {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 768px) {
  .bottom-controls {
    padding: 12px 16px;
    gap: 12px;
  }

  .left-bottom-controls,
  .right-controls {
    gap: 8px;
  }

  .control-btn {
    padding: 8px 12px !important;
    font-size: 13px !important;
  }

  .audio-player-compact {
    min-width: 0;
  }

  .bottom-controls.upload-mode-controls {
    align-items: stretch;
    flex-wrap: wrap;
  }

  .upload-mode-controls .left-bottom-controls,
  .upload-mode-controls .right-controls {
    flex: 1 1 100%;
  }

  .upload-mode-controls .right-controls {
    justify-content: flex-end;
  }

  .upload-mode-controls .audio-player-compact {
    flex: 1 1 100%;
    max-width: none;
  }

  .bottom-controls.upload-mode-controls.has-upload-media {
    display: flex;
    align-items: stretch;
    flex-wrap: wrap;
  }

  .upload-mode-controls.has-upload-media .left-bottom-controls {
    flex: 1 1 100%;
    flex-direction: row;
    align-items: center;
  }

  .upload-mode-controls.has-upload-media .right-controls {
    flex: 1 1 100%;
    display: grid;
    grid-template-columns: minmax(0, 1fr) 44px;
  }

  .upload-mode-controls.has-upload-media .audio-player-compact {
    min-width: 0;
  }

  .player-progress-compact .time {
    min-width: 30px;
    font-size: 11px;
  }
}

.player-progress-compact .progress-bg {
  height: 100%;
  background: #1890ff;
  border-radius: 2px;
  transition: width 0.1s ease;
}

.player-progress-compact .progress-handle {
  position: absolute;
  top: -4px;
  width: 12px;
  height: 12px;
  background: #1890ff;
  border-radius: 50%;
  transform: translateX(-50%);
  cursor: pointer;
}

.batch-edit-content {
  display: flex;
  flex-direction: column;
  gap: 15px;
}

.speaker-review-drawer :deep(.el-drawer__body) {
  padding: 0;
}

.speaker-review-workbench {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: #f8fafc;
}

.speaker-review-header {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  padding: 18px 20px 16px;
  border-bottom: 1px solid #e5e7eb;
  background: #fff;
}

.speaker-review-heading {
  display: flex;
  gap: 12px;
  min-width: 0;
}

.speaker-review-icon,
.speaker-review-avatar {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex: 0 0 auto;
  width: 36px;
  height: 36px;
  border-radius: 50%;
  color: #fff;
}

.speaker-review-icon {
  background: #2563eb;
}

.speaker-review-heading h3 {
  margin: 0;
  font-size: 17px;
  line-height: 1.35;
  color: #111827;
}

.speaker-review-heading p {
  margin: 4px 0 0;
  color: #64748b;
  font-size: 13px;
  line-height: 1.5;
}

.speaker-review-header-actions {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  flex-shrink: 0;
}

.speaker-review-summary {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 10px;
  padding: 14px 20px;
  background: #fff;
  border-bottom: 1px solid #e5e7eb;
}

.speaker-review-stat {
  min-width: 0;
  padding: 10px 12px;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  background: #f8fafc;
}

.speaker-review-stat span {
  display: block;
  color: #64748b;
  font-size: 12px;
}

.speaker-review-stat strong {
  display: block;
  margin-top: 4px;
  color: #111827;
  font-size: 18px;
  line-height: 1.2;
  font-weight: 700;
}

.speaker-review-list {
  display: flex;
  flex: 1;
  flex-direction: column;
  gap: 12px;
  min-height: 0;
  padding: 14px 20px 20px;
  overflow-y: auto;
}

.speaker-review-item {
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 14px;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  background: #fff;
}

.speaker-review-item-header {
  display: flex;
  justify-content: space-between;
  gap: 12px;
}

.speaker-review-identity {
  display: flex;
  gap: 10px;
  min-width: 0;
}

.speaker-review-title {
  display: flex;
  flex-direction: column;
  gap: 6px;
  min-width: 0;
  font-weight: 600;
  color: #303133;
}

.speaker-review-title > span {
  overflow-wrap: anywhere;
}

.speaker-review-samples {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.sample-play-btn {
  display: inline-flex;
  align-items: center;
  min-height: 32px;
  gap: 6px;
  border: 1px solid #dcdfe6;
  background: #f8fafc;
  border-radius: 8px;
  padding: 4px 10px;
  color: #475569;
  cursor: pointer;
  font-size: 12px;
}

.sample-play-btn::before {
  content: '';
  width: 0;
  height: 0;
  border-top: 5px solid transparent;
  border-bottom: 5px solid transparent;
  border-left: 7px solid currentColor;
}

.sample-play-btn:hover {
  color: #1890ff;
  border-color: #91caff;
  background: #f0f7ff;
}

.speaker-review-actions {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  flex-shrink: 0;
}

.speaker-merge-control {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr) auto;
  align-items: center;
  gap: 8px;
  padding-top: 12px;
  border-top: 1px solid #f1f5f9;
}

.speaker-merge-control span {
  color: #64748b;
  font-size: 13px;
}

.speaker-review-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 12px 20px;
  border-top: 1px solid #e5e7eb;
  background: #fff;
  color: #64748b;
  font-size: 12px;
}

@media (max-width: 768px) {
  .speaker-review-drawer {
    width: 100% !important;
  }

  .speaker-review-header,
  .speaker-review-item-header,
  .speaker-review-footer {
    flex-direction: column;
  }

  .speaker-review-header-actions,
  .speaker-review-actions {
    width: 100%;
  }

  .speaker-review-actions .el-button {
    flex: 1;
  }

  .speaker-review-summary {
    grid-template-columns: 1fr;
  }

  .speaker-merge-control {
    grid-template-columns: 1fr;
  }
}

.search-section {
  display: flex;
  flex-direction: column;
  gap: 15px;
}

.input-group {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.input-group label {
  color: #606266;
  font-size: 14px;
  font-weight: 500;
}

.match-info {
  display: flex;
  justify-content: center;
  padding: 10px 0;
}

.dialog-footer-custom {
  display: flex;
  gap: 8px;
  justify-content: center;
  flex-wrap: wrap;
}

.summary-task-progress {
  display: flex;
  flex-direction: column;
  align-items: stretch;
  gap: 6px;
  color: #606266;
  font-size: 12px;
}

/* 黄色高亮样式 */
:deep(.message-bubble .search-highlight),
:deep(.search-highlight) {
  background-color: #ffeb3b !important;
  color: #000 !important;
  padding: 2px 4px;
  border-radius: 2px;
  font-weight: 500;
}

/* 当前选中项高亮样式 - 带边框 */
:deep(.message-bubble .search-highlight-current),
:deep(.search-highlight-current) {
  background-color: #ffeb3b !important;
  color: #000 !important;
  padding: 2px 4px;
  border-radius: 2px;
  font-weight: 700;
  border: 2px solid #ff5722 !important;
  box-shadow: 0 0 8px rgba(255, 87, 34, 0.5);
  animation: highlight-pulse 1s ease-in-out;
}

@keyframes highlight-pulse {
  0%, 100% {
    box-shadow: 0 0 8px rgba(255, 87, 34, 0.5);
  }
  50% {
    box-shadow: 0 0 16px rgba(255, 87, 34, 0.8);
  }
}


</style>
