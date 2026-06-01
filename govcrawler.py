"""
按关键词保存政策文章 — 五阶段管道。

用法:
    python govcrawler.py
    交互式输入关键词，自动完成搜索→合并→爬取→导出。

阶段:
    1. 搜索 — gov.cn API → output/<kw>.json
    2. 合并 — pcode+title 去重 + 聚合匹配关键词 → output/allKeyword.json
    3. 爬取 — aiohttp 5并发，仅爬唯一URL → 写入 post 字段
    4. 导出 — JSON 转 CSV + XLSX → output/allKeyword.csv / .xlsx
    5. 生成 — XLSX 转逐篇 .docx / .pdf → output/post/ / output/pdf/
"""

import sys
import os
import time

os.chdir(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ".")

from config import OUTPUT_DIR, MERGED_JSON, ALLKEYWORD_CSV, ALLKEYWORD_XLSX, DOCX_DIR, PDF_DIR
from src.search_api import search_keyword
from src.json_handler import write_json, read_json, merge_json, json_to_csv, json_to_xlsx
from src.crawler import crawl_json
from src.generate_docx import main as generate_docx


def parse_keywords(raw: str):
    """解析用户输入：顿号/中文逗号/英文逗号分隔"""
    normalized = raw.replace("、", ",").replace("，", ",")
    return [kw.strip() for kw in normalized.split(",") if kw.strip()]


def check_existing_output() -> bool:
    """检测 output/ 目录下是否有存量 .json 文件，提醒用户备份。"""
    if not os.path.isdir(OUTPUT_DIR):
        return True

    existing = [f for f in os.listdir(OUTPUT_DIR) if f.endswith(".json")]
    if not existing:
        return True

    print("\n" + "!" * 60)
    print("  [WARN] 检测到 output/ 目录已有以下文件：")
    for f in sorted(existing):
        fpath = os.path.join(OUTPUT_DIR, f)
        size_kb = os.path.getsize(fpath) / 1024
        print(f"    - {f}  ({size_kb:.1f} KB)")
    print()
    print("  继续运行将覆盖同名文件，数据不可恢复！")
    print("  建议先复制 output/ 目录到其他位置备份。")
    print("!" * 60)
    choice = input("\n是否继续？（输入 yes 继续，其他任意键退出）: ").strip().lower()
    return choice == "yes"


def main():
    print("=" * 60)
    print("  按关键词保存政策文章")
    print("=" * 60)

    raw = input("\n请输入关键词（顿号/中文逗号/英文逗号分隔）: ").strip()
    keywords = parse_keywords(raw)
    if not keywords:
        print("[FAIL] 未输入有效关键词，退出")
        sys.exit(1)

    print(f"\n关键词: {', '.join(keywords)} ({len(keywords)}个)")
    print(f"输出目录: {OUTPUT_DIR}/")

    if not check_existing_output():
        print("已退出，请先备份 output/ 目录后重试")
        sys.exit(0)

    total_start = time.perf_counter()

    # ── Phase 1: 搜索 ──
    print("\n" + "=" * 60)
    print("  [Phase 1/5] 搜索 API 获取政策列表")
    print("=" * 60)

    keyword_jsons = []
    total_raw = 0
    for idx, kw in enumerate(keywords, 1):
        print(f"\n-- 搜索 [{idx}/{len(keywords)}]: {kw} --")
        results = search_keyword(kw)
        if not results:
            print(f"  [WARN] 关键词 '{kw}' 无结果，跳过")
            continue
        total_raw += len(results)
        json_path = os.path.join(OUTPUT_DIR, f"{kw}.json")
        write_json(json_path, results)
        keyword_jsons.append(json_path)

    if not keyword_jsons:
        print("[FAIL] 所有关键词均无搜索结果，退出")
        sys.exit(1)

    # Phase 1 汇总
    print(f"\n{'-' * 60}")
    print(f"  Phase 1 完成: {len(keywords)} 个关键词共检索到 {total_raw} 条原始结果")
    print("-" * 60)

    # ── Phase 2: 合并去重 ──
    print("\n" + "=" * 60)
    print("  [Phase 2/5] 合并去重（pcode + title）")
    print("-" * 60)

    merged_path = os.path.join(OUTPUT_DIR, MERGED_JSON)
    merge_json(keyword_jsons, merged_path)

    # ── Phase 3: 爬取 ──
    print("\n" + "=" * 60)
    print("  [Phase 3/5] 异步爬取页面正文")
    print("-" * 60)

    crawl_json(merged_path)

    # ── Phase 4: 导出 ──
    print("\n" + "=" * 60)
    print("  [Phase 4/5] 导出 CSV 和 XLSX")
    print("-" * 60)

    csv_path = os.path.join(OUTPUT_DIR, ALLKEYWORD_CSV)
    json_to_csv(merged_path, csv_path)

    xlsx_path = os.path.join(OUTPUT_DIR, ALLKEYWORD_XLSX)
    json_to_xlsx(merged_path, xlsx_path)

    # ── Phase 5: 生成文档 (可选) ──
    print("\n" + "=" * 60)
    print("  [Phase 5/5] 逐篇生成文档 (可选)")
    print("  格式: docx / pdf / both")
    print("-" * 60)

    fmt = input("\n选择格式（docx/pdf/both，其他键跳过）: ").strip().lower()
    if fmt in ("docx", "pdf", "both"):
        generate_docx(fmt)
    else:
        print("  已跳过 Phase 5")
        fmt = ""

    # ── 统计 ──
    total_elapsed = time.perf_counter() - total_start
    merged_items = read_json(merged_path)
    has_post = sum(1 for item in merged_items if item.get("post", "").strip())

    print("\n" + "=" * 60)
    print(f"  [DONE] 全部完成! 耗时 {total_elapsed:.0f}s")
    print(f"  关键词: {len(keywords)}个")
    print(f"  搜索到: {len(merged_items)} 篇去重文章")
    print(f"  含正文: {has_post} 篇")
    print(f"  JSON: {merged_path}")
    print(f"  CSV:  {csv_path}")
    print(f"  XLSX: {xlsx_path}")
    if fmt in ("docx", "both"):
        print(f"  DOCX: {os.path.join(OUTPUT_DIR, DOCX_DIR)}/")
    if fmt in ("pdf", "both"):
        print(f"  PDF:  {os.path.join(OUTPUT_DIR, PDF_DIR)}/")
    print("=" * 60)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n" + "=" * 60)
        print("  [STOP] 用户中断 (Ctrl+C)，已安全退出")
        print("=" * 60)
        sys.exit(0)