# -*- coding: utf-8 -*-
"""
ui.py —— tkinter 图形界面 + 游戏流程编排（局域网联机客户端）。

依赖：game_core、network、i18n。
特性：
  - 完整地图显示（带坐标刻度、可滚动）
  - 鼠标点击 + 键盘（方向键/R/回车/空格/Delete）操作
  - 中 / 英 / 日 三语即时切换
  - 图例 + 朝向预览 + 战斗日志，关键信息“文字+图像”双重说明
"""

import random
import threading
import tkinter as tk
from tkinter import ttk, messagebox

import game_core as gc
import network as net
import sound
from ai import AIOpponent
from i18n import Translator, LANGUAGE_NAMES, LANGUAGES

# ---------------------------------------------------------------------------
# 颜色常量
# ---------------------------------------------------------------------------
C_SEA = "#8ecae6"          # 未攻击海面
C_GRID = "#4f86b0"         # 网格线
C_EMPTY = "#eef3f7"        # 已攻击·空白（敌方棋盘）
C_DAMAGED = "#ffa726"      # 命中部件（敌方棋盘）
C_DESTROYED = "#e53935"    # 击落（敌方棋盘）/ 我方机头红
C_WRECKAGE = "#8d6e63"     # 残骸（敌方棋盘）
C_MY_PLANE = "#4caf50"     # 我方存活机体（绿）
C_MY_HEAD = "#e53935"      # 我方存活机头（红）
C_WRECKED_MINE = "#9e9e9e"  # 我方已坠毁部件（灰）
C_WRECKED_HEAD = "#7f1d1d"  # 我方已坠毁机头（暗红）
C_CURSOR = "#ff4081"       # 光标
C_PREVIEW_OK = "#a5d6a7"   # 部署预览（可放）
C_PREVIEW_BAD = "#ef9a9a"  # 部署预览（不可放）

BG = "#eef4f9"
PANEL = "#ffffff"


def rel_parts(orientation):
    """返回指定朝向的 {相对坐标: 部件名}。"""
    d = {}
    for (dx, dy), name in gc.BASE_PARTS.items():
        d[gc.rotate(dx, dy, orientation)] = name
    return d


def draw_plane_shape(canvas, orientation, cell=20):
    """在小画布上画出某朝向的“士”字形飞机（头红、身绿）。"""
    canvas.delete("all")
    rel = gc.plane_relative(orientation)
    minx = min(p[0] for p in rel)
    maxx = max(p[0] for p in rel)
    miny = min(p[1] for p in rel)
    maxy = max(p[1] for p in rel)
    cw = (maxx - minx + 1) * cell + 6
    ch = (maxy - miny + 1) * cell + 6
    canvas.configure(width=cw, height=ch)
    parts = rel_parts(orientation)
    for (dx, dy) in rel:
        name = parts.get((dx, dy), "body")
        color = C_MY_HEAD if name == "head" else C_MY_PLANE
        x0 = (dx - minx) * cell + 3
        y0 = (dy - miny) * cell + 3
        canvas.create_rectangle(x0, y0, x0 + cell, y0 + cell, fill=color, outline="#2f4f4f", width=1)


class BoardCanvas(tk.Frame):
    """带坐标刻度与滚动条的棋盘画布。"""

    def __init__(self, master, w, h, cell, on_click=None, on_hover=None):
        super().__init__(master)
        self.w = w
        self.h = h
        self.cell = cell
        self.margin = 26
        self.on_click = on_click
        self.on_hover = on_hover
        self.rects = {}
        self.texts = {}
        self.preview_ids = []
        self.cursor_rect = None
        self._last_hover = None

        view_w = min(620, self.margin + w * cell + 8)
        view_h = min(500, self.margin + h * cell + 8)

        self.canvas = tk.Canvas(self, bg="#ffffff", highlightthickness=1,
                                highlightbackground="#9db8cc", width=view_w, height=view_h)
        self.vbar = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.hbar = ttk.Scrollbar(self, orient="horizontal", command=self.canvas.xview)
        self.canvas.configure(yscrollcommand=self.vbar.set, xscrollcommand=self.hbar.set)

        self.canvas.grid(row=0, column=0, sticky="nsew")
        self.vbar.grid(row=0, column=1, sticky="ns")
        self.hbar.grid(row=1, column=0, sticky="ew")
        self.rowconfigure(0, weight=1)
        self.columnconfigure(0, weight=1)

        total_w = self.margin + w * cell + self.margin
        total_h = self.margin + h * cell + self.margin
        self.canvas.configure(scrollregion=(0, 0, total_w, total_h))

        self._build_grid()
        self.canvas.bind("<Button-1>", self._clicked)
        self.canvas.bind("<Motion>", self._motion)

    # ---- 绘制 ----
    def _build_grid(self):
        m = self.margin
        c = self.cell
        for y in range(1, self.h + 1):
            for x in range(1, self.w + 1):
                x0 = m + (x - 1) * c
                y0 = m + (y - 1) * c
                r = self.canvas.create_rectangle(x0, y0, x0 + c, y0 + c,
                                                 fill=C_SEA, outline=C_GRID, width=1)
                self.rects[(x, y)] = r
        fs = max(8, min(10, int(c * 0.45)))
        for x in range(1, self.w + 1):
            self.canvas.create_text(m + (x - 1) * c + c / 2, m / 2, text=str(x),
                                    font=("Consolas", fs), fill="#26455f")
        for y in range(1, self.h + 1):
            self.canvas.create_text(m / 2, m + (y - 1) * c + c / 2, text=str(y),
                                    font=("Consolas", fs), fill="#26455f")

    def set_fill(self, x, y, color):
        r = self.rects.get((x, y))
        if r is not None:
            self.canvas.itemconfigure(r, fill=color)

    def set_mark(self, x, y, text, color):
        c = self.cell
        m = self.margin
        cx = m + (x - 1) * c + c / 2
        cy = m + (y - 1) * c + c / 2
        size = max(9, int(c * 0.55))
        if (x, y) in self.texts:
            self.canvas.itemconfigure(self.texts[(x, y)], text=text, fill=color,
                                      font=("Consolas", size))
        else:
            self.texts[(x, y)] = self.canvas.create_text(cx, cy, text=text, fill=color,
                                                         font=("Consolas", size))

    def clear_mark(self, x, y):
        if (x, y) in self.texts:
            self.canvas.delete(self.texts.pop((x, y)))

    def clear_all_marks(self):
        for tid in self.texts.values():
            self.canvas.delete(tid)
        self.texts.clear()

    def set_cursor(self, x, y):
        m = self.margin
        c = self.cell
        if x is None:
            if self.cursor_rect is not None:
                self.canvas.delete(self.cursor_rect)
                self.cursor_rect = None
            return
        x0 = m + (x - 1) * c + 1
        y0 = m + (y - 1) * c + 1
        x1 = m + x * c - 1
        y1 = m + y * c - 1
        if self.cursor_rect is not None:
            self.canvas.coords(self.cursor_rect, x0, y0, x1, y1)
        else:
            self.cursor_rect = self.canvas.create_rectangle(x0, y0, x1, y1,
                                                            outline=C_CURSOR, width=3)
        self.canvas.tag_raise(self.cursor_rect)

    def set_preview(self, coords, valid):
        self.clear_preview()
        m = self.margin
        c = self.cell
        for (x, y) in coords:
            if 1 <= x <= self.w and 1 <= y <= self.h:
                x0 = m + (x - 1) * c + 2
                y0 = m + (y - 1) * c + 2
                x1 = m + x * c - 2
                y1 = m + y * c - 2
                rid = self.canvas.create_rectangle(x0, y0, x1, y1,
                                                   outline=C_PREVIEW_OK if valid else C_PREVIEW_BAD,
                                                   width=2)
                self.preview_ids.append(rid)

    def clear_preview(self):
        for rid in self.preview_ids:
            self.canvas.delete(rid)
        self.preview_ids = []

    # ---- 事件 ----
    def cell_from_event(self, event):
        cx = self.canvas.canvasx(event.x)
        cy = self.canvas.canvasy(event.y)
        x = int((cx - self.margin) // self.cell) + 1
        y = int((cy - self.margin) // self.cell) + 1
        if 1 <= x <= self.w and 1 <= y <= self.h:
            return x, y
        return None

    def _clicked(self, event):
        cell = self.cell_from_event(event)
        if cell is None:
            return
        self.set_cursor(*cell)
        if self.on_click:
            self.on_click(*cell)

    def _motion(self, event):
        if self.on_hover is None:
            return
        cell = self.cell_from_event(event)
        if cell != self._last_hover:
            self._last_hover = cell
            self.on_hover(cell)


# ---------------------------------------------------------------------------
# 主应用
# ---------------------------------------------------------------------------
class GameApp:
    def __init__(self, root):
        self.root = root
        self.tr = Translator("zh")

        self.peer = None
        self.host_socket = None
        self.my_index = None
        self.phase = "menu"
        self.user_closing = False
        self.host_mode = "direct"
        self.join_mode = "direct"
        self.room_code = ""
        self.opp_disconnected = False
        self.waiting_relay = False
        self.versus_ai = False

        # 参数
        self.param_w = tk.StringVar(value="10")
        self.param_h = tk.StringVar(value="10")
        self.param_n = tk.StringVar(value="3")
        self.host_port_var = tk.StringVar(value=str(net.DEFAULT_PORT))
        self.host_port = net.DEFAULT_PORT
        self.relay_addr_var = tk.StringVar(value="broker.emqx.io:1883")

        # 对局状态
        self.w = 10
        self.h = 10
        self.n = 3
        self.board = None
        self.orientation = 0
        self.cursor = (1, 1)
        self._deploy_hover = None
        self.my_shots = {}            # (x,y) -> term（敌方棋盘）
        self.my_shot_history = set()
        self.enemy_shots_on_me = {}   # (x,y) -> term（我方棋盘）
        self.enemy_shot_history = set()
        self.revealed_enemy_planes = []
        self.my_turn = False
        self.awaiting_result = False
        self.i_ready = False
        self.opp_ready = False
        self.started = False
        self.game_over_winner = None
        self.want_rematch = False
        self.opp_want_rematch = False

        # 页面引用（语言切换/状态刷新用）
        self.board_my = None
        self.board_enemy = None
        self.orientation_var = None
        self.count_label = None
        self.deploy_msg_label = None
        self.status_label = None
        self.log_text = None
        self.over_hint_label = None

        self._configure_root()
        self._build_topbar()
        self.build_menu()

        # 键盘
        for key in ("<Left>", "<Right>", "<Up>", "<Down>", "<space>", "<Return>",
                    "<Delete>", "<BackSpace>", "r", "R"):
            self.root.bind(key, self._on_key)

        self.root.after(50, self._poll)

    # ------------------------------------------------------------------
    # 基础
    # ------------------------------------------------------------------
    def _configure_root(self):
        self.root.title(self.tr.t("app_title"))
        self.root.geometry("1280x820")
        self.root.minsize(1000, 680)
        self.root.configure(bg=BG)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    def _build_topbar(self):
        self.topbar = tk.Frame(self.root, bg="#1f3a52", height=46)
        self.topbar.pack(side="top", fill="x")
        self.topbar.pack_propagate(False)
        self.title_label = tk.Label(self.topbar, text=self.tr.t("app_title"),
                                    bg="#1f3a52", fg="#ffffff", font=("", 14, "bold"))
        self.title_label.pack(side="left", padx=14)
        tk.Label(self.topbar, text=self.tr.t("language_label"),
                 bg="#1f3a52", fg="#cfe0ee", font=("", 9)).pack(side="right", padx=(8, 2))
        for lang in LANGUAGES:
            mark = "● " if lang == self.tr.lang else ""
            b = tk.Button(self.topbar, text=mark + LANGUAGE_NAMES[lang],
                          relief="flat", bg="#2c4f6e", fg="#ffffff", activebackground="#3b6487",
                          activeforeground="#ffffff", bd=0, padx=8, pady=3,
                          command=lambda l=lang: self._apply_language(l))
            b.pack(side="right", padx=3, pady=8)
        self.page = tk.Frame(self.root, bg=BG)
        self.page.pack(side="top", fill="both", expand=True)

    def _apply_language(self, lang):
        self.tr.set_lang(lang)
        self.root.title(self.tr.t("app_title"))
        self.title_label.configure(text=self.tr.t("app_title"))
        # 重建顶栏语言按钮（高亮当前）
        for w in self.topbar.winfo_children():
            if w not in (self.title_label,):
                w.destroy()
        self._build_lang_buttons()
        self.rebuild_page()

    def _build_lang_buttons(self):
        # 标题已存在，重建语言按钮 + 标签
        tk.Label(self.topbar, text=self.tr.t("language_label"),
                 bg="#1f3a52", fg="#cfe0ee", font=("", 9)).pack(side="right", padx=(8, 2))
        for lang in LANGUAGES:
            mark = "● " if lang == self.tr.lang else ""
            b = tk.Button(self.topbar, text=mark + LANGUAGE_NAMES[lang],
                          relief="flat", bg="#2c4f6e", fg="#ffffff", activebackground="#3b6487",
                          activeforeground="#ffffff", bd=0, padx=8, pady=3,
                          command=lambda l=lang: self._apply_language(l))
            b.pack(side="right", padx=3, pady=8)

    def _clear_page(self):
        """销毁当前页面所有子控件并清空页面级引用。"""
        for w in self.page.winfo_children():
            w.destroy()
        self.board_my = self.board_enemy = None
        self.orientation_var = self.count_label = self.deploy_msg_label = None
        self.status_label = self.log_text = self.over_hint_label = None
        self.shape_canvas = None
        self._deploy_hover = None

    def rebuild_page(self):
        """按当前 phase 重建页面（语言切换时调用）。各 build_* 会先清空页面。"""
        dispatch = {
            "menu": self.build_menu,
            "help": self.build_help_page,
            "host_setup": self.build_host_setup_page,
            "host_wait": self.build_host_page,
            "join": self.build_join_page,
            "connecting": self.build_connecting,
            "params_host": self.build_params_host_page,
            "params_wait": self.build_params_wait_page,
            "params_confirm": self.build_params_confirm_page,
            "deploy": self.build_deploy_page,
            "battle": self.build_battle_page,
            "over": self.build_over_page,
        }
        dispatch.get(self.phase, self.build_menu)()

    # ------------------------------------------------------------------
    # 主菜单
    # ------------------------------------------------------------------
    def build_menu(self):
        self._clear_page()
        self.phase = "menu"
        box = tk.Frame(self.page, bg=BG)
        box.place(relx=0.5, rely=0.5, anchor="center")
        tk.Label(box, text=self.tr.t("app_title"), bg=BG, fg="#1f3a52",
                 font=("", 22, "bold")).pack(pady=(0, 4))
        tk.Label(box, text=self.tr.t("menu_subtitle"), bg=BG, fg="#54718a",
                 font=("", 11)).pack(pady=(0, 20))

        def big_btn(text, cmd, accent="#2e7d32"):
            b = tk.Button(box, text=text, command=cmd, font=("", 13, "bold"),
                          width=26, height=2, bd=0, cursor="hand2",
                          bg=accent, fg="#ffffff", activebackground="#1b5e20",
                          activeforeground="#ffffff")
            b.pack(pady=6)
            return b

        big_btn(self.tr.t("btn_host"), self.do_host, "#2e7d32")
        big_btn(self.tr.t("btn_join"), self.do_join, "#1565c0")
        big_btn(self.tr.t("btn_ai"), self.do_ai, "#00695c")
        big_btn(self.tr.t("btn_help"), self.build_help_page, "#6a4fa3")
        big_btn(self.tr.t("btn_quit"), self._on_close, "#b03a3a")

    def build_help_page(self):
        self._clear_page()
        self.phase = "help"
        header = tk.Frame(self.page, bg=BG)
        header.pack(fill="x", padx=10, pady=(10, 4))
        tk.Label(header, text=self.tr.t("help_title"), bg=BG, font=("", 14, "bold"),
                 fg="#1f3a52").pack(side="left")
        self._button(header, self.tr.t("btn_back"), self.build_menu, accent="#455a64").pack(side="right")

        body = tk.Frame(self.page, bg=PANEL, bd=1, relief="solid")
        body.pack(fill="both", expand=True, padx=10, pady=6)
        txt = tk.Text(body, wrap="word", font=("", 10), bg="#ffffff", relief="flat",
                      padx=12, pady=10, highlightthickness=0, cursor="arrow", takefocus=0)
        sb = ttk.Scrollbar(body, orient="vertical", command=txt.yview)
        txt.configure(yscrollcommand=sb.set)
        txt.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        # 禁止选中文本（帮助页只读，不参与输入/复制）
        for seq in ("<Button-1>", "<ButtonRelease-1>", "<B1-Motion>",
                    "<Double-Button-1>", "<Control-Button-1>"):
            txt.bind(seq, lambda e: "break")
        txt.insert("1.0", self.tr.t("help_body"))
        txt.configure(state="disabled")

    # ------------------------------------------------------------------
    # 联网：主机 / 客户端
    # ------------------------------------------------------------------
    def do_host(self):
        self.my_index = 0
        self.versus_ai = False
        self.phase = "host_setup"
        self.build_host_setup_page()

    def _accept_loop(self):
        try:
            peer = net.accept_client(self.host_socket)
        except OSError:
            self.root.after(0, lambda: self._host_accept_error())
            return
        self.root.after(0, self._on_host_connected, peer)

    def _host_accept_error(self):
        if self.phase == "host_wait":
            messagebox.showerror(self.tr.t("host_title"), self.tr.t("conn_failed"))
            self._cleanup_connection()
            self.build_menu()

    def _on_host_connected(self, peer):
        if self.phase != "host_wait":
            peer.close()
            return
        self.peer = peer
        try:
            self.host_socket.close()
        except OSError:
            pass
        self.host_socket = None
        self.phase = "params_host"
        self.build_params_host_page()

    def do_join(self):
        self.phase = "join"
        self.my_index = 1
        self.versus_ai = False
        self.build_join_page()

    def do_ai(self):
        """人机对战（单人）：以本地 AI 作为对手。"""
        self.my_index = 0
        self.versus_ai = True
        self.peer = AIOpponent()
        self.phase = "params_host"
        self.build_params_host_page()

    def start_connect(self, host, port):
        self.build_connecting()
        threading.Thread(target=self._connect_loop, args=(host, port), daemon=True).start()

    def _connect_loop(self, host, port):
        try:
            peer = net.connect_to_host(host, port)
        except OSError:
            self.root.after(0, self._connect_failed)
            return
        self.root.after(0, self._on_client_connected, peer)

    def _connect_failed(self):
        if self.phase == "connecting":
            messagebox.showerror(self.tr.t("join_title"), self.tr.t("conn_failed"))
            self.build_join_page()

    def _on_client_connected(self, peer):
        self.peer = peer
        self.phase = "params_wait"
        self.build_params_wait_page()

    # ------------------------------------------------------------------
    # 主机页 / 加入页 / 连接中
    # ------------------------------------------------------------------
    def build_host_setup_page(self):
        self._clear_page()
        self.phase = "host_setup"
        box = self._centered_box()
        tk.Label(box, text=self.tr.t("host_setup_title"), bg=PANEL, font=("", 16, "bold"),
                 fg="#1f3a52").pack(pady=(0, 8))
        self.host_mode_var = tk.StringVar(value=self.host_mode)
        mode_row = tk.Frame(box, bg=PANEL)
        mode_row.pack(pady=2)
        for value, key in (("direct", "mode_direct"), ("relay", "mode_relay")):
            tk.Radiobutton(mode_row, text=self.tr.t(key), variable=self.host_mode_var, value=value,
                           bg=PANEL, command=self._on_host_mode_change, font=("", 10)).pack(side="left", padx=8)

        if self.host_mode == "relay":
            rrow = tk.Frame(box, bg=PANEL)
            rrow.pack(pady=6)
            tk.Label(rrow, text=self.tr.t("relay_server"), bg=PANEL, width=18, anchor="e").grid(row=0, column=0, padx=4)
            tk.Entry(rrow, textvariable=self.relay_addr_var, width=20, font=("Consolas", 11)).grid(row=0, column=1)
            tk.Label(box, text=self.tr.t("relay_addr_hint"), bg=PANEL, fg="#54718a",
                     font=("", 9)).pack(pady=(2, 0))
        else:
            ip = net.get_primary_ip() or self.tr.t("host_ip_unknown")
            tk.Label(box, text=self.tr.t("host_your_ip"), bg=PANEL, font=("", 11)).pack()
            tk.Label(box, text=ip, bg=PANEL, fg="#1565c0", font=("Consolas", 13, "bold")).pack(pady=(0, 4))
            row = tk.Frame(box, bg=PANEL)
            row.pack(pady=2)
            tk.Label(row, text=self.tr.t("host_port"), bg=PANEL, width=14, anchor="e").grid(row=0, column=0, padx=4)
            tk.Entry(row, textvariable=self.host_port_var, width=10, justify="center",
                     font=("Consolas", 13)).grid(row=0, column=1)
            tk.Label(box, text=self.tr.t("host_port_hint"), bg=PANEL, fg="#54718a",
                     font=("", 9), wraplength=400, justify="left").pack(pady=(6, 0))

        self.host_status_label = tk.Label(box, text="", bg=PANEL, fg="#c62828", font=("", 10),
                                          wraplength=380, justify="left")
        self.host_status_label.pack(pady=(6, 0))
        btns = tk.Frame(box, bg=PANEL)
        btns.pack(pady=12)
        self._button(btns, self.tr.t("btn_start_listen"), self.start_hosting, accent="#2e7d32").pack(side="left", padx=6)
        self._button(btns, self.tr.t("btn_back"), self._cancel_host).pack(side="left", padx=6)

    def _on_host_mode_change(self):
        self.host_mode = self.host_mode_var.get()
        self.build_host_setup_page()

    def start_hosting(self):
        sound.click()
        if self.host_mode == "relay":
            self._start_relay_host()
            return
        try:
            port = int(self.host_port_var.get().strip())
            if not (1 <= port <= 65535):
                raise ValueError
        except ValueError:
            messagebox.showerror(self.tr.t("host_setup_title"), self.tr.t("err_port_invalid"))
            return
        self.host_port = port
        try:
            self.host_socket = net.create_host_socket(port)
        except OSError as e:
            messagebox.showerror(self.tr.t("host_setup_title"), str(e))
            return
        self.phase = "host_wait"
        self.build_host_page()
        threading.Thread(target=self._accept_loop, daemon=True).start()

    def _start_relay_host(self):
        addr = self.relay_addr_var.get().strip()
        broker, port = self._parse_relay_addr(addr)
        self.host_status_label.configure(text=self.tr.t("connecting"), fg="#54718a")
        threading.Thread(target=self._mqtt_host_loop, args=(broker, port), daemon=True).start()

    def _mqtt_host_loop(self, broker, port):
        try:
            code = net.gen_room_code()
            peer = net.mqtt_host(code, broker=broker, port=port)
        except OSError:
            self.root.after(0, self._relay_host_error)
            return
        self.root.after(0, self._on_relay_host, peer, code)

    def _relay_host_error(self):
        self.host_status_label.configure(text=self.tr.t("relay_error"), fg="#c62828")

    def _on_relay_host(self, peer, code):
        if self.phase != "host_setup":
            peer.close()
            return
        self.peer = peer
        self.room_code = code
        self.waiting_relay = True
        self.host_status_label.configure(
            text=self.tr.t("your_room_code") + "  " + code + "\n" + self.tr.t("waiting_relay_client"),
            fg="#2e7d32")

    @staticmethod
    def _parse_relay_addr(addr):
        addr = addr.strip()
        if ":" in addr:
            host, port = addr.rsplit(":", 1)
            try:
                port = int(port)
            except ValueError:
                port = 4000
        else:
            host, port = addr, 4000
        return host, port

    def build_host_page(self):
        self._clear_page()
        self.phase = "host_wait"
        box = self._centered_box()
        tk.Label(box, text=self.tr.t("host_title"), bg=PANEL, font=("", 16, "bold"),
                 fg="#1f3a52").pack(pady=(0, 10))
        ip = net.get_primary_ip() or self.tr.t("host_ip_unknown")
        tk.Label(box, text=self.tr.t("host_your_ip"), bg=PANEL, font=("", 11)).pack()
        tk.Label(box, text=ip, bg=PANEL, fg="#1565c0", font=("Consolas", 15, "bold")).pack(pady=4)
        tk.Label(box, text="%s：%d" % (self.tr.t("host_port"), self.host_port), bg=PANEL,
                 font=("Consolas", 12)).pack(pady=2)
        tk.Label(box, text=self.tr.t("host_waiting"), bg=PANEL, fg="#54718a",
                 wraplength=420, justify="left", font=("", 10)).pack(pady=(10, 14))
        self._button(box, self.tr.t("btn_back"), self._cancel_host).pack(pady=(0, 2))

    def _cancel_host(self):
        self._cleanup_connection()
        self.build_menu()

    def build_join_page(self):
        self._clear_page()
        self.phase = "join"
        box = self._centered_box()
        tk.Label(box, text=self.tr.t("join_title"), bg=PANEL, font=("", 16, "bold"),
                 fg="#1f3a52").pack(pady=(0, 8))
        self.join_mode_var = tk.StringVar(value=self.join_mode)
        mode_row = tk.Frame(box, bg=PANEL)
        mode_row.pack(pady=2)
        for value, key in (("direct", "mode_direct"), ("relay", "mode_relay")):
            tk.Radiobutton(mode_row, text=self.tr.t(key), variable=self.join_mode_var, value=value,
                           bg=PANEL, command=self._on_join_mode_change, font=("", 10)).pack(side="left", padx=8)

        if self.join_mode == "relay":
            rr1 = tk.Frame(box, bg=PANEL)
            rr1.pack(pady=4)
            tk.Label(rr1, text=self.tr.t("relay_server"), bg=PANEL, width=18, anchor="e").grid(row=0, column=0, padx=4)
            relay_entry = tk.Entry(rr1, textvariable=self.relay_addr_var, width=20, font=("Consolas", 11))
            relay_entry.grid(row=0, column=1)
            rr2 = tk.Frame(box, bg=PANEL)
            rr2.pack(pady=4)
            tk.Label(rr2, text=self.tr.t("room_code_label"), bg=PANEL, width=14, anchor="e").grid(row=0, column=0, padx=4)
            code_entry = tk.Entry(rr2, width=12, justify="center", font=("Consolas", 16))
            code_entry.grid(row=0, column=1)
            self.join_code_entry = code_entry
        else:
            row = tk.Frame(box, bg=PANEL)
            row.pack(pady=4)
            tk.Label(row, text=self.tr.t("join_ip"), bg=PANEL, width=20, anchor="e").grid(row=0, column=0, padx=4)
            ip_entry = tk.Entry(row, width=26, font=("Consolas", 12))
            ip_entry.grid(row=0, column=1)
            ip_entry.insert(0, "127.0.0.1")
            row2 = tk.Frame(box, bg=PANEL)
            row2.pack(pady=4)
            tk.Label(row2, text=self.tr.t("join_port"), bg=PANEL, width=14, anchor="e").grid(row=0, column=0, padx=4)
            port_entry = tk.Entry(row2, width=22, font=("Consolas", 12))
            port_entry.grid(row=0, column=1)
            port_entry.insert(0, str(net.DEFAULT_PORT))

        self.join_status_label = tk.Label(box, text="", bg=PANEL, fg="#c62828", font=("", 10))
        self.join_status_label.pack(pady=(6, 0))
        btns = tk.Frame(box, bg=PANEL)
        btns.pack(pady=12)
        if self.join_mode == "relay":
            self._button(btns, self.tr.t("btn_join_room"), self._start_relay_join_from_ui,
                         accent="#1565c0").pack(side="left", padx=6)
        else:
            self._button(btns, self.tr.t("btn_connect"),
                         lambda: self._do_connect(ip_entry, port_entry), accent="#1565c0").pack(side="left", padx=6)
        self._button(btns, self.tr.t("btn_back"), self.build_menu).pack(side="left", padx=6)

    def _on_join_mode_change(self):
        self.join_mode = self.join_mode_var.get()
        self.build_join_page()

    def _start_relay_join_from_ui(self):
        addr = self.relay_addr_var.get().strip()
        code = self.join_code_entry.get().strip().upper()
        if not code:
            self.join_status_label.configure(text=self.tr.t("relay_join_error"))
            return
        host, port = self._parse_relay_addr(addr)
        self.join_status_label.configure(text=self.tr.t("connecting"), fg="#54718a")
        threading.Thread(target=self._relay_join_loop, args=(host, port, code), daemon=True).start()

    def _relay_join_loop(self, broker, port, code):
        try:
            peer = net.mqtt_join(code, broker=broker, port=port)
            peer.send({"type": "hello"})   # 通知主机：客户端已加入
        except OSError:
            self.root.after(0, self._relay_join_error)
            return
        self.root.after(0, self._on_client_connected, peer)

    def _relay_join_error(self):
        self.join_status_label.configure(text=self.tr.t("relay_join_error"), fg="#c62828")

    def _do_connect(self, ip_entry, port_entry):
        host = ip_entry.get().strip()
        try:
            port = int(port_entry.get().strip())
        except ValueError:
            messagebox.showerror(self.tr.t("join_title"), self.tr.t("conn_failed"))
            return
        if not host:
            messagebox.showerror(self.tr.t("join_title"), self.tr.t("conn_failed"))
            return
        self.start_connect(host, port)

    def build_connecting(self):
        self._clear_page()
        self.phase = "connecting"
        box = self._centered_box()
        tk.Label(box, text=self.tr.t("connecting"), bg=PANEL, font=("", 14)).pack(pady=20)

    # ------------------------------------------------------------------
    # 参数
    # ------------------------------------------------------------------
    def build_params_host_page(self):
        self._clear_page()
        self.phase = "params_host"
        box = self._centered_box()
        tk.Label(box, text=self.tr.t("params_title"), bg=PANEL, font=("", 16, "bold"),
                 fg="#1f3a52").pack(pady=(0, 4))
        tk.Label(box, text=self.tr.t("params_hint"), bg=PANEL, fg="#54718a",
                 font=("", 9), wraplength=420, justify="left").pack(pady=(0, 10))

        err = tk.Label(box, text="", bg=PANEL, fg="#c62828", font=("", 10))
        err.pack()

        def field(label, var):
            f = tk.Frame(box, bg=PANEL)
            f.pack(pady=4, fill="x")
            tk.Label(f, text=label, bg=PANEL, width=26, anchor="e").pack(side="left", padx=4)
            e = tk.Entry(f, textvariable=var, width=10, justify="center", font=("Consolas", 13))
            e.pack(side="left")
            return e

        field(self.tr.t("map_width"), self.param_w)
        field(self.tr.t("map_height"), self.param_h)
        field(self.tr.t("num_planes"), self.param_n)

        def confirm():
            try:
                w = int(self.param_w.get())
                h = int(self.param_h.get())
                n = int(self.param_n.get())
            except ValueError:
                err.configure(text=self.tr.t("err_params_invalid"))
                return
            ok, ekey = gc.validate_params(w, h, n)
            if not ok:
                err.configure(text=self.tr.t("err_" + ekey))
                return
            self.w, self.h, self.n = w, h, n
            self.board = gc.Board(w, h, n)
            self.peer.send({"type": "params", "w": w, "h": h, "n": n})
            err.configure(text=self.tr.t("waiting_client_accept"), fg="#2e7d32")

        self._button(box, self.tr.t("btn_confirm_params"), confirm, accent="#2e7d32").pack(pady=14)
        self._button(box, self.tr.t("btn_back"), self._cancel_host).pack(pady=(0, 2))

    def build_params_wait_page(self):
        self._clear_page()
        self.phase = "params_wait"
        box = self._centered_box()
        tk.Label(box, text=self.tr.t("params_waiting"), bg=PANEL, font=("", 13)).pack(pady=20)

    def build_params_confirm_page(self):
        self._clear_page()
        self.phase = "params_confirm"
        box = self._centered_box()
        tk.Label(box, text=self.tr.t("params_confirm_title"), bg=PANEL, font=("", 16, "bold"),
                 fg="#1f3a52").pack(pady=(0, 10))
        info = ("%s：%d\n%s：%d\n%s：%d" % (
            self.tr.t("map_width"), self.w,
            self.tr.t("map_height"), self.h,
            self.tr.t("num_planes"), self.n))
        tk.Label(box, text=info, bg=PANEL, font=("Consolas", 13), justify="left").pack(pady=6)
        btns = tk.Frame(box, bg=PANEL)
        btns.pack(pady=16)
        self._button(btns, self.tr.t("btn_accept"), self._accept_params, accent="#2e7d32").pack(side="left", padx=6)
        self._button(btns, self.tr.t("btn_reject"), self._reject_params, accent="#b03a3a").pack(side="left", padx=6)

    def _accept_params(self):
        self.board = gc.Board(self.w, self.h, self.n)
        self.peer.send({"type": "params_accept"})
        self._enter_deploy()

    def _reject_params(self):
        self.peer.send({"type": "params_reject"})
        self.phase = "params_wait"
        self.build_params_wait_page()

    def _on_params_received(self, msg):
        self.w = msg["w"]
        self.h = msg["h"]
        self.n = msg["n"]
        self.phase = "params_confirm"
        self.build_params_confirm_page()

    def _on_params_accept(self):
        self._enter_deploy()

    def _on_params_reject(self):
        messagebox.showinfo(self.tr.t("params_title"), self.tr.t("params_rejected"))
        self.phase = "params_host"
        self.build_params_host_page()

    def _enter_deploy(self):
        self.phase = "deploy"
        if self.board is None:
            self.board = gc.Board(self.w, self.h, self.n)
        self.cursor = (1, 1)
        self.orientation = 0
        self.build_deploy_page()

    # ------------------------------------------------------------------
    # 部署
    # ------------------------------------------------------------------
    def _choose_cell(self):
        c = 30
        while c > 12 and (self.w * c > 560 or self.h * c > 470):
            c -= 1
        return max(12, c)

    def build_deploy_page(self):
        self._clear_page()
        self.phase = "deploy"
        cell = self._choose_cell()

        header = tk.Frame(self.page, bg=BG)
        header.pack(fill="x", padx=10, pady=(10, 4))
        tk.Label(header, text=self.tr.t("deploy_title"), bg=BG, font=("", 14, "bold"),
                 fg="#1f3a52").pack(side="left")
        self.count_label = tk.Label(header, text="", bg=BG, font=("", 12, "bold"),
                                    fg="#2e7d32")
        self.count_label.pack(side="right")

        body = tk.Frame(self.page, bg=BG)
        body.pack(fill="both", expand=True, padx=10, pady=6)

        # 左侧：棋盘
        left = tk.Frame(body, bg=PANEL, bd=1, relief="solid")
        left.pack(side="left", fill="both", expand=True, padx=(0, 10))
        self.board_my = BoardCanvas(left, self.w, self.h, cell,
                                    on_click=self._on_deploy_click,
                                    on_hover=self._on_deploy_hover)
        self.board_my.pack(padx=6, pady=6)

        # 右侧：控制面板
        right = tk.Frame(body, bg=PANEL, bd=1, relief="solid", width=320)
        right.pack(side="right", fill="y", padx=(0, 0))
        right.pack_propagate(False)

        tk.Label(right, text=self.tr.t("orientation_label"), bg=PANEL,
                 font=("", 11, "bold")).pack(pady=(12, 2))
        self.orientation_var = tk.StringVar(value=str(self.orientation))
        ori_frame = tk.Frame(right, bg=PANEL)
        ori_frame.pack()
        ori_texts = {0: "ori_up", 90: "ori_right", 180: "ori_down", 270: "ori_left"}
        for ori in gc.ORIENTATIONS:
            rb = ttk.Radiobutton(ori_frame, text=self.tr.t(ori_texts[ori]),
                                 variable=self.orientation_var, value=str(ori),
                                 command=self._on_orientation_change)
            rb.grid(row=0, column=gc.ORIENTATIONS.index(ori), padx=2)

        tk.Label(right, text=self.tr.t("shape_preview"), bg=PANEL, fg="#54718a",
                 font=("", 9)).pack(pady=(12, 2))
        self.shape_canvas = tk.Canvas(right, bg="#ffffff", highlightthickness=1,
                                      highlightbackground="#ccdbe8", width=110, height=88)
        self.shape_canvas.pack()
        draw_plane_shape(self.shape_canvas, self.orientation)

        # 图例
        leg = tk.Frame(right, bg=PANEL)
        leg.pack(pady=(12, 4), fill="x", padx=10)
        self._legend_swatch(leg, C_MY_HEAD, self.tr.t("legend_my_head")).grid(row=0, column=0, sticky="w", padx=6)
        self._legend_swatch(leg, C_MY_PLANE, self.tr.t("legend_my_part")).grid(row=0, column=1, sticky="w", padx=6)

        self.deploy_msg_label = tk.Label(right, text="", bg=PANEL, fg="#c62828",
                                         wraplength=280, justify="left", font=("", 9))
        self.deploy_msg_label.pack(pady=4)

        btns = tk.Frame(right, bg=PANEL)
        btns.pack(pady=(6, 8))
        self._button(btns, self.tr.t("btn_random"), self._on_random, accent="#455a64").pack(side="left", padx=4)
        self._button(btns, self.tr.t("btn_clear"), self._on_clear, accent="#455a64").pack(side="left", padx=4)

        self._button(right, self.tr.t("btn_done"), self._on_done_deploy, accent="#2e7d32").pack(pady=(0, 4))
        self._button(right, self.tr.t("btn_back_menu"), self._quit_to_menu, accent="#455a64").pack(pady=(0, 6))

        hint = tk.Label(right, text=self.tr.t("deploy_hint"), bg="#f4f8fb", fg="#54718a",
                        wraplength=280, justify="left", font=("", 9))
        hint.pack(fill="both", expand=True, padx=8, pady=6)

        self._render_my_board_full()
        self._update_deploy_count()
        self.board_my.set_cursor(*self.cursor)
        self._apply_deploy_ready_state()

    def _apply_deploy_ready_state(self):
        """已发送 ready 后禁用交互并显示等待。"""
        if self.i_ready:
            if self.deploy_msg_label:
                self.deploy_msg_label.configure(text=self.tr.t("waiting_opponent_deploy"),
                                                fg="#2e7d32")

    def _legend_swatch(self, parent, color, text):
        f = tk.Frame(parent, bg=PANEL)
        tk.Label(f, bg=color, width=3, height=1, relief="solid", bd=1).pack(side="left")
        tk.Label(f, text=text, bg=PANEL, font=("", 9)).pack(side="left", padx=3)
        return f

    def _on_orientation_change(self):
        if self.orientation_var is None:
            return
        try:
            self.orientation = int(self.orientation_var.get())
        except (ValueError, tk.TclError):
            return
        if self.shape_canvas is not None:
            draw_plane_shape(self.shape_canvas, self.orientation)
        if self._deploy_hover is not None:
            self._on_deploy_hover(self._deploy_hover)

    def _on_deploy_hover(self, cell):
        self._deploy_hover = cell
        if self.board_my is None or self.board is None:
            return
        if self.phase != "deploy" or self.i_ready:
            self.board_my.clear_preview()
            return
        if cell is None:
            self.board_my.clear_preview()
            return
        coords = gc.plane_absolute(cell, self.orientation)
        valid = all(1 <= x <= self.w and 1 <= y <= self.h for (x, y) in coords) and \
                all(self.board.plane_at(x, y) is None for (x, y) in coords)
        self.board_my.set_preview(coords, valid)

    def _on_deploy_click(self, x, y):
        if self.phase != "deploy" or self.i_ready:
            return
        if self.board is None or self.board_my is None:
            return
        if self.board.plane_at(x, y) is not None:
            self.board.remove_plane_at(x, y)
            if self.deploy_msg_label is not None:
                self.deploy_msg_label.configure(text="", fg="#c62828")
        else:
            p = self.board.place((x, y), self.orientation)
            if p is None:
                if self.deploy_msg_label is not None:
                    self.deploy_msg_label.configure(text=self.tr.t("err_cant_place"), fg="#c62828")
                return
            if self.deploy_msg_label is not None:
                self.deploy_msg_label.configure(text="", fg="#c62828")
        self.cursor = (x, y)
        self.board_my.clear_preview()
        self._render_my_board_full()
        self._update_deploy_count()
        self.board_my.set_cursor(x, y)

    def _on_random(self):
        if self.i_ready:
            return
        if not gc.random_place(self.board):
            messagebox.showinfo(self.tr.t("deploy_title"), self.tr.t("random_failed"))
        self._render_my_board_full()
        self._update_deploy_count()

    def _on_clear(self):
        if self.i_ready:
            return
        self.board.clear()
        self._render_my_board_full()
        self._update_deploy_count()

    def _update_deploy_count(self):
        if self.count_label:
            self.count_label.configure(text=self.tr.t("deploy_count",
                                                      placed=self.board.count(), total=self.n))

    def _on_done_deploy(self):
        if self.peer is None or self.i_ready:
            return
        if not self.board.all_placed():
            messagebox.showwarning(self.tr.t("deploy_title"),
                                   self.tr.t("err_need_all", total=self.n))
            return
        self.i_ready = True
        self.peer.send({"type": "ready"})
        if self.opp_ready and self.my_index == 0 and not self.started:
            self._start_game()
            return
        self.build_deploy_page()

    def _on_opp_ready(self):
        self.opp_ready = True
        if self.i_ready and self.my_index == 0 and not self.started:
            self._start_game()

    def _start_game(self):
        first = random.randint(0, 1)
        self.started = True
        self.my_turn = (first == self.my_index)
        if self.my_index == 0:
            self.peer.send({"type": "start", "first": first})
        self.phase = "battle"
        self.build_battle_page()

    def _on_start(self, msg):
        first = msg.get("first", 0)
        self.started = True
        self.my_turn = (first == self.my_index)
        self.phase = "battle"
        self.build_battle_page()

    # ------------------------------------------------------------------
    # 战斗
    # ------------------------------------------------------------------
    def build_battle_page(self):
        self._clear_page()
        self.phase = "battle"
        cell = self._choose_cell()

        header = tk.Frame(self.page, bg=BG)
        header.pack(fill="x", padx=10, pady=(10, 2))
        tk.Label(header, text=self.tr.t("battle_title"), bg=BG, font=("", 14, "bold"),
                 fg="#1f3a52").pack(side="left")
        self.status_label = tk.Label(header, text="", bg=BG, font=("", 12, "bold"), fg="#1565c0")
        self.status_label.pack(side="right")

        body = tk.Frame(self.page, bg=BG)
        body.pack(fill="both", expand=True, padx=10, pady=6)

        # 我方棋盘
        myf = tk.Frame(body, bg=PANEL, bd=1, relief="solid")
        myf.pack(side="left", fill="both", expand=True, padx=(0, 6))
        tk.Label(myf, text=self.tr.t("my_board"), bg=PANEL, font=("", 10, "bold")).pack(pady=(4, 0))
        self.board_my = BoardCanvas(myf, self.w, self.h, cell)
        self.board_my.pack(padx=6, pady=6)

        # 敌方棋盘
        ef = tk.Frame(body, bg=PANEL, bd=1, relief="solid")
        ef.pack(side="left", fill="both", expand=True, padx=(6, 6))
        tk.Label(ef, text=self.tr.t("enemy_board"), bg=PANEL, font=("", 10, "bold")).pack(pady=(4, 0))
        self.board_enemy = BoardCanvas(ef, self.w, self.h, cell, on_click=self._on_enemy_click)
        self.board_enemy.pack(padx=6, pady=6)

        # 右侧面板
        right = tk.Frame(body, bg=PANEL, bd=1, relief="solid", width=290)
        right.pack(side="right", fill="y")
        right.pack_propagate(False)

        tk.Label(right, text=self.tr.t("legend_title"), bg=PANEL, font=("", 11, "bold")).pack(pady=(10, 4))
        # 敌方棋盘图例
        tk.Label(right, text=self.tr.t("enemy_board"), bg=PANEL, fg="#54718a",
                 font=("", 9)).pack(anchor="w", padx=10)
        leg = tk.Frame(right, bg=PANEL)
        leg.pack(fill="x", padx=8)
        for color, key in [(C_SEA, "lg_unknown"), (C_EMPTY, "lg_empty"),
                           (C_DAMAGED, "lg_damaged"), (C_DESTROYED, "lg_destroyed"),
                           (C_WRECKAGE, "lg_wreckage")]:
            self._legend_swatch(leg, color, self.tr.t(key)).pack(anchor="w", padx=4, pady=1)
        # 我方棋盘图例
        tk.Label(right, text=self.tr.t("my_board"), bg=PANEL, fg="#54718a",
                 font=("", 9)).pack(anchor="w", padx=10, pady=(8, 0))
        leg2 = tk.Frame(right, bg=PANEL)
        leg2.pack(fill="x", padx=8)
        self._legend_swatch(leg2, C_MY_PLANE, self.tr.t("lg_my_plane")).pack(anchor="w", padx=4, pady=1)
        self._legend_swatch(leg2, C_MY_HEAD, self.tr.t("legend_my_head")).pack(anchor="w", padx=4, pady=1)
        tk.Label(leg2, text="✕  " + self.tr.t("lg_enemy_hit"), bg=PANEL, fg="#b71c1c",
                 font=("", 9)).pack(anchor="w", padx=4, pady=1)
        tk.Label(leg2, text="·  " + self.tr.t("lg_enemy_miss"), bg=PANEL, fg="#5f7d95",
                 font=("", 9)).pack(anchor="w", padx=4, pady=1)

        tk.Label(right, text=self.tr.t("shot_log"), bg=PANEL, font=("", 10, "bold")).pack(pady=(10, 2))
        log_frame = tk.Frame(right, bg=PANEL)
        log_frame.pack(fill="both", expand=True, padx=8, pady=(0, 6))
        self.log_text = tk.Text(log_frame, height=12, width=34, state="disabled", font=("", 9),
                                bg="#fbfdfe", relief="solid", bd=1, wrap="word")
        sb = ttk.Scrollbar(log_frame, orient="vertical", command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=sb.set)
        self.log_text.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")

        self._button(right, self.tr.t("btn_quit_battle"), self._quit_battle, accent="#b03a3a").pack(pady=(0, 8))

        self._render_my_board_full()
        self._render_enemy_board_full()
        self.board_enemy.set_cursor(*self.cursor)
        self._update_turn_status()
        self._append_log(self.tr.t("battle_title") + " —— " +
                         (self.tr.t("player_role_host") if self.my_index == 0 else self.tr.t("player_role_client")))

    def _render_my_board_full(self):
        if self.board_my is None or self.board is None:
            return
        bc = self.board_my
        bc.clear_all_marks()
        for x in range(1, self.w + 1):
            for y in range(1, self.h + 1):
                bc.set_fill(x, y, C_SEA)
        for p in self.board.planes:
            for (x, y) in p.coords:
                if p.alive:
                    bc.set_fill(x, y, C_MY_HEAD if (x, y) == p.head_coord else C_MY_PLANE)
                else:
                    bc.set_fill(x, y, C_WRECKED_HEAD if (x, y) == p.head_coord else C_WRECKED_MINE)
        for (x, y), term in self.enemy_shots_on_me.items():
            self._apply_my_overlay(x, y, term)

    def _apply_my_overlay(self, x, y, term):
        bc = self.board_my
        if term in ("DAMAGED",):
            bc.set_mark(x, y, "✕", "#7a0000")
        elif term == "DESTROYED":
            bc.set_mark(x, y, "✕", "#ffffff")
        elif term == "EMPTY":
            bc.set_mark(x, y, "·", "#5f7d95")
        elif term == "WRECKAGE":
            bc.set_mark(x, y, "✕", "#3e2723")

    def _render_enemy_board_full(self):
        if self.board_enemy is None:
            return
        bc = self.board_enemy
        bc.clear_all_marks()
        for x in range(1, self.w + 1):
            for y in range(1, self.h + 1):
                bc.set_fill(x, y, C_SEA)
        for (x, y), term in self.my_shots.items():
            self._apply_enemy_shot(x, y, term)

    def _apply_enemy_shot(self, x, y, term):
        bc = self.board_enemy
        if term == "EMPTY":
            bc.set_fill(x, y, C_EMPTY)
            bc.set_mark(x, y, "·", "#90a4ae")
        elif term == "DAMAGED":
            bc.set_fill(x, y, C_DAMAGED)
            bc.set_mark(x, y, "✕", "#7a3d00")
        elif term == "DESTROYED":
            bc.set_fill(x, y, C_DESTROYED)
            bc.set_mark(x, y, "✕", "#ffffff")
        elif term == "WRECKAGE":
            bc.set_fill(x, y, C_WRECKAGE)
            bc.set_mark(x, y, "▦", "#ffffff")

    def _on_enemy_click(self, x, y):
        if self.peer is None or self.phase != "battle" or not self.my_turn or self.awaiting_result:
            return
        if (x, y) in self.my_shots:
            return
        self.cursor = (x, y)
        self.board_enemy.set_cursor(x, y)
        self.awaiting_result = True
        self.peer.send({"type": "shot", "x": x, "y": y})
        sound.shot()
        self._update_turn_status()

    def _update_turn_status(self):
        if self.status_label is None:
            return
        if self.phase != "battle":
            return
        if self.awaiting_result:
            self.status_label.configure(text=self.tr.t("waiting_result"), fg="#ef6c00")
        elif self.my_turn:
            self.status_label.configure(text=self.tr.t("your_turn"), fg="#2e7d32")
        else:
            self.status_label.configure(text=self.tr.t("enemy_turn"), fg="#1565c0")

    def _append_log(self, text):
        if self.log_text is None:
            return
        self.log_text.configure(state="normal")
        self.log_text.insert("end", text + "\n")
        self.log_text.see("end")
        self.log_text.configure(state="disabled")

    def _log(self, who, x, y, term):
        self._append_log("%s → (%d,%d)：%s" % (who, x, y, self.tr.t("term_" + term)))

    # ------------------------------------------------------------------
    # 消息处理
    # ------------------------------------------------------------------
    def _handle_message(self, msg):
        t = msg.get("type")
        if t == "__disconnect__":
            return
        if t == "params":
            self._on_params_received(msg)
        elif t == "params_accept":
            self._on_params_accept()
        elif t == "params_reject":
            self._on_params_reject()
        elif t == "ready":
            self._on_opp_ready()
        elif t == "start":
            self._on_start(msg)
        elif t == "shot":
            self._on_shot(msg)
        elif t == "result":
            self._on_result(msg)
        elif t == "rematch":
            self._on_rematch()
        elif t == "reveal":
            self.revealed_enemy_planes = [(tuple(p["head"]), p["ori"], p["alive"])
                                          for p in msg.get("planes", [])]
            if self.phase == "over":
                self._render_over_boards()
        elif t == "hello":
            if self.waiting_relay:
                self.waiting_relay = False
                self.phase = "params_host"
                self.build_params_host_page()

    def _on_shot(self, msg):
        if self.phase != "battle":
            return
        x, y = msg["x"], msg["y"]
        term = self.board.apply_shot(x, y, self.enemy_shot_history)
        if term != "INVALID":
            self.enemy_shots_on_me[(x, y)] = term
        gameover = (term != "INVALID") and self.board.all_destroyed()
        self.peer.send({"type": "result", "x": x, "y": y, "term": term, "gameover": gameover})
        self._apply_my_overlay(x, y, term)
        self._log(self.tr.t("opponent"), x, y, term)
        if not self.versus_ai:
            if term == "DESTROYED":
                sound.destroy()
            elif term == "DAMAGED":
                sound.hit()
            elif term in ("EMPTY", "WRECKAGE"):
                sound.miss()
        if gameover:
            self._end_game(winner=self.my_index ^ 1)
        else:
            if term != "INVALID":
                self.my_turn = True
            self._update_turn_status()

    def _on_result(self, msg):
        if self.phase != "battle":
            return
        x, y, term = msg["x"], msg["y"], msg["term"]
        gameover = bool(msg.get("gameover", False))
        self.awaiting_result = False
        if term != "INVALID":
            self.my_shots[(x, y)] = term
            self.my_shot_history.add((x, y))
        self._apply_enemy_shot(x, y, term)
        self._log(self.tr.t("me"), x, y, term)
        if term == "DESTROYED":
            sound.destroy()
        elif term == "DAMAGED":
            sound.hit()
        elif term in ("EMPTY", "WRECKAGE"):
            sound.miss()
        if gameover:
            self._end_game(winner=self.my_index)
        else:
            if term == "INVALID":
                self.my_turn = True
            else:
                self.my_turn = False
            self._update_turn_status()

    # ------------------------------------------------------------------
    # 结束 / 重开
    # ------------------------------------------------------------------
    def _end_game(self, winner):
        self.phase = "over"
        self.game_over_winner = winner
        self.my_turn = False
        self.awaiting_result = False
        self._send_reveal()
        if winner == self.my_index:
            sound.win()
        else:
            sound.lose()
        self.build_over_page()

    def _send_reveal(self):
        if self.peer is None or self.board is None:
            return
        planes = [{"head": list(p.head), "ori": p.orientation, "alive": p.alive}
                  for p in self.board.planes]
        self.peer.send({"type": "reveal", "planes": planes})

    def build_over_page(self):
        self._clear_page()
        self.phase = "over"
        cell = self._choose_cell()
        header = tk.Frame(self.page, bg=BG)
        header.pack(fill="x", padx=10, pady=(10, 4))
        tk.Label(header, text=self.tr.t("game_over"), bg=BG, font=("", 18, "bold"),
                 fg="#1f3a52").pack(side="left")
        if self.game_over_winner == self.my_index:
            text = self.tr.t("you_win")
            color = "#2e7d32"
        else:
            text = self.tr.t("you_lose")
            color = "#c62828"
        tk.Label(header, text=text, bg=BG, font=("", 16, "bold"), fg=color).pack(side="left", padx=18)
        self.over_hint_label = tk.Label(header, text="", bg=BG, fg="#c62828", font=("", 11))
        self.over_hint_label.pack(side="right")

        body = tk.Frame(self.page, bg=BG)
        body.pack(fill="both", expand=True, padx=10, pady=6)
        mf = tk.Frame(body, bg=PANEL, bd=1, relief="solid")
        mf.pack(side="left", fill="both", expand=True, padx=(0, 6))
        tk.Label(mf, text=self.tr.t("my_planes_label"), bg=PANEL, font=("", 10, "bold")).pack(pady=(4, 0))
        self.board_my = BoardCanvas(mf, self.w, self.h, cell)
        self.board_my.pack(padx=6, pady=6)
        ef = tk.Frame(body, bg=PANEL, bd=1, relief="solid")
        ef.pack(side="left", fill="both", expand=True, padx=(6, 0))
        tk.Label(ef, text=self.tr.t("enemy_planes_label"), bg=PANEL, font=("", 10, "bold")).pack(pady=(4, 0))
        self.board_enemy = BoardCanvas(ef, self.w, self.h, cell)
        self.board_enemy.pack(padx=6, pady=6)

        btns = tk.Frame(self.page, bg=BG)
        btns.pack(pady=(4, 10))
        self._button(btns, self.tr.t("btn_rematch"), self._request_rematch, accent="#2e7d32").pack(side="left", padx=6)
        self._button(btns, self.tr.t("btn_back_menu"), self._quit_to_menu, accent="#455a64").pack(side="left", padx=6)

        self._render_over_boards()
        self._update_over_hint()

    def _render_over_boards(self):
        if self.board_my is None or self.board_enemy is None:
            return
        self.board_my.clear_all_marks()
        self.board_enemy.clear_all_marks()
        for x in range(1, self.w + 1):
            for y in range(1, self.h + 1):
                self.board_my.set_fill(x, y, C_SEA)
                self.board_enemy.set_fill(x, y, C_SEA)
        if self.board is not None:
            for p in self.board.planes:
                for (x, y) in p.coords:
                    self.board_my.set_fill(x, y, C_MY_HEAD if (x, y) == p.head_coord else C_MY_PLANE)
        for (x, y), term in self.enemy_shots_on_me.items():
            self._apply_my_overlay(x, y, term)
        for (head, ori, alive) in self.revealed_enemy_planes:
            for (x, y) in gc.plane_absolute(head, ori):
                if alive:
                    self.board_enemy.set_fill(x, y, C_MY_HEAD if (x, y) == tuple(head) else C_MY_PLANE)
                else:
                    self.board_enemy.set_fill(x, y, C_WRECKED_HEAD if (x, y) == tuple(head) else C_WRECKED_MINE)
        for (x, y), term in self.my_shots.items():
            self._apply_enemy_shot(x, y, term)

    def _update_over_hint(self):
        if self.over_hint_label is None:
            return
        if self.opp_disconnected:
            self.over_hint_label.configure(text=self.tr.t("opp_left"))
        elif self.want_rematch:
            self.over_hint_label.configure(text=self.tr.t("rematch_waiting"))
        elif self.opp_want_rematch:
            self.over_hint_label.configure(text=self.tr.t("rematch_asked"))
        else:
            self.over_hint_label.configure(text="")

    def _request_rematch(self):
        if self.peer is None or self.opp_disconnected:
            self.opp_disconnected = True
            self._update_over_hint()
            return
        if self.want_rematch:
            return
        self.want_rematch = True
        self.peer.send({"type": "rematch"})
        if self.opp_want_rematch:
            self._start_rematch()
        else:
            self._update_over_hint()

    def _on_rematch(self):
        self.opp_want_rematch = True
        if self.want_rematch:
            self._start_rematch()
        else:
            self._update_over_hint()

    def _start_rematch(self):
        self._reset_round()
        self.phase = "deploy"
        self.build_deploy_page()

    def _reset_round(self):
        self.board = gc.Board(self.w, self.h, self.n)
        self._clear_round_state()
        self.i_ready = False
        self.opp_ready = False
        self.started = False

    def _clear_round_state(self):
        """清空一局对局中产生的所有状态（攻击历史、棋盘结果等）。"""
        self.my_shots.clear()
        self.my_shot_history.clear()
        self.enemy_shots_on_me.clear()
        self.enemy_shot_history.clear()
        self.revealed_enemy_planes = []
        self.my_turn = False
        self.awaiting_result = False
        self.game_over_winner = None
        self.want_rematch = False
        self.opp_want_rematch = False
        self.opp_disconnected = False
        self.cursor = (1, 1)
        self.orientation = 0

    # ------------------------------------------------------------------
    # 键盘
    # ------------------------------------------------------------------
    def _on_key(self, event):
        key = event.keysym
        if self.phase == "deploy":
            self._key_deploy(key)
        elif self.phase == "battle":
            self._key_battle(key)

    def _move_cursor(self, dx, dy):
        x, y = self.cursor
        x = max(1, min(self.w, x + dx))
        y = max(1, min(self.h, y + dy))
        self.cursor = (x, y)
        return x, y

    def _key_deploy(self, key):
        if self.i_ready:
            return
        if key in ("Left", "Right", "Up", "Down"):
            dx = dy = 0
            if key == "Left":
                dx = -1
            elif key == "Right":
                dx = 1
            elif key == "Up":
                dy = -1
            elif key == "Down":
                dy = 1
            x, y = self._move_cursor(dx, dy)
            if self.board_my is not None:
                self.board_my.set_cursor(x, y)
            self._on_deploy_hover((x, y))
        elif key in ("r", "R"):
            self.orientation = (self.orientation + 90) % 360
            if self.orientation_var is not None:
                self.orientation_var.set(str(self.orientation))
            if self.shape_canvas is not None:
                draw_plane_shape(self.shape_canvas, self.orientation)
            self._on_deploy_hover(self.cursor)
        elif key in ("space", "Return"):
            x, y = self.cursor
            if self.board.plane_at(x, y) is None:
                self._on_deploy_click(x, y)
        elif key in ("Delete", "BackSpace"):
            x, y = self.cursor
            if self.board.plane_at(x, y) is not None:
                self._on_deploy_click(x, y)

    def _key_battle(self, key):
        if key in ("Left", "Right", "Up", "Down"):
            dx = dy = 0
            if key == "Left":
                dx = -1
            elif key == "Right":
                dx = 1
            elif key == "Up":
                dy = -1
            elif key == "Down":
                dy = 1
            x, y = self._move_cursor(dx, dy)
            if self.board_enemy:
                self.board_enemy.set_cursor(x, y)
        elif key in ("space", "Return"):
            if self.board_enemy:
                self._on_enemy_click(*self.cursor)

    # ------------------------------------------------------------------
    # 退出 / 清理
    # ------------------------------------------------------------------
    def _quit_battle(self):
        if messagebox.askokcancel(self.tr.t("btn_quit_battle"), self.tr.t("btn_quit_battle") + "?"):
            self._cleanup_connection()
            self.build_menu()

    def _quit_to_menu(self):
        self._cleanup_connection()
        self.build_menu()

    def _cancel_host(self):
        self._cleanup_connection()
        self.build_menu()

    def _cleanup_connection(self):
        self.user_closing = True
        if self.peer is not None:
            try:
                self.peer.send({"type": "bye"})
            except Exception:
                pass
            self.peer.close()
            self.peer = None
        if self.host_socket is not None:
            try:
                self.host_socket.close()
            except OSError:
                pass
            self.host_socket = None
        self._reset_for_menu()
        self.user_closing = False

    def _reset_for_menu(self):
        self.my_index = None
        self.board = None
        self.phase = "menu"
        self._clear_round_state()
        self.i_ready = False
        self.opp_ready = False
        self.started = False

    def _on_disconnect(self):
        if self.user_closing:
            return
        if self.phase == "menu":
            return
        if self.phase == "over":
            self.opp_disconnected = True
            if self.peer is not None:
                self.peer.close()
                self.peer = None
            self._update_over_hint()
            return
        self._cleanup_connection()
        messagebox.showwarning(self.tr.t("app_title"), self.tr.t("connection_lost"))
        self.build_menu()

    def _on_close(self):
        self.user_closing = True
        self._cleanup_connection()
        self.root.destroy()

    # ------------------------------------------------------------------
    # 轮询
    # ------------------------------------------------------------------
    def _poll(self):
        try:
            if self.peer is not None:
                while True:
                    msg = self.peer.recv()
                    if msg is None:
                        break
                    self._handle_message(msg)
                if self.peer.is_closed():
                    self._on_disconnect()
        finally:
            self.root.after(50, self._poll)

    # ------------------------------------------------------------------
    # 小工具
    # ------------------------------------------------------------------
    def _centered_box(self):
        box = tk.Frame(self.page, bg=PANEL, bd=1, relief="solid", padx=26, pady=22)
        box.place(relx=0.5, rely=0.5, anchor="center")
        return box

    def _button(self, parent, text, cmd, accent="#2e7d32"):
        return tk.Button(parent, text=text, command=cmd, font=("", 11),
                         bd=0, cursor="hand2", padx=14, pady=6,
                         bg=accent, fg="#ffffff", activebackground="#1b5e20",
                         activeforeground="#ffffff")


def run():
    root = tk.Tk()
    GameApp(root)
    root.mainloop()
