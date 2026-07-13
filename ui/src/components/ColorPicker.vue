<script setup lang="ts">
import { ref, computed, watch } from 'vue'

interface Props {
  modelValue: string  // Hex color value
}

interface Emits {
  (e: 'update:modelValue', value: string): void
  (e: 'confirm', value: string): void
  (e: 'cancel'): void
}

const props = defineProps<Props>()
const emit = defineEmits<Emits>()

// HSV color model (Hue, Saturation, Value/Brightness)
const hue = ref(0)          // 0-360
const saturation = ref(100) // 0-100
const value = ref(100)      // 0-100 (brightness)

// Hex color input
const hexColor = ref(props.modelValue || '#000000')

// Convert HSV to RGB
function hsvToRgb(h: number, s: number, v: number): { r: number; g: number; b: number } {
  s = s / 100
  v = v / 100
  
  const c = v * s
  const x = c * (1 - Math.abs(((h / 60) % 2) - 1))
  const m = v - c
  
  let r = 0, g = 0, b = 0
  
  if (h >= 0 && h < 60) {
    r = c; g = x; b = 0
  } else if (h >= 60 && h < 120) {
    r = x; g = c; b = 0
  } else if (h >= 120 && h < 180) {
    r = 0; g = c; b = x
  } else if (h >= 180 && h < 240) {
    r = 0; g = x; b = c
  } else if (h >= 240 && h < 300) {
    r = x; g = 0; b = c
  } else if (h >= 300 && h < 360) {
    r = c; g = 0; b = x
  }
  
  return {
    r: Math.round((r + m) * 255),
    g: Math.round((g + m) * 255),
    b: Math.round((b + m) * 255)
  }
}

// Convert RGB to Hex
function rgbToHex(r: number, g: number, b: number): string {
  const toHex = (n: number) => {
    const hex = n.toString(16)
    return hex.length === 1 ? '0' + hex : hex
  }
  return `#${toHex(r)}${toHex(g)}${toHex(b)}`.toUpperCase()
}

// Convert Hex to RGB
function hexToRgb(hex: string): { r: number; g: number; b: number } | null {
  const result = /^#?([a-f\d]{2})([a-f\d]{2})([a-f\d]{2})$/i.exec(hex)
  return result ? {
    r: parseInt(result[1], 16),
    g: parseInt(result[2], 16),
    b: parseInt(result[3], 16)
  } : null
}

// Convert RGB to HSV
function rgbToHsv(r: number, g: number, b: number): { h: number; s: number; v: number } {
  r = r / 255
  g = g / 255
  b = b / 255
  
  const max = Math.max(r, g, b)
  const min = Math.min(r, g, b)
  const delta = max - min
  
  let h = 0
  const s = max === 0 ? 0 : (delta / max) * 100
  const v = max * 100
  
  if (delta !== 0) {
    if (max === r) {
      h = 60 * (((g - b) / delta) % 6)
    } else if (max === g) {
      h = 60 * (((b - r) / delta) + 2)
    } else {
      h = 60 * (((r - g) / delta) + 4)
    }
  }
  
  if (h < 0) h += 360
  
  return { h, s, v }
}

// Current selected color as hex
const selectedColor = computed(() => {
  const rgb = hsvToRgb(hue.value, saturation.value, value.value)
  return rgbToHex(rgb.r, rgb.g, rgb.b)
})

// Hue color (pure hue at full saturation and value)
const hueColor = computed(() => {
  const rgb = hsvToRgb(hue.value, 100, 100)
  return rgbToHex(rgb.r, rgb.g, rgb.b)
})

// Watch for HSV changes and update hex input
watch([hue, saturation, value], () => {
  hexColor.value = selectedColor.value
})

// Watch for hex input changes
watch(hexColor, (newHex) => {
  if (/^#[0-9A-F]{6}$/i.test(newHex)) {
    const rgb = hexToRgb(newHex)
    if (rgb) {
      const hsv = rgbToHsv(rgb.r, rgb.g, rgb.b)
      hue.value = hsv.h
      saturation.value = hsv.s
      value.value = hsv.v
    }
  }
})

// Initialize from prop value
if (props.modelValue) {
  const rgb = hexToRgb(props.modelValue)
  if (rgb) {
    const hsv = rgbToHsv(rgb.r, rgb.g, rgb.b)
    hue.value = hsv.h
    saturation.value = hsv.s
    value.value = hsv.v
  }
}

// Handle color picker area click
function handleColorPickerClick(event: MouseEvent) {
  const target = event.currentTarget as HTMLElement
  const rect = target.getBoundingClientRect()
  const x = event.clientX - rect.left
  const y = event.clientY - rect.top
  
  // Calculate saturation (0-100) based on X position
  saturation.value = Math.max(0, Math.min(100, (x / rect.width) * 100))
  
  // Calculate value/brightness (0-100) based on Y position (inverted: top=100, bottom=0)
  value.value = Math.max(0, Math.min(100, (1 - y / rect.height) * 100))
}

// Handle hue bar click
function handleHueBarClick(event: MouseEvent) {
  const target = event.currentTarget as HTMLElement
  const rect = target.getBoundingClientRect()
  const x = event.clientX - rect.left
  
  // Calculate hue (0-360) based on X position
  hue.value = Math.max(0, Math.min(360, (x / rect.width) * 360))
}

// Handle grayscale bar click
function handleGrayscaleBarClick(event: MouseEvent) {
  const target = event.currentTarget as HTMLElement
  const rect = target.getBoundingClientRect()
  const x = event.clientX - rect.left
  
  // Calculate grayscale value (0-100)
  const gray = Math.max(0, Math.min(100, (x / rect.width) * 100))
  
  // Set to grayscale: saturation = 0, value = gray
  saturation.value = 0
  value.value = gray
}

// Handle confirm
function handleConfirm() {
  emit('update:modelValue', selectedColor.value)
  emit('confirm', selectedColor.value)
}

// Handle cancel
function handleCancel() {
  emit('cancel')
}
</script>

<template>
  <div class="color-picker">
    <!-- 2D Color Selection Area (Saturation x Brightness) -->
    <div 
      class="color-picker-area"
      :style="{ backgroundColor: hueColor }"
      @click="handleColorPickerClick"
    >
      <div class="saturation-gradient"></div>
      <div class="brightness-gradient"></div>
    </div>

    <!-- Hue Bar and Grayscale Bar -->
    <div class="color-bars">
      <!-- Current Color Preview -->
      <div 
        class="color-preview"
        :style="{ backgroundColor: selectedColor }"
      ></div>

      <!-- Hue Bar (Rainbow Gradient) -->
      <div 
        class="hue-bar"
        @click="handleHueBarClick"
      ></div>
    </div>

    <!-- Grayscale Bar -->
    <div 
      class="grayscale-bar"
      @click="handleGrayscaleBarClick"
    ></div>

    <!-- HEX Input -->
    <div class="hex-input-container">
      <input 
        v-model="hexColor"
        type="text"
        class="hex-input"
        placeholder="#000000"
        maxlength="7"
      />
      <span class="hex-label">HEX</span>
    </div>

    <!-- OK/Cancel Buttons -->
    <div class="button-container">
      <button class="btn-cancel" @click="handleCancel">取消</button>
      <button class="btn-confirm" @click="handleConfirm">确定</button>
    </div>
  </div>
</template>

<style scoped>
.color-picker {
  width: 320px;
  padding: 15px;
  display: flex;
  flex-direction: column;
  gap: 15px;
  background: white;
}

/* 2D Color Selection Area */
.color-picker-area {
  position: relative;
  height: 220px;
  border-radius: 8px;
  border: 1px solid #DDDDDD;
  cursor: crosshair;
  overflow: hidden;
}

.saturation-gradient {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: linear-gradient(to right, #FFFFFF, transparent);
}

.brightness-gradient {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: linear-gradient(to bottom, transparent, #000000);
}

/* Color Bars Container */
.color-bars {
  display: grid;
  grid-template-columns: 50px 1fr;
  gap: 10px;
  align-items: center;
}

/* Current Color Preview */
.color-preview {
  width: 40px;
  height: 40px;
  border-radius: 20px;
  border: 2px solid #DDDDDD;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
}

/* Hue Bar (Rainbow Gradient) */
.hue-bar {
  height: 40px;
  border-radius: 6px;
  cursor: pointer;
  background: linear-gradient(to right,
    #FF0000 0%,
    #FFFF00 17%,
    #00FF00 33%,
    #00FFFF 50%,
    #0000FF 67%,
    #FF00FF 83%,
    #FF0000 100%
  );
}

/* Grayscale Bar */
.grayscale-bar {
  height: 25px;
  border-radius: 6px;
  cursor: pointer;
  background: linear-gradient(to right,
    #FFFFFF 0%,
    #808080 50%,
    #000000 100%
  );
}

/* HEX Input */
.hex-input-container {
  display: grid;
  grid-template-columns: 1fr auto;
  gap: 10px;
  align-items: center;
}

.hex-input {
  height: 40px;
  padding: 0 15px;
  border: 1px solid #DDDDDD;
  border-radius: 6px;
  font-size: 16px;
  font-weight: 500;
  text-align: center;
  outline: none;
  transition: border-color 0.2s;
}

.hex-input:focus {
  border-color: #0078D4;
}

.hex-label {
  font-size: 14px;
  color: #999999;
  font-weight: 500;
}

/* Buttons */
.button-container {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
}

.btn-cancel,
.btn-confirm {
  width: 90px;
  height: 40px;
  border-radius: 6px;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s;
  border: none;
  outline: none;
}

.btn-cancel {
  background: white;
  color: #666666;
  border: 1px solid #DDDDDD;
}

.btn-cancel:hover {
  background: #F5F5F5;
}

.btn-confirm {
  background: #0078D4;
  color: white;
}

.btn-confirm:hover {
  background: #005A9E;
}

.btn-cancel:active,
.btn-confirm:active {
  transform: scale(0.98);
}
</style>
