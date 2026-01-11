import webbrowser
import http.server
import socketserver
import os
import sys
import json
import shutil  # 新增：用于复制文件
from pathlib import Path
import threading
import time
from typing import Dict, Any

# =============================================================================
# 1. 路径与配置 (Path Configuration)
# =============================================================================

# 脚本位置
CURRENT_SCRIPT = Path(__file__).resolve()
PROJECT_ROOT = CURRENT_SCRIPT.parents[2] # 指向 DoubanV2 根目录

RESOURCES_DIR = PROJECT_ROOT / "resources"
CONFIG_PATH = RESOURCES_DIR / "config.json"

# --- 动态加载用户名 ---

def load_initial_config(config_path: Path) -> Dict[str, Any]:
    """读取配置文件以获取用户名"""
    if not config_path.exists():
        print(f"❌ 配置文件未找到: {config_path}")
        sys.exit(1)
    try:
        with config_path.open('r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"❌ 读取配置失败: {e}")
        sys.exit(1)

# 立即加载配置
GLOBAL_CONFIG = load_initial_config(CONFIG_PATH)
USERNAME = GLOBAL_CONFIG.get('douban_username')

if not USERNAME:
    print("❌ 配置错误: 'douban_username' 不能为空")
    sys.exit(1)

# --- 路径构建 ---

# 1. JS 文件路径配置
GLOBAL_UI_DIR = RESOURCES_DIR / "ui_resources"
USER_DATA_DIR = RESOURCES_DIR / "UserData" / USERNAME
USER_UI_DIR = USER_DATA_DIR / "ui_resources"

SOURCE_JS_PATH = GLOBAL_UI_DIR / "report_render.js"
TARGET_JS_PATH = USER_UI_DIR / "report_render.js"

# 2. 目标 HTML 文件的相对路径 (用于 URL)
# 路径结构: resources/UserData/{username}/ui_resources/report_with_data.html
TARGET_HTML_REL_PATH = f"resources/UserData/{USERNAME}/ui_resources/report_with_data.html"

# 目标文件的绝对路径 (用于检查文件是否存在)
TARGET_FILE_FULL_PATH = PROJECT_ROOT / TARGET_HTML_REL_PATH

# 服务器配置
PORT = 8000
HOST = "localhost"
# 完整的访问 URL
URL = f"http://{HOST}:{PORT}/{TARGET_HTML_REL_PATH}"
# =============================================================================
# 2. 核心功能函数
# =============================================================================

def copy_render_js():
    """
    在启动前将 report_render.js 从全局资源目录复制到用户目录，
    确保 HTML 能正确加载脚本。
    """
    print(f"📋 正在检查必要的 JS 资源...")
    
    if not SOURCE_JS_PATH.exists():
        print(f"❌ 错误: 源 JS 文件不存在: {SOURCE_JS_PATH}")
        return

    # 确保目标目录存在
    if not USER_UI_DIR.exists():
        try:
            USER_UI_DIR.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            print(f"❌ 创建用户目录失败: {e}")
            return

    try:
        print(f"   源文件: {SOURCE_JS_PATH.name}")
        print(f"   目标地: {USER_UI_DIR}")
        shutil.copy2(SOURCE_JS_PATH, TARGET_JS_PATH)
        print(f"✅ JS 文件复制成功！")
    except Exception as e:
        print(f"❌ JS 文件复制失败: {e}")


def start_server():
    """启动本地 HTTP 服务器"""
    # 关键步骤：切换工作目录到项目根目录
    try:
        os.chdir(PROJECT_ROOT)
        print(f"📂 服务器根目录已设置为: {PROJECT_ROOT}")
    except FileNotFoundError:
        print(f"❌ 错误: 无法找到项目根目录 {PROJECT_ROOT}")
        sys.exit(1)

    Handler = http.server.SimpleHTTPRequestHandler
    
    # 允许地址重用
    socketserver.TCPServer.allow_reuse_address = True

    try:
        with socketserver.TCPServer(("", PORT), Handler) as httpd:
            print("-" * 50)
            print(f"🚀 本地服务器已启动 (用户: {USERNAME})")
            print(f"📡 监听端口: {PORT}")
            print(f"🌐 访问地址: {URL}")
            print("-" * 50)
            httpd.serve_forever()
    except OSError as e:
        print(f"❌ 端口 {PORT} 被占用或无法绑定: {e}")
        print("   请尝试关闭占用该端口的程序，或在脚本中修改 PORT 变量。")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\n🛑 服务器已停止")

def open_browser():
    """延迟打开浏览器"""
    time.sleep(1.5)
    print(f"🌍 正在打开默认浏览器...")
    try:
        webbrowser.open(URL)
    except Exception as e:
        print(f"⚠️ 无法自动打开浏览器: {e}")
        print(f"👉 请手动复制地址访问: {URL}")

# =============================================================================
# 3. 主执行逻辑
# =============================================================================

if __name__ == "__main__":
    print(f"👤 当前用户: {USERNAME}")
    
    # 1. 执行资源复制 (新增步骤)
    copy_render_js()

    # 2. 检查目标 HTML 是否存在
    if not TARGET_FILE_FULL_PATH.exists():
        print(f"⚠️ 警告: 目标 HTML 文件不存在")
        print(f"   路径: {TARGET_FILE_FULL_PATH}")
        print("   请先运行生成报告的脚本 (UI_generate.py)")
    
    # 3. 启动浏览器线程
    browser_thread = threading.Thread(target=open_browser)
    browser_thread.daemon = True 
    browser_thread.start()

    # 4. 启动服务器 (主线程阻塞在此)
    start_server()