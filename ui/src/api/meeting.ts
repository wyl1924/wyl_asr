// 会议管理相关接口
import { SERVER_CONFIG } from '../config/api'

export interface Meeting {
  id?: number
  title: string
  fileName: string
  audioUrl?: string
  transcriptionContent?: string
  meetingMinutes?: string
  recognitionMode?: string
  transcription_source?: 'realtime' | 'upload' | string
  uploadTaskId?: string
  startTime: string
  endTime?: string
  duration?: string
  status: 'recording' | 'completed' | 'processing'
  createdAt?: string
  updatedAt?: string
}

export interface UploadedMeetingTranscriptionSegment {
  task_id?: string
  segment_index: number
  speaker: string
  speaker_type?: string
  speaker_confidence?: number
  text: string
  translation?: string
  mode: string
  timestamp?: number[][]
  startTime?: string
  endTime?: string
  startMs?: number
  endMs?: number
  speaker_result?: Record<string, any> | null
}

export interface UploadedMeetingTranscription {
  meeting_id: number
  source: 'realtime' | 'upload'
  task_id?: string | null
  task_ids: string[]
  file_names: string[]
  segments: UploadedMeetingTranscriptionSegment[]
  text: string
  plain_text: string
}

export interface MeetingResponse {
  success: boolean
  data?: Meeting
  message?: string
  error?: string
}

export interface MeetingListResponse {
  success: boolean
  data?: Meeting[]
  message?: string
  error?: string
}

export interface MeetingMinutesVersion {
  id: number
  meeting_id: number
  version: number
  summary: string
  instruction?: string
  source_version_id?: number | null
  is_current: boolean
  created_at?: string
}

export interface MeetingDocumentInfo {
  id: number
  meeting_id: number
  filename: string
  type: string
  file_path: string
  file_size: number
  created_time: string
  updated_time: string
  download_url: string
}

const API_BASE_URL = `${SERVER_CONFIG.DB_BASE_URL}/api`
export type MeetingDownloadFormat = 'original' | 'md' | 'docx' | 'word' | 'pdf'

type MeetingDocumentUrlSource = {
  id?: number | string | null
  file_path?: string | null
  filename?: string | null
  file_name?: string | null
}

const getFilenameFromContentDisposition = (contentDisposition: string | null): string | null => {
  if (!contentDisposition) return null
  const utf8Match = contentDisposition.match(/filename\*=UTF-8''([^;]+)/i)
  if (utf8Match?.[1]) {
    return decodeURIComponent(utf8Match[1])
  }
  const filenameMatch = contentDisposition.match(/filename="?([^";]+)"?/i)
  return filenameMatch?.[1] || null
}

const triggerBlobDownload = (blob: Blob, fileName: string) => {
  const blobUrl = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = blobUrl
  link.download = fileName
  link.style.display = 'none'
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
  URL.revokeObjectURL(blobUrl)
}

const getExtensionForDownloadFormat = (format?: MeetingDownloadFormat): string | null => {
  if (format === 'docx' || format === 'word') return '.docx'
  if (format === 'pdf') return '.pdf'
  if (format === 'md') return '.md'
  return null
}

const replaceFileExtension = (fileName: string, extension: string): string => {
  const slashIndex = Math.max(fileName.lastIndexOf('/'), fileName.lastIndexOf('\\'))
  const dotIndex = fileName.lastIndexOf('.')
  if (dotIndex > slashIndex) {
    return `${fileName.slice(0, dotIndex)}${extension}`
  }
  return `${fileName}${extension}`
}

const getDownloadFileName = (
  response: Response,
  fallbackName: string | undefined,
  format?: MeetingDownloadFormat
): string => {
  const headerName = getFilenameFromContentDisposition(response.headers.get('Content-Disposition'))
  if (headerName) return headerName

  const extension = getExtensionForDownloadFormat(format)
  if (fallbackName && extension) {
    return replaceFileExtension(fallbackName, extension)
  }
  return fallbackName || `meeting-document${extension || ''}`
}

const readApiErrorMessage = async (response: Response): Promise<string> => {
  try {
    const payload = await response.json()
    return payload.message || `HTTP error! status: ${response.status}`
  } catch {
    return `HTTP error! status: ${response.status}`
  }
}

export const buildMeetingDocumentUrl = (
  document: MeetingDocumentUrlSource,
  options: {
    inline?: boolean
    format?: MeetingDownloadFormat
  } = {}
): string => {
  const params = new URLSearchParams()
  if (document.id !== undefined && document.id !== null && String(document.id) !== '') {
    params.append('document_id', String(document.id))
  } else if (document.file_path) {
    params.append('file_path', document.file_path)
  }

  const fileName = document.filename || document.file_name
  if (fileName) {
    params.append('file_name', fileName)
  }
  if (options.inline) {
    params.append('inline', '1')
  }
  if (options.format && options.format !== 'original') {
    params.append('format', options.format)
  }

  return `${API_BASE_URL}/meetings/documents/download?${params.toString()}`
}

export const meetingApi = {
  // 综合保存会议接口（支持音频文件上传和JSON数据）
  saveCompleteMeeting: async (meetingData: {
    title: string
    description?: string
    participants?: string
    location?: string
    transcriptionContent?: string
    meetingMinutes?: string
    summary?: string
    keyPoints?: string[]
    actionItems?: string[]
    decisions?: string[]
    audioFile?: File | Blob
    audioFileName?: string
    audioFilePath?: string
    audioFileSize?: number
    uploadTaskId?: string
    audioFormat?: string
    sampleRate?: number
    channels?: number
    confidence?: number
    startTime?: number
    endTime?: number
    speakerId?: string
    language?: string
    recognitionMode?: string
  }): Promise<MeetingResponse> => {
    try {
      let requestOptions: RequestInit;
      
      // 如果包含音频文件，使用FormData格式
      if (meetingData.audioFile) {
        const formData = new FormData();
        
        // 添加基本信息
        formData.append('title', meetingData.title);
        if (meetingData.description) formData.append('description', meetingData.description);
        if (meetingData.participants) formData.append('participants', meetingData.participants);
        if (meetingData.location) formData.append('location', meetingData.location);
        
        // 添加音频文件
        formData.append('audioFile', meetingData.audioFile, meetingData.audioFileName || 'audio.wav');
        if (meetingData.audioFormat) formData.append('audioFormat', meetingData.audioFormat);
        if (meetingData.sampleRate) formData.append('sampleRate', meetingData.sampleRate.toString());
        if (meetingData.channels) formData.append('channels', meetingData.channels.toString());
        
        // 添加转录内容
        if (meetingData.transcriptionContent) {
          formData.append('transcriptionContent', meetingData.transcriptionContent);
        }
        
        // 添加会议纪要
        if (meetingData.meetingMinutes) {
          formData.append('meetingMinutes', meetingData.meetingMinutes);
        }
        if (meetingData.summary) {
          formData.append('summary', meetingData.summary);
        }
        
        // 添加其他可选字段
        if (meetingData.confidence) formData.append('confidence', meetingData.confidence.toString());
        if (meetingData.startTime) formData.append('startTime', meetingData.startTime.toString());
        if (meetingData.endTime) formData.append('endTime', meetingData.endTime.toString());
        if (meetingData.speakerId) formData.append('speakerId', meetingData.speakerId);
        if (meetingData.language) formData.append('language', meetingData.language);
        if (meetingData.recognitionMode) formData.append('recognitionMode', meetingData.recognitionMode);
        
        // 添加结构化数据（转换为JSON字符串）
        if (meetingData.keyPoints) formData.append('keyPoints', JSON.stringify(meetingData.keyPoints));
        if (meetingData.actionItems) formData.append('actionItems', JSON.stringify(meetingData.actionItems));
        if (meetingData.decisions) formData.append('decisions', JSON.stringify(meetingData.decisions));
        
        requestOptions = {
          method: 'POST',
          body: formData
        };
      } else {
        // 使用JSON格式
        requestOptions = {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json'
          },
          body: JSON.stringify(meetingData)
        };
      }
      
      const response = await fetch(`${API_BASE_URL}/meetings/save-complete`, requestOptions);
      
      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.message || `HTTP error! status: ${response.status}`);
      }
      
      const result = await response.json();
      return {
        success: true,
        data: result.data,
        message: result.message
      };
    } catch (error) {
      console.error('综合保存会议失败:', error);
      return {
        success: false,
        error: error instanceof Error ? error.message : '未知错误'
      };
    }
  },

  // 保存会议文档到本地文件夹（不存数据库）
  saveMeetingDocuments: async (meetingData: {
    title: string
    description?: string
    participants?: string
    transcriptionContent?: string
    meetingMinutes?: string
    summary?: string
    keyPoints?: string[]
    actionItems?: string[]
    decisions?: string[]
    uploadTaskId?: string
    upload_task_id?: string
    audioFileName?: string
    audioFilePath?: string
    audioFileSize?: number
    audioFormat?: string
    sampleRate?: number
    channels?: number
  }): Promise<MeetingResponse> => {
    try {
      const requestOptions: RequestInit = {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify(meetingData)
      };
      
      const response = await fetch(`${API_BASE_URL}/meetings/save-documents`, requestOptions);
      
      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.message || `HTTP error! status: ${response.status}`);
      }
      
      const result = await response.json();
      return {
        success: true,
        data: result.data,
        message: result.message
      };
    } catch (error) {
      console.error('保存会议文档失败:', error);
      return {
        success: false,
        error: error instanceof Error ? error.message : '未知错误'
      };
    }
  },

  // 获取会议文档列表
  getMeetingDocuments: async (filters?: {
    meeting_id?: number
    meeting_title?: string
    document_type?: 'transcription' | 'minutes' | 'emotion' | 'audio_info' | 'audio' | 'video' | 'media'
  }): Promise<{
    success: boolean
    data?: {
      documents: Array<{
        id: number
        meeting_id?: number
        filename: string
        title?: string
        meeting_title?: string
        type: string
        timestamp?: string
        file_path: string
        file_size: number
        created_time: string
        updated_time?: string
        modified_time?: string
        download_url: string
      }>
      total: number
      filters: any
    }
    error?: string
  }> => {
    try {
      const params = new URLSearchParams()
      if (filters?.meeting_id) {
        params.append('meeting_id', filters.meeting_id.toString())
      }
      if (filters?.meeting_title) {
        params.append('meeting_title', filters.meeting_title)
      }
      if (filters?.document_type) {
        params.append('document_type', filters.document_type)
      }
      
      const url = `${API_BASE_URL}/meetings/documents/list${params.toString() ? '?' + params.toString() : ''}`
      const response = await fetch(url)
      
      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}))
        throw new Error(errorData.message || `HTTP error! status: ${response.status}`)
      }
      
      const result = await response.json()
      return {
        success: true,
        data: result.data
      }
    } catch (error) {
      console.error('获取文档列表失败:', error)
      return {
        success: false,
        error: error instanceof Error ? error.message : '未知错误'
      }
    }
  },

  // 下载会议文档
  downloadMeetingDocument: async (
    documentIdOrPath: number | string,
    fileName?: string,
    format?: MeetingDownloadFormat
  ): Promise<{
    success: boolean
    error?: string
  }> => {
    try {
      const params = new URLSearchParams()
      if (typeof documentIdOrPath === 'number' || /^\d+$/.test(String(documentIdOrPath))) {
        params.append('document_id', String(documentIdOrPath))
      } else {
        params.append('file_path', String(documentIdOrPath))
      }
      if (fileName) {
        params.append('file_name', fileName)
      }
      if (format && format !== 'original') {
        params.append('format', format)
      }
      
      const url = `${API_BASE_URL}/meetings/documents/download?${params.toString()}`

      const response = await fetch(url)
      if (!response.ok) {
        throw new Error(await readApiErrorMessage(response))
      }

      const blob = await response.blob()
      const downloadName = getDownloadFileName(response, fileName, format)
      triggerBlobDownload(blob, downloadName)
      
      return {
        success: true
      }
    } catch (error) {
      console.error('下载文档失败:', error)
      return {
        success: false,
        error: error instanceof Error ? error.message : '未知错误'
      }
    }
  },

  // 获取会议纪要版本列表
  getMeetingMinutesVersions: async (meetingId: number): Promise<{
    success: boolean
    data?: {
      meeting_id: number
      versions: MeetingMinutesVersion[]
      total: number
    }
    error?: string
  }> => {
    try {
      const response = await fetch(`${API_BASE_URL}/meetings/${meetingId}/minutes/versions`)
      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}))
        throw new Error(errorData.message || `HTTP error! status: ${response.status}`)
      }
      const result = await response.json()
      return {
        success: true,
        data: result.data
      }
    } catch (error) {
      console.error('获取会议纪要版本失败:', error)
      return {
        success: false,
        error: error instanceof Error ? error.message : '未知错误'
      }
    }
  },

  // 按自然语言要求改写会议纪要
  reviseMeetingMinutes: async (
    meetingId: number,
    data: {
      instruction: string
      base_summary?: string
      source_version_id?: number
      options?: Record<string, any>
    }
  ): Promise<{
    success: boolean
    data?: {
      meeting_id: number
      version: MeetingMinutesVersion
      summary: string
    }
    error?: string
  }> => {
    try {
      const response = await fetch(`${API_BASE_URL}/meetings/${meetingId}/minutes/revise`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data)
      })
      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}))
        throw new Error(errorData.message || `HTTP error! status: ${response.status}`)
      }
      const result = await response.json()
      return {
        success: true,
        data: result.data
      }
    } catch (error) {
      console.error('改写会议纪要失败:', error)
      return {
        success: false,
        error: error instanceof Error ? error.message : '未知错误'
      }
    }
  },

  // 下载指定会议纪要版本
  downloadMeetingMinutesVersion: async (
    meetingId: number,
    versionId: number,
    format: Extract<MeetingDownloadFormat, 'md' | 'docx' | 'word' | 'pdf'> = 'docx'
  ): Promise<{
    success: boolean
    error?: string
  }> => {
    try {
      const params = new URLSearchParams()
      params.append('format', format)
      const url = `${API_BASE_URL}/meetings/${meetingId}/minutes/versions/${versionId}/download?${params.toString()}`
      const response = await fetch(url)
      if (!response.ok) {
        throw new Error(await readApiErrorMessage(response))
      }

      const blob = await response.blob()
      const downloadName = getDownloadFileName(response, `meeting-minutes-v${versionId}`, format)
      triggerBlobDownload(blob, downloadName)
      return { success: true }
    } catch (error) {
      console.error('下载会议纪要版本失败:', error)
      return {
        success: false,
        error: error instanceof Error ? error.message : '未知错误'
      }
    }
  },

  // 更新会议转录文档文本
  updateMeetingDocumentText: async (
    meetingId: number,
    documentId: number,
    content: string
  ): Promise<{
    success: boolean
    data?: {
      document: MeetingDocumentInfo
      content: string
    }
    error?: string
  }> => {
    try {
      const response = await fetch(`${API_BASE_URL}/meetings/${meetingId}/documents/${documentId}/text`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ content })
      })
      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}))
        throw new Error(errorData.message || `HTTP error! status: ${response.status}`)
      }
      const result = await response.json()
      return {
        success: true,
        data: result.data
      }
    } catch (error) {
      console.error('更新会议文档失败:', error)
      return {
        success: false,
        error: error instanceof Error ? error.message : '未知错误'
      }
    }
  },

  // 生成逐人情绪分析产物
  generateEmotionAnalysis: async (
    meetingId: number,
    transcript?: string
  ): Promise<{
    success: boolean
    data?: {
      document: MeetingDocumentInfo
      content: string
      analysis: Record<string, any>
    }
    error?: string
  }> => {
    try {
      const response = await fetch(`${API_BASE_URL}/meetings/${meetingId}/emotion-analysis`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ transcript })
      })
      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}))
        throw new Error(errorData.message || `HTTP error! status: ${response.status}`)
      }
      const result = await response.json()
      return {
        success: true,
        data: result.data
      }
    } catch (error) {
      console.error('生成情绪分析失败:', error)
      return {
        success: false,
        error: error instanceof Error ? error.message : '未知错误'
      }
    }
  },

  // 创建会议
  createMeeting: async (meetingData: {
    title: string
    fileName: string
    audioFile?: {
      fileName: string
      filePath: string
      fileSize: number
      format: string
    }
    transcriptionContent?: {
      fileName: string
      filePath: string
    }
    meetingMinutes?: {
      fileName: string
      filePath: string
    }
  } | FormData): Promise<MeetingResponse> => {
    try {
      let requestOptions: RequestInit;
      
      if (meetingData instanceof FormData) {
        // 兼容旧的FormData格式
        requestOptions = {
          method: 'POST',
          body: meetingData
        };
      } else {
        // 新的JSON格式
        requestOptions = {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json'
          },
          body: JSON.stringify(meetingData)
        };
      }
      
      const response = await fetch(`${API_BASE_URL}/meetings`, requestOptions)
      
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`)
      }
      
      const result = await response.json()
      return {
        success: true,
        data: result.data,
        message: result.message
      }
    } catch (error) {
      console.error('创建会议失败:', error)
      return {
        success: false,
        error: error instanceof Error ? error.message : '未知错误'
      }
    }
  },

  // 获取会议列表
  getMeetingList: async (): Promise<MeetingListResponse> => {
    try {
      const response = await fetch(`${API_BASE_URL}/meetings`, {
        method: 'GET'
      })

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`)
      }

      const result = await response.json()
      return {
        success: true,
        data: result.data,
        message: result.message
      }
    } catch (error) {
      console.error('Error fetching meeting list:', error)
      return {
        success: false,
        error: error instanceof Error ? error.message : '获取会议列表失败'
      }
    }
  },

  // 获取单个会议详情
  getMeeting: async (meetingId: number): Promise<MeetingResponse> => {
    try {
      const response = await fetch(`${API_BASE_URL}/meetings/${meetingId}`, {
        method: 'GET'
      })

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`)
      }

      const result = await response.json()
      return {
        success: true,
        data: result.data,
        message: result.message
      }
    } catch (error) {
      console.error('Error fetching meeting:', error)
      return {
        success: false,
        error: error instanceof Error ? error.message : '获取会议详情失败'
      }
    }
  },

  // 获取保存后关联的上传转写片段（实时转写仍使用转录文档）
  getMeetingUploadedTranscription: async (meetingId: number): Promise<{
    success: boolean
    data?: UploadedMeetingTranscription
    error?: string
  }> => {
    try {
      const response = await fetch(`${API_BASE_URL}/meetings/${meetingId}/uploaded-transcription`, {
        method: 'GET'
      })

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}))
        throw new Error(errorData.message || `HTTP error! status: ${response.status}`)
      }

      const result = await response.json()
      return {
        success: true,
        data: result.data
      }
    } catch (error) {
      console.error('获取上传转写回显失败:', error)
      return {
        success: false,
        error: error instanceof Error ? error.message : '未知错误'
      }
    }
  },

  // 删除会议
  deleteMeeting: async (meetingId: number): Promise<MeetingResponse> => {
    try {
      const response = await fetch(`${API_BASE_URL}/meetings/${meetingId}`, {
        method: 'DELETE'
      })

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`)
      }

      const result = await response.json()
      return {
        success: true,
        message: result.message
      }
    } catch (error) {
      console.error('Error deleting meeting:', error)
      return {
        success: false,
        error: error instanceof Error ? error.message : '删除会议失败'
      }
    }
  },

  // 下载会议音频文件
  downloadAudio: async (meetingId: number): Promise<Blob | null> => {
    try {
      const response = await fetch(`${API_BASE_URL}/meetings/${meetingId}/audio`, {
        method: 'GET'
      })

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`)
      }

      return await response.blob()
    } catch (error) {
      console.error('Error downloading audio:', error)
      return null
    }
  },

  // 下载会议转录文本
  downloadTranscription: async (meetingId: number): Promise<string | null> => {
    try {
      const response = await fetch(`${API_BASE_URL}/meetings/${meetingId}/transcription`, {
        method: 'GET'
      })

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`)
      }

      const result = await response.json()
      return result.data.transcriptionContent
    } catch (error) {
      console.error('Error downloading transcription:', error)
      return null
    }
  },

  // 下载会议纪要
  downloadMinutes: async (meetingId: number): Promise<string | null> => {
    try {
      const response = await fetch(`${API_BASE_URL}/meetings/${meetingId}/minutes`, {
        method: 'GET'
      })

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`)
      }

      const result = await response.json()
      return result.data.content
    } catch (error) {
      console.error('Error downloading minutes:', error)
      return null
    }
  }
}
