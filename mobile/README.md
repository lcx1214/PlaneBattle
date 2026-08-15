# 飞机大战 · 移动端（Android / Kivy）

本目录是「飞机大战」的 **Android 移动端**版本，使用 **Kivy** 编写，**触摸适配**，
与桌面版完全复用同一套游戏逻辑与联机协议：

- `game_core.py` —— 纯游戏逻辑（与桌面版同一份）
- `network.py` —— 局域网 TCP 联机（与桌面版同一份协议）
- `ai.py` —— 人机对手
- `i18n.py` —— 中/英/日三语

因此 **手机 APK 可与 Windows 的 exe 在同一局域网内直接对战**（任意一端做主机）。

## 目录结构

| 文件 | 作用 |
| --- | --- |
| `main.py` | 移动端入口 |
| `mobile_app.py` | Kivy 界面 + 对局流程（触摸适配） |
| `game_core.py` / `network.py` / `ai.py` / `i18n.py` | 与桌面版共享的模块（副本，需保持同步） |
| `buildozer.spec` | Android 打包配置 |

## 触摸操作

- **菜单**：点按钮进入主机/加入/人机/说明。
- **部署**：点棋盘格子放置机头（再点一次该飞机可移除）；下方按钮切换朝向、随机、清空、完成、返回。
- **对战**：点右上方「敌方棋盘」开火（己方回合时）；左上方显示我方棋盘。
- 所有按钮均为大按钮，适配手机竖屏。

## 如何打包成 APK

### 方式一：GitHub Actions 云端打包（推荐，无需本机 Android 环境）

1. 把整个 `飞机大战` 目录作为一个 Git 仓库推送到 GitHub（`mobile/` 在仓库内）。
2. 仓库里已有 `.github/workflows/build_apk.yml`。
3. 到 GitHub 的 **Actions** 页面 → 选择 **Build Android APK** → **Run workflow**。
4. 构建完成后，在运行的 **Artifacts** 里下载 `planebattle-apk` 压缩包，解压得到 `*.apk`。

### 方式二：本地 Linux 打包

需要 Linux（或 WSL）+ 已装 buildozer 依赖（Android SDK/NDK 由 buildozer 自动下载）：

```bash
pip install buildozer
cd mobile
buildozer android debug
# 产物在 mobile/bin/ 下
```

首次打包会下载 Android SDK/NDK，耗时较长。

## 安装与联机

1. 把 APK 传到手机安装（需允许「未知来源」安装）。
2. 手机与电脑（或其他手机）连接**同一局域网**（同一路由器/Wi-Fi）。
3. 任一端点「创建房间」，另一端点「加入房间」填入对方 **IP 和端口**（也支持域名，用于内网穿透）。
4. 若连不上：检查双方是否同一局域网、端口一致、路由器是否开启了「AP 隔离」（需关闭）。

> 注意：手机在 Wi-Fi 下访问局域网属于正常网络请求，APK 已声明 `INTERNET` 等权限。

## 与桌面 exe 联机说明

- 桌面版（`dist/飞机大战.exe`）与手机 APK 使用**完全相同**的 TCP 消息协议。
- 建议让**桌面做主机、手机加入**（桌面显示 IP 更方便复制）。
- 双方地图参数由主机设定，客户端确认后开始部署、对战。
