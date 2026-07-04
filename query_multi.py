"""
多站组合查询 — 支持多个起点/终点模糊匹配，只展示全局最优。

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
    if origin not in dep_index or dest not in dep_index:
        return None
    return reachability(trains, dep_index, origin, dest, start, ddl, transfer_min=TRANSFER_MIN)


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

    # 跑所有 OD 对
    results: list[tuple[str, str, dict]] = []
    for o in origins:
        for d in dests:
            r = query_one(trains, dep_index, o, d, start, ddl)
            if r is not None:
                results.append((o, d, r))

    # ---- 全局最早到达（直达、换乘分别选最优）----
    best_dea = None  # (arr_min, origin, dest, dict)
    best_tea = None  # (arr_min, origin, dest, dict)
    for o, d, r in results:
        de = r.get("direct_earliest")
        if de:
            de_min = int(de[:2]) * 60 + int(de[3:])
            if best_dea is None or de_min < best_dea[0]:
                best_dea = (de_min, o, d, r)
        path = r.get("path")
        if path:
            arr_min = path[-1][4]
            if best_tea is None or arr_min < best_tea[0]:
                best_tea = (arr_min, o, d, r)

    # ---- 全局最晚出发（直达、换乘分别选最优）----
    best_dld = None  # (dep_min, origin, dest, dict)
    best_tld = None  # (dep_min, origin, dest, dict)
    for o, d, r in results:
        dl = r.get("direct_latest_dep")
        if dl:
            dl_min = int(dl[:2]) * 60 + int(dl[3:])
            if best_dld is None or dl_min > best_dld[0]:
                best_dld = (dl_min, o, d, r)
        ld_path = r.get("latest_departure_path")
        if ld_path:
            dep_min = ld_path[0][3]
            if best_tld is None or dep_min > best_tld[0]:
                best_tld = (dep_min, o, d, r)

    # ================================================================
    # 🕐 最早到达
    # ================================================================
    print("  ── 🕐 最早到达 ──")
    # 直达 — 全局最优
    if best_dea:
        _, o, d, r = best_dea
        print(f"  {bold('直达')}: {o} {r['direct_dep']} ──({r['direct_train']})──→ {d} {bold(r['direct_earliest'])}")
    else:
        print(f"  {bold('直达')}: 无")

    # 换乘 — 全局最优
    if best_tea:
        _, o, d, r = best_tea
        path = r["path"]
        tag = " (≡ 直达)" if len(path) == 1 else ""
        print(f"  {bold('换乘')} ({len(path)} 段){tag}:")
        for i, (frm, to, tc, dep, arr) in enumerate(path, 1):
            a_str = bold(fmt_time(arr)) if i == len(path) else fmt_time(arr)
            transfer = ""
            if i < len(path):
                next_dep = path[i][3]
                transfer = f"  │ 等 {next_dep - arr}min"
            print(f"    {i}. {frm} {fmt_time(dep)} ──({tc})──→ {to} {a_str}{transfer}")
    else:
        print(f"  {bold('换乘')}: 无")

    # ================================================================
    # ⏰ 最晚出发
    # ================================================================
    print()
    print("  ── ⏰ 最晚出发 ──")
    # 直达 — 全局最优
    if best_dld:
        _, o, d, r = best_dld
        print(
            f"  {bold('直达')}: {o} {bold(r['direct_latest_dep'])} ──({r['direct_latest_train']})──→ {d} {r['direct_latest_arr']}"
        )
    else:
        print(f"  {bold('直达')}: 无")

    # 换乘 — 全局最优
    if best_tld:
        _, o, d, r = best_tld
        ld_path = r.get("latest_departure_path")
        if ld_path:
            tag = " (≡ 直达)" if len(ld_path) == 1 else ""
            print(f"  {bold('换乘')} ({len(ld_path)} 段){tag}:")
            for i, (frm, to, tc, dep, arr) in enumerate(ld_path, 1):
                d_str = bold(fmt_time(dep)) if i == 1 else fmt_time(dep)
                transfer = ""
                if i < len(ld_path):
                    next_dep = ld_path[i][3]
                    transfer = f"  │ 等 {next_dep - arr}min"
                print(f"    {i}. {frm} {d_str} ──({tc})──→ {to} {fmt_time(arr)}{transfer}")
    else:
        print(f"  {bold('换乘')}: 无")


if __name__ == "__main__":
    main()
