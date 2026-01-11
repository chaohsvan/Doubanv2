# -*- coding: utf-8 -*-
"""
doubanv2_enrich_tsv_streaming.py

完整、可运行、流式（chunksize）优化版的 IMDB TSV 丰富脚本。
优化说明：
- 使用 pathlib 全面替换 os.path，增强跨平台兼容性。
- 优化 I/O 路径管理和日志配置。
- 保持流式处理逻辑，优化内存管理。
- 支持多用户目录隔离。
"""

from __future__ import annotations
import argparse
import logging
import math
import re
import sys
import gc
import json
from collections import defaultdict
from typing import Dict, Tuple, Optional, Any, Set, List
from pathlib import Path

import pandas as pd
from tqdm import tqdm

# -----------------------------
# 1. Path & Config Management
# -----------------------------

# 获取当前脚本的绝对路径
CURRENT_SCRIPT = Path(__file__).resolve()
# 回溯两级目录获取项目根目录 (src/doubanv2/EnrichImdb.py -> ProjectRoot)
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

# 输入文件路径配置
FILE_PATHS = {
    # --- 用户特定路径 ---
    "base_db": USER_DB_DIR / "douban_movies.csv",
    
    # --- 全局共享静态库 (保持不变) ---
    "tsv_basics": STATIC_DB_DIR / "title.basics.tsv",
    "tsv_ratings": STATIC_DB_DIR / "title.ratings.tsv",
    "tsv_crew": STATIC_DB_DIR / "title.crew.tsv",
    "tsv_akas": STATIC_DB_DIR / "title.akas.tsv",
    "tsv_names": STATIC_DB_DIR / "name.basics.tsv",
}

# 输出文件路径 (用户特定)
OUTPUT_PATH = USER_ENRICHED_DIR / "douban_movies_Imdb_enriched.csv"

# -----------------------------
# 2. Logging Setup
# -----------------------------
def setup_logging(log_dir: Path) -> logging.Logger:
    # 确保日志目录存在
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / 'imdb_tsv_enrichment_streaming.log'

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

# -----------------------------
# 3. Utility helpers
# -----------------------------

def _norm_title(s: Any) -> Optional[str]:
    """规范化标题：去首尾空白并小写；None/NaN -> None"""
    if pd.isna(s):
        return None
    t = str(s).strip()
    if not t:
        return None
    # collapse whitespace and lowercase for matching
    return re.sub(r'\s+', ' ', t).lower()


def _to_int_year(v: Any) -> Optional[int]:
    """从 startYear 字段（可能为字符串、float）解析成 int 或 None"""
    try:
        if pd.isna(v):
            return None
        iv = int(float(v))
        return iv if iv > 0 else None
    except (ValueError, TypeError):
        return None


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

# -----------------------------
# 4. Streamed builders
# -----------------------------

def stream_build_ratings_map(tsv_path: Path, chunksize: int = 100_000) -> Dict[str, Tuple[Optional[float], Optional[int]]]:
    logger.info(f"Streaming ratings -> map: {tsv_path.name}")
    ratings: Dict[str, Tuple[Optional[float], Optional[int]]] = {}

    try:
        for chunk in pd.read_csv(tsv_path, sep='\t', usecols=['tconst', 'averageRating', 'numVotes'],
                                 na_values='\\N', chunksize=chunksize, dtype={'tconst': str}):
            # 向量化处理可能比迭代更快，但为了保持逻辑一致性和内存控制，保持原有迭代逻辑
            for r in chunk.itertuples(index=False):
                avg = None if pd.isna(r.averageRating) else float(r.averageRating)
                votes = None
                if not pd.isna(r.numVotes):
                    try:
                        votes = int(r.numVotes)
                    except ValueError:
                        votes = None
                ratings[r.tconst] = (avg, votes)
    except Exception as e:
        logger.error(f"Error reading ratings TSV: {e}")
        raise

    logger.info(f"Ratings map size: {len(ratings)}")
    return ratings


def stream_build_crew_map(tsv_path: Path, chunksize: int = 100_000) -> Dict[str, Dict[str, Optional[str]]]:
    logger.info(f"Streaming crew -> map: {tsv_path.name}")
    crew: Dict[str, Dict[str, Optional[str]]] = {}

    try:
        for chunk in pd.read_csv(tsv_path, sep='\t', usecols=['tconst', 'directors', 'writers'],
                                 na_values='\\N', chunksize=chunksize, dtype={'tconst': str, 'directors': str, 'writers': str}):
            for r in chunk.itertuples(index=False):
                crew[r.tconst] = {
                    'directors': None if pd.isna(r.directors) else str(r.directors),
                    'writers': None if pd.isna(r.writers) else str(r.writers)
                }
    except Exception as e:
        logger.error(f"Error reading crew TSV: {e}")
        raise

    logger.info(f"Crew map size: {len(crew)}")
    return crew


def stream_aggregate_akas(tsv_path: Path, chunksize: int = 100_000) -> Dict[str, str]:
    logger.info(f"Streaming akas -> aggregate map: {tsv_path.name}")
    tmp = defaultdict(set)

    try:
        for chunk in pd.read_csv(tsv_path, sep='\t', usecols=['titleId', 'title'],
                                 na_values='\\N', chunksize=chunksize, dtype={'titleId': str, 'title': str}):
            # 过滤掉无效的 title
            valid_rows = chunk.dropna(subset=['title'])
            for r in valid_rows.itertuples(index=False):
                t = str(r.title).strip()
                if t:
                    tmp[r.titleId].add(t)
    except Exception as e:
        logger.error(f"Error reading akas TSV: {e}")
        raise

    # 转换为最终字典
    akas_map = {tid: ' | '.join(sorted(list(titles))) for tid, titles in tmp.items()}
    logger.info(f"AKAS aggregated entries: {len(akas_map)}")
    return akas_map


def stream_build_basics_index(tsv_path: Path, chunksize: int = 100_000) -> Dict[Tuple[Optional[str], Optional[int]], list]:
    logger.info(f"Streaming basics -> building title-year index: {tsv_path.name}")
    index = defaultdict(list)

    try:
        for chunk in pd.read_csv(tsv_path, sep='\t', usecols=['tconst', 'primaryTitle', 'originalTitle', 'startYear'],
                                 na_values='\\N', chunksize=chunksize, dtype={'tconst': str, 'primaryTitle': str, 'originalTitle': str}):
            chunk['startYear'] = pd.to_numeric(chunk['startYear'], errors='coerce')

            for r in chunk.itertuples(index=False):
                year = _to_int_year(r.startYear)

                # Index by Primary Title
                p = _norm_title(r.primaryTitle)
                if p is not None:
                    index[(p, year)].append({
                        'tconst': r.tconst,
                        'primaryTitle': r.primaryTitle,
                        'originalTitle': r.originalTitle,
                        'startYear': year
                    })

                # Index by Original Title (if different)
                o = _norm_title(r.originalTitle)
                if o is not None and o != p:
                    index[(o, year)].append({
                        'tconst': r.tconst,
                        'primaryTitle': r.primaryTitle,
                        'originalTitle': r.originalTitle,
                        'startYear': year
                    })
    except Exception as e:
        logger.error(f"Error reading basics TSV: {e}")
        raise

    logger.info(f"Built basics index entries: {len(index)}")
    return index


def stream_build_name_map_for_ids(tsv_path: Path, needed_ids_set: Set[str], chunksize: int = 100_000) -> Dict[str, str]:
    """只从 name.basics.tsv 中挑出需要的 nconst（按需加载）"""
    logger.info(f"Streaming names -> building partial name map: {tsv_path.name}")
    name_map: Dict[str, str] = {}

    if not needed_ids_set:
        return name_map

    try:
        for chunk in pd.read_csv(tsv_path, sep='\t', usecols=['nconst', 'primaryName'],
                                 na_values='\\N', chunksize=chunksize, dtype={'nconst': str, 'primaryName': str}):
            mask = chunk['nconst'].isin(needed_ids_set)
            if not mask.any():
                continue

            for r in chunk[mask].itertuples(index=False):
                name_map[r.nconst] = r.primaryName

            if len(name_map) >= len(needed_ids_set):
                logger.info("Collected all required names, stopping scan.")
                break
    except Exception as e:
        logger.error(f"Error reading names TSV: {e}")
        raise

    logger.info(f"Name map size (partial): {len(name_map)}")
    return name_map


# -----------------------------
# 5. Matching logic
# -----------------------------

def _assemble_match_series(tconst: str, crew_map: Dict, ratings_map: Dict, akas_map: Dict) -> pd.Series:
    """Helper to create result row"""
    avg, votes = ratings_map.get(tconst, (None, None))
    crew = crew_map.get(tconst, {'directors': None, 'writers': None})
    other_titles = akas_map.get(tconst, None)

    return pd.Series({
        'tconst': tconst,
        'averageRating': avg,
        'numVotes': votes,
        'directors': crew.get('directors'),
        'writers': crew.get('writers'),
        'imdb_other_titles': other_titles
    })


def find_imdb_match_priority_stream(douban_row: pd.Series, basics_index: Dict, ratings_map: Dict, crew_map: Dict, akas_map: Dict) -> pd.Series:
    ch_name = douban_row.get('ch_name')
    orig_name = douban_row.get('original_name')
    year = douban_row.get('year')

    if pd.isna(year):
        return pd.Series(dtype=object)

    year_int = _to_int_year(year)

    def candidates_for(title: Any) -> List[Dict]:
        if title is None or pd.isna(title):
            return []
        key = (_norm_title(title), year_int)
        return basics_index.get(key, [])

    # Priority 1: Chinese Name
    if pd.notna(ch_name):
        cands = candidates_for(ch_name)
        if cands:
            return _assemble_match_series(cands[0]['tconst'], crew_map, ratings_map, akas_map)

    # Priority 2: Original Name
    if pd.notna(orig_name):
        cands = candidates_for(orig_name)
        if cands:
            return _assemble_match_series(cands[0]['tconst'], crew_map, ratings_map, akas_map)

    return pd.Series(dtype=object)


def map_ids_to_names(id_string: Optional[str], name_map: Dict[str, str]) -> Optional[str]:
    if pd.isna(id_string) or not id_string:
        return None
    ids = str(id_string).split(',')
    # 使用列表推导式处理，去空
    names = [name_map.get(i.strip(), i.strip()) for i in ids if i.strip()]
    return ' | '.join(names) if names else None


# -----------------------------
# 6. Main Execution Flow
# -----------------------------

def load_and_prep_tsv_data_stream(chunksize: int = 100_000) -> Tuple[Optional[Dict], Optional[Dict], Optional[Dict], Optional[Dict]]:
    logger.info(f"Starting TSV streaming load (chunksize={chunksize})...")
    try:
        basics_index = stream_build_basics_index(FILE_PATHS['tsv_basics'], chunksize)
        ratings_map = stream_build_ratings_map(FILE_PATHS['tsv_ratings'], chunksize)
        crew_map = stream_build_crew_map(FILE_PATHS['tsv_crew'], chunksize)
        akas_map = stream_aggregate_akas(FILE_PATHS['tsv_akas'], chunksize)

        logger.info("TSV streaming load finished.")
        return basics_index, ratings_map, crew_map, akas_map
    except Exception as e:
        logger.error(f"Fatal error during TSV loading: {e}")
        return None, None, None, None


def load_base_db(path: Path) -> Optional[pd.DataFrame]:
    logger.info(f"Loading base DB: {path}")
    if not path.exists():
        logger.error(f"FATAL: Base DB file not found: {path}")
        return None
    try:
        df = pd.read_csv(path, encoding='utf-8-sig')
        required = {'ch_name', 'original_name', 'year', 'link'}
        if not required.issubset(set(df.columns)):
            logger.error(f"FATAL: Missing columns: {required - set(df.columns)}")
            return None
        return df
    except Exception as e:
        logger.error(f"Error loading base DB: {e}")
        return None


def main(chunksize: int = 100_000):
    print(f"👤 当前用户: {USERNAME}")
    logger.info("--- IMDB TSV Enrichment Pipeline (Streaming, Incremental) Started ---")

    # 0. Check Files
    if not check_input_files(FILE_PATHS):
        return

    # 1. Load Base DB
    df_base = load_base_db(FILE_PATHS['base_db'])
    if df_base is None:
        return

    # 2. Incremental Logic
    processed_links_set: Set[str] = set()
    df_existing_enriched = pd.DataFrame()

    if OUTPUT_PATH.exists():
        try:
            logger.info(f"Loading existing enriched file: {OUTPUT_PATH}")
            df_existing_enriched = pd.read_csv(OUTPUT_PATH, encoding='utf-8-sig', low_memory=False)
            if 'link' in df_existing_enriched.columns:
                processed_links_set = set(df_existing_enriched['link'].dropna().astype(str))
                logger.info(f"Found {len(processed_links_set)} processed links.")
            else:
                logger.warning("'link' column missing in output. Re-processing all.")
                df_existing_enriched = pd.DataFrame()
        except Exception as e:
            logger.warning(f"Failed to load existing output: {e}. Re-processing all.")
            df_existing_enriched = pd.DataFrame()

    # Filter new items
    if processed_links_set:
        mask = ~df_base['link'].astype(str).isin(processed_links_set)
        df_to_process = df_base[mask].copy()
    else:
        df_to_process = df_base.copy()

    # Cleanup base df
    del df_base
    gc.collect()

    if df_to_process.empty:
        logger.info("No new items to process. Exiting.")
        return

    logger.info(f"Found {len(df_to_process)} new items to enrich.")

    # 3. Load TSV Data (Heavy Lifting)
    basics_index, ratings_map, crew_map, akas_map = load_and_prep_tsv_data_stream(chunksize)
    if basics_index is None:
        return

    # 4. Matching (Phase 1)
    logger.info("Starting matching process...")
    tqdm.pandas(desc="Matching")
    matched_data = df_to_process.progress_apply(
        lambda row: find_imdb_match_priority_stream(row, basics_index, ratings_map, crew_map, akas_map),
        axis=1
    )

    # Cleanup heavy indexes
    del basics_index, ratings_map, crew_map, akas_map
    gc.collect()
    logger.info("Released TSV indexes from memory.")

    # 5. Name Resolution (Phase 2)
    needed_ids: Set[str] = set()
    for col in ['directors', 'writers']:
        if col in matched_data.columns:
            for ids in matched_data[col].dropna().astype(str):
                for i in ids.split(','):
                    if i.strip():
                        needed_ids.add(i.strip())

    logger.info(f"Resolving names for {len(needed_ids)} IDs...")
    name_map = stream_build_name_map_for_ids(FILE_PATHS['tsv_names'], needed_ids, chunksize)

    if 'directors' in matched_data.columns:
        matched_data['imdb_director_names'] = matched_data['directors'].apply(lambda x: map_ids_to_names(x, name_map))
    if 'writers' in matched_data.columns:
        matched_data['imdb_writer_names'] = matched_data['writers'].apply(lambda x: map_ids_to_names(x, name_map))

    del name_map, needed_ids
    gc.collect()

    # 6. Final Cleanup & Formatting
    rename_map = {
        'tconst': 'imdb_tconst',
        'averageRating': 'imdb_averageRating',
        'numVotes': 'imdb_numVotes',
        'directors': 'imdb_directors_ids',
        'writers': 'imdb_writers_ids'
    }
    matched_data.rename(columns=rename_map, inplace=True)

    final_cols = [
        'imdb_tconst', 'imdb_averageRating', 'imdb_numVotes',
        'imdb_other_titles', 'imdb_director_names', 'imdb_writer_names',
        'imdb_directors_ids', 'imdb_writers_ids'
    ]
    # Keep only existing columns
    final_cols = [c for c in final_cols if c in matched_data.columns]
    matched_data = matched_data[final_cols]

    # 7. Merge & Save
    logger.info("Merging results...")
    df_new_full = pd.concat([df_to_process.reset_index(drop=True), matched_data.reset_index(drop=True)], axis=1)

    del df_to_process, matched_data
    gc.collect()

    logger.info("Appending to final file...")
    df_final = pd.concat([df_existing_enriched, df_new_full], ignore_index=True)

    del df_existing_enriched, df_new_full
    gc.collect()

    try:
        OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
        df_final.to_csv(OUTPUT_PATH, index=False, encoding='utf-8-sig')
        logger.info(f"Successfully saved {len(df_final)} rows to {OUTPUT_PATH}")
    except Exception as e:
        logger.error(f"Failed to save output: {e}")

    del df_final
    gc.collect()
    logger.info("--- Pipeline Finished Successfully ---")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Enrich Douban DB with IMDb TSV data (Streaming).")
    parser.add_argument("-c", "--chunksize", type=int, default=100_000, help="Chunk size for TSV processing")
    args = parser.parse_args()

    try:
        main(chunksize=args.chunksize)
    except KeyboardInterrupt:
        logger.warning("Process interrupted by user.")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Unhandled exception: {e}", exc_info=True)
        sys.exit(1)