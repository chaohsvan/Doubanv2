import json
import logging
import sys
from pathlib import Path
from typing import Dict, List, Any

# =============================================================================
# 1. 路径与配置 (Configuration & Path Management)
# =============================================================================

# 脚本位置: .../DoubanV2/src/doubanv2/UI_generate.py
CURRENT_SCRIPT = Path(__file__).resolve()
PROJECT_ROOT = CURRENT_SCRIPT.parents[2]

RESOURCES_DIR = PROJECT_ROOT / "resources"
CONFIG_PATH = RESOURCES_DIR / "config.json"
USERDATA_ROOT = RESOURCES_DIR / "UserData"
# 全局共享 UI 资源目录 (存放 show.html 模板)
GLOBAL_UI_RESOURCES_DIR = RESOURCES_DIR / "ui_resources"

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
USER_UI_DIR = USER_SPECIFIC_DIR / "ui_resources"

# --- 文件路径配置 ---

# 输入: 用户 JSON 数据
JSON_PATH = USER_UI_DIR / "full_report.json"

# 输入: 全局 HTML 模板 (保持不变)
TEMPLATE_PATH = GLOBAL_UI_RESOURCES_DIR / "show.html"

# 输出: 用户 HTML 报告
OUTPUT_PATH = USER_UI_DIR / "report_with_data.html"

# 日志配置
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("UIGenerator")

# =============================================================================
# 2. 核心逻辑 (Core Logic)
# =============================================================================

def check_dependencies() -> bool:
    """检查必要文件是否存在"""
    missing = []
    if not JSON_PATH.exists():
        missing.append(f"数据文件: {JSON_PATH}")
    if not TEMPLATE_PATH.exists():
        missing.append(f"HTML模板: {TEMPLATE_PATH}")

    if missing:
        logger.error("❌ 缺少必要文件:")
        for m in missing:
            logger.error(f"   - {m}")
        return False
    return True

def load_json(file_path: Path) -> Dict[str, Any]:
    """加载JSON数据"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"❌ 读取 JSON 失败: {e}")
        raise

def process_image_paths(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    调整图片路径为相对于 HTML 文件的路径。
    统一添加 ../../../ 前缀，指向 resources/tmdb_poster
    """
    
    # 1. 处理背景墙 (Screenshot Wall)
    summary_data = data.get('1_Summary', {})
    if 'screenshot_wall_sample' in summary_data:
        logger.info("🖼️  正在调整海报墙路径 (Relative Path Fix)...")
        new_paths = []
        for item in summary_data['screenshot_wall_sample']:
            # --- [修复核心] 兼容性处理 ---
            # 如果是旧数据的字符串格式，手动转换为字典，防止 .get() 报错
            if isinstance(item, str):
                item = {"path": item, "title": "加载中..."}
            
            # 确保 item 是字典后再处理
            if isinstance(item, dict):
                original_path = item.get('path', '')
                clean_path = str(original_path).replace("resources/", "").strip("/")
                
                # 更新字典中的 path 字段
                item['path'] = f"../../../{clean_path}"
                # 确保 title 字段存在
                if 'title' not in item:
                    item['title'] = "未知标题"
                    
                new_paths.append(item)
                
        data['1_Summary']['screenshot_wall_sample'] = new_paths

    # 2. 处理五星海报墙 (Five Star Movies)
    pref_data = data.get('5_Preferences_Cross_Analysis', {})
    if 'five_star_movies' in pref_data:
        logger.info("🌟 正在调整五星海报路径...")
        for movie in pref_data['five_star_movies']:
            poster = movie.get('poster')
            if poster and not poster.startswith('http'):
                # 清洗路径
                clean_poster = str(poster).replace("resources/", "").strip("/")
                # 应用同样的 ../../../ 逻辑
                movie['poster'] = f"../../../{clean_poster}"

    return data

def extend_word_cloud(data: Dict[str, Any]) -> Dict[str, Any]:
    """确保词云数据至少有100个词（为了前端视觉效果）"""
    content_data = data.get('3_Content_Analysis', {})
    if 'intro_word_cloud' in content_data:
        words = content_data['intro_word_cloud']
        count = len(words)

        if 0 < count < 100:
            logger.info(f"🔤 扩展词云数据 (当前: {count}, 目标: 100)...")
            extended = []
            while len(extended) < 100:
                extended.extend(words)

            data['3_Content_Analysis']['intro_word_cloud'] = extended[:100]

    return data

def generate_report():
    """主生成流程"""
    print(f"👤 当前用户: {USERNAME}")
    logger.info("🚀 开始生成观影报告 HTML...")
    logger.info(f"📂 输出目录: {USER_UI_DIR}")

    # 1. 依赖检查
    if not check_dependencies():
        return

    # 2. 加载与处理数据
    try:
        data = load_json(JSON_PATH)

        # 处理图片路径
        data = process_image_paths(data)

        # 处理词云
        data = extend_word_cloud(data)

        # 3. 读取模板
        logger.info("📄 读取 HTML 模板...")
        with open(TEMPLATE_PATH, 'r', encoding='utf-8') as f:
            template_content = f.read()

        # 4. 注入数据 (JSON Serialization)
        logger.info("💉 注入 JSON 数据...")
        # ensure_ascii=False 保证中文不被转义，减小文件体积且可读
        json_str = json.dumps(data, ensure_ascii=False, indent=None) # indent=None 压缩体积

        # 执行替换
        html_content = template_content.replace('{{DATA_PLACEHOLDER}}', json_str)

        # 5. 输出文件
        logger.info(f"💾 写入文件: {OUTPUT_PATH.name}...")
        # 确保输出目录存在
        OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
        
        with open(OUTPUT_PATH, 'w', encoding='utf-8') as f:
            f.write(html_content)

        logger.info("=" * 50)
        logger.info(f"✅ 报告生成成功！")
        logger.info(f"🔗 文件位置: {OUTPUT_PATH}")
        logger.info(f"👉 请在浏览器中打开上述文件查看结果。")
        logger.info("=" * 50)

    except Exception as e:
        logger.exception(f"❌ 生成过程中发生未预期的错误: {e}")

if __name__ == "__main__":
    generate_report()