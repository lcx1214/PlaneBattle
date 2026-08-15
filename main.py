# -*- coding: utf-8 -*-
"""
main.py —— “飞机大战”程序入口。

直接运行：  python main.py
（若用 pythonw 启动则不显示控制台窗口，异常会写入 error.log）
"""

import sys


def main():
    # 尝试以 UTF-8 输出（Windows 控制台友好，失败则忽略）
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, OSError):
        pass

    from ui import run
    try:
        run()
    except Exception:
        # 用 pythonw 启动时没有控制台，把异常写到 error.log 便于排查
        import datetime
        import traceback
        try:
            with open("error.log", "a", encoding="utf-8") as f:
                f.write("\n[%s]\n%s\n" % (datetime.datetime.now(), traceback.format_exc()))
        except OSError:
            pass
        raise


if __name__ == "__main__":
    main()
