# -*- coding: utf-8 -*-
"""
i18n.py —— 中 / 英 / 日 三语国际化。

使用方式：
    from i18n import Translator
    tr = Translator('zh')
    tr.t('btn_host')
    tr.set_lang('en')
"""

LANGUAGES = ("zh", "en", "ja")
LANGUAGE_NAMES = {"zh": "中文", "en": "English", "ja": "日本語"}

# 字符串表：key -> {lang: text}
STRINGS = {
    # ---- 通用 / 主菜单 ----
    "app_title": {
        "zh": "飞机大战 · 局域网联机",
        "en": "Plane Battle · LAN Multiplayer",
        "ja": "飛行機バトル · LAN対戦",
    },
    "menu_subtitle": {
        "zh": "士字形纸面空战（参数化）",
        "en": "Parametric paper air combat (\"shi\"-shaped plane)",
        "ja": "パラメータ紙面空戦（「士」字形飛行機）",
    },
    "btn_host": {"zh": "创建房间（主机）", "en": "Create Room (Host)", "ja": "ルームを作成（ホスト）"},
    "btn_join": {"zh": "加入房间（客户端）", "en": "Join Room (Client)", "ja": "ルームに参加（クライアント）"},
    "btn_ai": {"zh": "人机对战（单人）", "en": "Play vs AI (Single)", "ja": "AIと対戦（1人プレイ）"},
    "btn_help": {"zh": "游戏说明", "en": "Help / Rules", "ja": "遊び方・ルール"},
    "btn_quit": {"zh": "退出", "en": "Quit", "ja": "終了"},
    "btn_back": {"zh": "返回", "en": "Back", "ja": "戻る"},
    "btn_cancel": {"zh": "取消", "en": "Cancel", "ja": "キャンセル"},
    "language_label": {"zh": "语言 Language 言語", "en": "Language", "ja": "言語"},
    "player_role_host": {"zh": "你：主机（玩家1）", "en": "You: Host (Player 1)", "ja": "あなた：ホスト（プレイヤー1）"},
    "player_role_client": {"zh": "你：客户端（玩家2）", "en": "You: Client (Player 2)", "ja": "あなた：クライアント（プレイヤー2）"},
    "me": {"zh": "我", "en": "Me", "ja": "自分"},
    "opponent": {"zh": "对方", "en": "Opponent", "ja": "相手"},
    "waiting_result": {"zh": "已发送攻击，等待对方结算…", "en": "Shot sent, waiting for result…",
                       "ja": "攻撃を送信しました。結果待ち…"},
    "params_waiting": {"zh": "已连接，等待主机设置游戏参数…", "en": "Connected. Waiting for the host to set parameters…",
                       "ja": "接続しました。ホストのパラメータ設定待ち…"},
    "shape_preview": {"zh": "当前朝向预览（机头为红）", "en": "Current orientation preview (head is red)",
                      "ja": "現在の向きプレビュー（機首は赤）"},

    # ---- 主机页 ----
    "host_title": {"zh": "主机 · 等待玩家连接", "en": "Host · Waiting for player", "ja": "ホスト · プレイヤー待機中"},
    "host_your_ip": {"zh": "你的局域网 IP 地址：", "en": "Your LAN IP address:", "ja": "あなたのLAN IPアドレス："},
    "host_ip_unknown": {"zh": "未检测到，请用 ipconfig 查看 IPv4 地址",
                        "en": "Not detected. Run ipconfig to find your IPv4 address.",
                        "ja": "検出できません。ipconfig で IPv4 アドレスを確認してください"},
    "host_port": {"zh": "端口", "en": "Port", "ja": "ポート"},
    "host_setup_title": {"zh": "创建房间（主机）", "en": "Create Room (Host)", "ja": "ルームを作成（ホスト）"},
    "host_port_hint": {"zh": "双方需使用相同端口；使用内网穿透时请填写映射后的端口。",
                       "en": "Both sides must use the same port. When using NAT traversal, enter the mapped port.",
                       "ja": "両者同じポートを使用。NAT越えの際はマッピング後のポートを入力してください。"},
    "btn_start_listen": {"zh": "开始等待连接", "en": "Start Listening", "ja": "待機開始"},
    "err_port_invalid": {"zh": "端口必须是 1-65535 之间的整数。", "en": "Port must be an integer between 1 and 65535.",
                         "ja": "ポートは 1〜65535 の整数で指定してください。"},
    "host_waiting": {"zh": "等待玩家连接中…（请把 IP 和端口告诉对方）",
                     "en": "Waiting for a player to connect… (tell them your IP and port)",
                     "ja": "プレイヤーの接続を待っています…（IPとポートを相手に伝えてください）"},
    "host_connected": {"zh": "已连接！正在进入游戏…", "en": "Connected! Entering game…", "ja": "接続しました！ゲームに入ります…"},

    # ---- 客户端页 ----
    "join_title": {"zh": "客户端 · 加入房间", "en": "Client · Join Room", "ja": "クライアント · ルームに参加"},
    "join_ip": {"zh": "主机地址（IP 或域名）", "en": "Host address (IP or domain)", "ja": "ホストのアドレス（IP または ドメイン）"},
    "join_port": {"zh": "端口", "en": "Port", "ja": "ポート"},
    "btn_connect": {"zh": "连接", "en": "Connect", "ja": "接続"},
    "connecting": {"zh": "正在连接…", "en": "Connecting…", "ja": "接続中…"},
    "conn_failed": {"zh": "连接失败，请检查 IP / 端口 / 防火墙。", "en": "Connection failed. Check IP / port / firewall.",
                    "ja": "接続に失敗しました。IP / ポート / ファイアウォールを確認してください。"},

    # ---- 参数设置 ----
    "params_title": {"zh": "设置游戏参数", "en": "Game Parameters", "ja": "ゲームパラメータ"},
    "params_hint": {"zh": "由主机设定，双方确认后本局不可更改。", "en": "Set by the host; fixed for the whole game after both confirm.",
                    "ja": "ホストが設定し、双方の確認後は変更できません。"},
    "map_width": {"zh": "棋盘宽度 X（列数，≥5）", "en": "Map width X (columns, ≥5)", "ja": "盤の幅 X（列数、≥5）"},
    "map_height": {"zh": "棋盘高度 Y（行数，≥5）", "en": "Map height Y (rows, ≥5)", "ja": "盤の高さ Y（行数、≥5）"},
    "num_planes": {"zh": "每名玩家飞机数量（≥1）", "en": "Planes per player (≥1)", "ja": "各プレイヤーの機数（≥1）"},
    "btn_confirm_params": {"zh": "确定并发送", "en": "Confirm & Send", "ja": "決定して送信"},
    "err_width_too_small": {"zh": "棋盘宽度必须 ≥ 5。", "en": "Map width must be ≥ 5.", "ja": "盤の幅は 5 以上にしてください。"},
    "err_height_too_small": {"zh": "棋盘高度必须 ≥ 5。", "en": "Map height must be ≥ 5.", "ja": "盤の高さは 5 以上にしてください。"},
    "err_planes_too_few": {"zh": "飞机数量必须 ≥ 1。", "en": "Number of planes must be ≥ 1.", "ja": "機数は 1 以上にしてください。"},
    "err_too_crowded": {"zh": "空间不足：飞机数 × 10 不得超过棋盘总格数（宽×高）。",
                        "en": "Not enough space: planes × 10 must not exceed width × height.",
                        "ja": "スペース不足：機数 × 10 が盤の総マス（幅×高さ）を超えてはいけません。"},
    "err_cannot_fit": {"zh": "棋盘放不下这么多飞机：每架「士」字形飞机固定占 10 格。请减少飞机数量或增大棋盘。",
                       "en": "The board cannot fit this many planes: each \"shi\"-shaped plane uses 10 fixed cells. Reduce the plane count or enlarge the board.",
                       "ja": "この盤にはこれだけの機体を配置できません：「士」字形は固定形状で10マス使います。機数を減らすか、盤を大きくしてください。"},
    "err_params_invalid": {"zh": "参数不合法，请检查。", "en": "Invalid parameters.", "ja": "パラメータが不正です。"},
    "params_confirm_title": {"zh": "对方设定的游戏参数", "en": "Opponent's Game Parameters", "ja": "相手のゲームパラメータ"},
    "btn_accept": {"zh": "接受", "en": "Accept", "ja": "承諾"},
    "btn_reject": {"zh": "拒绝", "en": "Reject", "ja": "拒否"},
    "waiting_client_accept": {"zh": "已发送参数，等待对方确认…", "en": "Parameters sent, waiting for opponent…",
                              "ja": "パラメータを送信しました。相手の確認待ち…"},
    "params_rejected": {"zh": "对方拒绝了参数，请重新设定。", "en": "Opponent rejected the parameters. Set them again.",
                        "ja": "相手がパラメータを拒否しました。再設定してください。"},

    # ---- 部署阶段 ----
    "deploy_title": {"zh": "部署阶段 · 放置你的飞机", "en": "Deployment · Place your planes", "ja": "配置フェーズ · 機体を配置"},
    "deploy_count": {"zh": "已放置 {placed} / {total} 架飞机", "en": "Placed {placed} / {total} planes",
                     "ja": "配置済み {placed} / {total} 機"},
    "orientation_label": {"zh": "朝向", "en": "Orientation", "ja": "向き"},
    "ori_up": {"zh": "上 ↑", "en": "Up ↑", "ja": "上 ↑"},
    "ori_right": {"zh": "右 →", "en": "Right →", "ja": "右 →"},
    "ori_down": {"zh": "下 ↓", "en": "Down ↓", "ja": "下 ↓"},
    "ori_left": {"zh": "左 ←", "en": "Left ←", "ja": "左 ←"},
    "btn_random": {"zh": "随机布置", "en": "Random", "ja": "ランダム配置"},
    "btn_clear": {"zh": "清空", "en": "Clear", "ja": "クリア"},
    "btn_done": {"zh": "完成部署", "en": "Finish Deployment", "ja": "配置完了"},
    "err_cant_place": {"zh": "无法在此放置：越界或与其他飞机重叠。", "en": "Cannot place here: out of bounds or overlapping.",
                       "ja": "ここには置けません：範囲外、または他の機体と重なります。"},
    "err_need_all": {"zh": "请先放置全部 {total} 架飞机。", "en": "Please place all {total} planes first.",
                     "ja": "先に {total} 機すべてを配置してください。"},
    "random_failed": {"zh": "自动布置失败，请手动放置。", "en": "Random placement failed; place manually.",
                      "ja": "自動配置に失敗しました。手動で配置してください。"},
    "waiting_opponent_deploy": {"zh": "等待对方完成部署…", "en": "Waiting for opponent to deploy…",
                                "ja": "相手の配置を待っています…"},
    "deploy_hint": {"zh": "提示：点击格子放置机头（红色为机头）；点击已放飞机可移除。键盘：方向键移动、R 旋转朝向、回车/空格放置、Delete 移除。",
                    "en": "Tip: click a cell to place the plane head; click a placed plane to remove it. Keyboard: arrows move, R rotate, Enter/Space place, Delete remove.",
                    "ja": "ヒント：マスをクリックで機首を配置（機首は赤）。配置済みをクリックで削除。キー：矢印=移動、R=回転、Enter/Space=配置、Delete=削除。"},
    "legend_my_head": {"zh": "机头", "en": "Head", "ja": "機首"},
    "legend_my_part": {"zh": "机体（翼/身/尾）", "en": "Body (wing/body/tail)", "ja": "機体（翼/胴/尾）"},

    # ---- 战斗阶段 ----
    "battle_title": {"zh": "战斗阶段", "en": "Battle", "ja": "戦闘フェーズ"},
    "my_board": {"zh": "我方棋盘（对方攻击痕迹）", "en": "My board (enemy's shots)", "ja": "自分の盤（相手の攻撃痕）"},
    "enemy_board": {"zh": "敌方棋盘（我的攻击）", "en": "Enemy board (my shots)", "ja": "敵の盤（自分の攻撃）"},
    "your_turn": {"zh": "▶ 轮到你攻击：请点击敌方棋盘", "en": "▶ Your turn: click the enemy board",
                  "ja": "▶ あなたの番：敵の盤をクリック"},
    "enemy_turn": {"zh": "⏳ 等待对方攻击…", "en": "⏳ Waiting for opponent…", "ja": "⏳ 相手の攻撃待ち…"},
    "shot_log": {"zh": "战斗记录", "en": "Battle Log", "ja": "戦闘ログ"},
    "btn_quit_battle": {"zh": "退出战斗", "en": "Leave Battle", "ja": "戦闘を離脱"},
    "legend_title": {"zh": "图例说明", "en": "Legend", "ja": "凡例"},
    "lg_unknown": {"zh": "未攻击区域", "en": "Not attacked yet", "ja": "未攻撃"},
    "lg_empty": {"zh": "空白（未命中）", "en": "Empty (miss)", "ja": "空白（ミス）"},
    "lg_damaged": {"zh": "命中（部件受损）", "en": "Hit (part damaged)", "ja": "命中（パーツ損傷）"},
    "lg_destroyed": {"zh": "击落（命中机头）", "en": "Destroyed (head hit)", "ja": "撃墜（機首命中）"},
    "lg_wreckage": {"zh": "残骸（已坠毁部件）", "en": "Wreckage (destroyed plane)", "ja": "残骸（撃墜済み）"},
    "lg_my_plane": {"zh": "我方存活飞机", "en": "My alive plane", "ja": "自分の生存機"},
    "lg_enemy_hit": {"zh": "对方命中我方", "en": "Enemy hit me", "ja": "相手が命中"},
    "lg_enemy_miss": {"zh": "对方未命中", "en": "Enemy missed", "ja": "相手がミス"},

    # ---- 结果术语 ----
    "term_INVALID": {"zh": "无效（越界或已攻击过）", "en": "Invalid (out of bounds / already shot)", "ja": "無効（範囲外・既攻撃）"},
    "term_DESTROYED": {"zh": "击落！命中机头 ✈💥", "en": "Destroyed! Head hit ✈💥", "ja": "撃墜！機首命中 ✈💥"},
    "term_DAMAGED": {"zh": "命中！部件受损", "en": "Hit! Part damaged", "ja": "命中！パーツ損傷"},
    "term_WRECKAGE": {"zh": "残骸（已坠毁飞机部件）", "en": "Wreckage (of a destroyed plane)", "ja": "残骸（撃墜済み機体）"},
    "term_EMPTY": {"zh": "空白（未命中）", "en": "Empty (miss)", "ja": "空白（ミス）"},

    # ---- 结束 ----
    "you_win": {"zh": "🎉 你获胜了！", "en": "🎉 You win!", "ja": "🎉 あなたの勝ちです！"},
    "you_lose": {"zh": "😞 你输了。", "en": "😞 You lose.", "ja": "😞 あなたの負けです。"},
    "game_over": {"zh": "游戏结束", "en": "Game Over", "ja": "ゲームオーバー"},
    "btn_rematch": {"zh": "再来一局", "en": "Rematch", "ja": "もう一度"},
    "btn_back_menu": {"zh": "返回主菜单", "en": "Back to Menu", "ja": "メニューへ戻る"},
    "rematch_waiting": {"zh": "已请求再来一局，等待对方…", "en": "Rematch requested, waiting for opponent…",
                        "ja": "再戦を要求しました。相手待ち…"},
    "rematch_asked": {"zh": "对方想再来一局，请点击“再来一局”接受。", "en": "Opponent wants a rematch — click Rematch to accept.",
                      "ja": "相手が再戦を希望。承諾するには「もう一度」をクリック。"},
    "connection_lost": {"zh": "连接已断开。", "en": "Connection lost.", "ja": "接続が切れました。"},

    # ---- 房间号联机 / 中继 ----
    "mode_direct": {"zh": "直连（局域网）", "en": "Direct (LAN)", "ja": "直接（LAN）"},
    "mode_relay": {"zh": "房间号（服务器）", "en": "Room code (Server)", "ja": "ルームコード（サーバー）"},
    "relay_server": {"zh": "中继服务器 地址:端口", "en": "Relay server host:port", "ja": "中継サーバー ホスト:ポート"},
    "relay_addr_hint": {"zh": "例：127.0.0.1:4000", "en": "e.g. 127.0.0.1:4000", "ja": "例：127.0.0.1:4000"},
    "room_code_label": {"zh": "房间号", "en": "Room code", "ja": "ルームコード"},
    "your_room_code": {"zh": "你的房间号", "en": "Your room code", "ja": "あなたのルームコード"},
    "btn_create_room": {"zh": "创建房间", "en": "Create Room", "ja": "ルーム作成"},
    "btn_join_room": {"zh": "加入房间", "en": "Join Room", "ja": "ルームに参加"},
    "waiting_relay_client": {"zh": "已创建房间，把房间号告诉对方，等待加入…",
                             "en": "Room created. Share the code and wait…",
                             "ja": "ルーム作成済み。コードを共有して待機…"},
    "relay_error": {"zh": "连接中继服务器失败，请检查地址/端口。", "en": "Failed to connect to relay server.",
                    "ja": "中継サーバーへの接続に失敗しました。"},
    "relay_join_error": {"zh": "加入房间失败，请检查房间号是否正确。", "en": "Failed to join room; check the code.",
                         "ja": "ルーム参加に失敗しました。コードを確認してください。"},

    # ---- 终局复盘 ----
    "my_planes_label": {"zh": "我方飞机（复盘）", "en": "My planes (review)", "ja": "自分の機体（復習）"},
    "enemy_planes_label": {"zh": "对方飞机（复盘）", "en": "Opponent's planes (review)", "ja": "相手の機体（復習）"},

    # ---- 退出提示 ----
    "opp_left": {"zh": "对方已退出，无法再来一局。", "en": "Opponent has left.", "ja": "相手が退出しました。"},

    # ---- 帮助 ----
    "help_title": {"zh": "游戏说明", "en": "Help / Rules", "ja": "遊び方・ルール"},
    "help_body": {
        "zh": (
            "【目标】\n"
            "把对方所有飞机的「机头」（红色格）都打掉，你就赢了。\n\n"
            "【怎么玩】\n"
            "1. 先把自己的飞机藏进棋盘：点格子放飞机，可以旋转方向。\n"
            "2. 双方轮流点对方棋盘上的一个格子开火。\n"
            "3. 谁先打掉对方所有机头，谁获胜。\n\n"
            "【开火后会发生什么】\n"
            "· 空白　没打中（格子变灰）\n"
            "· 命中　打中了机身，飞机还在（橙色）\n"
            "· 击落　打中了机头，整架飞机坠毁（红色）\n"
            "· 残骸　这里曾是已坠毁的飞机（棕色）\n\n"
            "【小贴士】\n"
            "· 每架飞机是「士」字形，一共 10 格，但机头只有 1 格。\n"
            "· 打中机身后别停，机头通常就在附近，继续往四周打。\n"
            "· 可以用鼠标点，也可以用方向键移动、回车开火。\n\n"
            "祝你把对方全部击落！"
        ),
        "en": (
            "[Goal]\n"
            "Shoot down every enemy plane's head (the red cell) to win.\n\n"
            "[How to play]\n"
            "1. First hide your planes on your board: click a cell to place, and you can rotate them.\n"
            "2. Take turns clicking one cell on the enemy board to fire.\n"
            "3. Whoever hits all enemy heads first wins.\n\n"
            "[What happens after firing]\n"
            "· Miss       — nothing there (gray)\n"
            "· Hit        — damaged the body, the plane still flies (orange)\n"
            "· Destroyed  — hit the head, the whole plane goes down (red)\n"
            "· Wreckage   — this used to be a downed plane (brown)\n\n"
            "[Tips]\n"
            "· Each plane is a \"shi\" shape, 10 cells in total, but only 1 cell is the head.\n"
            "· After a body hit, keep going — the head is usually nearby.\n"
            "· Use the mouse, or arrow keys + Enter to fire.\n\n"
            "Good luck shooting them all down!"
        ),
        "ja": (
            "【目標】\n"
            "相手の全機の「機首」（赤マス）を撃ち落とせば勝ちです。\n\n"
            "【遊び方】\n"
            "1. まず自分の盤に機体を隠します：マスをクリックで配置、回転もできます。\n"
            "2. 交互に相手の盤の1マスをクリックして攻撃します。\n"
            "3. 先に相手の全機の機首を当てた方が勝ちです。\n\n"
            "【攻撃の結果】\n"
            "· 空白　何もない（グレー）\n"
            "· 命中　機体に命中、まだ飛んでいる（オレンジ）\n"
            "· 撃墜　機首に命中、機体ごと撃墜（赤）\n"
            "· 残骸　撃墜済みの機体だった場所（茶）\n\n"
            "【コツ】\n"
            "· 1機は「士」の形で全10マス、機首はたった1マスです。\n"
            "· 命中したら止めずに、機首はたいていその近くにあります。\n"
            "· マウスでも、矢印キー＋Enterでも操作できます。\n\n"
            "相手を全部撃ち落としましょう！"
        ),
    },
}


class Translator:
    def __init__(self, lang="zh"):
        self.lang = lang if lang in LANGUAGES else "zh"

    def set_lang(self, lang):
        if lang in LANGUAGES:
            self.lang = lang

    def t(self, key, **kwargs):
        entry = STRINGS.get(key)
        if entry is None:
            return key
        text = entry.get(self.lang) or entry.get("zh") or key
        if kwargs:
            try:
                text = text.format(**kwargs)
            except (KeyError, IndexError, ValueError):
                pass
        return text
