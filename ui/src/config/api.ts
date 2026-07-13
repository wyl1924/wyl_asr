/**
 * API配置文件 - 统一管理所有服务端点和IP地址
 */

// 统一配置参数
const USE_HTTPS = false  // 是否使用HTTPS/WSS
// 自动检测：如果从远程访问，使用当前主机名；否则使用localhost
const SERVER_IP = typeof window !== 'undefined' && window.location.hostname !== 'localhost' && window.location.hostname !== '127.0.0.1'
  ? window.location.hostname
  : '127.0.0.1'  // 服务器IP地址

// 服务器配置
export const SERVER_CONFIG = {
  // 统一配置
  USE_HTTPS,
  SERVER_IP,
  
  // ASR语音识别服务
  ASR_HOST: SERVER_IP,
  ASR_PORT: 10095,
  ASR_WS_URL: `${USE_HTTPS ? 'wss' : 'ws'}://${SERVER_IP}:10095/`,
  
  // 数据库API服务
  DB_HOST: SERVER_IP,
  DB_PORT: 8080,
  DB_BASE_URL: `${USE_HTTPS ? 'https' : 'http'}://${SERVER_IP}:8080`,
  
  // 会议纪要生成服务（Ollama Qwen3模型）
  SUMMARY_HOST: SERVER_IP,
  SUMMARY_PORT: 11434,
  SUMMARY_ENDPOINT: `${USE_HTTPS ? 'https' : 'http'}://${SERVER_IP}:11434/api/chat`,
  
  // 默认设置
  DEFAULT_HOST: '0.0.0.0', // 服务器监听地址
  LOCALHOST: '127.0.0.1'   // 本地回环地址
}

// API端点配置
export const API_ENDPOINTS = {
  // 说话人相关API
  SPEAKER: {
    REGISTER: `${SERVER_CONFIG.DB_BASE_URL}/api/speakers/register`,
    REGISTER_UPLOADED_SEGMENT: `${SERVER_CONFIG.DB_BASE_URL}/api/speakers/register-uploaded-segment`,
    LIST: `${SERVER_CONFIG.DB_BASE_URL}/api/speakers/list`,
    IDENTIFY: `${SERVER_CONFIG.DB_BASE_URL}/api/speakers/identify`,
    DELETE: `${SERVER_CONFIG.DB_BASE_URL}/api/speakers/delete`
  },
  
  // 会议相关API
  MEETING: {
    BASE: `${SERVER_CONFIG.DB_BASE_URL}/api/meetings`
  },
  
  // 会议纪要生成API
  SUMMARY: {
    GENERATE: SERVER_CONFIG.SUMMARY_ENDPOINT,
    TASKS: `${SERVER_CONFIG.DB_BASE_URL}/api/summary/tasks`
  },

  // LLM后端网关
  LLM: {
    CHAT: `${SERVER_CONFIG.DB_BASE_URL}/api/llm/chat`,
    TASKS: `${SERVER_CONFIG.DB_BASE_URL}/api/llm/tasks`,
    CONFIG: `${SERVER_CONFIG.DB_BASE_URL}/api/llm/config`
  },
  
  // 音频设备API
  AUDIO_DEVICES: {
    LIST: `${SERVER_CONFIG.DB_BASE_URL}/api/audio-devices`
  },

  // 上传识别API
  UPLOAD: {
    AUDIO_RECOGNIZE: `${SERVER_CONFIG.DB_BASE_URL}/api/upload/audio/recognize`,
    AUDIO_TASKS: `${SERVER_CONFIG.DB_BASE_URL}/api/upload/audio/tasks`
  }
}

// WebSocket配置
export const WS_CONFIG = {
  ASR_URL: SERVER_CONFIG.ASR_WS_URL,
  RECONNECT_INTERVAL: 3000,
  MAX_RECONNECT_ATTEMPTS: 5
}

// 工具函数：根据配置生成完整URL
export const buildUrl = (host: string, port: number, path: string = '') => {
  const protocol = USE_HTTPS ? 'https' : 'http'
  return `${protocol}://${host}:${port}${path}`
}

// 工具函数：根据配置生成WebSocket URL
export const buildWsUrl = (host: string, port: number, path: string = '') => {
  const protocol = USE_HTTPS ? 'wss' : 'ws'
  return `${protocol}://${host}:${port}${path}`
}

// 工具函数：处理服务器主机地址显示
export const getDisplayHost = (host: string) => {
  return host === '0.0.0.0' ? 'localhost' : host
}

// 导出默认配置
export default SERVER_CONFIG
