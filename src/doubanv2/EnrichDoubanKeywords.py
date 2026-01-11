import csv
import re
import sys
import json
from pathlib import Path
from collections import defaultdict
from itertools import zip_longest
from typing import Dict, Set, List, Optional, Any

# ================= 1. 路径与常量配置 =================

# 使用 pathlib 获取当前脚本的绝对路径
CURRENT_SCRIPT = Path(__file__).resolve()
# 回溯两级目录获取项目根目录 (src/doubanv2_test/EnrichDoubanKeywords.py -> ProjectRoot)
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
USER_DB_DIR = USER_SPECIFIC_DIR / "DBgenerate"
USER_ENRICHED_DIR = USER_SPECIFIC_DIR / "enriched_movies"

# 集中管理文件路径
FILE_PATHS = {
    # 用户特定 IO
    "input_csv": USER_DB_DIR / "douban_movies.csv",
    "output_csv": USER_ENRICHED_DIR / "douban_movies_keywords_enriched.csv",
    
    # 全局共享资源 (保持不变)
    "keywords_main": STATIC_DB_DIR / "douban_movies_keywords.csv",
    "keywords_pending": STATIC_DB_DIR / "douban_movies_keywords_pending.csv"
}

CATEGORIES = ["doubankeyword_地区", "doubankeyword_人员", "doubankeyword_类型", "doubankeyword_语言"]

# 常用百家姓 (用于正则优化)
CHINESE_SURNAMES = set([
    "李", "王", "张", "刘", "陈", "杨", "赵", "黄", "周", "吴", "徐", "孙", "胡", "朱", "高", "林", "何", "郭", "马", "罗",
    "梁", "宋", "郑", "谢", "韩", "唐", "冯", "于", "董", "萧", "程", "曹", "袁", "邓", "许", "傅", "沈", "曾", "彭", "吕",
    "苏", "卢", "蒋", "蔡", "贾", "丁", "魏", "薛", "叶", "阎", "余", "潘", "杜", "戴", "夏", "钟", "汪", "田", "任", "姜",
    "范", "方", "石", "姚", "谭", "廖", "邹", "熊", "金", "陆", "郝", "孔", "白", "崔", "康", "毛", "邱", "秦", "江", "史",
    "顾", "侯", "邵", "孟", "龙", "万", "段", "雷", "钱", "汤", "尹", "黎", "易", "常", "武", "乔", "贺", "赖", "龚", "文", "辛"
])

# 预编译正则
IGNORE_PATTERN = re.compile(r'^(\d{4}-\d{2}-\d{2}|\d+分钟)[(（].*[)）]$')
DATE_PATTERN = re.compile(r'^\d{4}-\d{2}-\d{2}$')

# ================= 3. 工具函数 =================

def print_step(msg: str):
    print(f"[*] {msg}")

def ensure_paths(file_paths_map: Dict[str, Path]):
    """
    基于 pathlib 的路径检查与创建。
    只创建目录，检查输入文件是否存在。
    """
    print_step("检查环境路径...")

    # 1. 确保所有输出文件的父目录存在
    dirs_to_create = set()

    for key, path in file_paths_map.items():
        if key == "input_csv": continue # 输入文件不创建目录
        # keywords_main/pending 位于 StaticMovieDB，如果不存在也会尝试创建(无害)
        dirs_to_create.add(path.parent)

    for d in dirs_to_create:
        if not d.exists():
            try:
                d.mkdir(parents=True, exist_ok=True)
                print(f"   [创建] 目录: {d}")
            except Exception as e:
                print(f"   [错误] 无法创建目录 {d}: {e}")

    # 2. 检查输入文件
    input_file = file_paths_map["input_csv"]
    if not input_file.exists():
        print(f"❌ [致命错误] 输入文件不存在: {input_file}")
        sys.exit(1)
    else:
        print(f"   [正常] 输入文件就绪: {input_file}")

# ================= 4. 关键词库管理类 =================

class KeywordManager:
    """管理主库和待确认库 (Pathlib 优化版)"""
    def __init__(self, main_path: Path, pending_path: Path):
        self.main_path = main_path
        self.pending_path = pending_path
        self.main_keywords = self._load_main_db()
        self.pending_keywords = self._load_pending_db()
        self.new_pending_buffer = defaultdict(set)
        self.has_updates = False

    def _load_main_db(self) -> Dict[str, Set[str]]:
        data = {cat: set() for cat in CATEGORIES}

        if not self.main_path.exists():
            print(f"   [提示] 主库不存在，初始化: {self.main_path}")
            # 自动创建带表头的文件
            self.main_path.parent.mkdir(parents=True, exist_ok=True)
            with self.main_path.open("w", encoding="utf-8-sig", newline="") as f:
                writer = csv.writer(f)
                writer.writerow(CATEGORIES)
            return data

        with self.main_path.open("r", encoding="utf-8-sig") as f:
            reader = csv.reader(f)
            headers = next(reader, [])
            header_map = {h.strip(): i for i, h in enumerate(headers) if h.strip() in CATEGORIES}
            for row in reader:
                for cat, idx in header_map.items():
                    if idx < len(row) and row[idx].strip():
                        data[cat].add(row[idx].strip())
        return data

    def _load_pending_db(self) -> Dict[str, Set[str]]:
        data = defaultdict(set)
        if not self.pending_path.exists():
            return data

        with self.pending_path.open("r", encoding="utf-8-sig") as f:
            reader = csv.reader(f)
            for row in reader:
                if len(row) >= 2:
                    cat, word = row[0], row[1]
                    if cat in CATEGORIES and word.strip():
                        data[cat].add(word.strip())
        return data

    def is_in_main_db(self, category: str, word: str) -> bool:
        return word in self.main_keywords.get(category, set())

    def add_to_pending(self, category: str, word: str):
        word = word.strip()
        if not word or word.isdigit():
            return
        if (word not in self.main_keywords[category]) and (word not in self.pending_keywords[category]):
            self.new_pending_buffer[category].add(word)
            self.pending_keywords[category].add(word) # 更新内存中的 pending 防止本次重复添加
            self.has_updates = True

    def save_pending_updates(self):
        if not self.has_updates: return

        # Append mode
        with self.pending_path.open("a", encoding="utf-8-sig", newline="") as f:
            writer = csv.writer(f)
            for cat, words in self.new_pending_buffer.items():
                for w in words:
                    writer.writerow([cat, w])

        count = sum(len(v) for v in self.new_pending_buffer.values())
        print_step(f"已追加 {count} 个新词到待确认文件。")
        self.new_pending_buffer.clear()
        self.has_updates = False

# ================= 5. 提取逻辑 =================

def extract_keywords_strict(intro: str, keyword_manager: KeywordManager) -> Dict[str, Set[str]]:
    found = {cat: set() for cat in CATEGORIES}
    if not intro: return found

    words = [w.strip() for w in intro.replace("\n", "/").split("/") if w.strip()]
    for w in words:
        if w.isdigit(): continue
        for cat in CATEGORIES:
            if keyword_manager.is_in_main_db(cat, w):
                found[cat].add(w)
    return found

# ================= 6. 主流程 =================

def main():
    print(f"\n=== 豆瓣电影分类系统 (用户: {USERNAME}) ===\n")

    ensure_paths(FILE_PATHS)

    kw_manager = KeywordManager(FILE_PATHS["keywords_main"], FILE_PATHS["keywords_pending"])
    processed_links = set()

    # --- 增量处理：读取已存在的输出 ---
    output_path = FILE_PATHS["output_csv"]
    if output_path.exists():
        print_step(f"读取断点记录: {output_path}")
        try:
            with output_path.open("r", encoding="utf-8-sig") as f_prev:
                reader = csv.DictReader(f_prev)
                if reader.fieldnames and "link" in reader.fieldnames:
                    for row in reader:
                        if row.get("link"):
                            processed_links.add(row["link"].strip())
            print(f"   已忽略 {len(processed_links)} 条已完成记录。")
        except Exception as e:
            print(f"   [警告] 读取历史记录失败: {e}，可能导致重复。")

    # --- 核心处理循环 ---
    input_path = FILE_PATHS["input_csv"]

    # 打开输出文件 (Append 模式)
    with input_path.open("r", encoding="utf-8-sig") as f_in, \
         output_path.open("a", encoding="utf-8-sig", newline="") as f_out:

        reader = csv.DictReader(f_in)

        if not reader.fieldnames:
            print("❌ [错误] 输入文件为空或无表头。")
            return

        # 确定输出表头
        base_headers = [h for h in reader.fieldnames if h not in CATEGORIES]
        output_headers = base_headers + CATEGORIES
        writer = csv.DictWriter(f_out, fieldnames=output_headers)

        # 仅当文件为空时写入表头 (st_size == 0)
        if output_path.stat().st_size == 0:
            writer.writeheader()
            print("   [初始化] 已写入新文件表头。")

        print_step("开始增量处理任务...")
        new_count = 0

        for i, row in enumerate(reader, 1):
            link = row.get("link", "").strip()

            if not link or link in processed_links:
                continue

            title = row.get("title", "未知标题")
            intro = row.get("intro", "")
            new_count += 1

            # 1. 严格匹配
            res = extract_keywords_strict(intro, kw_manager)
            known_words = {w for v in res.values() for w in v}

            # 1.5 正则补全人员
            if not res["doubankeyword_人员"]:
                regex_people = extract_people_regex(intro, known_words)
                if regex_people:
                    for p in regex_people:
                        res["doubankeyword_人员"].add(p)
                        known_words.add(p)
                        if not kw_manager.is_in_main_db("doubankeyword_人员", p):
                            kw_manager.add_to_pending("doubankeyword_人员", p)

            # 3. 写入
            output_row = {h: row.get(h) for h in base_headers}
            output_row.update({c: "/".join(sorted(res[c])) for c in CATEGORIES})
            writer.writerow(output_row)

            # 周期性 flush，防止数据丢失
            if new_count % 10 == 0:
                f_out.flush()

            processed_links.add(link)

    print("\n" + "="*40)
    print(f"✅ 处理完成。本次新增: {new_count} 条")
    if kw_manager.has_updates:
        kw_manager.save_pending_updates()
    print("="*40)

if __name__ == "__main__":
    main()