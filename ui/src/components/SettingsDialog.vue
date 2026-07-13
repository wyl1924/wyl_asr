<script setup lang="ts">
import { ref, reactive, watch } from 'vue'
import { ElMessage } from 'element-plus'
import type { FormInstance, FormRules } from 'element-plus'
import ColorPicker from './ColorPicker.vue'
import { subtitleSettingsApi, type SubtitleSettings } from '../api/subtitle-settings'

interface Props {
  visible: boolean
}

interface Emits {
  (e: 'update:visible', value: boolean): void
  (e: 'settings-saved'): void
}

const props = defineProps<Props>()
const emit = defineEmits<Emits>()

// Form reference
const formRef = ref<FormInstance>()

// Loading states
const loading = ref(false)
const saving = ref(false)

// Color picker visibility
const showBackgroundColorPicker = ref(false)
const showFontColorPicker = ref(false)

// Form data
const formData = reactive<SubtitleSettings>({
  windowWidth: 80,
  cornerRadius: 10,
  backgroundColor: '#000000',
  backgroundOpacity: 75,
  fontFamily: '宋体',
  fontSize: 14,
  fontColor: '默认',
  isBold: false,
  isItalic: false,
  showEnglish: false,
  maxDisplayLines: 2,
  scrollSpeed: 60,
  webSocketUrl: 'ws://127.0.0.1:10095/'
})

// Font family options
const fontFamilyOptions = [
  { label: '宋体', value: '宋体' },
  { label: '黑体', value: '黑体' },
  { label: '微软雅黑', value: '微软雅黑' },
  { label: 'Arial', value: 'Arial' },
  { label: 'Times New Roman', value: 'Times New Roman' },
  { label: 'Courier New', value: 'Courier New' }
]

// Validation rules
const rules = reactive<FormRules<SubtitleSettings>>({
  windowWidth: [
    { required: true, message: '请输入窗口宽度', trigger: 'blur' },
    { type: 'number', min: 10, max: 100, message: '窗口宽度必须在 10-100 之间', trigger: 'blur' }
  ],
  cornerRadius: [
    { required: true, message: '请输入圆角半径', trigger: 'blur' },
    { type: 'number', min: 0, max: 100, message: '圆角半径必须在 0-100 之间', trigger: 'blur' }
  ],
  backgroundColor: [
    { required: true, message: '请选择背景颜色', trigger: 'change' },
    { 
      pattern: /^#[0-9A-F]{6}$/i, 
      message: '背景颜色格式无效，请使用 #RRGGBB 格式', 
      trigger: 'change' 
    }
  ],
  backgroundOpacity: [
    { required: true, message: '请输入背景不透明度', trigger: 'blur' },
    { type: 'number', min: 0, max: 100, message: '背景不透明度必须在 0-100 之间', trigger: 'blur' }
  ],
  fontFamily: [
    { required: true, message: '请选择字体', trigger: 'change' }
  ],
  fontSize: [
    { required: true, message: '请输入字体大小', trigger: 'blur' },
    { type: 'number', min: 1, max: 100, message: '字体大小必须在 1-100 之间', trigger: 'blur' }
  ],
  fontColor: [
    { required: true, message: '请选择字体颜色', trigger: 'change' },
    { 
      validator: (rule, value, callback) => {
        if (value === '默认') {
          callback()
        } else if (!/^#[0-9A-F]{6}$/i.test(value)) {
          callback(new Error('字体颜色格式无效，请使用 #RRGGBB 格式'))
        } else {
          callback()
        }
      },
      trigger: 'change'
    }
  ],
  maxDisplayLines: [
    { required: true, message: '请输入最大显示行数', trigger: 'blur' },
    { type: 'number', min: 1, max: 20, message: '最大显示行数必须在 1-20 之间', trigger: 'blur' }
  ],
  scrollSpeed: [
    { required: true, message: '请输入滚动速度', trigger: 'blur' },
    { type: 'number', min: 20, max: 200, message: '滚动速度必须在 20-200 之间', trigger: 'blur' }
  ],
  webSocketUrl: [
    { required: true, message: '请输入 WebSocket 地址', trigger: 'blur' },
    { 
      pattern: /^wss?:\/\/.+/, 
      message: 'WebSocket 地址必须以 ws:// 或 wss:// 开头', 
      trigger: 'blur' 
    }
  ]
})

// Load settings from backend
async function loadSettings() {
  loading.value = true
  try {
    const response = await subtitleSettingsApi.getSubtitleSettings()
    if (response.success && response.data) {
      Object.assign(formData, response.data)
    } else {
      ElMessage.warning('加载设置失败，使用默认设置')
    }
  } catch (error) {
    console.error('加载设置失败:', error)
    ElMessage.error('加载设置失败')
  } finally {
    loading.value = false
  }
}

// Save settings
async function handleSave() {
  if (!formRef.value) return
  
  try {
    // Validate form
    const valid = await formRef.value.validate()
    if (!valid) {
      return
    }
    
    saving.value = true
    const response = await subtitleSettingsApi.saveSubtitleSettings(formData)
    
    if (response.success) {
      ElMessage.success('设置保存成功')
      emit('settings-saved')
      handleClose()
    } else {
      if (response.errors && response.errors.length > 0) {
        ElMessage.error(`设置验证失败: ${response.errors.join(', ')}`)
      } else {
        ElMessage.error(response.error || response.message || '保存设置失败')
      }
    }
  } catch (error) {
    console.error('保存设置失败:', error)
    ElMessage.error('保存设置失败')
  } finally {
    saving.value = false
  }
}

// Cancel and close dialog
function handleCancel() {
  handleClose()
}

// Close dialog
function handleClose() {
  emit('update:visible', false)
}

// Reset form to defaults
function handleReset() {
  Object.assign(formData, {
    windowWidth: 80,
    cornerRadius: 10,
    backgroundColor: '#000000',
    backgroundOpacity: 75,
    fontFamily: '宋体',
    fontSize: 14,
    fontColor: '默认',
    isBold: false,
    isItalic: false,
    showEnglish: false,
    maxDisplayLines: 2,
    scrollSpeed: 60,
    webSocketUrl: 'ws://127.0.0.1:10095/'
  })
  formRef.value?.clearValidate()
  ElMessage.success('已重置为默认设置')
}

// Handle background color picker confirm
function handleBackgroundColorConfirm(color: string) {
  formData.backgroundColor = color
  showBackgroundColorPicker.value = false
}

// Handle font color picker confirm
function handleFontColorConfirm(color: string) {
  formData.fontColor = color
  showFontColorPicker.value = false
}

// Use default font color
function useDefaultFontColor() {
  formData.fontColor = '默认'
  showFontColorPicker.value = false
}

// Watch for dialog visibility changes
watch(() => props.visible, (newVal) => {
  if (newVal) {
    loadSettings()
  }
})
</script>

<template>
  <el-dialog
    :model-value="visible"
    title="字幕显示设置"
    width="600px"
    :close-on-click-modal="false"
    @close="handleClose"
  >
    <el-form
      ref="formRef"
      :model="formData"
      :rules="rules"
      label-width="120px"
      v-loading="loading"
    >
      <!-- Window Settings -->
      <el-divider content-position="left">窗口设置</el-divider>
      
      <el-form-item label="窗口宽度 (%)" prop="windowWidth">
        <el-slider
          v-model="formData.windowWidth"
          :min="10"
          :max="100"
          :show-tooltip="true"
          style="width: 100%"
        />
        <el-input-number
          v-model="formData.windowWidth"
          :min="10"
          :max="100"
          style="margin-left: 10px; width: 100px"
        />
      </el-form-item>

      <el-form-item label="圆角半径" prop="cornerRadius">
        <el-slider
          v-model="formData.cornerRadius"
          :min="0"
          :max="100"
          :show-tooltip="true"
          style="width: 100%"
        />
        <el-input-number
          v-model="formData.cornerRadius"
          :min="0"
          :max="100"
          style="margin-left: 10px; width: 100px"
        />
      </el-form-item>

      <!-- Background Settings -->
      <el-divider content-position="left">背景设置</el-divider>

      <el-form-item label="背景颜色" prop="backgroundColor">
        <div style="display: flex; align-items: center; gap: 10px;">
          <div
            :style="{
              width: '40px',
              height: '40px',
              borderRadius: '4px',
              backgroundColor: formData.backgroundColor,
              border: '1px solid #dcdfe6',
              cursor: 'pointer'
            }"
            @click="showBackgroundColorPicker = true"
          ></div>
          <el-input
            v-model="formData.backgroundColor"
            placeholder="#000000"
            style="flex: 1"
          />
          <el-button @click="showBackgroundColorPicker = true">选择颜色</el-button>
        </div>
      </el-form-item>

      <el-form-item label="背景不透明度" prop="backgroundOpacity">
        <el-slider
          v-model="formData.backgroundOpacity"
          :min="0"
          :max="100"
          :show-tooltip="true"
          style="width: 100%"
        />
        <el-input-number
          v-model="formData.backgroundOpacity"
          :min="0"
          :max="100"
          style="margin-left: 10px; width: 100px"
        />
      </el-form-item>

      <!-- Font Settings -->
      <el-divider content-position="left">字体设置</el-divider>

      <el-form-item label="字体" prop="fontFamily">
        <el-select v-model="formData.fontFamily" placeholder="请选择字体" style="width: 100%">
          <el-option
            v-for="font in fontFamilyOptions"
            :key="font.value"
            :label="font.label"
            :value="font.value"
          />
        </el-select>
      </el-form-item>

      <el-form-item label="字体大小" prop="fontSize">
        <el-slider
          v-model="formData.fontSize"
          :min="1"
          :max="100"
          :show-tooltip="true"
          style="width: 100%"
        />
        <el-input-number
          v-model="formData.fontSize"
          :min="1"
          :max="100"
          style="margin-left: 10px; width: 100px"
        />
      </el-form-item>

      <el-form-item label="字体颜色" prop="fontColor">
        <div style="display: flex; align-items: center; gap: 10px;">
          <div
            :style="{
              width: '40px',
              height: '40px',
              borderRadius: '4px',
              backgroundColor: formData.fontColor === '默认' ? '#FFFFFF' : formData.fontColor,
              border: '1px solid #dcdfe6',
              cursor: 'pointer'
            }"
            @click="showFontColorPicker = true"
          ></div>
          <el-input
            v-model="formData.fontColor"
            placeholder="默认"
            style="flex: 1"
          />
          <el-button @click="showFontColorPicker = true">选择颜色</el-button>
          <el-button @click="useDefaultFontColor">使用默认</el-button>
        </div>
      </el-form-item>

      <el-form-item label="字体样式">
        <el-checkbox v-model="formData.isBold" label="粗体" />
        <el-checkbox v-model="formData.isItalic" label="斜体" style="margin-left: 20px" />
      </el-form-item>

      <!-- Display Settings -->
      <el-divider content-position="left">显示设置</el-divider>

      <el-form-item label="显示英文">
        <el-switch v-model="formData.showEnglish" />
      </el-form-item>

      <el-form-item label="最大显示行数" prop="maxDisplayLines">
        <el-slider
          v-model="formData.maxDisplayLines"
          :min="1"
          :max="20"
          :show-tooltip="true"
          style="width: 100%"
        />
        <el-input-number
          v-model="formData.maxDisplayLines"
          :min="1"
          :max="20"
          style="margin-left: 10px; width: 100px"
        />
      </el-form-item>

      <el-form-item label="滚动速度" prop="scrollSpeed">
        <el-slider
          v-model="formData.scrollSpeed"
          :min="20"
          :max="200"
          :show-tooltip="true"
          style="width: 100%"
        />
        <el-input-number
          v-model="formData.scrollSpeed"
          :min="20"
          :max="200"
          style="margin-left: 10px; width: 100px"
        />
      </el-form-item>

      <!-- Connection Settings -->
      <el-divider content-position="left">连接设置</el-divider>

      <el-form-item label="WebSocket 地址" prop="webSocketUrl">
        <el-input
          v-model="formData.webSocketUrl"
          placeholder="ws://127.0.0.1:10095/"
        />
      </el-form-item>
    </el-form>

    <template #footer>
      <div style="display: flex; justify-content: space-between;">
        <el-button @click="handleReset">重置为默认</el-button>
        <div>
          <el-button @click="handleCancel">取消</el-button>
          <el-button type="primary" :loading="saving" @click="handleSave">保存</el-button>
        </div>
      </div>
    </template>

    <!-- Background Color Picker Dialog -->
    <el-dialog
      v-model="showBackgroundColorPicker"
      title="选择背景颜色"
      width="380px"
      append-to-body
    >
      <ColorPicker
        :model-value="formData.backgroundColor"
        @confirm="handleBackgroundColorConfirm"
        @cancel="showBackgroundColorPicker = false"
      />
    </el-dialog>

    <!-- Font Color Picker Dialog -->
    <el-dialog
      v-model="showFontColorPicker"
      title="选择字体颜色"
      width="380px"
      append-to-body
    >
      <ColorPicker
        :model-value="formData.fontColor === '默认' ? '#FFFFFF' : formData.fontColor"
        @confirm="handleFontColorConfirm"
        @cancel="showFontColorPicker = false"
      />
    </el-dialog>
  </el-dialog>
</template>

<style scoped>
.el-form-item {
  margin-bottom: 22px;
}

.el-divider {
  margin: 20px 0;
}

:deep(.el-slider) {
  flex: 1;
}
</style>
