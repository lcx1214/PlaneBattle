[app]

# (str) 应用标题
title = Plane Battle

# (str) 包名
package.name = planebattle

# (str) 包域名（用于生成 Java 包：org.planebattle）
package.domain = org

# (str) 源码目录（相对本 spec 文件）
source.dir = .

# (list) 要包含的源码扩展名（含字体与音效）
source.include_exts = py,ttf,otf,wav

# (str) 应用版本
version = 1.0.0

# (list) 构建依赖（使用 p4a 稳定版默认的 Python 3.11，与 Kivy 兼容）
requirements = python3,kivy

# (str) 固定 python-for-android 到稳定版本（避免 master 分支的 Python 3.14 / pip 不兼容问题）
p4a.fork = kivy
p4a.branch = v2024.01.21

# (str) 屏幕方向：竖屏（portrait）适配手机
orientation = portrait

# (bool) 是否全屏
fullscreen = 0

# (str) 启动入口文件
# buildozer 默认使用 main.py

# (list) Android 权限（局域网联机需要网络权限）
android.permissions = INTERNET, ACCESS_NETWORK_STATE, ACCESS_WIFI_STATE

# (bool) 自动接受 SDK 许可
android.accept_sdk_license = True

# (int) 目标 / 最低 Android API
android.api = 33
android.minapi = 21
android.ndk_api = 21

# (bool) 允许在手机上安装 debug 包
android.allow_backup = True

# (str) 图标
icon.filename = %(source.dir)s/app_icon.png

[buildozer]

# (str) 输出 APK 的目录
# 默认 bin/

# (int) 构建日志级别
log_level = 2

# (bool) 失败时是否自动打开调试信息
warn_on_root = 0
