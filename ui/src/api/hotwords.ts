import { SERVER_CONFIG } from '../config/api'

export interface HotwordAsset {
  id: number
  word: string
  weight: number
  category?: string
  source?: string
  protected?: boolean
  description?: string
  created_at?: string
  updated_at?: string
}

interface ApiResponse<T> {
  code: number
  message: string
  data: T
}

const HOTWORDS_BASE_URL = `${SERVER_CONFIG.DB_BASE_URL}/api/hotwords`

async function parseResponse<T>(response: Response): Promise<T> {
  const payload = await response.json() as ApiResponse<T>
  if (!response.ok || payload.code !== 200) {
    throw new Error(payload.message || `请求失败: ${response.status}`)
  }
  return payload.data
}

export const hotwordApi = {
  async listHotwords(params: {
    q?: string
    category?: string
    source?: string
    protected?: 'true' | 'false'
    minWeight?: number
    maxWeight?: number
  } = {}): Promise<HotwordAsset[]> {
    const search = new URLSearchParams()
    if (params.q) search.set('q', params.q)
    if (params.category) search.set('category', params.category)
    if (params.source) search.set('source', params.source)
    if (params.protected) search.set('protected', params.protected)
    if (params.minWeight !== undefined) search.set('min_weight', String(params.minWeight))
    if (params.maxWeight !== undefined) search.set('max_weight', String(params.maxWeight))

    const suffix = search.toString() ? `?${search.toString()}` : ''
    const response = await fetch(`${HOTWORDS_BASE_URL}${suffix}`)
    return parseResponse<HotwordAsset[]>(response)
  },

  toHotwordText(hotwords: HotwordAsset[]): string {
    return hotwords
      .filter(item => item.word?.trim())
      .map(item => `${item.word.trim()} ${Math.max(1, Math.min(100, Number(item.weight || 90)))}`)
      .join('\n')
  }
}
