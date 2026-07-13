#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""FunASR WebSocket实时语音识别服务器。

这是一个基于WebSocket的实时语音识别服务器，提供以下核心功能：
1. 实时语音活动检测 (VAD)
2. 在线流式语音识别 (Online ASR)
3. 离线高精度语音识别 (Offline ASR)
4. 标点符号恢复 (Punctuation Restoration)
5. 双通道模式支持 (2pass模式：在线+离线)

支持的音频格式：16kHz, 16bit, PCM
网络协议：WebSocket with binary subprotocol
并发支持：当前版本仅支持单客户端连接

作者：ZST团队
版本：v1.0.0
许可：MIT License
"""

import asyncio
import os
import sys
import json
import tracemalloc
import threading
from typing import Optional

import websockets

# 导入核心模块
from src.modules.core.core import (
    setup_logging,
    load_models
)
from src.modules.config.arg_parser import parse_arguments
from src.modules.core.server_state import ServerState
from src.modules.network.websocket_service import ws_serve
from src.modules.config.ssl_config import setup_ssl_context
from src.modules.network.websocket_manager import clear_websocket
from src.modules.audio.audio_format_handler import init_audio_format_handler
from src.modules.speaker.speaker_labeling import init_speaker_labeler

# 导入API模块
from src.modules.database.database_api import create_app

# 导入串口模块
from src.modules.serial import init_serial_manager, shutdown_serial_manager

# 导入讯飞翻译模块（可选）
try:
    from src.modules.network.xfyun_translation import init_xfyun_translation
except ModuleNotFoundError:
    init_xfyun_translation = None


def list_available_serial_ports(logger) -> None:
    """列出所有可用的串口"""
    try:
        import serial.tools.list_ports
        
        logger.info("=" * 60)
        ports = list(serial.tools.list_ports.comports())
        
        if not ports:
            logger.warning("❌ 未找到任何串口设备")
            logger.info("")
            logger.info("💡 可能的原因:")
            logger.info("   1. 串口设备未连接")
            logger.info("   2. 驱动程序未安装")
            logger.info("   3. 设备未被系统识别")
            logger.info("")
            logger.info("=" * 60)
            return
        
        logger.info(f"✅ 找到 {len(ports)} 个串口设备:")
        logger.info("")
        
        available_ports = []
        
        for i, port in enumerate(ports, 1):
            logger.info(f"【串口 {i}】")
            logger.info(f"   端口号: {port.device}")
            logger.info(f"   描述: {port.description}")
            logger.info(f"   硬件ID: {port.hwid}")
            
            # 测试串口是否可用
            try:
                import serial
                test_serial = serial.Serial(port.device, 9600, timeout=0.5)
                test_serial.close()
                logger.info(f"   状态: ✅ 可用")
                available_ports.append(port.device)
            except serial.SerialException as e:
                error_msg = str(e).lower()
                if "access is denied" in error_msg or "permission denied" in error_msg:
                    logger.info(f"   状态: 🚫 拒绝访问（可能被其他程序占用）")
                elif "could not open port" in error_msg:
                    logger.info(f"   状态: ❌ 无法打开")
                else:
                    logger.info(f"   状态: ⚠️ 错误")
            except Exception:
                logger.info(f"   状态: ❌ 异常")
            
            logger.info("")
        
        logger.info("=" * 60)
        logger.info("📋 推荐配置")
        logger.info("=" * 60)
        logger.info("")
        
        if available_ports:
            recommended_port = available_ports[0]
            logger.info(f"✅ 推荐使用串口: {recommended_port}")
            logger.info("")
            logger.info("🚀 启动命令:")
            logger.info(f"   python main.py --serial_port {recommended_port}")
            logger.info("")
            
            if len(available_ports) > 1:
                logger.info("📝 其他可用串口:")
                for port in available_ports[1:]:
                    logger.info(f"   python main.py --serial_port {port}")
                logger.info("")
        else:
            logger.warning("⚠️ 没有可用的串口")
            logger.info("")
            logger.info("💡 建议:")
            logger.info("   1. 检查串口设备是否已连接")
            logger.info("   2. 关闭所有占用串口的程序")
            logger.info("   3. 重新插拔串口设备")
            logger.info("   4. 检查设备驱动是否正常")
            logger.info("")
            logger.info("🔧 如果不需要串口功能，可以禁用:")
            logger.info("   python main.py --disable_serial")
            logger.info("")
        
        logger.info("=" * 60)
        
    except ImportError:
        logger.error("❌ 错误: 未安装 pyserial 库")
        logger.info("💡 请运行: pip install pyserial")
    except Exception as e:
        logger.error(f"❌ 列出串口时出错: {e}")


async def main() -> None:
    """应用程序主入口点。

    执行流程：
    1. 初始化日志系统
    2. 解析命令行参数
    3. 加载AI模型
    4. 配置SSL (如果需要)
    5. 启动WebSocket服务器
    6. 运行事件循环

    Raises:
        SystemExit: 当初始化失败时退出程序
    """
    # 启用内存跟踪 (用于调试内存泄漏)
    tracemalloc.start()
    
    # 1. 初始化日志系统
    logger = setup_logging()
    logger.info("🚀 FunASR WebSocket实时语音识别服务器启动中...")
    
    try:
        # 2. 解析命令行参数
        args = parse_arguments()
        
        # 如果只是列出串口，则执行后退出
        if getattr(args, 'list_serial_ports', False):
            logger.info("🔍 列出所有可用串口...")
            list_available_serial_ports(logger)
            return
        
        logger.info("✅ 命令行参数解析完成")
        logger.info(f"🌐 服务器配置: {args.host}:{args.port}")
        logger.info(f"🖥️ 计算设备: {args.device} (GPU数量: {args.ngpu}, CPU核心: {args.ncpu})")
        logger.info(f"🤖 模型类型: {args.model_type} ({args.asr_model})")
        if args.model_type == "sensevoice":
            logger.info("🎯 SenseVoiceSmall模型支持: 语种检测、情感识别、事件检测")
        
        # 完整Pipeline模式配置信息
        if hasattr(args, 'enable_2pass') and args.enable_2pass:
            logger.info("🔄 启用完整Pipeline模式: 实现C++服务器处理流程")
            logger.info("📋 处理流程: 音频输入 → VAD检测 → 在线ASR(实时) → 离线ASR(精确) → 说话人识别/分离 → 热词增强 → 标点恢复 → 输出")
            logger.info(f"🌊 在线模型: {args.asr_model_online}")
            logger.info(f"🎯 离线模型: {args.asr_model}")
            if hasattr(args, 'lm_dir') and args.lm_dir:
                logger.info(f"🔤 语言模型: {args.lm_dir}")

            if hasattr(args, 'hotword') and args.hotword:
                logger.info(f"📝 热词文件: {args.hotword}")
                logger.info(f"⚖️ 热词权重: {getattr(args, 'fst_inc_wts', 20)}")
        
        # 解码参数信息
        if hasattr(args, 'global_beam'):
            logger.info(f"🎚️ 解码参数: beam={args.global_beam}, lattice_beam={getattr(args, 'lattice_beam', 3.0)}, am_scale={getattr(args, 'am_scale', 10.0)}")
        
        # 线程配置信息
        if hasattr(args, 'decoder_thread_num'):
            logger.info(f"🧵 线程配置: IO={getattr(args, 'io_thread_num', 2)}, 解码器={args.decoder_thread_num}, 模型={getattr(args, 'model_thread_num', 1)}")
        
        # 3. 初始化服务器状态
        server_state = ServerState()
        server_state.args = args
        server_state.logger = logger
        
        # 4. 加载AI模型
        load_models(server_state)
        
        # 5. 初始化音频格式处理器
        logger.info("\n🎵 初始化音频格式处理器...")
        init_audio_format_handler()
        logger.info("✅ 音频格式处理器初始化完成")
        
        # 6. 初始化说话人标记器
        logger.info("\n🏷️ 初始化说话人标记器...")
        init_speaker_labeler(
            similarity_threshold=args.speaker_labeling_similarity_threshold,
            consistency_threshold=args.speaker_labeling_consistency_threshold
        )
        logger.info(f"✅ 说话人标记器初始化完成 (相似度阈值: {args.speaker_labeling_similarity_threshold}, 一致性阈值: {args.speaker_labeling_consistency_threshold}（用于模式匹配）)")

        # 7. 初始化讯飞翻译服务
        logger.info("\n🌐 初始化讯飞翻译服务...")
        try:
            if init_xfyun_translation is None:
                logger.warning("⚠️ 讯飞翻译模块不可用，跳过讯飞翻译初始化")
            else:
                config_path = os.path.join(os.path.dirname(__file__), 'config', 'xfyun_config.json')
                if not os.path.exists(config_path):
                    logger.warning("⚠️ 未找到讯飞配置文件，翻译功能将使用模拟模式")
                else:
                    with open(config_path, 'r', encoding='utf-8') as f:
                        xfyun_config = json.load(f)
                    init_xfyun_translation(
                        xfyun_config['app_id'],
                        xfyun_config['api_key'],
                        xfyun_config['api_secret']
                    )
                    logger.info("✅ 讯飞翻译服务初始化完成")
        except Exception as e:
            logger.warning(f"⚠️ 讯飞翻译初始化失败: {e}，将使用模拟翻译")

        # 8. 初始化串口接收器（如果启用）
        logger.info("\n" + "="*60)
        logger.info("📡 检查串口配置...")
        
        # 检查配置文件
        import yaml
        from pathlib import Path
        serial_config_file = Path(args.serial_config)
        config_enabled = False
        
        if serial_config_file.exists():
            try:
                with open(serial_config_file, 'r', encoding='utf-8') as f:
                    serial_config = yaml.safe_load(f)
                    config_enabled = serial_config.get('serial', {}).get('enabled', False)
                    logger.info(f"📝 配置文件: {args.serial_config}")
                    logger.info(f"🔘 配置文件中的启用状态: {config_enabled}")
            except Exception as e:
                logger.warning(f"⚠️ 读取配置文件失败: {e}")
        else:
            logger.warning(f"⚠️ 配置文件不存在: {args.serial_config}")
        
        logger.info(f"🔘 串口功能状态: {'启用' if args.enable_serial else '禁用'}")
        
        if args.enable_serial:
            logger.info("✅ 串口功能已启用（默认）")
            logger.info("📡 初始化串口接收器...")
            serial_manager = init_serial_manager(
                config_path=args.serial_config,
                port=args.serial_port,
                baudrate=args.serial_baudrate,
                logger=logger
            )
            if serial_manager:
                logger.info(f"✅ 串口接收器初始化完成: {args.serial_port} @ {args.serial_baudrate}bps")
                # 可以在这里注册回调函数来处理串口数据
                # serial_manager.register_callback(your_callback_function)
            else:
                logger.warning("⚠️ 串口接收器初始化失败，继续运行...")
                logger.info("💡 如果不需要串口功能，可以使用 --disable_serial 参数禁用")
                logger.info(f"💡 如果需要更改串口号，可以使用 --serial_port <串口号> 参数")
        else:
            logger.info("ℹ️ 串口功能已被禁用 (--disable_serial)")
            if config_enabled:
                logger.warning("⚠️ 注意：配置文件中已启用串口，但被命令行参数禁用")
        
        logger.info("="*60 + "\n")
        
        # 9. 配置SSL
        ssl_context = setup_ssl_context(args, logger)
        
        # 10. 创建WebSocket服务器
        logger.info("🎧 正在启动WebSocket服务器...")
        
        # 创建服务器处理函数的包装器
        async def server_handler(websocket):
            # 在新版本的websockets中，path可以通过websocket.path获取
            path = getattr(websocket, 'path', '/')
            await ws_serve(websocket, path, server_state)
        
        # 启动WebSocket服务器
        if ssl_context:
            server = await websockets.serve(
                server_handler,
                args.host,
                args.port,
                subprotocols=["binary"],  # 支持binary子协议
                ping_interval=None,       # 禁用ping/pong机制
                ssl=ssl_context
            )
            protocol = "wss"
        else:
            server = await websockets.serve(
                server_handler,
                args.host,
                args.port,
                subprotocols=["binary"],  # 支持binary子协议
                ping_interval=None
            )
            protocol = "ws"
        
        # 11. 启动API服务器
        def start_api_server():
            """在单独线程中启动API服务器"""
            try:
                api_app = create_app(server_state=server_state)
                api_port = args.api_port  # 从命令行参数获取API端口
                
                # 根据SSL配置决定协议
                api_protocol = "https" if ssl_context else "http"
                logger.info(f"🌐 启动数据库API服务器: {api_protocol}://{args.host}:{api_port}")
                
                # 如果有SSL配置，使用SSL上下文启动
                if ssl_context:
                    api_app.run(
                        host=args.host,
                        port=api_port,
                        debug=False,
                        use_reloader=False,
                        threaded=True,
                        ssl_context=ssl_context
                    )
                else:
                    api_app.run(
                        host=args.host,
                        port=api_port,
                        debug=False,
                        use_reloader=False,
                        threaded=True
                    )
            except Exception as e:
                logger.error(f"❌ API服务器启动失败: {e}")
        
        # 在后台线程启动API服务器
        api_thread = threading.Thread(target=start_api_server, daemon=True)
        api_thread.start()
        logger.info("🔗 API服务器已在后台启动")
        
        # 12. 启动服务并运行
        logger.info(f"🎉 服务器启动成功!")
        logger.info(f"📡 WebSocket地址: {protocol}://{args.host}:{args.port}")
        api_port = args.api_port
        api_protocol = "https" if ssl_context else "http"
        logger.info(f"🌐 API接口地址: {api_protocol}://{args.host}:{api_port}")
        logger.info(f"🔍 健康检查: {api_protocol}://{args.host}:{api_port}/api/health")
        
        # 识别模式说明
        logger.info(f"🎯 支持的识别模式:")
        logger.info(f"   • online: 在线流式识别 (低延迟)")
        logger.info(f"   • offline: 离线高精度识别 (高准确率)")
        logger.info(f"   • pipeline: 完整处理流程 (C++服务器兼容模式)")
        logger.info(f"   • 2pass: 双通道识别 (实时反馈+高精度结果)")
        
        # Pipeline模式特别说明
        if hasattr(args, 'enable_2pass') and args.enable_2pass:
            logger.info(f"🔄 完整Pipeline模式已启用，完全兼容FunASR C++服务器:")
            logger.info(f"   • 步骤1: VAD语音活动检测")
            logger.info(f"   • 步骤2: 在线ASR实时识别 (低延迟反馈)")
            logger.info(f"   • 步骤3: 离线ASR高精度识别 (最终结果)")
            logger.info(f"   • 步骤4: 说话人识别/分离处理")
            logger.info(f"   • 步骤5: 热词增强处理")
            logger.info(f"   • 步骤6: ITN逆文本标准化")
            logger.info(f"   • 步骤7: 标点符号恢复")
            logger.info(f"   • 步骤8: 最终结果输出")
            logger.info(f"   • 🎯 已完成")
        
        logger.info(f"📊 音频格式: 16kHz, 16bit, PCM")
        logger.info("⚡ 服务器已就绪，等待客户端连接...")
        
        # 保持事件循环运行
        await asyncio.Future()  # 永远不会完成的Future，保持服务器运行
        
    except KeyboardInterrupt:
        logger.info("⚠️ 收到中断信号，正在关闭服务器...")
        
        # 清理所有连接
        if 'server_state' in locals():
            await clear_websocket(server_state)
        
        # 关闭串口接收器
        shutdown_serial_manager()
        
        logger.info("👋 服务器已安全关闭")
        
    except OSError as e:
        if e.errno == 48:  # Address already in use
            logger.error(f"❌ 端口 {args.port} 已被占用")
            logger.info("💡 解决方案:")
            logger.info(f"   1. 检查占用进程: lsof -i :{args.port}")
            logger.info(f"   2. 停止占用进程: kill -9 <PID>")
            logger.info(f"   3. 或使用其他端口: --port <新端口号>")
            
            # 自动尝试查找可用端口
            for port in range(args.port + 1, args.port + 10):
                try:
                    import socket
                    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                        s.bind((args.host, port))
                        logger.info(f"✅ 发现可用端口: {port}")
                        logger.info(f"   重新启动命令: python main.py --port {port}")
                        break
                except OSError:
                    continue
            else:
                logger.warning("🔍 未找到附近的可用端口")
        else:
            logger.error(f"❌ 网络错误: {e}")
            logger.error("错误详情:", exc_info=True)
        
    except Exception as e:
        logger.error(f"❌ 服务器启动失败: {e}")
        logger.error("错误详情:", exc_info=True)
        sys.exit(1)


def main_entry() -> None:
    """程序入口点函数。
    
    使用asyncio运行主函数，确保所有异步操作正确执行。
    """
    try:
        # Python 3.7+ 推荐的异步程序启动方式
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n🛑 程序被用户中断")
    except Exception as e:
        print(f"❌ 程序异常退出: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main_entry()
