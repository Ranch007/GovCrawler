"""
共享配置 — 修改参数只需改这一个文件。
"""

# ======================== 搜索 API ========================
SEARCH_API_URL = "https://sousuo.www.gov.cn/search-gov/data"
SEARCH_LIBRARY_TYPES = [                        # 按序搜索多个库，结果合并去重
    "zhengcelibrary_gw_bm",                     #   公文+部门联合索引
    "zhengce_zy",                               #   中央有关文件（如"健康中国2030"）
    "zhengce_gw",                               #   国务院文件
]
SEARCH_SEARCHFIELD = ""                         # 搜索词位置：空=全文，title:content:summary=标题+摘要
SEARCH_PAGE_SIZE = 250                          # 每页条数（最大 250）
SEARCH_MAX_PAGES = 1                            # 最大翻页数

# ======================== 文件路径 ========================
OUTPUT_DIR = "output"              # 输出目录
MERGED_JSON = "allKeyword.json"    # Phase 3 合并结果
ALLKEYWORD_CSV = "allKeyword.csv"  # Phase 4 CSV 导出
ALLKEYWORD_XLSX = "allKeyword.xlsx"  # Phase 4 XLSX 导出
DOCX_DIR = "docx"                    # Phase 5 docx 输出子目录
PDF_DIR = "pdf"                      # Phase 5 pdf 输出子目录

# ======================== 爬虫配置 ========================
REQUEST_DELAY = (1, 3)           # 请求间隔（秒），随机取区间内值
CONCURRENT = 5                   # 并发数（aiohttp）
SSL_VERIFY = True

# ======================== 反爬 ========================
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
]