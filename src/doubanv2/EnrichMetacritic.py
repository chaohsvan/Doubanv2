import pandas as pd
import logging
import re
import sys
import gc
import json
from tqdm import tqdm
from pathlib import Path
from typing import List, Optional, Dict, Any

# --- 1. 路径与常量配置 (Path & Configuration) ---

# 获取当前脚本的绝对路径
CURRENT_SCRIPT = Path(__file__).resolve()
# 回溯两级目录获取项目根目录 (src/doubanv2_test/EnrichMetacritic.py -> ProjectRoot)
PROJECT_ROOT = CURRENT_SCRIPT.parents[2]

RESOURCES_DIR = PROJECT_ROOT / "resources"
CONFIG_PATH = RESOURCES_DIR / "config.json"
STATIC_DB_DIR = RESOURCES_DIR / "StaticMovieDB"
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
USER_LOG_DIR = USER_SPECIFIC_DIR / "log"
USER_DB_DIR = USER_SPECIFIC_DIR / "DBgenerate"
USER_ENRICHED_DIR = USER_SPECIFIC_DIR / "enriched_movies"

# 文件路径配置
FILE_PATHS = {
    # 用户特定输入
    "base_db": USER_DB_DIR / "douban_movies.csv",
    # 共享静态输入
    "meta_db": STATIC_DB_DIR / "metacritic_16k_Movies.csv"
}

# 用户特定输出
OUTPUT_PATH = USER_ENRICHED_DIR / "douban_movies_metacritic_enriched.csv"

# Metacritic 配置
META_PREFIX = 'metacritic_'
META_ENRICH_COLS = [
    'Description',
    'Rating',
    'No of Persons Voted',
    'Directed by',
    'Written by',
    'Duration',
    'Genres'
]

# --- 2. 日志配置 (Logging) ---

def setup_logging(log_dir: Path) -> logging.Logger:
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / 'metacritic_enrichment.log'

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
        handlers=[
            logging.FileHandler(log_file, encoding='utf-8'),
            logging.StreamHandler(sys.stdout)
        ]
    )
    return logging.getLogger(__name__)

# 使用用户日志目录
logger = setup_logging(USER_LOG_DIR)

# --- 3. 辅助函数 (Helpers) ---

def check_input_files(paths: Dict[str, Path]) -> bool:
    """检查所有必需的输入文件是否存在"""
    missing = []
    for name, path in paths.items():
        if not path.exists():
            missing.append(f"{name}: {path}")

    if missing:
        logger.error("FATAL: The following required files are missing:")
        for m in missing:
            logger.error(f"  - {m}")
        return False
    return True

def safe_extract_year(series: pd.Series) -> pd.Series:
    """从各种日期格式中稳健地提取年份"""
    s_str = series.astype(str)
    # 匹配 YYYY 格式的年份
    year_match = s_str.str.extract(r'(\d{4})', expand=False)
    return pd.to_numeric(year_match, errors='coerce')

# --- 4. 数据加载与预处理 (Load & Prep) ---

def load_base_db(path: Path) -> Optional[pd.DataFrame]:
    """加载基础 Douban 数据库"""
    logger.info(f"Loading base DB: {path}")
    try:
        df = pd.read_csv(path, encoding='utf-8-sig')
        required_cols = {'ch_name', 'original_name', 'year'}

        if not required_cols.issubset(df.columns):
            missing = required_cols - set(df.columns)
            logger.error(f"FATAL: Base DB missing columns: {missing}")
            return None
        return df
    except Exception as e:
        logger.error(f"Error loading base DB: {e}")
        return None

def load_and_prep_metacritic(path: Path, columns_to_keep: List[str], prefix: str) -> Optional[pd.DataFrame]:
    """加载并预处理 Metacritic 数据"""
    logger.info(f"Loading Metacritic DB: {path}")

    try:
        # 优化：只读取需要的列 (Title, Release Date + enrich cols) 以节省内存
        # cols_to_read = ['Title', 'Release Date'] + [c for c in columns_to_keep]
        # 为了稳健性，读取全部，后续再筛选
        df = pd.read_csv(path)

        # 1. 提取年份
        if 'Release Date' in df.columns:
            df['meta_year'] = safe_extract_year(df['Release Date'])
        else:
            logger.warning("'Release Date' not found in Metacritic DB, year matching may fail.")
            df['meta_year'] = pd.NA

        # 2. 解析 "Name (Year)" 格式
        # 优化正则：编译正则表达式提高效率
        title_regex = re.compile(r'^(.*?)\s*\((\d{4})\)$')

        extracted = df['Title'].astype(str).str.extract(title_regex, expand=True)
        df['meta_title_from_title'] = extracted[0].str.strip()
        df['meta_year_from_title'] = pd.to_numeric(extracted[1], errors='coerce')

        # 3. 创建干净 Title
        df['meta_title'] = df['meta_title_from_title'].fillna(df['Title']).str.strip()

        # 4. 重命名并筛选列
        prefixed_map = {}
        final_cols = [
            'meta_title', 'meta_year',
            'meta_title_from_title', 'meta_year_from_title'
        ]

        for col in columns_to_keep:
            if col in df.columns:
                new_name = f"{prefix}{col}"
                prefixed_map[col] = new_name
                final_cols.append(new_name)

        df.rename(columns=prefixed_map, inplace=True)

        # 返回去重后的列
        return df[list(dict.fromkeys(final_cols))]

    except Exception as e:
        logger.error(f"Error loading Metacritic DB: {e}")
        return None

# --- 5. 核心匹配逻辑 (Core Matching Logic) ---

def find_match_with_priority(douban_row: pd.Series, df_meta: pd.DataFrame, all_meta_cols: List[str]) -> pd.Series:
    """为单行 Douban 数据执行 5 步匹配"""
    ch_name = douban_row.get('ch_name')
    orig_name = douban_row.get('original_name')
    year = douban_row.get('year')

    # 预先定义空结果
    empty_result = pd.Series([pd.NA] * len(all_meta_cols), index=all_meta_cols)

    # 辅助函数：快速检查并返回
    def get_result(mask):
        # 这是一个 View，不会导致拷贝，速度较快
        matches = df_meta[mask]
        if not matches.empty:
            return matches.iloc[0][all_meta_cols]
        return None

    # 1. ch_name + year
    if pd.notna(ch_name) and pd.notna(year):
        res = get_result((df_meta['meta_title'] == ch_name) & (df_meta['meta_year'] == year))
        if res is not None: return res

    # 2. orig_name + year
    if pd.notna(orig_name) and pd.notna(year):
        res = get_result((df_meta['meta_title'] == orig_name) & (df_meta['meta_year'] == year))
        if res is not None: return res

    # 3. ch_name only
    if pd.notna(ch_name):
        res = get_result(df_meta['meta_title'] == ch_name)
        if res is not None: return res

    # 4. orig_name only
    if pd.notna(orig_name):
        res = get_result(df_meta['meta_title'] == orig_name)
        if res is not None: return res

    # 5. "Name (Year)" match
    if pd.notna(year):
        # 先基于年份过滤 (大幅减小搜索空间)
        year_mask = df_meta['meta_year_from_title'] == year
        subset = df_meta[year_mask]

        if not subset.empty:
            if pd.notna(ch_name):
                matches = subset[subset['meta_title_from_title'] == ch_name]
                if not matches.empty:
                    return matches.iloc[0][all_meta_cols]

            if pd.notna(orig_name):
                matches = subset[subset['meta_title_from_title'] == orig_name]
                if not matches.empty:
                    return matches.iloc[0][all_meta_cols]

    return empty_result

# --- 6. 主执行函数 (Main) ---

def main():
    print(f"👤 当前用户: {USERNAME}")
    logger.info("--- Metacritic Enrichment Pipeline (Optimized) Started ---")

    # 0. 检查文件
    if not check_input_files(FILE_PATHS):
        return

    # 1. 加载 Metacritic
    df_meta = load_and_prep_metacritic(FILE_PATHS['meta_db'], META_ENRICH_COLS, META_PREFIX)
    if df_meta is None:
        return

    # 2. 加载 Douban
    df_base = load_base_db(FILE_PATHS['base_db'])
    if df_base is None:
        return

    logger.info(f"Base DB: {len(df_base)} rows | Metacritic DB: {len(df_meta)} rows")

    # 3. 执行匹配
    logger.info("Starting 5-step prioritized matching...")

    meta_cols_to_add = [col for col in df_meta.columns if col.startswith(META_PREFIX)]

    # 开启进度条
    tqdm.pandas(desc="Matching")

    # 优化：将 df_meta 设为 global 或传入闭包可能更快，但在 Pandas Apply 中传参是标准做法
    enrich_data = df_base.progress_apply(
        lambda row: find_match_with_priority(row, df_meta, meta_cols_to_add),
        axis=1
    )

    # 4. 合并结果
    logger.info("Merging results...")
    df_final = pd.concat([df_base, enrich_data], axis=1)

    # 显式清理内存
    del df_base, df_meta, enrich_data
    gc.collect()

    # 5. 保存
    try:
        OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
        df_final.to_csv(OUTPUT_PATH, index=False, encoding='utf-8-sig')
        logger.info(f"Successfully saved {len(df_final)} rows to: {OUTPUT_PATH}")
    except Exception as e:
        logger.error(f"Failed to save output: {e}")

    logger.info("--- Pipeline Finished ---")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logger.warning("Process interrupted by user.")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Unhandled exception: {e}", exc_info=True)
        sys.exit(1)