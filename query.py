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
    ddl = "17:30"

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

    # ================================================================
    # 🕐 最早到达
    # ================================================================
    print("  ── 🕐 最早到达 ──")
    if result["reachable"]:
        print(f"  换乘可达，到达 {result['earliest_arrival']}")
    elif result["earliest_arrival"] is not None:
        print(f"  DDL 前不可达，最早到达 {result['earliest_arrival']}")
    else:
        print("  无任何可达路径")

    # 直达最早
    if result["direct_earliest"]:
        dep = result["direct_dep"]
        arr = result["direct_earliest"]
        tc = result["direct_train"]
        print(f"  直达: {origin} {dep} ──({tc})──→ {dest} {arr}")
    else:
        print("  直达: 无")

    # 最早到达路径
    path = result["path"]
    if path:
        print(f"  换乘路径 ({len(path)} 段):")
        for i, (frm, to, tc, d, a) in enumerate(path, 1):
            print(f"    {i}. {frm} {fmt_time(d)} ──({tc})──→ {to} {fmt_time(a)}")

    # ================================================================
    # ⏰ 最晚出发
    # ================================================================
    print()
    print("  ── ⏰ 最晚出发 ──")
    if result["latest_departure"]:
        print(f"  最晚 {result['latest_departure']} 出发可赶上 DDL {ddl}")
    else:
        print("  无可行方案")

    # 直达最晚
    if result["direct_latest_dep"]:
        dep = result["direct_latest_dep"]
        arr = result["direct_latest_arr"]
        tc = result["direct_latest_train"]
        print(f"  直达: {origin} {dep} ──({tc})──→ {dest} {arr}")
    else:
        print("  直达: 无")

    # 最晚出发路径
    ld_path = result.get("latest_departure_path")
    if ld_path:
        print(f"  换乘路径 ({len(ld_path)} 段):")
        for i, (frm, to, tc, d, a) in enumerate(ld_path, 1):
            print(f"    {i}. {frm} {fmt_time(d)} ──({tc})──→ {to} {fmt_time(a)}")


if __name__ == "__main__":
    main()
