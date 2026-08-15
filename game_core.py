# -*- coding: utf-8 -*-
"""
game_core.py —— “飞机大战”纯游戏逻辑（不含 GUI、不含网络）。

完全依据《游戏规格说明书》实现：
  - “士”字形飞机的几何定义（10 格）
  - 4 种朝向的顺时针旋转变换
  - 部署阶段边界 / 互斥约束
  - 攻击判定优先级（INVALID / DESTROYED / DAMAGED / WRECKAGE / EMPTY）
  - 胜负判定与参数合法性校验

本模块可独立进行单元测试（不依赖 tkinter / socket）。
"""

import random

# ---------------------------------------------------------------------------
# 1. 飞机几何定义
# ---------------------------------------------------------------------------
# 标准“机头朝上”形态，机头为相对原点 (0,0)。Y 正方向向下。
BASE_COORDS = [
    (0, 0),                                        # 机头 Head
    (-2, 1), (-1, 1), (0, 1), (1, 1), (2, 1),      # 主翼 Wing
    (0, 2),                                        # 机身 Body
    (-1, 3), (0, 3), (1, 3),                       # 尾翼 Tail
]

# 每个相对坐标对应的部件名（用于“文字+图像”说明与染色）
BASE_PARTS = {
    (0, 0): "head",
    (-2, 1): "wing", (-1, 1): "wing", (0, 1): "wing", (1, 1): "wing", (2, 1): "wing",
    (0, 2): "body",
    (-1, 3): "tail", (0, 3): "tail", (1, 3): "tail",
}

ORIENTATIONS = (0, 90, 180, 270)   # 0=朝上 90=朝右 180=朝下 270=朝左（顺时针）

PLANE_CELL_COUNT = 10


def rotate(dx, dy, orientation):
    """对相对坐标应用顺时针旋转。

    依据规格：
      0°   : (dx, dy)
      90°  : (-dy, dx)
      180° : (-dx, -dy)
      270° : (dy, -dx)
    """
    if orientation == 0:
        return (dx, dy)
    if orientation == 90:
        return (-dy, dx)
    if orientation == 180:
        return (-dx, -dy)
    if orientation == 270:
        return (dy, -dx)
    raise ValueError("非法的朝向: %r" % (orientation,))


def plane_relative(orientation):
    """返回指定朝向下的 10 个相对坐标（机头为原点）。"""
    return [rotate(dx, dy, orientation) for (dx, dy) in BASE_COORDS]


def plane_absolute(head, orientation):
    """返回指定机头绝对坐标 + 朝向下的 10 个绝对坐标列表。"""
    hx, hy = head
    return [(hx + dx, hy + dy) for (dx, dy) in plane_relative(orientation)]


def plane_parts(head, orientation):
    """返回 {绝对坐标: 部件名} 的字典（部件名含 head/wing/body/tail）。"""
    hx, hy = head
    parts = {}
    for (dx, dy), name in BASE_PARTS.items():
        rx, ry = rotate(dx, dy, orientation)
        parts[(hx + rx, hy + ry)] = name
    return parts


# ---------------------------------------------------------------------------
# 2. 参数校验
# ---------------------------------------------------------------------------
def validate_params(w, h, n):
    """返回 (ok: bool, error_key: str|None)。

    error_key 用于 i18n 显示：
      'width_too_small' / 'height_too_small' / 'planes_too_few'
      / 'too_crowded' / 'cannot_fit'
    """
    if w < 5:
        return False, "width_too_small"
    if h < 5:
        return False, "height_too_small"
    if n < 1:
        return False, "planes_too_few"
    if n * PLANE_CELL_COUNT > w * h:
        return False, "too_crowded"
    # 面积够不等于放得下（“士”字形无法任意铺满），做一次真实可行性校验，
    # 避免出现如 10×10 放 10 架这类“总面积刚好、实际塞不下”的死局。
    if not can_fit_planes(w, h, n):
        return False, "cannot_fit"
    return True, None


# ---------------------------------------------------------------------------
# 3. 飞机实体
# ---------------------------------------------------------------------------
class Plane:
    """一架飞机。"""

    def __init__(self, head, orientation, index=0):
        self.index = index
        self.head = tuple(head)          # 机头绝对坐标
        self.orientation = orientation
        self.coords = plane_absolute(head, orientation)   # 10 个绝对坐标（含机头）
        self.parts = plane_parts(head, orientation)       # {坐标: 部件名}
        self.alive = True
        self.hit_cells = set()           # 已受损的非机头格子（DAMAGED 记录）

    @property
    def head_coord(self):
        return self.head

    def contains(self, x, y):
        return (x, y) in self.parts

    def part_at(self, x, y):
        return self.parts.get((x, y))


# ---------------------------------------------------------------------------
# 4. 棋盘
# ---------------------------------------------------------------------------
class Board:
    """一个玩家的棋盘：负责部署与承受攻击。"""

    def __init__(self, w, h, n):
        self.w = w
        self.h = h
        self.n = n
        self.planes = []
        self._occupied = {}   # (x,y) -> Plane

    # ---- 部署 ----
    def place(self, head, orientation):
        """尝试放置一架飞机。成功返回 Plane，失败返回 None。"""
        hx, hy = head
        if hx < 1 or hx > self.w or hy < 1 or hy > self.h:
            return None
        coords = plane_absolute((hx, hy), orientation)
        for (x, y) in coords:
            if x < 1 or x > self.w or y < 1 or y > self.h:
                return None          # 边界约束
            if (x, y) in self._occupied:
                return None          # 互斥约束（重叠）
        p = Plane((hx, hy), orientation, len(self.planes))
        for (x, y) in coords:
            self._occupied[(x, y)] = p
        self.planes.append(p)
        return p

    def remove_plane_at(self, x, y):
        """移除覆盖 (x,y) 的整架飞机。成功返回 True。"""
        p = self._occupied.get((x, y))
        if p is None:
            return False
        self.planes.remove(p)
        for c in p.coords:
            if self._occupied.get(c) is p:
                del self._occupied[c]
        return True

    def plane_at(self, x, y):
        return self._occupied.get((x, y))

    def clear(self):
        self.planes = []
        self._occupied = {}

    def count(self):
        return len(self.planes)

    def all_placed(self):
        return len(self.planes) == self.n

    # ---- 承受攻击（防守方判定，优先级严格按规格）----
    def apply_shot(self, x, y, shot_history):
        """按规格优先级判定一次攻击。

        shot_history: 攻击方“本局已成功攻击过的坐标”集合（含空/命中/残骸，但不含 INVALID）。
        返回术语字符串：INVALID / DESTROYED / DAMAGED / WRECKAGE / EMPTY
        """
        # 优先级 1：越界 或 已被攻击过
        if x < 1 or x > self.w or y < 1 or y > self.h or (x, y) in shot_history:
            return "INVALID"

        # 合法攻击：记录进攻击历史
        shot_history.add((x, y))

        plane = self._occupied.get((x, y))
        # 优先级 2：存活飞机的机头
        if plane is not None and plane.alive and (x, y) == plane.head_coord:
            plane.alive = False
            return "DESTROYED"
        # 优先级 3：存活飞机的非机头部件
        if plane is not None and plane.alive:
            plane.hit_cells.add((x, y))
            return "DAMAGED"
        # 优先级 4：已坠毁飞机的任意部件（残骸）
        if plane is not None:
            return "WRECKAGE"
        # 优先级 5：从未属于任何飞机
        return "EMPTY"

    # ---- 胜负 ----
    def all_destroyed(self):
        """所有飞机机头均已被击中（即全部坠毁）。"""
        return len(self.planes) == self.n and all(not p.alive for p in self.planes)

    # ---- 调试/测试辅助 ----
    def occupied_coords(self):
        return set(self._occupied.keys())


# ---------------------------------------------------------------------------
# 5. 随机布置
# ---------------------------------------------------------------------------
def _enumerate_placements(w, h):
    """枚举棋盘上所有合法的飞机放置，返回 [(机头, 朝向, 占用位掩码)]。

    位掩码第 ((y-1)*w + (x-1)) 位表示格子 (x,y) 被占用。
    """
    placements = []
    for ori in ORIENTATIONS:
        for x in range(1, w + 1):
            for y in range(1, h + 1):
                coords = plane_absolute((x, y), ori)
                if all(1 <= cx <= w and 1 <= cy <= h for (cx, cy) in coords):
                    mask = 0
                    for cx, cy in coords:
                        mask |= 1 << ((cy - 1) * w + (cx - 1))
                    placements.append(((x, y), ori, mask))
    return placements


def _solve_exact(placements, n, max_nodes=200000):
    """回溯 + 记忆化：从 placements 里选 n 个互不重叠的放置。

    返回 (indices_or_None, timed_out)：
      indices —— 选中的下标列表；None 表示无解（或达到节点上限，见 timed_out）。
    """
    memo = set()
    state = {"nodes": 0, "timeout": False}

    def dfs(used, idx, count):
        if count == n:
            return []
        if state["nodes"] >= max_nodes:
            state["timeout"] = True
            return None
        state["nodes"] += 1
        key = (used, idx)
        if key in memo:
            return None
        if count + (len(placements) - idx) < n:
            memo.add(key)
            return None
        for i in range(idx, len(placements)):
            m = placements[i][2]
            if used & m == 0:
                r = dfs(used | m, i + 1, count + 1)
                if r is not None:
                    return [i] + r
        memo.add(key)
        return None

    res = dfs(0, 0, 0)
    return res, state["timeout"]


def _exact_cover_solve(placements, n, w, h):
    """精确铺满（n*10 == w*h）时的 MRV 精确覆盖求解器。返回下标列表或 None。"""
    full = (1 << (w * h)) - 1
    cover = {}
    for pi, (_, _, m) in enumerate(placements):
        mm = m
        while mm:
            low = mm & -mm
            cell = low.bit_length() - 1
            cover.setdefault(cell, []).append(pi)
            mm ^= low

    memo = set()

    def dfs(used, count):
        if count == n:
            return [] if used == full else None
        if used in memo:
            return None
        available = full & ~used
        if available == 0:
            return None
        # 选择“可放置方案最少”的空格（MRV），剪枝最强
        best_cell = None
        best_list = None
        a = available
        while a:
            low = a & -a
            cell = low.bit_length() - 1
            valid = [pi for pi in cover.get(cell, ()) if (placements[pi][2] & used) == 0]
            if best_list is None or len(valid) < len(best_list):
                best_cell = cell
                best_list = valid
            a ^= low
        if best_cell is None or not best_list:
            memo.add(used)
            return None
        for pi in best_list:
            r = dfs(used | placements[pi][2], count + 1)
            if r is not None:
                return [pi] + r
        memo.add(used)
        return None

    return dfs(0, 0)


def can_fit_planes(w, h, n):
    """判断 w×h 棋盘能否放下 n 架互不重叠的飞机。"""
    placements = _enumerate_placements(w, h)
    if n * PLANE_CELL_COUNT == w * h:
        return _exact_cover_solve(placements, n, w, h) is not None
    res, timed_out = _solve_exact(placements, n)
    if timed_out:
        return True   # 无法快速判定时乐观放行，交给部署阶段的提示兜底
    return res is not None


def random_place(board):
    """随机自动布置，直到放满 n 架飞机。成功返回 True，失败返回 False（棋盘被清空）。"""
    w, h, n = board.w, board.h, board.n
    placements = _enumerate_placements(w, h)
    random.shuffle(placements)
    if n * PLANE_CELL_COUNT == w * h:
        indices = _exact_cover_solve(placements, n, w, h)
    else:
        indices, timed_out = _solve_exact(placements, n)
        if timed_out:
            indices = None
    board.clear()
    if indices is None:
        return False
    for i in indices:
        head, ori, _ = placements[i]
        if board.place(head, ori) is None:
            board.clear()
            return False
    return True
