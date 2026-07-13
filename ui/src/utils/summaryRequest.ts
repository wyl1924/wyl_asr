import type { GenerateSummaryOptions } from './summary'

type LlmServiceType = NonNullable<GenerateSummaryOptions['serviceType']>
export type SummaryTemplateId = 'standard' | 'project_review'

export const SUMMARY_TEMPLATE_STORAGE_KEY = 'meeting_summary_template_id'
export const SUMMARY_TEMPLATE_OPTIONS: Array<{id: SummaryTemplateId; label: string; description: string}> = [
  {
    id: 'standard',
    label: '标准会议纪要',
    description: '保留原有结构化会议纪要模板'
  },
  {
    id: 'project_review',
    label: '方案评审纪要',
    description: '按主题、系统和方案归类，输出会议主题、发言人、摘要和待办'
  }
]

export function normalizeSummaryTemplateId(templateId?: string | null): SummaryTemplateId {
  return SUMMARY_TEMPLATE_OPTIONS.some(option => option.id === templateId)
    ? templateId as SummaryTemplateId
    : 'standard'
}

export function getSummaryTemplateIdFromLocalStorage(): SummaryTemplateId {
  if (typeof localStorage === 'undefined') return 'standard'
  return normalizeSummaryTemplateId(localStorage.getItem(SUMMARY_TEMPLATE_STORAGE_KEY))
}

export function setSummaryTemplateIdToLocalStorage(templateId: string): SummaryTemplateId {
  const normalized = normalizeSummaryTemplateId(templateId)
  if (typeof localStorage !== 'undefined') {
    localStorage.setItem(SUMMARY_TEMPLATE_STORAGE_KEY, normalized)
  }
  return normalized
}

interface SummarySettings {
  serviceType?: string
  templateId?: string
  ollamaEndpoint?: string
  ollamaModel?: string
  xinferenceEndpoint?: string
  xinferenceModel?: string
  xinferenceApiKey?: string
  vllmEndpoint?: string
  vllmModel?: string
  vllmApiKey?: string
  sglangEndpoint?: string
  sglangModel?: string
  sglangApiKey?: string
}

export interface SummarySpeakerSegment {
  speaker?: string
  text?: string
  timestamp?: unknown
  startTime?: string
  endTime?: string
}

const DEFAULT_SUMMARY_SETTINGS = {
  serviceType: 'xinference',
  ollamaEndpoint: 'https://10.1.0.27/ollama/api/chat',
  ollamaModel: 'qwen3:30b-a3b-q4_K_M',
  xinferenceEndpoint: 'http://10.1.0.26:9997/v1/chat/completions',
  xinferenceModel: 'DeepSeek-R1-671B-1',
  vllmEndpoint: 'http://localhost:8000/v1/chat/completions',
  vllmModel: 'meta-llama/Llama-2-7b-chat-hf',
  sglangEndpoint: 'http://localhost:30000/v1/chat/completions',
  sglangModel: 'meta-llama/Llama-2-7b-chat-hf'
}

const LLM_SERVICE_TYPES: LlmServiceType[] = ['ollama', 'xinference', 'vllm', 'sglang']

function normalizeServiceType(serviceType?: string): LlmServiceType {
  return LLM_SERVICE_TYPES.includes(serviceType as LlmServiceType)
    ? serviceType as LlmServiceType
    : 'ollama'
}

export function buildSummaryOptionsFromSettings(settings: SummarySettings = {}): GenerateSummaryOptions {
  const serviceType = normalizeServiceType(settings.serviceType || DEFAULT_SUMMARY_SETTINGS.serviceType)
  const options: GenerateSummaryOptions = {
    serviceType,
    templateId: normalizeSummaryTemplateId(settings.templateId),
    useBackendStoredConfig: true
  }

  switch (serviceType) {
    case 'ollama':
      options.ollamaConfig = {
        endpoint: settings.ollamaEndpoint || DEFAULT_SUMMARY_SETTINGS.ollamaEndpoint,
        model: settings.ollamaModel || DEFAULT_SUMMARY_SETTINGS.ollamaModel
      }
      break
    case 'xinference':
      options.xinferenceConfig = {
        endpoint: settings.xinferenceEndpoint || DEFAULT_SUMMARY_SETTINGS.xinferenceEndpoint,
        model: settings.xinferenceModel || DEFAULT_SUMMARY_SETTINGS.xinferenceModel,
        apiKey: settings.xinferenceApiKey || undefined
      }
      break
    case 'vllm':
      options.vllmConfig = {
        endpoint: settings.vllmEndpoint || DEFAULT_SUMMARY_SETTINGS.vllmEndpoint,
        model: settings.vllmModel || DEFAULT_SUMMARY_SETTINGS.vllmModel,
        apiKey: settings.vllmApiKey || undefined
      }
      break
    case 'sglang':
      options.sglangConfig = {
        endpoint: settings.sglangEndpoint || DEFAULT_SUMMARY_SETTINGS.sglangEndpoint,
        model: settings.sglangModel || DEFAULT_SUMMARY_SETTINGS.sglangModel,
        apiKey: settings.sglangApiKey || undefined
      }
      break
  }

  return options
}

export function buildSummaryOptionsFromLocalStorage(): GenerateSummaryOptions {
  return {
    templateId: getSummaryTemplateIdFromLocalStorage(),
    useBackendStoredConfig: true
  }
}

export function stripHtmlTags(text = ''): string {
  return text.replace(/<[^>]*>/g, '')
}

function containsCjk(text: string): boolean {
  return /[\u4e00-\u9fff]/.test(text)
}

function looksLikeEnglishTranslation(text: string): boolean {
  const letters = (text.match(/[A-Za-z]/g) || []).length
  const englishWords = (text.match(/[A-Za-z]{2,}/g) || []).length
  const cjk = (text.match(/[\u4e00-\u9fff]/g) || []).length
  return letters >= 40 && englishWords >= 8 && letters > cjk * 3
}

export function stripTranslationsForSummary(transcript = ''): string {
  let hasCjkContext = false
  const withoutLabeledTranslations = transcript
    .split(/\r?\n/)
    .filter(line => {
      const trimmed = line.trim()
      if (/^\s*(翻译|译文|Translation|Translated)\s*[:：]/i.test(trimmed)) {
        return false
      }

      if (containsCjk(trimmed)) {
        hasCjkContext = true
        return true
      }

      if (hasCjkContext && looksLikeEnglishTranslation(trimmed)) {
        return false
      }

      return true
    })
    .join('\n')

  const blocks = withoutLabeledTranslations
    .split(/(?:\r?\n){2,}/)
    .map(block => block.trim())
    .filter(Boolean)

  while (
    blocks.length > 1 &&
    containsCjk(blocks.slice(0, -1).join('\n\n')) &&
    looksLikeEnglishTranslation(blocks[blocks.length - 1])
  ) {
    blocks.pop()
  }

  return blocks.join('\n\n').trim()
}

export function hasSummarySpeakerSegments(segments: SummarySpeakerSegment[]): boolean {
  return segments.some(segment => segment.speaker && segment.speaker.trim() !== '')
}

export function getSummaryCharCount(
  transcript: string,
  speakerSegments: SummarySpeakerSegment[],
  useSpeakerSegments = true
): number {
  if (useSpeakerSegments && speakerSegments.length > 0 && hasSummarySpeakerSegments(speakerSegments)) {
    return speakerSegments.reduce(
      (total, segment) => total + stripTranslationsForSummary(stripHtmlTags(segment.text || '')).length,
      0
    )
  }

  return stripTranslationsForSummary(transcript).length
}

export function buildTranscriptForSummary(
  transcript: string,
  speakerSegments: SummarySpeakerSegment[],
  options: {
    useSpeakerSegments?: boolean
    formatTimeRange?: (segment: SummarySpeakerSegment) => string
  } = {}
): string {
  const useSpeakerSegments = options.useSpeakerSegments ?? true

  if (!useSpeakerSegments || speakerSegments.length === 0 || !hasSummarySpeakerSegments(speakerSegments)) {
    return stripTranslationsForSummary(transcript)
  }

  const formatTimeRange = options.formatTimeRange || defaultFormatTimeRange

  return speakerSegments
    .map(segment => {
      const cleanText = stripTranslationsForSummary(stripHtmlTags(segment.text || ''))
      if (!cleanText) {
        return ''
      }
      const speaker = segment.speaker || '未知说话人'
      return `[${speaker}] (${formatTimeRange(segment)})\n${cleanText}`
    })
    .filter(Boolean)
    .join('\n\n')
}

function defaultFormatTimeRange(segment: SummarySpeakerSegment): string {
  if (segment.startTime && segment.endTime) {
    return `${segment.startTime} - ${segment.endTime}`
  }

  const timestamps = segment.timestamp
  if (Array.isArray(timestamps) && timestamps.length > 0) {
    const first = timestamps[0]
    const last = timestamps[timestamps.length - 1]

    if (Array.isArray(first) && Array.isArray(last)) {
      return `${formatMilliseconds(Number(first[0] || 0))} - ${formatMilliseconds(Number(last[1] || 0))}`
    }
  }

  return typeof timestamps === 'string' ? timestamps : '00:00'
}

function formatMilliseconds(ms: number): string {
  const totalSeconds = Math.floor(ms / 1000)
  const hours = Math.floor(totalSeconds / 3600)
  const minutes = Math.floor((totalSeconds % 3600) / 60)
  const seconds = totalSeconds % 60
  return `${hours.toString().padStart(2, '0')}:${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}`
}
