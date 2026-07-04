"""
从 train_list TSV 中读取所有车次，查询 2026-07-25 的停站数据，导出为 JSONL。

用法:
    python get-stops.py

输出:
    data/train_stops.jsonl

防风控策略:
    - 每次请求间延迟 REQUEST_DELAY 秒
    - 连续失败 CONSECUTIVE_FAIL_LIMIT 次后，进入冷却期
    - 冷却期休眠 COOLDOWN_SECONDS 秒后恢复
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
TRAIN_TYPE = "G"  # 只查询此类型（None = 全部）

# 风控参数
REQUEST_DELAY = 4  # 每次请求间延迟（秒）
MAX_RETRIES = 1  # 单次查询最大重试次数
CONSECUTIVE_FAIL_LIMIT = 5  # 连续失败多少次触发冷却
COOLDOWN_SECONDS = 60  # 冷却休眠秒数


def extract_train_code(station_train_code: str) -> str:
    """从 'D27(天津西-哈尔滨西)' 中提取纯车次 'D27'。"""
    m = re.match(r"(\w+)", station_train_code)
    return m.group(1) if m else station_train_code


def load_train_codes(tsv_path: Path, train_type: str | None = None) -> list[tuple[str, str, str]]:
    """从 TSV 加载车次，可指定类型过滤（如 'G'），返回 [(train_code, station_train_code, train_no), ...]."""
    codes: list[tuple[str, str, str]] = []
    with open(tsv_path, encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter="\t")
        for row in reader:
            if train_type and row["type"] != train_type:
                continue
            raw = row["station_train_code"]
            code = extract_train_code(raw)
            codes.append((code, raw, row["train_no"]))
    return codes


def load_completed_codes(jsonl_path: Path) -> set[str]:
    """从已有的 JSONL 中读取已查询成功的车次，用于断点续传。"""
    if not jsonl_path.exists():
        return set()
    completed: set[str] = set()
    with open(jsonl_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
                completed.add(rec["train_code"])
            except json.JSONDecodeError:
                pass
    return completed


def query_with_retry(train_code: str, date: str):
    """查询列车停站，失败重试 MAX_RETRIES 次（指数退避），返回 Train 或 None。"""
    for attempt in range(1 + MAX_RETRIES):
        try:
            result = get_train_stops(train=train_code, date=date)
            if result is not None:
                return result
        except Exception:
            pass  # 异常视为失败，下面统一处理

        if attempt < MAX_RETRIES:
            wait = 2**attempt  # 1s, 2s 指数退避
            time.sleep(wait)

    return None


def main():
    codes = load_train_codes(TSV_FILE, TRAIN_TYPE)
    total = len(codes)

    # 断点续传：跳过已查询成功的车次
    completed = load_completed_codes(OUTPUT_FILE)
    if completed:
        print(f"断点续传: 已有 {len(completed)} 条记录，将跳过")

    print(f"共 {total} 个车次，待查询 {total - len(completed)} 个, 日期: {QUERY_DATE}")
    print(f"风控: 请求间隔={REQUEST_DELAY}s, 连续失败{CONSECUTIVE_FAIL_LIMIT}次后冷却{COOLDOWN_SECONDS}s")
    print(f"输出: {OUTPUT_FILE}")

    success = 0
    failed = 0
    skipped = 0
    consecutive_fails = 0

    with open(OUTPUT_FILE, "a", encoding="utf-8") as fout:
        for i, (code, raw, tno) in enumerate(codes, 1):
            # 跳过已完成的
            if code in completed:
                skipped += 1
                continue

            # 正常请求间延迟
            if success > 0 or failed > 0:
                time.sleep(REQUEST_DELAY)

            print(f"\r[{i}/{total}] {code} ...", end="", flush=True)

            train = query_with_retry(code, QUERY_DATE)

            if train is None:
                failed += 1
                consecutive_fails += 1
                print(f"\n  ⚠ WARNING: {code} ({raw}) 查询失败（已重试 {MAX_RETRIES} 次），跳过")

                # 连续失败达到阈值 → 冷却
                if consecutive_fails >= CONSECUTIVE_FAIL_LIMIT:
                    print(f"  🛑 连续失败 {consecutive_fails} 次，触发风控冷却 {COOLDOWN_SECONDS}s ...")
                    time.sleep(COOLDOWN_SECONDS)
                    consecutive_fails = 0
                    print("  ✅ 冷却结束，继续查询。")
                continue

            # 查询成功，重置连续失败计数
            consecutive_fails = 0

            record = {
                "train_code": code,
                "train_no": tno,
                "query_date": QUERY_DATE,
                "stops": [{
                    "station": s.station,
                    "arrive": s.arrive,
                    "depart": s.depart,
                } for s in train.stops],
            }

            fout.write(json.dumps(record, ensure_ascii=False) + "\n")
            fout.flush()
            success += 1

    print(f"\n\n完成: 成功 {success}, 失败 {failed}, 跳过 {skipped}")


if __name__ == "__main__":
    main()
