from bs4 import BeautifulSoup
import re
import pandas as pd
import logging
from pathlib import Path
from typing import Optional, Tuple, List, Dict, Any
import json
import sys

# --- 1. 路径与配置初始化 ---

# 获取当前脚本的绝对路径并解析
CURRENT_SCRIPT = Path(__file__).resolve()
# 回溯两级目录获取项目根目录
PROJECT_ROOT = CURRENT_SCRIPT.parents[2]

RESOURCES_DIR = PROJECT_ROOT / "resources"
CONFIG_PATH = RESOURCES_DIR / "config.json"
USERDATA_ROOT = RESOURCES_DIR / "UserData"

# 日志配置
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def load_initial_config(config_path: Path) -> Dict[str, Any]:
    """读取配置文件以获取用户名"""
    if not config_path.exists():
        logger.error(f"❌ 配置文件未找到: {config_path}")
        sys.exit(1)
    try:
        with config_path.open('r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"❌ 读取配置失败: {e}")
        sys.exit(1)

# 立即加载配置
GLOBAL_CONFIG = load_initial_config(CONFIG_PATH)
USERNAME = GLOBAL_CONFIG.get('douban_username')

if not USERNAME:
    logger.error("❌ 配置错误: 'douban_username' 不能为空")
    sys.exit(1)

# --- 动态构建路径 ---
USER_SPECIFIC_DIR = USERDATA_ROOT / USERNAME
PAGES_DIR = USER_SPECIFIC_DIR / "pages"
DB_GEN_DIR = USER_SPECIFIC_DIR / "DBgenerate"
CSV_FILE = DB_GEN_DIR / "douban_movies.csv"

# --- 2. 核心解析函数 ---

def get_official_total_count(soup: BeautifulSoup) -> int:
    """从HTML Soup对象中提取用户“看过”的总数。"""
    # 尝试 1: H1 标签
    h1_tag = soup.select_one("div.info > h1")
    if h1_tag:
        match = re.search(r'\((\d+)\)', h1_tag.get_text(strip=True))
        if match:
            return int(match.group(1))

    # 尝试 2: Title 标签
    if soup.title:
        match = re.search(r'\((\d+)\)', soup.title.get_text(strip=True))
        if match:
            return int(match.group(1))

    return 0

def parse_intro_info(intro_text: Optional[str]) -> Tuple[Optional[str], Optional[str]]:
    """解析 intro 文本，提取最早首映日期和片长。"""
    if not intro_text:
        return None, None

    # 分割并清洗
    items = [i.strip() for i in intro_text.replace('\n', '').split('/') if i.strip()]

    premiere_dates = []
    duration_list = []

    date_pattern = re.compile(r'^\d{4}-\d{2}-\d{2}')
    duration_pattern = re.compile(r'^\d+\s*分钟$')

    for item in items:
        # 匹配日期 (取前10位 YYYY-MM-DD)
        if date_pattern.match(item):
            premiere_dates.append(item[:10])
        # 匹配时长
        elif duration_pattern.match(item):
            duration_list.append(item)

    premiere_date = min(premiere_dates) if premiere_dates else None
    duration = duration_list[0] if duration_list else None

    return premiere_date, duration

def parse_douban_html(html_path: Path) -> List[Dict[str, Any]]:
    """解析 HTML 页面，返回结构化列表"""
    if not html_path.exists():
        return []

    try:
        with html_path.open("r", encoding="utf-8", errors="ignore") as f:
            soup = BeautifulSoup(f, "lxml")
    except Exception as e:
        logger.error(f"解析文件失败 {html_path.name}: {e}")
        return []

    movie_items = soup.select("ul.list-view > li.item")
    results = []
    rating_map = {"rating1-t": 1, "rating2-t": 2, "rating3-t": 3, "rating4-t": 4, "rating5-t": 5}

    for item in movie_items:
        try:
            # 标题解析
            title_tag = item.select_one(".item-show .title a")
            if not title_tag: continue

            title_full = title_tag.get_text(strip=True)
            link = title_tag.get("href", "").strip()

            # 分割中文名与原名
            if " / " in title_full:
                parts = title_full.split(" / ", 1)
                ch_name = parts[0].strip()
                original_name = parts[1].strip()
            else:
                ch_name = title_full.strip()
                original_name = None

            # 观影日期
            date_tag = item.select_one(".item-show .date")
            watch_date = None
            if date_tag:
                raw_date = date_tag.get_text(strip=True).split('\n')[0].strip()
                # 提取 YYYY-MM-DD
                date_match = re.search(r'\d{4}-\d{2}-\d{2}', raw_date)
                if date_match:
                    watch_date = date_match.group(0)

            # 评分
            rating = None
            rating_span = item.select_one(".item-show .date span[class*='rating']")
            if rating_span and rating_span.has_attr("class"):
                for cls in rating_span["class"]:
                    if val := rating_map.get(cls):
                        rating = val
                        break

            # 简介与评论
            intro_tag = item.select_one(".comment-item .grid-date .intro")
            intro = intro_tag.get_text(strip=True) if intro_tag else None

            comment_tag = item.select_one(".comment-item .comment")
            comment = comment_tag.get_text(strip=True) if comment_tag else None

            # 首映日期与片长
            premiere_date, duration = parse_intro_info(intro)

            results.append({
                "title": title_full,
                "ch_name": ch_name,
                "original_name": original_name,
                "link": link,
                "watch_date": watch_date,
                "premiere_date": premiere_date,
                "duration": duration,
                "rating": rating,
                "intro": intro,
                "comment": comment,
            })

        except Exception as e:
            # 记录单条解析失败但不中断整个流程
            logger.debug(f"Skipping item due to error: {e}")
            continue

    return results

# --- 3. 主流程 ---

def main():
    print("="*50)
    print("🚀 豆瓣观影记录解析器 (HTML -> CSV)")
    print(f"👤 当前用户: {USERNAME}")
    print(f"📂 源文件目录: {PAGES_DIR}")
    print(f"💾 目标文件: {CSV_FILE}")
    print("="*50)
    
    # 检查源目录是否存在
    if not PAGES_DIR.exists():
        print(f"❌ 错误: 页面目录不存在: {PAGES_DIR}")
        print("   请先运行 SaveMoviesPages.py 下载数据。")
        sys.exit(1)

    # 确保输出目录存在
    if not DB_GEN_DIR.exists():
        print(f"📂 创建输出目录: {DB_GEN_DIR}")
        DB_GEN_DIR.mkdir(parents=True, exist_ok=True)

    # 1. 加载现有数据
    existing_links = set()
    existing_df = pd.DataFrame()

    if CSV_FILE.exists():
        print("📥 加载现有 CSV 库...")
        try:
            existing_df = pd.read_csv(CSV_FILE)
            if "link" in existing_df.columns:
                existing_links = set(existing_df["link"].dropna().astype(str))
                print(f"✅ 已加载 {len(existing_links)} 条历史记录。")
        except Exception as e:
            logger.error(f"❌ 读取 CSV 失败: {e} (将创建新文件)")
            existing_df = pd.DataFrame()
    else:
        print("✨ 未找到历史库，将创建新文件。")

    # 2. 批量解析 HTML
    movies_to_add = []
    page_index = 0
    step = 30
    official_total_count = 0
    consecutive_missing_files = 0 # 用于判断何时真正结束

    print("\n🔍 开始扫描 HTML 文件...")

    while True:
        file_name = f"moviePage_{page_index}.html"
        file_path = PAGES_DIR / file_name

        if not file_path.exists():
            # 简单的容错：只有连续找不到文件才退出，防止中间缺页导致中断
            # 但这里 SaveMoviesPages 通常是连续的，所以简单处理即可
            print(f"🏁 扫描结束 (未找到 {file_name})")
            break

        # 从第一页提取官方总数
        if page_index == 0:
            try:
                with file_path.open("r", encoding="utf-8", errors="ignore") as f:
                    soup_temp = BeautifulSoup(f, "lxml")
                    official_total_count = get_official_total_count(soup_temp)
            except Exception as e:
                logger.warning(f"⚠️  无法提取官方总数: {e}")

        # 解析当前页
        current_movies = parse_douban_html(file_path)

        # 增量筛选
        added_count = 0
        for movie in current_movies:
            link = movie.get("link")
            if link and str(link) not in existing_links:
                movies_to_add.append(movie)
                existing_links.add(str(link))
                added_count += 1

        print(f"   📄 {file_name}: 解析 {len(current_movies)} 条 -> 新增 {added_count} 条")
        page_index += step

    # 3. 合并与保存
    print("\n💾 正在保存数据...")

    if movies_to_add:
        new_df = pd.DataFrame(movies_to_add)
        combined_df = pd.concat([existing_df, new_df], ignore_index=True)

        # 提取年份列 (基于 premiere_date)
        if 'premiere_date' in combined_df.columns:
            combined_df['year'] = combined_df['premiere_date'].astype(str).str[:4]

        # 列排序优化
        desired_order = [
            "title", "ch_name", "original_name", "rating", "watch_date",
            "premiere_date", "year", "duration", "link", "intro", "comment"
        ]

        # 动态生成最终列序 (保证新旧兼容)
        current_cols = list(combined_df.columns)
        final_order = [c for c in desired_order if c in current_cols] + \
                      [c for c in current_cols if c not in desired_order]

        combined_df = combined_df[final_order]

        try:
            combined_df.to_csv(CSV_FILE, index=False, encoding="utf-8-sig") # utf-8-sig 兼容 Excel
            print(f"✅ 成功写入 {len(new_df)} 条新记录。")
            print(f"📍 文件位置: {CSV_FILE}")
        except Exception as e:
            logger.error(f"❌ 保存 CSV 失败: {e}")
    else:
        print("ℹ️  无新记录，跳过保存。")

    # 4. 数据完整性分析
    print("\n" + "="*50)
    print("📊 数据完整性报告")
    print("="*50)

    local_count = len(existing_links)
    print(f"1. 豆瓣官方总数: {official_total_count}")
    print(f"2. 本地入库总数: {local_count}")

    if official_total_count > 0:
        gap = official_total_count - local_count
        if gap > 0:
            print(f"⚠️  差异: 缺失 {gap} 条")
            print("   (原因可能是：未完全爬取、条目被封禁/隐藏、或豆瓣计数缓存)")
        elif gap == 0:
            print("✅ 数据完美一致！")
        else:
            print(f"⚠️  差异: 本地多出 {abs(gap)} 条")
            print("   (原因可能是：近期删除了记录但未清理本地库)")
    else:
        print("⚠️  未检测到官方总数，无法比对。")
    print("="*50 + "\n")

if __name__ == "__main__":
    main()