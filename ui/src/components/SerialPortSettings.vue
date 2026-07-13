<script setup lang="ts">
import { ref, onMounted, watch } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { ArrowLeft } from '@element-plus/icons-vue'
import { listSpeakers, type SpeakerInfo } from '../api/speaker'

const router = useRouter()

interface Unit {
  unit_number: number
  unit_hex: string
  channel_name: string
  speaker_name: string
  model: string
}

const API_BASE = 'http://127.0.0.1:8080/api'
const allUnits = ref<Unit[]>([])
const registeredSpeakers = ref<SpeakerInfo[]>([])
const currentMode = ref('voiceprint')
const editingUnits = ref<Set<number>>(new Set())
const searchText = ref('')
const loading = ref(false)
const showConfigPanel = ref(false)

// 串口配置
const serialConfig = ref({
  enabled: false,
  port: 'COM1',
  baudrate: 115200,
  protocol_type: 'auto',
  logging: false,
  log_level: 'INFO'
})

// 统计数据
const stats = ref({
  total: 0,
  bound: 0,
  model1: 0,
  model2: 0
})

// 加载识别模式
const loadMode = async () => {
  try {
    const response = await fetch(`${API_BASE}/serial/mode`)
    const result = await response.json()
    
    if (result.code === 200 && result.data) {
      currentMode.value = result.data.mode
    }
  } catch (error) {
    console.error('加载模式失败:', error)
  }
}

// 切换模式
const switchMode = async (mode: string) => {
  try {
    const response = await fetch(`${API_BASE}/serial/mode`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ mode })
    })
    
    const result = await response.json()
    
    if (result.code === 200) {
      currentMode.value = mode
      ElMessage.success(`已切换到${result.data.description}`)
    } else {
      ElMessage.error(result.message)
    }
  } catch (error) {
    ElMessage.error('切换模式失败')
    console.error(error)
  }
}

// 加载单元列表
const loadUnits = async () => {
  loading.value = true
  try {
    const response = await fetch(`${API_BASE}/serial/units`)
    const result = await response.json()
    
    if (result.code === 200 && result.data) {
      allUnits.value = result.data.units || []
      updateStats()
      updateGroupedUnits()
    } else {
      ElMessage.error(result.message)
    }
  } catch (error) {
    ElMessage.error('加载数据失败')
    console.error(error)
  } finally {
    loading.value = false
  }
}

// 加载已注册参会人
const loadRegisteredSpeakers = async () => {
  try {
    const result = await listSpeakers()
    registeredSpeakers.value = result.speakers || []
  } catch (error) {
    registeredSpeakers.value = []
    console.warn('加载已注册参会人失败:', error)
  }
}

// 更新统计信息
const updateStats = () => {
  stats.value.total = allUnits.value.length
  stats.value.model1 = allUnits.value.filter(u => u.model === '型号1').length
  stats.value.model2 = allUnits.value.filter(u => u.model === '型号2').length
  stats.value.bound = allUnits.value.filter(u => 
    u.speaker_name && u.speaker_name !== u.channel_name
  ).length
}

// 按型号分组单元
const groupedUnits = ref<{ [key: string]: Unit[] }>({})

const updateGroupedUnits = () => {
  const filtered = searchText.value 
    ? allUnits.value.filter(unit => {
        const text = searchText.value.toLowerCase()
        return unit.unit_number.toString().includes(text) ||
               unit.unit_hex.toLowerCase().includes(text) ||
               unit.channel_name.toLowerCase().includes(text) ||
               (unit.speaker_name && unit.speaker_name.toLowerCase().includes(text))
      })
    : allUnits.value

  groupedUnits.value = {
    '型号1': filtered.filter(u => u.model === '型号1'),
    '型号2': filtered.filter(u => u.model === '型号2'),
    '其他': filtered.filter(u => u.model === '未知')
  }
}

// 切换编辑状态
const toggleEdit = (unitNumber: number) => {
  if (editingUnits.value.has(unitNumber)) {
    return
  }
  editingUnits.value.add(unitNumber)
}

// 取消编辑
const cancelEdit = (unitNumber: number) => {
  editingUnits.value.delete(unitNumber)
}

// 保存单个单元
const saveUnit = async (unit: Unit, newName: string) => {
  const speakerName = newName.trim()
  if (!speakerName) {
    ElMessage.error('说话人名称不能为空')
    return
  }

  try {
    const response = await fetch(`${API_BASE}/serial/units/${unit.unit_number}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ speaker_name: speakerName })
    })
    
    const result = await response.json()
    
    if (result.code === 200) {
      ElMessage.success('保存成功')
      editingUnits.value.delete(unit.unit_number)
      await loadUnits()
    } else {
      ElMessage.error(result.message)
    }
  } catch (error) {
    ElMessage.error('保存失败')
    console.error(error)
  }
}

// 保存全部
const saveAll = async () => {
  const updates: any[] = []
  
  editingUnits.value.forEach(unitNumber => {
    const unit = allUnits.value.find(u => u.unit_number === unitNumber)
    if (unit && unit.speaker_name.trim()) {
      updates.push({
        unit_number: unitNumber,
        speaker_name: unit.speaker_name.trim()
      })
    }
  })

  if (updates.length === 0) {
    ElMessage.info('没有需要保存的更改')
    return
  }

  try {
    const response = await fetch(`${API_BASE}/serial/units/batch`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ units: updates })
    })
    
    const result = await response.json()
    
    if (result.code === 200) {
      ElMessage.success(result.message)
      editingUnits.value.clear()
      await loadUnits()
    } else {
      ElMessage.error(result.message)
    }
  } catch (error) {
    ElMessage.error('批量保存失败')
    console.error(error)
  }
}

// 加载串口配置
const loadSerialConfig = async () => {
  try {
    const response = await fetch(`${API_BASE}/serial/config`)
    const result = await response.json()
    
    if (result.code === 200 && result.data) {
      serialConfig.value = result.data
    } else {
      ElMessage.error(result.message)
    }
  } catch (error) {
    ElMessage.error('加载串口配置失败')
    console.error(error)
  }
}

// 保存串口配置
const saveSerialConfig = async () => {
  if (!serialConfig.value.port.trim()) {
    ElMessage.error('串口号不能为空')
    return
  }

  try {
    const response = await fetch(`${API_BASE}/serial/config`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(serialConfig.value)
    })
    
    const result = await response.json()
    
    if (result.code === 200) {
      ElMessage.success('串口配置保存成功，重启服务器后生效')
      showConfigPanel.value = false
    } else {
      ElMessage.error(result.message)
    }
  } catch (error) {
    ElMessage.error('保存串口配置失败')
    console.error(error)
  }
}

const openConfigPanel = async () => {
  showConfigPanel.value = true
  await loadSerialConfig()
}

const goToSpeakerRegistration = () => {
  router.push('/speaker-registration')
}

// 返回首页
const goBack = () => {
  router.push('/')
}

// 监听搜索文本变化
const handleSearch = () => {
  updateGroupedUnits()
}

// 初始化
onMounted(async () => {
  await loadMode()
  await loadSerialConfig()
  await loadRegisteredSpeakers()
  await loadUnits()
})

watch(showConfigPanel, async (visible) => {
  if (visible) {
    await loadSerialConfig()
  }
})
</script>

<template>
  <div class="serial-port-container">
    <div class="header">
      <div class="header-content">
        <el-button @click="goBack" class="back-btn">
          <el-icon><ArrowLeft /></el-icon>
          返回
        </el-button>
        <h1>🎤 串口单元号绑定管理</h1>
        <p>管理会议系统单元号与说话人的绑定关系</p>
      </div>
    </div>

    <div class="mode-selector">
      <label>识别模式：</label>
      <div class="mode-buttons">
        <el-button 
          :type="currentMode === 'voiceprint' ? 'primary' : ''"
          @click="switchMode('voiceprint')"
        >
          声纹识别
        </el-button>
        <el-button 
          :type="currentMode === 'serial' ? 'primary' : ''"
          @click="switchMode('serial')"
        >
          串口识别
        </el-button>
        <el-button 
          :type="currentMode === 'hybrid' ? 'primary' : ''"
          @click="switchMode('hybrid')"
        >
          混合模式
        </el-button>
      </div>
      <el-button type="primary" @click="openConfigPanel" style="margin-left: auto;">
        ⚙️ 串口配置
      </el-button>
    </div>

    <!-- 串口配置面板 -->
    <el-dialog v-model="showConfigPanel" title="串口配置" width="600px">
      <el-form :model="serialConfig" label-width="100px">
        <el-form-item label="启用串口">
          <el-switch v-model="serialConfig.enabled" />
        </el-form-item>
        <el-form-item label="串口号">
          <el-input v-model="serialConfig.port" placeholder="COM1" />
        </el-form-item>
        <el-form-item label="波特率">
          <el-select v-model="serialConfig.baudrate">
            <el-option label="9600" :value="9600" />
            <el-option label="19200" :value="19200" />
            <el-option label="38400" :value="38400" />
            <el-option label="57600" :value="57600" />
            <el-option label="115200" :value="115200" />
          </el-select>
        </el-form-item>
        <el-form-item label="协议类型">
          <el-select v-model="serialConfig.protocol_type">
            <el-option label="自动识别" value="auto" />
            <el-option label="协议A" value="A" />
            <el-option label="协议B" value="B" />
          </el-select>
        </el-form-item>
        <el-form-item label="启用日志">
          <el-switch v-model="serialConfig.logging" />
        </el-form-item>
        <el-form-item label="日志级别">
          <el-select v-model="serialConfig.log_level">
            <el-option label="DEBUG" value="DEBUG" />
            <el-option label="INFO" value="INFO" />
            <el-option label="WARNING" value="WARNING" />
            <el-option label="ERROR" value="ERROR" />
          </el-select>
        </el-form-item>
      </el-form>
      <el-alert
        title="注意：修改串口配置后需要重启ASR服务器才能生效"
        type="warning"
        :closable="false"
        style="margin-top: 15px;"
      />
      <template #footer>
        <el-button @click="showConfigPanel = false">取消</el-button>
        <el-button type="primary" @click="loadSerialConfig">刷新</el-button>
        <el-button type="success" @click="saveSerialConfig">保存配置</el-button>
      </template>
    </el-dialog>

    <div class="toolbar">
      <div class="search-box">
        <el-input
          v-model="searchText"
          placeholder="🔍 搜索单元号或说话人..."
          @input="handleSearch"
          clearable
        />
      </div>
      <div class="toolbar-buttons">
        <el-button @click="goToSpeakerRegistration">👥 参会人注册</el-button>
        <el-button type="success" @click="saveAll">💾 保存全部</el-button>
        <el-button type="primary" @click="loadUnits">🔄 刷新</el-button>
      </div>
    </div>

    <div class="content" v-loading="loading">
      <div v-if="allUnits.length === 0" class="empty-state">
        <div class="empty-state-icon">📭</div>
        <div class="empty-state-text">暂无单元号绑定</div>
        <div class="empty-state-hint">点击单元卡片开始绑定说话人</div>
      </div>

      <div v-else>
        <!-- 型号1 -->
        <div v-if="groupedUnits['型号1']?.length > 0" class="model-section">
          <div class="model-header">
            <span class="model-badge">型号1</span>
            <span class="model-title">01-0F (通道01-15)</span>
          </div>
          <div class="units-grid">
            <div 
              v-for="unit in groupedUnits['型号1']" 
              :key="unit.unit_number"
              class="unit-card"
              :class="{ editing: editingUnits.has(unit.unit_number) }"
              @click="toggleEdit(unit.unit_number)"
            >
              <div class="unit-header">
                <span class="unit-number">单元 {{ unit.unit_number }}</span>
                <span class="unit-hex">{{ unit.unit_hex }}</span>
              </div>
              <div class="channel-info">{{ unit.channel_name }}</div>
              
              <div v-if="editingUnits.has(unit.unit_number)" @click.stop>
                <el-select
                  v-model="unit.speaker_name"
                  filterable
                  allow-create
                  default-first-option
                  clearable
                  placeholder="选择或输入说话人姓名"
                >
                  <el-option
                    v-for="speaker in registeredSpeakers"
                    :key="speaker.speaker_id"
                    :label="speaker.speaker_name"
                    :value="speaker.speaker_name"
                  />
                </el-select>
                <div class="unit-hint">
                  {{ registeredSpeakers.length > 0 ? '可直接选择已注册参会人，也可输入新名称' : '暂无已注册参会人，可直接输入姓名' }}
                </div>
                <div class="unit-actions">
                  <el-button type="success" size="small" @click="saveUnit(unit, unit.speaker_name)">保存</el-button>
                  <el-button type="danger" size="small" @click="cancelEdit(unit.unit_number)">取消</el-button>
                </div>
              </div>
              
              <div v-else class="speaker-display" :class="{ empty: !unit.speaker_name || unit.speaker_name === unit.channel_name }">
                {{ (!unit.speaker_name || unit.speaker_name === unit.channel_name) ? '点击设置说话人' : unit.speaker_name }}
              </div>
            </div>
          </div>
        </div>

        <!-- 型号2 -->
        <div v-if="groupedUnits['型号2']?.length > 0" class="model-section">
          <div class="model-header">
            <span class="model-badge">型号2</span>
            <span class="model-title">21-36 (通道01-22)</span>
          </div>
          <div class="units-grid">
            <div 
              v-for="unit in groupedUnits['型号2']" 
              :key="unit.unit_number"
              class="unit-card"
              :class="{ editing: editingUnits.has(unit.unit_number) }"
              @click="toggleEdit(unit.unit_number)"
            >
              <div class="unit-header">
                <span class="unit-number">单元 {{ unit.unit_number }}</span>
                <span class="unit-hex">{{ unit.unit_hex }}</span>
              </div>
              <div class="channel-info">{{ unit.channel_name }}</div>
              
              <div v-if="editingUnits.has(unit.unit_number)" @click.stop>
                <el-select
                  v-model="unit.speaker_name"
                  filterable
                  allow-create
                  default-first-option
                  clearable
                  placeholder="选择或输入说话人姓名"
                >
                  <el-option
                    v-for="speaker in registeredSpeakers"
                    :key="speaker.speaker_id"
                    :label="speaker.speaker_name"
                    :value="speaker.speaker_name"
                  />
                </el-select>
                <div class="unit-hint">
                  {{ registeredSpeakers.length > 0 ? '可直接选择已注册参会人，也可输入新名称' : '暂无已注册参会人，可直接输入姓名' }}
                </div>
                <div class="unit-actions">
                  <el-button type="success" size="small" @click="saveUnit(unit, unit.speaker_name)">保存</el-button>
                  <el-button type="danger" size="small" @click="cancelEdit(unit.unit_number)">取消</el-button>
                </div>
              </div>
              
              <div v-else class="speaker-display" :class="{ empty: !unit.speaker_name || unit.speaker_name === unit.channel_name }">
                {{ (!unit.speaker_name || unit.speaker_name === unit.channel_name) ? '点击设置说话人' : unit.speaker_name }}
              </div>
            </div>
          </div>
        </div>

        <!-- 其他 -->
        <div v-if="groupedUnits['其他']?.length > 0" class="model-section">
          <div class="model-header">
            <span class="model-badge">其他</span>
            <span class="model-title">未知型号</span>
          </div>
          <div class="units-grid">
            <div 
              v-for="unit in groupedUnits['其他']" 
              :key="unit.unit_number"
              class="unit-card"
              :class="{ editing: editingUnits.has(unit.unit_number) }"
              @click="toggleEdit(unit.unit_number)"
            >
              <div class="unit-header">
                <span class="unit-number">单元 {{ unit.unit_number }}</span>
                <span class="unit-hex">{{ unit.unit_hex }}</span>
              </div>
              <div class="channel-info">{{ unit.channel_name }}</div>
              
              <div v-if="editingUnits.has(unit.unit_number)" @click.stop>
                <el-select
                  v-model="unit.speaker_name"
                  filterable
                  allow-create
                  default-first-option
                  clearable
                  placeholder="选择或输入说话人姓名"
                >
                  <el-option
                    v-for="speaker in registeredSpeakers"
                    :key="speaker.speaker_id"
                    :label="speaker.speaker_name"
                    :value="speaker.speaker_name"
                  />
                </el-select>
                <div class="unit-hint">
                  {{ registeredSpeakers.length > 0 ? '可直接选择已注册参会人，也可输入新名称' : '暂无已注册参会人，可直接输入姓名' }}
                </div>
                <div class="unit-actions">
                  <el-button type="success" size="small" @click="saveUnit(unit, unit.speaker_name)">保存</el-button>
                  <el-button type="danger" size="small" @click="cancelEdit(unit.unit_number)">取消</el-button>
                </div>
              </div>
              
              <div v-else class="speaker-display" :class="{ empty: !unit.speaker_name || unit.speaker_name === unit.channel_name }">
                {{ (!unit.speaker_name || unit.speaker_name === unit.channel_name) ? '点击设置说话人' : unit.speaker_name }}
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <div class="stats">
      <div class="stat-item">
        <div class="stat-value">{{ stats.total }}</div>
        <div class="stat-label">总单元数</div>
      </div>
      <div class="stat-item">
        <div class="stat-value">{{ stats.bound }}</div>
        <div class="stat-label">已绑定</div>
      </div>
      <div class="stat-item">
        <div class="stat-value">{{ stats.model1 }}</div>
        <div class="stat-label">型号1</div>
      </div>
      <div class="stat-item">
        <div class="stat-value">{{ stats.model2 }}</div>
        <div class="stat-label">型号2</div>
      </div>
    </div>
  </div>
</template>

<style lang="scss" scoped>
.serial-port-container {
  min-height: 100vh;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  padding: 20px;
}

.header {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
  padding: 30px;
  border-radius: 12px 12px 0 0;
  margin-bottom: 0;
  position: relative;
  
  .header-content {
    max-width: 1400px;
    margin: 0 auto;
    text-align: center;
  }
  
  .back-btn {
    position: absolute;
    left: 30px;
    top: 30px;
    background: rgba(255, 255, 255, 0.2);
    border: none;
    color: white;
    
    &:hover {
      background: rgba(255, 255, 255, 0.3);
    }
  }
  
  h1 {
    font-size: 28px;
    margin-bottom: 10px;
  }
  
  p {
    font-size: 14px;
    opacity: 0.9;
  }
}

.mode-selector {
  background: #f8f9fa;
  padding: 20px 30px;
  border-bottom: 2px solid #e9ecef;
  display: flex;
  align-items: center;
  justify-content: space-between;
  max-width: 1400px;
  margin: 0 auto;
  
  label {
    font-weight: 600;
    color: #495057;
    margin-right: 15px;
  }
  
  .mode-buttons {
    display: flex;
    gap: 10px;
  }
}

.toolbar {
  padding: 20px 30px;
  background: #f8f9fa;
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 15px;
  max-width: 1400px;
  margin: 0 auto;
  
  .search-box {
    flex: 1;
    min-width: 200px;
    max-width: 400px;
  }
  
  .toolbar-buttons {
    display: flex;
    gap: 10px;
  }
}

.content {
  padding: 30px;
  background: white;
  max-width: 1400px;
  margin: 0 auto;
  min-height: 400px;
}

.empty-state {
  text-align: center;
  padding: 60px 20px;
  color: #6c757d;
  
  .empty-state-icon {
    font-size: 64px;
    margin-bottom: 20px;
    opacity: 0.3;
  }
  
  .empty-state-text {
    font-size: 18px;
    margin-bottom: 10px;
  }
  
  .empty-state-hint {
    font-size: 14px;
    color: #adb5bd;
  }
}

.model-section {
  margin-bottom: 40px;
  
  .model-header {
    display: flex;
    align-items: center;
    margin-bottom: 20px;
    padding-bottom: 10px;
    border-bottom: 3px solid #667eea;
    
    .model-badge {
      background: #667eea;
      color: white;
      padding: 5px 15px;
      border-radius: 20px;
      font-size: 14px;
      font-weight: 600;
      margin-right: 15px;
    }
    
    .model-title {
      font-size: 20px;
      font-weight: 600;
      color: #212529;
    }
  }
}

.units-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 15px;
}

.unit-card {
  :deep(.el-select) {
    width: 100%;
  }

  background: white;
  border: 2px solid #e9ecef;
  border-radius: 8px;
  padding: 15px;
  transition: all 0.3s;
  cursor: pointer;
  
  &:hover {
    border-color: #667eea;
    box-shadow: 0 4px 12px rgba(102, 126, 234, 0.15);
    transform: translateY(-2px);
  }
  
  &.editing {
    border-color: #28a745;
    background: #f8fff9;
  }
  
  .unit-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 10px;
    
    .unit-number {
      font-size: 18px;
      font-weight: 700;
      color: #667eea;
    }
    
    .unit-hex {
      font-size: 12px;
      color: #6c757d;
      background: #f8f9fa;
      padding: 2px 8px;
      border-radius: 4px;
      font-family: 'Courier New', monospace;
    }
  }
  
  .channel-info {
    font-size: 14px;
    color: #6c757d;
    margin-bottom: 10px;
  }
  
  .speaker-display {
    font-size: 16px;
    color: #212529;
    font-weight: 500;
    padding: 8px 12px;
    background: #f8f9fa;
    border-radius: 6px;
    min-height: 40px;
    display: flex;
    align-items: center;
    
    &.empty {
      color: #adb5bd;
      font-style: italic;
    }
  }
  
  .unit-actions {
    display: flex;
    gap: 5px;
    margin-top: 10px;
  }

  .unit-hint {
    margin-top: 8px;
    font-size: 12px;
    color: #6c757d;
    line-height: 1.4;
  }
}

.stats {
  background: #f8f9fa;
  padding: 20px 30px;
  border-top: 2px solid #e9ecef;
  display: flex;
  justify-content: space-around;
  flex-wrap: wrap;
  gap: 20px;
  max-width: 1400px;
  margin: 0 auto;
  border-radius: 0 0 12px 12px;
  
  .stat-item {
    text-align: center;
    
    .stat-value {
      font-size: 32px;
      font-weight: 700;
      color: #667eea;
    }
    
    .stat-label {
      font-size: 14px;
      color: #6c757d;
      margin-top: 5px;
    }
  }
}
</style>
