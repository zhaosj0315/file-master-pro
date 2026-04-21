# -*- coding: utf-8 -*-
"""
文件管理大师 (File Master Pro) - v2.0 (最终功能版)

作者: [Your Name]
日期: 2025-08-23

新增功能:
- 主题切换: 在 Settings -> Theme 菜单中选择界面主题。
- 正则表达式搜索: 在关键词输入框旁勾选 "Regex" 以启用。
- 批量重命名: 选中文件后，点击下方 "批量重命名选中项" 按钮。
- 打包支持: 可通过 py2app 打包为独立的 macOS 应用。
"""

# --- 标准库 ---
import os
import sys
import subprocess
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import datetime
import hashlib
import threading
import queue
import json
import sqlite3
import locale
import tempfile
import re
from typing import Optional, Dict, List, Tuple, Any, Callable
from enum import Enum, auto
from dataclasses import dataclass

# --- 第三方库 ---
try:
    from ttkthemes import ThemedTk
    import send2trash
    from PIL import Image, ImageTk, UnidentifiedImageError
except ImportError as e:
    root = tk.Tk()
    root.withdraw()
    missing_module = str(e).split("'")[-2]
    messagebox.showerror(
        "缺少必要的库 (Missing Library)",
        f"错误: 模块 '{missing_module}' 未找到。\n\n"
        f"请在终端中运行以下命令来安装所有必需的库:\n"
        f"pip install ttkthemes send2trash Pillow"
    )
    sys.exit(1)

# =============================================================================
# 0. 常量与数据结构
# =============================================================================
CONFIG_FILE = 'file_master_pro_config.json'
DB_FILE = "file_hash_cache.db"
SIZE_UNITS = {"B": 1, "KB": 1024, "MB": 1024**2, "GB": 1024**3}

class QueueMsgType(Enum):
    PROGRESS = auto()
    COMPLETED = auto()
    STOPPED = auto()
    ERROR = auto()

@dataclass
class FileInfo:
    size: int
    mtime: float
    hash: Optional[str] = None

# =============================================================================
# 1. 配置管理
# =============================================================================
def load_config() -> Dict[str, Any]:
    defaults = {
        'last_directory': os.path.expanduser('~'),
        'window_geometry': '1500x950+100+100',
        'theme': 'adapta'
    }
    if not os.path.exists(CONFIG_FILE): return defaults
    try:
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            loaded_config = json.load(f)
        defaults.update(loaded_config)
        return defaults
    except (json.JSONDecodeError, IOError):
        return defaults

def save_config(config: Dict[str, Any]):
    try:
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=4)
    except IOError as e:
        print(f"错误：无法保存配置文件 - {e}")

# =============================================================================
# 2. 批量重命名对话框
# =============================================================================
class BatchRenameDialog(tk.Toplevel):
    def __init__(self, parent, files_to_rename, callback):
        super().__init__(parent)
        self.transient(parent)
        self.title("Batch Rename")
        self.files = files_to_rename
        self.callback = callback
        
        self.geometry("700x500")
        
        main_frame = ttk.Frame(self, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Find & Replace
        replace_frame = ttk.LabelFrame(main_frame, text="Find and Replace", padding=10)
        replace_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(replace_frame, text="Find:").grid(row=0, column=0, sticky='w', pady=2)
        self.find_var = tk.StringVar()
        ttk.Entry(replace_frame, textvariable=self.find_var).grid(row=0, column=1, sticky='ew', padx=5)
        
        ttk.Label(replace_frame, text="Replace with:").grid(row=1, column=0, sticky='w', pady=2)
        self.replace_var = tk.StringVar()
        ttk.Entry(replace_frame, textvariable=self.replace_var).grid(row=1, column=1, sticky='ew', padx=5)
        
        replace_frame.columnconfigure(1, weight=1)

        # Numbering
        num_frame = ttk.LabelFrame(main_frame, text="Add Numbering", padding=10)
        num_frame.pack(fill=tk.X, pady=5)
        
        self.add_num_var = tk.BooleanVar()
        ttk.Checkbutton(num_frame, text="Enable Numbering", variable=self.add_num_var).grid(row=0, column=0, columnspan=2, sticky='w')
        
        ttk.Label(num_frame, text="Prefix:").grid(row=1, column=0, sticky='w', pady=2)
        self.num_prefix_var = tk.StringVar(value="file_")
        ttk.Entry(num_frame, textvariable=self.num_prefix_var).grid(row=1, column=1)

        ttk.Label(num_frame, text="Start at:").grid(row=2, column=0, sticky='w', pady=2)
        self.num_start_var = tk.StringVar(value="1")
        ttk.Entry(num_frame, textvariable=self.num_start_var).grid(row=2, column=1)

        # Action Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, side=tk.BOTTOM, pady=10)
        
        ttk.Button(button_frame, text="Preview Changes", command=self.preview_rename).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Apply Rename", command=self.apply_rename).pack(side=tk.RIGHT)
        ttk.Button(button_frame, text="Cancel", command=self.destroy).pack(side=tk.RIGHT, padx=5)
        
        # Preview Listbox
        preview_label = ttk.Label(main_frame, text="Preview:")
        preview_label.pack(fill=tk.X, pady=(10,0), anchor='w')
        
        preview_list_frame = ttk.Frame(main_frame)
        preview_list_frame.pack(fill=tk.BOTH, expand=True)
        self.preview_list = tk.Listbox(preview_list_frame)
        self.preview_list.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar = ttk.Scrollbar(preview_list_frame, orient="vertical", command=self.preview_list.yview)
        self.preview_list.config(yscrollcommand=scrollbar.set)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.grab_set()
        self.wait_window()

    def generate_new_names(self):
        find_text = self.find_var.get()
        replace_text = self.replace_var.get()
        use_numbering = self.add_num_var.get()
        
        new_names = {}
        counter = int(self.num_start_var.get()) if self.num_start_var.get().isdigit() else 1
        
        for old_path in self.files:
            directory = os.path.dirname(old_path)
            filename, ext = os.path.splitext(os.path.basename(old_path))
            new_filename = filename
            
            if use_numbering:
                prefix = self.num_prefix_var.get()
                new_filename = f"{prefix}{counter}"
                counter += 1
            elif find_text:
                new_filename = new_filename.replace(find_text, replace_text)
            
            new_path = os.path.join(directory, new_filename + ext)
            new_names[old_path] = new_path
        
        return new_names

    def preview_rename(self):
        self.preview_list.delete(0, tk.END)
        self.new_name_map = self.generate_new_names()
        for old, new in self.new_name_map.items():
            self.preview_list.insert(tk.END, f"{os.path.basename(old)}  ->  {os.path.basename(new)}")

    def apply_rename(self):
        self.preview_rename()
        
        if messagebox.askyesno("Confirm Rename", f"Are you sure you want to rename {len(self.files)} files? This cannot be undone.", parent=self):
            renamed_count = 0
            errors = []
            for old, new in self.new_name_map.items():
                if old == new or os.path.exists(new):
                    if old != new: errors.append(f"Destination exists: {os.path.basename(new)}")
                    continue
                try:
                    os.rename(old, new)
                    renamed_count += 1
                except OSError as e:
                    errors.append(f"Could not rename {os.path.basename(old)}: {e}")
            
            if errors:
                messagebox.showerror("Rename Errors", "\n".join(errors), parent=self)

            messagebox.showinfo("Rename Complete", f"Successfully renamed {renamed_count} files.", parent=self)
            self.destroy()
            self.callback(rescan=True)

# =============================================================================
# 3. 数据库缓存管理器
# =============================================================================
class HashCacheDB:
    # ... (No changes from previous version)
    def __init__(self, db_file=DB_FILE):
        self.conn = sqlite3.connect(db_file, check_same_thread=False)
        self._create_table()

    def _create_table(self):
        with self.conn:
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS file_hashes (
                    filepath TEXT PRIMARY KEY, mtime REAL NOT NULL,
                    size INTEGER NOT NULL, hash TEXT NOT NULL
                )""")

    def get_cached_hash(self, filepath: str, mtime: float, size: int) -> Optional[str]:
        cursor = self.conn.cursor()
        cursor.execute("SELECT hash FROM file_hashes WHERE filepath=? AND mtime=? AND size=?", (filepath, mtime, size))
        result = cursor.fetchone()
        return result[0] if result else None

    def update_hash(self, filepath: str, mtime: float, size: int, file_hash: str):
        with self.conn:
            self.conn.execute("INSERT OR REPLACE INTO file_hashes VALUES (?, ?, ?, ?)", (filepath, mtime, size, file_hash))

    def close(self):
        if self.conn: self.conn.close()


# =============================================================================
# 4. 主应用类
# =============================================================================
class FileCleanerApp:
    def __init__(self, master: ThemedTk):
        self.master = master
        self.config = load_config()
        master.title("File Master Pro - v2.0")
        master.geometry(self.config.get('window_geometry'))
        master.set_theme(self.config.get('theme', 'adapta'))

        self.create_main_menu()

        self.file_data_cache: Dict[str, FileInfo] = {}
        self.duplicate_groups: Dict[str, List[str]] = {}
        self.current_displayed_files: List[str] = []

        self.scan_thread: Optional[threading.Thread] = None
        self.scan_queue = queue.Queue()
        self.stop_event = threading.Event()
        self.db_manager = HashCacheDB()

        self.setup_ui_configs()
        self.create_widgets()

        self.master.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.master.after(100, self.process_queue)
        self._after_id = None

    def create_main_menu(self):
        menubar = tk.Menu(self.master)
        self.master.config(menu=menubar)

        settings_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Settings", menu=settings_menu)
        theme_menu = tk.Menu(settings_menu, tearoff=0)
        settings_menu.add_cascade(label="Theme", menu=theme_menu)

        try:
            style = ttk.Style()
            available_themes = sorted(style.theme_names())
            curated_themes = ['adapta', 'arc', 'plastik', 'radiance', 'ubuntu', 'clearlooks', 'equilux', 'itft1', 'keramik']
            
            self.theme_var = tk.StringVar(value=self.config.get('theme', 'adapta'))

            for theme in curated_themes:
                if theme in available_themes:
                    theme_menu.add_radiobutton(label=theme, variable=self.theme_var, value=theme, command=self.change_theme)
        except tk.TclError as e:
            print(f"Could not load themes: {e}")

    def change_theme(self):
        selected_theme = self.theme_var.get()
        try:
            self.master.set_theme(selected_theme)
            self.config['theme'] = selected_theme
        except tk.TclError:
            messagebox.showerror("Error", f"Failed to apply theme '{selected_theme}'.")

    def setup_ui_configs(self):
        self.previewable_text_extensions = {'.txt', '.csv', '.json', '.xml', '.yml', '.yaml', '.log', '.md', '.py', '.js', '.css', '.html', '.sh', '.ini', '.cfg', '.conf'}
        self.previewable_image_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', '.webp'}
        self.file_type_categories = {
            "所有类型": {'.*'}, "图片": self.previewable_image_extensions.union({'.svg'}),
            "文档": {'.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx', '.txt', '.md', '.rtf'},
            "视频": {'.mp4', '.mkv', '.avi', '.mov', '.wmv', '.flv'}, "音频": {'.mp3', '.wav', '.flac', '.aac', '.ogg', '.m4a'},
            "压缩包": {'.zip', '.rar', '.7z', '.tar', '.gz', '.bz2'}, "代码": self.previewable_text_extensions - {'.txt', '.log', '.csv'}
        }
        self.SIZE_UNITS = SIZE_UNITS
        self.PREVIEW_LINES = 100
        self.system_encoding = locale.getpreferredencoding(False)

    def create_widgets(self):
        self._setup_styles()
        main_paned = tk.PanedWindow(self.master, orient=tk.VERTICAL, sashrelief=tk.RAISED)
        main_paned.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        top_panel = self._create_top_panel(main_paned)
        main_paned.add(top_panel, height=170)
        bottom_panel = self._create_main_content(main_paned)
        main_paned.add(bottom_panel)
        self._create_status_bar()

    def _setup_styles(self):
        style = ttk.Style(self.master)
        style.configure("Accent.TButton", font=("", 11, "bold"))
        style.configure("TLabel", font=("", 11))
        style.configure("TButton", font=("", 11))
        style.configure("TCombobox", font=("", 11))
        style.configure("TLabelframe.Label", font=("", 11, "bold"))
        style.configure("Treeview", rowheight=25)
        style.configure("Odd.Treeview", background="#f0f0f0")

    def _create_top_panel(self, parent) -> ttk.Frame:
        top_frame = ttk.Frame(parent, padding="10")
        dir_frame = ttk.LabelFrame(top_frame, text=" 1. 扫描目录 (多个用英文逗号 , 分隔) ", padding=10)
        dir_frame.pack(fill=tk.X, side=tk.TOP, pady=(0, 10))
        self.dir_entry = ttk.Entry(dir_frame, font=("", 12)); self.dir_entry.insert(0, self.config.get('last_directory'))
        self.dir_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5), ipady=4)
        self.browse_button = ttk.Button(dir_frame, text="浏览...", command=self.browse_directory)
        self.browse_button.pack(side=tk.LEFT, ipady=4)
        self.scan_button = ttk.Button(dir_frame, text="▶️ 开始扫描", command=self.start_scan_thread, style="Accent.TButton")
        self.scan_button.pack(side=tk.LEFT, padx=(10, 0), ipady=4)

        filter_sort_frame = ttk.LabelFrame(top_frame, text=" 2. 筛选与排序 (输入后自动应用) ", padding=10)
        filter_sort_frame.pack(fill=tk.X, side=tk.TOP)
        
        ttk.Label(filter_sort_frame, text="关键词:").grid(row=0, column=0, sticky='w', padx=(0, 5), pady=2)
        self.keyword_entry = ttk.Entry(filter_sort_frame, font=("", 12))
        self.keyword_entry.grid(row=0, column=1, sticky='ew', ipady=2)
        self.keyword_entry.bind("<KeyRelease>", self._schedule_filter)
        
        self.regex_var = tk.BooleanVar(value=False)
        regex_check = ttk.Checkbutton(filter_sort_frame, text="Regex", variable=self.regex_var, command=self.apply_filters_and_sort)
        regex_check.grid(row=0, column=2, sticky='w', padx=(5,10))

        ttk.Label(filter_sort_frame, text="文件类型:").grid(row=0, column=3, sticky='w', padx=(10, 5), pady=2)
        self.file_type_var = tk.StringVar(value="所有类型")
        self.type_menu = ttk.Combobox(filter_sort_frame, textvariable=self.file_type_var, values=list(self.file_type_categories.keys()), state="readonly", font=("", 11))
        self.type_menu.grid(row=0, column=4, columnspan=2, sticky='ew')
        self.type_menu.bind("<<ComboboxSelected>>", self.apply_filters_and_sort)
        
        ttk.Label(filter_sort_frame, text="大小范围:").grid(row=1, column=0, sticky='w', padx=(0, 5), pady=5)
        self.min_size_var = tk.StringVar(); self.max_size_var = tk.StringVar()
        min_size_entry = ttk.Entry(filter_sort_frame, textvariable=self.min_size_var, width=8)
        min_size_entry.grid(row=1, column=1, sticky='ew')
        self.min_unit_var = tk.StringVar(value="MB")
        min_unit_menu = ttk.Combobox(filter_sort_frame, textvariable=self.min_unit_var, values=list(self.SIZE_UNITS.keys()), state="readonly", width=4)
        min_unit_menu.grid(row=1, column=2, sticky='w')
        
        ttk.Label(filter_sort_frame, text=" - ").grid(row=1, column=3, sticky='w', padx=(10,0))
        max_size_entry = ttk.Entry(filter_sort_frame, textvariable=self.max_size_var, width=8)
        max_size_entry.grid(row=1, column=4, sticky='ew')
        self.max_unit_var = tk.StringVar(value="GB")
        max_unit_menu = ttk.Combobox(filter_sort_frame, textvariable=self.max_unit_var, values=list(self.SIZE_UNITS.keys()), state="readonly", width=4)
        max_unit_menu.grid(row=1, column=5, sticky='w')

        for widget in [min_size_entry, max_size_entry]: widget.bind("<KeyRelease>", self._schedule_filter)
        for widget in [min_unit_menu, max_unit_menu]: widget.bind("<<ComboboxSelected>>", self.apply_filters_and_sort)
        
        ttk.Label(filter_sort_frame, text="排序方式:").grid(row=2, column=0, sticky='w', padx=(0, 5), pady=5)
        self.sort_var = tk.StringVar(value="大小 (大到小)")
        sort_options = ["大小 (大到小)", "大小 (小到大)", "文件名 (A-Z)", "文件名 (Z-A)", "修改时间 (新到旧)", "修改时间 (旧到新)"]
        self.sort_menu = ttk.Combobox(filter_sort_frame, textvariable=self.sort_var, values=sort_options, state="readonly", font=("", 11))
        self.sort_menu.grid(row=2, column=1, columnspan=5, sticky='ew')
        self.sort_menu.bind("<<ComboboxSelected>>", self.apply_filters_and_sort)
        
        filter_sort_frame.columnconfigure(1, weight=1); filter_sort_frame.columnconfigure(4, weight=1)
        self.size_filter_widgets = [min_size_entry, min_unit_menu, max_size_entry, max_unit_menu]
        
        return top_frame

    def _create_main_content(self, parent) -> tk.PanedWindow:
        bottom_paned = tk.PanedWindow(parent, orient=tk.HORIZONTAL, sashrelief=tk.RAISED)
        results_frame = ttk.Frame(bottom_paned, padding="5")
        bottom_paned.add(results_frame, width=950)
        self.notebook = ttk.Notebook(results_frame)
        self.notebook.pack(fill=tk.BOTH, expand=True)

        cols = ("文件名", "大小", "修改时间", "完整路径")
        self.tree = self.create_treeview(self.notebook, "📂 所有文件", cols)
        self.duplicate_tree = self.create_treeview(self.notebook, "📜 重复文件", cols, is_duplicate_tree=True)

        for tree in [self.tree, self.duplicate_tree]:
            placeholder_text = "请先开始扫描..." if tree == self.tree else "扫描完成后，重复文件将在此处显示"
            placeholder_id = "placeholder" if tree == self.tree else "placeholder_dupe"
            tree.insert("", "end", text=placeholder_text, iid=placeholder_id, values=("", "", "", ""), tags=("placeholder",))
            tree.tag_configure("placeholder", foreground="gray", font=("", 11, "italic"))
            tree.tag_configure("oddrow", background="#f0f0f0")

            tree.bind("<<TreeviewSelect>>", self.on_file_select)
            if sys.platform == "darwin":
                tree.bind("<Double-1>", self.open_interactive_quicklook)
                tree.bind("<space>", self.open_interactive_quicklook)

        self.duplicate_tree.bind("<Button-3>", self.show_duplicate_context_menu)
        
        right_frame = ttk.Frame(bottom_paned, padding="5")
        bottom_paned.add(right_frame)
        
        action_frame = ttk.LabelFrame(right_frame, text=" 文件操作 ", padding=5)
        action_frame.pack(fill=tk.X, pady=(0, 10))
        self.open_button = ttk.Button(action_frame, text="打开文件", command=self.open_selected_file)
        self.open_button.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=2, ipady=4)
        self.open_folder_button = ttk.Button(action_frame, text="打开所在文件夹", command=self.open_selected_file_folder)
        self.open_folder_button.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=2, ipady=4)
        
        preview_frame_text = " 文件预览 "
        if sys.platform == "darwin":
            preview_frame_text += "(双击或按空格进行交互式预览)"
        preview_frame = ttk.LabelFrame(right_frame, text=preview_frame_text, padding=5)
        preview_frame.pack(fill=tk.BOTH, expand=True)
        
        self.preview_notebook = ttk.Notebook(preview_frame)
        self.preview_notebook.pack(fill=tk.BOTH, expand=True)
        text_preview_frame = ttk.Frame(self.preview_notebook)
        image_preview_frame = ttk.Frame(self.preview_notebook)
        self.preview_notebook.add(text_preview_frame, text="文本预览")
        self.preview_notebook.add(image_preview_frame, text="图片/原生预览")
        self.preview_text = tk.Text(text_preview_frame, wrap=tk.WORD, state=tk.DISABLED, height=10, font=("Menlo", 11))
        self.preview_text.pack(fill=tk.BOTH, expand=True)
        self.image_preview_label = ttk.Label(image_preview_frame, text="选择文件进行预览", anchor='center')
        self.image_preview_label.pack(fill=tk.BOTH, expand=True)

        batch_action_frame = ttk.LabelFrame(right_frame, text=" 批量操作 ", padding="5")
        batch_action_frame.pack(fill=tk.X, pady=10)
        self.rename_button = ttk.Button(batch_action_frame, text="🔄 批量重命名选中项", command=self.open_batch_rename_dialog)
        self.rename_button.pack(fill=tk.X, expand=True, pady=2, ipady=4)
        self.delete_button = ttk.Button(batch_action_frame, text="🗑️ 将选中项移至回收站", command=self.delete_selected_files)
        self.delete_button.pack(fill=tk.X, expand=True, pady=2, ipady=4)
        self.delete_all_dupes_button = ttk.Button(batch_action_frame, text="‼️ 批量清理所有重复项", command=self.delete_all_duplicate_copies)
        self.delete_all_dupes_button.pack(fill=tk.X, expand=True, pady=2, ipady=4)
        
        return bottom_paned

    def _create_status_bar(self):
        status_frame = ttk.Frame(self.master, padding="2")
        status_frame.pack(fill=tk.X, side=tk.BOTTOM)
        self.status_label = ttk.Label(status_frame, text="欢迎使用文件管理大师！选择目录后开始扫描。", anchor=tk.W)
        self.status_label.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.progress_bar = ttk.Progressbar(status_frame, orient=tk.HORIZONTAL, length=200, mode='determinate')
        self.progress_bar.pack(side=tk.RIGHT)

    def create_treeview(self, notebook, text, columns, is_duplicate_tree=False):
        tab_frame = ttk.Frame(notebook)
        notebook.add(tab_frame, text=text)
        tree_frame = ttk.Frame(tab_frame)
        tree_frame.pack(fill=tk.BOTH, expand=True)
        show_option = "tree headings" if is_duplicate_tree else "headings"
        tree = ttk.Treeview(tree_frame, columns=columns, show=show_option, selectmode="extended")
        if is_duplicate_tree: tree.heading("#0", text="重复文件组")
        for col in columns: tree.heading(col, text=col)
        tree.column("文件名", width=280); tree.column("大小", width=100, anchor=tk.E)
        tree.column("修改时间", width=150, anchor=tk.CENTER); tree.column("完整路径", width=420)
        scrollbar = ttk.Scrollbar(tree_frame, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        return tree
    
    def open_batch_rename_dialog(self):
        selected_items = self.get_active_tree().selection()
        valid_items = [item for item in selected_items if item in self.file_data_cache]
        
        if not valid_items:
            messagebox.showwarning("No Selection", "Please select one or more files to rename.")
            return
            
        rename_dialog = BatchRenameDialog(self.master, valid_items, self.apply_filters_and_sort)

    # --- The rest of the methods for FileCleanerApp ---
    # ... (All other methods from v1.3 are included here without change) ...
    # --- Event Handlers & Preview Logic ---
    def on_file_select(self, event):
        tree = self.get_active_tree()
        selected_items = [item for item in tree.selection() if item in self.file_data_cache]
        
        if selected_items:
            total_size = sum(self.file_data_cache[item].size for item in selected_items)
            size_mb = total_size / (1024*1024)
            self.status_label.config(text=f"选中 {len(selected_items)} 个文件, 总大小: {size_mb:.2f} MB")
            
            if len(selected_items) == 1:
                self.show_embedded_preview(selected_items[0])
        elif (first_selection := self._get_selected_filepath()):
            self.show_embedded_preview(first_selection)

    def show_embedded_preview(self, filepath: str):
        self.preview_text.config(state=tk.NORMAL); self.preview_text.delete(1.0, tk.END)
        self.image_preview_label.config(image='');
        if hasattr(self.image_preview_label, 'photo'): delattr(self.image_preview_label, 'photo')
        
        ext = os.path.splitext(filepath)[1].lower()

        if ext in self.previewable_image_extensions:
            self.preview_notebook.select(1)
            self._load_preview_image(filepath)
        elif ext in self.previewable_text_extensions:
            self.preview_notebook.select(0)
            self._load_text_preview(filepath)
        elif sys.platform == "darwin":
            self.preview_notebook.select(1)
            self._load_native_preview_as_image(filepath)
        else:
            self.preview_notebook.select(0)
            self.update_text_preview(f"文件类型 '{ext}' 不支持预览。")

    def _load_native_preview_as_image(self, filepath: str):
        self.image_preview_label.config(image='', text="正在生成原生预览图...")
        threading.Thread(target=self._generate_and_load_ql_image, args=(filepath,), daemon=True).start()

    def _generate_and_load_ql_image(self, filepath: str):
        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                proc = subprocess.run(
                    ['qlmanage', '-t', '-s', '800', '-o', tmpdir, filepath],
                    capture_output=True,
                    timeout=10
                )
                
                output_files = [f for f in os.listdir(tmpdir) if f.endswith('.png')]
                if not output_files:
                    error_msg = proc.stderr.decode('utf-8', errors='ignore')
                    raise RuntimeError(f"qlmanage 未能生成预览图。\n错误: {error_msg.strip()}")

                thumbnail_path = os.path.join(tmpdir, output_files[0])

                with Image.open(thumbnail_path) as img:
                    img.thumbnail(
                        (self.image_preview_label.winfo_width() - 10, self.image_preview_label.winfo_height() - 10),
                        Image.Resampling.LANCZOS
                    )
                    photo = ImageTk.PhotoImage(img)
                    
                    if self.master.winfo_exists():
                        self.master.after_idle(lambda p=photo, fp_check=filepath: self.update_image_preview(p, fp_check))

        except (subprocess.TimeoutExpired, FileNotFoundError, RuntimeError, UnidentifiedImageError, OSError) as e:
            if self.master.winfo_exists():
                self.master.after_idle(
                    lambda err=str(e): self.update_image_preview(None, None, f"无法生成原生预览:\n{err}")
                )

    def open_interactive_quicklook(self, event=None, custom_filepath=None):
        if sys.platform != "darwin": return
        if filepath := self._get_selected_filepath(custom_filepath):
            try:
                subprocess.run(['qlmanage', '-p', filepath], check=False)
            except FileNotFoundError:
                messagebox.showerror("Quick Look 错误", "无法找到 'qlmanage' 命令。")
            except Exception as e:
                messagebox.showerror("Quick Look 未知错误", f"预览时发生未知错误: {e}")

    def start_scan_thread(self):
        if self.scan_thread and self.scan_thread.is_alive():
            self.stop_event.set(); self.scan_button.config(text="正在停止...", state=tk.DISABLED); return
        dirs_str = self.dir_entry.get().strip()
        if not dirs_str: messagebox.showwarning("输入错误", "请至少输入一个有效的扫描目录！"); return
        dirs = [d.strip() for d in dirs_str.split(',') if d.strip() and os.path.isdir(d.strip())]
        if not dirs: messagebox.showwarning("路径无效", "输入的所有目录均无效或不存在。"); return
        self._reset_scan_state(); self._set_ui_state(tk.DISABLED)
        self.scan_button.config(text="⏹️ 停止扫描"); self.status_label.config(text="扫描已启动...")
        self.stop_event.clear()
        self.scan_thread = threading.Thread(target=self._scan_and_hash_in_thread_optimized, args=(dirs, self.scan_queue, self.stop_event), daemon=True)
        self.scan_thread.start()

    def process_queue(self):
        try:
            while True:
                msg = self.scan_queue.get_nowait()
                msg_type = msg["type"]
                if msg_type == QueueMsgType.PROGRESS:
                    self.status_label.config(text=msg["message"])
                    if "total" in msg and msg["total"] > 0: self.progress_bar["value"] = (msg["current"] / msg["total"]) * 100
                elif msg_type == QueueMsgType.COMPLETED:
                    self.file_data_cache, self.duplicate_groups = msg["file_data"], msg["duplicate_groups"]
                    total_size_mb = sum(info.size for info in self.file_data_cache.values()) / (1024 * 1024)
                    status = (f"✅ 扫描完成: {len(self.file_data_cache):,} 个文件 ({total_size_mb:.2f} MB), "
                              f"{len(self.duplicate_groups):,} 组重复。")
                    self.status_label.config(text=status); self.progress_bar["value"] = 100
                    self.apply_filters_and_sort()
                    self._set_ui_state(tk.NORMAL); self.scan_button.config(text="▶️ 开始扫描")
                elif msg_type == QueueMsgType.STOPPED:
                    self.status_label.config(text="⏹️ 扫描已由用户停止。"); self.progress_bar["value"] = 0
                    self._set_ui_state(tk.NORMAL); self.scan_button.config(text="▶️ 开始扫描")
                elif msg_type == QueueMsgType.ERROR:
                    messagebox.showerror("扫描错误", msg["message"])
        except queue.Empty: pass
        finally:
            if self.master.winfo_exists(): self.master.after(100, self.process_queue)

    def _scan_and_hash_in_thread_optimized(self, directories: List[str], q: queue.Queue, stop_event: threading.Event):
        # ... (scan logic is unchanged)
        q.put({"type": QueueMsgType.PROGRESS, "message": "阶段 1/2: 正在快速收集文件列表..."})
        files_by_size: Dict[int, List[Tuple[str, float]]] = {}
        try:
            for d in directories:
                for root, _, files in os.walk(d, topdown=True):
                    if stop_event.is_set(): q.put({"type": QueueMsgType.STOPPED}); return
                    for name in files:
                        if name.startswith('.'): continue
                        filepath = os.path.join(root, name)
                        try:
                            stat = os.stat(filepath)
                            files_by_size.setdefault(stat.st_size, []).append((filepath, stat.st_mtime))
                        except OSError:
                            continue
        except OSError as e:
            q.put({"type": QueueMsgType.ERROR, "message": f"读取目录时出错: {e}"}); return

        file_data: Dict[str, FileInfo] = {}
        hashes: Dict[str, List[str]] = {}
        potential_dupes = {size: paths for size, paths in files_by_size.items() if len(paths) > 1}
        total_to_hash = sum(len(paths) for paths in potential_dupes.values())
        hashed_count = 0

        q.put({"type": QueueMsgType.PROGRESS, "message": "阶段 2/2: 正在计算哈希..."})
        for size, file_tuples in potential_dupes.items():
            if stop_event.is_set(): q.put({"type": QueueMsgType.STOPPED}); return
            for fp, mtime in file_tuples:
                hashed_count += 1
                if hashed_count % 20 == 0:
                     q.put({"type": QueueMsgType.PROGRESS, "message": f"阶段 2/2: 计算哈希 {hashed_count:,}/{total_to_hash:,}", "current": hashed_count, "total": total_to_hash})

                file_hash = self.db_manager.get_cached_hash(fp, mtime, size)
                if not file_hash:
                    file_hash = self._get_file_hash(fp, stop_event)
                    if file_hash is None: continue
                    self.db_manager.update_hash(fp, mtime, size, file_hash)
                
                file_data[fp] = FileInfo(size=size, mtime=mtime, hash=file_hash)
                hashes.setdefault(file_hash, []).append(fp)
        
        for size, file_tuples in files_by_size.items():
            if size not in potential_dupes:
                 for fp, mtime in file_tuples:
                      if stop_event.is_set(): q.put({"type": QueueMsgType.STOPPED}); return
                      file_data[fp] = FileInfo(size=size, mtime=mtime)
        
        dupes = {h: p for h, p in hashes.items() if len(p) > 1}
        q.put({"type": QueueMsgType.COMPLETED, "file_data": file_data, "duplicate_groups": dupes})

    def apply_filters_and_sort(self, event=None, rescan=False):
        if rescan:
            # A bit of a heavy-handed refresh, but safest after renaming
            self.start_scan_thread()
            return

        keyword = self.keyword_entry.get().strip()
        use_regex = self.regex_var.get()
        sort_by = self.sort_var.get()
        file_type = self.file_type_var.get()
        allowed_extensions = self.file_type_categories.get(file_type, {'.*'})
        min_bytes, max_bytes = self._parse_size_filter()

        filtered_items = []

        regex_pattern = None
        if use_regex and keyword:
            try:
                regex_pattern = re.compile(keyword, re.IGNORECASE)
            except re.error as e:
                self.status_label.config(text=f"Invalid Regex: {e}")
                return

        for fp, info in self.file_data_cache.items():
            if keyword:
                filename = os.path.basename(fp)
                if use_regex:
                    if not regex_pattern or not regex_pattern.search(filename):
                        continue
                else:
                    if keyword.lower() not in filename.lower():
                        continue
            
            if ".*" not in allowed_extensions and os.path.splitext(fp)[1].lower() not in allowed_extensions: continue
            if min_bytes is not None and info.size < min_bytes: continue
            if max_bytes is not None and info.size > max_bytes: continue
            filtered_items.append((fp, info))

        sort_key_map: Dict[str, Tuple[Callable, bool]] = {
            "大小 (大到小)": (lambda item: item[1].size, True), "大小 (小到大)": (lambda item: item[1].size, False),
            "文件名 (A-Z)": (lambda item: os.path.basename(item[0]).lower(), False), "文件名 (Z-A)": (lambda item: os.path.basename(item[0]).lower(), True),
            "修改时间 (新到旧)": (lambda item: item[1].mtime, True), "修改时间 (旧到新)": (lambda item: item[1].mtime, False),
        }
        sort_func, reverse = sort_key_map.get(sort_by, (lambda item: item[1].size, True))
        filtered_items.sort(key=sort_func, reverse=reverse)

        self.current_displayed_files = [fp for fp, _ in filtered_items]
        self._update_all_files_display()
        self._update_duplicate_files_display()
        
        if self.current_displayed_files:
            total_size_mb = sum(self.file_data_cache[fp].size for fp in self.current_displayed_files) / (1024*1024)
            self.status_label.config(text=f"筛选结果: {len(self.current_displayed_files):,} 个文件 ({total_size_mb:.2f} MB)")

    def _update_all_files_display(self):
        self.tree.delete(*self.tree.get_children())
        if not self.current_displayed_files:
            self.tree.insert("", "end", text="没有符合筛选条件的文件", iid="placeholder", tags=("placeholder",)); return
        for fp in self.current_displayed_files:
            self.tree.insert("", "end", values=self._get_file_details_for_display(fp), iid=fp)

    def _update_duplicate_files_display(self):
        self.duplicate_tree.delete(*self.duplicate_tree.get_children())
        displayed_set = set(self.current_displayed_files)
        if not displayed_set:
            self.duplicate_tree.insert("", "end", text="没有符合条件的重复文件", iid="placeholder_dupe", tags=("placeholder",)); return
            
        temp_groups = {h: [p for p in paths if p in displayed_set] for h, paths in self.duplicate_groups.items()}
        valid_groups = {h: p for h, p in temp_groups.items() if len(p) > 1}
        sorted_groups = sorted(valid_groups.items(), 
                               key=lambda item: self.file_data_cache.get(item[1][0]).size * len(item[1]) if self.file_data_cache.get(item[1][0]) else 0, 
                               reverse=True)
        
        if not sorted_groups:
            self.duplicate_tree.insert("", "end", text="没有符合条件的重复文件", iid="placeholder_dupe", tags=("placeholder",)); return

        for i, (h, paths) in enumerate(sorted_groups):
            first_file_info = self.file_data_cache.get(paths[0])
            if not first_file_info: continue
            total_size_mb = first_file_info.size * len(paths) / (1024 * 1024)
            group_text = f"哈希: {h[:8]}... ({len(paths)} 个文件, 共 {total_size_mb:.2f} MB)"
            tags = ("oddrow",) if i % 2 else ()
            group_id = self.duplicate_tree.insert("", "end", text=group_text, open=True, tags=tags)
            for fp in paths: self.duplicate_tree.insert(group_id, "end", values=self._get_file_details_for_display(fp), iid=fp, tags=tags)

    def on_closing(self):
        if self.scan_thread and self.scan_thread.is_alive():
            self.stop_event.set(); self.scan_thread.join(timeout=0.2)
        self.config['last_directory'] = self.dir_entry.get()
        self.config['window_geometry'] = self.master.geometry()
        save_config(self.config)
        self.db_manager.close()
        self.master.destroy()
    
    def _parse_size_filter(self) -> Tuple[Optional[int], Optional[int]]:
        # ... (unchanged)
        min_bytes, max_bytes = None, None
        try:
            if min_val_str := self.min_size_var.get().strip():
                min_bytes = int(float(min_val_str) * self.SIZE_UNITS[self.min_unit_var.get()])
        except ValueError: pass
        try:
            if max_val_str := self.max_size_var.get().strip():
                max_bytes = int(float(max_val_str) * self.SIZE_UNITS[self.max_unit_var.get()])
        except ValueError: pass
        return min_bytes, max_bytes

    def _get_file_details_for_display(self, fp: str) -> Tuple:
        # ... (unchanged)
        info = self.file_data_cache.get(fp)
        if not info: return (os.path.basename(fp), "N/A", "N/A", fp)
        size_mb = info.size / (1024*1024)
        size_str = f"{size_mb:.3f} MB" if size_mb >= 0.01 else f"{info.size / 1024:.2f} KB"
        mod_time = datetime.datetime.fromtimestamp(info.mtime).strftime('%Y-%m-%d %H:%M:%S')
        return (os.path.basename(fp), size_str, mod_time, fp)

    @staticmethod
    def _get_file_hash(filepath: str, stop_event: threading.Event, chunk_size=8192) -> Optional[str]:
        # ... (unchanged)
        h = hashlib.md5()
        try:
            with open(filepath, "rb") as f:
                while chunk := f.read(chunk_size):
                    if stop_event.is_set(): return None
                    h.update(chunk)
            return h.hexdigest()
        except (IOError, OSError): return None

    def _load_text_preview(self, filepath: str):
        self.update_text_preview("正在加载预览..."); threading.Thread(target=self._read_text_file, args=(filepath,), daemon=True).start()

    def _read_text_file(self, filepath: str):
        # ... (unchanged)
        content, error = "", None
        try:
            with open(filepath, 'r', encoding='utf-8') as f: content = "".join([next(f) for _ in range(self.PREVIEW_LINES)])
        except UnicodeDecodeError:
            try:
                with open(filepath, 'r', encoding=self.system_encoding) as f: content = "".join([next(f) for _ in range(self.PREVIEW_LINES)])
            except Exception as e: error = f"尝试用系统默认编码({self.system_encoding})读取失败: {e}"
        except Exception as e: error = e
        if not self.master.winfo_exists(): return
        if error: self.master.after_idle(lambda err=error: self.update_text_preview(f"无法预览文件内容:\n{err}"))
        else:
            if len(content.splitlines()) >= self.PREVIEW_LINES: content += f"\n\n--- (仅显示前 {self.PREVIEW_LINES} 行) ---"
            self.master.after_idle(lambda c=content: self.update_text_preview(c))

    def _load_preview_image(self, filepath: str):
        self.image_preview_label.config(image='', text="正在加载图片...")
        threading.Thread(target=self._read_image_file, args=(filepath,), daemon=True).start()

    def _read_image_file(self, filepath: str):
        # ... (unchanged)
        try:
            with Image.open(filepath) as img:
                img.thumbnail((self.image_preview_label.winfo_width()-10, self.image_preview_label.winfo_height()-10), Image.Resampling.LANCZOS); photo = ImageTk.PhotoImage(img)
                if self.master.winfo_exists(): self.master.after_idle(lambda p=photo, fp_check=filepath: self.update_image_preview(p, fp_check))
        except (UnidentifiedImageError, OSError) as e:
            if self.master.winfo_exists(): self.master.after_idle(lambda err=e: self.update_image_preview(None, None, f"无法预览图片:\n{err}"))

    def update_text_preview(self, content):
        self.preview_text.config(state=tk.NORMAL); self.preview_text.delete(1.0, tk.END)
        self.preview_text.insert(tk.END, content); self.preview_text.config(state=tk.DISABLED)

    def update_image_preview(self, photo, filepath_when_loaded=None, error_text=None):
        current_selection = self._get_selected_filepath()
        if filepath_when_loaded and current_selection != filepath_when_loaded: return
        if photo:
            self.image_preview_label.config(image=photo, text="")
            self.image_preview_label.photo = photo
        else:
            self.image_preview_label.config(image='', text=error_text or "预览失败")
            if hasattr(self.image_preview_label, 'photo'): delattr(self.image_preview_label, 'photo')
            
    def show_duplicate_context_menu(self, event):
        # ... (unchanged)
        item_id = self.duplicate_tree.identify_row(event.y)
        if not item_id or not self.duplicate_tree.parent(item_id): return
        self.duplicate_tree.selection_set(item_id)
        
        menu = tk.Menu(self.master, tearoff=0)
        menu.add_command(label="保留此文件，清理其他副本", command=lambda: self.keep_one_delete_others(item_id))
        menu.add_separator()
        if sys.platform == "darwin":
            menu.add_command(label="交互式预览 (Quick Look)", command=lambda: self.open_interactive_quicklook(custom_filepath=item_id))
        menu.add_command(label="打开文件", command=lambda: self.open_selected_file(custom_filepath=item_id))
        menu.add_command(label="打开所在文件夹", command=lambda: self.open_selected_file_folder(custom_filepath=item_id))
        try: menu.tk_popup(event.x_root, event.y_root)
        except tk.TclError: pass

    def delete_selected_files(self):
        # ... (unchanged)
        tree = self.get_active_tree(); selected_items = tree.selection()
        if not selected_items: messagebox.showinfo("提示", "请选择要删除的文件！"); return
        to_delete = [item for item in selected_items if item in self.file_data_cache]
        if not to_delete: messagebox.showinfo("提示", "选中的项目无效或为组标题。"); return
        if messagebox.askyesno("确认操作", f"您确定要将这 {len(to_delete)} 个文件移动到回收站吗？"):
            deleted_count = 0
            for fp in to_delete:
                if self._move_file_to_trash_safely(fp):
                    self._remove_file_from_app_state(fp)
                    deleted_count += 1
            self.apply_filters_and_sort()
            messagebox.showinfo("操作完成", f"已成功将 {deleted_count} 个文件移动到回收站。")

    def keep_one_delete_others(self, file_to_keep: str):
        # ... (unchanged)
        file_hash = self.file_data_cache.get(file_to_keep, FileInfo(0,0,None)).hash
        if not file_hash or file_hash not in self.duplicate_groups: messagebox.showinfo("提示", "该文件不属于任何已识别的重复组。"); return
        to_delete = [p for p in self.duplicate_groups[file_hash] if p != file_to_keep and p in self.file_data_cache]
        if messagebox.askyesno("确认操作", f"保留 '{os.path.basename(file_to_keep)}' 并将其余 {len(to_delete)} 个副本移到回收站?"):
            deleted_count = 0
            for fp in to_delete:
                if self._move_file_to_trash_safely(fp):
                    self._remove_file_from_app_state(fp)
                    deleted_count += 1
            self.apply_filters_and_sort()
            messagebox.showinfo("操作完成", f"已成功将 {deleted_count} 个副本移到回收站。")
    
    def delete_all_duplicate_copies(self):
        # ... (unchanged)
        to_delete_count = sum(len(p) - 1 for p in self.duplicate_groups.values() if len(p) > 1)
        if to_delete_count == 0: messagebox.showinfo("提示", "没有多余的重复文件副本可供删除。"); return
        if messagebox.askyesno("确认批量操作", f"确定要将所有重复副本(每组保留修改时间最新的一个)移到回收站吗？\n总计将移动 {to_delete_count} 个文件。"):
            deleted_count = 0
            for filepaths in list(self.duplicate_groups.values()):
                if len(filepaths) > 1:
                    valid_paths = [p for p in filepaths if p in self.file_data_cache]
                    sorted_paths = sorted(valid_paths, key=lambda p: self.file_data_cache[p].mtime, reverse=True)
                    for fp in sorted_paths[1:]:
                        if self._move_file_to_trash_safely(fp):
                            self._remove_file_from_app_state(fp)
                            deleted_count += 1
            self.apply_filters_and_sort()
            messagebox.showinfo("批量清理完成", f"已成功将 {deleted_count} 个重复副本移到回收站。")

    def open_selected_file(self, custom_filepath=None):
        if fp := self._get_selected_filepath(custom_filepath):
            try:
                if sys.platform == "win32": os.startfile(fp)
                elif sys.platform == "darwin": subprocess.run(['open', fp], check=True)
                else: subprocess.run(['xdg-open', fp], check=True)
            except Exception as e: messagebox.showerror("打开失败", f"无法打开文件: {e}")

    def open_selected_file_folder(self, custom_filepath=None):
        if fp := self._get_selected_filepath(custom_filepath):
            try:
                if sys.platform == 'win32': subprocess.run(['explorer', '/select,', fp], check=True)
                elif sys.platform == 'darwin': subprocess.run(['open', '-R', fp], check=True)
                else: subprocess.run(['xdg-open', os.path.dirname(fp)], check=True)
            except Exception as e: messagebox.showerror("打开失败", f"无法打开文件夹: {e}")

    def browse_directory(self):
        directory = filedialog.askdirectory(initialdir=self.dir_entry.get() or os.path.expanduser('~'))
        if directory: self.dir_entry.delete(0, tk.END); self.dir_entry.insert(0, directory)
    
    def get_active_tree(self):
        try: return self.tree if self.notebook.tab(self.notebook.select(), "text") == "📂 所有文件" else self.duplicate_tree
        except tk.TclError: return self.tree

    def _get_selected_filepath(self, custom_filepath=None) -> Optional[str]:
        if custom_filepath: return custom_filepath
        tree = self.get_active_tree()
        selection = tree.selection()
        if not selection or "placeholder" in tree.item(selection[0], "tags"): return None
        return selection[0]

    def _schedule_filter(self, event=None):
        if self._after_id:
            self.master.after_cancel(self._after_id)
        self._after_id = self.master.after(500, self.apply_filters_and_sort)

    def _set_ui_state(self, state):
        widgets = [self.browse_button, self.keyword_entry, self.sort_menu, self.type_menu, self.rename_button, self.delete_button, self.delete_all_dupes_button]
        widgets.extend(self.size_filter_widgets)
        for widget in widgets:
            if widget: widget.config(state=state)
        if state == tk.NORMAL: self.scan_button.config(state=state)

    def _reset_scan_state(self):
        self.file_data_cache.clear(); self.duplicate_groups.clear(); self.current_displayed_files.clear()
        self.progress_bar["value"] = 0
        for tree in [self.tree, self.duplicate_tree]:
            tree.delete(*tree.get_children())
            placeholder_text = "请先开始扫描..." if tree == self.tree else "扫描完成后，重复文件将在此处显示"
            tree.insert("", "end", text=placeholder_text, iid="placeholder" if tree == self.tree else "placeholder_dupe", tags=("placeholder",))
    
    def _remove_file_from_app_state(self, filepath: str):
        if filepath in self.file_data_cache:
            info = self.file_data_cache.pop(filepath)
            if info.hash and info.hash in self.duplicate_groups:
                group = self.duplicate_groups[info.hash]
                if filepath in group: group.remove(filepath)
                if len(group) < 2: self.duplicate_groups.pop(info.hash)

    @staticmethod
    def _move_file_to_trash_safely(fp: str) -> bool:
        try: send2trash.send2trash(fp); return True
        except Exception as e: messagebox.showwarning("操作失败", f"无法将文件移到回收站:\n{fp}\n\n错误: {e}"); return False

# =============================================================================
# 5. 应用入口点
# =============================================================================
if __name__ == "__main__":
    try:
        if sys.platform == "win32": from ctypes import windll; windll.shcore.SetProcessDpiAwareness(1)
        root = ThemedTk(toplevel=True, themebg=True)
        app = FileCleanerApp(root)
        root.mainloop()
    except Exception as e:
        import traceback
        messagebox.showerror("严重错误", f"应用程序遇到严重错误并需要关闭。\n\n错误信息: {e}\n\n{traceback.format_exc()}")