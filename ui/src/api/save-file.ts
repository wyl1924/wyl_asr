import fs from 'fs'
import path from 'path'

export const saveFileHandler = async (req: any, res: any) => {
  try {
    const { content, filename, directory } = req.body
    
    // 解码base64内容
    const base64Data = content.split(',')[1]
    const fileData = Buffer.from(base64Data, 'base64')
    
    // 确保目录存在
    const fullPath = path.join(process.cwd(), directory)
    if (!fs.existsSync(fullPath)) {
      fs.mkdirSync(fullPath, { recursive: true })
    }
    
    // 保存文件
    const filePath = path.join(fullPath, filename)
    fs.writeFileSync(filePath, fileData)
    
    res.json({ success: true, path: filePath })
  } catch (error) {
    console.error('Error saving file:', error)
    res.status(500).json({ 
      success: false, 
      error: error instanceof Error ? error.message : '保存文件失败'
    })
  }
}