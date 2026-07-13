import { ElMessage } from 'element-plus'

interface TextProcessOptions {
  model?: string
  temperature?: number
  top_p?: number
  max_tokens?: number
}

/**
 * 对语音识别文本进行智能处理
 * @param text 原始语音识别文本
 * @param options 可选配置参数
 * @returns 处理后的文本内容
 */
export async function processText(text: string, _options: TextProcessOptions = {}) {
  if (!text) {
    throw new Error('没有可用的语音识别内容')
  }

  ElMessage.info('正在处理文本内容...')
  console.log('原始内容:', text)

  const API_URL = 'http://localhost:8880/api/v1/document/segmentation'
  const headers = {
    'Content-Type': 'application/json',
    'Access-Control-Allow-Origin': '*',
    'Access-Control-Allow-Methods': 'GET, POST, PUT, DELETE, OPTIONS',
    'Access-Control-Allow-Headers': 'Content-Type'
  }

  try {
    const response = await fetch(API_URL, {
      method: 'POST',
      headers,
      body: JSON.stringify({
        platform: 'tongyi',
        model: 'nlp_bert_document-segmentation_chinese-base',
        input: text
      })
    })

    if (!response.ok) {
      const errorText = await response.text()
      throw new Error(`API请求失败: ${response.status} - ${errorText || '未知错误'}`)
    }

    const data = await response.json()
    if (!data || typeof data !== 'object') {
      throw new Error('API返回的数据格式无效')
    }

    // 更新数据解析逻辑，处理分段结果
    if (!data.output || !Array.isArray(data.output.lines)) {
      throw new Error('API返回的数据中缺少有效的分段结果')
    }

    // 提取分段文本并合并
    const processedText = data.output.lines
      .map((line: { text: string }) => (line && typeof line === 'object' && 'text' in line ? line.text : ''))
      .filter((text: string): text is string => Boolean(text))
      .join('\n')

    if (!processedText) {
      throw new Error('处理后的文本内容为空')
    }

    return processedText
  } catch (error) {
    console.error('文本处理失败:', error)
    const errorMessage = error instanceof Error ? error.message : String(error)
    throw new Error(`文本处理失败：${errorMessage.includes('Failed to fetch') ? '网络连接失败，请检查网络设置' : errorMessage}`)
  }
}