import sys
import json
import sqlite3
import webbrowser
import threading
import time
import os
from pathlib import Path
from flask import Flask, jsonify, send_from_directory, abort, request

# =============================================================================
# 1. 路径与配置 (Path Configuration)
# =============================================================================

# 脚本位置
CURRENT_SCRIPT = Path(__file__).resolve()
PROJECT_ROOT = CURRENT_SCRIPT.parents[2]  # 指向 DoubanV2 根目录

RESOURCES_DIR = PROJECT_ROOT / "resources"
CONFIG_PATH = RESOURCES_DIR / "config.json"

# --- 动态加载用户名 ---

def load_initial_config(config_path: Path):
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

DB_PATH = RESOURCES_DIR / "UserData" / USERNAME / "DBgenerate" / "douban_movies.db"
POSTER_DIR = RESOURCES_DIR / "tmdb_poster"
HTML_DIR = RESOURCES_DIR

# 服务器配置
PORT = 5000
URL = f"http://localhost:{PORT}"

# =============================================================================
# 2. Flask 核心逻辑 (Core Logic)
# =============================================================================

app = Flask(__name__)

def get_db_connection():
    if not DB_PATH.exists():
        return None
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row 
    return conn

# --- 路由定义 ---

@app.route('/')
def index():
    return send_from_directory(str(HTML_DIR), 'mvdetails.html')

@app.route('/tmdb_poster/<path:filename>')
def serve_poster(filename):
    file_path = POSTER_DIR / filename
    if not file_path.exists():
        return abort(404)
    return send_from_directory(str(POSTER_DIR), filename)

# --- API 接口 ---

# 1. 搜索接口 (修改版)
@app.route('/api/search')
def search_movie():
    query_str = request.args.get('q', '').strip()
    if not query_str:
        return jsonify([])

    conn = get_db_connection()
    cursor = conn.cursor()
    
    # 修改点 1: SELECT 只保留 link (用于ID) 和 title (用于显示)
    # 修改点 2: 删除了 LIMIT 10，显示所有相关结果
    # 修改点 3: 确保包含 show_genre LIKE，支持斜杠分隔的格式搜索
    sql = """
        SELECT show_douban_link, show_movid_title
        FROM show_sql_table 
        WHERE show_movid_name LIKE ? 
           OR show_movid_title LIKE ? 
           OR show_crew_director_main LIKE ?
           OR show_crew_douban_personnel LIKE ?
           OR show_release_douban_region LIKE ?
           OR show_genre LIKE ?
    """
    param = f"%{query_str}%"
    
    try:
        # 参数需要传 6 次对应 6 个 ?
        rows = cursor.execute(sql, (param, param, param, param, param, param)).fetchall()
        results = [dict(row) for row in rows]
        return jsonify(results)
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        conn.close()

# 2. 获取电影详情 (支持指定 link 参数)
@app.route('/api/movie')
def get_movie():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    target_link = request.args.get('link')

    try:
        if target_link:
            # 查询特定电影
            query = "SELECT * FROM show_sql_table WHERE show_douban_link = ?"
            row = cursor.execute(query, (target_link,)).fetchone()
        else:
            # 随机展示一部有海报的
            query = """
                SELECT * FROM show_sql_table 
                WHERE show_img_poster_path IS NOT NULL 
                ORDER BY RANDOM()
                LIMIT 1
            """
            row = cursor.execute(query).fetchone()
            
        if row:
            return jsonify(dict(row))
        else:
            return jsonify({"error": "No movie found"}), 404
            
    except sqlite3.Error as e:
        return jsonify({"error": str(e)}), 500
    finally:
        conn.close()

# =============================================================================
# 3. 辅助功能函数 (Helper Functions)
# =============================================================================

def open_browser():
    """延迟打开浏览器"""
    time.sleep(1.5)  # 等待 Flask 启动
    print(f"🌍 正在打开默认浏览器...")
    try:
        webbrowser.open(URL)
    except Exception as e:
        print(f"⚠️ 无法自动打开浏览器: {e}")
        print(f"👉 请手动复制地址访问: {URL}")

# =============================================================================
# 4. 主执行逻辑 (Main Execution)
# =============================================================================

if __name__ == '__main__':
    # 切换工作目录到项目根目录，防止相对路径出错
    try:
        os.chdir(PROJECT_ROOT)
    except FileNotFoundError:
        pass

    print("-" * 60)
    print(f"🚀 电影详情服务已启动")
    print(f"📂 项目根目录: {PROJECT_ROOT}")
    print(f"👤 当前用户:   {USERNAME}")
    print(f"📄 数据库路径: {DB_PATH}")
    print(f"🌐 访问地址:   {URL}")
    print("-" * 60)

    # 启动浏览器线程
    threading.Thread(target=open_browser, daemon=True).start()

    # 启动 Flask 服务器
    # use_reloader=False 防止自动重载导致浏览器打开两次
    app.run(debug=True, port=PORT, use_reloader=False)