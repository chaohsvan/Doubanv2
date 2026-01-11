import csv
import sqlite3
import re
import sys
import gc
import logging
import json
from pathlib import Path
from collections import Counter
from typing import Dict, List, Optional, Tuple, Any, Union

# 尝试导入 tqdm
try:
    from tqdm import tqdm
except ImportError:
    print("⚠️ 建议安装 tqdm 以获取进度条体验: pip install tqdm")
    def tqdm(iterable, **kwargs): return iterable

# =============================================================================
# 1. 路径与配置 (Configuration & Path Management)
# =============================================================================

CURRENT_SCRIPT = Path(__file__).resolve()
PROJECT_ROOT = CURRENT_SCRIPT.parents[2]

RESOURCES_DIR = PROJECT_ROOT / "resources"
CONFIG_PATH = RESOURCES_DIR / "config.json"
USERDATA_ROOT = RESOURCES_DIR / "UserData"

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
USER_LOG_DIR = USER_SPECIFIC_DIR / "log"

# 统一将生成的数据文件放在 DBgenerate 文件夹下，保持整洁
LOG_FILE = USER_LOG_DIR / "importCsvSql.log"
CSV_FILE = USER_DB_DIR / "douban_movies_merged.csv"
DB_FILE = USER_DB_DIR / "douban_movies.db" 

BATCH_SIZE = 5000

# =============================================================================
# 2. 正则预编译 (Pre-compiled Regex)
# =============================================================================

RE_DATE = re.compile(r'(\d{4}-\d{1,2}-\d{1,2})')
RE_DURATION_H = re.compile(r'(\d+)\s*h', re.IGNORECASE)
RE_DURATION_M = re.compile(r'(\d+)\s*m', re.IGNORECASE)
RE_DIGIT_ONLY = re.compile(r'^\d+$')

# =============================================================================
# 3. 日志系统 (Logging System)
# =============================================================================

def setup_logging():
    # 确保日志目录存在
    USER_LOG_DIR.mkdir(parents=True, exist_ok=True)
    
    logger = logging.getLogger("DoubanETL")
    logger.setLevel(logging.INFO)
    logger.handlers = []

    file_handler = logging.FileHandler(LOG_FILE, encoding='utf-8')
    file_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
    logger.addHandler(file_handler)

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(logging.Formatter('%(message)s'))
    logger.addHandler(console_handler)
    return logger

logger = setup_logging()

# =============================================================================
# 4. 数据库Schema定义 (Database Schema)
# =============================================================================

# (保持原有的 TABLE_DEFINITIONS 和 COLUMN_MAPPING 不变)
TABLE_DEFINITIONS = {
    'movie_identification': {
        'description': '电影标识信息',
        'columns': [
            ('douban_link', 'TEXT PRIMARY KEY'),
            ('title', 'TEXT'), ('ch_name', 'TEXT'), ('original_name', 'TEXT'),
            ('imdb_tconst', 'TEXT'), ('tmdb_id', 'INTEGER'), ('imdb_other_titles', 'TEXT'),
            ('aname', 'TEXT'), ('chsname', 'TEXT'), ('staticdouban_电影名', 'TEXT'),
            ('rotomatoes2_title', 'TEXT'),
        ]
    },
    'personal_data': {
        'description': '个人数据',
        'columns': [
            ('douban_link', 'TEXT PRIMARY KEY'),
            ('my_rating', 'REAL'), ('my_watch_date', 'TEXT'), ('my_comment', 'TEXT'),
            ('local_backdrop_path', 'TEXT'), ('local_poster_path', 'TEXT'),
        ]
    },
    'release_distribution': {
        'description': '上映与发行',
        'columns': [
            ('douban_link', 'TEXT PRIMARY KEY'),
            ('premiere_date', 'TEXT'), ('release_year', 'INTEGER'), ('douban_premiere_date', 'TEXT'),
            ('rotten_tomatoes_theater_date', 'TEXT'), ('tmdb_release_date', 'TEXT'),
            ('staticdouban_release_date', 'TEXT'), ('rotten_tomatoes_studio', 'TEXT'),
            ('rotten_tomatoes2_distributor', 'TEXT'), ('douban_region', 'TEXT'),
        ]
    },
    'technical_specifications': {
        'description': '技术规格',
        'columns': [
            ('douban_link', 'TEXT PRIMARY KEY'),
            ('duration', 'TEXT'), ('douban_duration', 'TEXT'), ('metacritic_duration', 'TEXT'),
            ('rotten_tomatoes_duration', 'INTEGER'), ('rotten_tomatoes2_duration', 'INTEGER'),
            ('douban_genre', 'TEXT'), ('metacritic_genre', 'TEXT'), ('rotten_tomatoes_genre', 'TEXT'),
            ('rotten_tomatoes2_genre', 'TEXT'), ('douban_language', 'TEXT'), ('rotten_tomatoes2_language', 'TEXT'),
        ]
    },
    'cast_crew': {
        'description': '演职人员',
        'columns': [
            ('douban_link', 'TEXT PRIMARY KEY'),
            ('imdb_director_names', 'TEXT'), ('imdb_director_ids', 'TEXT'), ('metacritic_director', 'TEXT'),
            ('rotten_tomatoes_director', 'TEXT'), ('rotten_tomatoes2_director', 'TEXT'),
            ('imdb_writer_names', 'TEXT'), ('imdb_writer_ids', 'TEXT'), ('metacritic_writer', 'TEXT'),
            ('rotten_tomatoes_writers', 'TEXT'), ('rotten_tomatoes2_writer', 'TEXT'), ('douban_personnel', 'TEXT'),
        ]
    },
    'ratings_reviews': {
        'description': '评分与评价',
        'columns': [
            ('douban_link', 'TEXT PRIMARY KEY'),
            ('imdb_rating', 'REAL'), ('imdb_votes', 'INTEGER'), ('metacritic_rating', 'REAL'),
            ('metacritic_votes', 'TEXT'), ('rotten_tomatoes_rating', 'INTEGER'),
            ('rotten_tomatoes_critic_count', 'INTEGER'), ('rotten_tomatoes_audience_rating', 'INTEGER'),
            ('rotten_tomatoes_audience_count', 'INTEGER'), ('rotten_tomatoes_status', 'TEXT'),
            ('rotten_tomatoes2_audience_score', 'INTEGER'), ('rotten_tomatoes2_tomatometer', 'INTEGER'),
            ('tmdb_vote_average', 'REAL'), ('staticdouban_rating', 'REAL'), ('staticdouban_votes', 'INTEGER'),
        ]
    },
    'descriptive_content': {
        'description': '描述性内容',
        'columns': [
            ('douban_link', 'TEXT PRIMARY KEY'),
            ('douban_intro', 'TEXT'), ('metacritic_description', 'TEXT'),
            ('rotten_tomatoes_movie_info', 'TEXT'), ('tmdb_overview', 'TEXT'),
            ('rotten_tomatoes_critics_consensus', 'TEXT'),
        ]
    },
    'metadata': {
        'description': '元数据',
        'columns': [
            ('douban_link', 'TEXT PRIMARY KEY'),
            ('tmdb_data_quality', 'TEXT'), ('backdrop_path', 'TEXT'), ('poster_path', 'TEXT'),
        ]
    }
}

COLUMN_MAPPING = {
    'link': ('movie_identification', 'douban_link'),
    'title': ('movie_identification', 'title'),
    'ch_name': ('movie_identification', 'ch_name'),
    'original_name': ('movie_identification', 'original_name'),
    'imdb_tconst': ('movie_identification', 'imdb_tconst'),
    'tmdb_id': ('movie_identification', 'tmdb_id'),
    'imdb_other_titles': ('movie_identification', 'imdb_other_titles'),
    'aname': ('movie_identification', 'aname'),
    'chsname': ('movie_identification', 'chsname'),
    'staticdouban_电影名': ('movie_identification', 'staticdouban_电影名'),
    'rotomatoes2_title': ('movie_identification', 'rotomatoes2_title'),
    'rating': ('personal_data', 'my_rating'),
    'watch_date': ('personal_data', 'my_watch_date'),
    'comment': ('personal_data', 'my_comment'),
    'premiere_date': ('release_distribution', 'premiere_date'),
    'year': ('release_distribution', 'release_year'),
    'RottenTomatoes_in_theaters_date': ('release_distribution', 'rotten_tomatoes_theater_date'),
    'release_date_tmdb': ('release_distribution', 'tmdb_release_date'),
    'staticdouban_首映时间': ('release_distribution', 'staticdouban_release_date'),
    'RottenTomatoes_studio_name': ('release_distribution', 'rotten_tomatoes_studio'),
    'rotomatoes2_distributor': ('release_distribution', 'rotten_tomatoes2_distributor'),
    'doubankeyword_地区': ('release_distribution', 'douban_region'),
    'duration': ('technical_specifications', 'duration'),
    'metacritic_Duration': ('technical_specifications', 'metacritic_duration'),
    'RottenTomatoes_runtime_in_minutes': ('technical_specifications', 'rotten_tomatoes_duration'),
    'rotomatoes2_runtimeMinutes': ('technical_specifications', 'rotten_tomatoes2_duration'),
    'doubankeyword_类型': ('technical_specifications', 'douban_genre'),
    'metacritic_Genres': ('technical_specifications', 'metacritic_genre'),
    'RottenTomatoes_genre': ('technical_specifications', 'rotten_tomatoes_genre'),
    'rotomatoes2_genre': ('technical_specifications', 'rotten_tomatoes2_genre'),
    'doubankeyword_语言': ('technical_specifications', 'douban_language'),
    'rotomatoes2_originalLanguage': ('technical_specifications', 'rotten_tomatoes2_language'),
    'imdb_director_names': ('cast_crew', 'imdb_director_names'),
    'imdb_directors_ids': ('cast_crew', 'imdb_director_ids'),
    'metacritic_Directed by': ('cast_crew', 'metacritic_director'),
    'RottenTomatoes_directors': ('cast_crew', 'rotten_tomatoes_director'),
    'rotomatoes2_director': ('cast_crew', 'rotten_tomatoes2_director'),
    'imdb_writer_names': ('cast_crew', 'imdb_writer_names'),
    'imdb_writers_ids': ('cast_crew', 'imdb_writer_ids'),
    'metacritic_Written by': ('cast_crew', 'metacritic_writer'),
    'RottenTomatoes_writers': ('cast_crew', 'rotten_tomatoes_writers'),
    'rotomatoes2_writer': ('cast_crew', 'rotten_tomatoes2_writer'),
    'doubankeyword_人员': ('cast_crew', 'douban_personnel'),
    'imdb_averageRating': ('ratings_reviews', 'imdb_rating'),
    'imdb_numVotes': ('ratings_reviews', 'imdb_votes'),
    'metacritic_Rating': ('ratings_reviews', 'metacritic_rating'),
    'metacritic_No of Persons Voted': ('ratings_reviews', 'metacritic_votes'),
    'RottenTomatoes_tomatometer_rating': ('ratings_reviews', 'rotten_tomatoes_rating'),
    'RottenTomatoes_tomatometer_count': ('ratings_reviews', 'rotten_tomatoes_critic_count'),
    'RottenTomatoes_audience_rating': ('ratings_reviews', 'rotten_tomatoes_audience_rating'),
    'RottenTomatoes_audience_count': ('ratings_reviews', 'rotten_tomatoes_audience_count'),
    'RottenTomatoes_tomatometer_status': ('ratings_reviews', 'rotten_tomatoes_status'),
    'rotomatoes2_audienceScore': ('ratings_reviews', 'rotten_tomatoes2_audience_score'),
    'rotomatoes2_tomatoMeter': ('ratings_reviews', 'rotten_tomatoes2_tomatometer'),
    'tmdb_vote_average': ('ratings_reviews', 'tmdb_vote_average'),
    'staticdouban_评分': ('ratings_reviews', 'staticdouban_rating'),
    'staticdouban_评价人数': ('ratings_reviews', 'staticdouban_votes'),
    'intro': ('descriptive_content', 'douban_intro'),
    'metacritic_Description': ('descriptive_content', 'metacritic_description'),
    'RottenTomatoes_movie_info': ('descriptive_content', 'rotten_tomatoes_movie_info'),
    'tmdb_overview': ('descriptive_content', 'tmdb_overview'),
    'RottenTomatoes_critics_consensus': ('descriptive_content', 'rotten_tomatoes_critics_consensus'),
    'tmdb_data_quality': ('metadata', 'tmdb_data_quality'),
    'backdrop_path': ('metadata', 'backdrop_path'),
    'poster_path': ('metadata', 'poster_path'),
}

# =============================================================================
# 5. 工具函数 (Utility Functions)
# =============================================================================

def check_input_files() -> bool:
    if not CSV_FILE.exists():
        logger.error(f"❌ 严重错误: 找不到CSV文件: {CSV_FILE}")
        return False
    return True

def parse_csv_row(row: Dict[str, str]) -> Dict[str, Optional[str]]:
    parsed = {}
    for key, value in row.items():
        clean_key = key.lstrip('\ufeff')
        if value is None or value.strip() == '' or value == 'N/A':
            parsed[clean_key] = None
        else:
            parsed[clean_key] = value.strip()
    return parsed

def extract_premiere_date_from_intro(intro_text: Optional[str]) -> Optional[str]:
    if not intro_text:
        return None
    match = RE_DATE.search(intro_text)
    return match.group(1) if match else None

def parse_duration_to_minutes(duration_str: Any) -> Optional[int]:
    if not duration_str:
        return None
    if isinstance(duration_str, (int, float)):
        return int(duration_str)
    s_str = str(duration_str).strip()
    hours, minutes = 0, 0
    h_match = RE_DURATION_H.search(s_str)
    m_match = RE_DURATION_M.search(s_str)
    if h_match: hours = int(h_match.group(1))
    if m_match: minutes = int(m_match.group(1))
    total = (hours * 60) + minutes
    if total == 0 and not h_match and not m_match:
        if RE_DIGIT_ONLY.match(s_str):
            return int(s_str)
        return None
    return total if total > 0 else None

def extract_top_names(personnel_text: Optional[str], top_n: int = 2) -> Optional[str]:
    """提取前N个高频名字 - 修复：支持多种分隔符"""
    if not personnel_text:
        return None
    # 修复: 同时支持 | 和 / 和 ,
    clean_text = personnel_text.replace('|', '/').replace(',', '/')
    names = [n.strip() for n in clean_text.split('/') if n.strip()]
    if not names:
        return None
    top = [n for n, _ in Counter(names).most_common(top_n)]
    return '/'.join(top)

def deduplicate_names(*name_fields: Optional[str]) -> Optional[str]:
    seen = set()
    result = []
    for field in name_fields:
        if field:
            processed = field.replace(',', '/').replace('|', '/')
            names = [n.strip() for n in processed.split('/') if n.strip()]
            for name in names:
                if name not in seen:
                    seen.add(name)
                    result.append(name)
    return '/'.join(result) if result else None

def get_most_frequent_date(dates: List[Optional[str]]) -> Optional[str]:
    valid_dates = [d for d in dates if d]
    if not valid_dates:
        return None
    return Counter(valid_dates).most_common(1)[0][0]

# =============================================================================
# 6. 核心处理逻辑 (Core Logic)
# =============================================================================

def create_database_schema():
    logger.info(f"⚙️ 正在初始化数据库: {DB_FILE}")
    # 确保数据库父目录存在
    DB_FILE.parent.mkdir(parents=True, exist_ok=True)
    
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        for table_name, table_info in TABLE_DEFINITIONS.items():
            column_defs = [f"{col} {dtype}" for col, dtype in table_info['columns']]
            sql = f"CREATE TABLE IF NOT EXISTS {table_name} ({', '.join(column_defs)})"
            cursor.execute(sql)
        conn.commit()
    logger.info("✅ 数据库表结构创建完毕")

def import_csv_to_tables():
    logger.info(f"🚀 开始导入 CSV 数据: {CSV_FILE}")

    with open(CSV_FILE, 'r', encoding='utf-8-sig') as f:
        total_lines = sum(1 for _ in f) - 1

    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute("PRAGMA synchronous = OFF")
        cursor.execute("PRAGMA journal_mode = MEMORY")

        with open(CSV_FILE, 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            batch_buffer = {t: [] for t in TABLE_DEFINITIONS.keys()}

            with tqdm(total=total_lines, unit="row", desc="📥 Importing") as pbar:
                for row in reader:
                    parsed = parse_csv_row(row)
                    douban_link = parsed.get('link')
                    if not douban_link:
                        continue

                    # 提取intro中的日期
                    intro_date = extract_premiere_date_from_intro(parsed.get('intro'))

                    # 构建各表数据
                    for table, _ in TABLE_DEFINITIONS.items():
                        t_row = {'douban_link': douban_link}

                        # 1. 标准映射处理
                        for csv_col, (target_tbl, target_col) in COLUMN_MAPPING.items():
                            if target_tbl == table:
                                t_row[target_col] = parsed.get(csv_col)
                        
                        # 2. 【修复】特殊字段逻辑处理 (修复原先无法赋值的 Bug)
                        # douban_premiere_date 属于 release_distribution 表，但没有直接映射
                        if table == 'release_distribution':
                             t_row['douban_premiere_date'] = intro_date

                        batch_buffer[table].append(t_row)

                    # 批量写入
                    if len(batch_buffer['movie_identification']) >= BATCH_SIZE:
                        _flush_batch(cursor, batch_buffer)
                        conn.commit()
                    
                    pbar.update(1)

            _flush_batch(cursor, batch_buffer)
            conn.commit()

    logger.info("✅ CSV 数据导入完成")
    gc.collect()

def _flush_batch(cursor, buffer: Dict[str, List[dict]]):
    for table, rows in buffer.items():
        if not rows:
            continue
        cols = TABLE_DEFINITIONS[table]['columns']
        col_names = [c[0] for c in cols]
        placeholders = ', '.join(['?'] * len(col_names))
        data_tuples = []
        for r in rows:
            data_tuples.append(tuple(r.get(c) for c in col_names))
        sql = f"INSERT OR REPLACE INTO {table} ({', '.join(col_names)}) VALUES ({placeholders})"
        cursor.executemany(sql, data_tuples)
        rows.clear()

def create_summary_table():
    logger.info("📊 正在构建汇总表 show_sql_table ...")
    
    # (SQL 语句保持不变)
    create_sql = """
        CREATE TABLE IF NOT EXISTS show_sql_table (
            show_douban_link TEXT PRIMARY KEY,
            show_crew_director_main TEXT, show_crew_writer_main TEXT, show_crew_douban_personnel TEXT,
            show_intro_chs TEXT, show_intro_douban TEXT, show_intro_eng TEXT,
            show_intro_rotten_tomatoes_critics_consensus TEXT,
            show_img_backdrop_path TEXT, show_img_poster_path TEXT,
            show_movid_name TEXT, show_movid_title TEXT, show_movid_tmdb_id INTEGER,
            show_movid_imdb_tconst TEXT, show_personal_my_rating REAL,
            show_personal_my_watch_date TEXT, show_personal_my_comment TEXT,
            show_rate_imdb_rating REAL, show_rate_metacritic_rating REAL,
            show_rate_rotten_tomatoes_rating INTEGER, show_rate_rotten_tomatoes_audience_rating INTEGER,
            show_rate_rotten_tomatoes_status TEXT, show_rate_rotten_tomatoes2_audience_score INTEGER,
            show_rate_rotten_tomatoes2_tomatometer INTEGER, show_rate_tmdb_vote_average REAL,
            show_rate_staticdouban_rating REAL, show_rate_staticdouban_votes INTEGER,
            show_rate_imdb_votes INTEGER, show_rate_metacritic_votes TEXT,
            show_rate_rotten_tomatoes_critic_count INTEGER, show_rate_rotten_tomatoes_audience_count INTEGER,
            show_release_premiere_date_main TEXT, show_release_premiere_date_alter TEXT,
            show_release_rotten_tomatoes_studio TEXT, show_release_rotten_tomatoes2_distributor TEXT,
            show_release_douban_region TEXT, show_spec_duration_main TEXT,
            show_spec_duration_alter TEXT, show_genre TEXT, show_language TEXT
        )
    """
    select_sql = """
        SELECT
            mi.douban_link, mi.ch_name, mi.original_name, mi.imdb_other_titles, mi.aname, mi.chsname,
            mi.staticdouban_电影名, mi.rotomatoes2_title, mi.title, mi.tmdb_id, mi.imdb_tconst,
            pd.my_rating, pd.my_watch_date, pd.my_comment,
            cc.imdb_director_names, cc.metacritic_director, cc.rotten_tomatoes_director, cc.rotten_tomatoes2_director,
            cc.imdb_writer_names, cc.metacritic_writer, cc.rotten_tomatoes_writers, cc.rotten_tomatoes2_writer, cc.douban_personnel,
            dc.douban_intro, dc.tmdb_overview, dc.metacritic_description, dc.rotten_tomatoes_movie_info, dc.rotten_tomatoes_critics_consensus,
            rr.imdb_rating, rr.metacritic_rating, rr.rotten_tomatoes_rating, rr.rotten_tomatoes_audience_rating, rr.rotten_tomatoes_status,
            rr.rotten_tomatoes2_audience_score, rr.rotten_tomatoes2_tomatometer, rr.tmdb_vote_average, rr.staticdouban_rating,
            rr.staticdouban_votes, rr.imdb_votes, rr.metacritic_votes, rr.rotten_tomatoes_critic_count, rr.rotten_tomatoes_audience_count,
            rd.tmdb_release_date, rd.premiere_date, rd.douban_premiere_date, rd.rotten_tomatoes_theater_date, rd.staticdouban_release_date,
            rd.rotten_tomatoes_studio, rd.rotten_tomatoes2_distributor, rd.douban_region,
            ts.duration, ts.douban_duration, ts.metacritic_duration, ts.rotten_tomatoes_duration, ts.rotten_tomatoes2_duration,
            ts.douban_genre, ts.metacritic_genre, ts.rotten_tomatoes_genre, ts.rotten_tomatoes2_genre,
            ts.douban_language, ts.rotten_tomatoes2_language,
            md.backdrop_path, md.poster_path
        FROM movie_identification mi
        LEFT JOIN personal_data pd ON mi.douban_link = pd.douban_link
        LEFT JOIN cast_crew cc ON mi.douban_link = cc.douban_link
        LEFT JOIN descriptive_content dc ON mi.douban_link = dc.douban_link
        LEFT JOIN ratings_reviews rr ON mi.douban_link = rr.douban_link
        LEFT JOIN release_distribution rd ON mi.douban_link = rd.douban_link
        LEFT JOIN technical_specifications ts ON mi.douban_link = ts.douban_link
        LEFT JOIN metadata md ON mi.douban_link = md.douban_link
    """
    insert_sql = """
        INSERT INTO show_sql_table VALUES (
            ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
            ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
            ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
            ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
        )
    """

    with sqlite3.connect(DB_FILE) as conn:
        read_cursor = conn.cursor()
        write_cursor = conn.cursor()
        
        write_cursor.execute("DROP TABLE IF EXISTS show_sql_table")
        write_cursor.execute(create_sql)
        
        read_cursor.execute("SELECT COUNT(*) FROM movie_identification")
        total_rows = read_cursor.fetchone()[0]
        
        read_cursor.execute(select_sql)
        
        batch_data = []
        
        with tqdm(total=total_rows, unit="row", desc="🔨 Building Summary") as pbar:
            for row in read_cursor:
                (
                    douban_link, ch_name, original_name, imdb_other_titles, aname, chsname,
                    staticdouban_name, rotomatoes2_title, title, tmdb_id, imdb_tconst,
                    my_rating, my_watch_date, my_comment,
                    imdb_director_names, metacritic_director, rt_director, rt2_director,
                    imdb_writer_names, metacritic_writer, rt_writers, rt2_writer, douban_personnel,
                    douban_intro, tmdb_overview, metacritic_desc, rt_movie_info, rt_consensus,
                    imdb_rating, metacritic_rating, rt_rating, rt_aud_rating, rt_status,
                    rt2_aud_score, rt2_tomatometer, tmdb_vote_avg, staticdouban_rating,
                    staticdouban_votes, imdb_votes, metacritic_votes, rt_critic_count, rt_aud_count,
                    tmdb_release_date, premiere_date, douban_premiere_date, rt_theater_date, staticdouban_release_date,
                    rt_studio, rt2_distributor, douban_region,
                    duration, douban_duration, metacritic_duration, rt_duration, rt2_duration,
                    douban_genre, metacritic_genre, rt_genre, rt2_genre,
                    douban_language, rt2_language, backdrop_path, poster_path
                ) = row

                # --- 业务逻辑处理 ---
                
                director_main = extract_top_names(imdb_director_names)
                if not director_main:
                    director_main = deduplicate_names(metacritic_director, rt_director, rt2_director)
                    if director_main:
                        director_main = '/'.join([n for n, _ in Counter(director_main.split('/')).most_common(2)])

                writer_main = extract_top_names(imdb_writer_names)
                if not writer_main:
                    writer_main = deduplicate_names(metacritic_writer, rt_writers, rt2_writer)
                    if writer_main:
                        writer_main = '/'.join([n for n, _ in Counter(writer_main.split('/')).most_common(2)])

                movie_name = deduplicate_names(ch_name, original_name, imdb_other_titles, aname, chsname, staticdouban_name, rotomatoes2_title)
                intro_eng = deduplicate_names(metacritic_desc, rt_movie_info)
                premiere_date_alter = get_most_frequent_date([premiere_date, douban_premiere_date, rt_theater_date, staticdouban_release_date])
                
                durations = set()
                for d in [douban_duration, metacritic_duration, rt_duration, rt2_duration]:
                    m = parse_duration_to_minutes(d)
                    if m: durations.add(m)
                duration_alter = '/'.join(map(str, durations)) if durations else None
                
                genre = deduplicate_names(douban_genre, metacritic_genre, rt_genre, rt2_genre)
                language = deduplicate_names(douban_language, rt2_language)

                insert_row = (
                    douban_link, director_main, writer_main, douban_personnel,
                    tmdb_overview, douban_intro, intro_eng, rt_consensus,
                    backdrop_path, poster_path, movie_name, title, tmdb_id, imdb_tconst,
                    my_rating, my_watch_date, my_comment,
                    imdb_rating, metacritic_rating, rt_rating, rt_aud_rating, rt_status,
                    rt2_aud_score, rt2_tomatometer, tmdb_vote_avg, staticdouban_rating,
                    staticdouban_votes, imdb_votes, metacritic_votes, rt_critic_count, rt_aud_count,
                    tmdb_release_date, premiere_date_alter, rt_studio, rt2_distributor, douban_region,
                    duration, duration_alter, genre, language
                )
                
                batch_data.append(insert_row)
                
                if len(batch_data) >= BATCH_SIZE:
                    write_cursor.executemany(insert_sql, batch_data)
                    batch_data.clear()
                    pbar.update(BATCH_SIZE)
            
            if batch_data:
                write_cursor.executemany(insert_sql, batch_data)
                pbar.update(len(batch_data))
        
        conn.commit()
    
    logger.info("✅ 汇总表构建完成")
    gc.collect()

def print_summary():
    logger.info("\n" + "="*50)
    logger.info("📊 数据处理摘要")
    logger.info("="*50)
    
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM show_sql_table")
        count = cursor.fetchone()[0]
        logger.info(f"📌 总计处理电影: {count} 部")
        
        logger.info("\n📅 Top 5 电影年份分布:")
        cursor.execute("""
            SELECT STRFTIME('%Y', show_release_premiere_date_main) as yr, COUNT(*) as c
            FROM show_sql_table WHERE yr IS NOT NULL
            GROUP BY yr ORDER BY c DESC LIMIT 5
        """)
        for year, c in cursor.fetchall():
            logger.info(f"   - {year}: {c} 部")

    logger.info("\n✅ 全部流程执行完毕，数据库位置:")
    logger.info(f"   📂 {DB_FILE}")

def main():
    print(f"\n🎬 DoubanV2 Data ETL Tool")
    print(f"👤 用户: {USERNAME}")
    print("-" * 50)

    if not check_input_files():
        return

    if DB_FILE.exists():
        logger.warning(f"⚠️ 检测到旧数据库，正在删除: {DB_FILE}")
        try:
            DB_FILE.unlink()
        except PermissionError:
            logger.error("❌ 无法删除数据库文件，请确保文件未被占用。")
            return

    try:
        create_database_schema()
        import_csv_to_tables()
        create_summary_table()
        print_summary()
    except KeyboardInterrupt:
        logger.warning("\n⚠️ 用户强制中断操作")
        sys.exit(1)
    except Exception as e:
        logger.exception(f"❌ 未知错误: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()