#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
数据库API服务启动脚本

用于启动数据库API服务器，提供RESTful接口访问数据库功能。

使用方法:
    python start_api.py [--host HOST] [--port PORT] [--debug]

示例:
    python start_api.py                          # 默认配置启动
    python start_api.py --host 0.0.0.0 --port 8080  # 指定主机和端口
    python start_api.py --debug                 # 开启调试模式

作者: WYL ASR Team
版本: 1.0.0
创建时间: 2024年
"""

import argparse
import logging
import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from ..database.database_api import run_api_server


def setup_logging(debug=False):
    """设置日志配置"""
    level = logging.DEBUG if debug else logging.INFO
    
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler('api_server.log', encoding='utf-8')
        ]
    )
    
    # 设置Flask和Werkzeug日志级别
    logging.getLogger('werkzeug').setLevel(logging.WARNING)
    if not debug:
        logging.getLogger('flask').setLevel(logging.WARNING)


def parse_arguments():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(
        description='启动数据库API服务器',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  %(prog)s                                    # 使用默认配置启动
  %(prog)s --host 0.0.0.0 --port 8080        # 指定主机和端口
  %(prog)s --debug                           # 开启调试模式
  %(prog)s --host 127.0.0.1 --port 5000 --debug  # 完整配置
        """
    )
    
    parser.add_argument(
        '--host',
        type=str,
        default='127.0.0.1',
        help='服务器主机地址 (默认: 127.0.0.1)'
    )
    
    parser.add_argument(
        '--port',
        type=int,
        default=8080,
        help='服务器端口号 (默认: 8080)'
    )
    
    parser.add_argument(
        '--debug',
        action='store_true',
        help='开启调试模式'
    )
    
    parser.add_argument(
        '--db-path',
        type=str,
        default='data/wyl_asr.db',
        help='数据库文件路径 (默认: data/wyl_asr.db)'
    )
    
    return parser.parse_args()


def check_dependencies():
    """检查依赖包"""
    try:
        import flask
        import flask_cors
        import werkzeug
        print(f"✅ Flask版本: {flask.__version__}")
        print(f"✅ Flask-CORS版本: {flask_cors.__version__}")
        # 处理不同版本的Werkzeug
        try:
            print(f"✅ Werkzeug版本: {werkzeug.__version__}")
        except AttributeError:
            # 某些版本的Werkzeug可能没有__version__属性
            import pkg_resources
            try:
                version = pkg_resources.get_distribution("werkzeug").version
                print(f"✅ Werkzeug版本: {version}")
            except:
                print("✅ Werkzeug已安装")
    except ImportError as e:
        print(f"❌ 缺少依赖包: {e}")
        print("请运行: pip install -r requirements.txt")
        sys.exit(1)


def check_database():
    """检查数据库连接"""
    try:
        from ..database.database_manager import get_database_manager
        db = get_database_manager()
        info = db.get_database_info()
        print(f"✅ 数据库连接正常: {info['database_path']}")
        print(f"✅ 数据库大小: {info['database_size']} 字节")
        print(f"✅ 数据表数量: {len(info['tables'])}")
        return True
    except Exception as e:
        print(f"❌ 数据库连接失败: {e}")
        return False


def print_banner():
    """打印启动横幅"""
    banner = """
╔══════════════════════════════════════════════════════════════╗
║                    WYL ASR 数据库API服务器                    ║
║                                                              ║
║  提供完整的RESTful API接口来操作数据库功能                     ║
║  支持会议管理、音频文件、语音识别、翻译等功能                   ║
╚══════════════════════════════════════════════════════════════╝
    """
    print(banner)


def print_api_info(host, port):
    """打印API信息"""
    base_url = f"http://{host}:{port}"
    
    print("\n📋 API接口信息:")
    print(f"   基础URL: {base_url}")
    print(f"   健康检查: {base_url}/api/health")
    print(f"   数据库信息: {base_url}/api/database/info")
    
    print("\n🔗 主要接口:")
    print(f"   会议管理: {base_url}/api/meetings")
    print(f"   音频文件: {base_url}/api/meetings/{{id}}/audio-files")
    print(f"   语音识别: {base_url}/api/meetings/{{id}}/speech-results")
    print(f"   识别模式: {base_url}/api/meetings/{{id}}/recognition-modes")
    print(f"   翻译内容: {base_url}/api/meetings/{{id}}/translations")
    print(f"   说话人: {base_url}/api/speakers")
    print(f"   会议纪要: {base_url}/api/meetings/{{id}}/minutes")
    print(f"   系统配置: {base_url}/api/config")
    
    print("\n📖 API文档: docs/database_api.md")
    print("\n🧪 测试接口:")
    print(f"   curl {base_url}/api/health")
    print(f"   curl {base_url}/api/database/info")


def main():
    """主函数"""
    # 解析命令行参数
    args = parse_arguments()
    
    # 打印启动横幅
    print_banner()
    
    # 设置日志
    setup_logging(args.debug)
    logger = logging.getLogger(__name__)
    
    # 检查依赖
    print("🔍 检查系统依赖...")
    check_dependencies()
    
    # 检查数据库
    print("\n🔍 检查数据库连接...")
    if not check_database():
        print("\n❌ 数据库检查失败，请检查数据库配置")
        sys.exit(1)
    
    # 打印配置信息
    print("\n⚙️ 服务器配置:")
    print(f"   主机地址: {args.host}")
    print(f"   端口号: {args.port}")
    print(f"   调试模式: {'开启' if args.debug else '关闭'}")
    print(f"   数据库路径: {args.db_path}")
    
    # 打印API信息
    print_api_info(args.host, args.port)
    
    # 启动提示
    print("\n🚀 正在启动API服务器...")
    print("   按 Ctrl+C 停止服务器")
    print("=" * 60)
    
    try:
        # 启动API服务器
        logger.info(f"启动数据库API服务器: http://{args.host}:{args.port}")
        run_api_server(host=args.host, port=args.port, debug=args.debug)
        
    except KeyboardInterrupt:
        print("\n\n👋 服务器已停止")
        logger.info("服务器被用户停止")
        
    except Exception as e:
        print(f"\n\n💥 服务器启动失败: {e}")
        logger.error(f"服务器启动失败: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()