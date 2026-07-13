// 服务器状态检测相关接口
import { getDisplayHost } from '../config/api'

// 获取保存的服务器配置
const getServerConfig = () => {
  const saved = localStorage.getItem('asr_server_settings')
  if (saved) {
    try {
      const config = JSON.parse(saved)
      return {
        host: config.host || 'localhost',
        port: config.port || 10095,
        apiPort: config.apiPort || 8080
      }
    } catch (error) {
      console.warn('Failed to parse server config:', error)
    }
  }
  // 默认配置
  return {
    host: 'localhost',
    port: 10095,
    apiPort: 8080
  }
}

// 服务器状态响应接口
export interface ServerStatusResponse {
  success: boolean
  data: {
    status: 'running' | 'stopped' | 'error'
    uptime?: number
    version?: string
    host?: string
    port?: number
    apiPort?: number
  }
  error?: string
}

// 服务器启动响应接口
export interface ServerStartResponse {
  success: boolean
  data?: {
    message: string
    pid?: number
  }
  error?: string
}

// 服务器状态API
export const serverStatusApi = {
  // 检查服务器状态 - 通过ping API端口
  checkStatus: async (): Promise<ServerStatusResponse> => {
    const config = getServerConfig()
    const controller = new AbortController()
    const timeoutId = setTimeout(() => controller.abort(), 5000)
    
    // 构建服务器地址
    const serverHost = getDisplayHost(config.host)
    const apiUrl = `http://${serverHost}:${config.apiPort}/health`
    
    try {
      // 只检测API端口
      const apiResponse = await fetch(apiUrl, {
        method: 'GET',
        headers: {
          'Content-Type': 'application/json'
        },
        signal: controller.signal
      })
      
      clearTimeout(timeoutId)
      
      if (apiResponse.ok) {
        return {
          success: true,
          data: {
            status: 'running',
            host: serverHost,
            apiPort: config.apiPort
          }
        }
      }
    } catch (apiError) {
      clearTimeout(timeoutId)
    }
    
    // 服务器无响应，返回停止状态
    return {
      success: true,
      data: {
        status: 'stopped'
      }
    }
  },

  // 启动服务器
  startServer: async (config: any): Promise<ServerStartResponse> => {
    try {
      const response = await fetch('/api/server/start', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify(config)
      })
      
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`)
      }
      
      return await response.json()
    } catch (error) {
      return {
        success: false,
        error: error instanceof Error ? error.message : '启动服务器失败'
      }
    }
  },

  // 停止服务器
  stopServer: async (): Promise<ServerStartResponse> => {
    try {
      const response = await fetch('/api/server/stop', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        }
      })
      
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`)
      }
      
      return await response.json()
    } catch (error) {
      return {
        success: false,
        error: error instanceof Error ? error.message : '停止服务器失败'
      }
    }
  }
}