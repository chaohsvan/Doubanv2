import pandas as pd
import csv
import sys
import time
import os
from pathlib import Path
from typing import Tuple, Optional, List, Union

# === 1. 平台特定导入 (用于非阻塞 I/O) ===
IS_WINDOWS = os.name == 'nt'

if IS_WINDOWS:
    import msvcrt
else:
    import select
    import tty
    import termios

# === 2. 全局路径配置 ===
# 假设此脚本位于 src/doubanv2_test/ctsv_col_rm.py
# 项目根目录为 src/doubanv2_test/../../ -> ProjectRoot
CURRENT_SCRIPT = Path(__file__).resolve()
PROJECT_ROOT = CURRENT_SCRIPT.parents[2]
STATIC_DB_DIR = PROJECT_ROOT / "resources" / "StaticMovieDB"

# ================= 3. I/O 交互工具函数 =================

def print_header(title: str):
    """打印格式化的标题"""
    print(f"\n{'='*10} {title} {'='*10}")

def print_error(msg: str):
    """打印错误信息"""
    print(f"❌ 错误: {msg}")

def print_info(msg: str):
    """打印一般提示信息"""
    print(f"ℹ️  {msg}")

def _clear_line():
    """清除当前控制台行 (兼容性处理)"""
    sys.stdout.write("\r" + " " * 80 + "\r")
    sys.stdout.flush()

def get_timed_input(prompt: str,
                    timeout_sec: int,
                    timeout_default: str,
                    enter_default_val: str = '') -> str:
    """
    获取带超时的用户输入。支持 Windows 和 Unix。
    优化点：减少光标闪烁，统一逻辑。
    """
    sys.stdout.write(f"{prompt} ")
    sys.stdout.flush()

    start_time = time.time()
    buffer = []

    while True:
        elapsed = time.time() - start_time
        time_left = timeout_sec - elapsed

        # === 超时判断 ===
        if time_left <= 0:
            _clear_line()
            sys.stdout.write(f"{prompt} [超时! 默认: {timeout_default}]\n")
            return timeout_default

        # === 倒计时显示 (每秒更新一次，减少 I/O 压力) ===
        # 使用 \r 回到行首，重新打印 prompt 和倒计时
        timer_msg = f"({int(time_left) + 1}s) "
        current_input = "".join(buffer)
        sys.stdout.write(f"\r{prompt} {timer_msg}{current_input}")
        sys.stdout.flush()

        # === 输入检测逻辑 ===
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
                    except:
                        pass
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

        # === 处理按键 ===
        if char:
            if char == '\n':
                sys.stdout.write('\n')
                result = "".join(buffer).strip().lower()
                return result if result else enter_default_val

            elif char in ('\b', '\x7f'): # Backspace
                if buffer:
                    buffer.pop()
                    # 视觉删除：退格 -> 空格 -> 退格
                    sys.stdout.write("\b \b")
                    sys.stdout.flush()

            elif char.isprintable():
                buffer.append(char)


# ================= 4. 核心逻辑函数 =================

def get_file_to_process(directory: Path) -> Optional[Path]:
    """列出目录文件并引导用户选择"""
    print_header(f"文件选择: {directory.name}")

    if not directory.exists():
        print_error(f"目录不存在: {directory}")
        return None

    # 过滤 CSV/TSV
    files = sorted([f for f in directory.iterdir() if f.is_file() and f.suffix.lower() in ['.csv', '.tsv']])

    if not files:
        print_error("目录中没有 .csv 或 .tsv 文件。")
        return None

    for i, f in enumerate(files, start=1):
        print(f"  [{i}] {f.name}")

    while True:
        prompt = f"\n请输入序号或文件名 (默认[{files[0].name}], '..'退出):"
        choice = get_timed_input(prompt, 10, timeout_default="..", enter_default_val='') # 增加到10秒

        if choice == '..':
            return None

        if not choice:
            return files[0] # 默认第一个

        # 尝试解析序号
        if choice.isdigit():
            idx = int(choice)
            if 1 <= idx <= len(files):
                return files[idx - 1]

        # 尝试匹配文件名
        for f in files:
            if f.name.lower() == choice:
                return f

        print_error("无效的选择，请重试。")

def load_and_sniff(filepath: Path) -> Tuple[pd.DataFrame, str]:
    """加载文件并智能检测分隔符"""
    print_info(f"正在读取: {filepath.name} ...")

    delimiter = ',' # 默认值

    try:
        # 1. 尝试嗅探分隔符
        with open(filepath, 'r', encoding='utf-8-sig', errors='replace') as f:
            sample = f.read(4096) # 读取更多字节以提高准确性
            if not sample:
                raise pd.errors.EmptyDataError("文件为空")
            try:
                dialect = csv.Sniffer().sniff(sample, delimiters=[',', '\t', ';', '|'])
                delimiter = dialect.delimiter
                print(f"   ✅ 检测到分隔符: '{delimiter}'")
            except csv.Error:
                print(f"   ⚠️ 无法自动检测分隔符，将使用默认值: '{delimiter}'")

            # 2. 重置指针并读取
            f.seek(0)
            df = pd.read_csv(f, sep=delimiter)
            return df, delimiter

    except Exception as e:
        # 抛出异常让上层处理
        raise e

def select_columns_to_delete(df: pd.DataFrame) -> Optional[List[str]]:
    """交互式选择要删除的列"""
    if df.empty:
        print_error("文件无数据行。")
        return None

    cols = df.columns.tolist()

    print_header("列信息预览")
    # 漂亮的列展示
    print(f"{'ID':<4} | {'Column Name':<30} | {'Example Value'}")
    print("-" * 60)

    first_row = df.iloc[0].tolist() if len(df) > 0 else [''] * len(cols)

    for i, (name, val) in enumerate(zip(cols, first_row), 1):
        val_str = str(val)[:30] + "..." if len(str(val)) > 30 else str(val)
        print(f"[{i:<2}] | {name:<30} | {val_str}")

    while True:
        prompt = "\n请输入要删除的列 [序号/名称] (逗号分隔, '..'返回):"
        user_input = get_timed_input(prompt, 15, timeout_default="..") # 15秒超时

        if user_input == '..':
            return None

        if not user_input:
            continue

        # 解析输入
        selected_cols = []
        raw_items = [x.strip() for x in user_input.split(',') if x.strip()]

        valid_input = True
        for item in raw_items:
            if item in cols:
                selected_cols.append(item)
            elif item.isdigit():
                idx = int(item)
                if 1 <= idx <= len(cols):
                    selected_cols.append(cols[idx-1])
                else:
                    print_error(f"序号 {item} 超出范围")
                    valid_input = False
            else:
                print_error(f"未找到列: {item}")
                valid_input = False

        if valid_input and selected_cols:
            # 去重并返回
            return list(dict.fromkeys(selected_cols))
        elif not selected_cols:
            print_error("未选择有效列")

def save_data(df: pd.DataFrame, filepath: Path, delimiter: str, deleted_cols: List[str]) -> str:
    """保存数据并处理确认逻辑"""
    print_header("保存确认")
    print(f"即将删除: {', '.join(deleted_cols)}")
    print(f"目标文件: {filepath.name}")

    prompt = "保存操作: [1]覆盖保存 (默认)  [2]重选列  [3]取消返回"
    choice = get_timed_input(prompt, 5, timeout_default="3", enter_default_val='1')

    if choice == '1':
        try:
            temp_path = filepath.with_suffix(filepath.suffix + '.tmp')
            # 先写入临时文件，防止写入中断导致源文件损坏
            df.to_csv(temp_path, sep=delimiter, index=False, encoding='utf-8-sig')

            # 替换源文件
            if filepath.exists():
                filepath.unlink()
            temp_path.rename(filepath)

            print_info("✅ 文件已成功更新。")
            return 'exit'
        except Exception as e:
            print_error(f"保存失败: {e}")
            return 'back'

    elif choice == '2':
        return 'retry'
    else:
        return 'back'

# ================= 5. 主程序 =================

def main():
    try:
        # 确保目录存在
        if not STATIC_DB_DIR.exists():
            # 尝试创建或报错，这里选择安全退出
            print_error(f"资源目录未找到: {STATIC_DB_DIR}")
            return

        while True:
            # 1. 选择文件
            target_file = get_file_to_process(STATIC_DB_DIR)
            if not target_file:
                print("\n👋 程序退出。")
                break

            try:
                # 2. 加载数据
                df, delimiter = load_and_sniff(target_file)
            except Exception as e:
                print_error(f"无法读取文件: {e}")
                continue

            # 内部循环：列操作
            while True:
                # 3. 选择列
                cols_to_del = select_columns_to_delete(df)
                if not cols_to_del:
                    break # 返回文件选择

                # 4. 内存中删除
                try:
                    df_new = df.drop(columns=cols_to_del)
                    print(f"\n   [内存操作] 已移除 {len(cols_to_del)} 列。")
                except Exception as e:
                    print_error(f"删除列失败: {e}")
                    continue

                # 5. 保存确认
                action = save_data(df_new, target_file, delimiter, cols_to_del)

                if action == 'exit':
                    break # 返回文件选择 (或者可以选择直接退出程序)
                elif action == 'retry':
                    continue # 重新选列
                elif action == 'back':
                    break # 返回文件选择

    except KeyboardInterrupt:
        print("\n\n🛑 用户强制中断。")
    finally:
        # 确保 Unix 终端恢复状态 (防御性编程)
        if not IS_WINDOWS:
            try:
                os.system('stty sane')
            except:
                pass

if __name__ == "__main__":
    main()
