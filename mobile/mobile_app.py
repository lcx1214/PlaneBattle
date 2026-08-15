# -*- coding: utf-8 -*-
"""
mobile_app.py —— “飞机大战” Android/移动端（Kivy，触摸适配）。

与桌面版（tkinter）完全共用：
  - game_core.py  纯游戏逻辑
  - network.py    局域网 TCP 联机（同一套 JSON 协议）
  - ai.py         人机对手
  - i18n.py       中/英/日三语

因此移动端可与 Windows 的 exe 直接跨平台局域网对战。

界面为触摸设计：点按棋盘放置/攻击，按钮较大，适配手机竖屏。
"""

import threading

from kivy.app import App
from kivy.clock import Clock
from kivy.core.window import Window
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

import game_core as gc
import network as net
from ai import AIOpponent
from i18n import Translator, LANGUAGES, LANGUAGE_NAMES

# ---------------------------------------------------------------------------
# 颜色（RGB 0-1）
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

BG = _rgb("#eef4f9")
PANEL = _rgb("#ffffff")
NAVY = _rgb("#1f3a52")
INK = _rgb("#263238")
GRAY = _rgb("#54718a")


# ---------------------------------------------------------------------------
# 棋盘控件（触摸点按）
# ---------------------------------------------------------------------------
class BoardWidget(Widget):
    """可点按的网格棋盘。y=1 为最上一行（与桌面版一致）。"""

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

    def refresh(self, *args):
        self.canvas.clear()
        if self.width <= 0 or self.height <= 0:
            return
        cw = self.width / self.cols
        ch = self.height / self.rows
        with self.canvas:
            for gy in range(self.rows):
                for gx in range(self.cols):
                    Color(*self.cell_colors[gy][gx])
                    Rectangle(pos=(self.x + gx * cw,
                                   self.y + self.height - (gy + 1) * ch),
                              size=(cw, ch))
            Color(*C_GRID)
            for i in range(self.cols + 1):
                Line(points=[self.x + i * cw, self.y,
                             self.x + i * cw, self.y + self.height], width=1)
            for j in range(self.rows + 1):
                Line(points=[self.x, self.y + j * ch,
                             self.x + self.width, self.y + j * ch], width=1)

    def on_touch_down(self, touch):
        if self.collide_point(*touch.pos):
            cell = self._pos_to_cell(touch.pos)
            if cell is not None and self.on_tap is not None:
                self.on_tap(*cell)
            return True
        return False

    def _pos_to_cell(self, pos):
        if self.width <= 0 or self.height <= 0:
            return None
        cw = self.width / self.cols
        ch = self.height / self.rows
        gx = int((pos[0] - self.x) / cw)
        gy_bottom = int((pos[1] - self.y) / ch)
        if 0 <= gx < self.cols and 0 <= gy_bottom < self.rows:
            return gx + 1, self.rows - gy_bottom
        return None


class ShapePreview(Widget):
    """显示当前朝向的“士”字形飞机。"""

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
        cw = self.width / cols
        ch = self.height / rows
        with self.canvas:
            for (dx, dy) in rel:
                Color(*(C_MY_HEAD if (dx, dy) == (0, 0) else C_MY_PLANE))
                gx = dx - minx
                gy = dy - miny
                Rectangle(pos=(self.x + gx * cw,
                               self.y + (rows - 1 - gy) * ch),
                          size=(cw, ch))


def make_btn(text, on_press, accent=(0.18, 0.49, 0.20, 1), size_hint_y=None):
    b = Button(text=text, background_normal="", background_color=accent,
               color=(1, 1, 1, 1), font_size=dp(16))
    b.bind(on_press=lambda *a: on_press())
    if size_hint_y is not None:
        b.size_hint_y = size_hint_y
        b.height = dp(48)
    return b


def make_label(text, size=14, color=INK, bold=False):
    return Label(text=text, font_size=dp(size), color=color,
                 bold=bold, halign="left", valign="middle",
                 size_hint_y=None, height=dp(22), text_size=(None, None))


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
        root = BoxLayout(orientation="vertical", padding=dp(16), spacing=dp(10))
        root.add_widget(Label(text=self.app.tr.t("app_title"), font_size=dp(24),
                              bold=True, color=NAVY, size_hint_y=None, height=dp(60)))
        root.add_widget(Label(text=self.app.tr.t("menu_subtitle"), font_size=dp(13),
                              color=GRAY, size_hint_y=None, height=dp(26)))
        root.add_widget(make_btn(self.app.tr.t("btn_host"), self.app.goto_host, (0.18, 0.49, 0.20, 1)))
        root.add_widget(make_btn(self.app.tr.t("btn_join"), self.app.goto_join, (0.08, 0.40, 0.75, 1)))
        root.add_widget(make_btn(self.app.tr.t("btn_ai"), self.app.goto_ai, (0.0, 0.41, 0.36, 1)))
        root.add_widget(make_btn(self.app.tr.t("btn_help"), self.app.goto_help, (0.42, 0.31, 0.64, 1)))
        # 语言切换
        lang_row = BoxLayout(orientation="horizontal", spacing=dp(6), size_hint_y=None, height=dp(44))
        for lang in LANGUAGES:
            mark = "● " if lang == self.app.tr.lang else ""
            lang_row.add_widget(make_btn(mark + LANGUAGE_NAMES[lang],
                                         lambda l=lang: self.app.set_language(l)))
        root.add_widget(lang_row)
        root.add_widget(make_btn(self.app.tr.t("btn_quit"), self.app.do_quit, (0.69, 0.23, 0.23, 1)))
        self.add_widget(root)


class HelpScreen(BaseScreen):
    def build(self):
        self.clear_widgets()
        root = BoxLayout(orientation="vertical", padding=dp(12), spacing=dp(8))
        header = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp(46))
        header.add_widget(Label(text=self.app.tr.t("help_title"), bold=True, font_size=dp(18), color=NAVY))
        header.add_widget(make_btn(self.app.tr.t("btn_back"), self.app.goto_menu, (0.27, 0.36, 0.43, 1)))
        root.add_widget(header)
        sv = ScrollView()
        sv.add_widget(Label(text=self.app.tr.t("help_body"), font_size=dp(14), color=INK,
                            halign="left", valign="top", size_hint_y=None,
                            text_size=(None, None)))
        sv.bind(width=lambda s, w: setattr(s.children[0], "text_size", (w - dp(20), None)))
        root.add_widget(sv)
        self.add_widget(root)


class HostScreen(BaseScreen):
    def build(self):
        self.clear_widgets()
        root = BoxLayout(orientation="vertical", padding=dp(16), spacing=dp(10))
        root.add_widget(Label(text=self.app.tr.t("host_setup_title"), bold=True,
                              font_size=dp(18), color=NAVY, size_hint_y=None, height=dp(40)))
        ip = net.get_primary_ip() or self.app.tr.t("host_ip_unknown")
        root.add_widget(Label(text=self.app.tr.t("host_your_ip"), font_size=dp(14), color=GRAY,
                              size_hint_y=None, height=dp(24)))
        root.add_widget(Label(text=ip, font_size=dp(20), bold=True, color=(0.08, 0.40, 0.75, 1),
                              size_hint_y=None, height=dp(32)))
        row = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp(50), spacing=dp(8))
        row.add_widget(Label(text=self.app.tr.t("host_port"), size_hint_x=0.3, color=INK))
        self.port_input = TextInput(text=str(self.app.host_port), multiline=False,
                                    input_filter="int", size_hint_x=0.7, font_size=dp(16))
        row.add_widget(self.port_input)
        root.add_widget(row)
        self.status = make_label("", size=13, color=GRAY)
        root.add_widget(self.status)
        root.add_widget(make_btn(self.app.tr.t("btn_start_listen"), self.app.start_hosting))
        root.add_widget(make_btn(self.app.tr.t("btn_back"), self.app.cancel_host, (0.27, 0.36, 0.43, 1)))
        self.add_widget(root)


class JoinScreen(BaseScreen):
    def build(self):
        self.clear_widgets()
        root = BoxLayout(orientation="vertical", padding=dp(16), spacing=dp(10))
        root.add_widget(Label(text=self.app.tr.t("join_title"), bold=True,
                              font_size=dp(18), color=NAVY, size_hint_y=None, height=dp(40)))
        row1 = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp(50), spacing=dp(8))
        row1.add_widget(Label(text=self.app.tr.t("join_ip"), size_hint_x=0.35, color=INK))
        self.addr_input = TextInput(text="127.0.0.1", multiline=False, size_hint_x=0.65, font_size=dp(16))
        row1.add_widget(self.addr_input)
        root.add_widget(row1)
        row2 = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp(50), spacing=dp(8))
        row2.add_widget(Label(text=self.app.tr.t("join_port"), size_hint_x=0.35, color=INK))
        self.port_input = TextInput(text=str(net.DEFAULT_PORT), multiline=False,
                                    input_filter="int", size_hint_x=0.65, font_size=dp(16))
        row2.add_widget(self.port_input)
        root.add_widget(row2)
        self.status = make_label("", size=13, color=GRAY)
        root.add_widget(self.status)
        root.add_widget(make_btn(self.app.tr.t("btn_connect"), self.app.start_join, (0.08, 0.40, 0.75, 1)))
        root.add_widget(make_btn(self.app.tr.t("btn_back"), self.app.cancel_host, (0.27, 0.36, 0.43, 1)))
        self.add_widget(root)


class ParamsScreen(BaseScreen):
    """主机设置参数 / 客户端确认参数 共用。"""

    def build(self):
        self.clear_widgets()
        root = BoxLayout(orientation="vertical", padding=dp(16), spacing=dp(10))
        if self.app.phase == "params_wait":
            root.add_widget(Label(text=self.app.tr.t("params_waiting"), font_size=dp(15),
                                  color=INK, size_hint_y=None, height=dp(40)))
            root.add_widget(make_btn(self.app.tr.t("btn_back"), self.app.cancel_host,
                                     (0.27, 0.36, 0.43, 1)))
            self.add_widget(root)
            return
        root.add_widget(Label(text=self.app.tr.t("params_title"), bold=True,
                              font_size=dp(18), color=NAVY, size_hint_y=None, height=dp(40)))
        is_host = (self.app.my_index == 0)
        self.w_input = TextInput(text=str(self.app.w), multiline=False, input_filter="int", font_size=dp(16))
        self.h_input = TextInput(text=str(self.app.h), multiline=False, input_filter="int", font_size=dp(16))
        self.n_input = TextInput(text=str(self.app.n), multiline=False, input_filter="int", font_size=dp(16))
        for label, inp in ((self.app.tr.t("map_width"), self.w_input),
                           (self.app.tr.t("map_height"), self.h_input),
                           (self.app.tr.t("num_planes"), self.n_input)):
            row = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp(50), spacing=dp(8))
            row.add_widget(Label(text=label, size_hint_x=0.55, color=INK))
            row.add_widget(inp)
            inp.size_hint_x = 0.45
            inp.readonly = not is_host
            root.add_widget(row)
        self.err = make_label("", size=13, color=(0.78, 0.16, 0.16, 1))
        root.add_widget(self.err)
        if is_host:
            root.add_widget(make_btn(self.app.tr.t("btn_confirm_params"), self.app.send_params))
        else:
            btn_row = BoxLayout(orientation="horizontal", spacing=dp(8), size_hint_y=None, height=dp(48))
            btn_row.add_widget(make_btn(self.app.tr.t("btn_accept"), self.app.accept_params, (0.18, 0.49, 0.20, 1)))
            btn_row.add_widget(make_btn(self.app.tr.t("btn_reject"), self.app.reject_params, (0.69, 0.23, 0.23, 1)))
            root.add_widget(btn_row)
        root.add_widget(make_btn(self.app.tr.t("btn_back"), self.app.cancel_host, (0.27, 0.36, 0.43, 1)))
        self.add_widget(root)


class DeployScreen(BaseScreen):
    def build(self):
        self.clear_widgets()
        root = BoxLayout(orientation="vertical", padding=dp(8), spacing=dp(6))
        header = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp(44))
        header.add_widget(Label(text=self.app.tr.t("deploy_title"), bold=True,
                                font_size=dp(16), color=NAVY))
        self.count_label = Label(text="", font_size=dp(14), color=(0.18, 0.49, 0.20, 1))
        header.add_widget(self.count_label)
        root.add_widget(header)

        # 棋盘
        self.board = BoardWidget(self.app.w, self.app.h, on_tap=self.app.on_deploy_tap)
        board_box = BoxLayout(orientation="vertical", size_hint_y=1.0)
        board_box.add_widget(self.board)
        root.add_widget(board_box)

        # 朝向按钮
        ori_row = BoxLayout(orientation="horizontal", spacing=dp(6), size_hint_y=None, height=dp(46))
        self.ori_buttons = {}
        for ori, key in ((0, "ori_up"), (90, "ori_right"), (180, "ori_down"), (270, "ori_left")):
            b = make_btn(self.app.tr.t(key), lambda o=ori: self.app.set_orientation(o), (0.08, 0.40, 0.75, 1))
            self.ori_buttons[ori] = b
            ori_row.add_widget(b)
        root.add_widget(ori_row)

        # 预览 + 动作
        mid = BoxLayout(orientation="horizontal", spacing=dp(8), size_hint_y=None, height=dp(70))
        self.preview = ShapePreview(self.app.orientation, size_hint_x=0.5)
        mid.add_widget(self.preview)
        acts = GridLayout(cols=2, spacing=dp(6), size_hint_x=0.5)
        acts.add_widget(make_btn(self.app.tr.t("btn_random"), self.app.do_random, (0.27, 0.36, 0.43, 1)))
        acts.add_widget(make_btn(self.app.tr.t("btn_clear"), self.app.do_clear, (0.27, 0.36, 0.43, 1)))
        acts.add_widget(make_btn(self.app.tr.t("btn_done"), self.app.do_done, (0.18, 0.49, 0.20, 1)))
        acts.add_widget(make_btn(self.app.tr.t("btn_back_menu"), self.app.quit_to_menu, (0.27, 0.36, 0.43, 1)))
        mid.add_widget(acts)
        root.add_widget(mid)

        self.msg = make_label("", size=12, color=(0.78, 0.16, 0.16, 1))
        root.add_widget(self.msg)
        self.add_widget(root)
        self.refresh()

    def refresh(self):
        if self.app.board is None:
            return
        self.count_label.text = self.app.tr.t("deploy_count",
                                              placed=self.app.board.count(), total=self.app.n)
        self.preview.set_orientation(self.app.orientation)
        self.app.render_my_board(self.board)
        self.app.apply_deploy_ready_state()


class BattleScreen(BaseScreen):
    def build(self):
        self.clear_widgets()
        root = BoxLayout(orientation="vertical", padding=dp(8), spacing=dp(6))
        self.status = Label(text="", bold=True, font_size=dp(15), color=(0.08, 0.40, 0.75, 1),
                            size_hint_y=None, height=dp(30))
        root.add_widget(self.status)

        boards = BoxLayout(orientation="horizontal", spacing=dp(8))
        # 我方棋盘（较小）
        left = BoxLayout(orientation="vertical", size_hint_x=0.42)
        left.add_widget(Label(text=self.app.tr.t("my_board"), font_size=dp(12), color=GRAY,
                              size_hint_y=None, height=dp(20)))
        self.my_board = BoardWidget(self.app.w, self.app.h)
        left.add_widget(self.my_board)
        boards.add_widget(left)
        # 敌方棋盘（主战场，较大）
        right = BoxLayout(orientation="vertical", size_hint_x=0.58)
        right.add_widget(Label(text=self.app.tr.t("enemy_board"), font_size=dp(12), color=GRAY,
                               size_hint_y=None, height=dp(20)))
        self.enemy_board = BoardWidget(self.app.w, self.app.h, on_tap=self.app.on_enemy_tap)
        right.add_widget(self.enemy_board)
        boards.add_widget(right)
        root.add_widget(boards)

        # 图例
        legend = Label(text=self.app.legend_text(), font_size=dp(11), color=GRAY,
                       halign="left", valign="top", size_hint_y=None, height=dp(80))
        root.add_widget(legend)

        # 日志
        self.log = Label(text="", font_size=dp(12), color=INK, halign="left", valign="top")
        logsv = ScrollView(size_hint_y=0.9)
        logsv.add_widget(self.log)
        root.add_widget(logsv)

        root.add_widget(make_btn(self.app.tr.t("btn_quit_battle"), self.app.quit_to_menu,
                                 (0.69, 0.23, 0.23, 1)))
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
        root = BoxLayout(orientation="vertical", padding=dp(16), spacing=dp(12))
        root.add_widget(Label(text=self.app.tr.t("game_over"), bold=True,
                              font_size=dp(22), color=NAVY, size_hint_y=None, height=dp(50)))
        if self.app.game_over_winner == self.app.my_index:
            text = self.app.tr.t("you_win")
            color = (0.18, 0.49, 0.20, 1)
        else:
            text = self.app.tr.t("you_lose")
            color = (0.78, 0.16, 0.16, 1)
        root.add_widget(Label(text=text, font_size=dp(20), bold=True, color=color,
                              size_hint_y=None, height=dp(44)))
        self.hint = Label(text="", font_size=dp(13), color=GRAY, size_hint_y=None, height=dp(30))
        root.add_widget(self.hint)
        root.add_widget(make_btn(self.app.tr.t("btn_rematch"), self.app.request_rematch, (0.18, 0.49, 0.20, 1)))
        root.add_widget(make_btn(self.app.tr.t("btn_back_menu"), self.app.quit_to_menu, (0.27, 0.36, 0.43, 1)))
        self.add_widget(root)
        self.refresh()

    def refresh(self):
        if self.app.want_rematch:
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
        self.goto(self.sm.current)   # 重建当前页以刷新文字

    # ---------------- 主机 ----------------
    def start_hosting(self):
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
        self.goto("params")   # 客户端进入“等待主机参数”状态

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
        self.update_turn_status()

    def legend_text(self):
        tr = self.tr
        return (tr.t("lg_unknown") + "　" + tr.t("lg_empty") + "　" +
                tr.t("lg_damaged") + "\n" + tr.t("lg_destroyed") + "　" +
                tr.t("lg_wreckage") + "　" + tr.t("lg_my_plane"))

    def render_my_board(self, bw):
        bw.set_all(C_SEA)
        if self.board is None:
            bw.refresh()
            return
        for p in self.board.planes:
            for (x, y) in p.coords:
                if p.alive:
                    bw.set_cell(x, y, C_MY_HEAD if (x, y) == p.head_coord else C_MY_PLANE)
                else:
                    bw.set_cell(x, y, C_WRECKED_HEAD if (x, y) == p.head_coord else C_WRECKED_MINE)
        for (x, y), term in self.enemy_shots_on_me.items():
            if term in ("DAMAGED", "DESTROYED"):
                bw.set_cell(x, y, C_DAMAGED if term == "DAMAGED" else C_DESTROYED)
            elif term == "EMPTY":
                bw.set_cell(x, y, C_EMPTY)
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

    # ---------------- 消息处理（与桌面版一致） ----------------
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
        self.goto("over")

    def request_rematch(self):
        if self.want_rematch:
            return
        self.want_rematch = True
        self.peer.send({"type": "rematch"})
        if self.opp_want_rematch:
            self._start_rematch()
        else:
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
        self.my_turn = False
        self.awaiting_result = False
        self.game_over_winner = None
        self.want_rematch = False
        self.opp_want_rematch = False
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
        if self.phase in ("menu", "over"):
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
