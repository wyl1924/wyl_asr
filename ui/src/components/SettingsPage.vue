<template>
  <div class="settings-page">
    <div class="settings-header">
      <div class="header-controls">
        <el-button 
          type="info" 
          @click="goBack"
          class="back-button"
        >
          <el-icon><ArrowLeft /></el-icon>
          返回
        </el-button>
        <div class="server-status">
          <el-tag 
            :type="serverStatusType" 
            :loading="isCheckingStatus"
            @click="checkServerStatus"
            class="status-tag"
          >
            <el-icon><Connection /></el-icon>
            {{ serverStatusText }}
          </el-tag>
          <el-button 
            size="small" 
            @click="checkServerStatus"
            :loading="isCheckingStatus"
          >
            <el-icon><Refresh /></el-icon>
            刷新状态
          </el-button>
        </div>
      </div>
      <h1>🔧 后端服务配置</h1>
      <p>配置并启动实时语音识别服务器</p>
    </div>

    <el-card class="settings-card">
      <template #header>
        <div class="card-header">
          <span>服务器配置</span>
          <el-tag type="info">
            🔧 配置完成后生成启动命令
          </el-tag>
        </div>
      </template>
      
      <div class="server-controls">
        <el-button 
          type="primary" 
          :loading="isStarting"
          @click="startServer"
        >
          <el-icon><VideoPlay /></el-icon>
          直接启动服务
        </el-button>
        
        <el-button 
          type="success" 
          @click="saveAndStart"
        >
          <el-icon><VideoPlay /></el-icon>
          保存并启动
        </el-button>
      </div>
    </el-card>

    <el-form 
      ref="settingsForm" 
      :model="settings" 
      :rules="rules" 
      label-width="180px"
      class="settings-form"
    >
      <!-- 网络配置 -->
      <el-card class="config-section">
        <template #header>
          <h3>🌐 网络配置</h3>
        </template>
        
        <el-form-item label="服务器IP地址" prop="host">
          <el-input v-model="settings.host" :placeholder="SERVER_CONFIG.DEFAULT_HOST" />
        <div class="form-tip">监听所有接口请使用 {{ SERVER_CONFIG.DEFAULT_HOST }}，仅本地访问使用 {{ SERVER_CONFIG.LOCALHOST }}</div>
        </el-form-item>
        
        <el-form-item label="WebSocket端口" prop="port">
          <el-input-number v-model="settings.port" :min="1" :max="65535" />
        </el-form-item>
        
        <el-form-item label="API端口" prop="apiPort">
          <el-input-number v-model="settings.apiPort" :min="1" :max="65535" />
        </el-form-item>
        
        <el-form-item label="SSL证书文件">
          <el-input v-model="settings.certfile" placeholder="ssl/server.crt" />
        </el-form-item>
        
        <el-form-item label="SSL私钥文件">
          <el-input v-model="settings.keyfile" placeholder="ssl/server.key" />
        </el-form-item>
      </el-card>

      <!-- 模型配置 -->
      <el-card class="config-section">
        <template #header>
          <h3>🤖 模型配置</h3>
        </template>
        
        <el-form-item label="ASR模型类型" prop="modelType">
          <el-select v-model="settings.modelType" @change="onModelTypeChange">
            <el-option label="SenseVoice (多模态)" value="sensevoice" />
            <el-option label="Paraformer (传统)" value="paraformer" />
          </el-select>
          <div class="form-tip">
            SenseVoice: 支持多语言、情感检测、事件检测<br>
            Paraformer: 传统高精度识别模型
          </div>
        </el-form-item>
        
        <el-form-item label="离线ASR模型">
          <el-input v-model="settings.asrModel" />
        </el-form-item>
        
        <el-form-item label="在线ASR模型">
          <el-input v-model="settings.asrModelOnline" />
        </el-form-item>
        
        <el-form-item label="VAD模型">
          <el-input v-model="settings.vadModel" />
        </el-form-item>
        
        <el-form-item label="标点恢复模型">
          <el-input v-model="settings.puncModel" />
        </el-form-item>
        
        <el-form-item label="模型量化">
          <el-switch 
            v-model="settings.quantize" 
            active-text="启用" 
            inactive-text="禁用"
          />
          <div class="form-tip">启用量化可减少内存占用，提高推理速度</div>
        </el-form-item>
      </el-card>

      <!-- 2Pass模式配置 -->
      <el-card class="config-section">
        <template #header>
          <h3>🔄 2Pass模式配置</h3>
        </template>
        
        <el-form-item label="启用2Pass模式">
          <el-switch 
            v-model="settings.enable2pass" 
            active-text="启用" 
            inactive-text="禁用"
          />
          <div class="form-tip">2Pass模式结合在线和离线识别，提供实时反馈和高精度结果</div>
        </el-form-item>
        

      </el-card>

      <!-- 硬件配置 -->
      <el-card class="config-section">
        <template #header>
          <h3>⚡ 硬件配置</h3>
        </template>
        
        <el-form-item label="计算设备" prop="device">
          <el-select v-model="settings.device">
            <el-option label="CPU" value="cpu" />
            <el-option label="CUDA (NVIDIA GPU)" value="cuda" />
            <el-option label="MPS (Apple Silicon)" value="mps" />
          </el-select>
        </el-form-item>
        
        <el-form-item label="GPU数量" v-if="settings.device === 'cuda'">
          <el-input-number v-model="settings.ngpu" :min="0" :max="8" />
        </el-form-item>
        
        <el-form-item label="CPU核心数">
          <el-input-number v-model="settings.ncpu" :min="1" :max="32" />
        </el-form-item>
        
        <el-form-item label="批处理大小">
          <el-input-number v-model="settings.batchSize" :min="1" :max="16" />
        </el-form-item>
      </el-card>

      <!-- 说话人识别配置 -->
      <el-card class="config-section">
        <template #header>
          <h3>🆔 说话人识别配置</h3>
        </template>
        
        <el-form-item label="启用说话人验证">
          <el-switch 
            v-model="settings.enableSpeakerVerification" 
            active-text="启用" 
            inactive-text="禁用"
          />
        </el-form-item>
        
        <el-form-item label="启用说话人分离">
          <el-switch 
            v-model="settings.enableSpeakerDiarization" 
            active-text="启用" 
            inactive-text="禁用"
          />
        </el-form-item>
        
        <el-form-item label="验证阈值" v-if="settings.enableSpeakerVerification">
          <el-slider 
            v-model="settings.speakerThreshold" 
            :min="0" 
            :max="1" 
            :step="0.1" 
            show-input
          />
          <div class="form-tip">阈值越高，验证越严格</div>
        </el-form-item>
      </el-card>

      <!-- 翻译配置 -->
      <el-card class="config-section">
        <template #header>
          <h3>🌐 翻译配置</h3>
        </template>
        
        <el-form-item label="启用翻译功能">
          <el-switch 
            v-model="settings.enableTranslation" 
            active-text="启用" 
            inactive-text="禁用"
          />
        </el-form-item>
        
        <el-form-item label="翻译模型" v-if="settings.enableTranslation">
          <el-input v-model="settings.translationModel" />
        </el-form-item>
      </el-card>

      <!-- 线程配置 -->
      <el-card class="config-section">
        <template #header>
          <h3>🧵 线程配置</h3>
        </template>
        
        <el-form-item label="IO线程数">
          <el-input-number v-model="settings.ioThreadNum" :min="1" :max="16" />
        </el-form-item>
        
        <el-form-item label="解码器线程数">
          <el-input-number v-model="settings.decoderThreadNum" :min="1" :max="32" />
        </el-form-item>
        
        <el-form-item label="模型线程数">
          <el-input-number v-model="settings.modelThreadNum" :min="1" :max="8" />
        </el-form-item>
      </el-card>

      <!-- 操作按钮 -->
      <div class="form-actions">
        <el-button type="primary" @click="saveSettings">
          <el-icon><Document /></el-icon>
          保存配置
        </el-button>
        
        <el-button @click="loadSettings">
          <el-icon><Folder /></el-icon>
          加载配置
        </el-button>
        
        <el-button @click="resetSettings">
          <el-icon><RefreshLeft /></el-icon>
          重置默认
        </el-button>
        
        <el-button type="success" @click="saveAndStart">
          <el-icon><VideoPlay /></el-icon>
          保存并启动
        </el-button>
      </div>
    </el-form>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted, computed } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { 
  VideoPlay, 
  Document, 
  Folder, 
  RefreshLeft,
  ArrowLeft,
  Connection,
  Refresh
} from '@element-plus/icons-vue'
import { serverStatusApi } from '../api/server-status'
import { SERVER_CONFIG } from '../config/api'

// 路由实例
const router = useRouter()

// 操作状态
const isStarting = ref(false)
const isCheckingStatus = ref(false)

// 服务器状态
const serverStatus = ref<'running' | 'stopped' | 'error'>('stopped')
const serverError = ref<string>('')

// 设置表单引用
const settingsForm = ref()

// 配置数据
const settings = reactive({
  // 网络配置
  host: SERVER_CONFIG.DEFAULT_HOST,
  port: 10095,
  apiPort: 8080,
  certfile: '',
  keyfile: '',
  
  // 模型配置
  modelType: 'sensevoice',
  asrModel: 'iic/SenseVoiceSmall',
  asrModelOnline: 'iic/speech_paraformer-large_asr_nat-zh-cn-16k-common-vocab8404-online',
  vadModel: 'iic/speech_fsmn_vad_zh-cn-16k-common-pytorch',
  puncModel: 'iic/punc_ct-transformer_zh-cn-common-vad_realtime-vocab272727',
  quantize: true,
  
  // 2Pass模式
  enable2pass: true,
  
  // 硬件配置
  device: 'cpu',
  ngpu: 0,
  ncpu: 4,
  batchSize: 4,
  
  // 说话人识别
  enableSpeakerVerification: false,
  enableSpeakerDiarization: false,
  speakerThreshold: 0.5,
  
  // 翻译配置
  enableTranslation: false,
  translationModel: 'iic/nlp_csanmt_translation_zh2en',
  
  // 线程配置
  ioThreadNum: 2,
  decoderThreadNum: 8,
  modelThreadNum: 1
})

// 表单验证规则
const rules = {
  host: [
    { required: true, message: '请输入服务器IP地址', trigger: 'blur' }
  ],
  port: [
    { required: true, message: '请输入端口号', trigger: 'blur' },
    { type: 'number', min: 1, max: 65535, message: '端口号必须在1-65535之间', trigger: 'blur' }
  ],
  apiPort: [
    { required: true, message: '请输入API端口号', trigger: 'blur' },
    { type: 'number', min: 1, max: 65535, message: '端口号必须在1-65535之间', trigger: 'blur' }
  ],
  modelType: [
    { required: true, message: '请选择模型类型', trigger: 'change' }
  ],
  device: [
    { required: true, message: '请选择计算设备', trigger: 'change' }
  ]
}

// 服务器状态计算属性
const serverStatusText = computed(() => {
  switch (serverStatus.value) {
    case 'running':
      return '服务运行中'
    case 'stopped':
      return '服务已停止'
    case 'error':
      return '服务异常'
    default:
      return '状态未知'
  }
})

const serverStatusType = computed(() => {
  switch (serverStatus.value) {
    case 'running':
      return 'success'
    case 'stopped':
      return 'info'
    case 'error':
      return 'danger'
    default:
      return 'warning'
  }
})

// 返回上一页
const goBack = () => {
  router.back()
}

// 检查服务器状态
const checkServerStatus = async () => {
  isCheckingStatus.value = true
  try {
    const response = await serverStatusApi.checkStatus()
    if (response.success) {
      serverStatus.value = response.data.status
      serverError.value = ''
    } else {
      serverStatus.value = 'error'
      serverError.value = response.error || '状态检查失败'
    }
  } catch (error) {
    serverStatus.value = 'error'
    serverError.value = error instanceof Error ? error.message : '网络连接失败'
  } finally {
    isCheckingStatus.value = false
  }
}

// 模型类型变更处理
const onModelTypeChange = (value: string) => {
  if (value === 'sensevoice') {
    settings.asrModel = 'iic/SenseVoiceSmall'
  } else if (value === 'paraformer') {
    settings.asrModel = 'iic/speech_paraformer-large_asr_nat-zh-cn-16k-common-vocab8404-pytorch'
  }
}

// 直接启动服务器
const startServer = async () => {
  try {
    isStarting.value = true
    
    // 验证表单
    await settingsForm.value.validate()
    
    // 构建启动参数
    const args = buildServerArgs()
    
    // 直接执行Python命令
    const response = await fetch('/api/execute-python', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({ args })
    })
    
    if (response.ok) {
      const result = await response.json()
      if (result.success) {
        ElMessage.success('服务器启动成功！')
        // 显示启动信息
        ElMessageBox.alert(
          `服务器已启动！\n\n进程ID: ${result.pid}\n启动时间: ${new Date().toLocaleString()}`,
          '启动成功',
          {
            type: 'success'
          }
        )
      } else {
        throw new Error(result.message || '启动失败')
      }
    } else {
      throw new Error('网络请求失败')
    }
    
  } catch (error) {
    ElMessage.error(`启动失败: ${(error as any)?.message || error}`)
    
    // 如果API调用失败，回退到显示命令的方式
    try {
      const command = buildStartCommand()
      await ElMessageBox.alert(
        `API调用失败，请手动执行以下命令：\n\n${command}`,
        '手动启动',
        {
          confirmButtonText: '复制命令',
          type: 'warning'
        }
      )
      
      if (navigator.clipboard) {
        await navigator.clipboard.writeText(command)
        ElMessage.success('命令已复制到剪贴板')
      }
    } catch (fallbackError) {
      // 忽略回退错误
    }
  } finally {
    isStarting.value = false
  }
}



// 构建服务器启动参数数组
const buildServerArgs = () => {
  const args: string[] = []
  
  // 网络配置
  args.push('--host', settings.host)
  args.push('--port', settings.port.toString())
  args.push('--api-port', settings.apiPort.toString())
  
  if (settings.certfile) {
    args.push('--certfile', settings.certfile)
  }
  if (settings.keyfile) {
    args.push('--keyfile', settings.keyfile)
  }
  
  // 模型配置
  args.push('--model_type', settings.modelType)
  args.push('--asr_model', settings.asrModel)
  args.push('--asr_model_online', settings.asrModelOnline)
  args.push('--vad_model', settings.vadModel)
  args.push('--punc_model', settings.puncModel)
  args.push('--quantize', settings.quantize ? 'true' : 'false')
  
  // 2Pass模式
  if (settings.enable2pass) {
    args.push('--enable_2pass')
  } else {
    args.push('--disable_2pass')
  }
  
  // 硬件配置
  args.push('--device', settings.device)
  args.push('--ngpu', settings.ngpu.toString())
  args.push('--ncpu', settings.ncpu.toString())
  args.push('--batch_size', settings.batchSize.toString())
  
  // 说话人识别
  if (settings.enableSpeakerVerification) {
    args.push('--enable_speaker_verification')
    args.push('--speaker_threshold', settings.speakerThreshold.toString())
  }
  if (settings.enableSpeakerDiarization) {
    args.push('--enable_speaker_diarization')
  }
  
  // 翻译配置
  if (settings.enableTranslation) {
    args.push('--enable_translation')
    args.push('--translation_model', settings.translationModel)
  }
  
  // 线程配置
  args.push('--io_thread_num', settings.ioThreadNum.toString())
  args.push('--decoder_thread_num', settings.decoderThreadNum.toString())
  args.push('--model_thread_num', settings.modelThreadNum.toString())
  
  return args
}

// 构建完整的启动命令字符串
const buildStartCommand = () => {
  const args = buildServerArgs()
  const command = `conda activate funasr-ws && python main.py ${args.join(' ')}`
  return command
}

// 保存配置
const saveSettings = () => {
  const config = JSON.stringify(settings, null, 2)
  localStorage.setItem('asr_server_settings', config)
  ElMessage.success('配置已保存')
}

// 加载配置
const loadSettings = () => {
  const saved = localStorage.getItem('asr_server_settings')
  if (saved) {
    try {
      const config = JSON.parse(saved)
      Object.assign(settings, config)
      ElMessage.success('配置已加载')
    } catch (error) {
      ElMessage.error('配置文件格式错误')
    }
  } else {
    ElMessage.warning('未找到保存的配置')
  }
}

// 重置为默认配置
const resetSettings = async () => {
  try {
    await ElMessageBox.confirm('确定要重置为默认配置吗？', '确认重置', {
      type: 'warning'
    })
    
    // 重置为默认值
    Object.assign(settings, {
      host: SERVER_CONFIG.DEFAULT_HOST,
      port: 10095,
      apiPort: 8080,
      certfile: '',
      keyfile: '',
      modelType: 'sensevoice',
      asrModel: 'iic/SenseVoiceSmall',
      asrModelOnline: 'iic/speech_paraformer-large_asr_nat-zh-cn-16k-common-vocab8404-online',
      vadModel: 'iic/speech_fsmn_vad_zh-cn-16k-common-pytorch',
      puncModel: 'iic/punc_ct-transformer_zh-cn-common-vad_realtime-vocab272727',
      quantize: true,
      enable2pass: true,

      device: 'cpu',
      ngpu: 0,
      ncpu: 4,
      batchSize: 4,
      enableSpeakerVerification: false,
      enableSpeakerDiarization: false,
      speakerThreshold: 0.5,
      enableTranslation: false,
      translationModel: 'iic/nlp_csanmt_translation_zh2en',
      ioThreadNum: 2,
      decoderThreadNum: 8,
      modelThreadNum: 1
    })
    
    ElMessage.success('已重置为默认配置')
  } catch {
    // 用户取消
  }
}

// 保存并启动服务
const saveAndStart = async () => {
  try {
    saveSettings()
    await startServer()
  } catch (error) {
    ElMessage.error(`操作失败: ${(error as any)?.message || error}`)
  }
}

// 组件挂载时加载配置和检查服务器状态
onMounted(() => {
  loadSettings()
  checkServerStatus()
})
</script>

<style scoped lang="scss">
.settings-page {
  padding: 20px;
  max-width: 1200px;
  margin: 0 auto;
}

.settings-header {
  text-align: center;
  margin-bottom: 30px;
  
  .header-controls {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 20px;
    
    .back-button {
      min-width: 80px;
    }
    
    .server-status {
      display: flex;
      align-items: center;
      gap: 10px;
      
      .status-tag {
        cursor: pointer;
        transition: all 0.3s ease;
        
        &:hover {
          transform: scale(1.05);
        }
      }
    }
  }
  
  h1 {
    color: #409eff;
    margin-bottom: 10px;
  }
  
  p {
    color: #666;
    font-size: 16px;
  }
}

.settings-card {
  margin-bottom: 20px;
  
  .card-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
  }
}

.server-controls {
  display: flex;
  gap: 15px;
  justify-content: center;
  
  .el-button {
    min-width: 120px;
  }
}

.settings-form {
  .config-section {
    margin-bottom: 25px;
    
    h3 {
      margin: 0;
      color: #409eff;
      font-size: 18px;
    }
  }
  
  .form-tip {
    font-size: 12px;
    color: #999;
    margin-top: 5px;
    line-height: 1.4;
  }
  
  .el-form-item {
    margin-bottom: 20px;
  }
}

.form-actions {
  text-align: center;
  padding: 30px 0;
  border-top: 1px solid #eee;
  margin-top: 30px;
  
  .el-button {
    margin: 0 10px;
    min-width: 120px;
  }
}

// 响应式设计
@media (max-width: 768px) {
  .settings-page {
    padding: 10px;
  }
  
  .settings-header {
    .header-controls {
      flex-direction: column;
      gap: 15px;
      align-items: stretch;
      
      .server-status {
        justify-content: center;
        flex-wrap: wrap;
      }
    }
  }
  
  .server-controls {
    flex-direction: column;
    align-items: center;
  }
  
  .form-actions {
    .el-button {
      margin: 5px;
      width: 100%;
      max-width: 200px;
    }
  }
}
</style>