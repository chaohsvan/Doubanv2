import pandas as pd
import logging
import re
import sys
import gc
import json
from tqdm import tqdm
from pathlib import Path
from typing import List, Optional, Dict, Any

# --- 1. Path & Configuration ---

# Get current script path and resolve Project Root
CURRENT_SCRIPT = Path(__file__).resolve()
PROJECT_ROOT = CURRENT_SCRIPT.parents[2]

RESOURCES_DIR = PROJECT_ROOT / "resources"
CONFIG_PATH = RESOURCES_DIR / "config.json"
STATIC_DB_DIR = RESOURCES_DIR / "StaticMovieDB"
USERDATA_ROOT = RESOURCES_DIR / "UserData"

# --- Dynamic Config Loading ---

def load_initial_config(config_path: Path) -> Dict[str, Any]:
    """Load config to get username."""
    if not config_path.exists():
        print(f"❌ Config file not found: {config_path}")
        sys.exit(1)
    try:
        with config_path.open('r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"❌ Failed to load config: {e}")
        sys.exit(1)

# Load Config & Username
GLOBAL_CONFIG = load_initial_config(CONFIG_PATH)
USERNAME = GLOBAL_CONFIG.get('douban_username')

if not USERNAME:
    print("❌ Error: 'douban_username' is empty in config.")
    sys.exit(1)

# Construct User-Specific Paths
USER_SPECIFIC_DIR = USERDATA_ROOT / USERNAME
USER_LOG_DIR = USER_SPECIFIC_DIR / "log"
USER_DB_DIR = USER_SPECIFIC_DIR / "DBgenerate"
USER_ENRICHED_DIR = USER_SPECIFIC_DIR / "enriched_movies"

# Centralized File Paths
FILE_PATHS = {
    # User Input
    "base_db": USER_DB_DIR / "douban_movies.csv",
    # Shared Static Input
    "rt2_db": STATIC_DB_DIR / "rotten_tomatoes_movies.csv"
}

# User Output
OUTPUT_PATH = USER_ENRICHED_DIR / "douban_movies_rt2_enriched.csv"

# RT2 Configuration
RT2_PREFIX = 'rotomatoes2_'
RT2_ENRICH_COLS = [
    'title',
    'audienceScore',
    'tomatoMeter',
    'releaseDateTheaters',
    'runtimeMinutes',
    'genre',
    'originalLanguage',
    'director',
    'writer',
    'distributor'
]

# Pre-compiled Regex for performance
REGEX_YEAR = re.compile(r'(\d{4})')
REGEX_TITLE_PARSE = re.compile(r'^(.*?)\s*\((\d{4})\)$')

# --- 2. Logging Setup ---

def setup_logging(log_dir: Path) -> logging.Logger:
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / 'rt2_enrichment.log'

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

# Use User Log Directory
logger = setup_logging(USER_LOG_DIR)

# --- 3. Helper Functions ---

def check_input_files(paths: Dict[str, Path]) -> bool:
    """Check if all required input files exist."""
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
    """Robustly extract year from various date formats."""
    s_str = series.astype(str)
    year_match = s_str.str.extract(REGEX_YEAR, expand=False)
    return pd.to_numeric(year_match, errors='coerce')

# --- 4. Data Loading & Prep ---

def load_base_db(path: Path) -> Optional[pd.DataFrame]:
    """Load Base Douban Database."""
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

def load_and_prep_rotten_tomatoes_2(path: Path, columns_to_keep: List[str], prefix: str) -> Optional[pd.DataFrame]:
    """
    Load and prepare RT2 data.
    1. Extract year from releaseDateTheaters (rt2_year).
    2. Parse 'title' (e.g., "Name (YYYY)") into name and year.
    3. Create a clean match title (rt2_match_title).
    """
    logger.info(f"Loading RT2 DB: {path}")

    try:
        df = pd.read_csv(path)

        # 1. Extract Year
        if 'releaseDateTheaters' in df.columns:
            df['rt2_year'] = safe_extract_year(df['releaseDateTheaters'])
        else:
            logger.warning("'releaseDateTheaters' not found, year matching limited.")
            df['rt2_year'] = pd.NA

        # 2. Parse Title (Name + Year)
        if 'title' in df.columns:
            extracted_parts = df['title'].str.extract(REGEX_TITLE_PARSE, expand=True)
            df['rt2_title_from_title'] = extracted_parts[0].str.strip()
            df['rt2_year_from_title'] = pd.to_numeric(extracted_parts[1], errors='coerce')

            # 3. Create clean match title
            df['rt2_match_title'] = df['rt2_title_from_title'].fillna(df['title']).str.strip()
        else:
            logger.error("FATAL: 'title' column missing in RT2 DB.")
            return None

        # 4. Rename and Filter Columns
        prefixed_map = {}
        final_cols = [
            'rt2_match_title', 'rt2_year',
            'rt2_title_from_title', 'rt2_year_from_title'
        ]

        for col in columns_to_keep:
            if col in df.columns:
                new_name = f"{prefix}{col}"
                prefixed_map[col] = new_name
                final_cols.append(new_name)
            else:
                logger.debug(f"Optional column '{col}' not found in RT2.")

        df.rename(columns=prefixed_map, inplace=True)

        # Return unique columns
        return df[list(dict.fromkeys(final_cols))]

    except Exception as e:
        logger.error(f"Error loading RT2 DB: {e}")
        return None

# --- 5. Core Matching Logic ---

def find_match_with_priority(douban_row: pd.Series, df_rt2: pd.DataFrame, all_rt2_cols: List[str]) -> pd.Series:
    """Find match in RT2 for a single Douban row using 5-step priority."""
    ch_name = douban_row.get('ch_name')
    orig_name = douban_row.get('original_name')
    year = douban_row.get('year')

    # Pre-allocate empty result
    empty_result = pd.Series([pd.NA] * len(all_rt2_cols), index=all_rt2_cols)

    # Helper for fast masking
    def get_match(mask):
        subset = df_rt2[mask]
        if not subset.empty:
            return subset.iloc[0][all_rt2_cols]
        return None

    # 1. ch_name + year
    if pd.notna(ch_name) and pd.notna(year):
        res = get_match((df_rt2['rt2_match_title'] == ch_name) & (df_rt2['rt2_year'] == year))
        if res is not None: return res

    # 2. orig_name + year
    if pd.notna(orig_name) and pd.notna(year):
        res = get_match((df_rt2['rt2_match_title'] == orig_name) & (df_rt2['rt2_year'] == year))
        if res is not None: return res

    # 3. ch_name only
    if pd.notna(ch_name):
        res = get_match(df_rt2['rt2_match_title'] == ch_name)
        if res is not None: return res

    # 4. orig_name only
    if pd.notna(orig_name):
        res = get_match(df_rt2['rt2_match_title'] == orig_name)
        if res is not None: return res

    # 5. "Name (Year)" format matching
    if pd.notna(year):
        # Filter by year first (drastically reduces search space)
        year_subset = df_rt2[df_rt2['rt2_year_from_title'] == year]

        if not year_subset.empty:
            if pd.notna(ch_name):
                matches = year_subset[year_subset['rt2_title_from_title'] == ch_name]
                if not matches.empty:
                    return matches.iloc[0][all_rt2_cols]

            if pd.notna(orig_name):
                matches = year_subset[year_subset['rt2_title_from_title'] == orig_name]
                if not matches.empty:
                    return matches.iloc[0][all_rt2_cols]

    return empty_result

# --- 6. Main Orchestrator ---

def main():
    print(f"👤 Current User: {USERNAME}")
    logger.info("--- Rotten Tomatoes (RT2) Enrichment Pipeline (Optimized) Started ---")

    # 0. File Check
    if not check_input_files(FILE_PATHS):
        return

    # 1. Load RT2
    df_rt2 = load_and_prep_rotten_tomatoes_2(FILE_PATHS['rt2_db'], RT2_ENRICH_COLS, RT2_PREFIX)
    if df_rt2 is None:
        return

    # 2. Load Base DB
    df_base = load_base_db(FILE_PATHS['base_db'])
    if df_base is None:
        return

    logger.info(f"Base DB: {len(df_base)} rows | RT2 DB: {len(df_rt2)} rows")
    logger.info("Starting 5-step prioritized matching...")

    rt2_cols_to_add = [col for col in df_rt2.columns if col.startswith(RT2_PREFIX)]

    # 3. Execute Matching
    tqdm.pandas(desc="Enriching (RT2)")
    enrich_data = df_base.progress_apply(
        lambda row: find_match_with_priority(row, df_rt2, rt2_cols_to_add),
        axis=1
    )

    # 4. Merge & Cleanup
    logger.info("Merging results...")
    df_final = pd.concat([df_base, enrich_data], axis=1)

    del df_base, df_rt2, enrich_data
    gc.collect()

    # 5. Save
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