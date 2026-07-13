import { Buffer } from 'node:buffer'
import type { IncomingMessage } from 'node:http'
import { defineConfig, type Plugin } from 'vite'
import vue from '@vitejs/plugin-vue'

function readRequestBody(req: IncomingMessage): Promise<Buffer> {
  return new Promise((resolve, reject) => {
    const chunks: Buffer[] = []

    req.on('data', (chunk: Buffer | string) => {
      chunks.push(Buffer.isBuffer(chunk) ? chunk : Buffer.from(chunk))
    })
    req.on('end', () => resolve(Buffer.concat(chunks)))
    req.on('error', reject)
  })
}

function buildProxyHeaders(req: IncomingMessage): Record<string, string> {
  const ignoredHeaders = new Set(['connection', 'host', 'origin', 'referer'])
  const headers: Record<string, string> = {}

  Object.entries(req.headers).forEach(([key, value]) => {
    if (!value || ignoredHeaders.has(key.toLowerCase())) return
    headers[key] = Array.isArray(value) ? value.join(', ') : value
  })

  return headers
}

function dynamicOllamaProxyPlugin(): Plugin {
  return {
    name: 'dynamic-ollama-proxy',
    configureServer(server) {
      server.middlewares.use(async (req, res, next) => {
        if (!req.url?.startsWith('/ollama-proxy')) {
          next()
          return
        }

        try {
          const requestUrl = new URL(req.url, 'http://localhost')
          const target = requestUrl.searchParams.get('target')

          if (!target) {
            res.statusCode = 400
            res.end('Missing Ollama proxy target')
            return
          }

          const upstreamPath = requestUrl.pathname.replace(/^\/ollama-proxy/, '') || '/api/chat'
          const upstreamUrl = `${target}${upstreamPath}`
          const body = req.method === 'GET' || req.method === 'HEAD'
            ? undefined
            : await readRequestBody(req)

          console.log('Proxying dynamic Ollama request to:', upstreamUrl)

          const response = await fetch(upstreamUrl, {
            method: req.method,
            headers: buildProxyHeaders(req),
            body: body as any
          })
          const responseBody = Buffer.from(await response.arrayBuffer())

          res.statusCode = response.status
          response.headers.forEach((value, key) => {
            if (key === 'content-encoding' || key === 'content-length') return
            res.setHeader(key, value)
          })
          res.setHeader('content-length', String(responseBody.length))
          res.end(responseBody)
        } catch (error) {
          console.log('Dynamic Ollama proxy error:', error)
          res.statusCode = 502
          res.end(`Dynamic Ollama proxy error: ${error instanceof Error ? error.message : String(error)}`)
        }
      })
    }
  }
}

// https://vite.dev/config/
export default defineConfig({
  plugins: [vue(), dynamicOllamaProxyPlugin()],
  server: {
    proxy: {
      // 代理Ollama API请求到localhost
      '/ollama-api': {
        target: 'http://localhost:11434',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/ollama-api/, '/api'),
        configure: (proxy, _options) => {
          proxy.on('error', (err, _req, _res) => {
            console.log('Ollama proxy error:', err)
          })
          proxy.on('proxyReq', (proxyReq, _req, _res) => {
            console.log('Proxying request to:', proxyReq.getHeader('host') + proxyReq.path)
          })
        }
      },
      // 代理到其他IP地址的Ollama服务
      '/ollama-remote': {
        target: process.env.VITE_OLLAMA_HOST || 'http://10.1.0.27:11434',
        changeOrigin: true,
        secure: false, // 允许自签名证书
        rewrite: (path) => path.replace(/^\/ollama-remote/, '/api'),
        configure: (proxy, _options) => {
          proxy.on('error', (err, _req, _res) => {
            console.log('Remote Ollama proxy error:', err)
          })
          proxy.on('proxyReq', (proxyReq, _req, _res) => {
            console.log('Proxying remote request to:', proxyReq.getHeader('host') + proxyReq.path)
          })
        }
      }
    }
  }
})
