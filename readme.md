# File Master Pro

> 一款基于 Python + Tkinter 的 macOS 文件管理与重复文件清理工具，v2.0
>
> A macOS file management & duplicate cleaner built with Python + Tkinter, v2.0

[English](#english) | [中文](#中文)

---

<a name="中文"></a>
## 中文

### 功能特性

| 类别 | 功能 |
|------|------|
| **扫描** | 多目录同时扫描（英文逗号分隔），多线程执行，可随时停止 |
| **查重** | 两阶段算法：先按文件大小分组，再对同大小文件计算 MD5 哈希，精准识别重复 |
| **缓存** | SQLite 哈希缓存（`file_hash_cache.db`），重复扫描同一文件无需重新计算 |
| **筛选** | 关键词过滤（支持普通文本 / 正则表达式）、7 种文件类型过滤、大小范围过滤（B/KB/MB/GB） |
| **排序** | 6 种排序方式：大小升/降、文件名 A-Z/Z-A、修改时间新/旧 |
| **重命名** | 批量重命名：查找替换 + 自动编号（可预览后再执行） |
| **删除** | 将选中文件移至系统回收站（send2trash，可恢复） |
| **批量清理** | 一键清理所有重复副本，每组自动保留修改时间最新的文件 |
| **右键菜单** | 在重复文件列表中右键，可保留指定文件并清理其余副本 |
| **预览** | 文本预览（前 100 行，UTF-8 / 系统编码自动回退）、图片预览（Pillow）、macOS Quick Look 原生预览（双击或空格键） |
| **主题** | 通过 Settings → Theme 切换界面主题（ttkthemes，9 个可选主题） |
| **配置** | JSON 配置自动持久化（`file_master_pro_config.json`），记录上次目录、窗口尺寸、主题 |
| **打包** | 支持通过 py2app 打包为独立 macOS .app 应用 |

### 环境要求

- **操作系统**：macOS（Quick Look 预览功能依赖 `qlmanage`，为 macOS 专属）
- **Python**：3.10 或更高版本（代码使用了 walrus operator `:=`）
- **第三方依赖**：`ttkthemes` · `send2trash` · `Pillow`

### 安装与运行

```bash
pip install ttkthemes send2trash Pillow
python main.py
```

### 打包为 macOS 应用（可选）

```bash
pip install -U py2app
python setup.py py2app
```

打包产物位于 `dist/` 目录。

> **注意**：`setup.py` 的 `packages` 列表中包含 `PyQt5`，但当前代码不依赖 PyQt5。若打包时遇到相关报错，可将其从 `packages` 中移除。

### 自动生成的文件

| 文件 | 说明 |
|------|------|
| `file_hash_cache.db` | SQLite 哈希缓存，可安全删除（下次扫描会重建） |
| `file_master_pro_config.json` | 用户配置，记录上次目录、窗口大小、主题偏好 |

### 使用说明

1. 在顶部输入框填写扫描目录（多个目录用英文逗号 `,` 分隔）
2. 点击 **▶️ 开始扫描**，扫描中可点击 **⏹️ 停止扫描** 中断
3. 扫描完成后，在 **📂 所有文件** 标签页查看全部文件，在 **📜 重复文件** 标签页查看重复组
4. 使用筛选区域按关键词、类型、大小缩小范围
5. 选中文件后可进行预览、重命名、移至回收站等操作
6. 在重复文件列表中右键单个文件，可保留该文件并清理同组其余副本
7. 点击 **‼️ 批量清理所有重复项** 可一键清理全部重复副本（每组保留最新）

### 许可证

MIT License © 2025

---

<a name="english"></a>
## English

### Features

| Category | Description |
|----------|-------------|
| **Scan** | Multi-directory scan (comma-separated), multi-threaded, stoppable at any time |
| **Dedup** | Two-phase algorithm: group by file size first, then MD5 hash only size-matched candidates |
| **Cache** | SQLite hash cache (`file_hash_cache.db`) — repeat scans are near-instant |
| **Filter** | Keyword filter (plain text or regex), 7 file type categories, size range filter (B/KB/MB/GB) |
| **Sort** | 6 sort modes: size ↑↓, filename A-Z/Z-A, modified time newest/oldest |
| **Rename** | Batch rename: find & replace or auto-numbering, with preview before applying |
| **Delete** | Move selected files to system Trash via send2trash (recoverable) |
| **Bulk Clean** | One-click cleanup of all duplicate copies — keeps the newest file in each group |
| **Context Menu** | Right-click a duplicate to keep it and trash all other copies in the group |
| **Preview** | Text preview (first 100 lines, UTF-8 with system encoding fallback), image preview (Pillow), macOS Quick Look (double-click or spacebar) |
| **Themes** | Switch UI themes via Settings → Theme (9 themes via ttkthemes) |
| **Config** | Auto-persisted JSON config (`file_master_pro_config.json`) — saves last directory, window size, theme |
| **Package** | Supports building a standalone macOS .app via py2app |

### Requirements

- **OS**: macOS (Quick Look preview requires `qlmanage`, macOS only)
- **Python**: 3.10+ (uses walrus operator `:=`)
- **Dependencies**: `ttkthemes` · `send2trash` · `Pillow`

### Installation & Run

```bash
pip install ttkthemes send2trash Pillow
python main.py
```

### Package as macOS App (Optional)

```bash
pip install -U py2app
python setup.py py2app
```

Output is in the `dist/` directory.

> **Note**: `setup.py` lists `PyQt5` in `packages`, but the app does not use PyQt5. If you encounter PyQt5-related errors during packaging, remove it from the `packages` list.

### Auto-generated Files

| File | Description |
|------|-------------|
| `file_hash_cache.db` | SQLite hash cache — safe to delete, will be rebuilt on next scan |
| `file_master_pro_config.json` | User config — stores last directory, window geometry, theme preference |

### Usage

1. Enter scan directories in the top input box (separate multiple paths with `,`)
2. Click **▶️ Start Scan** — click **⏹️ Stop Scan** to interrupt at any time
3. After scanning, view all files in the **📂 All Files** tab and duplicate groups in the **📜 Duplicates** tab
4. Use the filter panel to narrow results by keyword, type, or size
5. Select a file to preview, rename, or move to Trash
6. Right-click a file in the Duplicates tab to keep it and trash all other copies in its group
7. Click **‼️ Clean All Duplicates** to bulk-remove all duplicate copies (keeps the newest in each group)

### License

MIT License © 2025
