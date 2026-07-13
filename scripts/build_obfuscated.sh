#!/bin/bash

# 完整的混淆构建脚本
# 支持前端Vue.js和后端Python的完整混淆构建

set -e

echo "=== WYL ASR 混淆构建脚本 ==="
echo "开始混淆构建..."

# 项目根目录
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

echo "项目根目录: $PROJECT_ROOT"

# 检查必要的工具
check_dependencies() {
    echo "检查构建依赖..."
    
    # 检查Node.js和npm
    if ! command -v node &> /dev/null; then
        echo "错误: 未找到 Node.js，请先安装 Node.js"
        exit 1
    fi
    
    if ! command -v npm &> /dev/null; then
        echo "错误: 未找到 npm，请先安装 npm"
        exit 1
    fi
    
    # 检查Python
    if ! command -v python3 &> /dev/null; then
        echo "错误: 未找到 python3，请先安装 Python 3"
        exit 1
    fi
    
    # 检查PyArmor
    if ! python3 -c "import pyarmor" 2>/dev/null; then
        echo "警告: PyArmor未安装，将自动安装..."
        python3 -m pip install pyarmor
    fi
    
    echo "依赖检查完成"
}

# 清理之前的构建
clean_build() {
    echo "清理之前的构建..."
    if [ -d "dist" ]; then
        rm -rf dist/
    fi
    mkdir -p dist/
    echo "清理完成"
}

# 构建前端
build_frontend() {
    echo "=== 构建前端 ==="
    cd ui/
    
    # 检查package.json是否存在
    if [ ! -f "package.json" ]; then
        echo "错误: 未找到 package.json"
        exit 1
    fi
    
    # 安装依赖（如果需要）
    if [ ! -d "node_modules" ]; then
        echo "安装前端依赖..."
        npm install
    else
        echo "前端依赖已存在，跳过安装"
    fi
    
    # 构建生产版本
    echo "构建混淆后的前端..."
    npm run build
    
    if [ ! -d "dist" ]; then
        echo "错误: 前端构建失败，未生成 dist 目录"
        exit 1
    fi
    
    echo "前端构建完成"
    
    # 返回项目根目录
    cd "$PROJECT_ROOT"
}

# 混淆Python代码
obfuscate_python() {
    echo "=== 混淆Python代码 ==="
    
    if [ ! -f "scripts/obfuscate_python.py" ]; then
        echo "错误: 未找到混淆脚本 scripts/obfuscate_python.py"
        exit 1
    fi
    
    python3 scripts/obfuscate_python.py
    
    if [ ! -d "dist/obfuscated" ]; then
        echo "错误: Python代码混淆失败"
        exit 1
    fi
    
    echo "Python代码混淆完成"
}

# 混淆关键模块
obfuscate_modules() {
    echo "=== 混淆关键模块 ==="
    
    if [ ! -f "scripts/obfuscate_modules.py" ]; then
        echo "警告: 未找到模块混淆脚本，跳过模块混淆"
        return
    fi
    
    python3 scripts/obfuscate_modules.py
    echo "关键模块混淆完成"
}

# 创建部署包
create_deployment_package() {
    echo "=== 创建部署包 ==="
    cd dist/
    
    # 创建时间戳
    TIMESTAMP=$(date +%Y%m%d_%H%M%S)
    PACKAGE_NAME="wyl_asr_obfuscated_${TIMESTAMP}"
    
    # 创建tar.gz包
    if command -v tar &> /dev/null; then
        echo "创建 tar.gz 部署包..."
        tar -czf "${PACKAGE_NAME}.tar.gz" obfuscated/
        echo "部署包创建完成: dist/${PACKAGE_NAME}.tar.gz"
    fi
    
    # 创建zip包（如果有zip命令）
    if command -v zip &> /dev/null; then
        echo "创建 zip 部署包..."
        zip -r "${PACKAGE_NAME}.zip" obfuscated/
        echo "部署包创建完成: dist/${PACKAGE_NAME}.zip"
    fi
    
    cd "$PROJECT_ROOT"
}

# 验证构建结果
verify_build() {
    echo "=== 验证构建结果 ==="
    
    OBFUSCATED_DIR="dist/obfuscated"
    
    # 检查主要文件
    if [ ! -f "$OBFUSCATED_DIR/main.py" ]; then
        echo "错误: 未找到混淆后的 main.py"
        exit 1
    fi
    
    # 检查前端文件
    if [ ! -d "$OBFUSCATED_DIR/ui/dist" ]; then
        echo "警告: 未找到前端构建文件"
    fi
    
    # 检查启动脚本
    if [ ! -f "$OBFUSCATED_DIR/start.sh" ]; then
        echo "警告: 未找到启动脚本"
    fi
    
    echo "构建结果验证完成"
}

# 显示构建信息
show_build_info() {
    echo ""
    echo "=== 构建完成 ==="
    echo "混淆代码位置: dist/obfuscated/"
    echo "部署包位置: dist/wyl_asr_obfuscated_*.tar.gz"
    echo ""
    echo "使用方法:"
    echo "1. 解压部署包到目标服务器"
    echo "2. cd dist/obfuscated/"
    echo "3. ./start.sh 或 python3 main.py"
    echo ""
    echo "注意事项:"
    echo "- 混淆后的代码无法直接修改"
    echo "- 请保留原始源码用于开发和调试"
    echo "- 建议在测试环境充分验证后再部署到生产环境"
    echo ""
}

# 主函数
main() {
    echo "开始时间: $(date)"
    
    check_dependencies
    clean_build
    build_frontend
    obfuscate_python
    obfuscate_modules
    create_deployment_package
    verify_build
    show_build_info
    
    echo "结束时间: $(date)"
    echo "混淆构建完成！"
}

# 错误处理
trap 'echo "构建过程中发生错误，退出码: $?"; exit 1' ERR

# 执行主函数
main "$@"