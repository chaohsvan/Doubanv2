import pandas as pd
import gc
import json
import sys
from pathlib import Path
from typing import List, Set, Any, Dict

# --- 1. 路径与常量配置 (Path & Configuration) ---

# 获取当前脚本的绝对路径并解析
CURRENT_SCRIPT = Path(__file__).resolve()
# 回溯两级目录获取项目根目录 (src/doubanv2/MergeEnrichedMovies.py -> ProjectRoot)
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
USER_ENRICHED_DIR = USER_SPECIFIC_DIR / "enriched_movies"

# 文件名配置
BASE_FILE_NAME = 'douban_movies.csv'
OUTPUT_FILE_NAME = 'douban_movies_merged.csv'

# 要合并的源文件列表 (位于 ENRICHED_DIR)
ENRICHED_FILES_LIST = [
    'douban_movies_Imdb_enriched.csv',
    'douban_movies_keywords_enriched.csv',
    'douban_movies_metacritic_enriched.csv',
    'douban_movies_rt1_enriched.csv',
    'douban_movies_rt2_enriched.csv',
    'douban_movies_Tmdb_enriched.csv',
    'douban_movies_staticdouban_enriched.csv'
]

# 合并主键
JOIN_KEY = 'link'

# 最终列排序依据
FINAL_COLUMN_ORDER = [
    'title', 'ch_name', 'original_name', 'rating', 'watch_date', 'premiere_date',
    'year', 'duration', 'link', 'intro', 'comment',
    # IMDb
    'imdb_writer_names', 'imdb_director_names', 'imdb_tconst', 'imdb_numVotes',
    'imdb_directors_ids', 'imdb_averageRating', 'imdb_writers_ids', 'imdb_other_titles',
    # 豆瓣关键词
    'doubankeyword_人员', 'doubankeyword_语言', 'doubankeyword_类型', 'doubankeyword_地区',
    # Metacritic
    'metacritic_No of Persons Voted', 'metacritic_Directed by', 'metacritic_Rating',
    'metacritic_Duration', 'metacritic_Genres', 'metacritic_Written by', 'metacritic_Description',
    # RottenTomatoes (RT1)
    'RottenTomatoes_writers', 'RottenTomatoes_movie_info', 'RottenTomatoes_tomatometer_rating',
    'RottenTomatoes_studio_name', 'RottenTomatoes_tomatometer_count', 'RottenTomatoes_audience_rating',
    'RottenTomatoes_tomatometer_status', 'RottenTomatoes_runtime_in_minutes',
    'RottenTomatoes_audience_count', 'RottenTomatoes_in_theaters_date',
    'RottenTomatoes_directors', 'RottenTomatoes_critics_consensus', 'RottenTomatoes_genre',
    # RottenTomatoes (RT2)
    'rotomatoes2_title', 'rotomatoes2_releaseDateTheaters', 'rotomatoes2_originalLanguage',
    'rotomatoes2_writer', 'rotomatoes2_director', 'rotomatoes2_runtimeMinutes',
    'rotomatoes2_genre', 'rotomatoes2_audienceScore', 'rotomatoes2_tomatoMeter',
    'rotomatoes2_distributor',
    # TMDB
    'tmdb_vote_average', 'aname', 'chsname', 'backdrop_path', 'poster_path',
    'tmdb_id', 'tmdb_overview', 'tmdb_data_quality', 'release_date_tmdb',
    # StaticDouban (可能有的列前缀)
    'staticdouban_'
]

# --- 2. 核心逻辑函数 ---

def load_dataframe(path: Path) -> pd.DataFrame:
    """安全加载 CSV 文件"""
    if not path.exists():
        print(f"❌ 错误：文件不存在 -> {path}")
        raise FileNotFoundError(f"File not found: {path}")
    try:
        return pd.read_csv(path, encoding='utf-8-sig')
    except Exception as e:
        print(f"❌ 读取失败 {path.name}: {e}")
        raise

def merge_enriched_files():
    # 路径指向用户专属目录
    base_file_path = USER_DB_DIR / BASE_FILE_NAME
    output_file_path = USER_DB_DIR / OUTPUT_FILE_NAME
    
    print("="*50)
    print(f"🚀 开始合并流程 (用户: {USERNAME})")
    print(f"📂 DB目录: {USER_DB_DIR}")
    print(f"📄 基础文件: {base_file_path.name}")
    print(f"📂 Enriched 目录: {USER_ENRICHED_DIR}")
    print("="*50)

    try:
        # 1. 读取基础文件
        df_base = load_dataframe(base_file_path)
        print(f"✅ 已加载基础文件，共 {len(df_base)} 行。")

        # 记录已有列，用于识别新列
        base_columns: Set[str] = set(df_base.columns)

        # 2. 循环处理 enriched 文件
        for file_name in ENRICHED_FILES_LIST:
            file_path = USER_ENRICHED_DIR / file_name

            if not file_path.exists():
                print(f"⚠️  跳过缺失文件: {file_name}")
                continue

            try:
                print(f"\n🔄 正在合并: {file_name} ...")

                # 读取文件
                df_enriched = pd.read_csv(file_path, encoding='utf-8-sig')

                # 检查 key
                if JOIN_KEY not in df_enriched.columns:
                    print(f"   ❌ 缺少合并键 '{JOIN_KEY}'，跳过。")
                    continue

                # 识别新列 (差集)
                enriched_cols = set(df_enriched.columns)
                new_columns = list(enriched_cols - base_columns)

                if not new_columns:
                    print(f"   ℹ️  无新列可合并，跳过。")
                    continue

                # 准备合并的数据 (Key + New Columns)
                cols_to_merge = [JOIN_KEY] + new_columns
                df_to_merge = df_enriched[cols_to_merge]

                # 执行左连接 (保留 df_base 所有行)
                df_base = pd.merge(df_base, df_to_merge, on=JOIN_KEY, how='left')

                print(f"   ✅ 成功合并 {len(new_columns)} 个新列。")

                # 更新基准列集合
                base_columns.update(new_columns)

                # 内存清理
                del df_enriched, df_to_merge
                gc.collect()

            except Exception as e:
                print(f"   ❌ 处理出错: {e}")

        print("\n" + "="*50)
        print("🧹 开始重排与清理列...")

        # --- 3. 列重新排序逻辑 ---
        current_cols = set(df_base.columns)

        # (A) 已知列：按 FINAL_COLUMN_ORDER 顺序提取存在的列
        ordered_cols = [col for col in FINAL_COLUMN_ORDER if col in current_cols]

        # (B) 静态豆瓣列特殊处理
        static_cols = [c for c in current_cols if c.startswith('staticdouban_') and c not in ordered_cols]
        if static_cols:
            ordered_cols.extend(sorted(static_cols))

        # (C) 未知列：不在配置列表中的其他列，按字母序排列
        known_set = set(ordered_cols)
        extra_cols = sorted([c for c in current_cols if c not in known_set])

        # (D) 最终列顺序
        final_cols_list = ordered_cols + extra_cols

        # 重建 DataFrame
        df_base = df_base[final_cols_list]

        print(f"✅ 列排序完成。总列数: {len(final_cols_list)}")
        if extra_cols:
            print(f"   ⚠️  附加了 {len(extra_cols)} 个未配置排序的列到末尾。")

        # 4. 保存
        print(f"\n💾 正在保存结果...")
        df_base.to_csv(output_file_path, index=False, encoding='utf-8-sig')
        print(f"🎉 全部完成！文件已保存至: {output_file_path}")

    except Exception as e:
        print(f"\n❌ 程序执行中发生严重错误: {e}")

if __name__ == "__main__":
    merge_enriched_files()