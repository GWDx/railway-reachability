"""
铁路可达性查询 CLI。

用法:
    python query.py
"""

from pathlib import Path

from engine import load_trains, build_departure_index, reachability, fmt_time

# --- 配置 ---
JSONL_PATH = Path(__file__).resolve().parent / "data" / "train_stops.jsonl"
TRANSFER_MIN = 12  # 同站换乘最小缓冲时间（分钟）


def main():
    print("=" * 60)
    print("  Railway Reachability Engine")
    print("=" * 60)

    # 加载数据
    print("\n[1] 加载数据 ...")
    trains = load_trains(JSONL_PATH)
    print(f"    已加载 {len(trains)} 趟列车")

    dep_index = build_departure_index(trains)
    stations = sorted(dep_index.keys())
    print(f"    共 {len(stations)} 个车站")

    # --- 测试查询 ---
    print("\n[2] 测试查询: 合肥南 → 上海虹桥")
    print("-" * 40)

    origin = "合肥南"
    dest = "上海虹桥"
    start = "13:00"
    ddl = "16:00"

    print(f"    起点: {origin}")
    print(f"    终点: {dest}")
    print(f"    当前时间: {start}")
    print(f"    DDL: {ddl}")
    print(f"    换乘缓冲: {TRANSFER_MIN} 分钟")

    # 检查车站是否存在
    for name, label in [(origin, "起点"), (dest, "终点")]:
        if name not in dep_index:
            print(f"\n    ⚠ {label}站 '{name}' 不在数据中！")
            print("    可出发站中包含 '合肥' 的:", [s for s in stations if "合肥" in s])
            print("    可出发站中包含 '上海' 的:", [s for s in stations if "上海" in s])
            return

    result = reachability(trains, dep_index, origin, dest, start, ddl, transfer_min=TRANSFER_MIN)

    print()
    if result["reachable"]:
        print("    ✅ 可达！")
        print(f"    到达时间: {result['earliest_arrival']}")
    else:
        if result["earliest_arrival"] is not None:
            print(f"    ❌ 不可达 (DDL {ddl} 前)")
            print(f"    最早到达: {result['earliest_arrival']}")
        else:
            print("    ❌ 不可达（无任何路径）")

    # 打印路径
    path = result["path"]
    if path:
        print(f"\n    路径 ({len(path)} 段):")
        for i, (frm, to, tc) in enumerate(path, 1):
            print(f"      {i}. {frm} ──({tc})──→ {to}")
    else:
        print("\n    无可用路径。")


if __name__ == "__main__":
    main()
