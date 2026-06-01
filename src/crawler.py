"""
正文爬取引擎 — aiohttp 并发抓取页面，提取 class="pages_content" 正文。

独立运行:  python -m src.crawler <json_path>
"""

import asyncio
import random
import time
from typing import Dict, List

import aiohttp
from bs4 import BeautifulSoup

from config import REQUEST_DELAY, CONCURRENT, USER_AGENTS, SSL_VERIFY
from .json_handler import read_json, write_json, MATCH_KW_KEY, strip_footer


def _get_headers() -> Dict[str, str]:
    return {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Referer": "https://www.gov.cn/",
    }


def _extract_content(html: str) -> str:
    """提取 class='pages_content' 标签内的正文（覆盖新旧 gov.cn 模板）

    gov.cn 页面可能存在多个 pages_content div（table 适配、响应式布局等），
    内容几乎一致但可能有微小差异（如末尾"扫一扫"页脚）。取首个标签
    并剥离页脚及之后重复区域，避免多标签拼接导致重复。
    """
    soup = BeautifulSoup(html, "html.parser")
    tags = soup.find_all(class_="pages_content")
    if not tags:
        return ""

    tag = tags[0]
    for t in tag(["script", "style", "iframe", "noscript"]):
        t.decompose()
    text = tag.get_text(separator="\n", strip=True)
    text = "\n".join(line.strip() for line in text.splitlines() if line.strip())
    return strip_footer(text)


def _progress_line(done: int, total: int, bar_width: int = 30) -> str:
    """生成进度条字符串  [#####-------] 45/224 (75%)

    使用 # 和 - 替代 Unicode 块字符，兼容 Windows GBK 终端。
    """
    filled = int(bar_width * done / total) if total > 0 else 0
    bar = "#" * filled + "-" * (bar_width - filled)
    pct = done * 100 // total if total > 0 else 100
    return f"  [{bar}] {done}/{total} ({pct}%)"


async def _fetch_with_progress(
    url: str,
    session: aiohttp.ClientSession,
    semaphore: asyncio.Semaphore,
    counter: Dict[str, int],
    total: int,
) -> str:
    """抓取单个 URL，完成后更新进度计数器"""
    content = ""
    async with semaphore:
        await asyncio.sleep(random.uniform(*REQUEST_DELAY))
        try:
            async with session.get(
                url, headers=_get_headers(),
                timeout=aiohttp.ClientTimeout(total=20),
                ssl=SSL_VERIFY,
            ) as resp:
                if resp.status == 200:
                    content = _extract_content(await resp.text())
        except Exception:
            pass

    counter["done"] += 1
    print(_progress_line(counter["done"], total), end="\r", flush=True)
    return content


async def _fetch_all(urls: List[str]) -> Dict[str, str]:
    """并发抓取所有 URL，显示进度条"""
    semaphore = asyncio.Semaphore(CONCURRENT)
    connector = aiohttp.TCPConnector(limit=CONCURRENT, force_close=True)
    counter = {"done": 0}
    total = len(urls)

    async with aiohttp.ClientSession(connector=connector) as session:
        tasks = [_fetch_with_progress(url, session, semaphore, counter, total) for url in urls]
        results = await asyncio.gather(*tasks)

    # 清除进度行
    print(" " * 60, end="\r", flush=True)
    return dict(zip(urls, results))


def crawl_json(filepath: str) -> None:
    """
    读取 JSON 中所有 url，并发爬取正文，关键词回检后过滤写入。

    回检规则：post 正文中必须包含"匹配关键词"字段中的至少一个关键词，
    否则删除该条目（API 返回了不相关的命中结果，不保留在 JSON 中）。
    """
    items = read_json(filepath)

    # 构建 url → 关键词映射
    url_kw_map: Dict[str, List[str]] = {}
    for item in items:
        url = item.get("url", "").strip()
        if not url:
            continue
        kw_str = item.get(MATCH_KW_KEY, "")
        kws = [k.strip() for k in kw_str.split(",") if k.strip()]
        url_kw_map[url] = kws

    urls = list(url_kw_map.keys())
    if not urls:
        print(f"  [WARN] JSON 中无有效 URL: {filepath}")
        return

    print(f"  [CRAWL] {len(urls)} 个 URL，{CONCURRENT} 并发")
    start = time.perf_counter()

    url_content_map = asyncio.run(_fetch_all(urls))

    elapsed = time.perf_counter() - start
    crawled_ok = sum(1 for v in url_content_map.values() if v)

    # 回填正文 + 关键词回检（sanitize 推迟到 Phase 4 导出阶段）
    for item in items:
        url = item.get("url", "").strip()
        content = url_content_map.get(url, "")
        if content:
            kws = url_kw_map.get(url, [])
            if kws and not any(kw in content for kw in kws):
                content = ""           # 无匹配 → 置空触发后续删除
        item["post"] = content

    kept = [it for it in items if it.get("post", "").strip()]
    removed = len(items) - len(kept)
    write_json(filepath, kept)

    print(f"  [OK] {len(kept)}/{len(urls)} 保存（爬取成功{crawled_ok}，关键词回检剔除{removed}），耗时 {elapsed:.0f}s ({elapsed/len(urls):.1f}s/条)")


# ======================== 独立运行 ========================
if __name__ == "__main__":
    import sys, os
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

    if len(sys.argv) < 2:
        print("用法: python -m src.crawler <json_path>")
        sys.exit(1)

    crawl_json(sys.argv[1])