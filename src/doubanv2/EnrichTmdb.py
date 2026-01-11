#!/usr/bin/env python3
"""
电影数据增强工具 (TMDb API) - Pathlib 优化版 (多用户支持)
已修改: 检测到本地有效海报/背景图时自动跳过下载
"""

import os
import sys
import json
import csv
import time
import logging
import re
import gc
import sqlite3
import argparse
import io
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import quote

import requests
from tqdm import tqdm

# 可选依赖
try:
    from PIL import Image
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

try:
    import diskcache
    HAS_DISKCACHE = True
except ImportError:
    HAS_DISKCACHE = False

# === 1. 路径与配置管理 ===

# 获取当前脚本路径并解析项目根目录
CURRENT_SCRIPT = Path(__file__).resolve()
PROJECT_ROOT = CURRENT_SCRIPT.parents[2]

RESOURCES_DIR = PROJECT_ROOT / "resources"
CONFIG_PATH = RESOURCES_DIR / "config.json"
USERDATA_ROOT = RESOURCES_DIR / "UserData"
CACHE_DIR_BASE = PROJECT_ROOT / ".cache"

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
    # --- 用户特定路径 ---
    "source_csv": USER_DB_DIR / "douban_movies.csv",
    "target_csv": USER_ENRICHED_DIR / "douban_movies_Tmdb_enriched.csv",
    "log_file": USER_LOG_DIR / "tmdb.log",
    "skip_file": USER_LOG_DIR / "tmdb_未下载海报.txt",
    "report_file": USER_LOG_DIR / "tmdb_processing_report.json",
    
    # --- 全局/共享路径 (保持不变) ---
    "config_json": CONFIG_PATH,
    "tmdb_poster_dir": RESOURCES_DIR / "tmdb_poster", # 海报库共享
    "cache_dir": CACHE_DIR_BASE / "tmdb_cache"      # API缓存共享
}

class Config:
    """配置管理类"""
    # 性能与网络
    MAX_WORKERS = 10
    RETRY_ATTEMPTS = 3
    REQUEST_TIMEOUT = 10
    REQUEST_DELAY = 0.3

    # 图片处理
    IMAGE_OPTIMIZE = True
    POSTER_MAX_SIZE = (800, 1200)
    BACKDROP_MAX_SIZE = (1920, 1080)
    IMAGE_QUALITY = 85

    # API
    TMDB_SEARCH_URL = 'https://api.themoviedb.org/3/search/movie'
    TMDB_IMAGE_URL = 'https://image.tmdb.org/t/p/original'

    # 动态加载的配置
    TMDB_API_KEY = None
    PROXIES = None

    @classmethod
    def load_from_json(cls):
        """从 JSON 加载 API Key 和 Proxy"""
        config_path = FILE_PATHS["config_json"]
        try:
            with config_path.open("r", encoding="utf-8") as f:
                data = json.load(f)
                cls.TMDB_API_KEY = data.get("tmdb_api_key")
                cls.PROXIES = data.get("proxy")
        except Exception as e:
            print(f"⚠️  加载配置失败: {e}")

    @classmethod
    def validate(cls):
        """验证关键配置"""
        if not cls.TMDB_API_KEY or cls.TMDB_API_KEY == "YOUR_TMDB_API_KEY_GOES_HERE":
            raise ValueError("❌ 错误：未设置有效 TMDB_API_KEY。")

        if not FILE_PATHS["source_csv"].exists():
            raise FileNotFoundError(f"❌ 错误：源文件不存在 {FILE_PATHS['source_csv']}")

        # 预创建目录
        paths_to_ensure = ["tmdb_poster_dir", "log_file", "cache_dir", "target_csv"]
        
        for path_key in paths_to_ensure:
            path = FILE_PATHS[path_key]
            target_dir = path.parent if path.suffix else path
            if not target_dir.exists():
                target_dir.mkdir(parents=True, exist_ok=True)

# === 2. 日志系统 ===

def setup_logging(verbose: bool = False):
    log_level = logging.DEBUG if verbose else logging.INFO
    log_file = FILE_PATHS["log_file"]

    log_file.parent.mkdir(parents=True, exist_ok=True)

    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(str(log_file), encoding='utf-8'),
            logging.StreamHandler(sys.stdout)
        ]
    )

# === 3. 缓存与网络 ===

class CacheManager:
    def __init__(self):
        self.cache = None
        if HAS_DISKCACHE:
            try:
                cache_path = FILE_PATHS["cache_dir"]
                cache_path.mkdir(parents=True, exist_ok=True)
                self.cache = diskcache.Cache(str(cache_path))
                logging.info(f"📦 缓存系统已就绪: {cache_path.name}")
            except Exception as e:
                logging.warning(f"⚠️  缓存初始化失败: {e}")

    def get(self, key: str) -> Any:
        return self.cache.get(key) if self.cache else None

    def set(self, key: str, value: Any, expire: int = 86400):
        if self.cache:
            try:
                self.cache.set(key, value, expire)
            except Exception:
                pass

    def close(self):
        if self.cache:
            self.cache.close()

class NetworkManager:
    def __init__(self, cache_manager: CacheManager):
        self.cache = cache_manager

    def safe_request_get(self, url: str, params: Dict = None, use_cache: bool = True, stream: bool = False) -> Optional[requests.Response]:
        if use_cache and self.cache and not stream:
            cache_key = f"req_{hash(frozenset(params.items()) if params else '')}_{url}"
            cached_content = self.cache.get(cache_key)
            if cached_content:
                resp = requests.Response()
                resp.status_code = 200
                resp._content = cached_content
                return resp

        for attempt in range(Config.RETRY_ATTEMPTS):
            try:
                resp = requests.get(
                    url, params=params, timeout=Config.REQUEST_TIMEOUT,
                    proxies=Config.PROXIES, stream=stream
                )

                if resp.status_code == 200:
                    if use_cache and self.cache and not stream:
                        cache_key = f"req_{hash(frozenset(params.items()) if params else '')}_{url}"
                        self.cache.set(cache_key, resp.content)
                    return resp
                elif resp.status_code == 429:
                    wait = int(resp.headers.get('Retry-After', 10)) + 1
                    time.sleep(wait)
                else:
                    time.sleep(attempt + 1)

            except requests.RequestException:
                time.sleep(attempt + 1)

        return None

    def search_movie_tmdb(self, title1: str, title2: str, year: int) -> Optional[Dict]:
        def _search(q: str, y: int) -> Optional[Dict]:
            if not q: return None
            params = {'api_key': Config.TMDB_API_KEY, 'query': q, 'language': 'zh-CN'}
            if y: params['year'] = y

            resp = self.safe_request_get(Config.TMDB_SEARCH_URL, params=params)
            if resp:
                try:
                    results = resp.json().get('results', [])
                    if y and results:
                        for res in results:
                            ry = res.get('release_date', '').split('-')[0]
                            if str(ry) == str(y): return res
                    return results[0] if results else None
                except json.JSONDecodeError:
                    pass
            return None

        res = _search(title1, year)
        if not res and title2:
            time.sleep(Config.REQUEST_DELAY)
            res = _search(title2, year)
        return res

    def download_image(self, api_path: str, save_path: Path, pbar: Optional[tqdm] = None) -> bool:
        if not api_path: return False
        
        # ===============================================
        # 修改: 严谨的跳过逻辑 (文件存在且大小 > 0)
        # ===============================================
        if save_path.exists():
            if save_path.stat().st_size > 0:
                logging.debug(f"♻️ 图片已存在，跳过下载: {save_path.name}")
                return True
            else:
                # 文件存在但为 0 bytes，可能是之前的错误残留，删除并重新下载
                try:
                    save_path.unlink()
                    logging.warning(f"🗑️ 发现空文件，已清理并重试: {save_path.name}")
                except OSError:
                    pass # 如果无法删除，后续写入可能会失败或覆盖

        url = f"{Config.TMDB_IMAGE_URL}{api_path}"
        resp = self.safe_request_get(url, stream=True)

        if resp:
            try:
                img_data = b''
                for chunk in resp.iter_content(8192):
                    if chunk:
                        img_data += chunk
                        if pbar: pbar.update(len(chunk))

                if Config.IMAGE_OPTIMIZE and HAS_PIL:
                    img_data = self._optimize_image(img_data, save_path)
                    if not img_data: return False

                save_path.parent.mkdir(parents=True, exist_ok=True)
                with save_path.open("wb") as f:
                    f.write(img_data)
                return True
            except Exception as e:
                logging.error(f"图片下载失败 {save_path.name}: {e}")
        return False

    def _optimize_image(self, data: bytes, path: Path) -> Optional[bytes]:
        if not HAS_PIL: return data
        try:
            img = Image.open(io.BytesIO(data))
            max_size = Config.POSTER_MAX_SIZE if '_poster' in path.name else Config.BACKDROP_MAX_SIZE
            img.thumbnail(max_size, Image.Resampling.LANCZOS)

            if img.mode != 'RGB':
                bg = Image.new('RGB', img.size, (255,255,255))
                if img.mode == 'RGBA':
                    bg.paste(img, mask=img.split()[-1])
                else:
                    bg.paste(img)
                img = bg

            out = io.BytesIO()
            img.save(out, 'JPEG', quality=Config.IMAGE_QUALITY, optimize=True)
            return out.getvalue()
        except Exception:
            return None

# === 4. 数据管理 ===

class DataManager:
    @staticmethod
    def load_movies(csv_path: Path) -> Tuple[List[Dict], List[Dict], List[str]]:
        all_movies = []
        to_process = []
        skipped = []
        processed_count = 0

        if not csv_path.exists():
            logging.critical(f"源文件不存在: {csv_path}")
            sys.exit(1)

        try:
            with csv_path.open("r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                has_poster = 'poster_path' in (reader.fieldnames or [])

                for row in reader:
                    movie = dict(row)
                    all_movies.append(movie)

                    link = movie.get('link')
                    if not link:
                        skipped.append(f"无链接: {movie.get('title')}")
                        continue

                    if has_poster and movie.get('poster_path'):
                        processed_count += 1
                        continue

                    # 解析字段
                    movie['chsname'] = movie.get('ch_name', '').strip()
                    movie['aname'] = movie.get('original_name', '').strip()
                    if movie['chsname'] == movie['aname']: movie['aname'] = None

                    movie['year'] = DataManager._extract_year(movie.get('premiere_date', ''))

                    if not (movie['chsname'] or movie['aname']) or not movie['year']:
                        skipped.append(f"数据不足: {link}")
                        continue

                    to_process.append(movie)
        except Exception as e:
            logging.critical(f"读取 CSV 失败: {e}")
            sys.exit(1)

        logging.info(f"加载: 总{len(all_movies)}, 待处理{len(to_process)}, 跳过{len(skipped)}, 已存{processed_count}")
        return all_movies, to_process, skipped

    @staticmethod
    def _extract_year(date_str: str) -> Optional[int]:
        if not date_str: return None
        match = re.search(r'(\d{4})', date_str)
        if match:
            y = int(match.group(1))
            if 1880 < y < 2050: return y
        return None

    @staticmethod
    def save_movies(movies: List[Dict], path: Path):
        if not movies: return

        # 字段映射与清洗
        csv_movies = []
        rename_map = {
            'overview': 'tmdb_overview',
            'vote_average': 'tmdb_vote_average',
            'data_quality': 'tmdb_data_quality'
        }

        for m in movies:
            cm = m.copy()
            for old, new in rename_map.items():
                if old in cm: cm[new] = cm.pop(old)
            csv_movies.append(cm)

        # 表头处理
        all_keys = set().union(*(d.keys() for d in csv_movies))
        preferred = [
            'title', 'ch_name', 'original_name', 'rating', 'watch_date', 'premiere_date', 'duration', 'link', 'intro', 'comment',
            '地区', '人员', '类型', '语言',
            'year', 'chsname', 'aname',
            'tmdb_id', 'poster_path', 'backdrop_path', 'tmdb_overview', 'tmdb_vote_average', 'release_date_tmdb', 'tmdb_data_quality'
        ]
        headers = [h for h in preferred if h in all_keys] + [h for h in all_keys if h not in preferred]

        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("w", encoding="utf-8", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=headers, extrasaction='ignore')
                writer.writeheader()
                writer.writerows(csv_movies)
            logging.info(f"✅ 已保存到: {path.name}")
        except Exception as e:
            logging.error(f"❌ 保存失败: {e}")

# === 5. 核心处理 ===

class MovieProcessor:
    def __init__(self, net_mgr: NetworkManager):
        self.net = net_mgr

    def process(self, movie: Dict, dry_run: bool, pbar: Optional[tqdm]) -> Dict:
        t1 = movie.get('chsname', '')
        t2 = movie.get('aname', '')
        year = movie.get('year')
        link = movie.get('link')

        # 1. 搜索
        res = self.net.search_movie_tmdb(t1, t2, year)
        if not res: return movie

        # 2. 更新元数据
        movie.update({
            'tmdb_id': res.get('id'),
            'overview': res.get('overview'),
            'vote_average': res.get('vote_average'),
            'release_date_tmdb': res.get('release_date')
        })

        # 3. 下载图片
        safe_name = re.sub(r'[\\/*?:"<>|]', "", t2 or t1 or str(hash(link))).strip().replace(" ", "_")[:50]
        file_base = f"{safe_name}_{year}"

        # Poster
        if res.get('poster_path'):
            fname = f"{file_base}_poster.jpg"
            full_path = FILE_PATHS["tmdb_poster_dir"] / fname
            rel_path = f"{FILE_PATHS['tmdb_poster_dir'].name}/{fname}"

            if not dry_run:
                if self.net.download_image(res['poster_path'], full_path, pbar):
                    movie['poster_path'] = rel_path
            else:
                movie['poster_path'] = f"[DryRun] {rel_path}"

        # Backdrop
        if res.get('backdrop_path'):
            fname = f"{file_base}_backdrop.jpg"
            full_path = FILE_PATHS["tmdb_poster_dir"] / fname
            rel_path = f"{FILE_PATHS['tmdb_poster_dir'].name}/{fname}"

            if not dry_run:
                if self.net.download_image(res['backdrop_path'], full_path):
                    movie['backdrop_path'] = rel_path
            else:
                movie['backdrop_path'] = f"[DryRun] {rel_path}"

        # 4. 质量评分
        self._validate_quality(movie)
        return movie

    def _validate_quality(self, movie: Dict):
        score = 100
        if not movie.get('poster_path'): score -= 30
        if not movie.get('tmdb_id'): score -= 25
        if len(movie.get('overview', '')) < 10: score -= 20

        score = max(0, min(100, score))
        movie['data_quality'] = "优秀" if score >= 80 else "良好" if score >= 60 else "一般" if score >= 40 else "较差"

# === 6. 主程序 ===

class App:
    def __init__(self, args):
        self.args = args
        self.cache = CacheManager()
        self.net = NetworkManager(self.cache)
        self.proc = MovieProcessor(self.net)
        self._apply_args()

    def _apply_args(self):
        Config.load_from_json()
        if self.args.source_csv:
            FILE_PATHS["source_csv"] = Path(self.args.source_csv).resolve()
        if self.args.target_csv:
            FILE_PATHS["target_csv"] = Path(self.args.target_csv).resolve()
        if self.args.workers:
            Config.MAX_WORKERS = self.args.workers
        if self.args.no_optimize:
            Config.IMAGE_OPTIMIZE = False

    def run(self):
        start = datetime.now()

        print(f"👤 当前用户: {USERNAME}")
        print(f"📂 读入: {FILE_PATHS['source_csv']}")
        print(f"📂 输出: {FILE_PATHS['target_csv']}")

        try:
            Config.validate()
        except Exception as e:
            logging.critical(e)
            return

        # 加载数据
        all_movies, tasks, skipped = DataManager.load_movies(FILE_PATHS["source_csv"])

        if not tasks:
            logging.info("🎉 所有电影均已处理完毕。")
            self.cache.close()
            return

        # 并发处理
        logging.info(f"🚀 开始处理 {len(tasks)} 部电影 (线程: {Config.MAX_WORKERS})...")
        results = []

        with tqdm(total=len(tasks), unit="部") as pbar:
            with ThreadPoolExecutor(max_workers=Config.MAX_WORKERS) as executor:
                futures = {
                    executor.submit(self.proc.process, m, self.args.dry_run, None): m
                    for m in tasks
                }

                for f in as_completed(futures):
                    try:
                        results.append(f.result())
                        pbar.update(1)
                    except Exception as e:
                        logging.error(f"任务失败: {e}")
                        pbar.update(1)

        # 合并结果
        processed_map = {m['link']: m for m in results}
        final_list = [processed_map.get(m.get('link'), m) for m in all_movies]

        # 保存
        if not self.args.dry_run:
            DataManager.save_movies(final_list, FILE_PATHS["target_csv"])

            # 保存报告
            report = {
                "summary": {
                    "duration": (datetime.now() - start).total_seconds(),
                    "processed": len(results),
                    "skipped": len(skipped)
                },
                "skipped_details": skipped
            }
            try:
                with FILE_PATHS["report_file"].open("w", encoding="utf-8") as f:
                    json.dump(report, f, indent=2, ensure_ascii=False)
            except: pass

        self.cache.close()
        logging.info("🏁 流程结束。")

def parse_args():
    parser = argparse.ArgumentParser(description="TMDb 数据增强工具 (Pathlib版)")
    parser.add_argument('--source-csv', help='源CSV路径')
    parser.add_argument('--target-csv', help='目标CSV路径')
    parser.add_argument('--workers', type=int, help='并发数')
    parser.add_argument('--dry-run', action='store_true', help='试运行')
    parser.add_argument('--no-optimize', action='store_true', help='禁用图片优化')
    parser.add_argument('--verbose', action='store_true', help='详细日志')
    return parser.parse_args()

if __name__ == "__main__":
    args = parse_args()
    setup_logging(args.verbose)

    try:
        app = App(args)
        app.run()
    except KeyboardInterrupt:
        logging.warning("🛑 用户强制中断。")
        sys.exit(0)
    except Exception as e:
        logging.critical(f"❌ 未知错误: {e}", exc_info=True)
        sys.exit(1)