# -*- coding: utf-8 -*-
"""
sound.py —— 游戏音效（跨平台）。

- Windows 桌面（含 exe）：使用标准库 winsound 播放 WAV。
- Android 移动端（Kivy）：使用 kivy.core.audio.SoundLoader 播放 WAV。

音效文件位于本模块同级的 sounds/ 目录。
"""

import os
import sys

if getattr(sys, "frozen", False):
    # PyInstaller 打包后资源在 _MEIPASS
    _SOUND_DIR = os.path.join(sys._MEIPASS, "sounds")
else:
    _SOUND_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sounds")

# 选择后端：Windows 有 winsound；Android 无 winsound，改用 Kivy
try:
    import winsound
    _BACKEND = "winsound"
except ImportError:
    _BACKEND = "kivy"

if _BACKEND == "kivy":
    from kivy.core.audio import SoundLoader
    _cache = {}

    def _play(name):
        try:
            s = _cache.get(name)
            if s is None:
                path = os.path.join(_SOUND_DIR, name + ".wav")
                s = SoundLoader.load(path)
                _cache[name] = s
            if s is not None:
                s.stop()
                s.play()
        except Exception:
            pass
else:
    # Windows：winsound（文件名中文路径也能用）
    def _play(name):
        path = os.path.join(_SOUND_DIR, name + ".wav")
        if os.path.exists(path):
            try:
                winsound.PlaySound(path, winsound.SND_FILENAME | winsound.SND_ASYNC)
            except Exception:
                pass


def shot():
    _play("shot")


def hit():
    _play("hit")


def miss():
    _play("miss")


def destroy():
    _play("destroy")


def win():
    _play("win")


def lose():
    _play("lose")


def place():
    _play("place")


def click():
    _play("click")
