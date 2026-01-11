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
# 回溯两级目录获取项目根目录 (src/doubanv2/EnrichRottenTomatoes1.py -> ProjectRoot)
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

# 集中管理文件路径
FILE_PATHS = {
    # 用户数据
    "base_db": USER_DB_DIR / "douban_movies.csv",
    # 静态数据库 (共享)
    "rt1_db": STATIC_DB_DIR / "Rotten Tomatoes Movies.csv"
}

# 输出路径
OUTPUT_PATH = USER_ENRICHED_DIR / "douban_movies_rt1_enriched.csv"

# RT1 配置
RT1_PREFIX = 'RottenTomatoes_'
RT1_ENRICH_COLS = [
    'movie_info', 'critics_consensus', 'genre', 'directors', 'writers',
    'in_theaters_date', 'runtime_in_minutes', 'studio_name',
    'tomatometer_status', 'tomatometer_rating', 'tomatometer_count',
    'audience_rating', 'audience_count'
]

# 预编译正则 (性能优化)
REGEX_YEAR = re.compile(r'(\d{4})')
REGEX_TITLE_PARSE = re.compile(r'^(.*?)\s*\((\d{4})\)$')

# --- 2. 日志配置 (Logging) ---

def setup_logging(log_dir: Path) -> logging.Logger:
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / 'rt1_enrichment.log'

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
    year_match = s_str.str.extract(REGEX_YEAR, expand=False)
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

def load_and_prep_rotten_tomatoes_1(path: Path, columns_to_keep: List[str], prefix: str) -> Optional[pd.DataFrame]:
    """加载并预处理 RT1 数据"""
    logger.info(f"Loading RT1 DB: {path}")

    try:
        df = pd.read_csv(path)

        # 1. 提取年份
        if 'in_theaters_date' in df.columns:
            df['rt1_year'] = safe_extract_year(df['in_theaters_date'])
        else:
            logger.warning("'in_theaters_date' not found, year matching may be limited.")
            df['rt1_year'] = pd.NA

        # 2. 解析 Title (Name + Year)
        if 'movie_title' in df.columns:
            extracted_parts = df['movie_title'].str.extract(REGEX_TITLE_PARSE, expand=True)
            df['rt1_title_from_title'] = extracted_parts[0].str.strip()
            df['rt1_year_from_title'] = pd.to_numeric(extracted_parts[1], errors='coerce')

            # 3. 创建干净 Title
            df['rt1_title'] = df['rt1_title_from_title'].fillna(df['movie_title']).str.strip()
        else:
            logger.error("FATAL: 'movie_title' column missing in RT1 DB.")
            return None

        # 4. 重命名列并筛选
        prefixed_map = {}
        final_cols = [
            'rt1_title', 'rt1_year',
            'rt1_title_from_title', 'rt1_year_from_title'
        ]

        for col in columns_to_keep:
            if col in df.columns:
                new_name = f"{prefix}{col}"
                prefixed_map[col] = new_name
                final_cols.append(new_name)
            else:
                # 记录警告但不中断，允许部分列缺失
                logger.debug(f"Optional column '{col}' not found in RT1.")

        df.rename(columns=prefixed_map, inplace=True)

        # 去重保留唯一列名
        return df[list(dict.fromkeys(final_cols))]

    except Exception as e:
        logger.error(f"Error loading RT1 DB: {e}")
        return None

# --- 5. 核心匹配逻辑 (Core Matching Logic) ---

def find_match_with_priority(douban_row: pd.Series, df_rt1: pd.DataFrame, all_rt1_cols: List[str]) -> pd.Series:
    """为单行 Douban 数据执行 5 步匹配"""
    ch_name = douban_row.get('ch_name')
    orig_name = douban_row.get('original_name')
    year = douban_row.get('year')

    # 预定义空结果 (性能优化)
    empty_result = pd.Series([pd.NA] * len(all_rt1_cols), index=all_rt1_cols)

    # 辅助内部函数：利用 Boolean Mask 快速筛选
    def get_match(mask):
        subset = df_rt1[mask]
        if not subset.empty:
            return subset.iloc[0][all_rt1_cols]
        return None

    # 1. ch_name + year
    if pd.notna(ch_name) and pd.notna(year):
        res = get_match((df_rt1['rt1_title'] == ch_name) & (df_rt1['rt1_year'] == year))
        if res is not None: return res

    # 2. orig_name + year
    if pd.notna(orig_name) and pd.notna(year):
        res = get_match((df_rt1['rt1_title'] == orig_name) & (df_rt1['rt1_year'] == year))
        if res is not None: return res

    # 3. ch_name only
    if pd.notna(ch_name):
        res = get_match(df_rt1['rt1_title'] == ch_name)
        if res is not None: return res

    # 4. orig_name only
    if pd.notna(orig_name):
        res = get_match(df_rt1['rt1_title'] == orig_name)
        if res is not None: return res

    # 5. "Name (Year)" 格式匹配
    if pd.notna(year):
        # 先基于年份大幅缩小搜索范围
        year_subset = df_rt1[df_rt1['rt1_year_from_title'] == year]

        if not year_subset.empty:
            if pd.notna(ch_name):
                matches = year_subset[year_subset['rt1_title_from_title'] == ch_name]
                if not matches.empty:
                    return matches.iloc[0][all_rt1_cols]

            if pd.notna(orig_name):
                matches = year_subset[year_subset['rt1_title_from_title'] == orig_name]
                if not matches.empty:
                    return matches.iloc[0][all_rt1_cols]

    return empty_result

# --- 6. 主执行函数 (Main) ---

def main():
    print(f"👤 当前用户: {USERNAME}")
    logger.info("--- Rotten Tomatoes (RT1) Enrichment Pipeline (Optimized) Started ---")

    # 0. 文件检查
    if not check_input_files(FILE_PATHS):
        return

    # 1. 加载 RT1
    df_rt1 = load_and_prep_rotten_tomatoes_1(FILE_PATHS['rt1_db'], RT1_ENRICH_COLS, RT1_PREFIX)
    if df_rt1 is None:
        return

    # 2. 加载 Douban
    df_base = load_base_db(FILE_PATHS['base_db'])
    if df_base is None:
        return

    logger.info(f"Base DB: {len(df_base)} rows | RT1 DB: {len(df_rt1)} rows")
    logger.info("Starting matching process...")

    rt1_cols_to_add = [col for col in df_rt1.columns if col.startswith(RT1_PREFIX)]

    # 3. 执行匹配
    tqdm.pandas(desc="Enriching (RT1)")
    enrich_data = df_base.progress_apply(
        lambda row: find_match_with_priority(row, df_rt1, rt1_cols_to_add),
        axis=1
    )

    # 4. 合并与清理
    logger.info("Merging results...")
    df_final = pd.concat([df_base, enrich_data], axis=1)

    # 显式释放内存
    del df_base, df_rt1, enrich_data
    gc.collect()

    # 5. 保存结果
    try:
        OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
        df_final.to_csv(OUTPUT_PATH, index=False, encoding='utf-8-sig')
        logger.info(f"✅ Successfully saved {len(df_final)} rows to: {OUTPUT_PATH}")
    except Exception as e:
        logger.error(f"❌ Failed to save output: {e}")

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