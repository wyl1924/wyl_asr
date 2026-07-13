// ASR相关类型定义

// 音频设备信息接口
export interface AudioDeviceInfo {
  deviceId: string
  label: string
  kind: string
}

// 语音识别配置接口
export interface AsrConfig {
  language: string
  audioSource: string
  continuous: boolean
  interimResults: boolean
}

// 热词配置接口
export interface HotWordConfig {
  words: string[]
  weight?: number
}

// 识别结果接口
export interface RecognitionResult {
  text: string
  isFinal: boolean
  confidence?: number
}