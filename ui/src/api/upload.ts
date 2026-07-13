// 文件上传相关接口
import { API_ENDPOINTS, SERVER_CONFIG } from '../config/api'

export interface UploadResponse {
  success: boolean
  data: {
    url: string
  }
  error?: string
}

export interface UploadedAudioSegment {
  speaker: string
  speaker_type?: string
  speaker_confidence?: number
  text: string
  translation?: string
  mode: string
  timestamp?: number[][]
  asr_timestamp?: number[][]
  startTime?: string
  endTime?: string
  startMs?: number
  endMs?: number
}

export interface UploadedSpeakerSample {
  index: number
  speaker: string
  text: string
  start_ms?: number
  end_ms?: number
  start_label?: string
  duration_ms: number
  quality?: 'good' | 'usable' | 'short'
  audio_url: string
}

export interface UploadedSpeakerCandidate {
  speaker: string
  display_name: string
  segment_count: number
  total_duration_ms: number
  total_duration_label?: string
  sample_segments: UploadedSpeakerSample[]
}

export interface UploadedAudioRegistrationRef {
  file_name?: string
  source_file_name?: string
  time_base?: string
  sample_rate?: number
  channels?: number
}

export interface UploadedTextCorrection {
  from: string
  to: string
  count?: number
}

export interface AudioRecognitionData {
  task_id?: string
  file_name: string
  mode?: string
  text: string
  plain_text: string
  translation?: string
  plain_translation?: string
  translation_enabled?: boolean
  confidence?: number
  language: string
  speaker_name?: string
  speaker_type?: string
  speaker_confidence?: number
  segments: UploadedAudioSegment[]
  timestamp?: number[][]
  registration_audio?: UploadedAudioRegistrationRef
  source_audio?: {
    file_name?: string
    saved_file_name?: string
    duration?: number
    format?: string
    codec?: string
    size?: number
  }
  asr_metadata?: {
    mode?: string
    model?: string
    sentence_count?: number
    has_timestamp?: boolean
    has_translation?: boolean
    voiceprint_matching_enabled?: boolean
    text_correction_count?: number
    text_correction_details?: UploadedTextCorrection[]
  }
}

export interface AudioRecognitionTask {
  task_id: string
  file_name: string
  saved_file_name: string
  status: 'queued' | 'running' | 'succeeded' | 'failed' | 'cancelled'
  progress: number
  stage?: string
  queue_position?: number | null
  error?: string
  result?: AudioRecognitionData | null
  media_info?: Record<string, any>
  min_speakers?: number | null
  max_speakers?: number | null
  created_at?: string
  updated_at?: string
  completed_at?: string
}

export interface AudioRecognitionResponse {
  success: boolean
  data: AudioRecognitionData | null
  task?: AudioRecognitionTask | null
  error?: string
}

export interface ApplyUploadedCorrectionsResponse {
  correction_count: number
  correction_details: UploadedTextCorrection[]
  result: AudioRecognitionData
}

const API_BASE_URL = `${SERVER_CONFIG.DB_BASE_URL}/api`

async function readApiPayload<T>(response: Response): Promise<T> {
  const payload = await response.json().catch(() => null)
  if (!response.ok) {
    throw new Error(payload?.message || payload?.error || `HTTP error! status: ${response.status}`)
  }
  return payload?.data as T
}

function sleep(ms: number) {
  return new Promise(resolve => setTimeout(resolve, ms))
}

const DEFAULT_AUDIO_TASK_TIMEOUT_MS = 2 * 60 * 60 * 1000
const DEFAULT_AUDIO_STAGE_STALL_TIMEOUTS_MS: Record<string, number> = {
  speaker: 60 * 60 * 1000
}

function createAbortError(): Error {
  const error = new Error('上传识别已取消')
  error.name = 'AbortError'
  return error
}

function absoluteApiUrl(path: string): string {
  if (/^https?:\/\//.test(path)) return path
  return `${SERVER_CONFIG.DB_BASE_URL}${path.startsWith('/') ? path : `/${path}`}`
}

function normalizeTaskStage(stage?: string): string {
  const normalizedStage = (stage || '').trim().toLowerCase()
  if (!normalizedStage) return ''
  if (normalizedStage === 'speaker' || normalizedStage.includes('说话人')) return 'speaker'
  if (normalizedStage === 'translation' || normalizedStage.includes('翻译')) return 'translation'
  if (normalizedStage === 'asr' || normalizedStage.includes('识别')) return 'asr'
  if (normalizedStage === 'prepare' || normalizedStage.includes('准备')) return 'prepare'
  return normalizedStage
}

function taskProgressSignature(task: AudioRecognitionTask): string {
  return [
    task.status,
    task.stage || '',
    task.progress ?? '',
    task.updated_at || ''
  ].join('|')
}

export const uploadApi = {
  // 上传录音文件
  uploadAudio: async (audioFile: Blob): Promise<UploadResponse> => {
    try {
      const formData = new FormData()
      formData.append('file', audioFile, 'audio.wav')

      const response = await fetch(`${API_BASE_URL}/upload/audio`, {
        method: 'POST',
        body: formData
      })

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`)
      }

      const data = await response.json()
      return {
        success: true,
        data: {
          url: data.url
        }
      }
    } catch (error) {
      console.error('Error uploading audio:', error)
      return {
        success: false,
        data: {
          url: ''
        },
        error: error instanceof Error ? error.message : '上传音频文件失败'
      }
    }
  },

  // 上传文本文件
  uploadText: async (textFile: Blob): Promise<UploadResponse> => {
    try {
      const formData = new FormData()
      formData.append('file', textFile, 'text.txt')

      const response = await fetch(`${API_BASE_URL}/upload/text`, {
        method: 'POST',
        body: formData
      })

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`)
      }

      const data = await response.json()
      return {
        success: true,
        data: {
          url: data.url
        }
      }
    } catch (error) {
      console.error('Error uploading text:', error)
      return {
        success: false,
        data: {
          url: ''
        },
        error: error instanceof Error ? error.message : '上传文本文件失败'
      }
    }
  },

  recognizeAudio: async (
    audioFile: File,
    options: {
      language?: string
      enableSpeakerDiarization?: boolean
      enableVoiceprintMatching?: boolean
      enableTranslation?: boolean
      speakerTopK?: number
      expectedSpeakers?: number | null
      minSpeakers?: number | null
      maxSpeakers?: number | null
      hotwords?: string
      includeDefaultHotwords?: boolean
      onTaskProgress?: (task: AudioRecognitionTask) => void
      signal?: AbortSignal
      taskTimeoutMs?: number
      taskStageStallTimeoutsMs?: Record<string, number>
      pollIntervalMs?: number
    } = {}
  ): Promise<AudioRecognitionResponse> => {
    try {
      const formData = new FormData()
      formData.append('file', audioFile, audioFile.name || 'audio.wav')
      formData.append('language', options.language || 'zh')
      formData.append('enable_speaker_diarization', 'true')
      formData.append('enable_voiceprint_matching', String(options.enableVoiceprintMatching ?? false))
      formData.append('enable_translation', String(options.enableTranslation ?? false))
      formData.append('speaker_top_k', String(options.speakerTopK ?? 3))
      formData.append('async_task', 'true')
      if (options.expectedSpeakers && options.expectedSpeakers >= 2) {
        formData.append('expected_speakers', String(options.expectedSpeakers))
      }
      if (options.minSpeakers && options.minSpeakers >= 2) {
        formData.append('min_speakers', String(options.minSpeakers))
      }
      if (options.maxSpeakers && options.maxSpeakers >= 2) {
        formData.append('max_speakers', String(options.maxSpeakers))
      }
      if (options.hotwords?.trim()) {
        formData.append('hotwords', options.hotwords)
      }
      if (options.includeDefaultHotwords !== undefined) {
        formData.append('include_default_hotwords', String(options.includeDefaultHotwords))
      }

      const response = await fetch(API_ENDPOINTS.UPLOAD.AUDIO_RECOGNIZE, {
        method: 'POST',
        body: formData,
        signal: options.signal
      })

      const createdTask = await readApiPayload<AudioRecognitionTask>(response)
      options.onTaskProgress?.(createdTask)
      const finishedTask = await uploadApi.pollAudioTask(createdTask.task_id, options.onTaskProgress, {
        signal: options.signal,
        timeoutMs: options.taskTimeoutMs,
        intervalMs: options.pollIntervalMs,
        stageStallTimeoutsMs: options.taskStageStallTimeoutsMs
      })
      if (finishedTask.status === 'failed') {
        throw new Error(finishedTask.error || '上传音频识别失败')
      }
      if (finishedTask.status === 'cancelled') {
        return {
          success: false,
          data: null,
          task: finishedTask,
          error: finishedTask.error || '上传识别已取消'
        }
      }

      return {
        success: true,
        data: finishedTask.result || null,
        task: finishedTask
      }
    } catch (error) {
      console.error('Error recognizing uploaded audio:', error)
      if ((error as Error).name === 'AbortError') {
        return {
          success: false,
          data: null,
          task: null,
          error: '上传识别已取消'
        }
      }
      return {
        success: false,
        data: null,
        task: null,
        error: error instanceof Error ? error.message : '上传音频识别失败'
      }
    }
  },

  getAudioTask: async (taskId: string, signal?: AbortSignal): Promise<AudioRecognitionTask> => {
    const response = await fetch(`${API_ENDPOINTS.UPLOAD.AUDIO_TASKS}/${encodeURIComponent(taskId)}`, { signal })
    return await readApiPayload<AudioRecognitionTask>(response)
  },

  cancelAudioTask: async (taskId: string): Promise<AudioRecognitionTask> => {
    const response = await fetch(`${API_ENDPOINTS.UPLOAD.AUDIO_TASKS}/${encodeURIComponent(taskId)}`, {
      method: 'DELETE'
    })
    return await readApiPayload<AudioRecognitionTask>(response)
  },

  pollAudioTask: async (
    taskId: string,
    onTaskProgress?: (task: AudioRecognitionTask) => void,
    options: {
      timeoutMs?: number
      intervalMs?: number
      signal?: AbortSignal
      stageStallTimeoutsMs?: Record<string, number>
    } = {}
  ): Promise<AudioRecognitionTask> => {
    const timeoutMs = options.timeoutMs ?? DEFAULT_AUDIO_TASK_TIMEOUT_MS
    const intervalMs = options.intervalMs ?? 1500
    const stageStallTimeoutsMs = {
      ...DEFAULT_AUDIO_STAGE_STALL_TIMEOUTS_MS,
      ...(options.stageStallTimeoutsMs || {})
    }
    const startedAt = Date.now()
    let lastProgressSignature = ''
    let lastProgressAt = startedAt

    for (;;) {
      if (Date.now() - startedAt > timeoutMs) {
        throw new Error('上传音频识别任务超时')
      }
      if (options.signal?.aborted) {
        throw createAbortError()
      }
      const task = await uploadApi.getAudioTask(taskId, options.signal)
      onTaskProgress?.(task)
      if (task.status === 'succeeded' || task.status === 'failed' || task.status === 'cancelled') {
        return task
      }

      const signature = taskProgressSignature(task)
      if (signature !== lastProgressSignature) {
        lastProgressSignature = signature
        lastProgressAt = Date.now()
      }
      const stageKey = normalizeTaskStage(task.stage)
      const stallTimeoutMs = stageStallTimeoutsMs[stageKey]
      if (task.status === 'running' && stallTimeoutMs && Date.now() - lastProgressAt > stallTimeoutMs) {
        try {
          await uploadApi.cancelAudioTask(taskId)
        } catch (cancelError) {
          console.warn('Cancel stalled upload task failed:', cancelError)
        }
        const timeoutMinutes = Math.max(1, Math.round(stallTimeoutMs / 60000))
        throw new Error(`说话人整理超过 ${timeoutMinutes} 分钟没有进展，已自动取消本次上传识别。请缩短文件、关闭声纹匹配，或调高后端 UPLOAD_SPEAKER_MAX_VAD_SEGMENTS 后重试。`)
      }
      await sleep(intervalMs)
    }
  },

  fetchSpeakerCandidates: async (taskId: string): Promise<UploadedSpeakerCandidate[]> => {
    const response = await fetch(`${API_ENDPOINTS.UPLOAD.AUDIO_TASKS}/${encodeURIComponent(taskId)}/speaker-candidates`)
    const data = await readApiPayload<{ candidates: UploadedSpeakerCandidate[] }>(response)
    return data.candidates || []
  },

  renameUploadedSpeaker: async (taskId: string, speaker: string, name: string): Promise<AudioRecognitionData> => {
    const response = await fetch(
      `${API_ENDPOINTS.UPLOAD.AUDIO_TASKS}/${encodeURIComponent(taskId)}/speakers/${encodeURIComponent(speaker)}`,
      {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name })
      }
    )
    const data = await readApiPayload<{ result: AudioRecognitionData }>(response)
    return data.result
  },

  renameUploadedSegmentSpeaker: async (taskId: string, segmentIndex: number, name: string): Promise<AudioRecognitionData> => {
    const response = await fetch(
      `${API_ENDPOINTS.UPLOAD.AUDIO_TASKS}/${encodeURIComponent(taskId)}/segments/${segmentIndex}/speaker`,
      {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name })
      }
    )
    const data = await readApiPayload<{ result: AudioRecognitionData }>(response)
    return data.result
  },

  mergeUploadedSpeakers: async (taskId: string, from: string, into: string): Promise<AudioRecognitionData> => {
    const response = await fetch(
      `${API_ENDPOINTS.UPLOAD.AUDIO_TASKS}/${encodeURIComponent(taskId)}/speakers/merge`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ from, into })
      }
    )
    const data = await readApiPayload<{ result: AudioRecognitionData }>(response)
    return data.result
  },

  applyUploadedCorrections: async (
    taskId: string,
    options: {
      corrections?: UploadedTextCorrection[] | Record<string, string> | string
      replacements?: UploadedTextCorrection[] | Record<string, string> | string
      useDefault?: boolean
      includeConfigFile?: boolean
    } = {}
  ): Promise<ApplyUploadedCorrectionsResponse> => {
    const response = await fetch(
      `${API_ENDPOINTS.UPLOAD.AUDIO_TASKS}/${encodeURIComponent(taskId)}/corrections`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          corrections: options.corrections,
          replacements: options.replacements,
          use_default: options.useDefault ?? false,
          include_config_file: options.includeConfigFile ?? false
        })
      }
    )
    return await readApiPayload<ApplyUploadedCorrectionsResponse>(response)
  },

  segmentAudioUrl: (sample: UploadedSpeakerSample): string => absoluteApiUrl(sample.audio_url)
}
