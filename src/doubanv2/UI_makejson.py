import sqlite3
import json
import re
import math
import random
import logging
import sys
from collections import defaultdict, Counter
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional, Set, Union

# --- 依赖库检测 ---
try:
    import jieba
    JIEBA_AVAILABLE = True
except ImportError:
    JIEBA_AVAILABLE = False

# =============================================================================
# 1. 路径与配置 (Configuration & Path Management)
# =============================================================================

# 脚本位置: .../DoubanV2/src/doubanv2/UI_makejson.py
CURRENT_SCRIPT = Path(__file__).resolve()
PROJECT_ROOT = CURRENT_SCRIPT.parents[2]

RESOURCES_DIR = PROJECT_ROOT / "resources"
CONFIG_PATH = RESOURCES_DIR / "config.json"
USERDATA_ROOT = RESOURCES_DIR / "UserData"
# 全局共享 UI 资源目录 (用于停用词等)
GLOBAL_UI_RESOURCES_DIR = RESOURCES_DIR / "ui_resources"

# --- 动态加载用户名以构建路径 ---

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

# 构建用户特定目录
USER_SPECIFIC_DIR = USERDATA_ROOT / USERNAME
USER_DB_DIR = USER_SPECIFIC_DIR / "DBgenerate"
USER_UI_DIR = USER_SPECIFIC_DIR / "ui_resources"

# --- 文件路径配置 ---

# 输入: 用户数据库
DB_PATH = USER_DB_DIR / "douban_movies.db"

# 输入: 全局停用词 (保持不变)
STOPWORDS_PATH = GLOBAL_UI_RESOURCES_DIR / "jiebastop"

# 输出: 用户 JSON 报告
OUTPUT_JSON_PATH = USER_UI_DIR / "full_report.json"

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("DataAnalyzer")

if not JIEBA_AVAILABLE:
    logger.warning('⚠️ 未找到 jieba 库，中文分词将使用正则兼容模式 (建议 pip install jieba)')

# =============================================================================
# 2. 核心工具函数 (Utility Functions)
# =============================================================================

def safe_float(value: Any) -> Optional[float]:
    """安全转换为浮点数"""
    if value is None:
        return None
    try:
        return float(value)
    except (ValueError, TypeError):
        return None

def parse_duration(duration_str: Any) -> int:
    """解析时长字符串为分钟数"""
    if not duration_str:
        return 0
    s = str(duration_str).lower()
    match_min = re.search(r'(\d+)\s*(?:分钟|min)?$', s)
    if match_min and 'h' not in s:
        return int(match_min.group(1))

    match_h = re.search(r'(\d+)\s*h', s)
    match_m = re.search(r'(\d+)\s*m', s)
    mins = 0
    if match_h: mins += int(match_h.group(1)) * 60
    if match_m: mins += int(match_m.group(1))
    return mins

def parse_year(date_str: Any) -> Optional[int]:
    """从日期字符串提取年份"""
    if not date_str: return None
    match = re.search(r'(\d{4})', str(date_str))
    return int(match.group(1)) if match else None

def clean_split(text: str, delimiter: str = '/') -> List[str]:
    """清理并分割字符串"""
    if not text: return []
    text = text.replace(' / ', '/').replace(',', '/')
    return [t.strip() for t in text.split(delimiter) if t.strip()]

def is_chinese(text: str) -> bool:
    """判断是否含中文字符"""
    return bool(re.search(r'[\u4e00-\u9fa5]', text))

def calculate_variance(values: List[float]) -> float:
    """计算方差"""
    if len(values) < 2: return 0.0
    avg = sum(values) / len(values)
    return sum((x - avg) ** 2 for x in values) / len(values)

def load_local_stopwords(file_path: Path) -> Set[str]:
    """读取本地停用词文件"""
    custom_stops = set()
    if file_path.exists():
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                for line in f:
                    word = line.strip()
                    if word:
                        custom_stops.add(word)
            logger.info(f"📚 已加载停用词库: {file_path.name} (共 {len(custom_stops)} 词)")
        except Exception as e:
            logger.warning(f"⚠️ 读取停用词失败: {e}")
    else:
        logger.info(f"ℹ️ 未找到本地停用词文件: {file_path} (使用默认)")
    return custom_stops

def get_tokenized_words(text: str, stop_words: Set[str]) -> List[str]:
    """分词处理"""
    words = []
    if not text: return words

    if JIEBA_AVAILABLE:
        for seg in jieba.cut(text):
            if len(seg) > 1 and seg not in stop_words:
                words.append(seg)
    else:
        # 正则回退模式
        for seg in re.findall(r'[\u4e00-\u9fa5]{2,}', text):
            if seg not in stop_words:
                words.append(seg)
    return words

# =============================================================================
# 3. 主分析逻辑 (Main Analysis Logic)
# =============================================================================

def analyze_full_dataset():
    print(f"👤 当前用户: {USERNAME}")
    
    if not DB_PATH.exists():
        logger.error(f"❌ 严重错误: 找不到数据库文件 {DB_PATH}")
        return

    logger.info(f"🔌 连接数据库: {DB_PATH} ...")

    # --- 初始化统计容器 ---
    stats_summary = {"total_movies": 0, "total_minutes": 0, "valid_ratings": [], "comment_length": 0}
    screenshot_pool = []

    # 时间轴
    stats_timeline = {
        "daily": Counter(),
        "quarterly": defaultdict(lambda: {"count": 0, "score_sum": 0, "ratings": []}),
        "monthly_duration": defaultdict(lambda: {"count": 0, "min_sum": 0, "list": []}),
        "monthly_comments": defaultdict(int)
    }

    # 内容
    stats_content = {
        "genres_zh": Counter(), "genres_en": Counter(),
        "regions_zh": Counter(), "regions_en": Counter(),
        "langs_zh": Counter(), "langs_en": Counter(),
        "durations_hist": Counter(),
        "decade_premieres": Counter(),
        "genre_title_map": defaultdict(list),
        "intro_words": Counter(),
        "comment_words": Counter()
    }

    # 人物
    stats_people = {
        "directors": defaultdict(list), "actors": Counter(), "writers": Counter(),
        "director_watch_sequence": []
    }

    # 偏好
    stats_preference = {
        "rating_dist": Counter(),
        "five_star_list": [],
        "dislikes": [],
        "discoveries": [],
        "cross_analysis": {
            "decade_r": defaultdict(list), "watch_y_r": defaultdict(list),
            "dur_r": defaultdict(list), "zh_genre_r": defaultdict(list),
            "en_genre_r": defaultdict(list)
        }
    }

    # 停用词准备
    default_stop_words = {
        '的','了','是','在','我','有','和','就','不','人','都','一','一个','上','也','很','到','说','要','去',
        '你','会','着','没有','看','好','自己','这','电影','影片','故事','导演','饰演','讲述','但是','就是',
        '因为','所以','他们','我们','以及','关于','或者','为了','开始','之后','虽然','不仅','而且','后来','与',
        '中','为','之'
    }
    local_stops = load_local_stopwords(STOPWORDS_PATH)
    stop_words = default_stop_words.union(local_stops)

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    query = """
    SELECT
        show_movid_title, show_personal_my_rating, show_personal_my_watch_date, show_personal_my_comment,
        show_spec_duration_main, show_release_premiere_date_main, show_genre,
        show_crew_director_main, show_crew_douban_personnel, show_crew_writer_main,
        show_intro_chs, show_img_backdrop_path, show_img_poster_path,
        show_release_douban_region, show_language,
        show_rate_imdb_rating, show_rate_metacritic_rating, show_rate_rotten_tomatoes_rating,
        show_rate_tmdb_vote_average, show_rate_staticdouban_rating
    FROM show_sql_table
    """

    try:
        cursor.execute(query)
        rows = cursor.fetchall()
        logger.info(f"📊 开始分析 {len(rows)} 条数据...")

        for row in rows:
            (title, my_rating_raw, watch_date, comment, dur_raw, prem_date,
             genre_raw, dir_raw, act_raw, writer_raw, intro,
             backdrop, poster,
             region_raw, lang_raw, imdb, meta, tomato, tmdb, douban_pub) = row

            # 1. 基础清洗
            title = title or "未知标题"
            my_rating = safe_float(my_rating_raw)
            mins = parse_duration(dur_raw)
            rel_year = parse_year(prem_date)
            w_year = parse_year(watch_date)

            # 2. 概览统计
            stats_summary["total_movies"] += 1
            stats_summary["total_minutes"] += mins

            if my_rating is not None and my_rating > 0:
                stats_summary["valid_ratings"].append(my_rating)

            if comment:
                stats_summary["comment_length"] += len(str(comment))

            if backdrop and str(backdrop).strip():
                # 清洗路径，确保没有前缀干扰
                clean_backdrop = str(backdrop).replace("resources/", "").strip("/")
                # 修改点：存入字典，包含标题
                screenshot_pool.append({"path": clean_backdrop, "title": title})

            # 3. 时间轴统计
            if watch_date:
                stats_timeline["daily"][watch_date] += 1
                if re.match(r'\d{4}-\d{2}', watch_date):
                    m_key = watch_date[:7]
                    stats_timeline["monthly_duration"][m_key]["count"] += 1
                    if mins > 0:
                        stats_timeline["monthly_duration"][m_key]["min_sum"] += mins
                        stats_timeline["monthly_duration"][m_key]["list"].append(mins)
                    if comment:
                        stats_timeline["monthly_comments"][m_key] += len(str(comment))
                try:
                    dt = datetime.strptime(watch_date, "%Y-%m-%d")
                    q_key = f"{dt.year}-Q{(dt.month - 1) // 3 + 1}"
                    stats_timeline["quarterly"][q_key]["count"] += 1
                    if my_rating and my_rating > 0:
                        stats_timeline["quarterly"][q_key]["score_sum"] += my_rating
                        stats_timeline["quarterly"][q_key]["ratings"].append(my_rating)
                except ValueError: pass

            # 4. 内容属性统计
            if mins > 0:
                interval = (mins // 5) * 5
                stats_content["durations_hist"][f"{interval}-{interval+5}"] += 1
                if my_rating:
                     bin_15 = (mins // 15) * 15
                     stats_preference["cross_analysis"]["dur_r"][f"{bin_15}-{bin_15+15}"].append(my_rating)

            if rel_year:
                stats_content["decade_premieres"][f"{(rel_year//10)*10}s"] += 1
                if my_rating:
                    stats_preference["cross_analysis"]["decade_r"][f"{(rel_year//10)*10}s"].append(my_rating)

            if w_year and my_rating:
                stats_preference["cross_analysis"]["watch_y_r"][w_year].append(my_rating)

            if genre_raw:
                genres = clean_split(genre_raw)
                for g in genres:
                    if is_chinese(g):
                        stats_content["genres_zh"][g] += 1
                        if my_rating: stats_preference["cross_analysis"]["zh_genre_r"][g].append(my_rating)
                        stats_content["genre_title_map"][g].append(title)
                    else:
                        stats_content["genres_en"][g] += 1
                        if my_rating: stats_preference["cross_analysis"]["en_genre_r"][g].append(my_rating)

            if region_raw:
                for r in clean_split(region_raw):
                    if is_chinese(r): stats_content["regions_zh"][r] += 1
                    else: stats_content["regions_en"][r] += 1
            if lang_raw:
                for l in clean_split(lang_raw):
                    if is_chinese(l): stats_content["langs_zh"][l] += 1
                    else: stats_content["langs_en"][l] += 1

            if intro:
                stats_content["intro_words"].update(get_tokenized_words(intro, stop_words))

            if comment:
                stats_content["comment_words"].update(get_tokenized_words(comment, stop_words))

            # 5. 人物统计
            if dir_raw:
                dirs = clean_split(dir_raw)
                if w_year:
                    stats_people["director_watch_sequence"].append({"year": w_year, "date": watch_date, "dirs": dirs})
                if my_rating:
                    for d in dirs: stats_people["directors"][d].append(my_rating)
            if act_raw: stats_people["actors"].update(clean_split(act_raw))
            if writer_raw: stats_people["writers"].update(clean_split(writer_raw))

            # 6. 偏好计算
            is_valid_rating = (my_rating is not None) and (my_rating > 0)
            if is_valid_rating:
                stats_preference["rating_dist"][my_rating] += 1
            else:
                stats_preference["rating_dist"]["未评分"] += 1

            if is_valid_rating:
                if my_rating == 5.0:
                    stats_preference["five_star_list"].append({
                        "title": title,
                        "watch_date": watch_date or "未知",
                        "poster": poster,
                        "rating": 5.0,
                        "douban_url": f"https://movie.douban.com/subject/"
                    })

                public_scores = []
                for val_raw, divisor in [(imdb, 2), (meta, 2), (tomato, 20), (tmdb, 2), (douban_pub, 2)]:
                    val = safe_float(val_raw)
                    if val is not None:
                        public_scores.append(val / divisor)

                if public_scores:
                    max_pub = max(public_scores)
                    diff_bad = my_rating - max_pub
                    if diff_bad < -1.0:
                        stats_preference["dislikes"].append({
                            "title": title, "my": my_rating,
                            "pub_max": round(max_pub, 2), "diff": round(diff_bad, 2)
                        })

                    diff_good = my_rating - max_pub
                    if diff_good > 0.5 and max_pub != 0 and len(public_scores) > 1:
                        stats_preference["discoveries"].append({
                            "title": title, "my": my_rating,
                            "pub_min": round(max_pub, 2), "diff": round(diff_good, 2)
                        })

    except sqlite3.Error as e:
        logger.error(f"❌ 数据库查询失败: {e}")
        return
    finally:
        conn.close()

    # ==========================================
    #            4. 数据聚合与输出
    # ==========================================
    logger.info("🧩 正在聚合分析结果...")

    def fmt_counter(c, min_count=1):
        return [{"name": k, "count": v} for k, v in c.most_common() if v >= min_count]

    def sort_dict(d): return dict(sorted(d.items(), key=lambda x: (-x[1], x[0])))

    # 1. Summary
    summary_out = {
        "total_movies": stats_summary["total_movies"],
        "total_hours": round(stats_summary["total_minutes"] / 60, 2),
        "avg_rating": round(sum(stats_summary["valid_ratings"])/len(stats_summary["valid_ratings"]), 2) if stats_summary["valid_ratings"] else 0,
        "total_comment_chars": stats_summary["comment_length"],
        "screenshot_wall_sample": random.sample(screenshot_pool, min(50, len(screenshot_pool)))
    }

    # 2. Timeline
    quarterly_out = []
    for q, d in stats_timeline["quarterly"].items():
        avg = round(d["score_sum"]/d["count"], 2) if d["count"] else 0
        quarterly_out.append({
            "quarter": q, "count": d["count"],
            "avg_rating": avg, "ratings": d["ratings"]
        })
    quarterly_out.sort(key=lambda x: x["quarter"])

    monthly_out = []
    for m in sorted(stats_timeline["monthly_duration"].keys()):
        d = stats_timeline["monthly_duration"][m]
        avg_dur = round(d["min_sum"]/d["count"], 1) if d["count"] else 0
        monthly_out.append({
            "month": m, "count": d["count"],
            "total_min": d["min_sum"], "avg_dur": avg_dur,
            "comment_chars": stats_timeline["monthly_comments"][m]
        })

    daily_out = [{"date": k, "count": v} for k, v in sorted(stats_timeline["daily"].items())]

    # 3. Content
    rare_global_list = []
    for g, movies in stats_content["genre_title_map"].items():
        rare_global_list.append({"genre": g, "count": len(movies), "movies": movies})
    rare_global_list.sort(key=lambda x: x['count'])
    rare_genres_global = rare_global_list[:10]

    # 4. People
    stats_people["director_watch_sequence"].sort(key=lambda x: x['date'] if x['date'] else "")

    dir_total_counts = Counter()
    for item in stats_people["director_watch_sequence"]:
        for d in item['dirs']: dir_total_counts[d] += 1

    seen_dirs = set()
    new_dirs_out = defaultdict(list)
    for item in stats_people["director_watch_sequence"]:
        for d in item['dirs']:
            if d not in seen_dirs:
                seen_dirs.add(d)
                if dir_total_counts[d] > 1:
                    new_dirs_out[item['year']].append(d)

    new_director_discovery = [{"year": y, "count": len(ds), "list": ds} for y, ds in sorted(new_dirs_out.items())]

    dir_metrics = {}
    for d, ratings in stats_people["directors"].items():
        if len(ratings) >= 3:
            dir_metrics[d] = {
                "count": len(ratings),
                "avg": round(sum(ratings)/len(ratings), 2),
                "variance": round(calculate_variance(ratings), 2)
            }
    top_directors = dict(sorted(dir_metrics.items(), key=lambda x: x[1]['avg'], reverse=True))

    # 5. Preference
    def calc_avg_dict(src_dict):
        res = {k: round(sum(v)/len(v), 2) for k, v in src_dict.items()}
        return dict(sorted(res.items(), key=lambda x: x[1], reverse=True))

    stats_preference["dislikes"].sort(key=lambda x: x["diff"])
    stats_preference["discoveries"].sort(key=lambda x: x["diff"], reverse=True)

    final_report = {
        "1_Summary": summary_out,
        "2_Timeline": {
            "daily_counts": daily_out,
            "quarterly_stats": quarterly_out,
            "monthly_stats": monthly_out
        },
        "3_Content_Analysis": {
            "genres": {"chinese": fmt_counter(stats_content["genres_zh"]), "english": fmt_counter(stats_content["genres_en"])},
            "regions_languages": {
                "regions_zh": sort_dict(stats_content["regions_zh"]),
                "regions_en": sort_dict(stats_content["regions_en"]),
                "langs_zh": sort_dict(stats_content["langs_zh"]),
                "langs_en": sort_dict(stats_content["langs_en"])
            },
            "duration_histogram": dict(sorted(stats_content["durations_hist"].items(), key=lambda x: int(x[0].split('-')[0]))),
            "decadal_premieres": dict(sorted(stats_content["decade_premieres"].items())),
            "intro_word_cloud": fmt_counter(stats_content["intro_words"], min_count=3)[:100],
            "comment_word_cloud": fmt_counter(stats_content["comment_words"], min_count=2)[:100],
            "rare_genres_global": rare_genres_global
        },
        "4_People_Analysis": {
            "top_actors": fmt_counter(stats_people["actors"])[:30],
            "top_writers": fmt_counter(stats_people["writers"])[:10],
            "new_director_discovery": new_director_discovery,
            "director_ratings_min3_movies": top_directors
        },
        "5_Preferences_Cross_Analysis": {
            "rating_distribution": dict(sorted(stats_preference["rating_dist"].items(), key=lambda x: -1 if x[0] == "未评分" else float(x[0]))),
            "five_star_movies": stats_preference["five_star_list"],
            "taste_deviation": {
                "not_my_cup_of_tea_top20": stats_preference["dislikes"][:20],
                "unexpected_discoveries_top20": stats_preference["discoveries"][:20]
            },
            "cross_metrics": {
                "rating_vs_decade": dict(sorted(calc_avg_dict(stats_preference["cross_analysis"]["decade_r"]).items())),
                "rating_vs_watch_year": dict(sorted(calc_avg_dict(stats_preference["cross_analysis"]["watch_y_r"]).items())),
                "rating_vs_duration_bin": dict(sorted(calc_avg_dict(stats_preference["cross_analysis"]["dur_r"]).items(), key=lambda x: int(x[0].split('-')[0]))),
                "rating_vs_genre_zh": calc_avg_dict(stats_preference["cross_analysis"]["zh_genre_r"]),
                "rating_vs_genre_en": calc_avg_dict(stats_preference["cross_analysis"]["en_genre_r"])
            }
        }
    }

    try:
        OUTPUT_JSON_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(OUTPUT_JSON_PATH, 'w', encoding='utf-8') as f:
            json.dump(final_report, f, indent=4, ensure_ascii=False)
        logger.info("-" * 30)
        logger.info(f"✅ 分析报告已生成: {OUTPUT_JSON_PATH}")
    except Exception as e:
        logger.error(f"❌ 写入JSON文件失败: {e}")

if __name__ == "__main__":
    analyze_full_dataset()