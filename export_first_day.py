"""
从 train_list.js 中提取第一天的数据，导出为 TSV 文件。

用法:
    python scripts/export_first_day.py

输出:
    data/train_list_day1.tsv
"""

import json
import re
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
INPUT_FILE = PROJECT_ROOT / "data" / "train_list.js"
OUTPUT_FILE = PROJECT_ROOT / "data" / "train_list_day1.tsv"


def parse_train_list_js(filepath: Path) -> dict:
    """解析 train_list.js，提取其中的 JSON 对象。

    该 JS 文件是 JavaScript 对象字面量格式：
    - 键名不加引号（如 D:, station_train_code:）
    - 字符串值用单引号
    - 可能有尾逗号

    需要先转换为标准 JSON。
    """
    text = filepath.read_text(encoding="utf-8")

    # 去掉 "var train_list = " 前缀
    match = re.search(r"var\s+train_list\s*=\s*", text)
    if not match:
        raise ValueError("未找到 'var train_list = ' 赋值语句")

    obj_text = text[match.end():]
    # 去掉末尾可能的分号
    obj_text = obj_text.rstrip().rstrip(";").rstrip()

    # Step 1: 给裸键加双引号（匹配 {, 后面的 word 或数字 key）
    #   例如: D: → "D": ,  8822: → "8822":
    obj_text = re.sub(
        r'(?<=[{,])\s*([A-Za-z_]\w*|\d+)\s*:',
        r'"\1":',
        obj_text,
    )

    # Step 2: 单引号字符串 → 双引号字符串
    obj_text = obj_text.replace("'", '"')

    return json.loads(obj_text)


def export_first_day(data: dict, output: Path) -> None:
    """导出第一天的数据为 TSV。"""
    # 按日期排序，取第一个
    sorted_dates = sorted(data.keys())
    first_date = sorted_dates[0]
    day_data = data[first_date]

    rows: list[tuple[str, str, str, str]] = []

    for train_type, trains in day_data.items():
        for entry in trains:
            rows.append((
                first_date,
                train_type,
                entry["station_train_code"],
                entry["train_no"],
            ))

    # 写入 TSV
    with output.open("w", encoding="utf-8", newline="") as f:
        f.write("date\ttype\tstation_train_code\ttrain_no\n")
        for row in rows:
            f.write("\t".join(row) + "\n")

    # 统计
    type_counts: dict[str, int] = {}
    for train_type, trains in day_data.items():
        type_counts[train_type] = len(trains)

    print(f"日期: {first_date}")
    print(f"列车总数: {len(rows)}")
    print()
    print("按类型统计:")
    for t in sorted(type_counts.keys()):
        print(f"  {t:>6s}: {type_counts[t]:>5d} 趟")
    print()
    print(f"已导出至: {output}")


def main() -> None:
    data = parse_train_list_js(INPUT_FILE)
    print(f"共加载 {len(data)} 个日期的数据")
    export_first_day(data, OUTPUT_FILE)


if __name__ == "__main__":
    main()
