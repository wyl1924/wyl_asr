<template>
  <div class="speaker-registration">
    <header class="registration-header">
      <div class="header-main">
        <button type="button" class="back-btn" @click="goBack">
          <el-icon><ArrowLeft /></el-icon>
          返回
        </button>

        <div class="title-block">
          <span class="eyebrow">声纹库管理</span>
          <h1>说话人声纹注册</h1>
          <p>建立稳定的说话人身份，用于会议转写中的自动标注与区分。</p>
        </div>
      </div>

      <div class="header-actions">
        <button type="button" class="tool-btn" @click="goToSerialBinding">
          <el-icon><Connection /></el-icon>
          串口绑定
        </button>
        <button type="button" class="tool-btn" @click="loadSpeakersList">
          <el-icon><Refresh /></el-icon>
          刷新
        </button>
      </div>
    </header>

    <section class="overview-strip" aria-label="声纹注册概览">
      <div class="overview-item">
        <el-icon><User /></el-icon>
        <div>
          <strong>{{ speakersList.length }}</strong>
          <span>已注册</span>
        </div>
      </div>
      <div class="overview-item">
        <el-icon><Microphone /></el-icon>
        <div>
          <strong>{{ formData.inputMethod === 'record' ? '录音' : '文件' }}</strong>
          <span>当前方式</span>
        </div>
      </div>
      <div class="overview-item">
        <el-icon><UploadFilled /></el-icon>
        <div>
          <strong>{{ isRecording ? '录制中' : (recordedAudio || formData.audioFile ? '已准备' : '待采集') }}</strong>
          <span>音频状态</span>
        </div>
      </div>
    </section>

    <main class="registration-workspace">
      <section class="registration-panel">
        <div class="panel-header">
          <div>
            <h2>新建声纹</h2>
            <p>先填写身份信息，再采集一段清晰音频。</p>
          </div>
          <el-tag type="success" effect="light">建议 3-10 秒</el-tag>
        </div>

        <div class="section-title">
          <span class="step-index">1</span>
          <div>
            <h3>说话人信息</h3>
            <p>名称会显示在识别结果和说话人列表中。</p>
          </div>
        </div>

        <el-form
          ref="registrationForm"
          :model="formData"
          :rules="rules"
          label-position="top"
          class="registration-form"
        >
          <div class="form-grid">
            <el-form-item label="说话人姓名" prop="speakerName">
              <el-input
                v-model="formData.speakerName"
                placeholder="请输入姓名"
                clearable
              />
            </el-form-item>

            <el-form-item label="覆盖设置">
              <div class="overwrite-box">
                <el-switch
                  v-model="formData.overwrite"
                  active-text="覆盖已存在"
                  inactive-text="保留已存在"
                />
                <span>同名说话人存在时的处理方式</span>
              </div>
            </el-form-item>
          </div>

          <el-form-item label="描述信息">
            <el-input
              v-model="formData.description"
              type="textarea"
              :rows="3"
              placeholder="角色、部门或备注（可选）"
            />
          </el-form-item>

          <div class="section-title capture-title">
            <span class="step-index">2</span>
            <div>
              <h3>采集音频</h3>
              <p>使用录音或上传音频文件完成声纹样本。</p>
            </div>
          </div>

          <el-form-item label="输入方式" prop="inputMethod">
            <el-radio-group
              v-model="formData.inputMethod"
              class="method-switch"
              @change="onInputMethodChange"
            >
              <el-radio-button value="record">录音上传</el-radio-button>
              <el-radio-button value="file">文件上传</el-radio-button>
            </el-radio-group>
          </el-form-item>

          <div v-if="formData.inputMethod === 'record'" class="capture-card record-card">
            <div class="capture-status" :class="{ active: isRecording, ready: recordedAudio }">
              <el-icon><Microphone /></el-icon>
              <strong>{{ isRecording ? '录音中' : (recordedAudio ? '录音已就绪' : '等待录音') }}</strong>
              <span v-if="recordedAudio">{{ recordDuration }} 秒 · {{ formatFileSize(recordedAudio.size) }}</span>
              <span v-else>保持环境安静，录制一段自然语音。</span>
            </div>

            <div class="record-controls">
              <el-button
                :type="isRecording ? 'danger' : 'primary'"
                @click="toggleRecording"
              >
                <el-icon><Microphone /></el-icon>
                {{ isRecording ? '停止录音' : '开始录音' }}
              </el-button>

              <el-button
                v-if="recordedAudio"
                type="success"
                plain
                @click="playRecording"
              >
                <el-icon><VideoPlay /></el-icon>
                播放
              </el-button>

              <el-button
                v-if="recordedAudio"
                type="warning"
                plain
                @click="clearRecording"
              >
                <el-icon><Delete /></el-icon>
                清除
              </el-button>
            </div>
          </div>

          <div v-if="formData.inputMethod === 'file'" class="capture-card file-card">
            <el-form-item prop="audioFile">
              <el-upload
                ref="uploadRef"
                class="audio-upload"
                drag
                :auto-upload="false"
                :show-file-list="true"
                :limit="1"
                accept=".wav,.mp3,.m4a,.flac"
                @change="onFileChange"
                @remove="onFileRemove"
              >
                <el-icon class="el-icon--upload"><UploadFilled /></el-icon>
                <div class="el-upload__text">
                  将音频文件拖到此处，或<em>点击上传</em>
                </div>
                <template #tip>
                  <div class="el-upload__tip">
                    支持 WAV、MP3、M4A、FLAC 格式
                  </div>
                </template>
              </el-upload>
            </el-form-item>
          </div>

          <div class="form-actions">
            <el-button
              type="primary"
              :loading="isRegistering"
              :disabled="isRecording"
              @click="registerSpeaker"
            >
              <el-icon><UserFilled /></el-icon>
              注册声纹
            </el-button>

            <el-button @click="resetForm">
              <el-icon><RefreshLeft /></el-icon>
              重置
            </el-button>
          </div>
        </el-form>
      </section>

      <section class="library-panel">
        <div class="panel-header">
          <div>
            <h2>声纹库</h2>
            <p>查看、刷新和删除已注册说话人。</p>
          </div>
          <span class="count-pill">{{ speakersList.length }} 人</span>
        </div>

        <div v-if="speakersList.length === 0" class="empty-state">
          <el-icon><User /></el-icon>
          <strong>暂无已注册的说话人</strong>
          <span>完成一次声纹注册后会显示在这里。</span>
        </div>

        <div v-else class="speaker-list">
          <article
            v-for="speaker in speakersList"
            :key="speaker.speaker_name"
            class="speaker-card"
          >
            <div class="speaker-avatar">
              {{ speaker.speaker_name.slice(0, 1).toUpperCase() }}
            </div>

            <div class="speaker-info">
              <div class="speaker-topline">
                <h3>{{ speaker.speaker_name }}</h3>
                <el-tooltip content="删除说话人" placement="top">
                  <button
                    type="button"
                    class="delete-btn"
                    :aria-label="`删除说话人 ${speaker.speaker_name}`"
                    @click="deleteSpeaker(speaker.speaker_name)"
                  >
                    <el-icon><Delete /></el-icon>
                  </button>
                </el-tooltip>
              </div>
              <p>{{ speaker.description || '无描述' }}</p>
              <div class="speaker-meta">
                <span>ID: {{ speaker.speaker_id }}</span>
                <span>{{ formatDate(speaker.registration_time) }}</span>
              </div>
            </div>
          </article>
        </div>
      </section>
    </main>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { 
  ArrowLeft,
  Connection,
  Microphone, 
  VideoPlay, 
  Delete, 
  UploadFilled, 
  User,
  UserFilled, 
  RefreshLeft,
  Refresh
} from '@element-plus/icons-vue'
import type { UploadFile, UploadFiles } from 'element-plus'
import { 
  registerSpeaker as registerSpeakerAPI, 
  listSpeakers as listSpeakersAPI, 
  deleteSpeaker as deleteSpeakerAPI,
  blobToBase64, 
  fileToBase64, 
  formatFileSize, 
  formatDate,
  type SpeakerInfo 
} from '../api/speaker'

const router = useRouter()

// 表单数据
const formData = reactive({
  speakerName: '',
  description: '',
  overwrite: false,
  inputMethod: 'record' as 'record' | 'file',
  audioFile: null as File | null
})

// 表单验证规则
const rules = {
  speakerName: [
    { required: true, message: '请输入说话人姓名', trigger: 'blur' },
    { min: 2, max: 50, message: '姓名长度在 2 到 50 个字符', trigger: 'blur' }
  ],
  inputMethod: [
    { required: true, message: '请选择输入方式', trigger: 'change' }
  ],
  audioFile: [
    { 
      validator: (rule: any, value: any, callback: any) => {
        if (formData.inputMethod === 'file' && !formData.audioFile) {
          callback(new Error('请上传音频文件'))
        } else {
          callback()
        }
      }, 
      trigger: 'change' 
    }
  ]
}

// 录音相关
const isRecording = ref(false)
const recordedAudio = ref<Blob | null>(null)
const recordDuration = ref(0)
const mediaRecorder = ref<MediaRecorder | null>(null)
const audioChunks = ref<Blob[]>([])
const recordStartTime = ref(0)
const audioStream = ref<MediaStream | null>(null)

// 上传相关
const uploadRef = ref()
const registrationForm = ref()

// 状态
const isRegistering = ref(false)
const speakersList = ref<SpeakerInfo[]>([])

const goBack = () => {
  router.back()
}

const goToSerialBinding = () => {
  router.push({ name: 'serial-port-settings' })
}

// 输入方式变更
const onInputMethodChange = () => {
  // 清除之前的数据
  if (formData.inputMethod === 'record') {
    formData.audioFile = null
    if (uploadRef.value) {
      uploadRef.value.clearFiles()
    }
  } else {
    clearRecording()
  }
}

// 录音功能
const toggleRecording = async () => {
  console.log('toggleRecording called, current state:', isRecording.value)
  
  if (isRecording.value) {
    stopRecording()
  } else {
    await startRecording()
  }
}

const startRecording = async () => {
  try {
    console.log('Starting recording...')
    audioStream.value = await navigator.mediaDevices.getUserMedia({ 
      audio: {
        sampleRate: 16000,
        channelCount: 1,
        echoCancellation: true,
        noiseSuppression: true
      } 
    })
    
    console.log('Got audio stream, creating MediaRecorder')
    // 使用标准音频格式
    let options = { mimeType: 'audio/wav' }
    if (!MediaRecorder.isTypeSupported('audio/wav')) {
      // 如果不支持WAV，尝试其他格式
      if (MediaRecorder.isTypeSupported('audio/mp4')) {
        options = { mimeType: 'audio/mp4' }
        console.log('使用MP4格式录音')
      } else {
        console.log('浏览器不支持标准音频格式，可能无法正常处理')
        options = { mimeType: 'audio/wav' } // 默认使用WAV
      }
    } else {
      console.log('使用WAV格式录音')
    }
    
    mediaRecorder.value = new MediaRecorder(audioStream.value, options)
    
    audioChunks.value = []
    recordStartTime.value = Date.now()
    
    mediaRecorder.value.ondataavailable = (event) => {
      console.log('Data available, size:', event.data.size)
      if (event.data.size > 0) {
        audioChunks.value.push(event.data)
      }
    }
    
    mediaRecorder.value.onstop = () => {
      console.log('MediaRecorder onstop event triggered')
      // 使用与录音格式一致的MIME类型
      const mimeType = options.mimeType || 'audio/wav'
      recordedAudio.value = new Blob(audioChunks.value, { type: mimeType })
      recordDuration.value = Math.round((Date.now() - recordStartTime.value) / 1000)
      
      console.log('Recording completed, duration:', recordDuration.value, 'seconds')
      console.log('Audio blob size:', recordedAudio.value.size, 'bytes')
      console.log('Audio blob type:', mimeType)
      
      // 在onstop事件中不需要再次停止轨道，因为stopRecording已经处理了
    }
    
    mediaRecorder.value.onstart = () => {
      console.log('MediaRecorder started successfully')
    }
    
    mediaRecorder.value.onerror = (event) => {
      console.error('MediaRecorder error:', event)
    }
    
    console.log('Starting MediaRecorder...')
    mediaRecorder.value.start()
    isRecording.value = true
    console.log('isRecording set to true, current value:', isRecording.value)
    ElMessage.success('开始录音')
    
  } catch (error) {
    console.error('录音失败:', error)
    ElMessage.error('录音失败，请检查麦克风权限')
  }
}

const stopRecording = () => {
  console.log('stopRecording called, isRecording:', isRecording.value, 'mediaRecorder state:', mediaRecorder.value?.state)
  
  if (mediaRecorder.value && isRecording.value) {
    try {
      // 检查MediaRecorder状态
      if (mediaRecorder.value.state === 'recording') {
        mediaRecorder.value.stop()
        console.log('MediaRecorder stopped')
      }
      
      isRecording.value = false
      
      // 立即停止音频轨道
      if (audioStream.value) {
        console.log('Stopping audio tracks, track count:', audioStream.value.getTracks().length)
        audioStream.value.getTracks().forEach(track => {
          console.log('Stopping track:', track.kind, track.readyState)
          track.stop()
        })
        audioStream.value = null
        console.log('Audio stream cleared')
      }
      
      ElMessage.success('录音完成')
    } catch (error) {
      console.error('Error stopping recording:', error)
      isRecording.value = false
      ElMessage.error('停止录音时出错')
    }
  } else {
    console.log('Cannot stop recording: mediaRecorder or isRecording is false')
  }
}

const playRecording = () => {
  if (recordedAudio.value) {
    const audioUrl = URL.createObjectURL(recordedAudio.value)
    const audio = new Audio(audioUrl)
    audio.play()
    audio.onended = () => {
      URL.revokeObjectURL(audioUrl)
    }
  }
}

const clearRecording = () => {
  recordedAudio.value = null
  recordDuration.value = 0
  audioChunks.value = []
  
  if (isRecording.value) {
    stopRecording()
  }
  
  // 确保清理音频流
  if (audioStream.value) {
    audioStream.value.getTracks().forEach(track => track.stop())
    audioStream.value = null
  }
}

// 文件上传
const onFileChange = (file: UploadFile, files: UploadFiles) => {
  if (file.raw) {
    formData.audioFile = file.raw
  }
}

const onFileRemove = () => {
  formData.audioFile = null
}

// 注册说话人
const registerSpeaker = async () => {
  try {
    // 表单验证
    await registrationForm.value.validate()
    
    // 检查音频数据
    let audioData: string | null = null
    
    if (formData.inputMethod === 'record') {
      if (!recordedAudio.value) {
        ElMessage.error('请先录音')
        return
      }
      // 转换为Base64
      audioData = await blobToBase64(recordedAudio.value)
    } else {
      if (!formData.audioFile) {
        ElMessage.error('请选择音频文件')
        return
      }
      // 转换为Base64
      audioData = await fileToBase64(formData.audioFile)
    }
    
    isRegistering.value = true
    
    // 调用API
    const result = await registerSpeakerAPI({
      speaker_name: formData.speakerName,
      description: formData.description,
      overwrite: formData.overwrite,
      audio_data: audioData
    })
    
    ElMessage.success('说话人声纹注册成功！')
    resetForm()
    loadSpeakersList()
    
  } catch (error) {
    console.error('注册失败:', error)
    ElMessage.error(`注册失败: ${(error as Error).message}`)
  } finally {
    isRegistering.value = false
  }
}

// 重置表单
const resetForm = () => {
  registrationForm.value?.resetFields()
  formData.speakerName = ''
  formData.description = ''
  formData.overwrite = false
  formData.inputMethod = 'record'
  formData.audioFile = null
  clearRecording()
  if (uploadRef.value) {
    uploadRef.value.clearFiles()
  }
}

// 加载说话人列表
const loadSpeakersList = async () => {
  try {
    const result = await listSpeakersAPI()
    speakersList.value = result.speakers || []
  } catch (error) {
    console.error('获取说话人列表失败:', error)
    ElMessage.error('获取说话人列表失败')
  }
}

// 删除说话人
const deleteSpeaker = async (speakerName: string) => {
  try {
    await ElMessageBox.confirm(
      `确定要删除说话人 "${speakerName}" 吗？此操作不可撤销。`,
      '确认删除',
      {
        confirmButtonText: '确定删除',
        cancelButtonText: '取消',
        type: 'warning',
      }
    )
    
    await deleteSpeakerAPI({ speaker_name: speakerName })
    ElMessage.success('说话人删除成功！')
    loadSpeakersList() // 重新加载列表
    
  } catch (error) {
    if (error !== 'cancel') {
      console.error('删除说话人失败:', error)
      ElMessage.error(`删除失败: ${(error as Error).message}`)
    }
  }
}

// 工具函数已从 API 模块导入

// 组件挂载时加载说话人列表
onMounted(() => {
  loadSpeakersList()
})
</script>

<style scoped lang="scss">
$bg: #f6f7fb;
$surface: #ffffff;
$surface-soft: #f9fafb;
$surface-tint: #f0fdfa;
$text-primary: #111827;
$text-secondary: #667085;
$text-muted: #98a2b3;
$border: #e5e7eb;
$primary: #0f766e;
$blue: #2563eb;
$danger: #dc2626;
$shadow: 0 12px 28px rgba(15, 23, 42, 0.07);

.speaker-registration {
  --el-color-primary: #0f766e;
  --el-color-primary-dark-2: #0b5f58;
  --el-color-primary-light-3: #26a69a;
  --el-color-primary-light-5: #5eead4;
  --el-color-primary-light-7: #99f6e4;
  --el-color-primary-light-8: #ccfbf1;
  --el-color-primary-light-9: #f0fdfa;

  min-height: 100dvh;
  padding: 24px clamp(16px, 3vw, 32px);
  background: $bg;
  color: $text-primary;
  font-family: -apple-system, BlinkMacSystemFont, 'PingFang SC', 'Microsoft YaHei', sans-serif;
}

.registration-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  width: 100%;
  max-width: 1200px;
  margin: 0 auto 16px;
}

.header-main {
  display: flex;
  align-items: flex-start;
  gap: 16px;
  min-width: 0;
}

.back-btn,
.tool-btn,
.delete-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border: 1px solid $border;
  background: $surface;
  color: $text-primary;
  cursor: pointer;
  transition: background-color 0.18s ease, border-color 0.18s ease, color 0.18s ease, box-shadow 0.18s ease;

  &:focus-visible {
    outline: 3px solid rgba($primary, 0.22);
    outline-offset: 2px;
  }
}

.back-btn,
.tool-btn {
  min-height: 40px;
  gap: 7px;
  padding: 0 14px;
  border-radius: 8px;
  font-size: 14px;
  font-weight: 600;

  &:hover {
    border-color: #cbd5e1;
    background: $surface-soft;
  }
}

.back-btn {
  flex-shrink: 0;
}

.title-block {
  min-width: 0;

  .eyebrow {
    display: inline-flex;
    align-items: center;
    min-height: 22px;
    padding: 0 8px;
    border-radius: 999px;
    background: rgba($primary, 0.1);
    color: $primary;
    font-size: 12px;
    font-weight: 700;
  }

  h1 {
    margin: 8px 0 6px;
    color: $text-primary;
    font-size: 26px;
    font-weight: 750;
    line-height: 1.25;
    letter-spacing: 0;
  }

  p {
    max-width: 560px;
    margin: 0;
    color: $text-secondary;
    font-size: 14px;
    line-height: 1.6;
  }
}

.header-actions {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 8px;
  flex-wrap: wrap;
}

.overview-strip,
.registration-workspace {
  width: 100%;
  max-width: 1200px;
  margin: 0 auto;
}

.overview-strip {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
  margin-bottom: 16px;
}

.overview-item {
  display: flex;
  align-items: center;
  gap: 12px;
  min-height: 78px;
  padding: 16px;
  border: 1px solid $border;
  border-radius: 8px;
  background: $surface;

  > .el-icon {
    width: 42px;
    height: 42px;
    border-radius: 8px;
    background: $surface-tint;
    color: $primary;
    font-size: 20px;
    flex-shrink: 0;
  }

  div {
    display: flex;
    min-width: 0;
    flex-direction: column;
  }

  strong {
    color: $text-primary;
    font-size: 20px;
    font-weight: 750;
    line-height: 1.2;
  }

  span {
    margin-top: 4px;
    color: $text-secondary;
    font-size: 13px;
  }
}

.registration-workspace {
  display: grid;
  grid-template-columns: minmax(0, 1.42fr) minmax(340px, 0.9fr);
  align-items: start;
  gap: 16px;
}

.registration-panel,
.library-panel {
  border: 1px solid $border;
  border-radius: 8px;
  background: $surface;
  box-shadow: none;
}

.registration-panel {
  padding: 22px;
}

.library-panel {
  display: flex;
  min-height: 540px;
  max-height: calc(100dvh - 188px);
  flex-direction: column;
  padding: 20px;
}

.panel-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  padding-bottom: 16px;
  border-bottom: 1px solid $border;

  h2 {
    margin: 0;
    color: $text-primary;
    font-size: 18px;
    font-weight: 750;
    line-height: 1.3;
    letter-spacing: 0;
  }

  p {
    margin: 6px 0 0;
    color: $text-secondary;
    font-size: 13px;
    line-height: 1.5;
  }
}

.count-pill {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-height: 28px;
  padding: 0 10px;
  border-radius: 999px;
  background: rgba($blue, 0.1);
  color: $blue;
  font-size: 13px;
  font-weight: 700;
  white-space: nowrap;
}

.section-title {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  margin: 20px 0 14px;

  h3 {
    margin: 0;
    color: $text-primary;
    font-size: 15px;
    font-weight: 750;
    line-height: 1.35;
  }

  p {
    margin: 4px 0 0;
    color: $text-secondary;
    font-size: 13px;
    line-height: 1.5;
  }
}

.capture-title {
  margin-top: 26px;
  padding-top: 20px;
  border-top: 1px solid $border;
}

.step-index {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  border-radius: 8px;
  background: $primary;
  color: #ffffff;
  font-size: 13px;
  font-weight: 750;
  flex-shrink: 0;
}

.registration-form {
  :deep(.el-form-item__label) {
    margin-bottom: 7px;
    color: $text-primary;
    font-weight: 650;
    line-height: 1.3;
  }

  :deep(.el-input__wrapper),
  :deep(.el-textarea__inner) {
    border-radius: 8px;
    box-shadow: 0 0 0 1px $border inset;
    transition: box-shadow 0.18s ease;

    &:hover,
    &.is-focus {
      box-shadow: 0 0 0 1px rgba($primary, 0.7) inset, 0 0 0 3px rgba($primary, 0.1);
    }
  }

  :deep(.el-input__wrapper) {
    min-height: 42px;
  }

  :deep(.el-textarea__inner) {
    min-height: 92px;
    resize: vertical;
  }

  :deep(.el-button) {
    min-height: 40px;
    border-radius: 8px;
    font-weight: 650;
  }
}

.form-grid {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(240px, 0.9fr);
  gap: 14px;
}

.overwrite-box {
  display: flex;
  min-height: 42px;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
  padding: 0 12px;
  border: 1px solid $border;
  border-radius: 8px;
  background: $surface-soft;

  span {
    color: $text-secondary;
    font-size: 13px;
  }
}

.method-switch {
  width: 100%;

  :deep(.el-radio-button) {
    flex: 1 1 0;
  }

  :deep(.el-radio-button__inner) {
    width: 100%;
    min-height: 42px;
    border-color: $border;
    font-weight: 650;
  }

  :deep(.el-radio-button:first-child .el-radio-button__inner) {
    border-radius: 8px 0 0 8px;
  }

  :deep(.el-radio-button:last-child .el-radio-button__inner) {
    border-radius: 0 8px 8px 0;
  }
}

.capture-card {
  display: grid;
  gap: 16px;
  margin-top: 4px;
  padding: 16px;
  border: 1px solid $border;
  border-radius: 8px;
  background: $surface-soft;
}

.record-card {
  grid-template-columns: minmax(0, 1fr) auto;
  align-items: center;
}

.capture-status {
  display: grid;
  grid-template-columns: 44px minmax(0, 1fr);
  align-items: center;
  gap: 4px 12px;
  min-width: 0;

  .el-icon {
    grid-row: span 2;
    width: 44px;
    height: 44px;
    border-radius: 8px;
    background: #eef2ff;
    color: $blue;
    font-size: 20px;
  }

  strong {
    color: $text-primary;
    font-size: 15px;
    font-weight: 750;
    line-height: 1.3;
  }

  span {
    overflow: hidden;
    color: $text-secondary;
    font-size: 13px;
    line-height: 1.4;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  &.active .el-icon {
    background: rgba($danger, 0.1);
    color: $danger;
  }

  &.ready .el-icon {
    background: rgba($primary, 0.1);
    color: $primary;
  }
}

.record-controls {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  flex-wrap: wrap;
}

.file-card {
  padding: 0;
  background: transparent;

  :deep(.el-form-item) {
    margin-bottom: 0;
  }
}

.audio-upload {
  width: 100%;

  :deep(.el-upload) {
    width: 100%;
  }

  :deep(.el-upload-dragger) {
    width: 100%;
    padding: 28px 16px;
    border-color: $border;
    border-radius: 8px;
    background: $surface-soft;
    transition: border-color 0.18s ease, background-color 0.18s ease;

    &:hover {
      border-color: rgba($primary, 0.7);
      background: #f8fffd;
    }
  }

  :deep(.el-icon--upload) {
    margin-bottom: 8px;
    color: $primary;
    font-size: 32px;
  }
}

.form-actions {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  padding-top: 20px;

  :deep(.el-button) {
    min-width: 112px;
    min-height: 42px;
    border-radius: 8px;
    font-weight: 650;
  }
}

.empty-state {
  min-height: 320px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex: 1;
  flex-direction: column;
  gap: 8px;
  border: 1px dashed #cbd5e1;
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.64);
  color: $text-secondary;
  text-align: center;

  .el-icon {
    margin-bottom: 6px;
    color: $primary;
    font-size: 38px;
  }

  strong {
    color: $text-primary;
    font-size: 16px;
  }

  span {
    color: $text-secondary;
    font-size: 13px;
  }
}

.speaker-list {
  display: flex;
  flex: 1;
  min-height: 0;
  flex-direction: column;
  gap: 10px;
  margin-top: 14px;
  overflow-y: auto;
  padding-right: 4px;

  &::-webkit-scrollbar {
    width: 6px;
  }

  &::-webkit-scrollbar-track {
    background: transparent;
  }

  &::-webkit-scrollbar-thumb {
    background: #cbd5e1;
    border-radius: 999px;
  }
}

.speaker-card {
  display: grid;
  grid-template-columns: 42px minmax(0, 1fr);
  gap: 12px;
  padding: 14px;
  border: 1px solid $border;
  border-radius: 8px;
  background: $surface;
  transition: border-color 0.18s ease, box-shadow 0.18s ease;

  &:hover {
    border-color: rgba($primary, 0.36);
    box-shadow: $shadow;
  }
}

.speaker-avatar {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 42px;
  height: 42px;
  border-radius: 8px;
  background: rgba($primary, 0.1);
  color: $primary;
  font-size: 18px;
  font-weight: 800;
}

.speaker-info {
  min-width: 0;

  p {
    display: -webkit-box;
    overflow: hidden;
    margin: 5px 0 8px;
    color: $text-secondary;
    font-size: 13px;
    line-height: 1.5;
    -webkit-box-orient: vertical;
    -webkit-line-clamp: 2;
  }
}

.speaker-topline {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;

  h3 {
    min-width: 0;
    overflow: hidden;
    margin: 0;
    color: $text-primary;
    font-size: 15px;
    font-weight: 750;
    line-height: 1.35;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
}

.delete-btn {
  width: 34px;
  height: 34px;
  border-radius: 8px;
  color: $text-muted;
  flex-shrink: 0;

  &:hover {
    border-color: rgba($danger, 0.35);
    background: rgba($danger, 0.06);
    color: $danger;
  }
}

.speaker-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;

  span {
    display: inline-flex;
    align-items: center;
    min-height: 22px;
    max-width: 100%;
    overflow: hidden;
    padding: 0 8px;
    border-radius: 999px;
    background: $surface-soft;
    color: $text-secondary;
    font-size: 12px;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
}

@media (max-width: 960px) {
  .registration-workspace {
    grid-template-columns: 1fr;
  }

  .library-panel {
    min-height: 360px;
    max-height: none;
  }
}

@media (max-width: 760px) {
  .speaker-registration {
    padding: 16px;
  }

  .registration-header {
    flex-direction: column;
    align-items: stretch;
  }

  .header-main {
    flex-direction: column;
  }

  .back-btn {
    width: fit-content;
    min-height: 44px;
  }

  .header-actions {
    justify-content: flex-start;
  }

  .tool-btn {
    min-height: 44px;
    flex: 1 1 144px;
  }

  .registration-form {
    :deep(.el-button) {
      min-height: 44px;
    }
  }

  .overview-strip {
    grid-template-columns: 1fr;
  }

  .registration-panel,
  .library-panel {
    padding: 16px;
  }

  .panel-header,
  .form-grid,
  .record-card {
    grid-template-columns: 1fr;
  }

  .panel-header {
    flex-direction: column;
  }

  .method-switch {
    display: flex;
  }

  .record-controls {
    justify-content: flex-start;
  }

  .form-actions {
    flex-direction: column;

    :deep(.el-button) {
      width: 100%;
      margin-left: 0;
    }
  }
}

@media (max-width: 480px) {
  .title-block h1 {
    font-size: 22px;
  }

  .capture-status {
    grid-template-columns: 38px minmax(0, 1fr);

    .el-icon {
      width: 38px;
      height: 38px;
    }

    span {
      white-space: normal;
    }
  }

  .speaker-card {
    grid-template-columns: 1fr;
  }
}

@media (prefers-reduced-motion: reduce) {
  .back-btn,
  .tool-btn,
  .delete-btn,
  .speaker-card,
  .registration-form :deep(.el-input__wrapper),
  .registration-form :deep(.el-textarea__inner),
  .audio-upload :deep(.el-upload-dragger) {
    transition: none;
  }
}
</style>
