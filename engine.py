"""
铁路可达性引擎核心模块。

提供：
- JSONL 数据加载
- 时间解析
- 出发索引构建
- Earliest Arrival Time (EAT) 算法
- Reachability 查询
"""

from __future__ import annotations

import heapq
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

# ---------------------------------------------------------------------------
# 数据模型
# ---------------------------------------------------------------------------


@dataclass
class Stop:
    """列车的一个停站。"""

    station: str
    arr_min: Optional[int]  # None 表示始发站（无到达时间）
    dep_min: Optional[int]  # None 表示终到站（无出发时间）


@dataclass
class Train:
    """一趟列车。"""

    code: str  # e.g. "G1"
    train_no: str  # 内部编码
    stops: list[Stop]  # 按运行顺序排列

    @property
    def origin(self) -> str:
        """始发站（从 stops 推导，始终准确）。"""
        return self.stops[0].station

    @property
    def terminus(self) -> str:
        """终到站（从 stops 推导，始终准确）。"""
        return self.stops[-1].station

    @property
    def label(self) -> str:
        """人类可读标签，如 'G1(北京南→上海虹桥)'。"""
        return f"{self.code}({self.origin}→{self.terminus})"


# ---------------------------------------------------------------------------
# 时间工具
# ---------------------------------------------------------------------------


def parse_time(s: str) -> Optional[int]:
    """将 "HH:MM" 转为分钟数, "----" 返回 None."""
    if s == "----":
        return None
    h, m = s.split(":")
    return int(h) * 60 + int(m)


def fmt_time(minutes: int) -> str:
    """将分钟数转为 "HH:MM"."""
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


# ---------------------------------------------------------------------------
# 数据加载
# ---------------------------------------------------------------------------


def load_trains(jsonl_path: Path) -> list[Train]:
    """从 JSONL 文件加载所有列车."""
    trains: list[Train] = []
    with open(jsonl_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            stops = [
                Stop(
                    station=s["station"],
                    arr_min=parse_time(s["arrive"]),
                    dep_min=parse_time(s["depart"]),
                ) for s in rec["stops"]
            ]
            trains.append(Train(
                code=rec["train_code"],
                train_no=rec["train_no"],
                stops=stops,
            ))
    return trains


# ---------------------------------------------------------------------------
# 出发索引
# ---------------------------------------------------------------------------


def build_departure_index(trains: list[Train]) -> dict[str, list[tuple[int, int, int]]]:
    """构建 station → [(train_idx, stop_pos, dep_min), ...] 索引.

    只包含有出发时间的停站（排除终到站）.
    """
    index: dict[str, list[tuple[int, int, int]]] = {}
    for ti, train in enumerate(trains):
        for si, stop in enumerate(train.stops):
            if stop.dep_min is None:
                continue  # 终到站，无法上车
            index.setdefault(stop.station, []).append((ti, si, stop.dep_min))
    return index


# ---------------------------------------------------------------------------
# Earliest Arrival Time 算法
# ---------------------------------------------------------------------------


@dataclass(order=True)
class _PQItem:
    """优先队列中的条目."""
    arr_min: int
    station: str = field(compare=False)
    prev_station: Optional[str] = field(compare=False)
    prev_train: Optional[str] = field(compare=False)


def earliest_arrival(
    trains: list[Train],
    dep_index: dict[str, list[tuple[int, int, int]]],
    origin: str,
    start_time_min: int,
    transfer_min: int = 12,
    ddl_min: int | None = None,
) -> tuple[dict[str, int], dict[str, tuple[str, str]]]:
    """计算从 origin 出发的最早到达时间 (EAT).

    Args:
        trains: 所有列车
        dep_index: station → [(train_idx, stop_pos, dep_min), ...]
        origin: 起点车站名（精确匹配）
        start_time_min: 出发时间（分钟数）
        transfer_min: 同站换乘最小缓冲时间（分钟）
        ddl_min: DDL 截止时间，超过此时间的状态不再探索。None 表示无限制。

    Returns:
        (best_arrival, prev):
            best_arrival[station] = 最早到达分钟数
            prev[station] = (上一站, 车次) 用于路径回溯
    """
    best: dict[str, int] = {origin: start_time_min}
    prev: dict[str, tuple[str, str]] = {}  # station → (prev_station, train_code)

    pq: list[_PQItem] = [_PQItem(arr_min=start_time_min, station=origin, prev_station=None, prev_train=None)]
    heapq.heapify(pq)

    while pq:
        item = heapq.heappop(pq)
        cur_station = item.station
        cur_arr = item.arr_min

        # 更优值已存在，跳过
        if cur_arr > best.get(cur_station, 10**9):
            continue

        # DDL 剪枝：PQ 按到达时间排序，超过 DDL 的后续只会更晚
        if ddl_min is not None and cur_arr > ddl_min:
            break

        # 本站在此之后可以乘坐的列车
        wait_from = cur_arr
        if cur_station != origin:
            wait_from += transfer_min

        # 遍历所有从此站出发的列车
        for ti, si, dep in dep_index.get(cur_station, []):
            if dep < wait_from:
                continue  # 赶不上

            train = trains[ti]
            # 沿列车到达每个后续站
            for sj in range(si + 1, len(train.stops)):
                stop = train.stops[sj]
                arr = stop.arr_min
                if arr is None:
                    continue

                # DDL 剪枝：同行车后续站只会更晚
                if ddl_min is not None and arr > ddl_min:
                    break

                if arr < best.get(stop.station, 10**9):
                    best[stop.station] = arr
                    prev[stop.station] = (cur_station, train.code)
                    heapq.heappush(
                        pq, _PQItem(
                            arr_min=arr,
                            station=stop.station,
                            prev_station=cur_station,
                            prev_train=train.code,
                        ))

    return best, prev


# ---------------------------------------------------------------------------
# 路径回溯
# ---------------------------------------------------------------------------


def reconstruct_path(
    prev: dict[str, tuple[str, str]],
    origin: str,
    dest: str,
) -> list[tuple[str, str, str]]:
    """从 prev 字典回溯完整路径.

    Returns:
        [(from_station, to_station, train_code), ...]
    """
    path: list[tuple[str, str, str]] = []
    cur = dest
    while cur in prev:
        from_station, train_code = prev[cur]
        path.append((from_station, cur, train_code))
        cur = from_station
    path.reverse()
    return path


# ---------------------------------------------------------------------------
# Reachability 查询
# ---------------------------------------------------------------------------


def reachability(
    trains: list[Train],
    dep_index: dict[str, list[tuple[int, int, int]]],
    origin: str,
    dest: str,
    start_time: str,
    ddl: str,
    transfer_min: int = 12,
) -> dict:
    """查询可达性.

    Returns:
        {
            "reachable": bool,
            "arrival": str | None,
            "path": [(from, to, train), ...] | None,
            "earliest_arrival": str,
        }
    """
    start_min = parse_time(start_time)
    ddl_min = parse_time(ddl)

    if start_min is None or ddl_min is None:
        raise ValueError(f"时间格式错误: {start_time}, {ddl}")

    best, prev = earliest_arrival(trains, dep_index, origin, start_min, transfer_min, ddl_min)

    earliest = best.get(dest)
    if earliest is None:
        return {
            "reachable": False,
            "earliest_arrival": None,
            "path": None,
        }

    path = reconstruct_path(prev, origin, dest)

    return {
        "reachable": earliest <= ddl_min,
        "earliest_arrival": fmt_time(earliest),
        "path": path,
    }
