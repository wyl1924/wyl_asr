import { ElMessage } from 'element-plus'
import { API_ENDPOINTS } from '../config/api'

// 会议纪要默认使用后端保存的OpenAI兼容模型配置
const MODEL_CONFIG = {
  name: 'DeepSeek-R1-671B-1',
  maxContextTokens: 128000,
  maxOutputTokens: 64000,
  endpoint: 'http://10.1.0.26:9997/v1/chat/completions',
  // 中文友好模型通常会把单个中文字符估算在0.6-0.8 token附近
  chineseCharToTokenRatio: 0.8,
  // 英文单词到token的近似比例
  englishWordToTokenRatio: 1.3
}

export interface GenerateSummaryOptions {
  model?: string
  temperature?: number
  top_p?: number
  max_tokens?: number
  customRequirements?: string
  templateId?: string
  useBackendSummary?: boolean
  meetingId?: number
  useBackendGateway?: boolean
  useBackendStoredConfig?: boolean
  onSummaryProgress?: (task: BackendSummaryTask) => void
  ollamaConfig?: {
    endpoint: string
    model: string
  }
  xinferenceConfig?: {
    endpoint: string
    model: string
    apiKey?: string
  }
  vllmConfig?: {
    endpoint: string
    model: string
    apiKey?: string
  }
  sglangConfig?: {
    endpoint: string
    model: string
    apiKey?: string
  }
  serviceType?: 'ollama' | 'xinference' | 'vllm' | 'sglang'
}

interface BackendLLMTask {
  task_id: string
  status: 'queued' | 'running' | 'succeeded' | 'failed'
  result?: {
    content?: string
    usage?: unknown
    metrics?: unknown
    duration_seconds?: number
  }
  error?: string
}

export interface BackendSummaryTask {
  task_id: string
  status: 'queued' | 'running' | 'succeeded' | 'failed'
  progress?: number
  stage?: string
  result?: {
    summary?: string
    mode?: string
    segments_count?: number
    meeting_id?: number | null
    minutes_id?: number | null
  }
  error?: string
}

export const SUMMARY_TASK_STORAGE_KEY = 'meeting_summary_active_task_id'

/**
 * 估算文本的token数量
 * @param text 文本内容
 * @returns 估算的token数量
 */
function estimateTokenCount(text: string): number {
  // 统计中文字符数量
  const chineseChars = (text.match(/[\u4e00-\u9fff]/g) || []).length
  // 统计英文单词数量
  const englishWords = (text.match(/[a-zA-Z]+/g) || []).length
  // 统计其他字符（标点符号、数字等）
  const otherChars = text.length - chineseChars - englishWords
  
  return Math.ceil(
    chineseChars * MODEL_CONFIG.chineseCharToTokenRatio +
    englishWords * MODEL_CONFIG.englishWordToTokenRatio +
    otherChars * 0.5
  )
}

/**
 * 智能分段处理，确保不超过模型的上下文限制
 * @param text 原始文本
 * @param systemPromptTokens 系统提示词的token数量
 * @returns 分段后的文本数组
 */
function intelligentSegmentation(text: string, systemPromptTokens: number): string[] {
  const maxSegmentTokens = Math.max(
    MODEL_CONFIG.maxContextTokens - systemPromptTokens - MODEL_CONFIG.maxOutputTokens - 2000,
    4000
  )
  
  // 按段落分割
  const paragraphs = text.split(/(?:\r?\n){2,}/).filter(p => p.trim())
  const segments: string[] = []
  let currentSegment = ''
  let currentTokens = 0
  
  for (const paragraph of paragraphs) {
    const paragraphTokens = estimateTokenCount(paragraph)
    
    // 如果单个段落就超过限制，需要进一步分割
    if (paragraphTokens > maxSegmentTokens) {
      if (currentSegment) {
        segments.push(currentSegment)
        currentSegment = ''
        currentTokens = 0
      }
      
      // 按句子分割超长段落
      const sentences = paragraph.split(/[。！？.!?]/).filter(s => s.trim())
      let tempSegment = ''
      let tempTokens = 0
      
      for (const sentence of sentences) {
        const sentenceTokens = estimateTokenCount(sentence + '。')
        
        // 如果单个句子就超过限制，强制按字符分割
        if (sentenceTokens > maxSegmentTokens) {
          if (tempSegment) {
            segments.push(tempSegment)
            tempSegment = ''
            tempTokens = 0
          }
          
          // 按字符强制分割超长句子
           const maxChars = Math.floor(maxSegmentTokens / 3) // 更保守的估计
           for (let i = 0; i < sentence.length; i += maxChars) {
             const chunk = sentence.slice(i, i + maxChars)
             if (chunk.trim()) {
               segments.push(chunk + '。')
             }
           }
        } else if (tempTokens + sentenceTokens > maxSegmentTokens) {
          if (tempSegment) {
            segments.push(tempSegment)
          }
          tempSegment = sentence + '。'
          tempTokens = sentenceTokens
        } else {
          tempSegment += (tempSegment ? '' : '') + sentence + '。'
          tempTokens += sentenceTokens
        }
      }
      
      if (tempSegment) {
        segments.push(tempSegment)
      }
    } else {
      // 检查是否可以添加到当前段落
      if (currentTokens + paragraphTokens > maxSegmentTokens) {
        if (currentSegment) {
          segments.push(currentSegment)
        }
        currentSegment = paragraph
        currentTokens = paragraphTokens
      } else {
        currentSegment += (currentSegment ? '\n\n' : '') + paragraph
        currentTokens += paragraphTokens
      }
    }
  }
  
  if (currentSegment) {
    segments.push(currentSegment)
  }
  
  return segments
}

function sleep(ms: number): Promise<void> {
  return new Promise(resolve => setTimeout(resolve, ms))
}

function stripLLMReasoningPreface(content: string): string {
  const headingPattern = /^\s*(?:#{1,6}\s*)?(?:(?:会议主题|发言人)\s*[:：].*|(?:会议纪要|会议摘要(?:（300字）|\(300字\))?|会议基本信息|主要内容|主要议题讨论|本段落主要议题|重要决策|待办事项|后续安排)\s*[:：]?\s*)$/m
  const headingMatch = content.match(headingPattern)
  if (!headingMatch || headingMatch.index === undefined || headingMatch.index === 0) {
    return content.trim()
  }

  const prefix = content.slice(0, headingMatch.index).trim()
  if (!prefix) {
    return content.slice(headingMatch.index).trim()
  }

  const reasoningMarkers = [
    '我现在需要',
    '首先',
    '接下来',
    '用户提供',
    '根据用户',
    '需要根据',
    '逐项分析',
    '开始分析',
    '确保',
    '推理',
    '思考',
    '好的',
    '以下是'
  ]

  if (prefix.length <= 1000 || reasoningMarkers.some(marker => prefix.includes(marker))) {
    return content.slice(headingMatch.index).trim()
  }

  return content.trim()
}

function stripLLMThinkingContent(content = ''): string {
  let cleaned = content
    .replace(/<(think|thinking)\b[^>]*>[\s\S]*?<\/\1>/gi, '')
    .trim()

  if (/^<(think|thinking)\b/i.test(cleaned)) {
    const headingMatch = cleaned.match(/^\s*#{1,6}\s+/m)
    if (headingMatch && headingMatch.index !== undefined) {
      cleaned = cleaned.slice(headingMatch.index).trim()
    }
  }

  return stripLLMReasoningPreface(cleaned)
}

async function readBackendResponse<T>(response: Response): Promise<T> {
  const text = await response.text()
  let payload: any = null

  try {
    payload = text ? JSON.parse(text) : null
  } catch {
    payload = null
  }

  if (!response.ok) {
    const message = payload?.message || payload?.error || text || `HTTP ${response.status}`
    throw new Error(message)
  }

  return (payload?.data ?? payload) as T
}

function getBackendGatewayConfig(options: GenerateSummaryOptions): {
  endpoint?: string
  model?: string
  apiKey?: string
} {
  const serviceType = options.serviceType || 'ollama'

  switch (serviceType) {
    case 'xinference':
      if (!options.xinferenceConfig) return {}
      return {
        endpoint: options.xinferenceConfig.endpoint,
        model: options.xinferenceConfig.model,
        apiKey: options.xinferenceConfig.apiKey
      }
    case 'vllm':
      if (!options.vllmConfig) return {}
      return {
        endpoint: options.vllmConfig.endpoint,
        model: options.vllmConfig.model,
        apiKey: options.vllmConfig.apiKey
      }
    case 'sglang':
      if (!options.sglangConfig) return {}
      return {
        endpoint: options.sglangConfig.endpoint,
        model: options.sglangConfig.model,
        apiKey: options.sglangConfig.apiKey
      }
    case 'ollama':
    default:
      return {
        endpoint: options.ollamaConfig?.endpoint || MODEL_CONFIG.endpoint,
        model: options.ollamaConfig?.model || options.model || MODEL_CONFIG.name
      }
  }
}

function buildBackendGatewayPayload(
  messages: Array<{role: string, content: string}>,
  options: GenerateSummaryOptions
) {
  return {
    serviceType: options.serviceType,
    config: getBackendGatewayConfig(options),
    messages,
    options: {
      temperature: options.temperature,
      top_p: options.top_p,
      max_tokens: options.max_tokens || MODEL_CONFIG.maxOutputTokens
    }
  }
}

function buildBackendSummaryPayload(transcript: string, options: GenerateSummaryOptions) {
  const gatewayPayload = options.useBackendStoredConfig === false
    ? buildBackendGatewayPayload([], options)
    : {
        serviceType: options.serviceType,
        config: {},
        options: {
          temperature: options.temperature,
          top_p: options.top_p,
          max_tokens: options.max_tokens || MODEL_CONFIG.maxOutputTokens
        }
      }

  return {
    transcript,
    templateId: options.templateId,
    customRequirements: options.customRequirements,
    meeting_id: options.meetingId,
    llm: {
      serviceType: gatewayPayload.serviceType,
      config: gatewayPayload.config
    },
    options: {
      ...gatewayPayload.options,
      templateId: options.templateId,
      customRequirements: options.customRequirements
    }
  }
}

async function callBackendSummaryTask(
  transcript: string,
  options: GenerateSummaryOptions
): Promise<string> {
  const payload = buildBackendSummaryPayload(transcript, options)
  const createResponse = await fetch(API_ENDPOINTS.SUMMARY.TASKS, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json'
    },
    body: JSON.stringify(payload)
  })
  const createdTask = await readBackendResponse<{task_id: string; status: string}>(createResponse)
  const taskId = createdTask.task_id

  if (!taskId) {
    throw new Error('后端会议纪要任务创建失败：未返回任务ID')
  }

  localStorage.setItem(SUMMARY_TASK_STORAGE_KEY, taskId)
  options.onSummaryProgress?.({
    task_id: taskId,
    status: 'queued',
    progress: 0,
    stage: '已提交后端会议纪要生成任务'
  })

  return await pollBackendSummaryTask(taskId, options)
}

async function pollBackendSummaryTask(
  taskId: string,
  options: GenerateSummaryOptions = {}
): Promise<string> {
  const startedAt = Date.now()
  const timeoutMs = 600000

  while (Date.now() - startedAt < timeoutMs) {
    await sleep(1500)

    const statusResponse = await fetch(`${API_ENDPOINTS.SUMMARY.TASKS}/${encodeURIComponent(taskId)}`)
    const task = await readBackendResponse<BackendSummaryTask>(statusResponse)
    options.onSummaryProgress?.(task)

    if (task.stage) {
      console.log(`后端会议纪要任务状态: ${task.status}, 进度: ${task.progress ?? 0}%, 阶段: ${task.stage}`)
    }

    if (task.status === 'succeeded') {
      const summary = task.result?.summary
      if (!summary) {
        throw new Error('后端会议纪要任务完成但返回内容为空')
      }
      console.log(`后端会议纪要生成完成，模式: ${task.result?.mode || 'unknown'}, 分段数: ${task.result?.segments_count || 1}`)
      localStorage.removeItem(SUMMARY_TASK_STORAGE_KEY)
      return summary
    }

    if (task.status === 'failed') {
      localStorage.removeItem(SUMMARY_TASK_STORAGE_KEY)
      throw new Error(task.error || '后端会议纪要任务失败')
    }
  }

  throw new Error('后端会议纪要任务等待超时')
}

export async function resumeSummaryTask(
  taskId: string,
  options: GenerateSummaryOptions = {}
): Promise<string> {
  return await pollBackendSummaryTask(taskId, options)
}

async function callBackendLLMGateway(
  messages: Array<{role: string, content: string}>,
  options: GenerateSummaryOptions
): Promise<string> {
  const payload = buildBackendGatewayPayload(messages, options)
  const createResponse = await fetch(API_ENDPOINTS.LLM.TASKS, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json'
    },
    body: JSON.stringify(payload)
  })
  const createdTask = await readBackendResponse<{task_id: string; status: string}>(createResponse)
  const taskId = createdTask.task_id

  if (!taskId) {
    throw new Error('后端LLM任务创建失败：未返回任务ID')
  }

  const startedAt = Date.now()
  const timeoutMs = 600000

  while (Date.now() - startedAt < timeoutMs) {
    await sleep(1500)

    const statusResponse = await fetch(`${API_ENDPOINTS.LLM.TASKS}/${encodeURIComponent(taskId)}`)
    const task = await readBackendResponse<BackendLLMTask>(statusResponse)

    if (task.status === 'succeeded') {
      const result = task.result
      const content = result?.content
      if (!content) {
        throw new Error('后端LLM任务完成但返回内容为空')
      }

      if (result.duration_seconds !== undefined) {
        console.log(`后端LLM任务完成，耗时: ${result.duration_seconds}秒`)
      }
      return content
    }

    if (task.status === 'failed') {
      throw new Error(task.error || '后端LLM任务失败')
    }

    console.log(`后端LLM任务状态: ${task.status} (${taskId})`)
  }

  throw new Error('后端LLM任务等待超时')
}

/**
 * 通用API调用函数，支持Ollama、Xinference、vLLM、SGLang
 */
async function callLLMAPI(
  messages: Array<{role: string, content: string}>,
  options: GenerateSummaryOptions
): Promise<string> {
  const serviceType = options.serviceType || 'ollama'

  if (options.useBackendGateway !== false) {
    return await callBackendLLMGateway(messages, options)
  }
  
  switch (serviceType) {
    case 'xinference':
      return await callXinferenceAPI(messages, options)
    case 'vllm':
      return await callVLLMAPI(messages, options)
    case 'sglang':
      return await callSGLangAPI(messages, options)
    case 'ollama':
    default:
      return await callOllamaAPI(messages, options)
  }
}

/**
 * Xinference API调用
 */
async function callXinferenceAPI(
  messages: Array<{role: string, content: string}>,
  options: GenerateSummaryOptions
): Promise<string> {
  const config = options.xinferenceConfig
  if (!config) {
    throw new Error('Xinference配置缺失')
  }
  
  const startTime = Date.now()
  const startTimeStr = new Date().toISOString()
  
  console.log(`[${startTimeStr}] 发送Xinference API请求`)
  console.log(`端点: ${config.endpoint}`)
  console.log(`模型: ${config.model}`)
  
  const requestBody = {
    model: config.model,
    messages: messages,
    temperature: options.temperature || 0.7,
    top_p: options.top_p || 0.9,
    max_tokens: options.max_tokens || MODEL_CONFIG.maxOutputTokens,
    stream: false
  }
  
  console.log('Xinference请求详情:', {
    endpoint: config.endpoint,
    model: requestBody.model,
    messagesCount: messages.length,
    temperature: requestBody.temperature,
    requestTime: startTimeStr
  })
  
  const headers: Record<string, string> = {
    'Content-Type': 'application/json'
  }
  
  if (config.apiKey) {
    headers['Authorization'] = `Bearer ${config.apiKey}`
  }
  
  const controller = new AbortController()
  const timeoutId = setTimeout(() => {
    console.log('Xinference API请求超时，正在取消请求...')
    controller.abort()
  }, 600000) // 10分钟超时
  
  const response = await fetch(config.endpoint, {
    method: 'POST',
    headers,
    body: JSON.stringify(requestBody),
    signal: controller.signal
  })
  
  clearTimeout(timeoutId)
  
  if (!response.ok) {
    let errorText = await response.text()
    let errorDetail = errorText
    
    // 尝试解析JSON错误响应
    try {
      const errorJson = JSON.parse(errorText)
      errorDetail = errorJson.error || errorJson.message || errorText
    } catch {
      // 如果不是JSON，使用原始文本
    }
    
    // 针对常见错误提供详细提示
    if (response.status === 500) {
      console.error('Xinference 500错误详情:', errorDetail)
      throw new Error(
        `Xinference服务器错误 (500)。可能原因：\n` +
        `1. 模型 "${config.model}" 未部署或未启动\n` +
        `2. Xinference服务未正常运行\n` +
        `3. 请求参数不兼容\n\n` +
        `建议操作：\n` +
        `- 检查Xinference Web UI确认模型状态\n` +
        `- 确认模型已正确部署并启动\n` +
        `- 检查Xinference服务日志\n\n` +
        `错误详情: ${errorDetail}`
      )
    }
    
    throw new Error(`Xinference API请求失败: ${response.status} - ${errorDetail}`)
  }
  
  const data = await response.json()
  
  if (!data.choices || !data.choices[0] || !data.choices[0].message) {
    throw new Error('Xinference API返回数据格式错误')
  }
  
  const result = stripLLMThinkingContent(data.choices[0].message.content)
  const endTime = Date.now()
  const endTimeStr = new Date().toISOString()
  const duration = endTime - startTime
  
  // 记录token使用量信息
  if (data.usage) {
    console.log(`[${endTimeStr}] Xinference Token使用统计:`)
    console.log(`- 请求Token数: ${data.usage.prompt_tokens || 'N/A'}`)
    console.log(`- 返回Token数: ${data.usage.completion_tokens || 'N/A'}`)
    console.log(`- 总Token数: ${data.usage.total_tokens || 'N/A'}`)
  } else {
    console.log(`[${endTimeStr}] Xinference API响应中未包含token使用量信息`)
  }
  
  console.log(`[${endTimeStr}] Xinference API响应完成`)
  console.log(`响应耗时: ${duration}ms (${(duration/1000).toFixed(2)}秒)`)
  console.log(`生成内容长度: ${result.length}字符`)
  console.log('完整响应数据结构:', Object.keys(data))
  console.log('完整生成内容:', result)
  
  return result
}

/**
  * vLLM API调用
  */
 async function callVLLMAPI(
   messages: Array<{role: string, content: string}>,
   options: GenerateSummaryOptions
 ): Promise<string> {
   const config = options.vllmConfig
   if (!config) {
     throw new Error('vLLM配置缺失')
   }
   
   const startTime = Date.now()
   const startTimeStr = new Date().toISOString()
   
   console.log(`[${startTimeStr}] 发送vLLM API请求`)
   console.log(`端点: ${config.endpoint}`)
   console.log(`模型: ${config.model}`)
   
   const requestBody = {
     model: config.model,
     messages: messages,
     temperature: options.temperature || 0.7,
     top_p: options.top_p || 0.9,
     max_tokens: options.max_tokens || MODEL_CONFIG.maxOutputTokens,
     stream: false
   }
   
   console.log('vLLM请求详情:', {
     endpoint: config.endpoint,
     model: requestBody.model,
     messagesCount: messages.length,
     temperature: requestBody.temperature,
     requestTime: startTimeStr
   })
   
   const headers: Record<string, string> = {
     'Content-Type': 'application/json'
   }
   
   if (config.apiKey) {
     headers['Authorization'] = `Bearer ${config.apiKey}`
   }
   
   const controller = new AbortController()
   const timeoutId = setTimeout(() => {
     console.log('vLLM API请求超时，正在取消请求...')
     controller.abort()
   }, 600000) // 10分钟超时
   
   const response = await fetch(config.endpoint, {
     method: 'POST',
     headers,
     body: JSON.stringify(requestBody),
     signal: controller.signal
   })
   
   clearTimeout(timeoutId)
   
   if (!response.ok) {
     let errorText = await response.text()
     let errorDetail = errorText
     
     // 尝试解析JSON错误响应
     try {
       const errorJson = JSON.parse(errorText)
       errorDetail = errorJson.error || errorJson.message || errorText
     } catch {
       // 如果不是JSON，使用原始文本
     }
     
     // 针对常见错误提供详细提示
     if (response.status === 500) {
       console.error('vLLM 500错误详情:', errorDetail)
       throw new Error(
         `vLLM服务器错误 (500)。可能原因：\n` +
         `1. 模型 "${config.model}" 未加载\n` +
         `2. vLLM服务未正常运行\n` +
         `3. 请求参数不兼容\n\n` +
         `建议操作：\n` +
         `- 检查vLLM服务日志\n` +
         `- 确认模型已正确加载\n` +
         `- 验证API端点配置\n\n` +
         `错误详情: ${errorDetail}`
       )
     }
     
     throw new Error(`vLLM API请求失败: ${response.status} - ${errorDetail}`)
   }
   
   const data = await response.json()
  
  if (!data.choices || !data.choices[0] || !data.choices[0].message) {
    throw new Error('vLLM API返回数据格式错误')
  }
  
  const result = stripLLMThinkingContent(data.choices[0].message.content)
  const endTime = Date.now()
  const endTimeStr = new Date().toISOString()
  const duration = endTime - startTime
  
  // 记录token使用量信息
  if (data.usage) {
    console.log(`[${endTimeStr}] vLLM Token使用统计:`)
    console.log(`- 请求Token数: ${data.usage.prompt_tokens || 'N/A'}`)
    console.log(`- 返回Token数: ${data.usage.completion_tokens || 'N/A'}`)
    console.log(`- 总Token数: ${data.usage.total_tokens || 'N/A'}`)
  } else {
    console.log(`[${endTimeStr}] vLLM API响应中未包含token使用量信息`)
  }
  
  console.log(`[${endTimeStr}] vLLM API响应完成`)
  console.log(`响应耗时: ${duration}ms (${(duration/1000).toFixed(2)}秒)`)
  console.log(`生成内容长度: ${result.length}字符`)
  console.log('完整响应数据结构:', Object.keys(data))
  console.log('完整生成内容:', result)
   
   return result
 }
 
 /**
  * SGLang API调用
  */
 async function callSGLangAPI(
   messages: Array<{role: string, content: string}>,
   options: GenerateSummaryOptions
 ): Promise<string> {
   const config = options.sglangConfig
   if (!config) {
     throw new Error('SGLang配置缺失')
   }
   
   const startTime = Date.now()
   const startTimeStr = new Date().toISOString()
   
   console.log(`[${startTimeStr}] 发送SGLang API请求`)
   console.log(`端点: ${config.endpoint}`)
   console.log(`模型: ${config.model}`)
   
   const requestBody = {
     model: config.model,
     messages: messages,
     temperature: options.temperature || 0.7,
     top_p: options.top_p || 0.9,
     max_tokens: options.max_tokens || MODEL_CONFIG.maxOutputTokens,
     stream: false
   }
   
   console.log('SGLang请求详情:', {
     endpoint: config.endpoint,
     model: requestBody.model,
     messagesCount: messages.length,
     temperature: requestBody.temperature,
     requestTime: startTimeStr
   })
   
   const headers: Record<string, string> = {
     'Content-Type': 'application/json'
   }
   
   if (config.apiKey) {
     headers['Authorization'] = `Bearer ${config.apiKey}`
   }
   
   const controller = new AbortController()
   const timeoutId = setTimeout(() => {
     console.log('SGLang API请求超时，正在取消请求...')
     controller.abort()
   }, 600000) // 10分钟超时
   
   const response = await fetch(config.endpoint, {
     method: 'POST',
     headers,
     body: JSON.stringify(requestBody),
     signal: controller.signal
   })
   
   clearTimeout(timeoutId)
   
   if (!response.ok) {
     let errorText = await response.text()
     let errorDetail = errorText
     
     // 尝试解析JSON错误响应
     try {
       const errorJson = JSON.parse(errorText)
       errorDetail = errorJson.error || errorJson.message || errorText
     } catch {
       // 如果不是JSON，使用原始文本
     }
     
     // 针对常见错误提供详细提示
     if (response.status === 500) {
       console.error('SGLang 500错误详情:', errorDetail)
       throw new Error(
         `SGLang服务器错误 (500)。可能原因：\n` +
         `1. 模型 "${config.model}" 未加载\n` +
         `2. SGLang服务未正常运行\n` +
         `3. 请求参数不兼容\n\n` +
         `建议操作：\n` +
         `- 检查SGLang服务日志\n` +
         `- 确认模型已正确加载\n` +
         `- 验证API端点配置\n\n` +
         `错误详情: ${errorDetail}`
       )
     }
     
     throw new Error(`SGLang API请求失败: ${response.status} - ${errorDetail}`)
   }
   
   const data = await response.json()
  
  if (!data.choices || !data.choices[0] || !data.choices[0].message) {
    throw new Error('SGLang API返回数据格式错误')
  }
  
  const result = stripLLMThinkingContent(data.choices[0].message.content)
  const endTime = Date.now()
  const endTimeStr = new Date().toISOString()
  const duration = endTime - startTime
  
  // 记录token使用量信息
  if (data.usage) {
    console.log(`[${endTimeStr}] SGLang Token使用统计:`)
    console.log(`- 请求Token数: ${data.usage.prompt_tokens || 'N/A'}`)
    console.log(`- 返回Token数: ${data.usage.completion_tokens || 'N/A'}`)
    console.log(`- 总Token数: ${data.usage.total_tokens || 'N/A'}`)
  } else {
    console.log(`[${endTimeStr}] SGLang API响应中未包含token使用量信息`)
  }
  
  console.log(`[${endTimeStr}] SGLang API响应完成`)
  console.log(`响应耗时: ${duration}ms (${(duration/1000).toFixed(2)}秒)`)
  console.log(`生成内容长度: ${result.length}字符`)
  console.log('完整响应数据结构:', Object.keys(data))
  console.log('完整生成内容:', result)
   
   return result
 }
 
/**
 * Ollama API调用
 */
function buildDevOllamaProxyEndpoint(endpoint: string): string {
  if (endpoint.startsWith('/')) {
    return endpoint
  }

  try {
    const url = new URL(endpoint)
    if (url.protocol !== 'http:' && url.protocol !== 'https:') {
      return endpoint
    }

    return `/ollama-proxy${url.pathname || '/api/chat'}?target=${encodeURIComponent(url.origin)}`
  } catch {
    return endpoint
  }
}

async function callOllamaAPI(
  messages: Array<{role: string, content: string}>,
  options: GenerateSummaryOptions
): Promise<string> {
  const config = options.ollamaConfig
  let endpoint = config?.endpoint || MODEL_CONFIG.endpoint
  const modelName = config?.model || options.model || MODEL_CONFIG.name
  
  // 检测开发环境并使用动态代理，避免用户修改IP后仍转发到旧的硬编码地址
  const isDev = import.meta.env?.DEV
  if (isDev) {
    endpoint = buildDevOllamaProxyEndpoint(endpoint)
  }
  
  const startTime = Date.now()
  const startTimeStr = new Date().toISOString()
  
  console.log(`[${startTimeStr}] 发送Ollama API请求`)
  console.log(`端点: ${endpoint}, 模型: ${modelName}`)
  
  // 根据Ollama官方API文档构建请求体
  const requestBody = {
    model: modelName,
    messages: messages,
    stream: false,  // 禁用流式响应
    options: {
      // 基本生成参数
      temperature: options.temperature || 0.5,
      top_p: options.top_p || 0.8,
      top_k: 40,  // 添加top_k参数
      repeat_penalty: 1.1,  // 重复惩罚
      
      // Token限制参数
      num_predict: Math.min(options.max_tokens || MODEL_CONFIG.maxOutputTokens, MODEL_CONFIG.maxOutputTokens),
      num_ctx: 32768,  // 上下文窗口大小
      
      // 停止序列（可选）
      stop: ['<|im_end|>', '</s>'],
      
      // 性能参数
      num_thread: -1,  // 使用所有可用线程
      num_gpu: -1      // 使用所有可用GPU
    },
    // 保持会话活跃时间
    keep_alive: '10m'
  }
  
  console.log('Ollama请求详情:', {
    endpoint,
    model: requestBody.model,
    messagesCount: messages.length,
    stream: requestBody.stream,
    keepAlive: requestBody.keep_alive,
    options: {
      temperature: requestBody.options.temperature,
      top_p: requestBody.options.top_p,
      top_k: requestBody.options.top_k,
      repeat_penalty: requestBody.options.repeat_penalty,
      num_ctx: requestBody.options.num_ctx,
      num_predict: requestBody.options.num_predict,
      num_thread: requestBody.options.num_thread,
      num_gpu: requestBody.options.num_gpu,
      stop: requestBody.options.stop
    },
    requestTime: startTimeStr
  })
  
  const controller = new AbortController()
  const timeoutId = setTimeout(() => {
    console.log('Ollama API请求超时，正在取消请求...')
    controller.abort()
  }, 600000) // 10分钟超时
  
  const response = await fetch(endpoint, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json'
    },
    body: JSON.stringify(requestBody),
    signal: controller.signal
  })
  
  clearTimeout(timeoutId)
  
  if (!response.ok) {
    let errorText = await response.text()
    let errorDetail = errorText
    
    // 尝试解析JSON错误响应
    try {
      const errorJson = JSON.parse(errorText)
      errorDetail = errorJson.error || errorText
    } catch {
      // 如果不是JSON，使用原始文本
    }
    
    // 针对500错误提供更详细的提示
    if (response.status === 500) {
      console.error('Ollama 500错误详情:', errorDetail)
      throw new Error(
        `Ollama服务器错误 (500)。可能原因：\n` +
        `1. 模型 "${modelName}" 未安装或未加载\n` +
        `2. Ollama服务未正常运行\n` +
        `3. 请求参数不兼容\n\n` +
        `建议操作：\n` +
        `- 运行 "ollama list" 查看已安装的模型\n` +
        `- 运行 "ollama pull ${modelName}" 下载模型\n` +
        `- 检查Ollama服务状态\n\n` +
        `错误详情: ${errorDetail}`
      )
    }
    
    throw new Error(`Ollama API请求失败: ${response.status} - ${errorDetail}`)
  }
  
  const data = await response.json()
  
  if (!data.message || !data.message.content) {
    throw new Error('Ollama API返回数据格式错误')
  }
  
  const result = stripLLMThinkingContent(data.message.content)
  const endTime = Date.now()
  const endTimeStr = new Date().toISOString()
  const duration = endTime - startTime
  
  // 记录token使用量和性能信息（根据Ollama官方API文档）
  if (data.prompt_eval_count || data.eval_count) {
    console.log(`[${endTimeStr}] Ollama Token使用统计:`)
    console.log(`- 请求Token数: ${data.prompt_eval_count || 'N/A'}`)
    console.log(`- 返回Token数: ${data.eval_count || 'N/A'}`)
    console.log(`- 总Token数: ${(data.prompt_eval_count || 0) + (data.eval_count || 0)}`)
    
    // 性能统计（根据官方文档格式）
    if (data.total_duration) {
      console.log(`- 总耗时: ${(data.total_duration / 1000000).toFixed(2)}ms`)
    }
    if (data.load_duration) {
      console.log(`- 模型加载时间: ${(data.load_duration / 1000000).toFixed(2)}ms`)
    }
    if (data.prompt_eval_duration) {
      console.log(`- 提示词评估时间: ${(data.prompt_eval_duration / 1000000).toFixed(2)}ms`)
    }
    if (data.eval_duration) {
      console.log(`- 生成时间: ${(data.eval_duration / 1000000).toFixed(2)}ms`)
      // 计算生成速度（tokens/秒）
      if (data.eval_count && data.eval_duration > 0) {
        const tokensPerSecond = (data.eval_count / data.eval_duration * 1000000000).toFixed(2)
        console.log(`- 生成速度: ${tokensPerSecond} tokens/秒`)
      }
    }
  } else {
    console.log(`[${endTimeStr}] Ollama API响应中未包含token使用量信息`)
  }
  
  console.log(`[${endTimeStr}] Ollama API响应完成`)
  console.log(`响应耗时: ${duration}ms (${(duration/1000).toFixed(2)}秒)`)
  console.log(`生成内容长度: ${result.length}字符`)
  console.log('完整响应数据结构:', Object.keys(data))
  console.log('完整生成内容:', result)
  
  return result
}

/**
 * 生成单个段落的会议纪要（分段处理时使用）
 */
async function generateSummaryForSegment(
  segment: string, 
  options: GenerateSummaryOptions, 
  segmentInfo?: { current: number; total: number }
): Promise<string> {
  try {
  // 为分段处理创建专门的系统提示词
  const segmentSystemPrompt = segmentInfo 
    ? `你是一个专业的会议纪要生成专家。这是一段较长会议内容的第${segmentInfo.current}部分（共${segmentInfo.total}部分）。

请为这部分内容生成结构化的纪要片段，重点关注：
1. 保持与其他部分的连贯性
2. 提取本段落的关键信息
3. 避免重复内容
4. 保持信息的完整性和准确性
5. 直接输出纪要内容，不需要思考过程

生成格式：
## 本段落主要议题
▸ 议题：[仅记录转录中明确讨论的具体话题，数量根据实际内容决定]
  - 讨论要点：[仅记录转录中的实际讨论内容，不得虚构]
  - 关键数据：[仅包含转录中明确提及的数字、百分比、金额等，不得虚构]
  - 各方观点：[仅记录转录中不同发言人的实际观点，不得虚构]
  - 达成共识：[仅记录转录中明确表达的一致意见，不得虚构]
  - 重要细节：[记录本段落中提到的重要细节信息，不得虚构]

## 重要信息
- 决策事项：[仅记录转录中明确的决策，如无则省略]
- 行动项：[仅记录转录中明确的任务，如无则省略]
- 时间节点：[仅记录转录中明确的时间，如无则省略]
- 参与人员：[仅记录转录中明确提及的人员，不得虚构]

特别要求：
- 严格基于提供的转录文本内容，绝对不添加、推测或虚构任何信息
- 保持所有具体信息的准确性，仅使用转录中的实际内容
- 对于转录中没有的信息，直接省略相关部分，不要标注"需补充"
- 只记录转录中实际存在的讨论点，不要为了完整性而添加内容
- 请直接输出纪要片段，不要包含思考过程或推理步骤
- 严禁输出<think>、</think>、<thinking>、</thinking>等任何思考标签
- 严禁输出任何形式的推理过程、内心独白或分析过程
- 严禁使用"我认为"、"我觉得"、"让我想想"等主观表达
- 严禁虚构议题、观点、数据、人员等任何信息
- 禁用所有形式的思维链(Chain of Thought)输出
${options.customRequirements ? `\n\n额外要求：\n${options.customRequirements}` : ''}

 /no_think`
    : createEnhancedSystemPrompt(options.customRequirements, options.templateId)

  const contextPrompt = segmentInfo
    ? `这是会议内容的第${segmentInfo.current}部分（共${segmentInfo.total}部分）：`
    : '会议转录内容：'

  const userContent = `${contextPrompt}\n\n${segment}`
  
  // 验证token数量
  const systemTokens = estimateTokenCount(segmentSystemPrompt)
  const userTokens = estimateTokenCount(userContent)
  const totalInputTokens = systemTokens + userTokens
  
  if (totalInputTokens > MODEL_CONFIG.maxContextTokens - MODEL_CONFIG.maxOutputTokens) {
    throw new Error(`输入内容过长，预估${totalInputTokens}个token，超过模型限制`)
  }

  const messages = [{
    role: 'system',
    content: segmentSystemPrompt + ' /no_think'
  }, {
    role: 'user',
    content: userContent + ' /no_think'
  }]
  
  console.log(`开始生成段落纪要 (${segmentInfo ? `${segmentInfo.current}/${segmentInfo.total}` : '单段'})`)
  console.log(`段落内容长度: ${segment.length} 字符`)
  
  const result = await callLLMAPI(messages, options)
  
  console.log(`段落纪要生成完成，内容长度: ${result.length} 字符`)
  return result
  
  } catch (error) {
    if (error instanceof Error) {
      if (error.name === 'AbortError') {
        console.error('API请求超时')
        throw new Error('API请求超时，请检查网络连接或稍后重试')
      } else {
        console.error('生成分段纪要失败:', error.message)
        throw error
      }
    } else {
      console.error('生成分段纪要时发生未知错误:', error)
      throw new Error('生成分段纪要时发生未知错误')
    }
  }
}

/**
 * 合并多个段落的会议纪要
 */
async function mergeSummaries(summaries: string[], options: GenerateSummaryOptions): Promise<string> {
  const mergeSystemPrompt = isProjectReviewTemplate(options.templateId)
    ? createProjectReviewSystemPrompt(options.customRequirements, true)
    : `你是一个专业的会议纪要整理助手。请将以下多个会议纪要片段合并成一份完整、连贯的会议纪要。

合并要求：
1. 保持所有重要信息和关键细节，避免遗漏任何具体内容
2. 统一格式，确保所有段落使用相同的结构
3. 将对应的内容归类整合到统一的标准格式中
4. 保持原有的具体数据、时间、人名、数字等关键细节不变，不得虚构，如果没有就不显示
5. 将各片段中的关键细节整合到相应的议题讨论下
6. 会议摘要应覆盖核心内容；转录内容较少时不强求字数
7. 去除重复内容，但保留所有独特信息和细节

标准输出格式：
## 会议基本信息
- 会议时间：[从各片段中提取，不得虚构，如果没有就不显示]
- 会议地点：[从各片段中提取，不得虚构，如果没有就不显示]
- 参与者：[合并所有提到的参与者，不得虚构，如果没有就不显示]
- 会议主题和目标：[整合各片段的主题]

## 会议摘要
[整合所有片段的核心内容、目标与结论，不得虚构；内容较少时保持简洁]

## 主要议题讨论
[按时间顺序整理，合并所有片段的讨论要点，议题数量根据实际内容决定，将关键细节整合到相应议题下]
▸ 议题名称：[整合所有讨论主题]
  - 讨论要点：[详细记录所有讨论内容和关键细节]
  - 关键数据：[合并所有具体数字、百分比、金额等关键细节]
  - 各方观点：[汇总各方观点和意见，包含具体细节]
  - 达成共识：[整理已达成共识的结论，包含具体细节]
  - 重要细节：[整合各片段中提到的重要细节信息]

## 重要决策
[合并所有片段中的决策事项]
▸ [整合决策内容]
▸ [合并决策依据和影响]
▸ [统一时间节点]

## 待办事项
[汇总所有片段的任务]
▸ [合并任务内容]
▸ [整理负责人信息，不得虚构，如果没有就不显示]
▸ [统一截止时间]
▸ [合并优先级和依赖关系]

## 后续安排
[整合所有后续计划]
- [合并下次会议安排]
- [汇总跟进事项]
- [整理风险点和注意事项]

特别要求：
7. 重点关注关键细节的保留：确保所有具体数字、时间点、人员姓名、技术参数等细节信息都被整合到相应的议题下
8. 细节归类整合：将散布在各片段中的相关细节信息归类到同一议题下，形成完整的讨论记录
9. 直接输出合并后的会议纪要，不需要思考过程或解释
10. 严禁输出<think>、</think>、<thinking>、</thinking>等任何思考标签
11. 严禁输出任何形式的推理过程、内心独白或分析过程
12. 严禁使用"我认为"、"我觉得"、"让我想想"等主观表达
13. 禁用所有形式的思维链(Chain of Thought)输出
14. 只输出纯净的会议纪要内容，不包含任何元信息

请合并以下会议纪要片段：

/no_think`
  
  const content = summaries.join('\n\n---分段---\n\n')
  
  // 检查合并内容的token数量
  const systemTokens = estimateTokenCount(mergeSystemPrompt)
  const contentTokens = estimateTokenCount(content)
  
  if (systemTokens + contentTokens > MODEL_CONFIG.maxContextTokens - MODEL_CONFIG.maxOutputTokens) {
    // 如果内容过长，采用分批合并策略
    return await batchMergeSummaries(summaries, options)
  }
  
  const messages = [{
    role: 'system',
    content: mergeSystemPrompt + ' /no_think'
  }, {
    role: 'user',
    content: content + ' /no_think'
  }]
  
  console.log(`开始合并${summaries.length}个会议纪要片段`)
  console.log(`合并内容总长度: ${content.length} 字符`)
  
  // 为合并过程设置更保守的参数
  const mergeOptions = {
    ...options,
    temperature: 0.5, // 降低温度确保稳定输出
    top_p: 0.8
  }
  
  const result = await callLLMAPI(messages, mergeOptions)
  
  console.log(`会议纪要合并完成，最终长度: ${result.length} 字符`)
  return result
}

/**
 * 分批合并会议纪要（当内容过长时使用）
 */
async function batchMergeSummaries(summaries: string[], options: GenerateSummaryOptions): Promise<string> {
  const batchSize = Math.ceil(summaries.length / 2)
  const batches: string[][] = []
  
  for (let i = 0; i < summaries.length; i += batchSize) {
    batches.push(summaries.slice(i, i + batchSize))
  }
  
  const mergedBatches: string[] = []
  for (const batch of batches) {
    const merged = await mergeSummaries(batch, options)
    mergedBatches.push(merged)
  }
  
  if (mergedBatches.length === 1) {
    return mergedBatches[0]
  }
  
  // 递归合并
  return await batchMergeSummaries(mergedBatches, options)
}

/**
 * 最终版会议纪要系统提示词
 */
function createEnhancedSystemPrompt(customRequirements?: string, templateId?: string): string {
  return createSingleSegmentFinalSystemPrompt(customRequirements, templateId)
    .replace('请基于提供的单段会议录音转写文本', '请基于提供的会议录音转写文本')
}

function isProjectReviewTemplate(templateId?: string): boolean {
  return templateId === 'project_review'
}

function createProjectReviewSystemPrompt(customRequirements?: string, merge = false): string {
  const intro = merge
    ? '你是专业会议纪要整理助手。下面输入的是多个分段生成的会议纪要片段，请去重、归并、重组，合并为一份完整的“方案评审型会议纪要”。不要保留“第1段/第2段”等分段痕迹。'
    : '你是专业会议纪要整理助手。请基于提供的会议转录内容，生成一份“方案评审型会议纪要”。'
  const sourceLabel = merge ? '片段' : '转录文本'
  const basePrompt = `${intro}

输出必须使用以下结构：

会议主题：[用一句话概括会议核心主题，优先使用${sourceLabel}中明确提到的系统、项目、方案名称]
发言人：[仅列出${sourceLabel}中实际出现的发言人名称，用顿号分隔；不要虚构]
会议摘要：[用一段话概括本次会议讨论的核心事项、形成的结论、后续推进方向，控制在150-300字]

---

一、[一级议题名称]
[用一段话概括该议题的讨论背景、目标和结论]

1. [二级主题]
[整理该主题下的具体讨论内容、统计口径、规则、方案、争议点或结论。必须保留关键名词、系统名称、业务口径、数字、流程节点等信息。]

2. [二级主题]
[继续整理同一一级议题下的相关内容。]

二、[一级议题名称]
[继续按同样格式整理。]

---

四、待办事项
[仅提取会议中明确要求后续推进、测试、调整、沟通、提供资料、更新文档等事项。每条单独一行。格式为：任务内容。 @负责人]
[如果负责人不明确，使用 @待确认]
[如果没有明确待办事项，输出：本次转录中未明确待办事项。]

严格要求：
- 只基于${sourceLabel}整理，不得虚构会议主题、发言人、任务、负责人、时间、结论。
- 不要输出“会议基本信息”“主要议题讨论”等标准模板标题。
- 一级标题使用中文数字编号：一、二、三、四。
- 二级条目使用阿拉伯数字编号：1. 2. 3.
- 每个一级议题下先写一段概括，再写二级条目。
- 待办事项必须尽量写成可执行动作，并在末尾标注 @负责人。
- 如果原文中出现多个系统、多个方案，需要按主题归类，不要按发言顺序机械堆叠。
- 保留业务术语和关键细节，例如统计口径、审批节点、测试环境、权限视图、上线策略、数据范围等。
- 不输出思考过程、分析过程、解释说明或任何 <think> 标签。`

  return customRequirements ? `${basePrompt}\n\n额外要求：\n${customRequirements}\n\n/no_think` : `${basePrompt}\n\n/no_think`
}

function createSingleSegmentFinalSystemPrompt(customRequirements?: string, templateId?: string): string {
  if (isProjectReviewTemplate(templateId)) {
    return createProjectReviewSystemPrompt(customRequirements)
  }

  const basePrompt = `你是一个专业的会议纪要生成专家。请基于提供的单段会议录音转写文本，直接生成最终版会议纪要。

生成要求：
- 会议摘要用300字概括会议核心目标与最终结论。
- 主要内容按议题分点整理，最少10条；每条必须只基于转录文本中明确提到的信息。
- 仅提取明确提到的信息，不推测未说明的细节。
- 如果转录中明确议题不足10条，不得虚构补齐，需标注“转录中明确议题不足10条”。

输出结构：
## 会议摘要（300字）
[用300字概括会议核心目标与最终结论；仅提取明确提到的信息，不推测未说明的细节]

## 主要内容
[按议题分点整理，最少10条；仅记录转录文本中实际讨论的议题，按讨论顺序整理]
▸ 议题1：[讨论主题，直接引用会议中的命名]
  - 关键数据/观点：[仅转录文本中出现的具体信息，没有则标注“未明确提及”]
  - 已达成共识的结论：[仅记录明确共识，没有则标注“未明确达成共识”]

## 待办事项
[仅记录会议中明确指定的任务；没有则标注“转录中未涉及具体待办事项”]
▸ 任务内容：[直接引用任务描述原话]
▸ 负责人：[以会议中指定的称呼为准；未明确则标注“待确认”]
▸ 截止时间：[格式：YYYY/MM/DD，无明确时间则标注待确认]

特别要求：
- 若任务要求存在模糊处，标注需补充说明而非自行解释。
- 严格基于转录文本，绝对不添加、推测或虚构任何信息。
- 请直接输出会议纪要，不要包含思考过程或推理步骤。
- 严禁输出<think>、</think>、<thinking>、</thinking>等任何思考标签。
- 严禁输出任何形式的推理过程、内心独白或分析过程。
- 严禁使用"我认为"、"我觉得"、"让我想想"等主观表达。
- 禁用所有形式的思维链(Chain of Thought)输出。`

  return customRequirements ? `${basePrompt}\n\n额外要求：\n${customRequirements}\n\n/no_think` : `${basePrompt}\n\n/no_think`
}

/**
 * 直接处理完整文本（优先方案）
 */
async function generateDirectSummary(transcript: string, options: GenerateSummaryOptions): Promise<string> {
  const systemPrompt = createEnhancedSystemPrompt(options.customRequirements, options.templateId)
  const userContent = `会议转录内容：\n${transcript}`
  
  // 验证token数量
  const systemTokens = estimateTokenCount(systemPrompt)
  const userTokens = estimateTokenCount(userContent)
  const totalInputTokens = systemTokens + userTokens
  
  console.log(`直接处理模式 - 系统提示词: ${systemTokens} tokens, 用户内容: ${userTokens} tokens, 总计: ${totalInputTokens} tokens`)
  
  if (totalInputTokens > MODEL_CONFIG.maxContextTokens - MODEL_CONFIG.maxOutputTokens) {
    throw new Error('CONTENT_TOO_LONG')
  }

  const messages = [{
    role: 'system',
    content: systemPrompt + ' /no_think'
  }, {
    role: 'user',
    content: userContent + ' /no_think'
  }]
  
  console.log(`直接处理模式 - 内容长度: ${userContent.length} 字符, 预计token: ${totalInputTokens}`)
  
  const result = await callLLMAPI(messages, options)
  
  console.log(`直接处理完成，生成内容长度: ${result.length} 字符`)
  return result
}

async function generateSingleSegmentFinalSummary(transcript: string, options: GenerateSummaryOptions): Promise<string> {
  const systemPrompt = createSingleSegmentFinalSystemPrompt(options.customRequirements, options.templateId)
  const userContent = `会议转录内容：\n${transcript}`

  const systemTokens = estimateTokenCount(systemPrompt)
  const userTokens = estimateTokenCount(userContent)
  const totalInputTokens = systemTokens + userTokens

  console.log(`单段最终纪要模式 - 系统提示词: ${systemTokens} tokens, 用户内容: ${userTokens} tokens, 总计: ${totalInputTokens} tokens`)

  if (totalInputTokens > MODEL_CONFIG.maxContextTokens - MODEL_CONFIG.maxOutputTokens) {
    throw new Error('CONTENT_TOO_LONG')
  }

  const messages = [{
    role: 'system',
    content: systemPrompt + ' /no_think'
  }, {
    role: 'user',
    content: userContent + ' /no_think'
  }]

  const result = await callLLMAPI(messages, options)

  console.log(`单段最终纪要生成完成，内容长度: ${result.length} 字符`)
  return result
}

/**
 * 评估生成纪要的完整性
 */
function assessSummaryCompleteness(summary: string, originalText: string): number {
  // 检查必需的结构部分（更灵活的匹配）
  const requiredSections = [
    { patterns: ['会议摘要', '摘要', '概述', '总结'], weight: 0.2 },
    { patterns: ['主要议题', '议题讨论', '讨论要点', '核心议题'], weight: 0.2 },
    { patterns: ['重要决策', '决策事项', '决定', '结论'], weight: 0.2 },
    { patterns: ['待办事项', '行动项', '任务', '跟进事项'], weight: 0.2 },
    { patterns: ['会议基本信息', '基本信息', '会议时间', '参与者'], weight: 0.1 },
    { patterns: ['后续安排', '下次会议', '跟进计划'], weight: 0.1 }
  ]
  
  let structureScore = 0
  requiredSections.forEach(section => {
    const hasSection = section.patterns.some(pattern => 
      summary.includes(pattern) || 
      summary.toLowerCase().includes(pattern.toLowerCase()) ||
      new RegExp(pattern, 'i').test(summary)
    )
    if (hasSection) {
      structureScore += section.weight
    }
  })
  
  // 检查内容长度和详细程度
  let lengthScore = 0
  const summaryLength = summary.length
  const originalLength = originalText.length
  
  if (summaryLength > 200) lengthScore += 0.1  // 基本长度
  if (summaryLength > 500) lengthScore += 0.1  // 详细程度
  if (summaryLength > 1000) lengthScore += 0.1 // 充分详细
  
  // 检查关键信息覆盖度（降低权重，避免过度依赖特定模式）
  const keyPatterns = [
    /\d{4}[年/-]\d{1,2}[月/-]\d{1,2}/g, // 日期
    /\d+[万千百十]?[元块钱]/g, // 金额
    /\d+%/g, // 百分比
    /负责人|责任人|联系人|主持人/g, // 责任人
    /截止|期限|时间|完成时间/g, // 时间要求
    /[A-Za-z\u4e00-\u9fa5]+(?:部门|公司|团队|组织)/g // 组织机构
  ]
  
  let contentScore = 0
  let totalPatterns = 0
  let matchedPatterns = 0
  
  keyPatterns.forEach(pattern => {
    const originalMatches = (originalText.match(pattern) || []).length
    const summaryMatches = (summary.match(pattern) || []).length
    if (originalMatches > 0) {
      totalPatterns++
      const coverage = Math.min(summaryMatches / originalMatches, 1)
      if (coverage > 0) matchedPatterns++
      contentScore += coverage * 0.05 // 降低单个模式的权重
    }
  })
  
  // 如果原文没有特定模式，给予基础分数
  if (totalPatterns === 0) {
    contentScore = 0.2 // 给予基础内容分数
  }
  
  // 检查markdown格式质量
  let formatScore = 0
  const hasHeaders = /^#{1,6}\s+.+$/m.test(summary)
  const hasBulletPoints = /^[\s]*[▸•-]\s+.+$/m.test(summary)
  const hasNumberedList = /^[\s]*\d+\.\s+.+$/m.test(summary)
  
  if (hasHeaders) formatScore += 0.05
  if (hasBulletPoints) formatScore += 0.05
  if (hasNumberedList) formatScore += 0.05
  
  const totalScore = Math.min(structureScore + lengthScore + contentScore + formatScore, 1.0)
  
  console.log(`完整性评分详情: 结构=${(structureScore*100).toFixed(0)}%, 长度=${(lengthScore*100).toFixed(0)}%, 内容=${(contentScore*100).toFixed(0)}%, 格式=${(formatScore*100).toFixed(0)}%, 总分=${(totalScore*100).toFixed(0)}%`)
  
  return totalScore
}

/**
 * 主要的会议纪要生成函数（混合式处理）
 */
export async function generateSummary(transcript: string, options: GenerateSummaryOptions = {}): Promise<string> {
  if (!transcript || transcript.trim().length === 0) {
    throw new Error('没有可用的语音转写内容')
  }

  const totalStartTime = Date.now()
  const totalStartTimeStr = new Date().toISOString()
  
  const loadingMessage = ElMessage({
    message: '正在生成会议纪要...',
    type: 'info',
    duration: 0,
    showClose: false
  })

  try {
    console.log(`\n=== [${totalStartTimeStr}] 开始生成会议纪要 ===`)
    console.log('输入文本长度:', transcript.length, '字符')
    console.log('配置选项:', options)

    if (options.useBackendSummary !== false) {
      ElMessage({
        message: '已提交后端会议纪要生成任务...',
        type: 'info',
        duration: 1500
      })

      const backendSummary = await callBackendSummaryTask(transcript, options)
      const completenessScore = assessSummaryCompleteness(backendSummary, transcript)
      const totalEndTime = Date.now()
      const totalEndTimeStr = new Date().toISOString()
      const totalDuration = totalEndTime - totalStartTime

      console.log(`\n=== [${totalEndTimeStr}] 会议纪要生成完成（后端任务） ===`)
      console.log(`总耗时: ${totalDuration}ms (${(totalDuration/1000).toFixed(2)}秒)`)
      console.log(`完整性评分: ${(completenessScore * 100).toFixed(0)}%`)

      loadingMessage.close()
      ElMessage.success('会议纪要生成成功（后端任务）')
      return backendSummary
    }
    
    // 优先尝试直接处理
    try {
      ElMessage({
        message: '尝试直接处理完整内容...',
        type: 'info',
        duration: 1500
      })
      
      const directSummary = await generateDirectSummary(transcript, options)
      
      // 评估完整性
      const completenessScore = assessSummaryCompleteness(directSummary, transcript)
      console.log(`直接处理完整性评分: ${(completenessScore * 100).toFixed(0)}%`)
      
      if (completenessScore < 0.5) {
        console.warn('直接处理完整性评分偏低，但保留已生成结果，避免短会或无决策会议被强制重跑')
      }

      const totalEndTime = Date.now()
      const totalEndTimeStr = new Date().toISOString()
      const totalDuration = totalEndTime - totalStartTime
      
      console.log(`\n=== [${totalEndTimeStr}] 会议纪要生成完成（直接处理） ===`)
      console.log(`总耗时: ${totalDuration}ms (${(totalDuration/1000).toFixed(2)}秒)`)
      console.log(`完整性评分: ${(completenessScore * 100).toFixed(0)}%`)
      
      loadingMessage.close()
      ElMessage.success('会议纪要生成成功（直接处理）')
      return directSummary
      
    } catch (error) {
      if (error instanceof Error && error.message === 'CONTENT_TOO_LONG') {
        console.log('切换到分段处理模式:', error.message)
      } else {
        throw error // 重新抛出其他错误
      }
    }
    
    // 后备方案：分段处理
    ElMessage({
      message: '使用分段处理模式...',
      type: 'info',
      duration: 1500
    })
    
    // 估算系统提示词的token数量
    const segmentationStartTime = Date.now()
    const systemPromptTokens = estimateTokenCount(createEnhancedSystemPrompt(options.customRequirements, options.templateId))
    console.log(`系统提示词token数: ${systemPromptTokens}`)
    
    // 智能分段
    const segments = intelligentSegmentation(transcript, systemPromptTokens)
    const segmentationEndTime = Date.now()
    const segmentationDuration = segmentationEndTime - segmentationStartTime
    
    console.log(`\n=== 分段处理信息 ===`)
    console.log(`分段耗时: ${segmentationDuration}ms`)
    console.log(`文本已分为${segments.length}个段落`)
    console.log(`原文总长度: ${transcript.length}字符`)
    
    // 显示每个段落的详细信息
    segments.forEach((segment, index) => {
      const segmentTokens = estimateTokenCount(segment)
      const segmentPreview = segment.substring(0, 100).replace(/\n/g, ' ') + (segment.length > 100 ? '...' : '')
      console.log(`段落${index + 1}: ${segment.length}字符, 约${segmentTokens}tokens`)
      console.log(`  预览: ${segmentPreview}`)
    })
    
    if (segments.length === 1) {
      // 分段后只有一段时，直接使用最终会议纪要提示词生成，不走分段片段提示词
      const summary = await generateSingleSegmentFinalSummary(segments[0], options)
      
      const totalEndTime = Date.now()
      const totalEndTimeStr = new Date().toISOString()
      const totalDuration = totalEndTime - totalStartTime
      
      console.log(`\n=== [${totalEndTimeStr}] 会议纪要生成完成（单段最终提示词） ===`)
      console.log(`总耗时: ${totalDuration}ms (${(totalDuration/1000).toFixed(2)}秒)`)
      
      loadingMessage.close()
      ElMessage.success('会议纪要生成成功')
      return summary
    }
    
    // 多段落处理
    ElMessage({
      message: `正在处理${segments.length}个文本段落...`,
      type: 'info',
      duration: 2000
    })
    
    // 添加超时控制的分段处理
    console.log(`\n=== 开始分段处理 ===`)
    const summaries: string[] = []
    const segmentProcessingStartTime = Date.now()
    
    for (let i = 0; i < segments.length; i++) {
      try {
        const segmentStartTime = Date.now()
        const segmentStartTimeStr = new Date().toISOString()
        
        console.log(`\n--- [${segmentStartTimeStr}] 开始处理第${i + 1}/${segments.length}个段落 ---`)
        console.log(`段落长度: ${segments[i].length}字符`)
        console.log(`预计token数: ${estimateTokenCount(segments[i])}`)
        
        ElMessage({
          message: `正在处理第${i + 1}/${segments.length}个段落...`,
          type: 'info',
          duration: 1000
        })
        
        // 为每个分段添加超时控制
        const segmentPromise = generateSummaryForSegment(segments[i], options, {
          current: i + 1,
          total: segments.length
        })
        
        const timeoutPromise = new Promise<never>((_, reject) => {
           setTimeout(() => reject(new Error(`第${i + 1}个段落处理超时`)), 600000) // 10分钟超时
         })
        
        const summary = await Promise.race([segmentPromise, timeoutPromise])
        
        const segmentEndTime = Date.now()
        const segmentEndTimeStr = new Date().toISOString()
        const segmentDuration = segmentEndTime - segmentStartTime
        
        summaries.push(summary)
        
        console.log(`--- [${segmentEndTimeStr}] 第${i + 1}个段落处理完成 ---`)
        console.log(`处理耗时: ${segmentDuration}ms (${(segmentDuration/1000).toFixed(2)}秒)`)
        console.log(`生成内容长度: ${summary.length}字符`)
        console.log(`生成内容预览: ${summary.substring(0, 200).replace(/\n/g, ' ')}${summary.length > 200 ? '...' : ''}`)
        
      } catch (error) {
        const segmentEndTime = Date.now()
        const segmentEndTimeStr = new Date().toISOString()
        
        console.error(`--- [${segmentEndTimeStr}] 第${i + 1}个段落处理失败 ---`)
        console.error(`错误信息:`, error)
        throw new Error(`第${i + 1}个段落处理失败: ${(error as Error).message}`)
      }
    }
    
    const segmentProcessingEndTime = Date.now()
    const segmentProcessingDuration = segmentProcessingEndTime - segmentProcessingStartTime
    
    console.log(`\n=== 分段处理完成 ===`)
    console.log(`总分段处理耗时: ${segmentProcessingDuration}ms (${(segmentProcessingDuration/1000).toFixed(2)}秒)`)
    console.log(`成功处理段落数: ${summaries.length}/${segments.length}`)
    console.log(`各段落生成内容长度: ${summaries.map(s => s.length).join(', ')}字符`)
    
    // 合并纪要
    const mergeStartTime = Date.now()
    const mergeStartTimeStr = new Date().toISOString()
    
    console.log(`\n=== [${mergeStartTimeStr}] 开始合并会议纪要 ===`)
    console.log(`待合并段落数: ${summaries.length}`)
    console.log(`各段落长度: ${summaries.map(s => s.length).join(', ')}字符`)
    console.log(`合并前总长度: ${summaries.reduce((total, s) => total + s.length, 0)}字符`)
    
    ElMessage({
      message: '正在合并会议纪要...',
      type: 'info',
      duration: 0,
      showClose: false
    })
    
    const finalSummary = await mergeSummaries(summaries, options)
    
    const mergeEndTime = Date.now()
    const mergeEndTimeStr = new Date().toISOString()
    const mergeDuration = mergeEndTime - mergeStartTime
    
    console.log(`=== [${mergeEndTimeStr}] 会议纪要合并完成 ===`)
    console.log(`合并耗时: ${mergeDuration}ms (${(mergeDuration/1000).toFixed(2)}秒)`)
    console.log(`合并后长度: ${finalSummary.length}字符`)
    console.log(`合并后预览: ${finalSummary.substring(0, 300).replace(/\n/g, ' ')}${finalSummary.length > 300 ? '...' : ''}`)
    
    if (!finalSummary || finalSummary.trim().length === 0) {
      throw new Error('生成的会议纪要内容为空')
    }
    
    // 最终完整性检查
    const completenessStartTime = Date.now()
    const finalCompletenessScore = assessSummaryCompleteness(finalSummary, transcript)
    const completenessEndTime = Date.now()
    const completenessDuration = completenessEndTime - completenessStartTime
    
    console.log(`\n=== 完整性评估结果 ===`)
    console.log(`评估耗时: ${completenessDuration}ms`)
    console.log(`最终完整性评分: ${(finalCompletenessScore * 100).toFixed(0)}%`)
    
    const totalEndTime = Date.now()
    const totalEndTimeStr = new Date().toISOString()
    const totalDuration = totalEndTime - totalStartTime
    
    console.log(`\n=== [${totalEndTimeStr}] 会议纪要生成完成 ===`)
    console.log(`总耗时: ${totalDuration}ms (${(totalDuration/1000).toFixed(2)}秒)`)
    console.log(`处理模式: 分段处理 (${segments.length}个段落)`)
    console.log(`最终内容长度: ${finalSummary.length}字符`)
    console.log(`最终完整性评分: ${(finalCompletenessScore * 100).toFixed(0)}%`)
    
    // 性能统计
    console.log(`\n=== 性能统计 ===`)
    console.log(`分段耗时: ${segmentationDuration}ms (${((segmentationDuration/totalDuration)*100).toFixed(1)}%)`)
    console.log(`段落处理耗时: ${segmentProcessingDuration}ms (${((segmentProcessingDuration/totalDuration)*100).toFixed(1)}%)`)
    console.log(`合并耗时: ${mergeDuration}ms (${((mergeDuration/totalDuration)*100).toFixed(1)}%)`)
    console.log(`评估耗时: ${completenessDuration}ms (${((completenessDuration/totalDuration)*100).toFixed(1)}%)`)
    console.log(`平均每段落耗时: ${(segmentProcessingDuration/segments.length).toFixed(0)}ms`)
    
    loadingMessage.close()
    ElMessage.success(`会议纪要生成成功（分段处理，完整性: ${(finalCompletenessScore * 100).toFixed(0)}%）`)
    return finalSummary
    
  } catch (error) {
    loadingMessage.close()
    console.error('生成会议纪要失败:', error)
    
    if (error instanceof Error) {
      if (error.message.includes('token')) {
        ElMessage.error('内容过长，请尝试分段处理或减少内容长度')
      } else if (error.message.includes('API请求失败')) {
        ElMessage.error('API服务异常，请检查网络连接或稍后重试')
      } else {
        ElMessage.error(`生成失败：${error.message}`)
      }
    } else {
      ElMessage.error('生成会议纪要时发生未知错误')
    }
    
    throw error
  }
}

// 导出工具函数供外部使用
export { estimateTokenCount, intelligentSegmentation, MODEL_CONFIG }
