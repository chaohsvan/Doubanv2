#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
DoubanV2 数据处理流程主控脚本。
优化点：使用 pathlib 实现跨平台路径兼容，优化 I/O 处理。
新增功能：支持 '服务器模式' (S/s)，仅启动服务器，跳过数据处理流程。
"""

import subprocess
import sys
import time
import logging
import threading
from pathlib import Path

# --- 1. 路径设置 (Path Optimizations) ---
CURRENT_FILE = Path(__file__).resolve()
SCRIPT_DIR = CURRENT_FILE.parent
PROJECT_ROOT = SCRIPT_DIR.parent.parent

RESOURCES_DIR = PROJECT_ROOT / 'resources'
LOG_DIR = RESOURCES_DIR / 'log'

try:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
except OSError as e:
    print(f"!!! 严重错误：无法创建日志目录 {LOG_DIR}: {e}")
    sys.exit(1)

# --- 2. 日志设置 ---

def setup_logging(log_dir: Path) -> logging.Logger:
    """配置日志记录器。"""

    log_file = log_dir / 'main_pipeline.log'

    logger = logging.getLogger('PipelineRunner')
    logger.setLevel(logging.DEBUG)
    logger.propagate = False

    if logger.hasHandlers():
        logger.handlers.clear()

    file_formatter = logging.Formatter(
        '%(asctime)s - %(levelname)s - [MainScript] - %(message)s'
    )

    file_handler = logging.FileHandler(str(log_file), mode='a', encoding='utf-8')
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(file_formatter)

    console_formatter = logging.Formatter('%(message)s')
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(console_formatter)

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    return logger

logger = setup_logging(LOG_DIR)


# --- 3. 核心执行函数 ---

def run_script(script_name: str) -> bool:
    """
    在 SCRIPT_DIR 中执行一个 Python 脚本。
    """
    script_path = SCRIPT_DIR / script_name

    if not script_path.exists():
        logger.warning(f"--- [警告] 脚本未找到，跳过: {script_path.name} ---")
        return True

    logger.info(f"--- [正在启动] {script_name} ---")

    try:
        process = subprocess.run(
            [sys.executable, str(script_path)],
            cwd=str(PROJECT_ROOT),
            check=False
        )

        exit_code_msg = f"(退出码: {process.returncode})"
        logger.debug(f"子脚本 {script_name} 原始退出码: {process.returncode}")

        if process.returncode != 0:
            logger.error(f"!!! [执行失败] {script_name} {exit_code_msg}。")

            while True:
                choice = input("是否继续执行下一个脚本? (y/n): ").strip().lower()
                if choice == 'y':
                    logger.warning("...用户选择继续...")
                    return True
                elif choice == 'n':
                    logger.warning("...用户选择终止...")
                    return False
                else:
                    logger.info("无效输入，请输入 'y' (是) 或 'n' (否)。")

        logger.info(f"--- [执行完毕] {script_name} {exit_code_msg} ---")
        return True

    except KeyboardInterrupt:
        logger.warning(f"\n--- [用户中断] 手动停止了 {script_name} ---")
        return False
    except Exception as e:
        logger.critical(f"!!! [严重错误] 无法启动 {script_name}: {e}", exc_info=True)
        return False

# --- 数据处理脚本流程定义 ---
PIPELINE_FLOW = [
    "SaveMoviesPages.py",
    "Raw2BasicDB.py",
    # "KeywordMaintenance.py",
    # "ctsv_col_rm.py",
    "EnrichTmdb.py",
    "EnrichRottenTomatoes1.py",
    "EnrichRottenTomatoes2.py",
    "EnrichMetacritic.py",
    "EnrichImdb.py",
    "EnrichDoubanKeywords.py",
    "EnrichStaticDouban.py",
    "MergeEnrichedMovies.py",
    "import_csv_to_sqlite.py",
    "UI_makejson.py",
    "UI_generate.py",
]

# --- 4. 服务器启动函数 (核心新增/修改) ---

def start_server_non_blocking(script_name: str, logger: logging.Logger) -> subprocess.Popen:
    """
    非阻塞地启动一个 Python 脚本作为子进程。
    """
    script_path = SCRIPT_DIR / script_name
    
    if not script_path.exists():
        logger.warning(f"--- [警告] 服务器脚本未找到，跳过: {script_path.name} ---")
        return None

    logger.info(f"--- [正在启动服务器] {script_name} (非阻塞) ---")
    
    try:
        # 使用 Popen 启动子进程，不等待它结束
        # 注意: 如果服务器脚本内有 webBrowser.open()，它会在子进程中被执行。
        process = subprocess.Popen(
            [sys.executable, str(script_path)],
            cwd=str(PROJECT_ROOT)
        )
        logger.info(f"--- [服务器已启动] {script_name} (PID: {process.pid}) ---")
        return process
    except Exception as e:
        logger.critical(f"!!! [严重错误] 无法启动服务器 {script_name}: {e}", exc_info=True)
        return None

def run_servers(logger: logging.Logger, start_time: float):
    """
    启动所有 Web 服务器并等待用户中断。
    """
    server_processes = []
            
    # 1. 启动第一个服务器
    p1 = start_server_non_blocking("UI_showHtml.py", logger)
    if p1:
        server_processes.append(p1)

    # 2. 启动第二个服务器
    p2 = start_server_non_blocking("UI_moviedetail_server.py", logger)
    if p2:
        server_processes.append(p2)
        
    if server_processes:
        logger.info("\n" + "="*70)
        logger.info("🎬 Web 服务已在后台启动。")
        logger.info("   按下 Ctrl+C 终止所有服务并退出主程序。")
        logger.info("="*70)
        
        # 阻塞主线程，等待用户中断
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            logger.info("\n\n🛑 收到中断信号，正在关闭 Web 服务...")
            
            # 终止子进程
            for p in server_processes:
                if p.poll() is None: # 检查进程是否仍在运行
                    p.terminate()
                    logger.info(f"   已终止进程 (PID: {p.pid})")
    
    # 流程总结
    end_time = time.time()
    total_time = end_time - start_time
    logger.info("\n" + "="*70)
    logger.info(f"🏁 流程执行完毕。总耗时: {total_time:.2f} 秒。")
    logger.info("="*70)


# --- 5. 主函数 (核心修改) ---

def main():
    """
    运行整个数据处理流程
    """
    total_scripts = len(PIPELINE_FLOW)
    start_time = time.time()

    logger.info("="*70)
    logger.info(f"🚀 开始执行 DoubanV2 数据处理流程 (Pathlib Optimized)")
    logger.info(f"   项目根目录: {PROJECT_ROOT}")
    logger.info(f"   脚本目录: {SCRIPT_DIR}")
    logger.info(f"   日志文件: {LOG_DIR / 'main_pipeline.log'}")
    logger.info(f"   待执行脚本: {total_scripts}")
    logger.info("="*70)

    # 0: 服务器模式, 1: 自动模式, 2: 手动模式
    run_mode = -1 

    while run_mode == -1:
        try:
            logger.info("\n" + "-"*70)
            logger.info("   请选择运行模式:")
            logger.info("   (y) 自动模式: 自动运行所有步骤 (更新数据)")
            logger.info("   (n) 手动模式: 每步需 Enter 确认 (更新数据)")
            logger.info("   (s) 服务器模式: 仅启动 Web 服务 (观看已有报告)")

            choice = input("   请输入选择 (y/n/s) [默认为 n]: ").strip().lower()

            if choice == 'y':
                run_mode = 1
                logger.info("   [自动模式] 已启用。")
            elif choice == 'n' or choice == '':
                run_mode = 2
                logger.info("   [手动模式] 已启用。")
            elif choice == 's':
                run_mode = 0
                logger.info("   [服务器模式] 已启用。跳过数据处理流程。")
            else:
                logger.info("   无效输入。")
        except KeyboardInterrupt:
            logger.warning("\n\n🛑 流程在模式选择时被中断。")
            return

    logger.info("-" * 70)
    
    # --- 流程执行部分 ---
    if run_mode == 0:
        # 服务器模式: 跳过 PIPELINE_FLOW
        logger.info("➡️ 正在进入服务器模式...")
        run_servers(logger, start_time)
        return # 服务器模式结束

    # 数据更新模式 (run_mode 1 或 2)
    auto_mode = (run_mode == 1)
    
    try:
        for i, script_name in enumerate(PIPELINE_FLOW):
            logger.info(f"\n[流程 {i+1}/{total_scripts}]")

            if not auto_mode:
                try:
                    input(f"   即将执行: {script_name}。请按 Enter 键继续...")
                except KeyboardInterrupt:
                    logger.warning("\n\n🛑 流程在等待下一步时被中断。")
                    break
            else:
                logger.info(f"   [自动] 即将执行: {script_name}")

            continue_pipeline = run_script(script_name)

            if not continue_pipeline:
                logger.error(f"\n🛑 流程在 [Step {i+1}: {script_name}] 处终止。")
                break
            
            # 暂停 1 秒
            if i < total_scripts - 1:
                logger.info("   ⏳ 脚本执行完毕，冷却 1 秒...")
                time.sleep(1)

    except KeyboardInterrupt:
        logger.warning("\n\n🛑 流程被用户强行中断。")

    finally:
        # 数据更新流程结束后，启动服务器
        logger.info("🎬 所有数据处理流程完毕。")
        run_servers(logger, start_time)


if __name__ == "__main__":
    main()