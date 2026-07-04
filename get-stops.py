"""
从 train_list TSV 中读取所有车次，查询 2026-07-25 的停站数据，导出为 JSONL。

用法:
    python get-stops.py

输出:
    data/train_stops.jsonl
"""

import csv
import json
import re
import sys
import time
from pathlib import Path

from py12306 import get_train_stops

# --- 配置 ---
PROJECT_ROOT = Path(__file__).resolve().parent
TSV_FILE = PROJECT_ROOT / "data" / "train_list_day1.tsv"
OUTPUT_FILE = PROJECT_ROOT / "data" / "train_stops.jsonl"
QUERY_DATE = "2026-07-25"
MAX_RETRIES = 2


def extract_train_code(station_train_code: str) -> str:
    """从 'D27(天津西-哈尔滨西)' 中提取纯车次 'D27'。"""
    m = re.match(r"(\w+)", station_train_code)
    return m.group(1) if m else station_train_code


def load_train_codes(tsv_path: Path) -> list[tuple[str, str, str]]:
    """从 TSV 加载所有车次，返回 [(train_code, station_train_code, train_no), ...]。"""
    codes: list[tuple[str, str, str]] = []
    with open(tsv_path, encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter="\t")
        for row in reader:
            raw = row["station_train_code"]
            code = extract_train_code(raw)
            codes.append((code, raw, row["train_no"]))
    return codes


def query_with_retry(train_code: str, date: str):
    """查询列车停站，失败重试 MAX_RETRIES 次，返回 Train 或 None。"""
    for attempt in range(1 + MAX_RETRIES):
        try:
            result = get_train_stops(train=train_code, date=date)
            if result is not None:
                return result
        except Exception:
            pass  # 异常视为失败，下面统一处理

        if attempt < MAX_RETRIES:
            time.sleep(1)

    return None


def main():
    # 加载车次列表
    codes = load_train_codes(TSV_FILE)
    total = len(codes)
    print(f"共 {total} 个车次，查询日期: {QUERY_DATE}")
    print(f"输出: {OUTPUT_FILE}")

    success = 0
    failed = 0

    with open(OUTPUT_FILE, "w", encoding="utf-8") as fout:
        for i, (code, raw, tno) in enumerate(codes, 1):
            print(f"\r[{i}/{total}] {code} ...", end="", flush=True)

            train = query_with_retry(code, QUERY_DATE)

            if train is None:
                failed += 1
                print(f"\n  ⚠ WARNING: {code} ({raw}) 查询失败（已重试 {MAX_RETRIES} 次），跳过")
                continue

            # 构建输出记录
            record = {
                "train_code": code,
                "station_train_code": raw,
                "train_no": tno,
                "query_date": QUERY_DATE,
                "stops": [{
                    "station": s.station,
                    "arrive": s.arrive,
                    "depart": s.depart,
                } for s in train.stops],
            }

            fout.write(json.dumps(record, ensure_ascii=False) + "\n")
            fout.flush()  # 每条立即落盘
            success += 1

    print(f"\n\n完成: 成功 {success}, 失败 {failed}")


if __name__ == "__main__":
    main()
