#!/usr/bin/env python3
"""
LLM Agent Trading Arena 服务器启动脚本
自动初始化数据加载器并启动FastAPI服务器
"""

import os
import sys
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))


def init_data_loader():
    """初始化数据加载器"""
    try:
        from server_platform.app.core.data_loader import init_data_loader
        from config import DATA_DIRS

        # 数据目录路径
        price_data_dir = DATA_DIRS["PRICE_DATA"]
        news_data_dir = DATA_DIRS["NEWS_DATA"]

        print("初始化数据加载器...")
        print(f"价格数据目录: {price_data_dir}")
        print(f"新闻数据目录: {news_data_dir}")

        # 检查目录是否存在
        if not price_data_dir.exists():
            print(f"警告: 价格数据目录不存在: {price_data_dir}")
        if not news_data_dir.exists():
            print(f"警告: 新闻数据目录不存在: {news_data_dir}")

        # 初始化数据加载器
        data_loader = init_data_loader(str(price_data_dir), str(news_data_dir))
        print("数据加载器初始化完成!")

        # 测试数据加载
        print("\n测试数据加载...")

        # 测试交易日列表
        trading_dates = data_loader.get_trading_dates(20250101, 20250110)
        print(f"找到 {len(trading_dates)} 个交易日")

        # 测试价格数据
        test_funds = ["000300.SH"]
        test_date = 20250102

        market_data = data_loader.get_price_data(test_funds, test_date)
        print(f"测试市场数据 ({test_date}):")
        for fund, data in market_data.items():
            print(f"  {fund}: {data}")

        # 测试新闻数据
        news_data = data_loader.get_news(
            sources=["caixin"],
            current_date=20250630,
            top_rank=5,
            pre_k_days=1,
        )
        print(f"找到 {len(news_data)} 条新闻")

        return True

    except Exception as e:
        print(f"数据加载器初始化失败: {e}")
        import traceback

        traceback.print_exc()
        return False


def start_server():
    """启动FastAPI服务器"""
    try:
        import uvicorn

        print("\n" + "=" * 50)
        print("🚀 启动 LLM Agent Trading Arena 服务器")
        print("=" * 50)

        from config import SERVER_PLATFORM

        # 服务器配置
        host = SERVER_PLATFORM["HOST"]
        port = SERVER_PLATFORM["PORT"]
        reload = SERVER_PLATFORM["RELOAD"]

        print(f"服务器地址: http://{host}:{port}")
        print(f"API文档: http://{host}:{port}/docs")
        print(f"前端界面: http://{host}:{port}/")
        print("=" * 50)

        from server_platform.logging_config import LOGGING_CONFIG
        # 启动服务器
        uvicorn.run("server_platform.app.main:app", host=host, port=port, reload=reload, log_config=LOGGING_CONFIG)

    except Exception as e:
        print(f"服务器启动失败: {e}")
        import traceback

        traceback.print_exc()


def main():
    """主函数"""
    print("LLM Agent Trading Arena 启动器")
    print("=" * 50)
    print("")
    print("注意: 数据加载将在服务器启动时自动完成（仅加载一次）")
    print("查看服务器日志可了解数据加载进度")
    print("")
    print("=" * 50)

    # 启动服务器
    start_server()


if __name__ == "__main__":
    main()
