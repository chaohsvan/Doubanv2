import pandas as pd
import logging
import sys
import gc
import json
from pathlib import Path
from typing import Dict, Optional, Any

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

# !!! Configuration: Static Database Filename !!!
STATIC_DB_FILENAME = 'douban_static_database.csv'

# Centralized File Paths
FILE_PATHS = {
    # User Input
    "base_db": USER_DB_DIR / "douban_movies.csv",
    # Shared Static Input
    "static_db": STATIC_DB_DIR / STATIC_DB_FILENAME
}

# User Output
OUTPUT_PATH = USER_ENRICHED_DIR / 'douban_movies_staticdouban_enriched.csv'

# StaticDouban Configuration
PREFIX = 'staticdouban_'
KEY_COLUMN_BASE = 'link'   # Key in douban_movies.csv
KEY_COLUMN_STATIC = '链接'  # Key in douban_static_database.csv

# --- 2. Logging Setup ---

def setup_logging(log_dir: Path) -> logging.Logger:
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / 'staticdouban_enrichment.log'

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

# --- 4. Data Loading & Prep ---

def load_base_db(path: Path, key_col: str) -> Optional[pd.DataFrame]:
    """Load Base Douban Database."""
    logger.info(f"Loading base DB: {path}")
    try:
        df = pd.read_csv(path, encoding='utf-8-sig')
        if key_col not in df.columns:
            logger.error(f"FATAL: Base DB missing key column '{key_col}'. Found: {list(df.columns)[:5]}...")
            return None
        # Ensure key is string for merging
        df[key_col] = df[key_col].astype(str)
        return df
    except Exception as e:
        logger.error(f"Error loading base DB: {e}")
        return None

def load_and_prep_static_db(path: Path, key_col_static: str, key_col_base: str, prefix: str) -> Optional[pd.DataFrame]:
    """
    Load and prepare Static Douban DB.
    1. Check for key column.
    2. Rename key column to match base DB.
    3. Prefix all other columns.
    """
    logger.info(f"Loading Static Douban DB: {path}")

    try:
        df = pd.read_csv(path, encoding='utf-8-sig')

        if key_col_static not in df.columns:
            logger.error(f"FATAL: Static DB missing key column '{key_col_static}'. Found: {list(df.columns)[:5]}...")
            return None

        # 1. Standardize Key
        df[key_col_static] = df[key_col_static].astype(str)
        df.rename(columns={key_col_static: key_col_base}, inplace=True)

        # 2. Rename Content Columns
        cols_to_rename = {}
        for col in df.columns:
            if col != key_col_base:
                cols_to_rename[col] = f"{prefix}{col}"

        df.rename(columns=cols_to_rename, inplace=True)

        logger.info(f"Loaded {len(df)} static records. Prefixed {len(cols_to_rename)} columns.")

        # Return only the key and the prefixed columns
        keep_cols = [key_col_base] + list(cols_to_rename.values())
        return df[keep_cols]

    except Exception as e:
        logger.error(f"Error loading Static DB: {e}")
        return None

# --- 5. Main Orchestrator ---

def main():
    print(f"👤 Current User: {USERNAME}")
    logger.info("--- Static Douban Enrichment Pipeline (Optimized) Started ---")

    # 0. Pre-check Files
    if not check_input_files(FILE_PATHS):
        return

    # 1. Load Static DB (Source)
    df_static = load_and_prep_static_db(
        FILE_PATHS['static_db'],
        KEY_COLUMN_STATIC,
        KEY_COLUMN_BASE,
        PREFIX
    )
    if df_static is None:
        return

    # 2. Load Base DB (Target)
    df_base = load_base_db(FILE_PATHS['base_db'], KEY_COLUMN_BASE)
    if df_base is None:
        return

    logger.info(f"Base DB: {len(df_base)} rows | Static DB: {len(df_static)} rows")

    # 3. Merge
    logger.info(f"Merging on key: '{KEY_COLUMN_BASE}'...")

    # Left merge to keep all base rows
    df_final = pd.merge(
        df_base,
        df_static,
        on=KEY_COLUMN_BASE,
        how='left'
    )

    # Cleanup source frames to free memory
    del df_base, df_static
    gc.collect()

    # 4. Save
    try:
        OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
        logger.info(f"Saving to: {OUTPUT_PATH}")

        df_final.to_csv(OUTPUT_PATH, index=False, encoding='utf-8-sig')

        # Calc stats
        # Find the first prefixed column to check for non-nulls (successful matches)
        example_col = [c for c in df_final.columns if c.startswith(PREFIX)]
        if example_col:
            matched_count = df_final[example_col[0]].notna().sum()
            total = len(df_final)
            logger.info(f"✅ Saved {total} rows.")
            logger.info(f"📊 Match Rate: {matched_count}/{total} ({matched_count/total:.2%})")
        else:
            logger.warning("Saved file, but could not determine match stats (no prefixed columns found).")

    except Exception as e:
        logger.error(f"❌ Failed to save output: {e}")

    # Final cleanup
    del df_final
    gc.collect()
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