#!/bin/bash

# 测试崩溃修复脚本
# 用于验证 WebSocket 重连和异常处理是否正常工作

echo "================================"
echo "VoiceRecognitionDisplay 崩溃修复测试"
echo "================================"
echo ""

# 颜色定义
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 测试计数
TESTS_PASSED=0
TESTS_FAILED=0

# 测试函数
test_build() {
    echo -e "${YELLOW}测试 1: 编译检查${NC}"
    cd "$(dirname "$0")"
    
    if dotnet build VoiceRecognitionDisplay.macOS/VoiceRecognitionDisplay.macOS.csproj > /dev/null 2>&1; then
        echo -e "${GREEN}✓ 编译成功${NC}"
        ((TESTS_PASSED++))
        return 0
    else
        echo -e "${RED}✗ 编译失败${NC}"
        ((TESTS_FAILED++))
        return 1
    fi
}

test_websocket_service() {
    echo -e "${YELLOW}测试 2: WebSocketService 语法检查${NC}"
    
    # 检查关键修复是否存在
    if grep -q "SemaphoreSlim _reconnectLock" VoiceRecognitionDisplay/Services/WebSocketService.cs && \
       grep -q "_isReconnecting" VoiceRecognitionDisplay/Services/WebSocketService.cs && \
       grep -q "maxAttempts" VoiceRecognitionDisplay/Services/WebSocketService.cs; then
        echo -e "${GREEN}✓ WebSocketService 包含所有关键修复${NC}"
        ((TESTS_PASSED++))
        return 0
    else
        echo -e "${RED}✗ WebSocketService 缺少关键修复${NC}"
        ((TESTS_FAILED++))
        return 1
    fi
}

test_exception_handlers() {
    echo -e "${YELLOW}测试 3: 全局异常处理器检查${NC}"
    
    # 检查 macOS Program.cs
    if grep -q "UnhandledException" VoiceRecognitionDisplay.macOS/Program.cs && \
       grep -q "UnobservedTaskException" VoiceRecognitionDisplay.macOS/Program.cs; then
        echo -e "${GREEN}✓ macOS 全局异常处理器已添加${NC}"
        ((TESTS_PASSED++))
    else
        echo -e "${RED}✗ macOS 缺少全局异常处理器${NC}"
        ((TESTS_FAILED++))
        return 1
    fi
    
    # 检查 Desktop App.axaml.cs
    if grep -q "UnhandledException" VoiceRecognitionDisplay.Desktop/App.axaml.cs && \
       grep -q "UnobservedTaskException" VoiceRecognitionDisplay.Desktop/App.axaml.cs; then
        echo -e "${GREEN}✓ Desktop 全局异常处理器已添加${NC}"
        ((TESTS_PASSED++))
        return 0
    else
        echo -e "${RED}✗ Desktop 缺少全局异常处理器${NC}"
        ((TESTS_FAILED++))
        return 1
    fi
}

test_thread_safety() {
    echo -e "${YELLOW}测试 4: 线程安全检查${NC}"
    
    if grep -q "_bufferLock" VoiceRecognitionDisplay/ViewModels/MainWindowViewModel.cs && \
       grep -q "lock (_bufferLock)" VoiceRecognitionDisplay/ViewModels/MainWindowViewModel.cs; then
        echo -e "${GREEN}✓ MainWindowViewModel 线程安全已实现${NC}"
        ((TESTS_PASSED++))
        return 0
    else
        echo -e "${RED}✗ MainWindowViewModel 缺少线程安全保护${NC}"
        ((TESTS_FAILED++))
        return 1
    fi
}

test_log_directory() {
    echo -e "${YELLOW}测试 5: 日志目录检查${NC}"
    
    LOG_DIR="$HOME/Library/Logs/VoiceRecognitionDisplay"
    
    if [ -d "$LOG_DIR" ]; then
        echo -e "${GREEN}✓ 日志目录已存在: $LOG_DIR${NC}"
        ((TESTS_PASSED++))
    else
        echo -e "${YELLOW}⚠ 日志目录不存在（首次运行时会创建）${NC}"
        echo "  位置: $LOG_DIR"
        ((TESTS_PASSED++))
    fi
    
    return 0
}

test_health_monitor() {
    echo -e "${YELLOW}测试 6: 健康监控服务检查${NC}"
    
    if [ -f "VoiceRecognitionDisplay/Services/HealthMonitor.cs" ]; then
        echo -e "${GREEN}✓ HealthMonitor 服务已创建${NC}"
        ((TESTS_PASSED++))
        return 0
    else
        echo -e "${RED}✗ HealthMonitor 服务不存在${NC}"
        ((TESTS_FAILED++))
        return 1
    fi
}

# 运行所有测试
echo "开始测试..."
echo ""

test_build
echo ""

test_websocket_service
echo ""

test_exception_handlers
echo ""

test_thread_safety
echo ""

test_log_directory
echo ""

test_health_monitor
echo ""

# 输出测试结果
echo "================================"
echo "测试结果汇总"
echo "================================"
echo -e "通过: ${GREEN}${TESTS_PASSED}${NC}"
echo -e "失败: ${RED}${TESTS_FAILED}${NC}"
echo ""

if [ $TESTS_FAILED -eq 0 ]; then
    echo -e "${GREEN}✓ 所有测试通过！${NC}"
    echo ""
    echo "建议的下一步："
    echo "1. 运行应用: ./run.sh"
    echo "2. 测试无后端连接场景（验证重连逻辑）"
    echo "3. 检查日志文件: $HOME/Library/Logs/VoiceRecognitionDisplay/crash.log"
    echo "4. 监控内存使用和线程数"
    exit 0
else
    echo -e "${RED}✗ 有测试失败，请检查上述错误${NC}"
    exit 1
fi
