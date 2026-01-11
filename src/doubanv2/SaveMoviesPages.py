import requests
import json
import sys
import time
import os
from pathlib import Path
from typing import Optional, Dict, Any

# === 1. 平台特定导入 (用于非阻塞 I/O) ===
IS_WINDOWS = os.name == 'nt'
if IS_WINDOWS:
    import msvcrt
else:
    import select
    import tty
    import termios

# === 2. 基础路径配置 (静态部分) ===
# 获取当前脚本的绝对路径并解析
CURRENT_SCRIPT = Path(__file__).resolve()
# 回溯两级目录获取项目根目录 (src/doubanv2/SaveMoviesPages.py -> ProjectRoot)
PROJECT_ROOT = CURRENT_SCRIPT.parents[2]

RESOURCES_DIR = PROJECT_ROOT / "resources"
CONFIG_PATH = RESOURCES_DIR / "config.json"
USERDATA_ROOT = RESOURCES_DIR / "UserData"

# === 3. 初始化配置与动态路径 (关键修改) ===

def load_initial_config(config_path: Path) -> Dict[str, Any]:
    """在脚本启动初期读取配置，用于构建路径"""
    if not config_path.exists():
        print(f"❌ 严重错误: 配置文件未找到: {config_path}")
        sys.exit(1)
    try:
        with config_path.open('r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"❌ 读取配置失败: {e}")
        sys.exit(1)

# 立即加载配置以获取用户名
GLOBAL_CONFIG = load_initial_config(CONFIG_PATH)
USERNAME = GLOBAL_CONFIG.get('douban_username')

if not USERNAME:
    print("❌ 配置错误: 'douban_username' 不能为空")
    sys.exit(1)

# --- 在此处完成所有路径和文件名的定义 ---
# 用户的根目录: resources/UserData/{username}
USER_SPECIFIC_DIR = USERDATA_ROOT / USERNAME
# 页面保存目录: resources/UserData/{username}/pages
PAGES_DIR = USER_SPECIFIC_DIR / "pages"

# === 4. 交互工具函数 ===

def get_timed_input(prompt: str,
                    timeout_sec: int,
                    timeout_default: str,
                    enter_default_val: str = '') -> str:
    """
    获取带超时的用户输入。支持 Windows 和 Unix。
    """
    sys.stdout.write(f"{prompt} ")
    sys.stdout.flush()

    start_time = time.time()
    buffer = []

    while True:
        elapsed = time.time() - start_time
        time_left = timeout_sec - elapsed

        if time_left <= 0:
            sys.stdout.write(f"\n⏱️  超时! 默认选择: {timeout_default}\n")
            return timeout_default

        timer_str = f"({int(time_left) + 1}s) "
        current_input = "".join(buffer)
        sys.stdout.write(f"\r{prompt} {timer_str}{current_input}")
        sys.stdout.flush()

        char = None
        if IS_WINDOWS:
            if msvcrt.kbhit():
                char_bytes = msvcrt.getch()
                if char_bytes in (b'\r', b'\n'):
                    char = '\n'
                elif char_bytes == b'\x08':
                    char = '\b'
                else:
                    try:
                        char = char_bytes.decode('utf-8')
                    except: pass
            else:
                time.sleep(0.05)
        else: # Unix
            fd = sys.stdin.fileno()
            old_settings = termios.tcgetattr(fd)
            try:
                tty.setcbreak(fd)
                rlist, _, _ = select.select([sys.stdin], [], [], 0.05)
                if rlist:
                    char = sys.stdin.read(1)
            finally:
                termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)

        if char:
            if char == '\n':
                sys.stdout.write('\n')
                res = "".join(buffer).strip().lower()
                return res if res else enter_default_val
            elif char in ('\b', '\x7f'):
                if buffer:
                    buffer.pop()
                    sys.stdout.write("\b \b")
            elif char.isprintable():
                buffer.append(char)

# === 5. 核心逻辑函数 ===

def check_and_create_dirs(target_dir: Path) -> None:
    """
    构建文件夹部分的代码 (主逻辑调用)
    检查并清理/创建页面存储目录
    """
    print(f"📂 检查存储目录: {target_dir}")
    
    # 确保父级目录 (UserData/username) 存在
    if not target_dir.parent.exists():
        print(f"   创建用户目录: {target_dir.parent}")
        target_dir.parent.mkdir(parents=True, exist_ok=True)

    if not target_dir.exists():
        try:
            target_dir.mkdir(parents=True, exist_ok=True)
            print("✅ Pages 目录已创建")
            return
        except Exception as e:
            print(f"❌ 无法创建目录: {e}")
            sys.exit(1)

    # 获取现有文件
    files = [f for f in target_dir.iterdir() if f.is_file()]

    if not files:
        print("✅ 目录为空，准备就绪。")
        return

    print(f"⚠️  目录中已存在 {len(files)} 个文件。")
    if len(files) <= 5:
        print(f"   文件: {', '.join([f.name for f in files])}")
    else:
        print(f"   示例: {files[0].name} ... {files[-1].name}")

    prompt = f"是否清空目录? (y/n, 默认n):"
    choice = get_timed_input(prompt, 5, timeout_default='n', enter_default_val='n')

    if choice == 'y':
        deleted = 0
        for f in files:
            try:
                f.unlink()
                deleted += 1
            except Exception as e:
                print(f"❌ 删除失败 {f.name}: {e}")
        print(f"🧹 已清理 {deleted} 个文件。")
    else:
        # --- 修改点开始: 如果选择 n，直接退出脚本 ---
        print("🚫 用户选择不清空目录，程序终止，跳过后续任务。")
        sys.exit(0)
        # --- 修改点结束 ---

def download_page(url: str, filepath: Path, headers: Dict[str, str], proxy_config: dict = None) -> bool:
    """下载并保存页面，带重试机制和代理支持"""
    max_retries = 3
    
    # 简单的代理配置处理
    proxies = None
    if proxy_config:
        proxies = proxy_config

    for attempt in range(max_retries):
        try:
            response = requests.get(url, headers=headers, proxies=proxies, timeout=15)
            response.raise_for_status()
            # 豆瓣通常是 utf-8，但也可能是其他
            response.encoding = response.apparent_encoding or 'utf-8'

            with filepath.open("w", encoding="utf-8") as f:
                f.write(response.text)

            print(f"   ✅ [OK] {filepath.name}")
            return True
        except requests.RequestException as e:
            wait = (attempt + 1) * 2
            print(f"   ⚠️  [失败] {url} (尝试 {attempt+1}/{max_retries}): {e}")
            if attempt < max_retries - 1:
                time.sleep(wait)
            else:
                print(f"   ❌ [放弃] {filepath.name}")
                return False

def main():
    # 1. 环境准备 (调用构建文件夹代码)
    # 此时 USERNAME, PAGES_DIR 等变量已经在文件头部定义完成
    check_and_create_dirs(PAGES_DIR)

    # 读取其他配置 (movie_count, proxy等)
    count = GLOBAL_CONFIG.get('movie_count', 0)
    proxy_conf = GLOBAL_CONFIG.get('proxy', None)

    if not isinstance(count, int) or count < 0:
        print("❌ 'movie_count' 必须为非负整数")
        sys.exit(1)

    print(f"✅ 任务启动: 用户 [{USERNAME}]")
    print(f"🎯 目标目录: {PAGES_DIR}")
    print(f"📊 计划下载: {count} 部电影")

    # 2. 计算页数 (每页30部)
    # range(start, stop, step)
    pages = range(0, count + 1, 30)
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }

    print("\n🚀 开始下载任务...")

    total_pages = len(pages)
    success_count = 0

    for i, start in enumerate(pages, 1):
        url = f"https://movie.douban.com/people/{USERNAME}/collect?start={start}&sort=time&type=all&filter=all&mode=list"
        
        # 文件名已经在逻辑中确定
        filename = f"moviePage_{start}.html"
        filepath = PAGES_DIR / filename

        print(f"[{i}/{total_pages}] 下载中: {filename} ...")
        if download_page(url, filepath, headers, proxy_conf):
            success_count += 1

        # 礼貌性延时
        if i < total_pages:
            time.sleep(3)

    print("\n" + "="*40)
    print(f"🏁 任务结束。成功: {success_count}/{total_pages}")
    print(f"📂 所有文件已保存在: {PAGES_DIR}")
    print("="*40)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n🛑 用户强制中断。")
    except Exception as e:
        print(f"\n❌ 未知错误: {e}")
    finally:
        if not IS_WINDOWS:
            try:
                os.system('stty sane')
            except: pass