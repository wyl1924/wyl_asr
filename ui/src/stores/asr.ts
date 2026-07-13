import { defineStore } from 'pinia'
import { ref } from 'vue'
import { ElMessage } from 'element-plus'
import { WS_CONFIG, API_ENDPOINTS } from '../config/api'
import '../utils/recorder/recorder-core.js'
import '../utils/recorder/wav.js'
import '../utils/recorder/pcm.js'

// 确保录音器正确初始化
if (typeof window !== 'undefined') {
  // 等待录音器加载完成
  const checkRecorder = () => {
    if (!window.Recorder) {
      console.error('Recorder未正确加载')
      return false
    }
    if (!window.Recorder.prototype.wav) {
      console.error('WAV编码器未正确加载')
      return false
    }
    if (!window.Recorder.pcm2wav) {
      console.error('pcm2wav函数未正确加载')
      return false
    }
    console.log('录音器组件加载完成')
    return true
  }
  
  // 延迟检查，确保所有脚本都已加载
  setTimeout(checkRecorder, 100)
}

declare global {
  interface Window {
    Recorder: any;
  }
}

interface AsrWebSocket extends WebSocket {
  isConnected?: boolean
}

// 说话人信息接口
interface SpeakerSegment {
  speaker: string
  text: string
  timestamp?: string | number[][]  // 原始时间戳数据
  mode: string
  startTime?: string  // 开始时间（格式化）如 "00:00:35"
  endTime?: string    // 结束时间（格式化）如 "00:00:40"
  startMs?: number    // 开始时间（毫秒）
  endMs?: number      // 结束时间（毫秒）
  translation?: string // 英文翻译
  registrationAudio?: {
    file_name?: string
    source_file_name?: string
    time_base?: string
    sample_rate?: number
    channels?: number
  }
}

export const useAsrStore = defineStore('asr', () => {
  const transcript = ref('')
  const offlineTranscript = ref('')
  const isRecording = ref(false)
  const hotWords = ref('')
  const wsConnection = ref<AsrWebSocket | null>(null)

  const audioDevices = ref<MediaDeviceInfo[]>([])
  const audioSource = ref('')
  const language = ref('zh')
  const asrMode = ref('2pass')
  const wsUrl = ref(WS_CONFIG.ASR_URL)
  // const hotWordsText = ref('') // 暂时注释未使用的变量
  const audioUrl = ref('')
  const uploadedMediaTaskId = ref('')
  const uploadedMediaFileName = ref('')
  const useITN = ref(false)
  const meetingSummary = ref('')
  
  // 音频采集模式：'browser' - 浏览器采集音频发送给服务器，'server' - 服务器自己采集音频
  const audioCaptureMode = ref<'browser' | 'server'>(localStorage.getItem('audio_capture_mode') as 'browser' | 'server' || 'browser')
  
  // 说话人相关状态
  const speakerSegments = ref<SpeakerSegment[]>([])
  const currentSpeaker = ref('')
  const lastSpeaker = ref('')
  const onlineText = ref('')
  const onlineTranslation = ref('')

  // 翻译功能开关
  const enableTranslation = ref<boolean>(localStorage.getItem('enable_translation') === 'true')

  const isSpeakerDiarizationEnabled = () => {
    return localStorage.getItem('enable_speaker_diarization') !== 'false'
  }

  async function getAudioDevices() {
    try {
      if (audioCaptureMode.value === 'browser') {
        // 浏览器采集模式：获取本地音频设备
        // 检查浏览器是否支持录音
        if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
          throw new Error('您的浏览器不支持录音功能')
        }

        // 检查是否已授权音频权限
        const permissionStatus = await navigator.permissions.query({ name: 'microphone' as PermissionName })
        if (permissionStatus.state === 'denied') {
          throw new Error('请允许使用麦克风权限')
        }

        // 获取设备权限
        const stream = await navigator.mediaDevices.getUserMedia({ 
          audio: {
            echoCancellation: true,
            noiseSuppression: true,
            autoGainControl: true
          }
        })
        
        // 获取所有设备列表
        const devices = await navigator.mediaDevices.enumerateDevices()
        const inputDevices = devices.filter(device => device.kind === 'audioinput')
        
        if (inputDevices.length === 0) {
          throw new Error('未检测到任何音频输入设备')
        }

        // 更新音频设备列表
        audioDevices.value = inputDevices
        
        // 选择默认设备
        const defaultDevice = inputDevices.find(device => device.deviceId === 'default')
        if (defaultDevice) {
          audioSource.value = defaultDevice.deviceId
        } else {
          audioSource.value = inputDevices[0].deviceId
        }

        // 释放临时媒体流
        stream.getTracks().forEach(track => track.stop())
      } else {
        // 服务器采集模式：从服务器API获取音频设备列表
        const response = await fetch(API_ENDPOINTS.AUDIO_DEVICES.LIST)
        if (!response.ok) {
          const errorText = await response.text()
          throw new Error(`获取服务器音频设备失败: ${response.status} - ${errorText}`)
        }
        
        const result = await response.json()
        
        // 检查API响应格式
        if (!result.data || !result.data.devices) {
          throw new Error('服务器返回的数据格式不正确')
        }
        
        if (result.data.devices.length === 0) {
          throw new Error('服务器未检测到任何音频输入设备')
        }
        
        // 转换服务器返回的设备列表为浏览器格式
        audioDevices.value = result.data.devices.map((device: any) => ({
          deviceId: device.id || device.index.toString(),
          kind: 'audioinput',
          label: device.name,
          groupId: ''
        } as MediaDeviceInfo))
        
        // 选择默认设备
        if (result.data.default_device) {
          audioSource.value = result.data.default_device
        } else {
          audioSource.value = audioDevices.value[0].deviceId
        }
      }

      return true
    } catch (error) {
      console.error('获取音频设备失败:', error)
      throw error
    }
  }

  // 设备变更监听
  const deviceChangeHandler = async () => {
    try {
      await getAudioDevices()
    } catch (error) {
      console.error('设备变更处理失败:', error)
    }
  }

  navigator.mediaDevices.removeEventListener('devicechange', deviceChangeHandler)
  navigator.mediaDevices.addEventListener('devicechange', deviceChangeHandler)

  // 音频缓冲区 - 与samples版本保持一致
  let sampleBuf = new Int16Array()
  
  // 初始值为 null，避免在 defineStore 阶段构造多余的 Recorder 实例（含麦克风权限请求）
  const rec = ref<any>(null)

  

  function getHotWords() {
    if (!hotWords.value) {
      console.log(`[${new Date().toLocaleTimeString()}] 热词文本为空，不进行热词优化`)
      return null
    }
    
    const items = hotWords.value.split(/[\r\n]+/).filter(item => item.trim() !== '')
    const jsonResult: Record<string, number> = {}
    const regexNum = /^[0-9]*$/

    for (const item of items) {
      const result = item.split(' ')
      if (result.length >= 2 && regexNum.test(result[result.length - 1])) {
        const wordStr = result.slice(0, -1).join(' ')
        jsonResult[wordStr.trim()] = parseInt(result[result.length - 1])
      }
    }

    const hotWordsStr = Object.keys(jsonResult).length > 0 ? JSON.stringify(jsonResult) : null
    console.log(`[${new Date().toLocaleTimeString()}] 解析热词结果:`, hotWordsStr)
    return hotWordsStr
  }

  function startRecording() {
    // 清空当前文本和音频缓冲区
    transcript.value = ''
    offlineTranscript.value = ''
    uploadedMediaTaskId.value = ''
    uploadedMediaFileName.value = ''
    sampleBuf = new Int16Array() // 重置音频缓冲区
    console.log(`[${new Date().toLocaleTimeString()}] 开始录音，ASR模式: ${asrMode.value}, 音频采集模式: ${audioCaptureMode.value}`);
    
    // 建立WebSocket连接
    if (wsConnection.value) {
      wsConnection.value.close()
      wsConnection.value = null
    }
    
    wsConnection.value = new WebSocket(wsUrl.value, ['binary']) as AsrWebSocket
    console.log(`[${new Date().toLocaleTimeString()}] 尝试连接WebSocket服务器: ${wsUrl.value}`);
    console.log(`[${new Date().toLocaleTimeString()}] 当前使用的音频输入设备: ID=${audioSource.value}, 名称=${audioDevices.value.find(device => device.deviceId === audioSource.value)?.label || '未知设备'}`);
    
    // 等待WebSocket连接建立，超时时通过 UI 提示并重置状态（setTimeout 内 throw 无法被外层 catch）
    const wsConnectTimeout = setTimeout(() => {
      if (!wsConnection.value?.isConnected) {
        console.error(`[${new Date().toLocaleTimeString()}] WebSocket连接超时`)
        ElMessage.error('WebSocket连接超时，请检查服务器是否启动')
        wsConnection.value?.close()
        wsConnection.value = null
        isRecording.value = false
      }
    }, 5000)

    wsConnection.value.onopen = () => {
      clearTimeout(wsConnectTimeout)
      console.log(`[${new Date().toLocaleTimeString()}] WebSocket连接已建立`);
      wsConnection.value!.isConnected = true
      
      // 发送初始化配置
      const config: {
        chunk_size: number[];
        wav_name: string;
        is_speaking: boolean;
        chunk_interval: number;
        mode: string;
        language: string;
        audio_capture_mode?: string;
        server_audio_device?: string;
        hotwords?: string;
        enable_speaker_diarization?: boolean;
        enable_translation?: boolean;
      } = {
        chunk_size: [5, 10, 5],
        wav_name: audioCaptureMode.value === 'browser' ? 'h5' : 'server',
        is_speaking: true,
        chunk_interval: 10,
        mode: asrMode.value,
        language: language.value,
        audio_capture_mode: audioCaptureMode.value
      }
      
      // 如果是服务器采集模式，添加服务器音频设备ID
      if (audioCaptureMode.value === 'server') {
        config.server_audio_device = audioSource.value
      }
      
      // 添加说话人识别配置
      const enableSpeakerDiarization = isSpeakerDiarizationEnabled()
      config.enable_speaker_diarization = enableSpeakerDiarization
      console.log(`[${new Date().toLocaleTimeString()}] 说话人识别设置: ${enableSpeakerDiarization ? '启用' : '禁用'}`)

      // 添加翻译功能配置
      config.enable_translation = enableTranslation.value
      console.log(`[${new Date().toLocaleTimeString()}] 翻译功能设置: ${enableTranslation.value ? '启用' : '禁用'}`)
      const hotWordsStr = getHotWords()
      if (hotWordsStr) {
        config['hotwords'] = hotWordsStr
        console.log(`[${new Date().toLocaleTimeString()}] 已配置热词优化:`, hotWordsStr)
      } else {
        console.log(`[${new Date().toLocaleTimeString()}] 未配置热词优化`)
      }
      console.log(`[${new Date().toLocaleTimeString()}] 当前ASR模式: ${asrMode.value}`)
      console.log(`[${new Date().toLocaleTimeString()}] 发送WebSocket初始化配置:`, config);

      // 发送配置信息
      wsConnection.value!.send(JSON.stringify(config))

      if (audioCaptureMode.value === 'browser') {
        // 浏览器采集模式：初始化录音器并开始录音
        // 每次开始录音时重新初始化录音器，以使用最新选择的设备
        initRecorder()
        
        rec.value.open((error?: Error) => {
          if (error) {
            console.error(`[${new Date().toLocaleTimeString()}] 录音初始化失败:`, error)
            wsConnection.value?.close()
            wsConnection.value = null
            isRecording.value = false
            return
          }
          
          // 验证实际使用的音频设备
          const stream = rec.value.stream
          if (stream && stream.getAudioTracks) {
            const audioTracks = stream.getAudioTracks()
            if (audioTracks.length > 0) {
              const track = audioTracks[0]
              const settings = track.getSettings()
              console.log(`[${new Date().toLocaleTimeString()}] ✅ 录音器已打开，实际使用设备:`, {
                label: track.label,
                deviceId: settings.deviceId,
                sampleRate: settings.sampleRate,
                channelCount: settings.channelCount
              })
            }
          }
          
          rec.value.start()
          isRecording.value = true
          console.log(`[${new Date().toLocaleTimeString()}] 浏览器录音已开始，采样率: 16000Hz, 位深: 16bit`);
        })
      } else {
        // 服务器采集模式：直接标记为录音中，服务器会自己采集音频
        isRecording.value = true
        console.log(`[${new Date().toLocaleTimeString()}] 已通知服务器开始音频采集，设备: ${audioSource.value}`);
      }
    }

    let rec_text = ''
    wsConnection.value.onmessage = (event) => {
      try {
        // 检查接收到的数据类型
        if (typeof event.data !== 'string') {
          console.warn(`[${new Date().toLocaleTimeString()}] 收到非字符串类型的WebSocket消息:`, typeof event.data)
          return
        }
        
        // 打印原始数据用于调试（截断长度以避免日志过长）
        const rawData = event.data.length > 200 ? event.data.substring(0, 200) + '...' : event.data
        console.log(`[${new Date().toLocaleTimeString()}] 收到原始WebSocket数据:`, rawData)
        
        const response = JSON.parse(event.data)
        console.log(`[${new Date().toLocaleTimeString()}] 收到WebSocket消息:`, response)

        if (response.text) {
          const rectxt = response.text
          const asrmodel = response.mode
          // const _is_final = response.is_final // 暂时注释未使用的变量

          // 优先使用 asr_timestamp（数组格式），否则使用 timestamp（可能是数组或数字）
          const timestamp = response.asr_timestamp || response.timestamp
          const speaker = response.speaker_name || response.speaker || response.spk || ''
          const startTime = response.start_time  // 后端返回的格式化开始时间
          const endTime = response.end_time      // 后端返回的格式化结束时间
          const translation = enableTranslation.value ? (response.translation || '') : ''  // 翻译结果
          console.log('🌐 提取translation:', translation, 'response.translation:', response.translation)

          // 处理说话人信息
          handleSpeakerInfo(speaker, rectxt, asrmodel, timestamp, startTime, endTime, translation)

          if (asrmodel === '2pass-offline') {
            // 处理离线模式的结果，默认启用时间戳
            const timestampedText = handleTimestampResult(rectxt, timestamp)
            offlineTranscript.value += timestampedText
            rec_text = offlineTranscript.value
          } else {
            // 处理在线模式的结果
            rec_text += rectxt
          }
          transcript.value = rec_text
        }
      } catch (error) {
        console.error(`[${new Date().toLocaleTimeString()}] 解析WebSocket消息失败:`, error)
        console.error(`[${new Date().toLocaleTimeString()}] 原始消息数据:`, event.data)
        console.error(`[${new Date().toLocaleTimeString()}] 消息数据类型:`, typeof event.data)
        console.error(`[${new Date().toLocaleTimeString()}] 消息数据长度:`, event.data?.length)
      }
    }

    wsConnection.value.onerror = (error) => {
      clearTimeout(wsConnectTimeout)
      console.error('WebSocket错误:', error)
      wsConnection.value!.isConnected = false
      isRecording.value = false
      throw new Error('WebSocket连接失败')
    }
  }

  // 处理说话人信息
  function handleSpeakerInfo(speaker: string, text: string, mode: string, timestamp?: any, startTime?: string, endTime?: string, translation?: string) {
    console.log('处理说话人信息:', { speaker, text, mode, timestamp, startTime, endTime, translation })
    
    // 如果是2pass-online模式且没有说话人信息，使用最近的说话人
    if (mode === '2pass-online' && !speaker && lastSpeaker.value) {
      speaker = lastSpeaker.value
      
      //console.log('onlineText:', onlineText.value)
    }
    if(mode === '2pass-online'){
      onlineText.value += text
      if (translation) {
        onlineTranslation.value += (onlineTranslation.value ? ' ' : '') + translation
      }
    }

    // 提取时间戳的开始和结束时间（毫秒）
    let startMs: number | undefined
    let endMs: number | undefined
    if (timestamp && Array.isArray(timestamp) && timestamp.length > 0) {
      startMs = timestamp[0][0]  // 第一个片段的开始时间
      endMs = timestamp[timestamp.length - 1][1]  // 最后一个片段的结束时间
    }

    // 如果有说话人信息
    if (speaker) {
      //console.log('说话人信息:'+speaker + onlineText.value)
      currentSpeaker.value = speaker
      
      // 如果说话人与最近的不一致，或者是第一个2pass-offline输出
      if (speaker !== lastSpeaker.value || (mode === '2pass-offline' && !lastSpeaker.value)) {
        // 处理标点符号：如果新说话人的文本以标点符号开头，将标点符号移到上一个说话人末尾
        let processedText = text
        
        // 定义标点符号集合
        const punctuationChars = ['，', '。', '！', '？', '；', '：', '、', ',', '.', '!', '?', ';', ':']
        const firstChar = text.charAt(0)
        
        if (text.length > 0 && punctuationChars.includes(firstChar) && speakerSegments.value.length > 0) {
          const previousSegment = speakerSegments.value[speakerSegments.value.length - 1]
          if (previousSegment) {
            // 将开头的标点符号添加到上一个说话人的文本末尾
            previousSegment.text += firstChar
            // 从当前文本中移除开头的标点符号
            processedText = text.substring(1).trim()
            console.log(`移动标点符号 "${firstChar}" 到上一个说话人`)
          }
        }
        
        // 创建新的说话人段落
        const segment: SpeakerSegment = {
          speaker: speaker,
          text: processedText,
          mode: mode,
          timestamp: timestamp,
          startTime: startTime,
          endTime: endTime,
          startMs: startMs,
          endMs: endMs,
          translation: translation
        }
        console.log('✅ 创建新segment，translation:', translation)
        
        // 删除上一个说话人段落中的onlineText内容（仅在2pass-offline时）
        if (mode === '2pass-offline' && speakerSegments.value.length > 0 && onlineText.value) {
          const previousSegment = speakerSegments.value[speakerSegments.value.length - 1]
          if (previousSegment) {
            console.log('🔍 上一个说话人段落:', previousSegment.text)
            console.log('🔍 需要移除的在线文本:', onlineText.value)
            
            // 直接从末尾移除在线文本（按字符数）
            const lines = previousSegment.text.split('\n')
            let charsToRemove = onlineText.value.length
            let newLines = []
            
            console.log('📊 需要移除的字符数:', charsToRemove)
            
            // 从后往前处理每一行
            for (let i = lines.length - 1; i >= 0 && charsToRemove > 0; i--) {
              const line = lines[i]
              const lineText = line.replace(/\d{2}:\d{2}:\d{2}\s*/, '')
              
              console.log(`  处理第${i}行: "${line}" -> 纯文本: "${lineText}" (长度=${lineText.length})`)
              
              if (charsToRemove >= lineText.length) {
                // 整行都要移除
                console.log(`    移除整行 (${lineText.length}字符)`)
                charsToRemove -= lineText.length
              } else {
                // 只移除部分内容
                const keepText = lineText.slice(0, lineText.length - charsToRemove)
                const timestamp = line.match(/\d{2}:\d{2}:\d{2}/)
                console.log(`    部分移除: 保留 "${keepText}" (移除${charsToRemove}字符)`)
                if (timestamp && keepText) {
                  newLines.unshift(`${timestamp[0]} ${keepText}`)
                } else if (keepText) {
                  newLines.unshift(keepText)
                }
                charsToRemove = 0
              }
              
              if (charsToRemove === 0) {
                // 保留剩余的行
                newLines = lines.slice(0, i).concat(newLines)
                break
              }
            }
            
            previousSegment.text = newLines.join('\n')
            console.log('✂️ 新说话人：从末尾移除在线文本:', onlineText.value)
            console.log('📄 移除后的段落文本:', previousSegment.text)

            // 同时移除online临时翻译
            console.log('🔍 [DEBUG-新说话人] 准备移除online翻译')
            console.log('🔍 [DEBUG-新说话人] onlineTranslation.value:', onlineTranslation.value)
            console.log('🔍 [DEBUG-新说话人] previousSegment.translation:', previousSegment.translation)
            if (onlineTranslation.value && previousSegment.translation) {
              console.log('🔍 [DEBUG-新说话人] endsWith检查:', previousSegment.translation.endsWith(onlineTranslation.value))
              if (previousSegment.translation.endsWith(onlineTranslation.value)) {
                const oldTranslation = previousSegment.translation
                previousSegment.translation = previousSegment.translation.slice(0, -onlineTranslation.value.length).trim()
                console.log('✂️ 新说话人：移除在线临时翻译:', onlineTranslation.value)
                console.log('✂️ 移除前:', oldTranslation)
                console.log('✂️ 移除后:', previousSegment.translation)
              } else {
                console.log('⚠️ [DEBUG-新说话人] translation不以onlineTranslation结尾，无法移除')
              }
            }
          }
        }
        
        speakerSegments.value.push(segment)
        lastSpeaker.value = speaker
        onlineText.value = '' // 只在创建新说话人段落时清空
        onlineTranslation.value = ''
      } else {
        console.log('说话人一致，追加文本并更新结束时间')
        const lastSegment = speakerSegments.value[speakerSegments.value.length - 1]
        console.log('lastSegment:', lastSegment)
        if (lastSegment) {
          // 如果是离线模式且有onlineText内容，需要移除在线文本
          console.log('mode:', mode)
          console.log('onlineText:', onlineText.value)
          if (mode === '2pass-offline' && onlineText.value) {
            console.log('🔍 同一说话人-离线模式，当前段落文本:', lastSegment.text)
            console.log('🔍 同一说话人-需要移除的在线文本:', onlineText.value)

            // 直接从末尾移除在线文本（按字符数）
            const lines = lastSegment.text.split('\n')
            let charsToRemove = onlineText.value.length
            let newLines = []

            console.log('📊 需要移除的字符数:', charsToRemove)

            // 从后往前处理每一行
            for (let i = lines.length - 1; i >= 0 && charsToRemove > 0; i--) {
              const line = lines[i]
              const lineText = line.replace(/\d{2}:\d{2}:\d{2}\s*/, '')

              console.log(`  处理第${i}行: "${line}" -> 纯文本: "${lineText}" (长度=${lineText.length})`)

              if (charsToRemove >= lineText.length) {
                // 整行都要移除
                console.log(`    移除整行 (${lineText.length}字符)`)
                charsToRemove -= lineText.length
              } else {
                // 只移除部分内容
                const keepText = lineText.slice(0, lineText.length - charsToRemove)
                const timestamp = line.match(/\d{2}:\d{2}:\d{2}/)
                console.log(`    部分移除: 保留 "${keepText}" (移除${charsToRemove}字符)`)
                if (timestamp && keepText) {
                  newLines.unshift(`${timestamp[0]} ${keepText}`)
                } else if (keepText) {
                  newLines.unshift(keepText)
                }
                charsToRemove = 0
              }

              if (charsToRemove === 0) {
                // 保留剩余的行
                newLines = lines.slice(0, i).concat(newLines)
                break
              }
            }

            lastSegment.text = newLines.join('\n')
            console.log('✂️ 同一说话人：从末尾移除在线文本:', onlineText.value)
            console.log('📄 移除后的段落文本:', lastSegment.text)

            // 移除online临时翻译（在清空之前）
            console.log('🔍 [DEBUG] 准备移除online翻译')
            console.log('🔍 [DEBUG] onlineTranslation.value:', onlineTranslation.value)
            console.log('🔍 [DEBUG] lastSegment.translation:', lastSegment.translation)
            if (onlineTranslation.value && lastSegment.translation) {
              console.log('🔍 [DEBUG] endsWith检查:', lastSegment.translation.endsWith(onlineTranslation.value))
              if (lastSegment.translation.endsWith(onlineTranslation.value)) {
                const oldTranslation = lastSegment.translation
                lastSegment.translation = lastSegment.translation.slice(0, -onlineTranslation.value.length).trim()
                console.log('✂️ 移除在线临时翻译:', onlineTranslation.value)
                console.log('✂️ 移除前:', oldTranslation)
                console.log('✂️ 移除后:', lastSegment.translation)
              } else {
                console.log('⚠️ [DEBUG] translation不以onlineTranslation结尾，无法移除')
              }
            }

            onlineText.value = ''
            onlineTranslation.value = ''
          }
          // 追加新的文本
          lastSegment.text += text

          // 追加翻译
          if (translation) {
            lastSegment.translation = (lastSegment.translation || '') + (lastSegment.translation ? ' ' : '') + translation
            console.log('✅ 更新translation:', lastSegment.translation, 'mode:', mode)
          }

          // 更新结束时间（保持开始时间不变，只更新结束时间）
          if (endTime) {
            lastSegment.endTime = endTime
          }
          if (endMs !== undefined) {
            lastSegment.endMs = endMs
          }
          
          console.log(`📝 同一说话人，更新时间范围: ${lastSegment.startTime} - ${lastSegment.endTime}`)
        }       
      }
    } else if (mode === '2pass-offline' && !lastSpeaker.value) {
      // 第一个2pass-offline输出且没有说话人信息，创建空说话人段落
      const segment: SpeakerSegment = {
        speaker: '',
        text: text,
        mode: mode,
        timestamp: timestamp,
        startTime: startTime,
        endTime: endTime,
        startMs: startMs,
        endMs: endMs,
        translation: translation
      }
      speakerSegments.value.push(segment)
      onlineText.value = '' // 创建新段落时清空
      onlineTranslation.value = ''
    } else if (!speaker && speakerSegments.value.length > 0) {
      // 没有说话人信息，但有已存在的段落，追加到最后一个段落
      const lastSegment = speakerSegments.value[speakerSegments.value.length - 1]
      if (lastSegment) {
        lastSegment.text += text
        if (translation) {
          lastSegment.translation = (lastSegment.translation || '') + (lastSegment.translation ? ' ' : '') + translation
          console.log('✅ 无speaker更新translation:', lastSegment.translation, 'mode:', mode)
        }
      }
    }
  }

  // 将毫秒转换为时分秒格式 (00:00:00)
  function formatTimestamp(milliseconds: number): string {
    const totalSeconds = Math.floor(milliseconds / 1000)
    const hours = Math.floor(totalSeconds / 3600)
    const minutes = Math.floor((totalSeconds % 3600) / 60)
    const seconds = totalSeconds % 60
    
    return `${hours.toString().padStart(2, '0')}:${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}`
  }

  function handleTimestampResult(text: string, timestamp: any): string {
    console.log('处理文本:', text)
    console.log('处理时间戳:', timestamp)
    
    if (!timestamp || timestamp === 'undefined' || text.length <= 0) {
      return text
    }
    
    // 处理标点符号，统一替换为逗号
    text = text.replace(/。|？|，|、|\?|\.| \s/g, ',') 
    
    // 分割文本
    const words = text.split(',') 
    
    // 解析时间戳 - 如果timestamp已经是对象，则直接使用；如果是字符串，则解析
    let jsontime: any
    if (typeof timestamp === 'string') {
      try {
        jsontime = JSON.parse(timestamp)
      } catch (error) {
        console.error('时间戳解析失败:', error, '原始数据:', timestamp)
        return text
      }
    } else if (Array.isArray(timestamp)) {
      jsontime = timestamp
    } else {
      console.warn('无效的时间戳格式:', timestamp)
      return text
    } 
    let char_index = 0
    let text_withtime = ''
    
    for (let i = 0; i < words.length; i++) {
      if (words[i] === 'undefined' || words[i].length <= 0) {
        continue
      }
      
      console.log('处理词语:', words[i])
      console.log('时间戳索引:', char_index)
      
      if (/^[a-zA-Z]+$/.test(words[i])) {
        // 英文单词，时间戳单位是词
        const timeStr = formatTimestamp(jsontime[char_index][0])
        text_withtime += `${timeStr} ${words[i]}\n`
        char_index += 1
      } else {
        // 中文句子，时间戳单位是字
        const timeStr = formatTimestamp(jsontime[char_index][0])
        text_withtime += `${timeStr} ${words[i]}\n`
        char_index += words[i].length
      }
    }
    
    return text_withtime
  }

  function initRecorder() {
    const deviceId = audioSource.value || undefined
    const deviceName = audioDevices.value.find(d => d.deviceId === audioSource.value)?.label || '默认设备'
    console.log(`[${new Date().toLocaleTimeString()}] 初始化录音器，使用设备: ${deviceName} (ID: ${deviceId})`)
    
    // 重置音频缓冲区，防止残留数据污染新录音
    sampleBuf = new Int16Array()
    
    rec.value = new window.Recorder({
      type: "pcm",
      bitRate: 16,
      sampleRate: 16000,
      audioTrackSet: {
        deviceId: deviceId,
        echoCancellation: true,
        noiseSuppression: true,
        autoGainControl: true
      },
      onProcess: (buffer: any[], _powerLevel: number, _bufferDuration: number, bufferSampleRate: number) => {
        if (isRecording.value && wsConnection.value?.isConnected) {
          const data_48k = buffer[buffer.length-1];
          const data_16k = window.Recorder.SampleData([data_48k], bufferSampleRate, 16000).data;
          
          // 对齐为960字节的数据包以避免后端分片问题
          const newBuf = new Int16Array(sampleBuf.length + data_16k.length);
          newBuf.set(sampleBuf, 0);
          newBuf.set(data_16k, sampleBuf.length);
          sampleBuf = newBuf;
          
          const chunk_size = 960;
          while(sampleBuf.length >= chunk_size) {
            const sendBuf = sampleBuf.slice(0, chunk_size);
            sampleBuf = sampleBuf.slice(chunk_size, sampleBuf.length);
            wsConnection.value.send(sendBuf.buffer);
          }
        }
      }
    })
  }

  function stopRecording() {
    try {
      if (audioCaptureMode.value === 'browser') {
        // 浏览器采集模式：停止录音器
        if (!rec.value || !wsConnection.value) return

        // 发送剩余的音频缓冲区数据
        if (sampleBuf.length > 0 && wsConnection.value?.isConnected) {
          console.log(`[${new Date().toLocaleTimeString()}] 发送剩余音频数据: ${sampleBuf.length} 样本`)
          wsConnection.value.send(sampleBuf.buffer)
          sampleBuf = new Int16Array() // 清空缓冲区
        }
        
        // 先停止录音
        rec.value.stop((blob: Blob) => {
          console.log(`[${new Date().toLocaleTimeString()}] 录音已停止:`, blob)
          isRecording.value = false
          
          // 创建音频URL并更新播放器
          if (window.Recorder && window.Recorder.pcm2wav) {
            window.Recorder.pcm2wav({sampleRate:16000, bitRate:16, blob:blob},
              (wavBlob: Blob) => {
                console.log('WAV转换完成:', wavBlob)
                audioUrl.value = (window.URL||webkitURL).createObjectURL(wavBlob)
              },
              (error: any) => {
                console.error('WAV转换失败:', error)
                // 如果转换失败，直接使用原始blob创建URL
                audioUrl.value = (window.URL||webkitURL).createObjectURL(blob)
              }
            )
          } else {
            console.error('Recorder.pcm2wav不可用，直接使用原始音频')
            // 直接使用原始blob创建URL
            audioUrl.value = (window.URL||webkitURL).createObjectURL(blob)
          }
          // 添加类型声明以支持可选的loadAudioBlob方法
          (window as any).loadAudioBlob?.(blob)

          // 发送停止识别的请求
          const request = {
            chunk_size: [5, 10, 5],
            wav_name: 'h5',
            is_speaking: false,
            chunk_interval: 10,
            mode: asrMode.value,
            audio_capture_mode: audioCaptureMode.value
          }
          wsConnection.value?.send(JSON.stringify(request))

          // 等待3秒后关闭连接，确保接收到最后的识别结果
          const currentWs = wsConnection.value;
          setTimeout(() => {
            if (currentWs) {
              currentWs.close()
            }
            if (wsConnection.value === currentWs) {
              wsConnection.value = null
            }
            // 重新初始化录音设备
            initRecorder()
          }, 3000)
        }, (error: any) => {
          console.error(`[${new Date().toLocaleTimeString()}] 录音错误:`, error)
          isRecording.value = false
          if (wsConnection.value) {
            wsConnection.value.close()
            wsConnection.value = null
          }
          // 重新初始化录音设备
          initRecorder()
        })
      } else {
        // 服务器采集模式：只发送停止信号
        if (!wsConnection.value) return
        
        console.log(`[${new Date().toLocaleTimeString()}] 通知服务器停止音频采集`)
        isRecording.value = false
        
        // 发送停止识别的请求
        const request = {
          chunk_size: [5, 10, 5],
          wav_name: 'server',
          is_speaking: false,
          chunk_interval: 10,
          mode: asrMode.value,
          audio_capture_mode: audioCaptureMode.value,
          server_audio_device: audioSource.value
        }
        wsConnection.value.send(JSON.stringify(request))

        // 等待3秒后关闭连接，确保接收到最后的识别结果
        const currentWs = wsConnection.value;
        setTimeout(() => {
          if (currentWs) {
            currentWs.close()
          }
          if (wsConnection.value === currentWs) {
            wsConnection.value = null
          }
        }, 3000)
      }
    } catch (error) {
      console.error(`[${new Date().toLocaleTimeString()}] 停止录音失败:`, error)
      isRecording.value = false
      if (wsConnection.value) {
        wsConnection.value.close()
        wsConnection.value = null
      }
      if (audioCaptureMode.value === 'browser') {
        initRecorder()
      }
    }
  }

  function clearTranscript() {
    transcript.value = ''
    offlineTranscript.value = ''
    meetingSummary.value = ''
    speakerSegments.value = []
    currentSpeaker.value = ''
    lastSpeaker.value = ''
    onlineText.value = ''
    onlineTranslation.value = ''
    uploadedMediaTaskId.value = ''
    uploadedMediaFileName.value = ''
  }

  function setUploadedMediaContext(taskId: string, fileName: string = '') {
    uploadedMediaTaskId.value = taskId
    uploadedMediaFileName.value = fileName
  }

  return {
    transcript,
    isRecording,
    audioDevices,
    audioSource,
    language,
    hotWords,
    asrMode,
    useITN,
    audioUrl,
    uploadedMediaTaskId,
    uploadedMediaFileName,
    meetingSummary,
    speakerSegments,
    currentSpeaker,
    lastSpeaker,
    wsConnection,
    audioCaptureMode,
    enableTranslation,
    getAudioDevices,
    startRecording,
    stopRecording,
    clearTranscript,
    setUploadedMediaContext
  }
})
