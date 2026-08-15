# -*- coding: utf-8 -*-
"""
mobile_app.py —— “飞机大战” Android/移动端（Kivy，触摸适配）。

与桌面版共用 game_core / network / ai / i18n / sound。
界面为触摸设计：点按棋盘放置/攻击，按钮较大，适配手机竖屏。
"""

import os
import threading

from kivy.app import App
from kivy.clock import Clock
from kivy.graphics import Color, Line, Rectangle
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.scrollview import ScrollView
from kivy.uix.screenmanager import Screen, ScreenManager
from kivy.uix.textinput import TextInput
from kivy.uix.widget import Widget

# 注册 CJK 字体（解决中文/日文显示为 ☒ 的问题）
from kivy.core.text import LabelBase
_FONT_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fonts", "NotoSansSC.ttf")
if os.path.exists(_FONT_PATH):
    LabelBase.register(name="Roboto", fn_regular=_FONT_PATH)

import game_core as gc
import network as net
import sound
from ai import AIOpponent
from i18n import Translator, LANGUAGES, LANGUAGE_NAMES

RELAY_DEFAULT = "127.0.0.1:4000"


# ---------------------------------------------------------------------------
# 颜色（RGB 0-1，高对比度）
# ---------------------------------------------------------------------------
def _rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4)) + (1.0,)


C_SEA = _rgb("#8ecae6")
C_GRID = _rgb("#4f86b0")
C_EMPTY = _rgb("#eef3f7")
C_DAMAGED = _rgb("#ffa726")
C_DESTROYED = _rgb("#e53935")
C_WRECKAGE = _rgb("#8d6e63")
C_MY_PLANE = _rgb("#4caf50")
C_MY_HEAD = _rgb("#e53935")
C_WRECKED_MINE = _rgb("#9e9e9e")
C_WRECKED_HEAD = _rgb("#7f1d1d")

BG = _rgb("#eef2f7")
PANEL = _rgb("#ffffff")
NAVY = _rgb("#1f3a52")
INK = _rgb("#1a2b3c")        # 深色正文，高对比
GRAY = _rgb("#455a64")       # 次级文字（加深，提高对比）
ACCENT = _rgb("#1565c0")
GREEN = _rgb("#2e7d32")
RED = _rgb("#c62828")
ORANGE = _rgb("#ef6c00")


class Swatch(Widget):
    """一个纯色小方块，用于图例。"""

    def __init__(self, color, **kw):
        super().__init__(**kw)
        self._color = color
        with self.canvas:
            Color(*color)
            self._rect = Rectangle(pos=self.pos, size=self.size)
        self.bind(pos=self._upd, size=self._upd)

    def _upd(self, *a):
        self._rect.pos = self.pos
        self._rect.size = self.size


def legend_row(color, text):
    row = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp(26), spacing=dp(8))
    sw = Swatch(color, size_hint=(None, None), size=(dp(18), dp(18)), pos_hint={"center_y": 0.5})
    row.add_widget(sw)
    row.add_widget(Label(text=text, font_size=dp(13), color=INK, halign="left", valign="middle"))
    return row


class BoardWidget(Widget):
    """可点按的网格棋盘（保持正方形格子，不拉伸）。y=1 为最上一行。"""

    def __init__(self, w, h, on_tap=None, **kw):
        super().__init__(**kw)
        self.cols = w
        self.rows = h
        self.on_tap = on_tap
        self.cell_colors = [[C_SEA for _ in range(w)] for _ in range(h)]
        self.bind(pos=self.refresh, size=self.refresh)

    def set_cell(self, x, y, color):
        self.cell_colors[y - 1][x - 1] = color

    def set_all(self, color):
        for y in range(self.rows):
            for x in range(self.cols):
                self.cell_colors[y][x] = color

    def _grid_geometry(self):
        """返回 (cell, ox, oy)：正方形格子边长与居中偏移。"""
        if self.width <= 0 or self.height <= 0:
            return 0.0, 0.0, 0.0
        cell = min(self.width / self.cols, self.height / self.rows)
        ox = (self.width - cell * self.cols) / 2.0
        oy = (self.height - cell * self.rows) / 2.0
        return cell, ox, oy

    def refresh(self, *args):
        self.canvas.clear()
        cell, ox, oy = self._grid_geometry()
        if cell <= 0:
            return
        with self.canvas:
            for gy in range(self.rows):
                for gx in range(self.cols):
                    Color(*self.cell_colors[gy][gx])
                    Rectangle(pos=(self.x + ox + gx * cell,
                                   self.y + oy + (self.rows - 1 - gy) * cell),
                              size=(cell, cell))
            Color(*C_GRID)
            for i in range(self.cols + 1):
                Line(points=[self.x + ox + i * cell, self.y + oy,
                             self.x + ox + i * cell, self.y + oy + self.rows * cell], width=1)
            for j in range(self.rows + 1):
                Line(points=[self.x + ox, self.y + oy + j * cell,
                             self.x + ox + self.cols * cell, self.y + oy + j * cell], width=1)

    def on_touch_down(self, touch):
        if self.collide_point(*touch.pos):
            cell = self._pos_to_cell(touch.pos)
            if cell is not None and self.on_tap is not None:
                self.on_tap(*cell)
            return True
        return False

    def _pos_to_cell(self, pos):
        cell, ox, oy = self._grid_geometry()
        if cell <= 0:
            return None
        gx = int((pos[0] - self.x - ox) / cell)
        gy_bottom = int((pos[1] - self.y - oy) / cell)
        if 0 <= gx < self.cols and 0 <= gy_bottom < self.rows:
            return gx + 1, self.rows - gy_bottom
        return None


class ShapePreview(Widget):
    """显示当前朝向的“士”字形飞机（正方形格子）。"""

    def __init__(self, orientation=0, **kw):
        super().__init__(**kw)
        self.orientation = orientation
        self.bind(pos=self.refresh, size=self.refresh)

    def set_orientation(self, ori):
        self.orientation = ori
        self.refresh()

    def refresh(self, *args):
        self.canvas.clear()
        if self.width <= 0 or self.height <= 0:
            return
        rel = gc.plane_relative(self.orientation)
        minx = min(p[0] for p in rel)
        maxx = max(p[0] for p in rel)
        miny = min(p[1] for p in rel)
        maxy = max(p[1] for p in rel)
        cols = maxx - minx + 1
        rows = maxy - miny + 1
        cell = min(self.width / cols, self.height / rows)
        ox = (self.width - cell * cols) / 2.0
        oy = (self.height - cell * rows) / 2.0
        with self.canvas:
            for (dx, dy) in rel:
                Color(*(C_MY_HEAD if (dx, dy) == (0, 0) else C_MY_PLANE))
                gx = dx - minx
                gy = dy - miny
                Rectangle(pos=(self.x + ox + gx * cell,
                               self.y + oy + (rows - 1 - gy) * cell),
                          size=(cell, cell))


def make_btn(text, on_press, accent=GREEN, height=dp(52)):
    b = Button(text=text, background_normal="", background_color=accent,
               color=(1, 1, 1, 1), font_size=dp(17), bold=True)
    b.bind(on_press=lambda *a: on_press())
    b.size_hint_y = None
    b.height = height
    return b


def make_label(text, size=14, color=INK, bold=False):
    return Label(text=text, font_size=dp(size), color=color, bold=bold,
                 halign="left", valign="middle", size_hint_y=None, height=dp(22))


# ---------------------------------------------------------------------------
# 屏幕基类
# ---------------------------------------------------------------------------
class BaseScreen(Screen):
    def __init__(self, app, **kw):
        super().__init__(**kw)
        self.app = app


class MenuScreen(BaseScreen):
    def build(self):
        self.clear_widgets()
        root = BoxLayout(orientation="vertical", padding=dp(20), spacing=dp(12))
        root.add_widget(Label(text=self.app.tr.t("app_title"), font_size=dp(26),
                              bold=True, color=NAVY, size_hint_y=None, height=dp(64)))
        root.add_widget(Label(text=self.app.tr.t("menu_subtitle"), font_size=dp(14),
                              color=GRAY, size_hint_y=None, height=dp(26)))
        root.add_widget(make_btn(self.app.tr.t("btn_host"), self.app.goto_host, GREEN))
        root.add_widget(make_btn(self.app.tr.t("btn_join"), self.app.goto_join, ACCENT))
        root.add_widget(make_btn(self.app.tr.t("btn_ai"), self.app.goto_ai, _rgb("#00695c")))
        root.add_widget(make_btn(self.app.tr.t("btn_help"), self.app.goto_help, _rgb("#6a4fa3")))
        lang_row = BoxLayout(orientation="horizontal", spacing=dp(8), size_hint_y=None, height=dp(50))
        for lang in LANGUAGES:
            mark = "● " if lang == self.app.tr.lang else ""
            lang_row.add_widget(make_btn(mark + LANGUAGE_NAMES[lang],
                                         lambda l=lang: self.app.set_language(l), _rgb("#455a64"), height=dp(46)))
        root.add_widget(lang_row)
        root.add_widget(make_btn(self.app.tr.t("btn_quit"), self.app.do_quit, RED))
        self.add_widget(root)


class HelpScreen(BaseScreen):
    def build(self):
        self.clear_widgets()
        root = BoxLayout(orientation="vertical", padding=dp(14), spacing=dp(8))
        header = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp(48))
        header.add_widget(Label(text=self.app.tr.t("help_title"), bold=True, font_size=dp(19), color=NAVY))
        header.add_widget(make_btn(self.app.tr.t("btn_back"), self.app.goto_menu, _rgb("#455a64"), height=dp(44)))
        root.add_widget(header)
        sv = ScrollView()
        lbl = Label(text=self.app.tr.t("help_body"), font_size=dp(15), color=INK,
                    halign="left", valign="top", size_hint_y=None)
        lbl.bind(width=lambda w, x: setattr(lbl, "text_size", (x - dp(24), None)))
        sv.add_widget(lbl)
        root.add_widget(sv)
        self.add_widget(root)


class HostScreen(BaseScreen):
    def build(self):
        self.clear_widgets()
        root = BoxLayout(orientation="vertical", padding=dp(16), spacing=dp(10))
        root.add_widget(Label(text=self.app.tr.t("host_setup_title"), bold=True,
                              font_size=dp(19), color=NAVY, size_hint_y=None, height=dp(40)))
        mode_row = BoxLayout(orientation="horizontal", spacing=dp(8), size_hint_y=None, height=dp(50))
        self.mode_buttons = {}
        for mode, key in (("direct", "mode_direct"), ("relay", "mode_relay")):
            b = make_btn(self.app.tr.t(key), lambda m=mode: self.app.set_host_mode(m), ACCENT, height=dp(46))
            self.mode_buttons[mode] = b
            mode_row.add_widget(b)
        root.add_widget(mode_row)

        self.direct_box = BoxLayout(orientation="vertical", spacing=dp(6))
        ip = net.get_primary_ip() or self.app.tr.t("host_ip_unknown")
        self.direct_box.add_widget(Label(text=self.app.tr.t("host_your_ip"), font_size=dp(14), color=GRAY,
                                         size_hint_y=None, height=dp(22)))
        self.direct_box.add_widget(Label(text=ip, font_size=dp(20), bold=True, color=ACCENT,
                                         size_hint_y=None, height=dp(30)))
        prow = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp(50), spacing=dp(8))
        prow.add_widget(Label(text=self.app.tr.t("host_port"), size_hint_x=0.35, color=INK))
        self.port_input = TextInput(text=str(self.app.host_port), multiline=False,
                                    input_filter="int", size_hint_x=0.65, font_size=dp(16))
        prow.add_widget(self.port_input)
        self.direct_box.add_widget(prow)
        root.add_widget(self.direct_box)

        self.relay_box = BoxLayout(orientation="vertical", spacing=dp(6))
        rrow = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp(50), spacing=dp(8))
        rrow.add_widget(Label(text=self.app.tr.t("relay_server"), size_hint_x=0.4, color=INK, font_size=dp(14)))
        self.relay_input = TextInput(text=RELAY_DEFAULT, multiline=False, size_hint_x=0.6, font_size=dp(16))
        rrow.add_widget(self.relay_input)
        self.relay_box.add_widget(rrow)
        self.relay_box.add_widget(Label(text=self.app.tr.t("relay_addr_hint"), font_size=dp(12), color=GRAY,
                                        size_hint_y=None, height=dp(20)))
        root.add_widget(self.relay_box)

        self.status = make_label("", size=14, color=RED)
        root.add_widget(self.status)
        root.add_widget(make_btn(self.app.tr.t("btn_start_listen"), self.app.start_hosting, GREEN))
        root.add_widget(make_btn(self.app.tr.t("btn_back"), self.app.cancel_host, _rgb("#455a64")))
        self.add_widget(root)
        self.refresh()

    def refresh(self):
        relay = (self.app.host_mode == "relay")
        for m, b in self.mode_buttons.items():
            b.background_color = ACCENT if (m == "relay") == relay else _rgb("#9aa8b5")
        self.direct_box.opacity = 0 if relay else 1
        self.direct_box.disabled = relay
        self.relay_box.opacity = 1 if relay else 0
        self.relay_box.disabled = not relay


class JoinScreen(BaseScreen):
    def build(self):
        self.clear_widgets()
        root = BoxLayout(orientation="vertical", padding=dp(16), spacing=dp(10))
        root.add_widget(Label(text=self.app.tr.t("join_title"), bold=True,
                              font_size=dp(19), color=NAVY, size_hint_y=None, height=dp(40)))
        mode_row = BoxLayout(orientation="horizontal", spacing=dp(8), size_hint_y=None, height=dp(50))
        self.mode_buttons = {}
        for mode, key in (("direct", "mode_direct"), ("relay", "mode_relay")):
            b = make_btn(self.app.tr.t(key), lambda m=mode: self.app.set_join_mode(m), ACCENT, height=dp(46))
            self.mode_buttons[mode] = b
            mode_row.add_widget(b)
        root.add_widget(mode_row)

        self.direct_box = BoxLayout(orientation="vertical", spacing=dp(6))
        row1 = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp(50), spacing=dp(8))
        row1.add_widget(Label(text=self.app.tr.t("join_ip"), size_hint_x=0.35, color=INK, font_size=dp(14)))
        self.addr_input = TextInput(text="127.0.0.1", multiline=False, size_hint_x=0.65, font_size=dp(16))
        row1.add_widget(self.addr_input)
        self.direct_box.add_widget(row1)
        row2 = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp(50), spacing=dp(8))
        row2.add_widget(Label(text=self.app.tr.t("join_port"), size_hint_x=0.35, color=INK))
        self.port_input = TextInput(text=str(net.DEFAULT_PORT), multiline=False,
                                    input_filter="int", size_hint_x=0.65, font_size=dp(16))
        row2.add_widget(self.port_input)
        self.direct_box.add_widget(row2)
        root.add_widget(self.direct_box)

        self.relay_box = BoxLayout(orientation="vertical", spacing=dp(6))
        rr1 = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp(50), spacing=dp(8))
        rr1.add_widget(Label(text=self.app.tr.t("relay_server"), size_hint_x=0.4, color=INK, font_size=dp(14)))
        self.relay_input = TextInput(text=RELAY_DEFAULT, multiline=False, size_hint_x=0.6, font_size=dp(16))
        rr1.add_widget(self.relay_input)
        self.relay_box.add_widget(rr1)
        rr2 = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp(50), spacing=dp(8))
        rr2.add_widget(Label(text=self.app.tr.t("room_code_label"), size_hint_x=0.4, color=INK))
        self.code_input = TextInput(text="", multiline=False, size_hint_x=0.6, font_size=dp(18))
        rr2.add_widget(self.code_input)
        self.relay_box.add_widget(rr2)
        root.add_widget(self.relay_box)

        self.status = make_label("", size=14, color=RED)
        root.add_widget(self.status)
        root.add_widget(make_btn(self.app.tr.t("btn_join_room"), self.app.start_join, ACCENT))
        root.add_widget(make_btn(self.app.tr.t("btn_back"), self.app.cancel_host, _rgb("#455a64")))
        self.add_widget(root)
        self.refresh()

    def refresh(self):
        relay = (self.app.join_mode == "relay")
        for m, b in self.mode_buttons.items():
            b.background_color = ACCENT if (m == "relay") == relay else _rgb("#9aa8b5")
        self.direct_box.opacity = 0 if relay else 1
        self.direct_box.disabled = relay
        self.relay_box.opacity = 1 if relay else 0
        self.relay_box.disabled = not relay


class ParamsScreen(BaseScreen):
    def build(self):
        self.clear_widgets()
        root = BoxLayout(orientation="vertical", padding=dp(16), spacing=dp(10))
        if self.app.phase == "params_wait":
            root.add_widget(Label(text=self.app.tr.t("params_waiting"), font_size=dp(15), color=INK,
                                  size_hint_y=None, height=dp(40)))
            root.add_widget(make_btn(self.app.tr.t("btn_back"), self.app.cancel_host, _rgb("#455a64")))
            self.add_widget(root)
            return
        root.add_widget(Label(text=self.app.tr.t("params_title"), bold=True,
                              font_size=dp(19), color=NAVY, size_hint_y=None, height=dp(40)))
        is_host = (self.app.my_index == 0)
        self.w_input = TextInput(text=str(self.app.w), multiline=False, input_filter="int", font_size=dp(16))
        self.h_input = TextInput(text=str(self.app.h), multiline=False, input_filter="int", font_size=dp(16))
        self.n_input = TextInput(text=str(self.app.n), multiline=False, input_filter="int", font_size=dp(16))
        for label, inp in ((self.app.tr.t("map_width"), self.w_input),
                           (self.app.tr.t("map_height"), self.h_input),
                           (self.app.tr.t("num_planes"), self.n_input)):
            row = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp(50), spacing=dp(8))
            row.add_widget(Label(text=label, size_hint_x=0.55, color=INK))
            inp.size_hint_x = 0.45
            inp.readonly = not is_host
            row.add_widget(inp)
            root.add_widget(row)
        self.err = make_label("", size=14, color=RED)
        root.add_widget(self.err)
        if is_host:
            root.add_widget(make_btn(self.app.tr.t("btn_confirm_params"), self.app.send_params, GREEN))
        else:
            btn_row = BoxLayout(orientation="horizontal", spacing=dp(8), size_hint_y=None, height=dp(50))
            btn_row.add_widget(make_btn(self.app.tr.t("btn_accept"), self.app.accept_params, GREEN, height=dp(46)))
            btn_row.add_widget(make_btn(self.app.tr.t("btn_reject"), self.app.reject_params, RED, height=dp(46)))
            root.add_widget(btn_row)
        root.add_widget(make_btn(self.app.tr.t("btn_back"), self.app.cancel_host, _rgb("#455a64")))
        self.add_widget(root)


class DeployScreen(BaseScreen):
    def build(self):
        self.clear_widgets()
        root = BoxLayout(orientation="vertical", padding=dp(8), spacing=dp(6))
        header = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp(44))
        header.add_widget(Label(text=self.app.tr.t("deploy_title"), bold=True, font_size=dp(16), color=NAVY))
        self.count_label = Label(text="", font_size=dp(14), color=GREEN)
        header.add_widget(self.count_label)
        root.add_widget(header)

        self.board = BoardWidget(self.app.w, self.app.h, on_tap=self.app.on_deploy_tap)
        root.add_widget(self.board)

        ori_row = BoxLayout(orientation="horizontal", spacing=dp(6), size_hint_y=None, height=dp(48))
        self.ori_buttons = {}
        for ori, key in ((0, "ori_up"), (90, "ori_right"), (180, "ori_down"), (270, "ori_left")):
            b = make_btn(self.app.tr.t(key), lambda o=ori: self.app.set_orientation(o), ACCENT, height=dp(44))
            self.ori_buttons[ori] = b
            ori_row.add_widget(b)
        root.add_widget(ori_row)

        mid = BoxLayout(orientation="horizontal", spacing=dp(8), size_hint_y=None, height=dp(80))
        self.preview = ShapePreview(self.app.orientation, size_hint_x=0.5)
        mid.add_widget(self.preview)
        acts = GridLayout(cols=2, spacing=dp(6), size_hint_x=0.5)
        acts.add_widget(make_btn(self.app.tr.t("btn_random"), self.app.do_random, _rgb("#455a64"), height=dp(36)))
        acts.add_widget(make_btn(self.app.tr.t("btn_clear"), self.app.do_clear, _rgb("#455a64"), height=dp(36)))
        acts.add_widget(make_btn(self.app.tr.t("btn_done"), self.app.do_done, GREEN, height=dp(36)))
        acts.add_widget(make_btn(self.app.tr.t("btn_back_menu"), self.app.quit_to_menu, _rgb("#455a64"), height=dp(36)))
        mid.add_widget(acts)
        root.add_widget(mid)

        self.msg = make_label("", size=13, color=RED)
        root.add_widget(self.msg)
        self.add_widget(root)
        self.refresh()

    def refresh(self):
        if self.app.board is None:
            return
        self.count_label.text = self.app.tr.t("deploy_count", placed=self.app.board.count(), total=self.app.n)
        self.preview.set_orientation(self.app.orientation)
        self.app.render_my_board(self.board)
        self.app.apply_deploy_ready_state()


class BattleScreen(BaseScreen):
    def build(self):
        self.clear_widgets()
        root = BoxLayout(orientation="vertical", padding=dp(8), spacing=dp(6))
        self.status = Label(text="", bold=True, font_size=dp(16), color=ACCENT, size_hint_y=None, height=dp(32))
        root.add_widget(self.status)

        boards = BoxLayout(orientation="horizontal", spacing=dp(8))
        left = BoxLayout(orientation="vertical", size_hint_x=0.44)
        left.add_widget(Label(text=self.app.tr.t("my_board"), font_size=dp(12), color=GRAY,
                              size_hint_y=None, height=dp(20)))
        self.my_board = BoardWidget(self.app.w, self.app.h)
        left.add_widget(self.my_board)
        boards.add_widget(left)
        right = BoxLayout(orientation="vertical", size_hint_x=0.56)
        right.add_widget(Label(text=self.app.tr.t("enemy_board"), font_size=dp(12), color=GRAY,
                               size_hint_y=None, height=dp(20)))
        self.enemy_board = BoardWidget(self.app.w, self.app.h, on_tap=self.app.on_enemy_tap)
        right.add_widget(self.enemy_board)
        boards.add_widget(right)
        root.add_widget(boards)

        leg = BoxLayout(orientation="vertical", size_hint_y=None, height=dp(110), spacing=dp(1))
        leg.add_widget(legend_row(C_SEA, self.app.tr.t("lg_unknown")))
        leg.add_widget(legend_row(C_DAMAGED, self.app.tr.t("lg_damaged") + " / " + self.app.tr.t("lg_destroyed")))
        leg.add_widget(legend_row(C_WRECKAGE, self.app.tr.t("lg_wreckage")))
        leg.add_widget(legend_row(C_MY_PLANE, self.app.tr.t("lg_my_plane") + "（" + self.app.tr.t("legend_my_head") + "）"))
        root.add_widget(leg)

        self.log = Label(text="", font_size=dp(12), color=INK, halign="left", valign="top")
        logsv = ScrollView(size_hint_y=1)
        logsv.add_widget(self.log)
        root.add_widget(logsv)

        root.add_widget(make_btn(self.app.tr.t("btn_quit_battle"), self.app.quit_to_menu, RED, height=dp(46)))
        self.add_widget(root)
        self.refresh()

    def refresh(self):
        self.app.render_my_board(self.my_board)
        self.app.render_enemy_board(self.enemy_board)
        self.app.update_turn_status()
        self.log.text = self.app.log_text


class OverScreen(BaseScreen):
    def build(self):
        self.clear_widgets()
        root = BoxLayout(orientation="vertical", padding=dp(12), spacing=dp(8))
        root.add_widget(Label(text=self.app.tr.t("game_over"), bold=True, font_size=dp(22), color=NAVY,
                              size_hint_y=None, height=dp(46)))
        if self.app.game_over_winner == self.app.my_index:
            text = self.app.tr.t("you_win")
            color = GREEN
        else:
            text = self.app.tr.t("you_lose")
            color = RED
        root.add_widget(Label(text=text, font_size=dp(20), bold=True, color=color, size_hint_y=None, height=dp(42)))

        boards = BoxLayout(orientation="horizontal", spacing=dp(8))
        left = BoxLayout(orientation="vertical", size_hint_x=0.5)
        left.add_widget(Label(text=self.app.tr.t("my_planes_label"), font_size=dp(12), color=GRAY,
                              size_hint_y=None, height=dp(20)))
        self.my_board = BoardWidget(self.app.w, self.app.h)
        left.add_widget(self.my_board)
        boards.add_widget(left)
        right = BoxLayout(orientation="vertical", size_hint_x=0.5)
        right.add_widget(Label(text=self.app.tr.t("enemy_planes_label"), font_size=dp(12), color=GRAY,
                               size_hint_y=None, height=dp(20)))
        self.enemy_board = BoardWidget(self.app.w, self.app.h)
        right.add_widget(self.enemy_board)
        boards.add_widget(right)
        root.add_widget(boards)

        self.hint = Label(text="", font_size=dp(13), color=RED, size_hint_y=None, height=dp(30))
        root.add_widget(self.hint)
        root.add_widget(make_btn(self.app.tr.t("btn_rematch"), self.app.request_rematch, GREEN, height=dp(48)))
        root.add_widget(make_btn(self.app.tr.t("btn_back_menu"), self.app.quit_to_menu, _rgb("#455a64"), height=dp(46)))
        self.add_widget(root)
        self.refresh()

    def refresh(self):
        self.app.render_my_board(self.my_board)
        self.app.render_revealed_enemy_board(self.enemy_board)
        if self.app.opp_disconnected:
            self.hint.text = self.app.tr.t("opp_left")
        elif self.app.want_rematch:
            self.hint.text = self.app.tr.t("rematch_waiting")
        elif self.app.opp_want_rematch:
            self.hint.text = self.app.tr.t("rematch_asked")
        else:
            self.hint.text = ""


# ---------------------------------------------------------------------------
# 应用主体
# ---------------------------------------------------------------------------
class PlaneBattleApp(App):
    def build(self):
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

        self.w = 10
        self.h = 10
        self.n = 3
        self.board = None
        self.orientation = 0
        self.host_port = net.DEFAULT_PORT

        self.my_shots = {}
        self.my_shot_history = set()
        self.enemy_shots_on_me = {}
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
        self.log_text = ""

        self.sm = ScreenManager()
        self.menu_screen = MenuScreen(self, name="menu")
        self.help_screen = HelpScreen(self, name="help")
        self.host_screen = HostScreen(self, name="host")
        self.join_screen = JoinScreen(self, name="join")
        self.params_screen = ParamsScreen(self, name="params")
        self.deploy_screen = DeployScreen(self, name="deploy")
        self.battle_screen = BattleScreen(self, name="battle")
        self.over_screen = OverScreen(self, name="over")
        for s in (self.menu_screen, self.help_screen, self.host_screen, self.join_screen,
                  self.params_screen, self.deploy_screen, self.battle_screen, self.over_screen):
            self.sm.add_widget(s)
        self.menu_screen.build()

        Clock.schedule_interval(self._poll, 0.05)
        return self.sm

    # ---------------- 导航 ----------------
    def goto(self, name, build=True):
        screen = self.sm.get_screen(name)
        if build:
            screen.build()
        self.sm.current = name

    def goto_menu(self):
        self.goto("menu")

    def goto_help(self):
        self.goto("help")

    def goto_host(self):
        self.my_index = 0
        self.phase = "host"
        self.goto("host")

    def goto_join(self):
        self.my_index = 1
        self.phase = "join"
        self.goto("join")

    def goto_ai(self):
        self.my_index = 0
        self.peer = AIOpponent()
        self.phase = "params"
        self.goto("params")

    def set_language(self, lang):
        self.tr.set_lang(lang)
        self.goto(self.sm.current)

    def set_host_mode(self, mode):
        self.host_mode = mode
        self.host_screen.refresh()

    def set_join_mode(self, mode):
        self.join_mode = mode
        self.join_screen.refresh()

    # ---------------- 主机 ----------------
    def start_hosting(self):
        sound.click()
        if self.host_mode == "relay":
            self._start_relay_host()
            return
        try:
            port = int(self.host_screen.port_input.text.strip())
            if not (1 <= port <= 65535):
                raise ValueError
        except ValueError:
            self.host_screen.status.text = self.tr.t("err_port_invalid")
            return
        self.host_port = port
        try:
            self.host_socket = net.create_host_socket(port)
        except OSError as e:
            self.host_screen.status.text = str(e)
            return
        self.host_screen.status.text = self.tr.t("host_waiting")
        threading.Thread(target=self._accept_loop, daemon=True).start()

    def _start_relay_host(self):
        addr = self.host_screen.relay_input.text.strip()
        host, port = self._parse_relay_addr(addr)
        self.host_screen.status.text = self.tr.t("connecting")
        threading.Thread(target=self._relay_host_loop, args=(host, port), daemon=True).start()

    def _relay_host_loop(self, host, port):
        try:
            peer, code = net.relay_host(host, port)
        except OSError:
            Clock.schedule_once(lambda dt: self._relay_host_error(), 0)
            return
        Clock.schedule_once(lambda dt: self._on_relay_host(peer, code), 0)

    def _relay_host_error(self):
        self.host_screen.status.text = self.tr.t("relay_error")

    def _on_relay_host(self, peer, code):
        if self.phase != "host":
            peer.close()
            return
        self.peer = peer
        self.room_code = code
        self.host_screen.status.text = self.tr.t("your_room_code") + "  " + code + "\n" + self.tr.t("waiting_relay_client")
        self.phase = "params"
        Clock.schedule_once(lambda dt: self.goto("params"), 1.2)

    def _accept_loop(self):
        try:
            peer = net.accept_client(self.host_socket)
        except OSError:
            Clock.schedule_once(lambda dt: self._accept_error(), 0)
            return
        Clock.schedule_once(lambda dt: self._on_host_connected(peer), 0)

    def _accept_error(self):
        self.host_screen.status.text = self.tr.t("conn_failed")
        self._cleanup_connection()
        self.goto_menu()

    def _on_host_connected(self, peer):
        if self.phase != "host":
            peer.close()
            return
        self.peer = peer
        try:
            self.host_socket.close()
        except OSError:
            pass
        self.host_socket = None
        self.phase = "params"
        self.goto("params")

    def cancel_host(self):
        self._cleanup_connection()
        self.goto_menu()

    # ---------------- 客户端 ----------------
    def start_join(self):
        sound.click()
        if self.join_mode == "relay":
            self._start_relay_join()
            return
        host = self.join_screen.addr_input.text.strip()
        try:
            port = int(self.join_screen.port_input.text.strip())
        except ValueError:
            self.join_screen.status.text = self.tr.t("conn_failed")
            return
        if not host:
            self.join_screen.status.text = self.tr.t("conn_failed")
            return
        self.join_screen.status.text = self.tr.t("connecting")
        threading.Thread(target=self._connect_loop, args=(host, port), daemon=True).start()

    def _start_relay_join(self):
        addr = self.join_screen.relay_input.text.strip()
        code = self.join_screen.code_input.text.strip().upper()
        if not code:
            self.join_screen.status.text = self.tr.t("relay_join_error")
            return
        host, port = self._parse_relay_addr(addr)
        self.join_screen.status.text = self.tr.t("connecting")
        threading.Thread(target=self._relay_join_loop, args=(host, port, code), daemon=True).start()

    def _relay_join_loop(self, host, port, code):
        try:
            peer = net.relay_join(host, port, code)
        except OSError:
            Clock.schedule_once(lambda dt: self._relay_join_error(), 0)
            return
        Clock.schedule_once(lambda dt: self._on_client_connected(peer), 0)

    def _relay_join_error(self):
        self.join_screen.status.text = self.tr.t("relay_join_error")

    def _connect_loop(self, host, port):
        try:
            peer = net.connect_to_host(host, port)
        except OSError:
            Clock.schedule_once(lambda dt: self._connect_failed(), 0)
            return
        Clock.schedule_once(lambda dt: self._on_client_connected(peer), 0)

    def _connect_failed(self):
        if self.phase == "join":
            self.join_screen.status.text = self.tr.t("conn_failed")

    def _on_client_connected(self, peer):
        if self.phase != "join":
            peer.close()
            return
        self.peer = peer
        self.phase = "params_wait"
        self.goto("params")

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

    # ---------------- 参数 ----------------
    def send_params(self):
        try:
            w = int(self.params_screen.w_input.text)
            h = int(self.params_screen.h_input.text)
            n = int(self.params_screen.n_input.text)
        except ValueError:
            self.params_screen.err.text = self.tr.t("err_params_invalid")
            return
        ok, ekey = gc.validate_params(w, h, n)
        if not ok:
            self.params_screen.err.text = self.tr.t("err_" + ekey)
            return
        self.w, self.h, self.n = w, h, n
        self.board = gc.Board(w, h, n)
        self.peer.send({"type": "params", "w": w, "h": h, "n": n})
        self.params_screen.err.text = self.tr.t("waiting_client_accept")

    def accept_params(self):
        self.board = gc.Board(self.w, self.h, self.n)
        self.peer.send({"type": "params_accept"})
        self._enter_deploy()

    def reject_params(self):
        self.peer.send({"type": "params_reject"})
        self.params_screen.err.text = self.tr.t("params_waiting")

    def _enter_deploy(self):
        self.phase = "deploy"
        if self.board is None:
            self.board = gc.Board(self.w, self.h, self.n)
        self.orientation = 0
        self.goto("deploy")

    # ---------------- 部署 ----------------
    def set_orientation(self, ori):
        self.orientation = ori
        self.deploy_screen.refresh()

    def on_deploy_tap(self, x, y):
        if self.phase != "deploy" or self.i_ready or self.board is None:
            return
        if self.board.plane_at(x, y) is not None:
            self.board.remove_plane_at(x, y)
            self.deploy_screen.msg.text = ""
        else:
            p = self.board.place((x, y), self.orientation)
            if p is None:
                self.deploy_screen.msg.text = self.tr.t("err_cant_place")
                return
            self.deploy_screen.msg.text = ""
            sound.place()
        self.deploy_screen.refresh()

    def do_random(self):
        if self.i_ready or self.board is None:
            return
        if not gc.random_place(self.board):
            self.deploy_screen.msg.text = self.tr.t("random_failed")
        self.deploy_screen.refresh()

    def do_clear(self):
        if self.i_ready or self.board is None:
            return
        self.board.clear()
        self.deploy_screen.refresh()

    def do_done(self):
        if self.i_ready or self.peer is None:
            return
        if not self.board.all_placed():
            self.deploy_screen.msg.text = self.tr.t("err_need_all", total=self.n)
            return
        self.i_ready = True
        self.peer.send({"type": "ready"})
        if self.opp_ready and self.my_index == 0 and not self.started:
            self._start_game()
            return
        self.deploy_screen.refresh()

    def apply_deploy_ready_state(self):
        if self.i_ready:
            self.deploy_screen.msg.text = self.tr.t("waiting_opponent_deploy")

    # ---------------- 战斗 ----------------
    def on_enemy_tap(self, x, y):
        if self.peer is None or self.phase != "battle" or not self.my_turn or self.awaiting_result:
            return
        if (x, y) in self.my_shots:
            return
        self.awaiting_result = True
        self.peer.send({"type": "shot", "x": x, "y": y})
        sound.shot()
        self.update_turn_status()

    def render_my_board(self, bw):
        bw.set_all(C_SEA)
        if self.board is None:
            bw.refresh()
            return
        self._render_planes(bw, [(p.head, p.orientation, p.alive) for p in self.board.planes])
        for (x, y), term in self.enemy_shots_on_me.items():
            if term in ("DAMAGED", "DESTROYED"):
                bw.set_cell(x, y, C_DAMAGED if term == "DAMAGED" else C_DESTROYED)
            elif term == "EMPTY":
                bw.set_cell(x, y, C_EMPTY)
            elif term == "WRECKAGE":
                bw.set_cell(x, y, C_WRECKAGE)
        bw.refresh()

    def render_revealed_enemy_board(self, bw):
        bw.set_all(C_SEA)
        self._render_planes(bw, self.revealed_enemy_planes)
        for (x, y), term in self.my_shots.items():
            if term == "EMPTY":
                bw.set_cell(x, y, C_EMPTY)
            elif term == "DAMAGED":
                bw.set_cell(x, y, C_DAMAGED)
            elif term == "DESTROYED":
                bw.set_cell(x, y, C_DESTROYED)
            elif term == "WRECKAGE":
                bw.set_cell(x, y, C_WRECKAGE)
        bw.refresh()

    def render_enemy_board(self, bw):
        bw.set_all(C_SEA)
        for (x, y), term in self.my_shots.items():
            if term == "EMPTY":
                bw.set_cell(x, y, C_EMPTY)
            elif term == "DAMAGED":
                bw.set_cell(x, y, C_DAMAGED)
            elif term == "DESTROYED":
                bw.set_cell(x, y, C_DESTROYED)
            elif term == "WRECKAGE":
                bw.set_cell(x, y, C_WRECKAGE)
        bw.refresh()

    @staticmethod
    def _render_planes(bw, planes):
        for (head, ori, alive) in planes:
            coords = gc.plane_absolute(head, ori)
            for (x, y) in coords:
                if alive:
                    bw.set_cell(x, y, C_MY_HEAD if (x, y) == tuple(head) else C_MY_PLANE)
                else:
                    bw.set_cell(x, y, C_WRECKED_HEAD if (x, y) == tuple(head) else C_WRECKED_MINE)

    def update_turn_status(self):
        st = self.battle_screen.status
        if self.awaiting_result:
            st.text = self.tr.t("waiting_result")
        elif self.my_turn:
            st.text = self.tr.t("your_turn")
        else:
            st.text = self.tr.t("enemy_turn")

    def append_log(self, text):
        self.log_text = (self.log_text + text + "\n")[-4000:]
        if self.sm.current == "battle":
            self.battle_screen.log.text = self.log_text

    # ---------------- 消息处理 ----------------
    def _handle_message(self, msg):
        t = msg.get("type")
        if t == "__disconnect__":
            return
        if t == "params":
            self.w, self.h, self.n = msg["w"], msg["h"], msg["n"]
            self.phase = "params"
            self.goto("params")
        elif t == "params_accept":
            self._enter_deploy()
        elif t == "params_reject":
            self.params_screen.err.text = self.tr.t("params_rejected")
            self.phase = "params"
            self.goto("params")
        elif t == "ready":
            self.opp_ready = True
            if self.i_ready and self.my_index == 0 and not self.started:
                self._start_game()
        elif t == "start":
            first = msg.get("first", 0)
            self.started = True
            self.my_turn = (first == self.my_index)
            self.phase = "battle"
            self.goto("battle")
        elif t == "shot":
            self._on_shot(msg)
        elif t == "result":
            self._on_result(msg)
        elif t == "reveal":
            self.revealed_enemy_planes = [(tuple(p["head"]), p["ori"], p["alive"])
                                          for p in msg.get("planes", [])]
            if self.sm.current == "over":
                self.over_screen.refresh()
        elif t == "rematch":
            self.opp_want_rematch = True
            if self.want_rematch:
                self._start_rematch()
            elif self.sm.current == "over":
                self.over_screen.refresh()

    def _on_shot(self, msg):
        if self.phase != "battle":
            return
        x, y = msg["x"], msg["y"]
        term = self.board.apply_shot(x, y, self.enemy_shot_history)
        if term != "INVALID":
            self.enemy_shots_on_me[(x, y)] = term
        gameover = (term != "INVALID") and self.board.all_destroyed()
        self.peer.send({"type": "result", "x": x, "y": y, "term": term, "gameover": gameover})
        self.append_log("%s → (%d,%d)：%s" % (self.tr.t("opponent"), x, y, self.tr.t("term_" + term)))
        if term == "DESTROYED":
            sound.destroy()
        elif term == "DAMAGED":
            sound.hit()
        elif term in ("EMPTY", "WRECKAGE"):
            sound.miss()
        if gameover:
            self._end_game(self.my_index ^ 1)
        else:
            if term != "INVALID":
                self.my_turn = True
            self.update_turn_status()
        if self.sm.current == "battle":
            self.battle_screen.refresh()

    def _on_result(self, msg):
        if self.phase != "battle":
            return
        x, y, term = msg["x"], msg["y"], msg["term"]
        gameover = bool(msg.get("gameover", False))
        self.awaiting_result = False
        if term != "INVALID":
            self.my_shots[(x, y)] = term
            self.my_shot_history.add((x, y))
        self.append_log("%s → (%d,%d)：%s" % (self.tr.t("me"), x, y, self.tr.t("term_" + term)))
        if term == "DESTROYED":
            sound.destroy()
        elif term == "DAMAGED":
            sound.hit()
        elif term in ("EMPTY", "WRECKAGE"):
            sound.miss()
        if gameover:
            self._end_game(self.my_index)
        else:
            self.my_turn = (term == "INVALID")
            self.update_turn_status()
        if self.sm.current == "battle":
            self.battle_screen.refresh()

    def _start_game(self):
        import random
        first = random.randint(0, 1)
        self.started = True
        self.my_turn = (first == self.my_index)
        if self.my_index == 0:
            self.peer.send({"type": "start", "first": first})
        self.phase = "battle"
        self.log_text = ""
        self.goto("battle")

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
        self.goto("over")

    def _send_reveal(self):
        if self.peer is None or self.board is None:
            return
        planes = [{"head": list(p.head), "ori": p.orientation, "alive": p.alive} for p in self.board.planes]
        self.peer.send({"type": "reveal", "planes": planes})

    def request_rematch(self):
        if self.peer is None or self.opp_disconnected:
            self.hint_opp_left()
            return
        if self.want_rematch:
            return
        self.want_rematch = True
        self.peer.send({"type": "rematch"})
        if self.opp_want_rematch:
            self._start_rematch()
        else:
            self.over_screen.refresh()

    def hint_opp_left(self):
        self.opp_disconnected = True
        self.over_screen.refresh()

    def _start_rematch(self):
        self._reset_round()
        self.phase = "deploy"
        self.goto("deploy")

    def _reset_round(self):
        self.board = gc.Board(self.w, self.h, self.n)
        self._clear_round_state()
        self.i_ready = False
        self.opp_ready = False
        self.started = False

    def _clear_round_state(self):
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
        self.orientation = 0

    # ---------------- 清理 / 轮询 ----------------
    def quit_to_menu(self):
        self._cleanup_connection()
        self.goto_menu()

    def do_quit(self):
        self._cleanup_connection()
        self.stop()

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
            if self.sm.current == "over":
                self.over_screen.refresh()
            return
        self._cleanup_connection()
        self.goto_menu()

    def _poll(self, dt):
        if self.peer is not None:
            while True:
                msg = self.peer.recv()
                if msg is None:
                    break
                self._handle_message(msg)
            if self.peer.is_closed():
                self._on_disconnect()
