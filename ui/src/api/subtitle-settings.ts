// 字幕显示设置相关接口
import { SERVER_CONFIG } from '../config/api'

/**
 * 字幕设置数据结构
 */
export interface SubtitleSettings {
  windowWidth: number          // 10-100
  cornerRadius: number         // 0-100
  backgroundColor: string      // Hex color #RRGGBB
  backgroundOpacity: number    // 0-100
  fontFamily: string           // Font name
  fontSize: number             // 1-100
  fontColor: string            // "默认" or hex color
  isBold: boolean
  isItalic: boolean
  showEnglish: boolean
  maxDisplayLines: number      // 1-20
  scrollSpeed: number          // 20-200
  webSocketUrl: string         // ws:// or wss://
}

/**
 * API响应接口
 */
export interface SubtitleSettingsResponse {
  success: boolean
  data?: SubtitleSettings
  message?: string
  error?: string
  errors?: string[]
}

const API_BASE_URL = `${SERVER_CONFIG.DB_BASE_URL}/api`

/**
 * 字幕设置API
 */
export const subtitleSettingsApi = {
  /**
   * 获取当前字幕设置
   * @returns 当前设置或默认设置
   */
  getSubtitleSettings: async (): Promise<SubtitleSettingsResponse> => {
    try {
      const response = await fetch(`${API_BASE_URL}/subtitle-settings`, {
        method: 'GET',
        headers: {
          'Content-Type': 'application/json'
        }
      })

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}))
        throw new Error(errorData.message || `HTTP error! status: ${response.status}`)
      }

      const result = await response.json()
      return {
        success: true,
        data: result.data,
        message: result.message
      }
    } catch (error) {
      console.error('获取字幕设置失败:', error)
      return {
        success: false,
        error: error instanceof Error ? error.message : '获取字幕设置失败'
      }
    }
  },

  /**
   * 保存字幕设置并广播到所有客户端
   * @param settings 字幕设置对象
   * @returns 保存结果
   */
  saveSubtitleSettings: async (settings: SubtitleSettings): Promise<SubtitleSettingsResponse> => {
    try {
      const response = await fetch(`${API_BASE_URL}/subtitle-settings`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify(settings)
      })

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}))
        
        // 处理验证错误（400状态码）
        if (response.status === 400 && errorData.errors) {
          return {
            success: false,
            errors: errorData.errors,
            message: errorData.message || '设置验证失败'
          }
        }
        
        throw new Error(errorData.message || `HTTP error! status: ${response.status}`)
      }

      const result = await response.json()
      return {
        success: true,
        data: result.data,
        message: result.message
      }
    } catch (error) {
      console.error('保存字幕设置失败:', error)
      return {
        success: false,
        error: error instanceof Error ? error.message : '保存字幕设置失败'
      }
    }
  }
}
