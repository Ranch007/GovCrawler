"""
gov.cn 政策文件搜索 API。

调用政府搜索引擎，解析 catMap → 返回结构化结果列表。

独立运行:  python -m src.search_api --keyword 安宁疗护
"""

import time
import random
import re
from typing import List, Dict, Optional
from urllib.parse import urlencode

import requests

from config import (
    SEARCH_API_URL, SEARCH_LIBRARY_TYPES, SEARCH_SEARCHFIELD,
    SEARCH_PAGE_SIZE, SEARCH_MAX_PAGES, USER_AGENTS, SSL_VERIFY,
)

_FIELDS = ["pcode", "title", "pubtimeStr", "url", "childtype", "puborg"]


def _build_params(keyword: str, library_type: str, page: int = 1, page_size: int = SEARCH_PAGE_SIZE) -> Dict[str, str]:
    """构建搜索 API 查询参数"""
    return {
        "t": library_type,
        "q": keyword,
        "timetype": "", "mintime": "", "maxtime": "",
        "sort": "score", "sortType": "1",
        "searchfield": SEARCH_SEARCHFIELD,
        "pcodeJiguan": "", "childtype": "", "subchildtype": "",
        "tsbq": "", "pubtimeyear": "", "puborg": "",
        "pcodeYear": "", "pcodeNum": "", "filetype": "",
        "p": str(page), "n": str(page_size),
        "inpro": "", "bmfl": "", "dup": "", "orpro": "", "bmpubyear": "",
    }


def _get_headers() -> Dict[str, str]:
    return {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "application/json, text/plain, */*",
        "Referer": "https://sousuo.www.gov.cn/",
    }


def _get_session() -> requests.Session:
    """绕过系统代理直连 gov.cn"""
    s = requests.Session()
    s.trust_env = False
    s.proxies = {"http": None, "https": None}
    return s


def _call_api(keyword: str, library_type: str, page: int, page_size: int = SEARCH_PAGE_SIZE, session: requests.Session = None) -> Optional[Dict]:
    """单次 API 调用，返回 JSON 或 None"""
    if session is None:
        session = _get_session()
    params = _build_params(keyword, library_type=library_type, page=page, page_size=page_size)
    url = f"{SEARCH_API_URL}?{urlencode(params)}"

    for attempt in range(3):
        try:
            resp = session.get(url, headers=_get_headers(), timeout=30, verify=SSL_VERIFY)
            resp.raise_for_status()
            data = resp.json()
            if data.get("code") == 200:
                return data
            print(f"  [FAIL] API code={data.get('code')} msg={data.get('msg')}")
            return None
        except Exception as e:
            print(f"  [RETRY] 第{attempt+1}/3次: {str(e)[:60]}")
            if attempt < 2:
                time.sleep(2 * (attempt + 1))
    return None


# 匹配所有 Unicode 空白字符，替换为普通半角空格
_RE_SPECIAL_SPACE = re.compile(r"[ -   　]+")
_RE_HTML_TAG = re.compile(r"<[^>]+>")


def _clean_text(text: str) -> str:
    """剥离 HTML 标签（如 <em>）+ 归一化空白"""
    if not isinstance(text, str):
        return text
    text = _RE_HTML_TAG.sub("", text)
    text = _RE_SPECIAL_SPACE.sub(" ", text)
    return re.sub(r" {2,}", " ", text).strip()


def _parse_results(data: Dict) -> List[Dict[str, str]]:
    """
    从 API 响应中提取结果列表。

    适配两种嵌套结构:
      - 顶层 catMap.<category>.listVO[]
      - 嵌套在 searchVO.catMap.<category>.listVO[]
    """
    results = []
    sv = data.get("searchVO", {})
    cat_map = data.get("catMap") or sv.get("catMap", {})

    for _cat_name, cat_data in cat_map.items():
        if not isinstance(cat_data, dict):
            continue
        for item in cat_data.get("listVO", []):
            if not isinstance(item, dict) or not item.get("url"):
                continue
            row = {}
            for field in _FIELDS:
                row[field] = _clean_text(item.get(field, ""))
            results.append(row)
    return results


def search_keyword(keyword: str, page_size: int = None, max_pages: int = None) -> List[Dict[str, str]]:
    """
    搜索单个关键词，遍历全部 library_type，自动翻页 + 跨库去重。

    Args:
        keyword:   搜索关键词
        page_size: 每页条数（默认 SEARCH_PAGE_SIZE）
        max_pages: 最大翻页数（默认 SEARCH_MAX_PAGES）

    Returns:
        [{pcode, title, pubtimeStr, url, childtype, puborg}, ...]
    """
    if page_size is None:
        page_size = SEARCH_PAGE_SIZE
    if max_pages is None:
        max_pages = SEARCH_MAX_PAGES

    all_results: List[Dict[str, str]] = []
    seen_urls: set = set()
    seen_titles: set = set()

    print(f"  [SEARCH] 关键词: {keyword}")

    session = _get_session()
    for lib_idx, library_type in enumerate(SEARCH_LIBRARY_TYPES, 1):
        lib_total = 0
        print(f"    库 [{lib_idx}/{len(SEARCH_LIBRARY_TYPES)}]: t={library_type}")

        for page in range(1, max_pages + 1):
            data = _call_api(keyword, library_type, page, page_size, session=session)
            if not data:
                break

            page_results = _parse_results(data)
            if not page_results:
                break

            new_count = 0
            for r in page_results:
                url = r["url"]
                title = r["title"].strip()
                # URL + title 跨库去重（同一政策可能出现在多个库中）
                if url not in seen_urls and title not in seen_titles:
                    seen_urls.add(url)
                    seen_titles.add(title)
                    all_results.append(r)
                    new_count += 1

            lib_total += len(page_results)
            print(f"      第{page}页: {len(page_results)}条, 新增{new_count}条, 库累计{lib_total}条, 全局累计{len(all_results)}条")

            if len(page_results) < page_size:
                break
            time.sleep(random.uniform(0.3, 0.6))

        # 库间短暂间隔
        if lib_idx < len(SEARCH_LIBRARY_TYPES):
            time.sleep(random.uniform(0.5, 0.8))

    print(f"  [OK] {len(SEARCH_LIBRARY_TYPES)} 个库共 {len(all_results)} 个唯一结果")
    return all_results


# ======================== 独立运行 ========================
if __name__ == "__main__":
    import argparse, sys, os
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

    parser = argparse.ArgumentParser(description="gov.cn 政策文件搜索")
    parser.add_argument("--keyword", "-k", default="安宁疗护")
    args = parser.parse_args()

    results = search_keyword(args.keyword)
    for i, r in enumerate(results[:5], 1):
        print(f"  {i}. {r['title'][:60]}")
    if len(results) > 5:
        print(f"  ... 还有 {len(results) - 5} 条")