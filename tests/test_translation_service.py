#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
翻译服务测试模块
================

测试基于ModelScope的中英翻译功能。
"""

import asyncio
import sys
import os
import logging

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.modules.translation_service import TranslationService, get_translation_service, initialize_translation_service


def setup_logging():
    """设置日志配置"""
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )


def test_translation_service_initialization():
    """测试翻译服务初始化"""
    print("\n=== 测试翻译服务初始化 ===")
    
    service = TranslationService()
    print(f"初始化前状态: {service.get_status()}")
    
    success = service.initialize()
    print(f"初始化结果: {success}")
    print(f"初始化后状态: {service.get_status()}")
    
    return service if success else None


async def test_single_translation(service):
    """测试单个文本翻译"""
    print("\n=== 测试单个文本翻译 ===")
    
    test_texts = [
        "你好，世界！",
        "今天天气很好。",
        "我正在学习人工智能。",
        "这是一个语音识别系统。",
        "欢迎使用我们的服务。",
        "",  # 空文本测试
        "   ",  # 空白文本测试
    ]
    
    for text in test_texts:
        print(f"\n原文: '{text}'")
        translation = await service.translate(text)
        print(f"译文: '{translation}'")


async def test_batch_translation(service):
    """测试批量翻译"""
    print("\n=== 测试批量翻译 ===")
    
    test_texts = [
        "你好，世界！",
        "今天天气很好。",
        "我正在学习人工智能。",
        "这是一个语音识别系统。",
        "欢迎使用我们的服务。"
    ]
    
    print("批量翻译输入:")
    for i, text in enumerate(test_texts, 1):
        print(f"  {i}. {text}")
    
    translations = await service.translate_batch(test_texts)
    
    print("\n批量翻译结果:")
    for i, (original, translation) in enumerate(zip(test_texts, translations), 1):
        print(f"  {i}. '{original}' -> '{translation}'")


async def test_global_service():
    """测试全局翻译服务"""
    print("\n=== 测试全局翻译服务 ===")
    
    # 初始化全局服务
    success = initialize_translation_service()
    print(f"全局服务初始化结果: {success}")
    
    if success:
        # 获取全局服务实例
        service = get_translation_service()
        print(f"全局服务状态: {service.get_status()}")
        
        # 测试翻译
        test_text = "这是全局服务测试。"
        translation = await service.translate(test_text)
        print(f"全局服务翻译: '{test_text}' -> '{translation}'")


def test_error_handling():
    """测试错误处理"""
    print("\n=== 测试错误处理 ===")
    
    # 测试未初始化的服务
    service = TranslationService()
    print(f"未初始化服务状态: {service.get_status()}")
    
    # 尝试同步翻译（应该返回None）
    result = service._translate_sync("测试文本")
    print(f"未初始化服务翻译结果: {result}")


async def test_websocket_integration():
    """测试WebSocket集成场景"""
    print("\n=== 测试WebSocket集成场景 ===")
    
    # 模拟WebSocket对象
    class MockWebSocket:
        def __init__(self):
            self.enable_translation = True
    
    websocket = MockWebSocket()
    
    # 初始化翻译服务
    service = get_translation_service()
    if not service.is_initialized:
        service.initialize()
    
    # 模拟ASR结果
    asr_results = [
        "你好，欢迎使用语音识别系统。",
        "请问有什么可以帮助您的吗？",
        "系统正在处理您的请求。"
    ]
    
    print("模拟ASR结果处理:")
    for result in asr_results:
        print(f"\nASR结果: '{result}'")
        
        # 模拟翻译处理
        if getattr(websocket, 'enable_translation', False):
            translation = await service.translate(result)
            if translation:
                print(f"翻译结果: '{translation}'")
                
                # 模拟消息数据构建
                message_data = {
                    "mode": "2pass-offline",
                    "text": result,
                    "translation": translation,
                    "wav_name": "test.wav",
                    "is_final": True
                }
                print(f"消息数据: {message_data}")


async def main():
    """主测试函数"""
    setup_logging()
    
    print("开始翻译服务测试...")
    
    # 测试服务初始化
    service = test_translation_service_initialization()
    
    if service:
        # 测试翻译功能
        await test_single_translation(service)
        await test_batch_translation(service)
        
        # 关闭服务
        service.shutdown()
    
    # 测试全局服务
    await test_global_service()
    
    # 测试错误处理
    test_error_handling()
    
    # 测试WebSocket集成
    await test_websocket_integration()
    
    print("\n=== 翻译服务测试完成 ===")


if __name__ == "__main__":
    asyncio.run(main())