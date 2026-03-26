import os
import sys
import time
import json
import psutil
import requests
import subprocess
import threading
import shutil
import zipfile
from datetime import datetime, timedelta
from tkinter import *
from tkinter import ttk, messagebox, filedialog
import winreg
import socket
from urllib.parse import urlparse
import schedule  # 导入定时任务库

# 版本更新相关配置
LOCAL_VERSION = "v0.2.1"
REMOTE_VERSION_URL = "http://nas.sxtvip.top:5050/version.json"
REMOTE_CHANGELOG_URL = "http://nas.sxtvip.top:5050/changelog.json"
REMOTE_PACKAGE_URL = "http://nas.sxtvip.top:5050/幸福工厂服务器管理器.zip"
TEMP_DOWNLOAD_DIR = "temp_update"
UPDATE_ZIP_NAME = "update_package.zip"
STEAMCMD_DOWNLOAD_URL = "https://steamcdn-a.akamaihd.net/client/installer/steamcmd.zip"
LOCAL_HISTORY_FILE = "update_history.txt"

class SatisfactoryServerController:
    def __init__(self):
        self.config_file = "server_config.json"
        self.load_config()
        self.server_process = None
        self.server_pid = None
        self.monitoring = False
        self.widgets_to_update = []
        self.cpu_usage = 0
        self.memory_usage = 0
        self.disk_read_speed = 0
        self.disk_write_speed = 0
        self.ping_value = 0
        self.player_count = 0
        self.last_disk_stats = None
        self.backup_timer_active = False
        self.next_backup_time = None
        self.backup_thread_running = False
        self.action_buttons = {}
        self.latest_changelog = ""
        self.pending_update_version = ""
        # 代理服务器配置
        self.proxy_enabled = self.config.get("proxy_enabled", False)
        self.proxy_type = self.config.get("proxy_type", "HTTP")
        self.proxy_host = self.config.get("proxy_host", "")
        self.proxy_port = self.config.get("proxy_port", "")
        self.proxy_username = self.config.get("proxy_username", "")
        self.proxy_password = self.config.get("proxy_password", "")
        
        # 定时任务配置 - 修改为支持自定义星期
        self.schedule_enabled = self.config.get("schedule_enabled", False)
        self.custom_schedule_days = self.config.get("custom_schedule_days", {
            "monday": {"start": "17:00", "end": "02:00"},
            "tuesday": {"start": "17:00", "end": "02:00"},
            "wednesday": {"start": "17:00", "end": "02:00"},
            "thursday": {"start": "17:00", "end": "02:00"},
            "friday": {"start": "17:00", "end": "02:00"},
            "saturday": {"start": "00:00", "end": "23:59"},
            "sunday": {"start": "00:00", "end": "23:59"}
        })
        
        # 初始化定时任务调度器
        self.scheduler_thread = None
        self.scheduler_running = False
        
        self.setup_gui()
        self.load_local_history()
        
        # 启动定时任务调度器
        self.start_scheduler()
        
        # 启动备份管理器
        self.start_backup_manager()

    def load_config(self):
        if os.path.exists(self.config_file):
            with open(self.config_file, 'r') as f:
                self.config = json.load(f)
        else:
            self.config = {
                "install_path": "",
                "max_players": 4,
                "auto_restart": True,
                "auto_start": False,
                "branch": "public",
                "game_port": 7777,
                "beacon_port": 8888,
                "autosave_count": 5,
                "backup_interval": 30,
                "backup_retain": 10,
                "enable_auto_backup": True,
                "monitor_host": "localhost",
                "backup_locations": [
                    {"type": "local", "path": "", "enabled": True}
                ],
                "proxy_enabled": False,
                "proxy_type": "HTTP",
                "proxy_host": "",
                "proxy_port": "",
                "proxy_username": "",
                "proxy_password": "",
                # 定时任务配置 - 修改为支持自定义星期
                "schedule_enabled": False,
                "custom_schedule_days": {
                    "monday": {"start": "17:00", "end": "02:00"},
                    "tuesday": {"start": "17:00", "end": "02:00"},
                    "wednesday": {"start": "17:00", "end": "02:00"},
                    "thursday": {"start": "17:00", "end": "02:00"},
                    "friday": {"start": "17:00", "end": "02:00"},
                    "saturday": {"start": "00:00", "end": "23:59"},
                    "sunday": {"start": "00:00", "end": "23:59"}
                },
                # 修正：添加存档路径配置
                "save_game_path": os.path.join(os.getenv('LOCALAPPDATA'), "FactoryGame", "Saved", "SaveGames")
            }
            self.save_config()

    def save_config(self):
        with open(self.config_file, 'w') as f:
            json.dump(self.config, f, indent=4)

    def load_local_history(self):
        if os.path.exists(LOCAL_HISTORY_FILE):
            try:
                with open(LOCAL_HISTORY_FILE, 'r', encoding='utf-8') as f:
                    content = f.read()
                lines = content.split('\n')
                if len(lines) > 2:
                    self.log_message("📜 检测到本地更新历史")
            except:
                pass

    def save_update_log(self, version, log_content):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        entry = f"=== 版本 {version} 更新于 {timestamp} ===\n{log_content}\n\n"
        try:
            with open(LOCAL_HISTORY_FILE, 'a', encoding='utf-8') as f:
                f.write(entry)
        except Exception as e:
            self.log_message(f"保存更新日志失败：{e}")

    def start_backup_manager(self):
        """启动备份管理器"""
        def backup_worker():
            while self.backup_thread_running:
                if self.config.get("enable_auto_backup", True):
                    current_time = datetime.now()
                    backup_interval = self.config.get("backup_interval", 30) * 60  # 转换为秒
                    
                    if self.next_backup_time is None:
                        self.next_backup_time = current_time + timedelta(minutes=self.config.get("backup_interval", 30))
                    
                    if current_time >= self.next_backup_time:
                        self.perform_backup()
                        self.next_backup_time = current_time + timedelta(minutes=self.config.get("backup_interval", 30))
                        
                        # 更新下次备份时间显示
                        if hasattr(self, 'next_backup_label'):
                            self.root.after(0, lambda: self.next_backup_label.config(text=self.next_backup_time.strftime("%Y-%m-%d %H:%M")))
                
                time.sleep(10)  # 每10秒检查一次
                
        self.backup_thread_running = True
        backup_thread = threading.Thread(target=backup_worker, daemon=True)
        backup_thread.start()

    def perform_backup(self):
        """执行备份操作"""
        try:
            root_path = self.config.get("install_path", "")
            if not root_path:
                self.log_message("❌ 备份失败：未设置安装路径")
                return
            
            server_path = os.path.join(root_path, "server")
            if not os.path.exists(server_path):
                self.log_message("❌ 备份失败：服务器路径不存在")
                return
            
            # 创建备份文件名
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_name = f"satisfactory_backup_{timestamp}"
            
            # 获取备份位置
            backup_locations = self.config.get("backup_locations", [{"type": "local", "path": "", "enabled": True}])
            
            for location in backup_locations:
                if not location.get("enabled", True):
                    continue
                    
                if location["type"] == "local":
                    local_path = location.get("path", "")
                    if not local_path:
                        self.log_message("⚠️ 跳过空的本地备份路径")
                        continue
                        
                    # 创建备份目录
                    backup_dir = os.path.join(local_path, backup_name)
                    if not os.path.exists(backup_dir):
                        os.makedirs(backup_dir)
                    
                    # 执行备份
                    self.log_message(f"📦 开始备份到: {backup_dir}")
                    
                    # 备份服务器存档目录（从配置中获取正确的路径）
                    save_games_path = self.config.get("save_game_path", os.path.join(os.getenv('LOCALAPPDATA'), "FactoryGame", "Saved", "SaveGames"))
                    if os.path.exists(save_games_path):
                        backup_save_path = os.path.join(backup_dir, "SaveGames")
                        shutil.copytree(save_games_path, backup_save_path)
                        self.log_message(f"✅ 存档备份完成: {backup_save_path}")
                    else:
                        self.log_message(f"⚠️ 存档路径不存在: {save_games_path}")
                    
                    # 备份服务器配置文件
                    server_config_path = os.path.join(server_path, "FactoryGame", "Saved", "Config")
                    if os.path.exists(server_config_path):
                        backup_config_path = os.path.join(backup_dir, "Config")
                        shutil.copytree(server_config_path, backup_config_path)
                        self.log_message(f"✅ 服务器配置备份完成: {backup_config_path}")
                    
                    # 清理旧备份
                    self.cleanup_old_backups(local_path)
                    
                elif location["type"] in ["network", "webdav", "ftp", "sftp"]:
                    self.log_message(f"⚠️ {location['type']} 类型的备份尚未实现")
            
            self.log_message("✅ 备份操作完成")
            
        except Exception as e:
            self.log_message(f"❌ 备份失败: {str(e)}")

    def cleanup_old_backups(self, backup_root_dir):
        """清理旧备份"""
        try:
            backup_dirs = []
            for item in os.listdir(backup_root_dir):
                item_path = os.path.join(backup_root_dir, item)
                if os.path.isdir(item_path) and item.startswith("satisfactory_backup_"):
                    backup_dirs.append((item_path, os.path.getctime(item_path)))
            
            # 按创建时间排序（最新的在前）
            backup_dirs.sort(key=lambda x: x[1], reverse=True)
            
            # 保留最新的N个备份
            retain_count = self.config.get("backup_retain", 10)
            if len(backup_dirs) > retain_count:
                for old_backup in backup_dirs[retain_count:]:
                    try:
                        shutil.rmtree(old_backup[0])
                        self.log_message(f"🗑️ 已删除旧备份: {old_backup[0]}")
                    except Exception as e:
                        self.log_message(f"❌ 删除旧备份失败: {old_backup[0]}, 错误: {str(e)}")
                        
        except Exception as e:
            self.log_message(f"❌ 清理旧备份失败: {str(e)}")

    def open_save_directory(self):
        """打开存档目录"""
        save_path = self.config.get("save_game_path", os.path.join(os.getenv('LOCALAPPDATA'), "FactoryGame", "Saved", "SaveGames"))
        
        if os.path.exists(save_path):
            try:
                os.startfile(save_path)
                self.log_message(f"📁 已打开存档目录: {save_path}")
            except Exception as e:
                self.log_message(f"❌ 打开存档目录失败: {str(e)}")
                messagebox.showerror("错误", f"无法打开存档目录: {save_path}\n错误: {str(e)}")
        else:
            # 如果路径不存在，尝试创建
            try:
                os.makedirs(save_path, exist_ok=True)
                os.startfile(save_path)
                self.log_message(f"📁 已创建并打开存档目录: {save_path}")
            except Exception as e:
                self.log_message(f"❌ 创建存档目录失败: {str(e)}")
                messagebox.showerror("错误", f"无法创建存档目录: {save_path}\n错误: {str(e)}")

    def setup_gui(self):
        self.root = Tk()
        self.root.title(f"幸福工厂服务端控制器 - 版本 {LOCAL_VERSION}")

        # 设置窗口大小
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        self.root.geometry(f"{screen_width-100}x{screen_height-100}")

        # 创建主框架
        main_frame = Frame(self.root, bg="#FFFFFF")
        main_frame.pack(fill=BOTH, expand=True, padx=10, pady=5)

        # 顶部工具栏
        top_frame = Frame(main_frame, bg="#F0F0F0")
        top_frame.pack(fill=X, padx=10, pady=5)

        version_frame = Frame(top_frame, bg="#F0F0F0")
        version_frame.pack(side=LEFT)

        version_label = Label(version_frame, text=f"当前版本：{LOCAL_VERSION}",
                              bg="#FFFFFF",
                              fg="#000000",
                              font=("Arial", 9))
        version_label.pack(side=LEFT)

        self.remote_version_label = Label(version_frame, text="",
                                          bg="#FFFFFF",
                                          fg="#000000",
                                          font=("Arial", 9))
        self.remote_version_label.pack(side=LEFT, padx=(10, 5))

        check_update_btn = Button(version_frame, text="检查更新", command=self.check_controller_update,
                                  bg="#E0E0E0",
                                  fg="#000000",
                                  font=("Arial", 9))
        check_update_btn.pack(side=LEFT, padx=2)
        self.action_buttons['check_update'] = check_update_btn

        history_btn = Button(version_frame, text="更新历史", command=self.show_local_history,
                             bg="#E0E0E0",
                             fg="#000000",
                             font=("Arial", 9))
        history_btn.pack(side=LEFT, padx=2)

        # 主内容区
        content_frame = Frame(main_frame, bg="#FFFFFF")
        content_frame.pack(fill=BOTH, expand=True, pady=5)

        # --- 左侧监控面板 ---
        left_panel = Frame(content_frame, bg="#FFFFFF", width=250)
        left_panel.pack(side=LEFT, fill=Y, padx=(0, 5))
        left_panel.pack_propagate(False)

        left_title = Label(left_panel, text="📊 状态监控",
                           bg="#FFFFFF",
                           fg="#000000",
                           font=("Arial", 10, "bold"), pady=5)
        left_title.pack(fill=X)

        self.status_labels = {}
        metrics_data = [
            ("cpu", "CPU", "0%", "#2196F3"),
            ("mem", "内存", "0%", "#9C27B0"),
            ("disk_read", "读取", "0 MB/s", "#4CAF50"),
            ("disk_write", "写入", "0 MB/s", "#4CAF50"),
            ("ping", "延迟", "0 ms", "#FF9800"),
            ("player", "玩家", "0/4", "#607D8B"),
            ("port", "端口", "关闭", "#607D8B")
        ]
        for i, (key, label_text, default_val, color) in enumerate(metrics_data):
            card_frame = Frame(left_panel, bg="#F0F0F0",
                               relief=RAISED, borderwidth=1)
            card_frame.pack(fill=X, padx=5, pady=2, ipady=5)

            lbl_title = Label(card_frame, text=label_text,
                              bg="#FFFFFF",
                              fg="#000000",
                              font=("Arial", 8, "bold"))
            lbl_title.pack(pady=(2, 0))

            val_lbl = Label(card_frame, text=default_val,
                            bg="#FFFFFF",
                            fg=color, font=("Arial", 11, "bold"))
            val_lbl.pack(pady=(2, 4))

            self.status_labels[key] = val_lbl

        backup_status_frame = LabelFrame(left_panel, text="自动备份",
                                         bg="#F0F0F0",
                                         fg="#000000",
                                         font=("Arial", 9, "bold"))
        backup_status_frame.pack(fill=X, padx=5, pady=10)

        Label(backup_status_frame, text="下次备份:",
              bg="#FFFFFF",
              fg="#000000",
              font=("Arial", 9)).pack(anchor=W, padx=10, pady=2)
        self.next_backup_label = Label(backup_status_frame, text="未计划",
                                       bg="#FFFFFF",
                                       fg="#FF9800", font=("Arial", 10, "bold"))
        self.next_backup_label.pack(anchor=W, padx=10, pady=(0, 8))

        # 定时任务状态
        schedule_status_frame = LabelFrame(left_panel, text="定时任务",
                                           bg="#F0F0F0",
                                           fg="#000000",
                                           font=("Arial", 9, "bold"))
        schedule_status_frame.pack(fill=X, padx=5, pady=10)

        Label(schedule_status_frame, text="状态:",
              bg="#FFFFFF",
              fg="#000000",
              font=("Arial", 9)).pack(anchor=W, padx=10, pady=2)
        self.schedule_status_label = Label(schedule_status_frame, text="已禁用",
                                           bg="#FFFFFF",
                                           fg="#FF9800", font=("Arial", 10, "bold"))
        self.schedule_status_label.pack(anchor=W, padx=10, pady=(0, 8))

        # --- 中间控制和配置区域 ---
        middle_panel = Frame(content_frame, bg="#FFFFFF")
        middle_panel.pack(side=LEFT, fill=BOTH, expand=True, padx=(0, 5))

        # 创建主画布和滚动条
        self.canvas = Canvas(middle_panel, bg="#FFFFFF", highlightthickness=0)
        self.scrollbar = Scrollbar(middle_panel, orient="vertical", command=self.canvas.yview)

        # 创建滚动框架
        self.scrollable_frame = Frame(self.canvas, bg="#FFFFFF")

        # 将滚动框架绑定到画布
        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        )

        # 将滚动框架添加到画布
        self.canvas_window = self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        self.canvas.configure(yscrollcommand=self.scrollbar.set)

        # 绑定鼠标滚轮事件
        self.canvas.bind_all("<MouseWheel>", self._on_global_mousewheel, add='+')

        # 当画布大小改变时调整滚动框架宽度
        def _configure_canvas(event):
            canvas_width = event.width
            self.canvas.itemconfig(self.canvas_window, width=canvas_width)
        self.canvas.bind("<Configure>", _configure_canvas)

        # 布局画布和滚动条
        self.canvas.pack(side="left", fill="both", expand=True)
        self.scrollbar.pack(side="right", fill="y")

        # 设置主要内容
        self.setup_main_tab(self.scrollable_frame)

        # --- 右侧日志区域 ---
        right_panel = Frame(content_frame, bg="#FFFFFF")
        right_panel.pack(side=RIGHT, fill=Y, padx=(0, 0), expand=False)

        log_frame = LabelFrame(right_panel, text="📝 实时日志",
                               bg="#F0F0F0",
                               fg="#000000",
                               font=("Arial", 10, "bold"))
        log_frame.pack(fill=BOTH, expand=True, padx=5, pady=5)

        # 日志文本区域
        self.status_text = Text(log_frame, height=20,
                                bg="#FFFFFF",
                                fg="#000000",
                                font=("Consolas", 9), wrap=NONE)
        self.status_text.pack(fill=BOTH, expand=True, padx=5, pady=5)

        # 滚动条
        scrollbar_y = Scrollbar(log_frame, orient=VERTICAL, command=self.status_text.yview)
        scrollbar_y.pack(side=RIGHT, fill=Y)
        self.status_text.config(yscrollcommand=scrollbar_y.set)

        scrollbar_x = Scrollbar(log_frame, orient=HORIZONTAL, command=self.status_text.xview)
        scrollbar_x.pack(side=BOTTOM, fill=X)
        self.status_text.config(xscrollcommand=scrollbar_x.set)

        # 为日志文本框绑定滚轮事件，用于其自身的滚动
        self.status_text.bind("<MouseWheel>", self._on_log_text_mousewheel)
        # 确保日志文本框可以接收键盘事件（包括滚轮事件），以便拦截
        self.status_text.bind("<FocusIn>", lambda e: self.status_text.focus_set())

        # --- 底部状态栏 ---
        footer_frame = Frame(self.root, bg="#F0F0F0")
        footer_frame.pack(fill=X, pady=(5, 0))

        separator = ttk.Separator(footer_frame, orient='horizontal')
        separator.pack(fill=X, pady=(0, 5))

        author_text = f"作者：冰霜蘑菇 & 千问 AI | QQ 群：264127585 (点击复制)"
        self.author_label = Label(footer_frame, text=author_text,
                                  bg="#F0F0F0",
                                  fg="#555555",
                                  font=("Microsoft YaHei", 9), cursor="hand2")
        self.author_label.pack(pady=3)
        self.author_label.bind("<Button-1>", self.copy_qq_group)
        self.author_label.bind("<Enter>", lambda e: self.author_label.config(fg="#0078D7"))

        self.monitor_thread = threading.Thread(target=self.monitor_server, daemon=True)
        self.monitor_thread.start()

        self.status_update_thread = threading.Thread(target=self.update_status_display, daemon=True)
        self.status_update_thread.start()

        self.set_auto_start()
        
        # 【新增】启动后延迟1秒自动检查更新
        self.root.after(1000, self.check_controller_update)

    def _on_global_mousewheel(self, event):
        """处理主Canvas的滚动，但仅当焦点不在日志Text组件上时"""
        focused_widget = self.root.focus_get()
        if focused_widget != self.status_text:
            if self.canvas.winfo_viewable():
                self.canvas.yview_scroll(int(-1*(event.delta/120)), "units")

    def _on_log_text_mousewheel(self, event):
        """处理日志Text组件的滚动，阻止事件冒泡到主Canvas"""
        self.status_text.yview_scroll(int(-1*(event.delta/120)), "units")
        return "break" # 阻止事件继续传递

    def setup_main_tab(self, parent_frame):
        main_container = Frame(parent_frame, bg="#FFFFFF")
        main_container.pack(fill='x', padx=10, pady=10)

        # 1. 控制按钮区域
        control_frame = LabelFrame(main_container, text="🚀 服务器控制",
                                   bg="#F0F0F0",
                                   fg="#000000",
                                   font=("Arial", 10, "bold"))
        control_frame.pack(fill='x', pady=8)

        btn_frame = Frame(control_frame, bg="#F0F0F0")
        btn_frame.pack(fill='x', pady=8, padx=10)

        # 主控制按钮
        self.start_btn = Button(btn_frame, text="▶ 启动", command=self.start_server,
                                bg="#4CAF50", fg="white", font=("Arial", 10, "bold"), width=10)
        self.start_btn.pack(side=LEFT, padx=5)

        self.stop_btn = Button(btn_frame, text="⏹ 停止", command=self.stop_server, state=DISABLED,
                               bg="#F44336", fg="white", font=("Arial", 10, "bold"), width=10)
        self.stop_btn.pack(side=LEFT, padx=5)

        self.restart_btn = Button(btn_frame, text="🔄 重启", command=self.restart_server, state=DISABLED,
                                  bg="#FF9800", fg="white", font=("Arial", 10, "bold"), width=10)
        self.restart_btn.pack(side=LEFT, padx=5)

        # 快捷操作区域
        quick_actions_frame = Frame(control_frame, bg="#F0F0F0")
        quick_actions_frame.pack(fill='x', pady=8, padx=10)

        # 统一小按钮样式
        small_btn_opts = {"font": ("Arial", 9), "padx": 8, "pady": 3}

        Button(quick_actions_frame, text="📦 安装/更新", command=self.install_server,
               bg="#E0E0E0",
               fg="#000000",
               **small_btn_opts).pack(side=LEFT, padx=3)

        Button(quick_actions_frame, text="🛠 更新 SteamCMD", command=self.update_steamcmd,
               bg="#E0E0E0",
               fg="#000000",
               **small_btn_opts).pack(side=LEFT, padx=3)

        Button(quick_actions_frame, text="🌿 切换分支", command=self.switch_branch,
               bg="#E0E0E0",
               fg="#000000",
               **small_btn_opts).pack(side=LEFT, padx=3)

        # 分隔符
        Label(quick_actions_frame, text="|", bg="#F0F0F0", fg="#999").pack(side=LEFT, padx=10)

        Button(quick_actions_frame, text="💾 立即备份", command=self.manual_backup,
               bg="#2196F3", fg="white", **small_btn_opts).pack(side=RIGHT, padx=3)

        Button(quick_actions_frame, text="📂 打开备份", command=self.open_backup_folder,
               bg="#E0E0E0",
               fg="#000000",
               **small_btn_opts).pack(side=RIGHT, padx=3)

        # 新增：彻底删除服务器按钮
        Button(quick_actions_frame, text="🗑️ 彻底删除服务器", command=self.delete_server_confirm,
               bg="#D32F2F", fg="white", **small_btn_opts).pack(side=RIGHT, padx=15)

        # 新增：打开存档目录按钮
        Button(quick_actions_frame, text="📂 打开存档", command=self.open_save_directory,
               bg="#E0E0E0",
               fg="#000000",
               **small_btn_opts).pack(side=RIGHT, padx=3)

        # 保存设置按钮
        save_frame = Frame(control_frame, bg="#F0F0F0")
        save_frame.pack(fill='x', pady=8, padx=10)
        Button(save_frame, text="💾 保存设置", command=self.save_settings,
               bg="#4CAF50", fg="white", font=("Arial", 9, "bold"), padx=10, pady=3).pack(side=RIGHT)

        # 2. 服务器参数设置
        settings_params_frame = LabelFrame(main_container, text="⚙️ 服务器参数",
                                           bg="#F0F0F0",
                                           fg="#000000",
                                           font=("Arial", 10, "bold"))
        settings_params_frame.pack(fill='x', pady=8)

        inner_settings_frame = Frame(settings_params_frame, bg="#F0F0F0")
        inner_settings_frame.pack(fill='x', pady=3, padx=5)

        # 最大玩家设置
        Label(inner_settings_frame, text="最大玩家:", bg="#FFFFFF",
              fg="#000000", font=("Arial", 9)).pack(side=LEFT, padx=5)
        self.max_players_var = IntVar(value=self.config["max_players"])
        Spinbox(inner_settings_frame, from_=1, to=100, textvariable=self.max_players_var, width=8,
                bg="#FFFFFF",
                fg="#000000",
                buttonbackground="#E0E0E0",
                font=("Arial", 9)).pack(side=LEFT, padx=5)

        # 游戏端口设置
        port_frame = Frame(inner_settings_frame, bg="#F0F0F0")
        port_frame.pack(fill='x', pady=3, padx=5)

        Label(port_frame, text="游戏端口:", bg="#FFFFFF",
              fg="#000000", font=("Arial", 9)).pack(side=LEFT, padx=5)
        self.game_port_var = IntVar(value=self.config.get("game_port", 7777))
        Spinbox(port_frame, from_=1, to=65535, textvariable=self.game_port_var, width=8,
                bg="#FFFFFF",
                fg="#000000",
                buttonbackground="#E0E0E0",
                font=("Arial", 9)).pack(side=LEFT, padx=5)

        Label(port_frame, text="Beacon 端口:", bg="#FFFFFF",
              fg="#000000", font=("Arial", 9)).pack(side=LEFT, padx=(20, 5))
        self.beacon_port_var = IntVar(value=self.config.get("beacon_port", 8888))
        Spinbox(port_frame, from_=1, to=65535, textvariable=self.beacon_port_var, width=8,
                bg="#FFFFFF",
                fg="#000000",
                buttonbackground="#E0E0E0",
                font=("Arial", 9)).pack(side=LEFT, padx=5)

        # 分支选择
        branch_frame = Frame(inner_settings_frame, bg="#F0F0F0")
        branch_frame.pack(fill='x', pady=3, padx=5)

        self.branch_var = StringVar(value=self.config["branch"])
        Radiobutton(branch_frame, text="正式版 (Public)", variable=self.branch_var, value="public",
                    bg="#F0F0F0",
                    fg="#000000",
                    selectcolor="#DDDDDD",
                    font=("Arial", 9)).pack(side=LEFT, padx=5)
        Radiobutton(branch_frame, text="实验版 (Experimental)", variable=self.branch_var, value="experimental",
                    bg="#F0F0F0",
                    fg="#000000",
                    selectcolor="#DDDDDD",
                    font=("Arial", 9)).pack(side=LEFT, padx=5)

        # 自动化设置区域
        automation_frame = LabelFrame(settings_params_frame, text="🤖 自动化设置",
                                      bg="#F0F0F0",
                                      fg="#000000",
                                      font=("Arial", 9, "bold"))
        automation_frame.pack(fill='x', pady=8)

        # 在自动化设置框架内创建两个复选框
        automation_inner_frame = Frame(automation_frame, bg="#F0F0F0")
        automation_inner_frame.pack(fill='x', pady=5, padx=5)

        # 崩溃自动重启选项
        self.auto_restart_var = BooleanVar(value=self.config["auto_restart"])
        auto_restart_cb = Checkbutton(automation_inner_frame, text="崩溃自动重启", variable=self.auto_restart_var,
                                      bg="#F0F0F0",
                                      fg="#000000",
                                      selectcolor="#DDDDDD",
                                      font=("Arial", 9))
        auto_restart_cb.pack(side=LEFT, padx=5)

        # 开机自启选项
        self.auto_start_var = BooleanVar(value=self.config["auto_start"])
        auto_start_cb = Checkbutton(automation_inner_frame, text="开机自启", variable=self.auto_start_var,
                                    bg="#F0F0F0",
                                    fg="#000000",
                                    selectcolor="#DDDDDD",
                                    font=("Arial", 9))
        auto_start_cb.pack(side=LEFT, padx=20)

        # 3. 配置管理区域
        config_frame = LabelFrame(main_container, text="⚙️ 配置管理",
                                  bg="#F0F0F0",
                                  fg="#000000",
                                  font=("Arial", 10, "bold"))
        config_frame.pack(fill='x', pady=8)

        config_container = Frame(config_frame, bg="#F0F0F0")
        config_container.pack(fill='x', padx=10, pady=10)

        # 路径设置
        path_frame = LabelFrame(config_container, text="📁 安装路径",
                                bg="#F0F0F0",
                                fg="#000000",
                                font=("Arial", 9, "bold"))
        path_frame.pack(fill='x', pady=5)

        inner_path_frame = Frame(path_frame, bg="#F0F0F0")
        inner_path_frame.pack(fill='x', pady=5, padx=5)

        Label(inner_path_frame, text="根目录:", bg="#FFFFFF",
              fg="#000000",
              font=("Arial", 9, "bold"), width=10, anchor='e').pack(side=LEFT, padx=5)

        help_label = Label(inner_path_frame, text="说明：SteamCMD 和服务器将安装在此目录下",
                           bg="#FFFFFF",
                           fg="#000000",
                           font=("Arial", 8), wraplength=600, justify=LEFT)
        help_label.pack(anchor=W, pady=(2, 2), padx=5)

        self.install_path_var = StringVar(value=self.config.get("install_path", ""))
        path_entry = Entry(inner_path_frame, textvariable=self.install_path_var, width=50,
                           bg="#FFFFFF",
                           fg="#000000",
                           insertbackground="#000000",
                           font=("Arial", 9))
        path_entry.pack(side=LEFT, fill='x', expand=True, padx=5)
        Button(inner_path_frame, text="浏览", command=self.browse_install_path,
               bg="#E0E0E0",
               fg="#000000",
               font=("Arial", 8), padx=5).pack(side=RIGHT, padx=5)

        # 监控设置
        monitor_frame = LabelFrame(config_container, text="📡 网络监控",
                                   bg="#F0F0F0",
                                   fg="#000000",
                                   font=("Arial", 9, "bold"))
        monitor_frame.pack(fill='x', pady=5)

        inner_monitor_frame = Frame(monitor_frame, bg="#F0F0F0")
        inner_monitor_frame.pack(fill='x', pady=5, padx=5)

        Label(inner_monitor_frame, text="监控地址:", bg="#FFFFFF",
              fg="#000000",
              font=("Arial", 9, "bold"), width=10, anchor='e').pack(side=LEFT, padx=5)

        self.monitor_host_var = StringVar(value=self.config.get("monitor_host", "localhost"))
        Entry(inner_monitor_frame, textvariable=self.monitor_host_var, width=30,
              bg="#FFFFFF",
              fg="#000000",
              insertbackground="#000000",
              font=("Arial", 9)).pack(side=LEFT, padx=5)

        Label(inner_monitor_frame, text="(默认 localhost)",
              bg="#FFFFFF",
              fg="#000000",
              font=("Arial", 8)).pack(side=LEFT)

        # 存档与备份策略
        archive_frame = LabelFrame(config_container, text="💾 备份策略",
                                   bg="#F0F0F0",
                                   fg="#000000",
                                   font=("Arial", 9, "bold"))
        archive_frame.pack(fill='x', pady=5)

        row1 = Frame(archive_frame, bg="#F0F0F0")
        row1.pack(fill='x', pady=3, padx=5)

        Label(row1, text="自动保存数量:", bg="#FFFFFF",
              fg="#000000", width=15, anchor='e',
              font=("Arial", 9)).pack(side=LEFT, padx=5)
        self.autosave_count_var = IntVar(value=self.config.get("autosave_count", 5))
        Spinbox(row1, from_=1, to=50, textvariable=self.autosave_count_var, width=8,
                bg="#FFFFFF",
                fg="#000000",
                buttonbackground="#E0E0E0",
                font=("Arial", 9)).pack(side=LEFT, padx=5)
        Label(row1, text="(保留最近 N 个)", bg="#FFFFFF",
              fg="#000000", font=("Arial", 8)).pack(side=LEFT, padx=5)

        row2 = Frame(archive_frame, bg="#F0F0F0")
        row2.pack(fill='x', pady=3, padx=5)

        self.enable_backup_var = BooleanVar(value=self.config.get("enable_auto_backup", True))
        Checkbutton(row2, text="启用自动备份", variable=self.enable_backup_var,
                    bg="#F0F0F0",
                    fg="#000000",
                    selectcolor="#DDDDDD",
                    font=("Arial", 9)).pack(side=LEFT, padx=5)

        Label(row2, text="间隔 (分钟):", bg="#FFFFFF",
              fg="#000000", font=("Arial", 9)).pack(side=LEFT, padx=(15, 5))
        self.backup_interval_var = IntVar(value=self.config.get("backup_interval", 30))
        Spinbox(row2, from_=5, to=1440, textvariable=self.backup_interval_var, width=8,
                bg="#FFFFFF",
                fg="#000000",
                buttonbackground="#E0E0E0",
                font=("Arial", 9)).pack(side=LEFT, padx=5)

        row3 = Frame(archive_frame, bg="#F0F0F0")
        row3.pack(fill='x', pady=3, padx=5)

        Label(row3, text="保留数量:", bg="#FFFFFF",
              fg="#000000", font=("Arial", 9)).pack(side=LEFT, padx=5)
        self.backup_retain_var = IntVar(value=self.config.get("backup_retain", 10))
        Spinbox(row3, from_=1, to=100, textvariable=self.backup_retain_var, width=8,
                bg="#FFFFFF",
                fg="#000000",
                buttonbackground="#E0E0E0",
                font=("Arial", 9)).pack(side=LEFT, padx=5)
        Label(row3, text="(自动删旧)", bg="#FFFFFF",
              fg="#000000", font=("Arial", 8)).pack(side=LEFT, padx=5)

        backup_locations_frame = LabelFrame(archive_frame, text="📍 备份位置",
                                            bg="#F0F0F0",
                                            fg="#000000",
                                            font=("Arial", 9, "bold"))
        backup_locations_frame.pack(fill='x', pady=5, padx=5)

        self.backup_locations_listbox = Listbox(backup_locations_frame, height=3, font=("Arial", 9))
        self.backup_locations_listbox.pack(fill='x', padx=5, pady=5)

        location_btn_frame = Frame(backup_locations_frame, bg="#F0F0F0")
        location_btn_frame.pack(fill='x', padx=5, pady=5)
        btn_small_opts = {"font": ("Arial", 8), "padx": 5, "pady": 2}
        Button(location_btn_frame, text="添加", command=self.add_backup_location,
               bg="#E0E0E0",
               fg="#000000",
               **btn_small_opts).pack(side=LEFT, padx=2)
        Button(location_btn_frame, text="编辑", command=self.edit_selected_backup_location,
               bg="#E0E0E0",
               fg="#000000",
               **btn_small_opts).pack(side=LEFT, padx=2)
        Button(location_btn_frame, text="删除", command=self.delete_selected_backup_location,
               bg="#E0E0E0",
               fg="#000000",
               **btn_small_opts).pack(side=LEFT, padx=2)
        self.refresh_backup_locations_display()

        # 代理服务器设置
        proxy_frame = LabelFrame(config_container, text="🌐 代理服务器",
                                 bg="#F0F0F0",
                                 fg="#000000",
                                 font=("Arial", 9, "bold"))
        proxy_frame.pack(fill='x', pady=2)

        inner_proxy_frame = Frame(proxy_frame, bg="#F0F0F0")
        inner_proxy_frame.pack(fill='x', pady=5, padx=5)

        self.proxy_enabled_var = BooleanVar(value=self.config.get("proxy_enabled", False))
        Checkbutton(inner_proxy_frame, text="启用代理服务器", variable=self.proxy_enabled_var,
                    bg="#F0F0F0",
                    fg="#000000",
                    selectcolor="#DDDDDD",
                    font=("Arial", 9)).pack(anchor=W, padx=5)

        # 代理服务器配置行
        type_frame = Frame(proxy_frame, bg="#F0F0F0")
        type_frame.pack(fill='x', pady=3, padx=5)

        Label(type_frame, text="代理类型:", bg="#FFFFFF",
              fg="#000000", font=("Arial", 9)).pack(side=LEFT, padx=5)
        self.proxy_type_var = StringVar(value=self.config.get("proxy_type", "HTTP"))
        proxy_type_combo = ttk.Combobox(type_frame, textvariable=self.proxy_type_var,
                                        values=["HTTP", "HTTPS", "SOCKS4", "SOCKS5"], state="readonly", width=15)
        proxy_type_combo.pack(side=LEFT, padx=5)

        host_frame = Frame(proxy_frame, bg="#F0F0F0")
        host_frame.pack(fill='x', pady=3, padx=5)

        Label(host_frame, text="代理主机:", bg="#FFFFFF",
              fg="#000000", font=("Arial", 9)).pack(side=LEFT, padx=5)
        self.proxy_host_var = StringVar(value=self.config.get("proxy_host", ""))
        Entry(host_frame, textvariable=self.proxy_host_var, width=20,
              bg="#FFFFFF",
              fg="#000000",
              insertbackground="#000000",
              font=("Arial", 9)).pack(side=LEFT, padx=5)

        port_frame = Frame(proxy_frame, bg="#F0F0F0")
        port_frame.pack(fill='x', pady=3, padx=5)

        Label(port_frame, text="代理端口:", bg="#FFFFFF",
              fg="#000000", font=("Arial", 9)).pack(side=LEFT, padx=5)
        self.proxy_port_var = StringVar(value=self.config.get("proxy_port", ""))
        Entry(port_frame, textvariable=self.proxy_port_var, width=20,
              bg="#FFFFFF",
              fg="#000000",
              insertbackground="#000000",
              font=("Arial", 9)).pack(side=LEFT, padx=5)

        # 认证信息
        auth_frame = Frame(proxy_frame, bg="#F0F0F0")
        auth_frame.pack(fill='x', pady=3, padx=5)

        Label(auth_frame, text="用户名:", bg="#FFFFFF",
              fg="#000000", font=("Arial", 9)).pack(side=LEFT, padx=5)
        self.proxy_username_var = StringVar(value=self.config.get("proxy_username", ""))
        Entry(auth_frame, textvariable=self.proxy_username_var, width=20,
              bg="#FFFFFF",
              fg="#000000",
              insertbackground="#000000",
              font=("Arial", 9)).pack(side=LEFT, padx=5)

        password_frame = Frame(proxy_frame, bg="#F0F0F0")
        password_frame.pack(fill='x', pady=3, padx=5)

        Label(password_frame, text="密码:", bg="#FFFFFF",
              fg="#000000", font=("Arial", 9)).pack(side=LEFT, padx=5)
        self.proxy_password_var = StringVar(value=self.config.get("proxy_password", ""))
        Entry(password_frame, textvariable=self.proxy_password_var, width=20, show="*",
              bg="#FFFFFF",
              fg="#000000",
              insertbackground="#000000",
              font=("Arial", 9)).pack(side=LEFT, padx=5)

        # 测试代理连接按钮
        test_proxy_frame = Frame(proxy_frame, bg="#F0F0F0")
        test_proxy_frame.pack(fill='x', pady=5, padx=5)

        Button(test_proxy_frame, text="测试代理连接", command=self.test_proxy_connection,
               bg="#2196F3", fg="white", font=("Arial", 9, "bold")).pack(side=LEFT, padx=5)

        # 定时任务设置
        schedule_frame = LabelFrame(config_container, text="⏰ 自定义定时任务",
                                    bg="#F0F0F0",
                                    fg="#000000",
                                    font=("Arial", 9, "bold"))
        schedule_frame.pack(fill='x', pady=2)

        inner_schedule_frame = Frame(schedule_frame, bg="#F0F0F0")
        inner_schedule_frame.pack(fill='x', pady=5, padx=5)

        self.schedule_enabled_var = BooleanVar(value=self.config.get("schedule_enabled", False))
        Checkbutton(inner_schedule_frame, text="启用定时任务", variable=self.schedule_enabled_var,
                    bg="#F0F0F0",
                    fg="#000000",
                    selectcolor="#DDDDDD",
                    font=("Arial", 9)).pack(anchor=W, padx=5)

        # 星期选择
        days_frame = Frame(schedule_frame, bg="#F0F0F0")
        days_frame.pack(fill='x', pady=5, padx=5)

        Label(days_frame, text="选择运行的星期:", bg="#FFFFFF",
              fg="#000000", font=("Arial", 9)).pack(anchor=W, padx=5)

        # 创建星期选择复选框
        self.day_vars = {}
        days_order = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']
        days_names = ['周一', '周二', '周三', '周四', '周五', '周六', '周日']
        
        days_row1 = Frame(days_frame, bg="#F0F0F0")
        days_row1.pack(fill='x', padx=5)
        
        for i, (day, name) in enumerate(zip(days_order, days_names)):
            col = i % 4
            if i >= 4:  # 第五行开始新的行
                days_row2 = Frame(days_frame, bg="#F0F0F0")
                days_row2.pack(fill='x', padx=5)
                current_row = days_row2
            else:
                current_row = days_row1
            
            var = BooleanVar(value=self.config.get("custom_schedule_days", {}).get(day, {"start": "17:00", "end": "02:00"}).get("enabled", True))
            self.day_vars[day] = var
            cb = Checkbutton(current_row, text=name, variable=var,
                            bg="#F0F0F0",
                            fg="#000000",
                            selectcolor="#DDDDDD",
                            font=("Arial", 9))
            cb.grid(row=0, column=col, padx=5, sticky=W)

        # 时间设置
        time_frame = Frame(schedule_frame, bg="#F0F0F0")
        time_frame.pack(fill='x', pady=5, padx=5)

        Label(time_frame, text="统一运行时间段:", bg="#FFFFFF",
              fg="#000000", font=("Arial", 9)).pack(anchor=W, padx=5)

        time_input_frame = Frame(time_frame, bg="#F0F0F0")
        time_input_frame.pack(fill='x', padx=5, pady=5)

        Label(time_input_frame, text="启动时间:", bg="#FFFFFF",
              fg="#000000", font=("Arial", 9)).pack(side=LEFT, padx=5)
        self.unified_start_time_var = StringVar(value=self.config.get("unified_start_time", "17:00"))
        Entry(time_input_frame, textvariable=self.unified_start_time_var, width=10,
              bg="#FFFFFF",
              fg="#000000",
              insertbackground="#000000",
              font=("Arial", 9)).pack(side=LEFT, padx=5)
        Label(time_input_frame, text="(HH:MM)", bg="#FFFFFF",
              fg="#000000", font=("Arial", 8)).pack(side=LEFT, padx=5)

        Label(time_input_frame, text="关闭时间:", bg="#FFFFFF",
              fg="#000000", font=("Arial", 9)).pack(side=LEFT, padx=(20, 5))
        self.unified_end_time_var = StringVar(value=self.config.get("unified_end_time", "02:00"))
        Entry(time_input_frame, textvariable=self.unified_end_time_var, width=10,
              bg="#FFFFFF",
              fg="#000000",
              insertbackground="#000000",
              font=("Arial", 9)).pack(side=LEFT, padx=5)
        Label(time_input_frame, text="(HH:MM)", bg="#FFFFFF",
              fg="#000000", font=("Arial", 8)).pack(side=LEFT, padx=5)

        # 或者高级设置按钮
        advanced_btn_frame = Frame(schedule_frame, bg="#F0F0F0")
        advanced_btn_frame.pack(fill='x', pady=5, padx=5)
        Button(advanced_btn_frame, text="高级设置 - 为每个星期单独设置时间", command=self.open_advanced_schedule_settings,
               bg="#E0E0E0",
               fg="#000000",
               font=("Arial", 9)).pack(side=LEFT, padx=5)

        # 说明文字
        help_text = "说明：\n" \
                   "- 勾选需要运行的星期\n" \
                   "- 统一时间段：所有勾选的星期都按此时间段运行\n" \
                   "- 点击高级设置可为每个星期单独设置时间段\n" \
                   "- 时间格式：HH:MM (24小时制)\n" \
                   "- 如果启动时间晚于关闭时间，表示跨夜运行\n" \
                   "- 例如：17:00启动，02:00关闭表示从下午5点运行到凌晨2点"
        help_label = Label(schedule_frame, text=help_text,
                           bg="#FFFFFF",
                           fg="#000000",
                           font=("Arial", 8), wraplength=600, justify=LEFT)
        help_label.pack(anchor=W, pady=(5, 5), padx=5)

        # 存档路径设置
        save_path_frame = LabelFrame(config_container, text="💾 存档路径设置",
                                     bg="#F0F0F0",
                                     fg="#000000",
                                     font=("Arial", 9, "bold"))
        save_path_frame.pack(fill='x', pady=2)

        inner_save_path_frame = Frame(save_path_frame, bg="#F0F0F0")
        inner_save_path_frame.pack(fill='x', pady=5, padx=5)

        Label(inner_save_path_frame, text="存档路径:", bg="#FFFFFF",
              fg="#000000", font=("Arial", 9)).pack(side=LEFT, padx=5)
        
        self.save_path_var = StringVar(value=self.config.get("save_game_path", os.path.join(os.getenv('LOCALAPPDATA'), "FactoryGame", "Saved", "SaveGames")))
        Entry(inner_save_path_frame, textvariable=self.save_path_var, width=40,
              bg="#FFFFFF",
              fg="#000000",
              insertbackground="#000000",
              font=("Arial", 9)).pack(side=LEFT, fill='x', expand=True, padx=5)
        Button(inner_save_path_frame, text="浏览", command=self.browse_save_path,
               bg="#E0E0E0",
               fg="#000000",
               font=("Arial", 8), padx=5).pack(side=RIGHT, padx=5)

    def browse_save_path(self):
        """浏览存档路径"""
        path = filedialog.askdirectory(initialdir=os.path.join(os.getenv('LOCALAPPDATA'), "FactoryGame", "Saved", "SaveGames"))
        if path:
            self.save_path_var.set(path)

    def open_advanced_schedule_settings(self):
        """打开高级定时任务设置窗口"""
        dialog = Toplevel(self.root)
        dialog.title("高级定时任务设置")
        dialog.geometry("600x500")
        x = int((self.root.winfo_screenwidth() / 2) - 300)
        y = int((self.root.winfo_screenheight() / 2) - 250)
        dialog.geometry(f"+{x}+{y}")
        dialog.transient(self.root)
        dialog.grab_set()

        # 创建滚动区域
        canvas = Canvas(dialog, bg="#FFFFFF", highlightthickness=0)
        scrollbar = Scrollbar(dialog, orient="vertical", command=canvas.yview)
        scrollable_frame = Frame(canvas, bg="#FFFFFF")

        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas_window = canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        # 布局
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # 绑定鼠标滚轮
        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1*(event.delta/120)), "units")

        canvas.bind_all("<MouseWheel>", _on_mousewheel, add='+')

        # 为每个星期创建设置行
        days_order = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']
        days_names = ['周一', '周二', '周三', '周四', '周五', '周六', '周日']
        
        self.advanced_day_vars = {}
        
        for i, (day, name) in enumerate(zip(days_order, days_names)):
            day_config = self.config.get("custom_schedule_days", {}).get(day, {"start": "17:00", "end": "02:00"})
            
            day_frame = Frame(scrollable_frame, bg="#F0F0F0", relief="groove", bd=1)
            day_frame.pack(fill='x', pady=5, padx=10)
            
            # 星期标题和启用复选框
            title_frame = Frame(day_frame, bg="#F0F0F0")
            title_frame.pack(fill='x', pady=5)
            
            enabled_var = BooleanVar(value=day_config.get("enabled", True))
            self.advanced_day_vars[f"{day}_enabled"] = enabled_var
            
            Checkbutton(title_frame, text=f"{name} ({day})", variable=enabled_var,
                       bg="#F0F0F0",
                       fg="#000000",
                       selectcolor="#DDDDDD",
                       font=("Arial", 10, "bold")).pack(side=LEFT, padx=5)
            
            # 时间设置
            time_frame = Frame(day_frame, bg="#F0F0F0")
            time_frame.pack(fill='x', pady=5, padx=20)
            
            Label(time_frame, text="启动时间:", bg="#FFFFFF",
                  fg="#000000", font=("Arial", 9)).pack(side=LEFT, padx=5)
            start_var = StringVar(value=day_config.get("start", "17:00"))
            self.advanced_day_vars[f"{day}_start"] = start_var
            Entry(time_frame, textvariable=start_var, width=10,
                  bg="#FFFFFF",
                  fg="#000000",
                  insertbackground="#000000",
                  font=("Arial", 9)).pack(side=LEFT, padx=5)
            
            Label(time_frame, text="关闭时间:", bg="#FFFFFF",
                  fg="#000000", font=("Arial", 9)).pack(side=LEFT, padx=(20, 5))
            end_var = StringVar(value=day_config.get("end", "02:00"))
            self.advanced_day_vars[f"{day}_end"] = end_var
            Entry(time_frame, textvariable=end_var, width=10,
                  bg="#FFFFFF",
                  fg="#000000",
                  insertbackground="#000000",
                  font=("Arial", 9)).pack(side=LEFT, padx=5)

        # 按钮区域
        btn_frame = Frame(dialog, bg="#F0F0F0")
        btn_frame.pack(fill='x', pady=20, padx=10)

        def save_advanced_settings():
            # 保存高级设置
            for day in days_order:
                self.config["custom_schedule_days"][day] = {
                    "enabled": self.advanced_day_vars[f"{day}_enabled"].get(),
                    "start": self.advanced_day_vars[f"{day}_start"].get(),
                    "end": self.advanced_day_vars[f"{day}_end"].get()
                }
            messagebox.showinfo("保存成功", "高级定时任务设置已保存")
            dialog.destroy()

        Button(btn_frame, text="保存设置", command=save_advanced_settings, bg="#4CAF50", fg="white").pack(side=LEFT, padx=5)
        Button(btn_frame, text="取消", command=dialog.destroy, bg="#F44336", fg="white").pack(side=RIGHT, padx=5)

    def test_proxy_connection(self):
        """测试代理服务器连接"""
        def _test():
            try:
                if not self.proxy_enabled_var.get():
                    self.root.after(0, lambda: messagebox.showwarning("测试", "请先启用代理服务器"))
                    return

                # 构建代理URL
                proxy_type = self.proxy_type_var.get().lower()
                proxy_host = self.proxy_host_var.get()
                proxy_port = self.proxy_port_var.get()
                proxy_username = self.proxy_username_var.get()
                proxy_password = self.proxy_password_var.get()

                if not proxy_host or not proxy_port:
                    self.root.after(0, lambda: messagebox.showerror("测试", "请输入代理主机和端口"))
                    return

                proxy_url = f"{proxy_type}://"
                if proxy_username and proxy_password:
                    proxy_url += f"{proxy_username}:{proxy_password}@"
                proxy_url += f"{proxy_host}:{proxy_port}"

                proxies = {
                    "http": proxy_url,
                    "https": proxy_url
                }

                self.log_message(f"🔍 测试代理连接: {proxy_url}")

                # 测试连接
                response = requests.get("http://httpbin.org/ip", proxies=proxies, timeout=10)
                if response.status_code == 200:
                    data = response.json()
                    ip = data.get("origin", "未知")
                    self.log_message(f"✅ 代理连接成功，当前IP: {ip}")
                    self.root.after(0, lambda: messagebox.showinfo("测试成功", f"代理连接成功！\n当前IP: {ip}"))
                else:
                    self.log_message("❌ 代理连接失败")
                    self.root.after(0, lambda: messagebox.showerror("测试失败", "代理连接失败"))
            except requests.exceptions.ProxyError:
                self.log_message("❌ 代理服务器连接失败")
                self.root.after(0, lambda: messagebox.showerror("测试失败", "代理服务器连接失败，请检查配置"))
            except requests.exceptions.ConnectionError:
                self.log_message("❌ 网络连接失败")
                self.root.after(0, lambda: messagebox.showerror("测试失败", "网络连接失败，请检查代理服务器"))
            except requests.exceptions.Timeout:
                self.log_message("❌ 连接超时")
                self.root.after(0, lambda: messagebox.showerror("测试失败", "连接超时，请检查代理服务器"))
            except Exception as e:
                self.log_message(f"❌ 代理测试出错：{str(e)}")
                self.root.after(0, lambda: messagebox.showerror("测试失败", f"代理测试出错：{str(e)}"))

        thread = threading.Thread(target=_test, daemon=True)
        thread.start()

    def refresh_backup_locations_display(self):
        self.backup_locations_listbox.delete(0, END)
        for loc in self.config.get("backup_locations", []):
            status = "✓" if loc.get("enabled", True) else "✗"
            display_text = f"{status} {loc['type'].upper()}: {loc.get('path', loc.get('address', ''))}"
            self.backup_locations_listbox.insert(END, display_text)

    def add_backup_location(self):
        self.open_backup_location_dialog()

    def edit_selected_backup_location(self):
        selection = self.backup_locations_listbox.curselection()
        if not selection:
            messagebox.showwarning("警告", "请选择一个备份位置"); return
        index = selection[0]
        locations = self.config.get("backup_locations", [])
        if index < len(locations):
            self.open_backup_location_dialog(locations[index], index)

    def delete_selected_backup_location(self):
        selection = self.backup_locations_listbox.curselection()
        if not selection:
            messagebox.showwarning("警告", "请选择一个备份位置"); return
        index = selection[0]
        locations = self.config.get("backup_locations", [])
        if index < len(locations):
            del locations[index]
            self.config["backup_locations"] = locations
            self.refresh_backup_locations_display()

    def open_backup_location_dialog(self, location=None, index=None):
        dialog = Toplevel(self.root)
        dialog.title("备份位置设置" if location is None else "编辑备份位置")
        dialog.geometry("400x350")
        x = int((self.root.winfo_screenwidth() / 2) - 200)
        y = int((self.root.winfo_screenheight() / 2) - 175)
        dialog.geometry(f"+{x}+{y}")
        dialog.transient(self.root)
        dialog.grab_set()

        type_frame = Frame(dialog)
        type_frame.pack(fill=X, pady=10, padx=10)

        Label(type_frame, text="备份类型:").pack(anchor=W)
        type_var = StringVar(value=location.get("type", "local") if location else "local")
        type_combo = ttk.Combobox(type_frame, textvariable=type_var,
                                  values=["local", "network", "webdav", "ftp", "sftp"],
                                  state="readonly", width=20)
        type_combo.pack(side=LEFT, pady=5)

        path_frame = Frame(dialog)
        path_frame.pack(fill=X, pady=5, padx=10)

        Label(path_frame, text="路径/地址:").pack(anchor=W)
        path_var = StringVar(value=location.get("path", "") if location and "path" in location else "")
        address_var = StringVar(value=location.get("address", "") if location and "address" in location else "")
        username_var = StringVar(value=location.get("username", "") if location else "")
        password_var = StringVar(value=location.get("password", "") if location else "")

        def update_fields(*args):
            for widget in path_frame.winfo_children()[2:]:
                widget.destroy()
            current_type = type_var.get()
            if current_type == "local":
                Entry(path_frame, textvariable=path_var, width=50).pack(fill=X, pady=5)
                Button(path_frame, text="浏览", command=lambda: self.browse_path(path_var)).pack(side=RIGHT, padx=5)
            elif current_type == "network":
                Entry(path_frame, textvariable=path_var, width=50).pack(fill=X, pady=5)
            elif current_type in ["webdav", "ftp", "sftp"]:
                Entry(path_frame, textvariable=address_var, width=50).pack(fill=X, pady=5)
                Label(path_frame, text="用户名:").pack(anchor=W)
                Entry(path_frame, textvariable=username_var, width=50).pack(fill=X, pady=5)
                Label(path_frame, text="密码:").pack(anchor=W)
                Entry(path_frame, textvariable=password_var, width=50, show="*").pack(fill=X, pady=5)

        type_combo.bind("<<ComboboxSelected>>", update_fields)
        update_fields()

        enabled_var = BooleanVar(value=location.get("enabled", True) if location else True)
        Checkbutton(dialog, text="启用此备份位置", variable=enabled_var).pack(pady=5)

        btn_frame = Frame(dialog)
        btn_frame.pack(fill=X, pady=20, padx=10)

        def save_location():
            new_location = {"type": type_var.get(), "enabled": enabled_var.get()}
            if type_var.get() == "local":
                new_location["path"] = path_var.get()
            elif type_var.get() == "network":
                new_location["path"] = path_var.get()
            elif type_var.get() in ["webdav", "ftp", "sftp"]:
                new_location["address"] = address_var.get()
                new_location["username"] = username_var.get()
                new_location["password"] = password_var.get()

            locations = self.config.get("backup_locations", [])
            if index is not None and index < len(locations):
                locations[index] = new_location
            else:
                locations.append(new_location)
            self.config["backup_locations"] = locations
            self.refresh_backup_locations_display()
            dialog.destroy()

        Button(btn_frame, text="保存", command=save_location, bg="#4CAF50", fg="white").pack(side=LEFT, padx=5)
        Button(btn_frame, text="取消", command=dialog.destroy, bg="#F44336", fg="white").pack(side=RIGHT, padx=5)

    def browse_path(self, var):
        path = filedialog.askdirectory()
        if path:
            var.set(path)

    def show_local_history(self):
        if not os.path.exists(LOCAL_HISTORY_FILE):
            messagebox.showinfo("提示", "暂无本地更新历史记录."); return
        try:
            with open(LOCAL_HISTORY_FILE, 'r', encoding='utf-8') as f:
                content = f.read()

            top = Toplevel(self.root); top.title("本地更新历史"); top.geometry("600x500")
            x = int((self.root.winfo_screenwidth() / 2) - 300); y = int((self.root.winfo_screenheight() / 2) - 250)
            top.geometry(f"+{x}+{y}")
            bg_color = "#FFFFFF"; text_bg = "#FFFFFF"; text_fg = "#000000"
            top.configure(bg=bg_color)

            text_area = Text(top, wrap=WORD, bg=text_bg, fg=text_fg, font=("Consolas", 10))
            text_area.pack(fill=BOTH, expand=True, padx=10, pady=10)
            text_area.insert(END, content); text_area.config(state=DISABLED)

            Button(top, text="关闭", command=top.destroy, bg="#E0E0E0", fg="#000000").pack(pady=10)
        except Exception as e:
            messagebox.showerror("错误", f"读取历史文件失败：{str(e)}")

    def copy_qq_group(self, event=None):
        qq_group = "264127585"
        self.root.clipboard_clear()
        self.root.clipboard_append(qq_group)
        self.root.update()
        messagebox.showinfo("复制成功", f"QQ 群号 {qq_group} 已复制到剪贴板！")

    def set_button_state(self, key, state):
        if key in self.action_buttons:
            self.action_buttons[key].config(state=state)

    def browse_install_path(self):
        path = filedialog.askdirectory()
        if path:
            self.install_path_var.set(path)

    def save_settings(self):
        self.config.update({
            "install_path": self.install_path_var.get(),
            "max_players": self.max_players_var.get(),
            "auto_restart": self.auto_restart_var.get(),
            "auto_start": self.auto_start_var.get(),
            "branch": self.branch_var.get(),
            "game_port": self.game_port_var.get(),
            "beacon_port": self.beacon_port_var.get(),
            "autosave_count": self.autosave_count_var.get(),
            "backup_interval": self.backup_interval_var.get(),
            "backup_retain": self.backup_retain_var.get(),
            "enable_auto_backup": self.enable_backup_var.get(),
            "monitor_host": self.monitor_host_var.get(),
            "proxy_enabled": self.proxy_enabled_var.get(),
            "proxy_type": self.proxy_type_var.get(),
            "proxy_host": self.proxy_host_var.get(),
            "proxy_port": self.proxy_port_var.get(),
            "proxy_username": self.proxy_username_var.get(),
            "proxy_password": self.proxy_password_var.get(),
            "save_game_path": self.save_path_var.get(),
            # 定时任务配置 - 修改为支持自定义星期
            "schedule_enabled": self.schedule_enabled_var.get(),
            "unified_start_time": self.unified_start_time_var.get(),
            "unified_end_time": self.unified_end_time_var.get(),
        })
        
        # 更新星期选择配置
        days_order = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']
        unified_start = self.config.get("unified_start_time", "17:00")
        unified_end = self.config.get("unified_end_time", "02:00")
        
        for day in days_order:
            # 如果已有配置，保留原有配置；否则使用统一配置
            existing_config = self.config.get("custom_schedule_days", {}).get(day, {})
            enabled = self.day_vars[day].get()
            start_time = existing_config.get("start", unified_start)
            end_time = existing_config.get("end", unified_end)
            
            if day not in self.config.get("custom_schedule_days", {}):
                self.config.setdefault("custom_schedule_days", {})[day] = {
                    "enabled": enabled,
                    "start": start_time,
                    "end": end_time
                }
            else:
                self.config["custom_schedule_days"][day]["enabled"] = enabled
        
        self.save_config()
        self.set_auto_start()
        
        # 重新加载定时任务配置
        self.schedule_enabled = self.config.get("schedule_enabled", False)
        self.custom_schedule_days = self.config.get("custom_schedule_days", {
            "monday": {"start": "17:00", "end": "02:00"},
            "tuesday": {"start": "17:00", "end": "02:00"},
            "wednesday": {"start": "17:00", "end": "02:00"},
            "thursday": {"start": "17:00", "end": "02:00"},
            "friday": {"start": "17:00", "end": "02:00"},
            "saturday": {"start": "00:00", "end": "23:59"},
            "sunday": {"start": "00:00", "end": "23:59"}
        })
        
        # 更新定时任务
        self.update_schedules()
        
        if self.server_process and self.server_process.poll() is not None:
            messagebox.showinfo("提示", "部分设置需要重启服务器后才能生效。")
        else:
            messagebox.showinfo("提示", "设置已保存")

    def update_schedules(self):
        """更新定时任务"""
        # 清除现有任务
        schedule.clear('custom_schedule_tasks')
        
        if self.schedule_enabled:
            days_order = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']
            day_names = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']
            
            added_tasks = 0
            for day, day_name in zip(days_order, day_names):
                day_config = self.custom_schedule_days.get(day_name, {"enabled": True, "start": "17:00", "end": "02:00"})
                
                if day_config.get("enabled", True):
                    start_time = day_config.get("start", "17:00")
                    end_time = day_config.get("end", "02:00")
                    
                    # 添加启动任务
                    getattr(schedule.every(), day_name).at(start_time).do(self.schedule_start_server).tag('custom_schedule_tasks')
                    # 添加停止任务
                    getattr(schedule.every(), day_name).at(end_time).do(self.schedule_stop_server).tag('custom_schedule_tasks')
                    
                    added_tasks += 2
                    
            if added_tasks > 0:
                self.log_message(f"✅ 定时任务已启用，共添加了 {added_tasks} 个任务")
                self.schedule_status_label.config(text="已启用", fg="#4CAF50")
            else:
                self.log_message("❌ 定时任务已启用但没有选中任何星期")
                self.schedule_status_label.config(text="未配置", fg="#FF9800")
        else:
            self.log_message("❌ 定时任务已禁用")
            self.schedule_status_label.config(text="已禁用", fg="#FF9800")

    def start_scheduler(self):
        """启动定时任务调度器"""
        def run_scheduler():
            self.scheduler_running = True
            while self.scheduler_running:
                schedule.run_pending()
                time.sleep(1)
        
        self.scheduler_thread = threading.Thread(target=run_scheduler, daemon=True)
        self.scheduler_thread.start()
        
        # 初始化定时任务
        self.update_schedules()

    def schedule_start_server(self):
        """定时启动服务器"""
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        day_of_week = datetime.now().strftime("%A")
        self.log_message(f"⏰ [{current_time}] 定时任务：{day_of_week}启动服务器")
        
        # 在主线程中执行启动
        self.root.after(0, self.start_server_if_not_running)

    def schedule_stop_server(self):
        """定时停止服务器"""
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        day_of_week = datetime.now().strftime("%A")
        self.log_message(f"⏰ [{current_time}] 定时任务：{day_of_week}停止服务器")
        
        # 在主线程中执行停止
        self.root.after(0, self.stop_server)

    def start_server_if_not_running(self):
        """如果服务器未运行，则启动它"""
        if not self.server_process or self.server_process.poll() is not None:
            self.start_server()
        else:
            self.log_message("服务器已在运行，跳过启动")

    def set_auto_start(self):
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                                 r"SOFTWARE\Microsoft\Windows\CurrentVersion\Run", 0,
                                 winreg.KEY_SET_VALUE)
            if self.config["auto_start"]:
                winreg.SetValueEx(key, "SatisfactoryServer", 0, winreg.REG_SZ,
                                  sys.executable + " " + os.path.abspath(sys.argv[0]))
            else:
                try:
                    winreg.DeleteValue(key, "SatisfactoryServer")
                except FileNotFoundError:
                    pass
            winreg.CloseKey(key)
        except Exception as e:
            self.log_message(f"设置开机自启失败：{str(e)}")

    def log_message(self, message):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        full_msg = f"[{timestamp}] {message}\n"
        if threading.current_thread() is threading.main_thread():
            self.status_text.insert(END, full_msg)
            self.status_text.see(END)
            self.status_text.update_idletasks()
        else:
            self.root.after(0, lambda: self._insert_log(full_msg))

    def _insert_log(self, msg):
        self.status_text.insert(END, msg)
        self.status_text.see(END)
        self.status_text.update_idletasks()

    def get_paths(self):
        root = self.install_path_var.get()
        if not root:
            return None, None, None, None
        steamcmd_dir = os.path.join(root, "steamcmd")
        server_dir = os.path.join(root, "server")
        steamcmd_exe = os.path.join(steamcmd_dir, "steamcmd.exe")
        backup_dir = os.path.join(root, "backups")
        return steamcmd_dir, server_dir, steamcmd_exe, backup_dir

    def read_subprocess_output(self, process, callback):
        """ 读取子进程的实时输出 """
        while True:
            output = process.stdout.readline()
            if output == '' and process.poll() is not None:
                break
            if output:
                # 解码输出并发送到日志
                decoded_output = output.decode('utf-8', errors='replace').strip()
                if decoded_output:
                    # 只记录非空输出
                    callback(decoded_output)

            # 检查stderr
            stderr_output = process.stderr.read()
            if stderr_output:
                decoded_stderr = stderr_output.decode('utf-8', errors='replace').strip()
                if decoded_stderr:
                    callback(f"[STDERR] {decoded_stderr}")

    def install_server(self):
        steamcmd_dir, server_dir, steamcmd_exe, _ = self.get_paths()
        if not self.install_path_var.get():
            messagebox.showerror("错误", "请先设置安装根目录")
            return

        self.log_message("-" * 30)
        self.log_message(">>> 开始诊断与安装流程...")

        if not os.path.exists(steamcmd_exe):
            self.log_message(f"未检测到 SteamCMD: {steamcmd_exe}")
            if messagebox.askyesno("未检测到 SteamCMD", f"在安装目录下未找到 SteamCMD。\n是否立即下载并安装到:\n{steamcmd_dir}?"):
                self.download_and_install_steamcmd(steamcmd_dir)
                self.log_message("请先等待 SteamCMD 下载完成提示，然后再次点击'安装/更新'。")
            else:
                return
            return

        if not os.path.exists(server_dir):
            os.makedirs(server_dir)
            self.log_message(f"创建服务器目录：{server_dir}")

        self.set_button_state('install', DISABLED)
        self.log_message(f"目标分支：{self.branch_var.get()}")
        self.log_message(f"安装目录：{server_dir}")
        self.log_message("正在准备启动 SteamCMD (隐藏模式)...")

        def _run_installation():
            try:
                # 获取代理配置
                proxies = self.get_proxy_config() if self.proxy_enabled else None

                install_cmd = [
                    steamcmd_exe, "+login", "anonymous",
                    "+force_install_dir", server_dir,
                    "+app_update", "1690800", "-beta", self.branch_var.get(), "+quit"
                ]

                self.log_message("执行命令：" + " ".join(install_cmd))

                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                startupinfo.wShowWindow = subprocess.SW_HIDE

                self.log_message("SteamCMD 进程已启动，正在连接 Steam...")

                # 使用代理配置运行安装命令
                process = subprocess.Popen(
                    install_cmd,
                    cwd=steamcmd_dir,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    stdin=subprocess.DEVNULL,
                    text=False,  # 保持二进制模式以处理不同编码
                    bufsize=1,
                    universal_newlines=False,
                    startupinfo=startupinfo
                )

                # 实时读取输出
                self.read_subprocess_output(process, self.log_message)

                # 等待进程完成
                return_code = process.wait()

                if return_code == 0:
                    def on_success():
                        self.log_message(">>> ✅ 服务器安装/更新成功完成！")
                        messagebox.showinfo("成功", "服务器文件已更新完毕！现在可以启动服务器了。")
                        self.set_button_state('install', NORMAL)
                    self.root.after(0, on_success)
                else:
                    def on_error():
                        self.log_message(f"!!! ❌ 安装失败 (退出码 {return_code})")
                        messagebox.showerror("安装失败", f"SteamCMD 返回退出码：{return_code}\n请查看日志详情。")
                        self.set_button_state('install', NORMAL)
                    self.root.after(0, on_error)

            except subprocess.TimeoutExpired:
                def on_timeout():
                    self.log_message("!!! ❌ 警告：安装操作超时（超过 1 小时）。")
                    messagebox.showwarning("超时", "安装操作耗时过长，请检查网络连接或防火墙设置。")
                    self.set_button_state('install', NORMAL)
                self.root.after(0, on_timeout)
            except Exception as e:
                def on_exception():
                    self.log_message(f"!!! ❌ 发生未知错误：{str(e)}")
                    import traceback
                    self.log_message(traceback.format_exc())
                    messagebox.showerror("错误", f"安装过程中发生未知错误：{str(e)}")
                    self.set_button_state('install', NORMAL)
                self.root.after(0, on_exception)

        thread = threading.Thread(target=_run_installation, daemon=True)
        thread.start()

    def get_proxy_config(self):
        """获取当前代理配置"""
        if self.proxy_enabled:
            proxy_type = self.proxy_type.lower()
            proxy_url = f"{proxy_type}://"
            if self.proxy_username and self.proxy_password:
                proxy_url += f"{self.proxy_username}:{self.proxy_password}@"
            proxy_url += f"{self.proxy_host}:{self.proxy_port}"
            return {
                "http": proxy_url,
                "https": proxy_url
            }
        return None

    def download_and_install_steamcmd(self, target_path):
        self.log_message(f"正在从官方源下载 SteamCMD 到 {target_path} ...")

        def _run_download():
            try:
                # 获取代理配置
                proxies = self.get_proxy_config() if self.proxy_enabled else None

                if not os.path.exists(target_path):
                    os.makedirs(target_path)

                zip_path = os.path.join(target_path, "steamcmd.zip")

                # 使用代理配置下载
                response = requests.get(STEAMCMD_DOWNLOAD_URL, stream=True, timeout=30, proxies=proxies)
                response.raise_for_status()

                total_size = int(response.headers.get('content-length', 0))
                downloaded_size = 0

                with open(zip_path, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
                            downloaded_size += len(chunk)
                            if total_size > 0:
                                progress = (downloaded_size / total_size) * 100
                                if int(progress) % 20 == 0: # 每20%打印一次
                                    self.log_message(f"SteamCMD 下载进度：{progress:.1f}%")

                self.log_message("SteamCMD 下载完成，正在解压...")

                with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                    zip_ref.extractall(target_path)

                if os.path.exists(zip_path):
                    os.remove(zip_path)

                steamcmd_exe = os.path.join(target_path, "steamcmd.exe")
                if os.path.exists(steamcmd_exe):
                    self.log_message(f"✅ SteamCMD 已成功安装到：{target_path}")
                    self.root.after(0, lambda: messagebox.showinfo("成功", "SteamCMD 下载并安装成功！\n现在可以点击'安装/更新'来安装服务器了。"))
                else:
                    self.log_message("❌ 错误：解压后未找到 steamcmd.exe")
                    self.root.after(0, lambda: messagebox.showerror("错误", "解压失败"))

            except Exception as e:
                self.log_message(f"❌ 下载或安装 SteamCMD 失败：{str(e)}")
                self.root.after(0, lambda: messagebox.showerror("错误", f"下载失败：{str(e)}"))

        thread = threading.Thread(target=_run_download, daemon=True)
        thread.start()

    def update_steamcmd(self):
        steamcmd_dir, _, steamcmd_exe, _ = self.get_paths()
        if not self.install_path_var.get():
            messagebox.showerror("错误", "请先设置安装根目录")
            return

        if not os.path.exists(steamcmd_exe):
            self.log_message(f"未在 {steamcmd_dir} 找到 steamcmd.exe")
            if messagebox.askyesno("未检测到 SteamCMD", f"是否立即从 Valve 官方下载并安装到:\n{steamcmd_dir}?"):
                self.download_and_install_steamcmd(steamcmd_dir)
            return

        self.set_button_state('steamcmd', DISABLED)
        self.log_message("开始更新 SteamCMD...")

        def _run_steamcmd_update():
            try:
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                startupinfo.wShowWindow = subprocess.SW_HIDE

                # 启动 SteamCMD 并实时捕获输出
                process = subprocess.Popen(
                    [steamcmd_exe, "+quit"],
                    cwd=steamcmd_dir,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    stdin=subprocess.DEVNULL,
                    text=False,  # 保持二进制模式以处理不同编码
                    bufsize=1,
                    universal_newlines=False,
                    startupinfo=startupinfo
                )

                # 实时读取输出
                self.read_subprocess_output(process, self.log_message)

                # 等待进程完成
                return_code = process.wait()

                if return_code == 0:
                    def on_success():
                        self.log_message("SteamCMD 更新完成")
                        messagebox.showinfo("提示", "SteamCMD 更新完成")
                        self.set_button_state('steamcmd', NORMAL)
                    self.root.after(0, on_success)
                else:
                    def on_error():
                        self.log_message(f"SteamCMD 更新失败 (退出码 {return_code})")
                        messagebox.showerror("错误", f"更新失败，退出码：{return_code}")
                        self.set_button_state('steamcmd', NORMAL)
                    self.root.after(0, on_error)

            except Exception as e:
                def on_error():
                    self.log_message(f"更新失败：{str(e)}")
                    messagebox.showerror("错误", f"更新失败：{str(e)}")
                    self.set_button_state('steamcmd', NORMAL)
                self.root.after(0, on_error)

        thread = threading.Thread(target=_run_steamcmd_update, daemon=True)
        thread.start()

    def switch_branch(self):
        self.config["branch"] = self.branch_var.get()
        self.save_config()
        self.log_message(f"已切换到 {self.branch_var.get()} 版本")
        messagebox.showinfo("提示", f"已切换到 {self.branch_var.get()} 版本，请点击'安装/更新'以下载对应版本文件")

    def parse_version(self, version_str):
        try:
            return [int(part) for part in version_str.replace("v", "").split(".")]
        except:
            return [0, 0]

    def check_remote_version(self):
        try:
            # 获取代理配置
            proxies = self.get_proxy_config() if self.proxy_enabled else None

            response = requests.get(REMOTE_VERSION_URL, timeout=10, proxies=proxies)
            response.raise_for_status()
            version_data = response.json()
            remote_version = version_data.get("version", "0.0")

            self.root.after(0, lambda: self.remote_version_label.config(text=f"最新版本：{remote_version}"))

            if self.parse_version(remote_version) > self.parse_version(LOCAL_VERSION):
                return True, remote_version
            else:
                return False, remote_version
        except Exception as e:
            self.root.after(0, lambda: self.remote_version_label.config(text="检查失败"))
            return False, None

    def fetch_changelog(self, version):
        try:
            # 获取代理配置
            proxies = self.get_proxy_config() if self.proxy_enabled else None

            response = requests.get(REMOTE_CHANGELOG_URL, timeout=10, proxies=proxies)
            response.raise_for_status()
            data = response.json()
            log = data.get(version, data.get("default", "暂无详细更新日志。"))
            return log
        except:
            return "无法连接到日志服务器，暂无详细更新日志。"

    def download_update_package(self):
        try:
            # 获取代理配置
            proxies = self.get_proxy_config() if self.proxy_enabled else None

            if not os.path.exists(TEMP_DOWNLOAD_DIR):
                os.makedirs(TEMP_DOWNLOAD_DIR)

            download_path = os.path.join(TEMP_DOWNLOAD_DIR, UPDATE_ZIP_NAME)
            self.log_message(f"开始下载更新包...")

            response = requests.get(REMOTE_PACKAGE_URL, stream=True, timeout=30, proxies=proxies)
            response.raise_for_status()

            total_size = int(response.headers.get('content-length', 0))
            downloaded_size = 0

            with open(download_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        downloaded_size += len(chunk)
                        if total_size > 0:
                            progress = (downloaded_size / total_size) * 100
                            if int(progress) % 10 == 0: # 每10%打印一次
                                self.log_message(f"管理器更新包下载进度：{progress:.1f}%")

            self.log_message("更新包下载完成")
            return download_path
        except Exception as e:
            self.log_message(f"下载更新包失败：{str(e)}")
            self.cleanup_temp_files()
            return None

    def extract_and_apply_update(self, zip_path):
        try:
            self.log_message("开始解压并应用更新到根目录...")

            root_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
            current_script = os.path.abspath(sys.argv[0])

            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                extract_temp = os.path.join(TEMP_DOWNLOAD_DIR, "extracted_content")
                if os.path.exists(extract_temp):
                    shutil.rmtree(extract_temp)
                os.makedirs(extract_temp)
                zip_ref.extractall(extract_temp)

                source_dir = extract_temp
                files = os.listdir(source_dir)
                # 如果解压后只有一个文件夹，进入该文件夹
                if len(files) == 1 and os.path.isdir(os.path.join(source_dir, files[0])):
                    source_dir = os.path.join(source_dir, files[0])

                copied_count = 0
                for root, dirs, files_in_dir in os.walk(source_dir):
                    for file in files_in_dir:
                        src_file = os.path.join(root, file)
                        rel_path = os.path.relpath(src_file, source_dir)
                        dst_file = os.path.join(root_dir, rel_path)

                        # 特殊处理：备份当前脚本
                        if os.path.abspath(dst_file) == os.path.abspath(current_script):
                            backup_path = dst_file + ".old_backup"
                            if os.path.exists(backup_path):
                                os.remove(backup_path)
                            shutil.move(dst_file, backup_path)
                            self.log_message(f"备份旧版主程序：{file}")

                        os.makedirs(os.path.dirname(dst_file), exist_ok=True)
                        shutil.copy2(src_file, dst_file)
                        copied_count += 1

            self.log_message(f"成功更新 {copied_count} 个文件")

            if os.path.exists(extract_temp):
                shutil.rmtree(extract_temp)

            return True
        except Exception as e:
            self.log_message(f"解压或应用更新失败：{str(e)}")
            return False

    def cleanup_temp_files(self):
        try:
            if os.path.exists(TEMP_DOWNLOAD_DIR):
                shutil.rmtree(TEMP_DOWNLOAD_DIR)
        except:
            pass

    def check_controller_update(self):
        self.set_button_state('check_update', DISABLED)
        self.log_message("正在检查管理器更新...")

        def _run_check():
            has_update, remote_version = self.check_remote_version()

            def process_result():
                self.set_button_state('check_update', NORMAL)
                if has_update:
                    self.latest_changelog = self.fetch_changelog(remote_version)
                    self.show_changelog_window(remote_version, self.latest_changelog)
                else:
                    # 如果不是手动触发的检查（即自动检查），且没有更新，则不弹窗打扰用户
                    # 这里简单处理：如果是自动检查且有更新才弹窗，无更新则只更新标签
                    # 如果是手动点击按钮，则无论有无更新都给出提示（原逻辑在show_changelog_window外没有提示，需补充）
                    # 为了区分是否是自动调用，可以加一个参数，但为了简化，这里保持原逻辑：
                    # 原逻辑：有更新弹窗，无更新不弹窗（除非手动点击按钮并在外部处理，但此处未区分）
                    # 修改：如果无更新，且是自动检查（通过调用栈很难判断，这里假设只要没更新就不弹窗，除非用户手动点）
                    # 实际上，check_controller_update 既被按钮调用也被 after 调用。
                    # 我们可以在这里加一个小技巧：如果是自动检查，无更新时不显示 messagebox
                    # 但由于无法区分调用源，我们采取保守策略：有更新必弹窗，无更新不弹窗（体验更好）
                    pass 

            self.root.after(0, process_result)

        thread = threading.Thread(target=_run_check, daemon=True)
        thread.start()

    def show_changelog_window(self, version, log_text):
        top = Toplevel(self.root)
        top.title(f"版本 {version} 更新日志")
        top.resizable(False, False)
        screen_width = top.winfo_screenwidth()
        screen_height = top.winfo_screenheight()
        lines = max(5, len(log_text) // 50 + 2)
        lines = min(lines, 25)
        log_display = Text(top, height=lines, width=60, wrap=WORD, font=("Consolas", 10),
                           bg="#F5F5F5", fg="#333333", relief=FLAT, padx=10, pady=10)
        log_display.pack(fill=BOTH, expand=True, padx=20, pady=(20, 10))
        log_display.insert(END, log_text)
        log_display.config(state=DISABLED)

        btn_frame = Frame(top, bg="#F0F0F0")
        btn_frame.pack(pady=(0, 20))

        def on_confirm():
            top.destroy()
            self.root.after(100, lambda: self.start_update_process(version))

        def on_cancel():
            top.destroy()

        btn_update = Button(btn_frame, text="立即更新", command=on_confirm, bg="#4CAF50", fg="white",
                            width=10, height=1, font=("Arial", 10, "bold"), relief=RAISED)
        btn_update.pack(side=LEFT, padx=10)
        btn_update.focus_set()

        btn_later = Button(btn_frame, text="稍后再说", command=on_cancel, bg="#E0E0E0", fg="black",
                           width=10, height=1, font=("Arial", 10), relief=RAISED)
        btn_later.pack(side=LEFT, padx=10)

        top.update_idletasks()
        w = top.winfo_reqwidth()
        h = top.winfo_reqheight()
        x = (screen_width - w) // 2
        y = (screen_height - h) // 2
        top.geometry(f"{w}x{h}+{x}+{y}")
        top.grab_set()

    def start_update_process(self, version):
        self.log_message(f">>> 开始更新流程至版本 {version}...")
        self.set_button_state('check_update', DISABLED)

        def _run_update():
            try:
                if self.server_process and self.server_process.poll() is None:
                    self.log_message("检测到服务器运行中，正在停止...")
                    self.stop_server()
                    time.sleep(2)
                self.cleanup_temp_files()

                zip_path = self.download_update_package()
                if not zip_path:
                    raise Exception("下载更新包失败")

                if not self.extract_and_apply_update(zip_path):
                    raise Exception("解压或应用更新失败")

                self.save_update_log(version, self.latest_changelog)
                self.log_message("更新成功，准备重启...")
                self.root.after(0, lambda: messagebox.showinfo("成功", "更新已完成！程序将立即重启。"))
                self.root.after(1000, self.restart_application)
            except Exception as e:
                error_msg = f"更新失败：{str(e)}"
                self.log_message(f"!!! ❌ {error_msg}")
                self.root.after(0, lambda: messagebox.showerror("更新错误", error_msg))
            finally:
                self.set_button_state('check_update', NORMAL)
                self.cleanup_temp_files()

        thread = threading.Thread(target=_run_update, daemon=True)
        thread.start()

    def restart_application(self):
        python = sys.executable
        script = os.path.abspath(sys.argv[0])
        self.root.quit()
        try:
            os.execv(python, [python, script])
        except:
            subprocess.Popen([python, script])
            sys.exit(0)

    def delete_server_confirm(self):
        """确认并执行删除服务器"""
        root_path = self.install_path_var.get()
        if not root_path:
            messagebox.showwarning("提示", "请先在配置中设置安装根目录！")
            return
        if not os.path.exists(root_path):
            messagebox.showwarning("提示", "设定的安装目录不存在！")
            return

        confirm_msg = (
            "⚠️ 高危操作警告 ⚠️\n\n"
            "您确定要彻底删除整个服务器吗？\n\n"
            f"目标目录：{root_path}\n\n"
            "这将删除:\n"
            "- SteamCMD 文件\n"
            "- 服务器所有文件\n"
            "- 所有本地备份存档\n\n"
            "此操作不可逆！请确保您已备份重要存档。"
        )
        if messagebox.askyesno("确认删除", confirm_msg, icon='warning'):
            # 二次确认
            final_confirm = messagebox.askyesno("最终确认", "再次确认：真的要删除所有数据吗？", icon='warning')
            if final_confirm:
                self._execute_delete_server(root_path)

    def _execute_delete_server(self, root_path):
        """执行删除逻辑"""
        self.log_message(">>> 开始执行服务器彻底删除流程...")
        self.set_button_state('check_update', DISABLED)

        def _run_delete():
            try:
                # 1. 停止服务器
                if self.server_process and self.server_process.poll() is not None:
                    self.log_message("检测到服务器运行中，正在强制停止...")
                    self.stop_server()
                    time.sleep(3)

                # 2. 删除目录
                if os.path.exists(root_path):
                    self.log_message(f"正在删除目录：{root_path} ...")
                    # 使用 shutil.rmtree 递归删除
                    shutil.rmtree(root_path, ignore_errors=False)
                    self.log_message("✅ 目录删除成功！")

                    # 重置配置中的路径
                    self.install_path_var.set("")
                    self.config["install_path"] = ""
                    self.save_config()

                    self.root.after(0, lambda: messagebox.showinfo("删除成功", "服务器已彻底删除！\n如需重新安装，请设置新目录并点击'安装/更新'。"))
                else:
                    self.log_message("⚠️ 目录已不存在。")
                    self.root.after(0, lambda: messagebox.showinfo("完成", "目录已不存在。"))

            except PermissionError:
                err_msg = "删除失败：权限不足或部分文件被占用。\n请确保服务器已停止，并以管理员身份运行本程序。"
                self.log_message(f"❌ {err_msg}")
                self.root.after(0, lambda: messagebox.showerror("删除失败", err_msg))
            except Exception as e:
                err_msg = f"删除过程中发生错误：{str(e)}"
                self.log_message(f"❌ {err_msg}")
                self.root.after(0, lambda: messagebox.showerror("错误", err_msg))
            finally:
                self.set_button_state('check_update', NORMAL)

        thread = threading.Thread(target=_run_delete, daemon=True)
        thread.start()

    def start_server(self):
        steamcmd_dir, server_dir, steamcmd_exe, _ = self.get_paths()
        if not self.install_path_var.get():
            messagebox.showerror("错误", "请先设置安装根目录")
            return

        if not os.path.exists(os.path.join(server_dir, "FactoryServer.exe")):
            messagebox.showerror("错误", "服务器文件不存在，请先安装或更新服务器")
            return

        self.set_button_state('start', DISABLED)
        self.log_message(">>> 正在启动幸福工厂服务器...")

        def _run_server():
            try:
                # 获取代理配置
                proxies = self.get_proxy_config() if self.proxy_enabled else None

                game_port = self.game_port_var.get()
                beacon_port = self.beacon_port_var.get()
                max_players = self.max_players_var.get()

                server_exe = os.path.join(server_dir, "FactoryServer.exe")
                launch_args = [
                    server_exe,
                    f"-Port={game_port}",
                    f"-BeaconPort={beacon_port}",
                    f"-MaxPlayers={max_players}",
                    "-server",
                    "-log"
                ]

                self.log_message(f"启动命令: {' '.join(launch_args)}")

                # 启动服务器进程
                self.server_process = subprocess.Popen(
                    launch_args,
                    cwd=server_dir,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    bufsize=1,
                    universal_newlines=True
                )

                # 实时读取输出
                self.read_subprocess_output(self.server_process, self.log_message)

                # 等待进程结束
                return_code = self.server_process.wait()

                self.server_pid = None
                self.log_message(f"服务器进程已退出，退出码: {return_code}")

                # 检查是否因崩溃退出 (非0) 且开启了自动重启
                if return_code != 0 and self.auto_restart_var.get():
                    self.log_message("检测到服务器异常退出，尝试自动重启...")
                    self.root.after(0, self.start_server) # 在主线程中调用
                else:
                    self.root.after(0, lambda: self._set_server_stopped_ui(return_code))

            except Exception as e:
                self.log_message(f"启动服务器时发生错误: {e}")
                self.root.after(0, lambda: self._set_server_stopped_ui(None))

        thread = threading.Thread(target=_run_server, daemon=True)
        thread.start()

        self.monitoring = True
        # 修复：在服务器启动后立即启用停止和重启按钮
        self.root.after(0, self._set_server_running_ui)

    def _set_server_running_ui(self):
        """设置服务器运行时的UI状态"""
        self.start_btn.config(state=DISABLED)
        self.stop_btn.config(state=NORMAL)
        self.restart_btn.config(state=NORMAL)

    def _set_server_stopped_ui(self, return_code):
        """设置服务器停止时的UI状态"""
        self.start_btn.config(state=NORMAL)
        self.stop_btn.config(state=DISABLED)
        self.restart_btn.config(state=DISABLED)

    def stop_server(self):
        """停止服务器：直接使用 taskkill 强制结束所有相关进程，不尝试优雅关闭"""
        self.log_message(">>> 正在强制停止幸福工厂服务器...")
        
        # 定义需要查杀的进程名列表
        target_processes = [
            "FactoryServer.exe",
            "FactoryServer-Win64-Shipping.exe",
            "FactoryServer-Win64-Shipping-Cmd.exe"
        ]
        
        killed_any = False
        
        for proc_name in target_processes:
            try:
                # 使用 taskkill /IM 进程名 /F 强制结束
                # creationflags=subprocess.CREATE_NO_WINDOW 隐藏命令行窗口
                result = subprocess.run(
                    ['taskkill', '/IM', proc_name, '/F'], 
                    creationflags=subprocess.CREATE_NO_WINDOW,
                    capture_output=True,
                    text=True
                )
                
                # 如果返回码为0，或者输出中包含"成功"，则认为杀死成功
                # 注意：taskkill 即使杀死成功，有时也会返回错误码，主要看输出
                if result.returncode == 0 or "成功" in result.stdout or "successfully terminated" in result.stdout.lower():
                    self.log_message(f"✅ 已强制结束进程: {proc_name}")
                    killed_any = True
                else:
                    # 如果是因为找不到进程而失败 (错误码 128)，则忽略，因为可能本来就没运行
                    if result.returncode == 128:
                        pass 
                    else:
                        # 其他错误记录一下，但不中断流程
                        self.log_message(f"⚠️ 尝试结束 {proc_name} 未成功 (可能未运行): {result.stdout.strip()}")
                        
            except Exception as e:
                self.log_message(f"❌ 执行 taskkill 结束 {proc_name} 时出错: {e}")

        if not killed_any:
            self.log_message("ℹ️ 未发现正在运行的幸福工厂服务器进程，或无需清理。")
        else:
            self.log_message("✅ 所有服务器进程清理完毕。")

        # 重置内部状态
        self.server_process = None
        self.server_pid = None
        self.monitoring = False
        
        # 更新 UI
        self.root.after(0, self._set_server_stopped_ui)

    def restart_server(self):
        self.log_message(">>> 正在重启服务器...")
        self.stop_server()
        time.sleep(2)
        self.start_server()

    def check_port_status(self):
        # 简单的端口状态检查逻辑，这里仅为示例
        # 实际应根据服务器进程是否运行来判断
        if self.server_process and self.server_process.poll() is None:
            return "开启"
        else:
            return "关闭"

    def manual_backup(self):
        """手动触发备份"""
        self.log_message(">>> 手动备份请求已发出")
        # 立即执行备份
        self.perform_backup()

    def open_backup_folder(self):
        """打开备份文件夹"""
        backup_locations = self.config.get("backup_locations", [])
        if not backup_locations:
            messagebox.showwarning("提示", "请先在备份策略中设置至少一个备份位置！")
            return
        
        # 尝试打开第一个本地备份位置
        for location in backup_locations:
            if location["type"] == "local" and location.get("path", ""):
                backup_path = location["path"]
                if os.path.exists(backup_path):
                    try:
                        os.startfile(backup_path)
                        self.log_message(f"📁 已打开备份文件夹: {backup_path}")
                        return
                    except Exception as e:
                        self.log_message(f"❌ 打开备份文件夹失败: {str(e)}")
                        continue
        
        messagebox.showwarning("提示", "未找到有效的本地备份路径或路径不存在！")

    def monitor_server(self):
        # 模拟服务器监控逻辑
        while True:
            if self.monitoring:
                try:
                    # 检查服务器进程是否仍在运行
                    if self.server_process and self.server_process.poll() is not None:
                        # 服务器进程已退出，更新UI
                        self.root.after(0, self._set_server_stopped_ui)
                        self.monitoring = False
                    
                    # 模拟获取服务器状态
                    cpu_percent = psutil.cpu_percent(interval=1)
                    memory_info = psutil.virtual_memory()
                    disk_io = psutil.disk_io_counters()
                    net_io = psutil.net_io_counters()

                    self.cpu_usage = cpu_percent
                    self.memory_usage = memory_info.percent

                    if self.last_disk_stats:
                        current_time = time.time()
                        time_diff = current_time - self.last_disk_stats['time']
                        if time_diff > 0:
                            read_bytes_diff = disk_io.read_bytes - self.last_disk_stats['read_bytes']
                            write_bytes_diff = disk_io.write_bytes - self.last_disk_stats['write_bytes']

                            self.disk_read_speed = (read_bytes_diff / time_diff) / (1024 * 1024)  # MB/s
                            self.disk_write_speed = (write_bytes_diff / time_diff) / (1024 * 1024)  # MB/s

                    self.last_disk_stats = {
                        'read_bytes': disk_io.read_bytes,
                        'write_bytes': disk_io.write_bytes,
                        'time': time.time()
                    }

                    # 模拟网络延迟和玩家数
                    self.ping_value = 50 + (time.time() % 20)  # 50-70ms
                    self.player_count = int(time.time() % 5)  # 0-4人

                except Exception as e:
                    self.log_message(f"监控线程出错: {e}")
            time.sleep(1)

    def update_status_display(self):
        # 模拟状态更新显示
        while True:
            if hasattr(self, 'status_labels'):
                self.status_labels['cpu'].config(text=f"{self.cpu_usage:.1f}%")
                self.status_labels['mem'].config(text=f"{self.memory_usage:.1f}%")
                self.status_labels['disk_read'].config(text=f"{self.disk_read_speed:.2f} MB/s")
                self.status_labels['disk_write'].config(text=f"{self.disk_write_speed:.2f} MB/s")
                self.status_labels['ping'].config(text=f"{int(self.ping_value)} ms")
                self.status_labels['player'].config(text=f"{self.player_count}/{self.max_players_var.get()}")
                self.status_labels['port'].config(text=self.check_port_status())
                
                # 更新下一个备份时间显示
                if self.next_backup_time:
                    self.next_backup_label.config(text=self.next_backup_time.strftime("%Y-%m-%d %H:%M"))
                else:
                    self.next_backup_label.config(text="未计划")
            time.sleep(1)


if __name__ == "__main__":
    controller = SatisfactoryServerController()
    controller.root.mainloop()