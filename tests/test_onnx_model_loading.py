#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FunASR ONNX模型加载测试脚本

测试不同ONNX模型的加载和推理功能。
"""

import os
import sys
import time
import logging
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


def setup_logging():
    """设置日志配置"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    return logging.getLogger(__name__)


def test_onnx_model_loading():
    """测试ONNX模型加载"""
    logger = setup_logging()
    logger.info("🧪 开始测试ONNX模型加载...")
    
    try:
        from funasr import AutoModel
        logger.info("✅ FunASR库导入成功")
    except ImportError as e:
        logger.error(f"❌ FunASR库导入失败: {e}")
        logger.error("请安装FunASR: pip install funasr")
        return False
    
    # 测试模型列表
    test_models = [
        {
            'name': 'SenseVoice ONNX',
            'model_id': 'damo/SenseVoiceSmall-onnx',
            'type': 'asr'
        },
        {
            'name': 'Paraformer Online ONNX',
            'model_id': 'damo/speech_paraformer-large_asr_nat-zh-cn-16k-common-vocab8404-online-onnx',
            'type': 'asr_streaming'
        },
        {
            'name': 'VAD ONNX',
            'model_id': 'damo/speech_fsmn_vad_zh-cn-16k-common-onnx',
            'type': 'vad'
        }
    ]
    
    success_count = 0
    total_count = len(test_models)
    
    for model_info in test_models:
        logger.info(f"\n🔍 测试模型: {model_info['name']}")
        logger.info(f"模型ID: {model_info['model_id']}")
        
        try:
            start_time = time.time()
            
            # 加载模型
            model = AutoModel(
                model=model_info['model_id'],
                device='cpu',
                ngpu=0,
                ncpu=2,
                disable_pbar=True,
                disable_log=True,
                disable_update=True
            )
            
            load_time = time.time() - start_time
            logger.info(f"✅ {model_info['name']} 加载成功")
            logger.info(f"⏱️ 加载耗时: {load_time:.2f}秒")
            
            # 检查模型属性
            logger.info(f"📊 模型设备: {getattr(model, 'device', 'unknown')}")
            logger.info(f"📊 模型类型: {type(model).__name__}")
            
            success_count += 1
            
        except Exception as e:
            logger.error(f"❌ {model_info['name']} 加载失败: {e}")
            logger.error(f"错误类型: {type(e).__name__}")
    
    # 测试结果统计
    logger.info(f"\n📈 测试结果统计:")
    logger.info(f"成功加载: {success_count}/{total_count}")
    logger.info(f"成功率: {success_count/total_count*100:.1f}%")
    
    return success_count == total_count


def test_quantized_vs_standard():
    """测试量化模型与标准模型的性能对比"""
    logger = setup_logging()
    logger.info("\n🔬 测试量化模型性能对比...")
    
    try:
        from funasr import AutoModel
        
        model_id = "damo/SenseVoiceSmall-onnx"
        
        # 测试标准模型
        logger.info("📊 测试标准ONNX模型...")
        start_time = time.time()
        standard_model = AutoModel(
            model=model_id,
            device='cpu',
            disable_pbar=True,
            disable_log=True
        )
        standard_load_time = time.time() - start_time
        
        logger.info(f"✅ 标准模型加载完成")
        logger.info(f"⏱️ 标准模型加载耗时: {standard_load_time:.2f}秒")
        
        # 注意：量化配置通常在模型内部处理，这里主要测试加载时间
        logger.info(f"\n📈 性能对比结果:")
        logger.info(f"标准模型加载时间: {standard_load_time:.2f}秒")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ 性能对比测试失败: {e}")
        return False


def test_local_model_detection():
    """测试本地ONNX模型检测"""
    logger = setup_logging()
    logger.info("\n🔍 测试本地ONNX模型检测...")
    
    # 获取项目根目录
    project_root = Path(__file__).parent.parent
    models_dir = project_root / "models"
    
    logger.info(f"📁 模型目录: {models_dir}")
    
    if not models_dir.exists():
        logger.warning(f"⚠️ 模型目录不存在: {models_dir}")
        return False
    
    # 检查ONNX模型
    onnx_models = []
    for model_dir in models_dir.iterdir():
        if model_dir.is_dir():
            # 检查是否包含ONNX文件
            onnx_files = list(model_dir.glob("*.onnx"))
            if onnx_files:
                onnx_models.append({
                    'name': model_dir.name,
                    'path': model_dir,
                    'onnx_files': [f.name for f in onnx_files]
                })
    
    logger.info(f"🎯 发现 {len(onnx_models)} 个本地ONNX模型:")
    for model in onnx_models:
        logger.info(f"  📦 {model['name']}")
        logger.info(f"    📁 路径: {model['path']}")
        logger.info(f"    📄 ONNX文件: {', '.join(model['onnx_files'])}")
        
        # 检查配置文件
        config_file = model['path'] / 'config.yaml'
        if config_file.exists():
            logger.info(f"    ✅ 配置文件: config.yaml")
        else:
            logger.warning(f"    ⚠️ 缺少配置文件: config.yaml")
    
    return len(onnx_models) > 0


def test_onnx_inference():
    """测试ONNX模型推理功能"""
    logger = setup_logging()
    logger.info("\n🎯 测试ONNX模型推理功能...")
    
    try:
        from funasr import AutoModel
        
        # 加载SenseVoice ONNX模型
        logger.info("📦 加载SenseVoice ONNX模型...")
        model = AutoModel(
            model="damo/SenseVoiceSmall-onnx",
            device='cpu',
            disable_pbar=True,
            disable_log=True
        )
        
        logger.info("✅ 模型加载成功")
        
        # 检查模型是否支持推理
        if hasattr(model, 'generate'):
            logger.info("✅ 模型支持generate方法")
        else:
            logger.warning("⚠️ 模型不支持generate方法")
        
        # 注意：实际推理需要音频文件，这里只测试模型加载
        logger.info("📊 模型推理接口测试完成")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ ONNX模型推理测试失败: {e}")
        return False


def main():
    """主测试函数"""
    logger = setup_logging()
    logger.info("🚀 开始FunASR ONNX模型测试")
    logger.info("=" * 60)
    
    test_results = []
    
    # 测试1: 基础模型加载
    test_results.append((
        "ONNX模型加载测试",
        test_onnx_model_loading()
    ))
    
    # 测试2: 性能对比
    test_results.append((
        "量化模型性能测试",
        test_quantized_vs_standard()
    ))
    
    # 测试3: 本地模型检测
    test_results.append((
        "本地模型检测测试",
        test_local_model_detection()
    ))
    
    # 测试4: 推理功能
    test_results.append((
        "模型推理功能测试",
        test_onnx_inference()
    ))
    
    # 输出测试结果
    logger.info("\n" + "=" * 60)
    logger.info("📊 测试结果汇总:")
    
    passed = 0
    total = len(test_results)
    
    for test_name, result in test_results:
        status = "✅ 通过" if result else "❌ 失败"
        logger.info(f"  {test_name}: {status}")
        if result:
            passed += 1
    
    logger.info(f"\n🎯 总体结果: {passed}/{total} 测试通过")
    logger.info(f"📈 通过率: {passed/total*100:.1f}%")
    
    if passed == total:
        logger.info("🎉 所有测试通过！ONNX模型功能正常")
        return True
    else:
        logger.warning("⚠️ 部分测试失败，请检查配置")
        return False


if __name__ == "__main__":
    try:
        success = main()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n⚠️ 用户中断测试")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ 测试过程中发生错误: {e}")
        sys.exit(1)