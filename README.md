# GovCrawler · 中国政府网政策文章采集工具

[![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

按关键词从 [gov.cn](https://www.gov.cn) 搜索政策文件，并发爬取正文，合并去重导出 **JSON、CSV、XLSX** 和 **逐篇 `.docx` / `.pdf`**。

## 目录

- [GovCrawler · 中国政府网政策文章采集工具](#govcrawler--中国政府网政策文章采集工具)
  - [目录](#目录)
  - [项目结构](#项目结构)
  - [快速开始](#快速开始)
  - [五阶段管道](#五阶段管道)
    - [Phase 1 — 搜索](#phase-1--搜索)
    - [Phase 2 — 合并去重](#phase-2--合并去重)
    - [Phase 3 — 爬取 + 关键词回检](#phase-3--爬取--关键词回检)
    - [Phase 4 — 导出](#phase-4--导出)
    - [Phase 5 — 生成 .docx / .pdf（可选）](#phase-5--生成-docx--pdf可选)
  - [字段说明](#字段说明)
  - [独立运行](#独立运行)
  - [配置](#配置)
  - [技术栈](#技术栈)
  - [安全防护](#安全防护)
  - [许可](#许可)

## 项目结构

```
├── govcrawler.py             # 唯一入口 — 交互式运行五阶段管道
├── config.py                # 共享配置（API 地址、搜索库、并发数等）
├── requirements.txt         # Python 依赖
├── README.md
├── LICENSE
│
├── src/
│   ├── search_api.py        # Phase 1 — gov.cn 搜索 API 客户端
│   ├── crawler.py           # Phase 3 — aiohttp 并发爬取 + 关键词回检
│   ├── json_handler.py      # JSON 读写、去重合并、CSV/XLSX 导出
│   └── generate_docx.py     # Phase 5 — XLSX 转逐篇 .docx / .pdf
│
└── output/                  # 产物目录（运行时生成，已加入 .gitignore）
    ├── <keyword>.json       # Phase 1 各关键词搜索结果
    ├── allKeyword.json      # Phase 2 合并去重结果 + Phase 3 写入正文
    ├── allKeyword.csv       # Phase 4 CSV 导出
    ├── allKeyword.xlsx      # Phase 4 XLSX 导出
    ├── docx/                # Phase 5 逐篇 .docx 目录
    └── pdf/                 # Phase 5 逐篇 .pdf 目录
```

## 快速开始

```bash
# 1. 克隆仓库
git clone https://github.com/Ranch007/govcrawler.git
cd govcrawler

# 2. 创建虚拟环境
python -m venv .venv
# Windows:
.venv\Scripts\activate
# Linux/macOS:
source .venv/bin/activate

# 3. 安装依赖
pip install -r requirements.txt

# 4. 运行
python govcrawler.py
```

交互式输入关键词（顿号、逗号分隔均可），五阶段按序执行。`Ctrl+C` 任意阶段均可安全退出，不会抛出异常。

## 五阶段管道

### Phase 1 — 搜索

对每个关键词调用 gov.cn 搜索 API，**遍历全部预配置搜索库**，各库结果跨库去重后合并。

```
GET https://sousuo.www.gov.cn/search-gov/data
  ?t=<library_type>
  &q=<keyword>
  &sortType=1
  &searchfield=           （空=全文搜索）
  &p=<page>&n=250
```

内置 3 个搜索库：

| `t` 值 | 覆盖范围 | 示例 |
|--------|---------|------|
| `zhengcelibrary_gw_bm` | 公文+部门联合索引 | 国办发、国卫基层发等 |
| `zhengce_zy` | 中央有关文件 | "健康中国 2030"规划纲要 |
| `zhengce_gw` | 国务院文件 | 国发、国办发、国函等 |

- **跨库去重**：URL + title 双重去重，去重集合跨库共享，同一政策命中多个库时只保留首条
- **HTML 标签剥离**：API 用 `<em>` 高亮搜索词（如 `<em>安宁疗护</em>`），入库前剥离所有 HTML 标签

每个关键词写入 `output/<keyword>.json`，所有关键词搜索完毕输出总计：

```
Phase 1 完成: 4 个关键词共检索到 112 条原始结果
```

### Phase 2 — 合并去重

所有关键词 JSON 合并为 `allKeyword.json`：

- **pcode + title 双重去重**：以 `pcode|title` 为复合键，相同者只保留首条
- O(1) 哈希去重（`Dict` 索引）
- 新增 **"匹配关键词"** 字段，聚合命中的所有关键词（逗号分隔，排序）

### Phase 3 — 爬取 + 关键词回检

读取合并后 JSON 的所有 `url`，用 **aiohttp 5 并发** 抓取页面，提取正文。

- 正文选择器 `class="pages_content"` 同时覆盖 gov.cn 新旧页面模板
- **正文去重**：gov.cn 页面可能包含多个重复的 `pages_content` div（响应式布局），提取时对相同文本去重，避免正文重复写入
- **关键词回检**：正文中必须包含"匹配关键词"中的至少一个词，否则删除该条目（过滤 API 噪声结果）
- JSON 中 `post` 保留页面原始段落结构（`\n\n`），`sanitize_post()` 推迟到 Phase 4 导出阶段按需调用

### Phase 4 — 导出

- `sanitize_post()` 在此阶段清理全部空白字符（`\s+` 正则），保证 CSV/XLSX 单行兼容
- **CSV**：UTF-8 with BOM，Excel 双击打开不乱码
- **XLSX**：openpyxl 生成，表头加粗、首行冻结

### Phase 5 — 生成 .docx / .pdf（可选）

Phase 4 完成后询问用户选择输出格式——`docx`、`pdf` 或 `both`，其他键跳过。

**共通特性：**
- **逐篇文件**：`序号_标题.ext`，序号补零对齐 `01_xxx.ext`
- **元数据区**：主题分类、发文机关、标题、发文字号、发布日期、关键词（逗号转顿号），标题行 14pt / 加粗
- **正文区**：优先按 `\n\n` 自然段落切分（JSON 保留原始结构），遇旧 sanitized 数据时回退到 `。！？` 句末标点切段
- 表头动态映射（按列名查找，不依赖列序）
- 文件名自动剔除 `\/:*?"<>|` 非法字符，标题超过 60 字截断

**DOCX**（`output/docx/`）：
- `python-docx` 生成
- 字体：仿宋 12pt

**PDF**（`output/pdf/`）：
- `fpdf2` 纯 Python 生成，无需 Word 或 LibreOffice
- 自动查找系统仿宋字体（`simfang.ttf`），与 docx 视觉一致
- A4 页面，自动换页

## 字段说明

| 字段 | 来源 | 说明 |
|------|------|------|
| 序号 | Phase 4 追加 | CSV/XLSX 行号（JSON 中无此字段） |
| pcode | API | 发文字号，如 `国办发〔2026〕11号` |
| title | API | 政策标题 |
| pubtimeStr | API | 发布日期，如 `2026.04.09` |
| url | API | 页面 URL |
| childtype | API | 分类路径 |
| puborg | API | 发文机关 |
| post | Phase 3 追加 | 爬取到的页面正文（JSON 中保留原始段落，CSV/XLSX 中已清理空白） |
| 匹配关键词 | Phase 2 追加 | 该政策命中的所有关键词 |

## 独立运行

```bash
# 搜索单个关键词
python -m src.search_api --keyword 安宁疗护

# 爬取指定 JSON
python -m src.crawler output/allKeyword.json

# XLSX 转逐篇 .docx / .pdf
python -m src.generate_docx --fmt docx
python -m src.generate_docx --fmt pdf
python -m src.generate_docx --fmt both
```

## 配置

修改 `config.py`：

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `SEARCH_LIBRARY_TYPES` | `["zhengcelibrary_gw_bm", "zhengce_zy", "zhengce_gw"]` | 搜索库列表，按序搜索后合并去重 |
| `SEARCH_SEARCHFIELD` | `""` (全文) | 搜索词位置：空=全文，`title:content:summary`=标题+摘要 |
| `SEARCH_PAGE_SIZE` | 250 | 每页条数（最大 250） |
| `SEARCH_MAX_PAGES` | 1 | 最大翻页数 |
| `CONCURRENT` | 5 | 爬取并发数 |
| `REQUEST_DELAY` | (1, 3) | 请求间随机延迟（秒） |
| `OUTPUT_DIR` | `output` | 输出目录 |
| `MERGED_JSON` | `allKeyword.json` | Phase 2 合并文件名 |
| `ALLKEYWORD_CSV` | `allKeyword.csv` | Phase 4 CSV 文件名 |
| `ALLKEYWORD_XLSX` | `allKeyword.xlsx` | Phase 4 XLSX 文件名 |
| `DOCX_DIR` | `docx` | Phase 5 docx 输出子目录（位于 output/ 下） |
| `PDF_DIR` | `pdf` | Phase 5 pdf 输出子目录（位于 output/ 下） |

## 技术栈

| 组件 | 用途 | 依赖 |
|------|------|------|
| 搜索 | gov.cn API 调用、翻页、跨库去重 | `requests` |
| 爬取 | 5 并发 aiohttp 抓取页面正文 + 进度条 | `aiohttp`, `beautifulsoup4` |
| 导出 | JSON 读写、CSV/XLSX 生成 | 标准库 `json`/`csv`、`openpyxl` |
| DOCX | 逐篇政策文档生成 | `python-docx` |
| PDF | 逐篇 PDF 生成，系统仿宋字体 | `fpdf2` |

## 安全防护

- 再次运行检测到 `output/` 已有 JSON 时，列出存量文件并提示输入 `yes` 确认，防止误覆盖
- 全部阶段均捕获 `Ctrl+C`（`KeyboardInterrupt`），中断时打印提示信息，不会抛出 traceback
- 爬取阶段同时按 URL 和 title 双重去重，防止重复请求和处理

## 许可

[MIT](LICENSE)
