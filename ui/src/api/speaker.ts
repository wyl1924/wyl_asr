import { API_ENDPOINTS } from '../config/api'

/**
 * 说话人管理API接口
 */

export interface SpeakerInfo {
  speaker_id: string
  speaker_name: string
  description?: string
  registration_time: string
  audio_samples: number
  last_updated: string
}

export interface RegisterSpeakerRequest {
  speaker_name: string
  description?: string
  overwrite?: boolean
  audio_data?: string  // Base64编码的音频数据
  audio_file_path?: string  // 音频文件路径
}

export interface UploadedSegmentRegistrationAudio {
  file_name?: string
  source_file_name?: string
  time_base?: string
}

export interface UploadedSegmentRange {
  start_ms: number
  end_ms: number
}

export interface RegisterUploadedSegmentRequest {
  speaker_name: string
  description?: string
  overwrite?: boolean
  registration_audio?: UploadedSegmentRegistrationAudio
  segments?: UploadedSegmentRange[]
  start_ms?: number
  end_ms?: number
  duration_ms?: number
  max_duration_ms?: number
}

export interface RegisterSpeakerResponse {
  success: boolean
  message: string
  speaker_info?: SpeakerInfo
  embedding_shape?: number[]
}

export interface IdentifySpeakerRequest {
  audio_data?: string  // Base64编码的音频数据
  audio_file_path?: string  // 音频文件路径
  top_k?: number
}

export interface SpeakerCandidate {
  speaker_name: string
  similarity: number
  speaker_info: SpeakerInfo
}

export interface IdentifySpeakerResponse {
  success: boolean
  message?: string
  best_match?: SpeakerCandidate
  candidates: SpeakerCandidate[]
  threshold: number
  query_embedding_shape?: number[]
}

export interface ListSpeakersResponse {
  speakers: SpeakerInfo[]
  count: number
}

export interface DeleteSpeakerRequest {
  speaker_name: string
}

export interface DeleteSpeakerResponse {
  success: boolean
  message: string
}

/**
 * 注册说话人声纹
 */
export async function registerSpeaker(data: RegisterSpeakerRequest): Promise<RegisterSpeakerResponse> {
  const response = await fetch(API_ENDPOINTS.SPEAKER.REGISTER, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json'
    },
    body: JSON.stringify(data)
  })
  
  const result = await response.json()
  
  if (!response.ok) {
    throw new Error(result.message || '注册失败')
  }
  
  return result.data
}

/**
 * 从上传识别文件的时间片段注册说话人声纹
 */
export async function registerSpeakerFromUploadedSegment(data: RegisterUploadedSegmentRequest): Promise<RegisterSpeakerResponse> {
  const response = await fetch(API_ENDPOINTS.SPEAKER.REGISTER_UPLOADED_SEGMENT, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json'
    },
    body: JSON.stringify(data)
  })

  const result = await response.json()

  if (!response.ok) {
    throw new Error(result.message || '注册失败')
  }

  return result.data
}

/**
 * 获取已注册说话人列表
 */
export async function listSpeakers(): Promise<ListSpeakersResponse> {
  const response = await fetch(API_ENDPOINTS.SPEAKER.LIST)
  const result = await response.json()
  
  if (!response.ok) {
    throw new Error(result.message || '获取列表失败')
  }
  
  return result.data
}

/**
 * 识别说话人
 */
export async function identifySpeaker(data: IdentifySpeakerRequest): Promise<IdentifySpeakerResponse> {
  const response = await fetch(API_ENDPOINTS.SPEAKER.IDENTIFY, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json'
    },
    body: JSON.stringify(data)
  })
  
  const result = await response.json()
  
  if (!response.ok) {
    throw new Error(result.message || '识别失败')
  }
  
  return result.data
}

/**
 * 删除说话人
 */
export async function deleteSpeaker(data: DeleteSpeakerRequest): Promise<DeleteSpeakerResponse> {
  const response = await fetch(API_ENDPOINTS.SPEAKER.DELETE, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(data),
  })

  if (!response.ok) {
    throw new Error(`删除失败: ${response.status} ${response.statusText}`)
  }

  return await response.json()
}

/**
 * 将Blob转换为Base64字符串
 */
export function blobToBase64(blob: Blob): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => {
      const result = reader.result as string
      // 移除 data:audio/*;base64, 前缀
      const base64 = result.split(',')[1]
      resolve(base64)
    }
    reader.onerror = reject
    reader.readAsDataURL(blob)
  })
}

/**
 * 将File转换为Base64字符串
 */
export function fileToBase64(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => {
      const result = reader.result as string
      // 移除 data:audio/*;base64, 前缀
      const base64 = result.split(',')[1]
      resolve(base64)
    }
    reader.onerror = reject
    reader.readAsDataURL(file)
  })
}

/**
 * 格式化文件大小
 */
export function formatFileSize(bytes: number): string {
  if (bytes === 0) return '0 B'
  const k = 1024
  const sizes = ['B', 'KB', 'MB', 'GB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i]
}

/**
 * 格式化日期
 */
export function formatDate(dateString: string): string {
  return new Date(dateString).toLocaleString('zh-CN')
}
