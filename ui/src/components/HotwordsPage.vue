<template>
  <div class="hotwords-page">
    <header class="hotwords-header">
      <div class="header-controls">
        <el-button type="info" @click="goBack" class="back-button">
          <el-icon><ArrowLeft /></el-icon>
          返回
        </el-button>
        <div class="header-actions">
          <el-button type="success" @click="saveHotwords" :loading="isSaving">
            <el-icon><DocumentAdd /></el-icon>
            保存资产
          </el-button>
          <el-button type="primary" @click="loadHotwords" :loading="isLoading">
            <el-icon><Refresh /></el-icon>
            刷新
          </el-button>
        </div>
      </div>
      <h1>热词资产</h1>
      <p>维护语音识别热词、权重、分类和保护状态，并同步导出给识别服务使用。</p>
    </header>

    <section class="asset-summary">
      <div class="summary-item">
        <span class="summary-label">热词总数</span>
        <strong>{{ hotwords.length }}</strong>
      </div>
      <div class="summary-item">
        <span class="summary-label">受保护</span>
        <strong>{{ protectedCount }}</strong>
      </div>
      <div class="summary-item">
        <span class="summary-label">分类</span>
        <strong>{{ categoryOptions.length }}</strong>
      </div>
      <div class="summary-item">
        <span class="summary-label">当前筛选</span>
        <strong>{{ filteredHotwords.length }}</strong>
      </div>
    </section>

    <el-card class="hotwords-card">
      <template #header>
        <div class="card-header">
          <span>热词治理</span>
          <el-tag type="info" effect="plain">权重越高，识别越偏向该词</el-tag>
        </div>
      </template>

      <div class="add-hotword-section">
        <el-form
          :model="newHotword"
          :rules="hotwordRules"
          ref="newHotwordForm"
          inline
          class="add-form"
        >
          <el-form-item label="热词" prop="word">
            <el-input
              v-model="newHotword.word"
              placeholder="请输入热词"
              class="word-input"
              @keyup.enter="addHotword"
            />
          </el-form-item>
          <el-form-item label="权重" prop="weight">
            <el-input-number v-model="newHotword.weight" :min="1" :max="100" class="weight-input" />
          </el-form-item>
          <el-form-item label="分类" prop="category">
            <el-input v-model="newHotword.category" placeholder="通用" class="category-input" />
          </el-form-item>
          <el-form-item label="保护">
            <el-switch v-model="newHotword.protected" />
          </el-form-item>
          <el-form-item>
            <el-button type="primary" @click="addHotword" :loading="isAdding">
              <el-icon><Plus /></el-icon>
              添加
            </el-button>
          </el-form-item>
        </el-form>
      </div>

      <div class="filter-bar">
        <el-input
          v-model="filters.keyword"
          placeholder="搜索热词或描述"
          clearable
          class="filter-search"
        >
          <template #prefix>
            <el-icon><Search /></el-icon>
          </template>
        </el-input>
        <el-select v-model="filters.category" placeholder="全部分类" clearable class="filter-select">
          <el-option
            v-for="category in categoryOptions"
            :key="category"
            :label="category"
            :value="category"
          />
        </el-select>
        <el-select v-model="filters.source" placeholder="全部来源" clearable class="filter-select">
          <el-option
            v-for="source in sourceOptions"
            :key="source"
            :label="source"
            :value="source"
          />
        </el-select>
        <el-select v-model="filters.protection" placeholder="保护状态" class="filter-select">
          <el-option label="全部状态" value="all" />
          <el-option label="仅受保护" value="protected" />
          <el-option label="未保护" value="unprotected" />
        </el-select>
        <div class="weight-filter">
          <el-input-number v-model="filters.minWeight" :min="1" :max="100" placeholder="最低" controls-position="right" />
          <span>至</span>
          <el-input-number v-model="filters.maxWeight" :min="1" :max="100" placeholder="最高" controls-position="right" />
        </div>
        <el-button @click="resetFilters">重置筛选</el-button>
      </div>

      <div class="hotwords-list">
        <el-table
          :data="filteredHotwords"
          row-key="id"
          style="width: 100%"
          :loading="isLoading"
          empty-text="暂无热词数据"
        >
          <el-table-column prop="word" label="热词" min-width="220">
            <template #default="scope">
              <el-input
                v-if="scope.row.editing"
                v-model="scope.row.word"
                size="small"
                @keyup.enter="saveEdit(scope.row)"
              />
              <span v-else class="word-cell">{{ scope.row.word }}</span>
            </template>
          </el-table-column>

          <el-table-column prop="category" label="分类" width="150">
            <template #default="scope">
              <el-input
                v-if="scope.row.editing"
                v-model="scope.row.category"
                size="small"
                placeholder="通用"
                @keyup.enter="saveEdit(scope.row)"
              />
              <el-tag v-else effect="plain">{{ scope.row.category || '通用' }}</el-tag>
            </template>
          </el-table-column>

          <el-table-column prop="weight" label="权重" width="120">
            <template #default="scope">
              <el-input-number
                v-if="scope.row.editing"
                v-model="scope.row.weight"
                :min="1"
                :max="100"
                size="small"
                controls-position="right"
                @keyup.enter="saveEdit(scope.row)"
              />
              <el-tag v-else :type="getWeightType(scope.row.weight)">
                {{ scope.row.weight }}
              </el-tag>
            </template>
          </el-table-column>

          <el-table-column prop="source" label="来源" width="130">
            <template #default="scope">
              <el-tag type="info" effect="plain">{{ scope.row.source || '手动' }}</el-tag>
            </template>
          </el-table-column>

          <el-table-column label="保护" width="120">
            <template #default="scope">
              <el-switch
                v-model="scope.row.protected"
                inline-prompt
                active-text="锁定"
                inactive-text="开放"
              />
            </template>
          </el-table-column>

          <el-table-column prop="updated_at" label="更新时间" width="180">
            <template #default="scope">
              <span class="muted-text">{{ formatDateTime(scope.row.updated_at) }}</span>
            </template>
          </el-table-column>

          <el-table-column label="操作" width="210" fixed="right">
            <template #default="scope">
              <el-button-group v-if="!scope.row.editing">
                <el-button size="small" type="primary" @click="editHotword(scope.row)">
                  <el-icon><Edit /></el-icon>
                  编辑
                </el-button>
                <el-button
                  size="small"
                  type="danger"
                  :disabled="scope.row.protected"
                  @click="deleteHotword(scope.row)"
                >
                  <el-icon><Delete /></el-icon>
                  删除
                </el-button>
              </el-button-group>

              <el-button-group v-else>
                <el-button size="small" type="success" @click="saveEdit(scope.row)">
                  <el-icon><Check /></el-icon>
                  保存
                </el-button>
                <el-button size="small" type="info" @click="cancelEdit(scope.row)">
                  <el-icon><Close /></el-icon>
                  取消
                </el-button>
              </el-button-group>
            </template>
          </el-table-column>
        </el-table>
      </div>

      <div class="batch-operations" v-if="hotwords.length > 0">
        <el-divider content-position="left">批量操作</el-divider>
        <div class="batch-row">
          <el-button type="warning" @click="clearUnprotectedHotwords">
            <el-icon><Unlock /></el-icon>
            清空未保护热词
          </el-button>
          <el-button type="info" @click="exportHotwords('txt')">
            <el-icon><Download /></el-icon>
            导出 TXT
          </el-button>
          <el-button type="info" @click="exportHotwords('json')">
            <el-icon><Download /></el-icon>
            导出资产 JSON
          </el-button>
          <el-select v-model="importOptions.mode" class="import-mode">
            <el-option label="合并导入" value="merge" />
            <el-option label="仅追加新词" value="append" />
            <el-option label="替换未保护词" value="replace" />
          </el-select>
          <el-input v-model="importOptions.category" placeholder="导入分类" class="import-category" />
          <el-upload :show-file-list="false" :before-upload="importHotwords" accept=".txt,.csv,.json">
            <el-button type="success" :loading="isImporting">
              <el-icon><Upload /></el-icon>
              导入文件
            </el-button>
          </el-upload>
        </div>
      </div>

      <div class="preset-hotwords">
        <el-divider content-position="left">预设热词</el-divider>
        <div class="preset-tags">
          <el-tag
            v-for="preset in presetHotwords"
            :key="preset.word"
            class="preset-tag"
            effect="plain"
            @click="addPresetHotword(preset)"
          >
            {{ preset.word }} ({{ preset.weight }})
          </el-tag>
        </div>
      </div>
    </el-card>

    <el-card class="file-info-card">
      <template #header>
        <span>文件信息</span>
      </template>
      <el-descriptions :column="1" border>
        <el-descriptions-item label="资产文件">
          <el-text type="info">{{ assetFilePath }}</el-text>
        </el-descriptions-item>
        <el-descriptions-item label="识别导出">
          <el-text type="info">{{ hotwordsFilePath }}</el-text>
        </el-descriptions-item>
        <el-descriptions-item label="最后加载">
          <el-text type="info">{{ lastUpdateTime || '未知' }}</el-text>
        </el-descriptions-item>
      </el-descriptions>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, reactive, onMounted, nextTick } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import type { FormInstance, FormRules } from 'element-plus'
import {
  ArrowLeft,
  DocumentAdd,
  Refresh,
  Plus,
  Edit,
  Delete,
  Check,
  Close,
  Download,
  Upload,
  Unlock,
  Search
} from '@element-plus/icons-vue'
import { SERVER_CONFIG } from '../config/api'

interface HotwordAsset {
  id: number
  word: string
  weight: number
  category: string
  source: string
  protected: boolean
  description?: string
  created_at?: string
  updated_at?: string
  editing?: boolean
  original?: HotwordAsset
}

const router = useRouter()
const newHotwordForm = ref<FormInstance>()

const hotwords = ref<HotwordAsset[]>([])
const newHotword = reactive({
  word: '',
  weight: 90,
  category: '通用',
  protected: false
})

const filters = reactive({
  keyword: '',
  category: '',
  source: '',
  protection: 'all',
  minWeight: undefined as number | undefined,
  maxWeight: undefined as number | undefined
})

const importOptions = reactive({
  mode: 'merge',
  category: '导入',
  source: '导入'
})

const isLoading = ref(false)
const isSaving = ref(false)
const isAdding = ref(false)
const isImporting = ref(false)
const lastUpdateTime = ref('')
const hotwordsFilePath = 'data/hotwords.txt'
const assetFilePath = 'data/hotwords_assets.json'

const presetHotwords = [
  { word: '真视通', weight: 90, category: '品牌' },
  { word: '数字科技', weight: 90, category: '品牌' },
  { word: '紫荆视通', weight: 90, category: '品牌' },
  { word: '紫荆', weight: 90, category: '品牌' },
  { word: '玲珑AI', weight: 90, category: '产品' },
  { word: '玲珑', weight: 90, category: '产品' },
  { word: '博数', weight: 90, category: '品牌' },
  { word: '博数智源', weight: 90, category: '品牌' },
  { word: '视频会议', weight: 90, category: '业务' },
  { word: '音视频', weight: 90, category: '业务' },
  { word: '无纸化', weight: 90, category: '业务' },
  { word: 'AV', weight: 90, category: '业务' },
  { word: 'AI', weight: 90, category: '技术' },
  { word: '无纸化系统', weight: 90, category: '业务' }
]

const hotwordRules: FormRules = {
  word: [
    { required: true, message: '请输入热词', trigger: 'blur' },
    { min: 1, max: 50, message: '热词长度应在1-50个字符之间', trigger: 'blur' }
  ],
  weight: [
    { required: true, message: '请输入权重', trigger: 'blur' },
    { type: 'number', min: 1, max: 100, message: '权重应在1-100之间', trigger: 'blur' }
  ],
  category: [
    { min: 1, max: 30, message: '分类长度应在1-30个字符之间', trigger: 'blur' }
  ]
}

const protectedCount = computed(() => hotwords.value.filter(item => item.protected).length)
const categoryOptions = computed(() => uniqueValues(hotwords.value.map(item => item.category || '通用')))
const sourceOptions = computed(() => uniqueValues(hotwords.value.map(item => item.source || '手动')))
const filteredHotwords = computed(() => {
  const keyword = filters.keyword.trim().toLowerCase()
  return hotwords.value.filter(item => {
    if (keyword) {
      const content = `${item.word} ${item.description || ''}`.toLowerCase()
      if (!content.includes(keyword)) return false
    }
    if (filters.category && item.category !== filters.category) return false
    if (filters.source && item.source !== filters.source) return false
    if (filters.protection === 'protected' && !item.protected) return false
    if (filters.protection === 'unprotected' && item.protected) return false
    if (filters.minWeight !== undefined && item.weight < filters.minWeight) return false
    if (filters.maxWeight !== undefined && item.weight > filters.maxWeight) return false
    return true
  })
})

function uniqueValues(values: string[]) {
  return Array.from(new Set(values.filter(Boolean))).sort((a, b) => a.localeCompare(b, 'zh-CN'))
}

function normalizeHotword(item: any): HotwordAsset {
  return {
    id: Number(item.id || Date.now()),
    word: String(item.word || '').trim(),
    weight: Math.max(1, Math.min(100, Number(item.weight || 90))),
    category: String(item.category || '通用').trim() || '通用',
    source: String(item.source || '手动').trim() || '手动',
    protected: Boolean(item.protected ?? item.isProtected),
    description: item.description || '',
    created_at: item.created_at,
    updated_at: item.updated_at,
    editing: false
  }
}

const goBack = () => {
  router.back()
}

const loadHotwords = async () => {
  isLoading.value = true
  try {
    const response = await fetch(`${SERVER_CONFIG.DB_BASE_URL}/api/hotwords`)
    const data = await response.json()

    if (data.code === 200) {
      hotwords.value = (Array.isArray(data.data) ? data.data : []).map(normalizeHotword)
      lastUpdateTime.value = new Date().toLocaleString()
      ElMessage.success('热词加载成功')
    } else {
      ElMessage.error(data.message || '加载热词失败')
    }
  } catch (error) {
    ElMessage.error('网络错误，请检查服务器连接')
    console.error('加载热词失败:', error)
  } finally {
    isLoading.value = false
  }
}

const saveHotwords = async () => {
  isSaving.value = true
  try {
    const response = await fetch(`${SERVER_CONFIG.DB_BASE_URL}/api/hotwords`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        hotwords: hotwords.value.map(toPayloadHotword)
      })
    })

    const data = await response.json()

    if (data.code === 200) {
      lastUpdateTime.value = new Date().toLocaleString()
      ElMessage.success('热词资产已保存并导出')
      await loadHotwords()
    } else {
      ElMessage.error(data.message || '保存热词失败')
    }
  } catch (error) {
    ElMessage.error('网络错误，请检查服务器连接')
    console.error('保存热词失败:', error)
  } finally {
    isSaving.value = false
  }
}

function toPayloadHotword(item: HotwordAsset) {
  return {
    id: item.id,
    word: item.word,
    weight: item.weight,
    category: item.category,
    source: item.source,
    protected: item.protected,
    description: item.description || '',
    created_at: item.created_at
  }
}

const addHotword = async () => {
  if (!newHotwordForm.value) return

  try {
    await newHotwordForm.value.validate()

    const word = newHotword.word.trim()
    const exists = hotwords.value.some(item => item.word === word)
    if (exists) {
      ElMessage.warning('该热词已存在')
      return
    }

    isAdding.value = true
    const now = new Date().toISOString()
    hotwords.value.push({
      id: Date.now(),
      word,
      weight: newHotword.weight,
      category: newHotword.category.trim() || '通用',
      source: '手动',
      protected: newHotword.protected,
      created_at: now,
      updated_at: now,
      editing: false
    })

    newHotword.word = ''
    newHotword.weight = 90
    newHotword.category = '通用'
    newHotword.protected = false
    newHotwordForm.value.resetFields()

    ElMessage.success('热词添加成功')
  } catch (error) {
    console.error('添加热词失败:', error)
  } finally {
    isAdding.value = false
  }
}

const editHotword = (row: HotwordAsset) => {
  row.editing = true
  row.original = { ...row, original: undefined }

  nextTick(() => {
    const input = document.querySelector('.el-input__inner') as HTMLInputElement
    input?.focus()
  })
}

const saveEdit = (row: HotwordAsset) => {
  row.word = row.word.trim()
  row.category = row.category?.trim() || '通用'
  row.weight = Math.max(1, Math.min(100, Number(row.weight || 90)))

  if (!row.word) {
    ElMessage.warning('热词不能为空')
    return
  }

  const duplicate = hotwords.value.some(item => item.id !== row.id && item.word === row.word)
  if (duplicate) {
    ElMessage.warning('热词已存在，不能重名')
    return
  }

  row.updated_at = new Date().toISOString()
  row.editing = false
  delete row.original
  ElMessage.success('修改成功')
}

const cancelEdit = (row: HotwordAsset) => {
  if (row.original) {
    Object.assign(row, row.original)
  }
  row.editing = false
  delete row.original
}

const deleteHotword = async (row: HotwordAsset) => {
  if (row.protected) {
    ElMessage.warning('受保护热词不能删除，请先取消保护')
    return
  }

  try {
    await ElMessageBox.confirm(
      `确定要删除热词 "${row.word}" 吗？`,
      '确认删除',
      {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'warning'
      }
    )

    const index = hotwords.value.findIndex(item => item.id === row.id)
    if (index > -1) {
      hotwords.value.splice(index, 1)
      ElMessage.success('删除成功')
    }
  } catch {
    // 用户取消删除
  }
}

const clearUnprotectedHotwords = async () => {
  const unprotectedCount = hotwords.value.length - protectedCount.value
  if (unprotectedCount <= 0) {
    ElMessage.info('当前没有未保护热词')
    return
  }

  try {
    await ElMessageBox.confirm(
      `确定要清空 ${unprotectedCount} 个未保护热词吗？受保护热词会保留。`,
      '确认清空',
      {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'warning'
      }
    )

    hotwords.value = hotwords.value.filter(item => item.protected)
    ElMessage.success('已清空未保护热词')
  } catch {
    // 用户取消清空
  }
}

const exportHotwords = (format: 'txt' | 'json') => {
  const content = format === 'json'
    ? JSON.stringify({
      version: 1,
      exported_at: new Date().toISOString(),
      items: hotwords.value.map(toPayloadHotword)
    }, null, 2)
    : hotwords.value.map(item => `${item.word} ${item.weight}`).join('\n')

  const blob = new Blob([content], { type: format === 'json' ? 'application/json;charset=utf-8' : 'text/plain;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = format === 'json' ? 'hotwords_assets.json' : 'hotwords.txt'
  link.click()
  URL.revokeObjectURL(url)

  ElMessage.success(format === 'json' ? '热词资产导出成功' : '热词 TXT 导出成功')
}

const importHotwords = (file: File) => {
  isImporting.value = true
  const reader = new FileReader()
  reader.onload = async (event) => {
    try {
      const content = event.target?.result as string
      const response = await fetch(`${SERVER_CONFIG.DB_BASE_URL}/api/hotwords/import`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          content,
          mode: importOptions.mode,
          category: importOptions.category || '导入',
          source: importOptions.source || '导入',
          preserveProtected: true
        })
      })
      const data = await response.json()

      if (data.code === 200) {
        hotwords.value = (data.data.hotwords || []).map(normalizeHotword)
        lastUpdateTime.value = new Date().toLocaleString()
        const stats = data.data.stats || {}
        ElMessage.success(`导入完成：新增 ${stats.added || 0}，更新 ${stats.updated || 0}，保护跳过 ${stats.skipped_protected || 0}`)
      } else {
        ElMessage.error(data.message || '导入热词失败')
      }
    } catch (error) {
      ElMessage.error('文件导入失败')
      console.error('导入热词失败:', error)
    } finally {
      isImporting.value = false
    }
  }
  reader.onerror = () => {
    isImporting.value = false
    ElMessage.error('文件读取失败')
  }
  reader.readAsText(file)
  return false
}

const addPresetHotword = (preset: { word: string; weight: number; category: string }) => {
  const exists = hotwords.value.some(item => item.word === preset.word)
  if (exists) {
    ElMessage.warning('该热词已存在')
    return
  }

  const now = new Date().toISOString()
  hotwords.value.push({
    id: Date.now(),
    word: preset.word,
    weight: preset.weight,
    category: preset.category,
    source: '预设',
    protected: true,
    created_at: now,
    updated_at: now,
    editing: false
  })

  ElMessage.success(`已添加预设热词: ${preset.word}`)
}

const getWeightType = (weight: number) => {
  if (weight >= 90) return 'danger'
  if (weight >= 70) return 'warning'
  if (weight >= 50) return 'success'
  return 'info'
}

const formatDateTime = (value?: string) => {
  if (!value) return '-'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return '-'
  return date.toLocaleString()
}

const resetFilters = () => {
  filters.keyword = ''
  filters.category = ''
  filters.source = ''
  filters.protection = 'all'
  filters.minWeight = undefined
  filters.maxWeight = undefined
}

onMounted(() => {
  loadHotwords()
})
</script>

<style scoped>
.hotwords-page {
  padding: 20px;
  max-width: 1280px;
  margin: 0 auto;
}

.hotwords-header {
  margin-bottom: 16px;
}

.header-controls {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.header-actions {
  display: flex;
  gap: 12px;
}

.hotwords-header h1 {
  margin: 0 0 8px;
  color: #303133;
  font-size: 28px;
}

.hotwords-header p {
  margin: 0;
  color: #606266;
  font-size: 14px;
}

.asset-summary {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
  margin-bottom: 16px;
}

.summary-item {
  min-height: 76px;
  display: flex;
  flex-direction: column;
  justify-content: center;
  gap: 6px;
  padding: 14px 16px;
  border: 1px solid #e4e7ed;
  border-radius: 8px;
  background: #fff;
}

.summary-label {
  color: #606266;
  font-size: 13px;
}

.summary-item strong {
  color: #1f2d3d;
  font-size: 24px;
  line-height: 1;
}

.hotwords-card {
  margin-bottom: 20px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
}

.add-hotword-section {
  margin-bottom: 16px;
  padding: 16px;
  background-color: #f8f9fa;
  border-radius: 8px;
}

.add-form {
  display: flex;
  align-items: center;
  gap: 12px;
}

.word-input {
  width: 220px;
}

.weight-input {
  width: 128px;
}

.category-input {
  width: 140px;
}

.filter-bar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 10px;
  margin-bottom: 16px;
}

.filter-search {
  width: 240px;
}

.filter-select {
  width: 140px;
}

.weight-filter {
  display: flex;
  align-items: center;
  gap: 8px;
}

.weight-filter :deep(.el-input-number) {
  width: 104px;
}

.hotwords-list {
  margin-bottom: 18px;
}

.word-cell {
  color: #303133;
  font-weight: 600;
}

.muted-text {
  color: #909399;
  font-size: 12px;
}

.batch-operations {
  margin-bottom: 18px;
}

.batch-row {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 10px;
}

.import-mode {
  width: 140px;
}

.import-category {
  width: 120px;
}

.preset-hotwords {
  margin-bottom: 10px;
}

.preset-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.preset-tag {
  cursor: pointer;
  transition: border-color 0.2s ease, color 0.2s ease, background-color 0.2s ease;
}

.preset-tag:hover {
  color: #1677ff;
  border-color: #91caff;
  background-color: #f0f7ff;
}

.file-info-card {
  margin-bottom: 20px;
}

.back-button {
  margin-right: 12px;
}

@media (max-width: 1024px) {
  .asset-summary {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .filter-search,
  .filter-select,
  .import-mode,
  .import-category {
    width: 100%;
  }
}

@media (max-width: 768px) {
  .hotwords-page {
    padding: 12px;
  }

  .header-controls,
  .header-actions,
  .add-form,
  .batch-row {
    flex-direction: column;
    align-items: stretch;
  }

  .asset-summary {
    grid-template-columns: 1fr;
  }

  .word-input,
  .weight-input,
  .category-input {
    width: 100%;
  }

  .weight-filter {
    width: 100%;
  }

  .weight-filter :deep(.el-input-number) {
    flex: 1;
    width: auto;
  }
}
</style>
