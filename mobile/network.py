# -*- coding: utf-8 -*-
"""
network.py —— 局域网 TCP 联机（基于标准库 socket）。

- 消息为「换行分隔的 JSON」，文本统一 UTF-8。
- Peer 内含后台读线程，把收到的消息放入线程安全队列，供主线程（tkinter）轮询。
- 提供 get_local_ips() 以便主机向对方展示自己的局域网 IP。
"""

import json
import queue
import socket
import threading

DEFAULT_PORT = 34567
PROTOCOL_VERSION = 1


class Peer:
    """封装一条已建立的 TCP 连接。"""

    def __init__(self, sock, name="peer"):
        self.sock = sock
        self.name = name
        self.sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        self.inbox = queue.Queue()
        self.closed = threading.Event()
        self._write_lock = threading.Lock()
        self._reader = threading.Thread(target=self._read_loop, name="net-reader", daemon=True)
        self._reader.start()

    def _read_loop(self):
        try:
            f = self.sock.makefile("r", encoding="utf-8", newline="\n")
        except OSError:
            self.closed.set()
            return
        try:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    msg = json.loads(line)
                    self.inbox.put(msg)
                except (json.JSONDecodeError, TypeError):
                    # 忽略无法解析的行
                    continue
        except (OSError, ValueError):
            pass
        finally:
            try:
                f.close()
            except OSError:
                pass
            self.closed.set()
            self.inbox.put({"type": "__disconnect__"})

    def send(self, msg):
        """发送一个 JSON 消息。失败返回 False。"""
        try:
            data = (json.dumps(msg, ensure_ascii=False) + "\n").encode("utf-8")
            with self._write_lock:
                self.sock.sendall(data)
            return True
        except (OSError, ValueError):
            self.closed.set()
            return False

    def recv(self):
        """非阻塞取一条消息；没有则返回 None。"""
        try:
            return self.inbox.get_nowait()
        except queue.Empty:
            return None

    def is_closed(self):
        return self.closed.is_set()

    def close(self):
        self.closed.set()
        try:
            self.sock.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
        try:
            self.sock.close()
        except OSError:
            pass


def get_local_ips():
    """尽力枚举本机局域网 IPv4 地址（用于主机展示给客户端填写）。"""
    ips = set()
    # 方式一：主机名解析
    try:
        hostname = socket.gethostname()
        for ip in socket.gethostbyname_ex(hostname)[2]:
            if not ip.startswith("127."):
                ips.add(ip)
    except OSError:
        pass
    # 方式二：UDP“假连接”获取对外网卡地址（不真正发包）
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(1)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        if not ip.startswith("127."):
            ips.add(ip)
        s.close()
    except OSError:
        pass
    return sorted(ips)


def get_primary_ip():
    """返回一个“最可能正确”的局域网 IPv4 地址（只一个，避免多网卡造成困惑）。

    优先使用 UDP 路由探测（得到真正对外活动的网卡地址），
    失败则回退到主机名解析的首个非回环地址。
    """
    # 方式一：UDP 路由探测（最准确）
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(1)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        if ip and not ip.startswith("127."):
            return ip
    except OSError:
        pass
    # 方式二：主机名解析，过滤常见的虚拟网卡网段
    try:
        hostname = socket.gethostname()
        candidates = []
        for ip in socket.gethostbyname_ex(hostname)[2]:
            if ip.startswith("127.") or ip.startswith("169.254."):
                continue
            candidates.append(ip)
        if candidates:
            # 优先 192.168.* / 10.* / 172.16-31.*（常见局域网段）
            for ip in candidates:
                if ip.startswith("192.168.") or ip.startswith("10.") or \
                        (ip.startswith("172.") and 16 <= int(ip.split(".")[1]) <= 31):
                    return ip
            return candidates[0]
    except OSError:
        pass
    return ""


def create_host_socket(port):
    """创建监听 socket。"""
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind(("0.0.0.0", port))
    s.listen(1)
    return s


def accept_client(host_socket):
    """阻塞接受一个连接，返回 Peer。"""
    conn, addr = host_socket.accept()
    return Peer(conn, name=str(addr))


def connect_to_host(host, port, timeout=8.0):
    """连接主机。host 支持 IP、域名/链接（内网穿透时填域名即可）。"""
    s = socket.create_connection((host, port), timeout=timeout)
    s.settimeout(None)
    return Peer(s, name=host)


def _recv_line_raw(sock):
    """逐字节读取一行（到 \\n），用于中继握手，避免缓冲读过头。"""
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


def _send_line_raw(sock, obj):
    sock.sendall((json.dumps(obj, ensure_ascii=False) + "\n").encode("utf-8"))


def relay_host(relay_host, relay_port, timeout=20.0):
    """房间号模式：主机连接中继服务器，立即返回 (Peer, 房间号)。"""
    s = socket.create_connection((relay_host, relay_port), timeout=timeout)
    s.settimeout(timeout)
    try:
        _send_line_raw(s, {"type": "host"})
        line = _recv_line_raw(s)
        msg = json.loads(line.decode("utf-8", "ignore")) if line else {}
        code = msg.get("code")
        if not code:
            raise OSError("relay host failed")
    except Exception:
        try:
            s.close()
        except OSError:
            pass
        raise
    s.settimeout(None)
    return Peer(s, name="relay:" + code), code


def relay_join(relay_host, relay_port, code, timeout=20.0):
    """房间号模式：客户端连接中继服务器并加入指定房间，返回 Peer。"""
    s = socket.create_connection((relay_host, relay_port), timeout=timeout)
    s.settimeout(timeout)
    try:
        _send_line_raw(s, {"type": "join", "code": (code or "").strip().upper()})
        line = _recv_line_raw(s)
        msg = json.loads(line.decode("utf-8", "ignore")) if line else {}
        if msg.get("type") != "relay_ready":
            raise OSError("relay join failed: " + str(msg))
    except Exception:
        try:
            s.close()
        except OSError:
            pass
        raise
    s.settimeout(None)
    return Peer(s, name="relay:" + code)
