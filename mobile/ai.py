# -*- coding: utf-8 -*-
"""
ai.py —— 人机对战（单人模式）的本地 AI 对手。

AI 实现与 network.Peer 相同的接口（send / recv / is_closed / close），
因此在 ui.GameApp 中可以直接当作“对手连接”使用，无需改动对局状态机。

AI 策略：猎杀/追打（hunt/target）
  - 平时随机选择一个未攻击过的坐标；
  - 命中（DAMAGED）后，把相邻四格加入候选队列优先攻击；
  - 击落（DESTROYED）后清空候选，重新开始搜索下一架飞机。
"""

import queue
import random

import game_core as gc


class AIOpponent:
    def __init__(self):
        self.inbox = queue.Queue()
        self.rng = random.Random()
        self.w = self.h = self.n = 0
        self.board = None             # AI 自己的棋盘（防守用）
        self.player_shots = set()     # 玩家对 AI 的有效攻击历史
        self.ai_shots = {}            # AI 对玩家棋盘的攻击结果
        self.ai_shot_history = set()  # AI 已攻击过的坐标
        self.my_turn = False
        self.started = False
        self.hunt_queue = []          # 待优先攻击的候选坐标

    # ------------------------------------------------------------------
    # Peer 兼容接口
    # ------------------------------------------------------------------
    def send(self, msg):
        """玩家 -> AI 的消息入口；返回的响应消息进入 inbox 供 recv() 读取。"""
        resp = self._handle(msg)
        for r in resp:
            self.inbox.put(r)
        return True

    def recv(self):
        try:
            return self.inbox.get_nowait()
        except queue.Empty:
            return None

    def is_closed(self):
        return False

    def close(self):
        pass

    # ------------------------------------------------------------------
    # 消息处理（返回响应消息列表）
    # ------------------------------------------------------------------
    def _handle(self, msg):
        t = msg.get("type")
        if t == "params":
            return self._on_params(msg)
        if t == "ready":
            return [{"type": "ready"}]
        if t == "start":
            return self._on_start(msg)
        if t == "shot":
            return self._on_shot(msg)
        if t == "result":
            return self._on_result(msg)
        if t == "rematch":
            self._reset()
            return [{"type": "rematch"}]
        if t == "reveal":
            # 终局复盘：AI 也回传自己的飞机位置
            planes = [{"head": list(p.head), "ori": p.orientation, "alive": p.alive}
                      for p in (self.board.planes if self.board else [])]
            return [{"type": "reveal", "planes": planes}]
        return []   # bye / 其它：忽略

    def _on_params(self, msg):
        self.w = msg["w"]
        self.h = msg["h"]
        self.n = msg["n"]
        self.board = gc.Board(self.w, self.h, self.n)
        gc.random_place(self.board)   # 参数已通过可行性校验，正常都能放下
        return [{"type": "params_accept"}]

    def _on_start(self, msg):
        first = msg.get("first", 0)
        self.started = True
        self.my_turn = (first == 1)      # 玩家编号 0，AI 编号 1
        if self.my_turn:
            return self._fire()
        return []

    def _on_shot(self, msg):
        """玩家攻击 AI：结算并回 result，若回合转给 AI 则顺势反击。"""
        x, y = msg["x"], msg["y"]
        term = self.board.apply_shot(x, y, self.player_shots)
        gameover = (term != "INVALID") and self.board.all_destroyed()
        out = [{"type": "result", "x": x, "y": y, "term": term, "gameover": gameover}]
        if not gameover and term != "INVALID":
            self.my_turn = True
            out.extend(self._fire())
        return out

    def _on_result(self, msg):
        """AI 的攻击结果回执。"""
        x, y, term = msg["x"], msg["y"], msg["term"]
        gameover = bool(msg.get("gameover", False))
        if term == "INVALID":
            self.my_turn = True
            return self._fire()          # 理论上不会发生，防御性重试
        self.ai_shots[(x, y)] = term
        self.ai_shot_history.add((x, y))
        if term == "DAMAGED":
            self._add_hunt_neighbors(x, y)
        elif term == "DESTROYED":
            self.hunt_queue = []         # 该机已坠毁，重新搜索
        self.my_turn = False
        return []

    # ------------------------------------------------------------------
    # 攻击决策
    # ------------------------------------------------------------------
    def _fire(self):
        c = self._choose_shot()
        if c is None:
            return []
        self.ai_shot_history.add(c)
        return [{"type": "shot", "x": c[0], "y": c[1]}]

    def _choose_shot(self):
        # 1. 优先攻击候选（命中相邻格）
        while self.hunt_queue:
            c = self.hunt_queue.pop()
            if c not in self.ai_shot_history:
                return c
        # 2. 随机未攻击格
        cells = [(x, y) for x in range(1, self.w + 1) for y in range(1, self.h + 1)
                 if (x, y) not in self.ai_shot_history]
        if not cells:
            return None
        return self.rng.choice(cells)

    def _add_hunt_neighbors(self, x, y):
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nx, ny = x + dx, y + dy
            if 1 <= nx <= self.w and 1 <= ny <= self.h and (nx, ny) not in self.ai_shot_history:
                self.hunt_queue.append((nx, ny))

    # ------------------------------------------------------------------
    def _reset(self):
        self.board = gc.Board(self.w, self.h, self.n) if self.w else None
        if self.board is not None:
            gc.random_place(self.board)
        self.player_shots = set()
        self.ai_shots = {}
        self.ai_shot_history = set()
        self.my_turn = False
        self.started = False
        self.hunt_queue = []
