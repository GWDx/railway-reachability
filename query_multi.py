"""
多站组合查询 — 支持多个起点/终点模糊匹配。

用法:
    python query_multi.py
"""

from pathlib import Path

from engine import load_trains, build_departure_index, reachability, fmt_time

JSONL_PATH = Path(__file__).resolve().parent / "data" / "train_stops.jsonl"
TRANSFER_MIN = 12


def bold(s: str) -> str:
    return f"\033[1m{s}\033[0m"


def query_one(trains, dep_index, origin, dest, start, ddl) -> dict | None:
    """查询单个 OD 对，车站不存在则返回 None."""
    if origin not in dep_index or dest not in dep_index:
        return None
    return reachability(trains, dep_index, origin, dest, start, ddl, transfer_min=TRANSFER_MIN)


def print_section(results: list[tuple[str, str, dict]]):
    """打印结果区块."""
    print("  ── 🕐 最早到达 ──")
    best_ea = (9999, "", "", "")  # (arr_min, origin, dest, label)

    for o, d, r in results:
        if r is None:
            continue
        de = r.get("direct_earliest")
        if de:
            print(f"  {bold('直达')}: {o} {r['direct_dep']} ──({r['direct_train']})──→ {d} {bold(de)}")
            de_min = _min_of(de)
            if de_min < best_ea[0]:
                best_ea = (de_min, o, d, "直达")
        else:
            print(f"  {bold('直达')}: {o} → {d}  无")

        path = r.get("path")
        if path:
            arr_min = path[-1][4]
            dep_min = path[0][3]
            arr_str = fmt_time(arr_min)
            if len(path) == 1:
                if not de or arr_min < _min_of(de):
                    print(f"  {bold('换乘')}: {o} {fmt_time(dep_min)} → {d} {bold(arr_str)}  (≡ 直达)")
            else:
                print(f"  {bold('换乘')}: {o} {fmt_time(dep_min)} → {d} {bold(arr_str)}  ({len(path)} 段)")
            if arr_min < best_ea[0]:
                best_ea = (arr_min, o, d, "换乘")
        else:
            print(f"  {bold('换乘')}: {o} → {d}  无")

    print(f"\n  → 全局最早到达: {best_ea[1]} → {best_ea[2]} 到达 {bold(fmt_time(best_ea[0]))} ({best_ea[3]})")

    # --- 最晚出发 ---
    print()
    print("  ── ⏰ 最晚出发 ──")
    best_ld = (-1, "", "", "")  # (dep_min, origin, dest, label)

    for o, d, r in results:
        if r is None:
            continue
        dl = r.get("direct_latest_dep")
        if dl:
            print(f"  {bold('直达')}: {o} {bold(dl)} ──({r['direct_latest_train']})──→ {d} {r['direct_latest_arr']}")
            dl_min = _min_of(dl)
            if dl_min > best_ld[0]:
                best_ld = (dl_min, o, d, "直达")
        else:
            print(f"  {bold('直达')}: {o} → {d}  无")

        ld_path = r.get("latest_departure_path")
        if ld_path:
            dep_min = ld_path[0][3]
            dep_str = fmt_time(dep_min)
            arr_str = fmt_time(ld_path[-1][4])
            tag = " (≡ 直达)" if len(ld_path) == 1 else f"  ({len(ld_path)} 段)"
            print(f"  {bold('换乘')}: {o} {bold(dep_str)} → {d} {arr_str}{tag}")
            if dep_min > best_ld[0]:
                best_ld = (dep_min, o, d, "换乘")
        else:
            print(f"  {bold('换乘')}: {o} → {d}  无")

    if best_ld[0] >= 0:
        print(f"\n  → 全局最晚出发: {best_ld[1]} {bold(fmt_time(best_ld[0]))} → {best_ld[2]} ({best_ld[3]})")


def _min_of(t: str) -> int:
    """ "HH:MM" → 分钟数."""
    h, m = t.split(":")
    return int(h) * 60 + int(m)


def main():
    print("=" * 60)
    print("  Railway Reachability Engine — Multi Query")
    print("=" * 60)

    print("\n[1] 加载数据 ...")
    trains = load_trains(JSONL_PATH)
    dep_index = build_departure_index(trains)
    print(f"    已加载 {len(trains)} 趟列车, {len(dep_index)} 个车站")

    origins = ["合肥南", "合肥"]
    dests = ["上海虹桥", "上海"]
    start = "20:00"
    ddl = "23:59"

    print(f"\n[2] 查询: {origins} → {dests}")
    print(f"    当前时间: {start}  DDL: {ddl}  换乘: {TRANSFER_MIN}min")
    print()

    results: list[tuple[str, str, dict]] = []
    for o in origins:
        for d in dests:
            r = query_one(trains, dep_index, o, d, start, ddl)
            results.append((o, d, r))

    print_section(results)


if __name__ == "__main__":
    main()
