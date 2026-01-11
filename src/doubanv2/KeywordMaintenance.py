import csv
import shutil
import re
import sys
import time
import os
from pathlib import Path
from itertools import zip_longest
from collections import defaultdict
from typing import List, Dict, Set, Tuple, Optional, Any

# === 1. 平台特定导入 (用于非阻塞 I/O) ===
IS_WINDOWS = os.name == 'nt'
if IS_WINDOWS:
    import msvcrt
else:
    import select
    import tty
    import termios

# === 2. 路径与常量配置 ===

# 获取当前脚本的绝对路径并解析
CURRENT_SCRIPT = Path(__file__).resolve()
# 回溯两级目录获取项目根目录 (src/doubanv2_test/KeywordMaintenance.py -> ProjectRoot)
PROJECT_ROOT = CURRENT_SCRIPT.parents[2]

RESOURCES_DIR = PROJECT_ROOT / "resources"

# 文件路径配置
FILE_PATHS = {
    "keywords_main": RESOURCES_DIR / "StaticMovieDB"/ "douban_movies_keywords.csv",
    "keywords_pending": RESOURCES_DIR / "StaticMovieDB"/ "douban_movies_keywords_pending.csv"
}

CATEGORIES = ["地区", "人员", "类型", "语言"]

# === 3. 交互工具函数 ===

def get_timed_input(prompt: str,
                    timeout_sec: int,
                    timeout_default: str,
                    enter_default_val: str = '') -> str:
    """
    获取带超时的用户输入。支持 Windows 和 Unix。
    """
    sys.stdout.write(f"{prompt} ")
    sys.stdout.flush()

    start_time = time.time()
    buffer = []
    timeout_default = str(timeout_default).lower()

    while True:
        elapsed = time.time() - start_time
        time_left = timeout_sec - elapsed

        if time_left <= 0:
            sys.stdout.write(f"\n⏱️  超时! 默认选择: {timeout_default}\n")
            return timeout_default

        # 倒计时显示
        timer_str = f"({int(time_left) + 1}s) "
        current_input = "".join(buffer)
        sys.stdout.write(f"\r{prompt} {timer_str}{current_input}")
        sys.stdout.flush()

        # 检测输入
        char = None
        if IS_WINDOWS:
            if msvcrt.kbhit():
                char_bytes = msvcrt.getch()
                if char_bytes in (b'\r', b'\n'):
                    char = '\n'
                elif char_bytes == b'\x08': # Backspace
                    char = '\b'
                else:
                    try:
                        char = char_bytes.decode('utf-8')
                    except: pass
            else:
                time.sleep(0.05)
        else: # Unix
            fd = sys.stdin.fileno()
            old_settings = termios.tcgetattr(fd)
            try:
                tty.setcbreak(fd)
                rlist, _, _ = select.select([sys.stdin], [], [], 0.05)
                if rlist:
                    char = sys.stdin.read(1)
            finally:
                termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)

        # 处理按键
        if char:
            if char == '\n':
                sys.stdout.write('\n')
                res = "".join(buffer).strip().lower()
                # 如果只按回车，返回默认值；否则返回输入值
                return res if res else timeout_default
            elif char in ('\b', '\x7f'): # Backspace
                if buffer:
                    buffer.pop()
                    sys.stdout.write("\b \b") # 视觉删除
            elif char.isprintable():
                buffer.append(char)

# === 4. 核心逻辑类 ===

class KeywordReviewer:
    def __init__(self):
        self.main_path = FILE_PATHS["keywords_main"]
        self.pending_path = FILE_PATHS["keywords_pending"]

        self.main_db = self._load_main_db()
        self.pending_list = self._load_pending_db()

        self.to_add: Dict[str, Set[str]] = defaultdict(set)
        self.to_keep_pending: List[Tuple[str, str]] = []

    def _load_main_db(self) -> Dict[str, Set[str]]:
        """加载主库到字典 {category: set(words)}"""
        data = {cat: set() for cat in CATEGORIES}
        if not self.main_path.exists():
            return data

        try:
            with self.main_path.open("r", encoding="utf-8-sig") as f:
                reader = csv.reader(f)
                headers = next(reader, [])
                header_map = {h.strip(): i for i, h in enumerate(headers) if h.strip() in CATEGORIES}

                for row in reader:
                    for cat, idx in header_map.items():
                        if idx < len(row) and row[idx].strip():
                            data[cat].add(row[idx].strip())
        except Exception as e:
            print(f"❌ 读取主库失败: {e}")
        return data

    def _load_pending_db(self) -> List[Tuple[str, str]]:
        """加载待确认列表"""
        data = []
        if not self.pending_path.exists():
            return data

        try:
            with self.pending_path.open("r", encoding="utf-8-sig") as f:
                reader = csv.reader(f)
                for row in reader:
                    if len(row) >= 2:
                        cat, word = row[0].strip(), row[1].strip()
                        if cat in CATEGORIES and word:
                            if word in self.main_db[cat]: # 过滤已存在的
                                continue
                            data.append((cat, word))
        except Exception as e:
            print(f"❌ 读取待确认库失败: {e}")

        # 去重并排序
        unique_data = sorted(list(set(data)), key=lambda x: x[0])
        return unique_data

    def backup_files(self):
        """备份当前文件"""
        for path in [self.main_path, self.pending_path]:
            if path.exists():
                backup_path = path.with_suffix(path.suffix + ".bak")
                shutil.copy(path, backup_path)
        print("💾 已创建 .bak 备份文件")

    def save(self):
        """保存所有更改"""
        if not self.to_add and len(self.pending_list) == len(self.to_keep_pending):
            print("ℹ️  无更改，跳过保存。")
            return

        self.backup_files()

        # 1. 更新并保存主库
        for cat, new_words in self.to_add.items():
            self.main_db[cat].update(new_words)
            print(f"   -> [{cat}] 新增 {len(new_words)} 个词")

        columns = [sorted(list(self.main_db.get(cat, set()))) for cat in CATEGORIES]

        try:
            self.main_path.parent.mkdir(parents=True, exist_ok=True)
            with self.main_path.open("w", encoding="utf-8-sig", newline="") as f:
                writer = csv.writer(f)
                writer.writerow(CATEGORIES)
                for row in zip_longest(*columns, fillvalue=''):
                    writer.writerow(row)
        except Exception as e:
            print(f"❌ 保存主库失败: {e}")
            return

        # 2. 更新并保存待确认库
        try:
            self.pending_path.parent.mkdir(parents=True, exist_ok=True)
            with self.pending_path.open("w", encoding="utf-8-sig", newline="") as f:
                writer = csv.writer(f)
                for cat, word in self.to_keep_pending:
                    writer.writerow([cat, word])
        except Exception as e:
            print(f"❌ 保存待确认库失败: {e}")
            return

        print(f"✅ 保存完成！待确认库剩余: {len(self.to_keep_pending)} 个")

    def approve_all_pending(self):
        """批量批准"""
        if not self.pending_list:
            print("ℹ️  无待处理词条。")
            return

        print(f"🚀 正在批量入库 {len(self.pending_list)} 个词条...")
        for cat, word in self.pending_list:
            if word not in self.main_db[cat]:
                self.to_add[cat].add(word)

        self.to_keep_pending = []
        self.pending_list = []
        self.save()

    def deduplicate_local_database(self):
        """本地数据库去重逻辑"""
        print("\n=== 🧹 开始数据库去重 ===")

        # 1.同类去重 (在内存中直接用 set 转换即可，无需复杂逻辑)
        for cat in CATEGORIES:
            original_count = len(self.main_db[cat])
            # 重新构建集合实际上已经完成了去重
            # 如果之前的逻辑是 list 可能会有重复，这里已经是 set 了，但为了流程完整性保留提示
            # 此处实际上是在检查加载时是否有重复 (csv 中有重复行)
            pass

        # 2. 跨类去重
        print("🔍 检查跨类别重复项...")
        word_map = defaultdict(list)
        for cat in CATEGORIES:
            for word in self.main_db[cat]:
                word_map[word].append(cat)

        cross_dupes = {w: cats for w, cats in word_map.items() if len(cats) > 1}

        if not cross_dupes:
            print("✅ 未发现跨类别重复项。")
            return

        for word, cats in cross_dupes.items():
            print(f"\n⚠️  重复词: 【{word}】 位于: {', '.join(cats)}")

            prompt = "处理: [1]保留首个 [2]手动选择 [s]跳过 (默认s):"
            choice = get_timed_input(prompt, 5, "s")

            if choice == '1':
                keep = cats[0]
                for c in cats[1:]:
                    self.main_db[c].discard(word)
                print(f"   ✅ 保留于 [{keep}]")
            elif choice == '2':
                for i, c in enumerate(cats, 1):
                    print(f"   [{i}] {c}")
                sel = get_timed_input("选择保留序号 (默认1):", 5, "1")
                try:
                    idx = int(sel) - 1
                    if 0 <= idx < len(cats):
                        keep = cats[idx]
                        for c in cats:
                            if c != keep:
                                self.main_db[c].discard(word)
                        print(f"   ✅ 保留于 [{keep}]")
                except:
                    print("   ❌ 无效选择，跳过。")
            else:
                print("   ➡️  跳过。")

    def split_names_in_personnel(self) -> bool:
        """拆分 '人员' 类中的中英文名"""
        print("\n=== ✂️  拆分人员姓名 ===")

        if "人员" not in self.main_db or not self.main_db["人员"]:
            print("ℹ️  '人员' 类为空。")
            return False

        pattern = re.compile(r'^([\u4e00-\u9fff\u00B7·]+)\s+([a-zA-Z\s\.-]+)$')
        new_names = set()
        count = 0

        # 遍历副本
        for word in list(self.main_db["人员"]):
            match = pattern.match(word)
            if match:
                cn, en = match.group(1).strip(), match.group(2).strip()
                if cn and en:
                    new_names.add(cn)
                    new_names.add(en)
                    count += 1

        if count == 0:
            print("✅ 未发现混合姓名。")
            return False

        print(f"🔍 发现 {count} 个混合姓名，新增拆分结果...")
        original_len = len(self.main_db["人员"])
        self.main_db["人员"].update(new_names)
        added = len(self.main_db["人员"]) - original_len

        if added > 0:
            print(f"✅ 实际新增 {added} 个条目。")
            return True
        else:
            print("ℹ️  拆分结果已存在，无新增。")
            return False

    def start_review(self):
        """逐条审核流程"""
        total = len(self.pending_list)
        print(f"\n=== 🔍 逐条审核 ({total} 个) ===")
        print("指令: [y]入库 [n]删除 [s]跳过 [q]保存退出")

        for i, (cat, word) in enumerate(self.pending_list, 1):
            while True:
                # 交互式输入无需倒计时
                prompt = f"[{i}/{total}] [{cat}] {word} -> "
                try:
                    choice = input(prompt).strip().lower()
                except KeyboardInterrupt:
                    self.save()
                    sys.exit(0)

                if choice == 'y':
                    self.to_add[cat].add(word)
                    print(f"   ✅ 入库")
                    break
                elif choice == 'n':
                    print(f"   🗑️  删除")
                    break
                elif choice == 's':
                    self.to_keep_pending.append((cat, word))
                    print(f"   ➡️  跳过")
                    break
                elif choice == 'q':
                    self.to_keep_pending.append((cat, word))
                    self.to_keep_pending.extend(self.pending_list[i:])
                    print("\n⏹️  保存进度并退出...")
                    self.save()
                    return

        print("\n🎉 审核完成！")
        self.save()

# === 5. 主程序 ===

def main():
    try:
        reviewer = KeywordReviewer()

        # 1. 去重
        if get_timed_input("\n🧹 进行数据库去重? (y/n 默认n):", 5, "n") == 'y':
            if get_timed_input("⚠️  确认修改文件? (y/n 默认n):", 5, "n") == 'y':
                reviewer.deduplicate_local_database()
                print("\n💾 保存去重结果...")
                reviewer.backup_files()
                # 写入主库
                columns = [sorted(list(reviewer.main_db.get(cat, set()))) for cat in CATEGORIES]
                try:
                    with reviewer.main_path.open("w", encoding="utf-8-sig", newline="") as f:
                        writer = csv.writer(f)
                        writer.writerow(CATEGORIES)
                        for row in zip_longest(*columns, fillvalue=''):
                            writer.writerow(row)
                    print("✅ 已保存。")
                except Exception as e:
                    print(f"❌ 保存失败: {e}")

        # 2. 拆分姓名
        if get_timed_input("\n✂️  拆分人员姓名? (y/n 默认n):", 5, "n") == 'y':
            if get_timed_input("⚠️  确认操作? (y/n 默认n):", 5, "n") == 'y':
                if reviewer.split_names_in_personnel():
                    print("\n💾 保存拆分结果...")
                    reviewer.backup_files()
                    columns = [sorted(list(reviewer.main_db.get(cat, set()))) for cat in CATEGORIES]
                    with reviewer.main_path.open("w", encoding="utf-8-sig", newline="") as f:
                        writer = csv.writer(f)
                        writer.writerow(CATEGORIES)
                        for row in zip_longest(*columns, fillvalue=''):
                            writer.writerow(row)
                    print("✅ 已保存。")

        # 3. 审核
        # 重新加载 pending (防止上述操作影响)
        reviewer.pending_list = reviewer._load_pending_db()
        count = len(reviewer.pending_list)

        if count > 0:
            print(f"\n📝 待审核: {count} 条")
            mode = get_timed_input("模式: [a]全部批准 [r]逐条审核 (默认r):", 5, "r")

            if mode == 'a':
                if get_timed_input("⚠️  确认全部入库? (y/n 默认n):", 5, "n") == 'y':
                    if get_timed_input("🚨 最终确认? (y/n 默认n):", 5, "n") == 'y':
                        reviewer.approve_all_pending()
                    else:
                        print("已取消。")
                else:
                    print("已取消。")
            else:
                reviewer.start_review()
        else:
            print("\n✨ 无待审核内容。")

    except KeyboardInterrupt:
        print("\n\n🛑 用户强制中断。")
    except Exception as e:
        print(f"\n❌ 未知错误: {e}")
    finally:
        if not IS_WINDOWS:
            try:
                os.system('stty sane')
            except: pass

if __name__ == "__main__":
    main()
