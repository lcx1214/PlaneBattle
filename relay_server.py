# -*- coding: utf-8 -*-
"""
relay_server.py —— 房间号联机中继服务器（用于内网穿透替代方案）。

主机与客户端各自连接本服务器，用「房间号」匹配后，服务器在两者之间透明转发 TCP 数据。
这样客户端只需填写一个房间号即可与主机联机，无需内网穿透/公网 IP。

运行（放在有公网 IP 或做了端口转发的服务器上）：
    python relay_server.py [端口]      # 默认端口 4000

游戏客户端「房间号模式」填写的服务器地址 = 本服务器的 IP 或域名 + 该端口。
"""

import json
import random
import socket
import string
import sys
import threading

DEFAULT_PORT = 4000


def recv_line(sock):
    """逐字节读取一行（到 \\n 为止），避免缓冲读过头。"""
    data = b""
    while True:
        try:
            ch = sock.recv(1)
        except OSError:
            return data
        if not ch:
            return data
        if ch == b"\n":
            return data
        data += ch


def send_line(sock, obj):
    try:
        sock.sendall((json.dumps(obj, ensure_ascii=False) + "\n").encode("utf-8"))
    except OSError:
        pass


def forward(src, dst):
    """单向转发 src -> dst，直到对端关闭或出错。"""
    try:
        while True:
            data = src.recv(4096)
            if not data:
                break
            dst.sendall(data)
    except OSError:
        pass
    finally:
        try:
            dst.shutdown(socket.SHUT_WR)
        except OSError:
            pass


class RelayServer:
    def __init__(self, port):
        self.port = port
        self.rooms = {}          # code -> {"host", "client", "joined"}
        self.lock = threading.Lock()

    def _gen_code_locked(self):
        while True:
            code = "".join(random.choices(string.ascii_uppercase + string.digits, k=5))
            if code not in self.rooms:
                return code

    def handle(self, conn, addr):
        conn.settimeout(180)
        try:
            line = recv_line(conn)
            if not line:
                conn.close()
                return
            msg = json.loads(line.decode("utf-8", "ignore"))
        except (ValueError, OSError):
            conn.close()
            return

        typ = msg.get("type")
        if typ == "host":
            self._handle_host(conn)
        elif typ == "join":
            self._handle_join(conn, msg.get("code"))
        else:
            conn.close()

    def _handle_host(self, conn):
        with self.lock:
            code = self._gen_code_locked()
            room = {"host": conn, "client": None, "joined": threading.Event()}
            self.rooms[code] = room
        send_line(conn, {"type": "room_code", "code": code})
        conn.settimeout(None)
        # 等待客户端加入（最长 10 分钟）
        if not room["joined"].wait(600):
            with self.lock:
                self.rooms.pop(code, None)
            try:
                conn.close()
            except OSError:
                pass

    def _handle_join(self, conn, code):
        code = (code or "").strip().upper()
        with self.lock:
            room = self.rooms.get(code)
        if room is None or room["client"] is not None:
            send_line(conn, {"type": "error", "msg": "room_not_found"})
            conn.close()
            return
        room["client"] = conn
        room["joined"].set()
        send_line(room["host"], {"type": "relay_ready"})
        send_line(conn, {"type": "relay_ready"})
        conn.settimeout(None)
        room["host"].settimeout(None)

        t1 = threading.Thread(target=forward, args=(room["host"], conn), daemon=True)
        t2 = threading.Thread(target=forward, args=(conn, room["host"]), daemon=True)
        t1.start()
        t2.start()
        t1.join()
        t2.join()

        with self.lock:
            self.rooms.pop(code, None)
        try:
            room["host"].close()
        except OSError:
            pass
        try:
            conn.close()
        except OSError:
            pass

    def run(self):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind(("0.0.0.0", self.port))
        s.listen(64)
        print("Relay server listening on port %d ..." % self.port, flush=True)
        while True:
            conn, addr = s.accept()
            threading.Thread(target=self.handle, args=(conn, addr), daemon=True).start()


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_PORT
    RelayServer(port).run()
