// ASR相关接口

// 示例接口定义
export interface AsrResponse {
  success: boolean
  data: {
    text: string
    confidence: number
  }
  error?: string
}

// 可以在这里添加与语音识别相关的API调用
export const asrApi = {
  // 示例方法
  transcribe: async (_audioData: Blob): Promise<AsrResponse> => {
    // 实际项目中这里会调用后端API
    // 当前仅返回模拟数据
    return {
      success: true,
      data: {
        text: '语音识别结果',
        confidence: 0.95
      }
    }
  }
}