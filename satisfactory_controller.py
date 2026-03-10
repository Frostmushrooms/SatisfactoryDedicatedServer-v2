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

# 版本更新相关配置
LOCAL_VERSION = "0.1.4"  # 版本号升级
REMOTE_VERSION_URL = "http://nas.sxtvip.top:5050/version.json"
REMOTE_CHANGELOG_URL = "http://nas.sxtvip.top:5050/changelog.json"
REMOTE_PACKAGE_URL = "http://nas.sxtvip.top:5050/幸福工厂服务器管理器.zip"
TEMP_DOWNLOAD_DIR = "temp_update"
UPDATE_ZIP_NAME = "update_package.zip"
STEAMCMD_DOWNLOAD_URL = "https://steamcdn-a.akamaihd.net/client/installer/steamcmd.zip"
LOCAL_HISTORY_FILE = "update_history.txt"

class SatisfactoryServerController:
    def __init__(self):
        self.themes = {
            "light": {
                "bg": "#FFFFFF", "fg": "#000000", "button_bg": "#E0E0E0", "button_fg": "#000000",
                "entry_bg": "#FFFFFF", "entry_fg": "#000000", "text_bg": "#FFFFFF", "text_fg": "#000000",
                "label_bg": "#FFFFFF", "label_fg": "#000000", "frame_bg": "#F0F0F0",
                "highlight_bg": "#DDDDDD", "highlight_fg": "#000000",
                "footer_fg": "#555555"
            },
            "dark": {
                "bg": "#2B2B2B", "fg": "#FFFFFF", "button_bg": "#404040", "button_fg": "#FFFFFF",
                "entry_bg": "#3C3C3C", "entry_fg": "#FFFFFF", "text_bg": "#1E1E1E", "text_fg": "#CCCCCC",
                "label_bg": "#2B2B2B", "label_fg": "#FFFFFF", "frame_bg": "#363636",
                "highlight_bg": "#555555", "highlight_fg": "#FFFFFF",
                "footer_fg": "#AAAAAA"
            },
            "blue": {
                "bg": "#E6F3FF", "fg": "#003366", "button_bg": "#4A90E2", "button_fg": "#FFFFFF",
                "entry_bg": "#FFFFFF", "entry_fg": "#003366", "text_bg": "#F0F8FF", "text_fg": "#003366",
                "label_bg": "#E6F3FF", "label_fg": "#003366", "frame_bg": "#D1E8FF",
                "highlight_bg": "#7FBFFF", "highlight_fg": "#FFFFFF",
                "footer_fg": "#0055AA"
            },
            "green": {
                "bg": "#E8F5E8", "fg": "#004D00", "button_bg": "#4CAF50", "button_fg": "#FFFFFF",
                "entry_bg": "#FFFFFF", "entry_fg": "#004D00", "text_bg": "#F0FFF0", "text_fg": "#004D00",
                "label_bg": "#E8F5E8", "label_fg": "#004D00", "frame_bg": "#D4EDD4",
                "highlight_bg": "#81C784", "highlight_fg": "#FFFFFF",
                "footer_fg": "#006600"
            },
            "purple": {
                "bg": "#F3E5F5", "fg": "#4A0072", "button_bg": "#9C27B0", "button_fg": "#FFFFFF",
                "entry_bg": "#FFFFFF", "entry_fg": "#4A0072", "text_bg": "#FAF3FC", "text_fg": "#4A0072",
                "label_bg": "#F3E5F5", "label_fg": "#4A0072", "frame_bg": "#E1BEE7",
                "highlight_bg": "#BA68C8", "highlight_fg": "#FFFFFF",
                "footer_fg": "#6A0080"
            }
        }
        
        self.config_file = "server_config.json"
        self.load_config()
        self.current_theme = self.config.get("theme", "light")
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
        self.pending_update_version = "" # 存储待更新的版本号
        
        self.setup_gui()
        self.check_update_on_start()
        self.load_local_history()
        
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
                "theme": "light", 
                "game_port": 7777, 
                "beacon_port": 8888,
                "autosave_count": 5,
                "backup_interval": 30,
                "backup_retain": 10,
                "enable_auto_backup": True
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
                        self.log_message("📜 检测到本地更新历史，最近一次更新内容已记录在 update_history.txt")
            except: pass

    def save_update_log(self, version, log_content):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        entry = f"=== 版本 {version} 更新于 {timestamp} ===\n{log_content}\n\n"
        try:
            with open(LOCAL_HISTORY_FILE, 'a', encoding='utf-8') as f:
                f.write(entry)
        except Exception as e:
            self.log_message(f"保存更新日志失败：{e}")

    def show_changelog_window(self, version, log_text):
        top = Toplevel(self.root)
        top.title(f"版本 {version} 更新日志")
        top.resizable(False, False)
        
        # 获取屏幕尺寸，用于居中
        screen_width = top.winfo_screenwidth()
        screen_height = top.winfo_screenheight()
        
        # --- 关键修改开始：动态计算高度 ---
        
        # 1. 计算文本大概有多少行 (每 50 个字符算一行，最少 5 行)
        lines = max(5, len(log_text) // 50 + 2)
        # 限制最大行数，防止日志太长窗口爆屏 (最多 25 行)
        lines = min(lines, 25)
        
        # 2. 创建文本框，使用计算出的行数
        # 注意：这里不再写死 height=20，而是用变量 lines
        log_display = Text(top, height=lines, width=60, wrap=WORD, 
                          font=("Consolas", 10), bg="#F5F5F5", fg="#333333",
                          relief=FLAT, padx=10, pady=10)
        log_display.pack(fill=BOTH, expand=True, padx=20, pady=(20, 10))
        
        log_display.insert(END, log_text)
        log_display.config(state=DISABLED) # 设为只读
        
        # --- 关键修改结束 ---

        # 创建按钮帧
        btn_frame = Frame(top, bg="#F0F0F0")
        btn_frame.pack(pady=(0, 20)) # 底部留一点边距

        def on_confirm():
            top.destroy()
            self.root.after(100, lambda: self.start_update_process(version))

        def on_cancel():
            top.destroy()

        # 创建按钮
        btn_update = Button(btn_frame, text="立即更新", command=on_confirm, 
                           bg="#4CAF50", fg="white", width=12, height=2, 
                           font=("Arial", 10, "bold"), relief=RAISED)
        btn_update.pack(side=LEFT, padx=20)
        
        # 给“立即更新”按钮一个焦点，方便直接按回车确认
        btn_update.focus_set() 

        btn_later = Button(btn_frame, text="稍后再说", command=on_cancel, 
                          bg="#E0E0E0", fg="black", width=12, height=2, 
                          font=("Arial", 10), relief=RAISED)
        btn_later.pack(side=LEFT, padx=20)

        # 窗口居中逻辑
        top.update_idletasks()
        w = top.winfo_reqwidth()
        h = top.winfo_reqheight()
        x = (screen_width - w) // 2
        y = (screen_height - h) // 2
        top.geometry(f"{w}x{h}+{x}+{y}")
        
        # 设置为模态窗口
        top.grab_set()
    def start_update_process(self, version):
        """后台线程：执行完整的更新流程"""
        self.log_message(f">>> 开始更新流程至版本 {version}...")
        self.set_button_state('check_update', DISABLED)
        
        def _run_update():
            try:
                # 1. 检查并停止服务器
                if self.server_process and self.server_process.poll() is None:
                    self.log_message("检测到服务器运行中，正在停止...")
                    self.stop_server()
                    time.sleep(2) # 等待完全停止
                
                # 2. 清理旧临时文件
                self.cleanup_temp_files()
                
                # 3. 下载更新包
                zip_path = self.download_update_package()
                if not zip_path:
                    raise Exception("下载更新包失败")
                
                # 4. 解压并应用
                if not self.extract_and_apply_update(zip_path):
                    raise Exception("解压或应用更新失败")
                
                # 5. 保存日志
                self.save_update_log(version, self.latest_changelog)
                
                # 6. 重启程序
                self.log_message("更新成功，准备重启...")
                self.root.after(0, lambda: messagebox.showinfo("成功", "更新已完成！程序将立即重启。"))
                self.root.after(1000, self.restart_application)
                
            except Exception as e:
                error_msg = f"更新失败：{str(e)}"
                self.log_message(f"!!! ❌ {error_msg}")
                self.root.after(0, lambda: messagebox.showerror("更新错误", error_msg))
                self.set_button_state('check_update', NORMAL)
            finally:
                self.cleanup_temp_files()

        thread = threading.Thread(target=_run_update, daemon=True)
        thread.start()

    def setup_gui(self):
        self.root = Tk()
        self.root.title(f"幸福工厂服务端控制器 - 版本 {LOCAL_VERSION}")
        
        window_width = 1050
        window_height = 920
        self.root.geometry(f"{window_width}x{window_height}")
        self.root.resizable(False, False)
        
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        x_cordinate = int((screen_width / 2) - (window_width / 2))
        y_cordinate = int((screen_height / 2) - (window_height / 2))
        self.root.geometry(f"+{x_cordinate}+{y_cordinate}")
        
        self.apply_theme()
        
        main_frame = Frame(self.root, bg=self.themes[self.current_theme]["frame_bg"])
        main_frame.pack(fill=BOTH, expand=True, padx=10, pady=10)
        self.widgets_to_update.append(('frame', main_frame))
        
        top_frame = Frame(main_frame, bg=self.themes[self.current_theme]["frame_bg"])
        top_frame.pack(fill=X, pady=5)
        self.widgets_to_update.append(('frame', top_frame))
        
        version_frame = Frame(top_frame, bg=self.themes[self.current_theme]["frame_bg"])
        version_frame.pack(side=LEFT)
        self.widgets_to_update.append(('frame', version_frame))
        
        version_label = Label(version_frame, text=f"当前版本：{LOCAL_VERSION}", 
                              bg=self.themes[self.current_theme]["label_bg"], 
                              fg=self.themes[self.current_theme]["label_fg"])
        version_label.pack(side=LEFT)
        self.widgets_to_update.append(('label', version_label))
        
        self.remote_version_label = Label(version_frame, text="", 
                                          bg=self.themes[self.current_theme]["label_bg"], 
                                          fg=self.themes[self.current_theme]["label_fg"])
        self.remote_version_label.pack(side=LEFT, padx=(15, 5))
        self.widgets_to_update.append(('label', self.remote_version_label))
        
        check_update_btn = Button(version_frame, text="检查更新", 
                                  command=self.check_controller_update,
                                  bg=self.themes[self.current_theme]["button_bg"],
                                  fg=self.themes[self.current_theme]["button_fg"])
        check_update_btn.pack(side=LEFT)
        self.widgets_to_update.append(('button', check_update_btn))
        self.action_buttons['check_update'] = check_update_btn
        
        history_btn = Button(version_frame, text="查看更新历史", 
                             command=self.show_local_history,
                             bg=self.themes[self.current_theme]["button_bg"],
                             fg=self.themes[self.current_theme]["button_fg"])
        history_btn.pack(side=LEFT, padx=5)
        self.widgets_to_update.append(('button', history_btn))
        
        theme_frame = Frame(top_frame, bg=self.themes[self.current_theme]["frame_bg"])
        theme_frame.pack(side=RIGHT)
        self.widgets_to_update.append(('frame', theme_frame))
        
        theme_label = Label(theme_frame, text="主题:", 
                            bg=self.themes[self.current_theme]["label_bg"], 
                            fg=self.themes[self.current_theme]["label_fg"])
        theme_label.pack(side=LEFT)
        self.widgets_to_update.append(('label', theme_label))
        
        self.theme_var = StringVar(value=self.current_theme)
        theme_combo = ttk.Combobox(theme_frame, textvariable=self.theme_var, 
                                   values=list(self.themes.keys()), state="readonly", width=12)
        theme_combo.pack(side=LEFT, padx=(5, 0))
        theme_combo.bind("<<ComboboxSelected>>", self.change_theme)
        
        config_frame = LabelFrame(main_frame, text="路径与配置", 
                                  bg=self.themes[self.current_theme]["frame_bg"], 
                                  fg=self.themes[self.current_theme]["fg"])
        config_frame.pack(fill=X, pady=5)
        self.widgets_to_update.append(('labelframe', config_frame))
        
        path_frame = Frame(config_frame, bg=self.themes[self.current_theme]["frame_bg"])
        path_frame.pack(fill=X, pady=10)
        self.widgets_to_update.append(('frame', path_frame))
        
        Label(path_frame, text="安装根目录:", bg=self.themes[self.current_theme]["label_bg"], 
              fg=self.themes[self.current_theme]["label_fg"], font=("Arial", 10, "bold")).pack(anchor=W)
        
        help_label = Label(path_frame, text="说明：SteamCMD -> <目录>\\steamcmd, 服务器 -> <目录>\\server, 备份 -> <目录>\\backups", 
                           bg=self.themes[self.current_theme]["label_bg"], 
                           fg=self.themes[self.current_theme]["label_fg"], font=("Arial", 9), wraplength=900, justify=LEFT)
        help_label.pack(anchor=W, pady=(5, 10))
        
        self.install_path_var = StringVar(value=self.config.get("install_path", ""))
        Entry(path_frame, textvariable=self.install_path_var, width=60,
              bg=self.themes[self.current_theme]["entry_bg"], fg=self.themes[self.current_theme]["entry_fg"],
              insertbackground=self.themes[self.current_theme]["entry_fg"]).pack(side=LEFT, fill=X, expand=True)
        
        Button(path_frame, text="浏览", command=self.browse_install_path,
               bg=self.themes[self.current_theme]["button_bg"], fg=self.themes[self.current_theme]["button_fg"]).pack(side=RIGHT, padx=(5,0))
        
        archive_frame = LabelFrame(config_frame, text="存档管理与备份策略", 
                                   bg=self.themes[self.current_theme]["frame_bg"], 
                                   fg=self.themes[self.current_theme]["fg"])
        archive_frame.pack(fill=X, pady=10, padx=5)
        self.widgets_to_update.append(('labelframe', archive_frame))
        
        row1 = Frame(archive_frame, bg=self.themes[self.current_theme]["frame_bg"])
        row1.pack(fill=X, pady=5)
        self.widgets_to_update.append(('frame', row1))
        
        Label(row1, text="游戏内自动保存数量 (-autosavecount):", 
              bg=self.themes[self.current_theme]["label_bg"], 
              fg=self.themes[self.current_theme]["label_fg"], width=30, anchor='e').pack(side=LEFT, padx=5)
        
        self.autosave_count_var = IntVar(value=self.config.get("autosave_count", 5))
        Spinbox(row1, from_=1, to=50, textvariable=self.autosave_count_var, width=10,
                bg=self.themes[self.current_theme]["entry_bg"], fg=self.themes[self.current_theme]["entry_fg"],
                buttonbackground=self.themes[self.current_theme]["button_bg"]).pack(side=LEFT, padx=5)
        Label(row1, text="(服务器自动删除旧存档，保留最近N个)", 
              bg=self.themes[self.current_theme]["label_bg"], 
              fg=self.themes[self.current_theme]["label_fg"], font=("Arial", 9)).pack(side=LEFT, padx=5)

        row2 = Frame(archive_frame, bg=self.themes[self.current_theme]["frame_bg"])
        row2.pack(fill=X, pady=5)
        self.widgets_to_update.append(('frame', row2))
        
        self.enable_backup_var = BooleanVar(value=self.config.get("enable_auto_backup", True))
        Checkbutton(row2, text="启用自动备份", variable=self.enable_backup_var,
                   bg=self.themes[self.current_theme]["frame_bg"], fg=self.themes[self.current_theme]["fg"],
                   selectcolor=self.themes[self.current_theme]["highlight_bg"]).pack(side=LEFT, padx=5)
        
        Label(row2, text="备份间隔 (分钟):", 
              bg=self.themes[self.current_theme]["label_bg"], 
              fg=self.themes[self.current_theme]["label_fg"]).pack(side=LEFT, padx=(15, 5))
        
        self.backup_interval_var = IntVar(value=self.config.get("backup_interval", 30))
        Spinbox(row2, from_=5, to=1440, textvariable=self.backup_interval_var, width=10,
                bg=self.themes[self.current_theme]["entry_bg"], fg=self.themes[self.current_theme]["entry_fg"],
                buttonbackground=self.themes[self.current_theme]["button_bg"]).pack(side=LEFT, padx=5)

        row3 = Frame(archive_frame, bg=self.themes[self.current_theme]["frame_bg"])
        row3.pack(fill=X, pady=5)
        self.widgets_to_update.append(('frame', row3))
        
        Label(row3, text="保留备份数量:", 
              bg=self.themes[self.current_theme]["label_bg"], 
              fg=self.themes[self.current_theme]["label_fg"]).pack(side=LEFT, padx=5)
        
        self.backup_retain_var = IntVar(value=self.config.get("backup_retain", 10))
        Spinbox(row3, from_=1, to=100, textvariable=self.backup_retain_var, width=10,
                bg=self.themes[self.current_theme]["entry_bg"], fg=self.themes[self.current_theme]["entry_fg"],
                buttonbackground=self.themes[self.current_theme]["button_bg"]).pack(side=LEFT, padx=5)
        
        Label(row3, text="(自动删除最旧的备份)", 
              bg=self.themes[self.current_theme]["label_bg"], 
              fg=self.themes[self.current_theme]["label_fg"]).pack(side=LEFT, padx=5)
        
        btn_group = Frame(row3, bg=self.themes[self.current_theme]["frame_bg"])
        btn_group.pack(side=RIGHT, padx=10)
        self.widgets_to_update.append(('frame', btn_group))
        
        Button(btn_group, text="立即备份", command=self.manual_backup,
               bg="#4CAF50", fg="white").pack(side=LEFT, padx=5)
        
        Button(btn_group, text="打开备份目录", command=self.open_backup_folder,
               bg=self.themes[self.current_theme]["button_bg"], fg=self.themes[self.current_theme]["button_fg"]).pack(side=LEFT, padx=5)

        settings_frame = Frame(config_frame, bg=self.themes[self.current_theme]["frame_bg"])
        settings_frame.pack(fill=X, pady=5)
        self.widgets_to_update.append(('frame', settings_frame))
        
        Label(settings_frame, text="最大玩家数:", bg=self.themes[self.current_theme]["label_bg"], 
              fg=self.themes[self.current_theme]["label_fg"]).pack(anchor=W)
        
        self.max_players_var = IntVar(value=self.config["max_players"])
        Spinbox(settings_frame, from_=1, to=100, textvariable=self.max_players_var, width=10,
                bg=self.themes[self.current_theme]["entry_bg"], fg=self.themes[self.current_theme]["entry_fg"],
                buttonbackground=self.themes[self.current_theme]["button_bg"]).pack(anchor=W)
        
        port_frame = Frame(settings_frame, bg=self.themes[self.current_theme]["frame_bg"])
        port_frame.pack(fill=X, pady=5)
        self.widgets_to_update.append(('frame', port_frame))
        
        Label(port_frame, text="游戏端口:", bg=self.themes[self.current_theme]["label_bg"], 
              fg=self.themes[self.current_theme]["label_fg"]).pack(side=LEFT)
        
        self.game_port_var = IntVar(value=self.config.get("game_port", 7777))
        Spinbox(port_frame, from_=1, to=65535, textvariable=self.game_port_var, width=10,
                bg=self.themes[self.current_theme]["entry_bg"], fg=self.themes[self.current_theme]["entry_fg"],
                buttonbackground=self.themes[self.current_theme]["button_bg"]).pack(side=LEFT, padx=(5,20))
        
        Label(port_frame, text="Beacon端口:", bg=self.themes[self.current_theme]["label_bg"], 
              fg=self.themes[self.current_theme]["label_fg"]).pack(side=LEFT)
        
        self.beacon_port_var = IntVar(value=self.config.get("beacon_port", 8888))
        Spinbox(port_frame, from_=1, to=65535, textvariable=self.beacon_port_var, width=10,
                bg=self.themes[self.current_theme]["entry_bg"], fg=self.themes[self.current_theme]["entry_fg"],
                buttonbackground=self.themes[self.current_theme]["button_bg"]).pack(side=LEFT, padx=(5,0))
        
        self.branch_var = StringVar(value=self.config["branch"])
        Radiobutton(settings_frame, text="正式版本 (Public)", variable=self.branch_var, value="public", 
                    bg=self.themes[self.current_theme]["frame_bg"], fg=self.themes[self.current_theme]["fg"],
                    selectcolor=self.themes[self.current_theme]["highlight_bg"]).pack(anchor=W)
        Radiobutton(settings_frame, text="实验版本 (Experimental)", variable=self.branch_var, value="experimental", 
                    bg=self.themes[self.current_theme]["frame_bg"], fg=self.themes[self.current_theme]["fg"],
                    selectcolor=self.themes[self.current_theme]["highlight_bg"]).pack(anchor=W)
        
        button_frame = Frame(main_frame, bg=self.themes[self.current_theme]["frame_bg"])
        button_frame.pack(fill=X, pady=10)
        self.widgets_to_update.append(('frame', button_frame))
        
        btn_configs = [
            ("install", "一键安装/更新", self.install_server),
            ("steamcmd", "仅更新 SteamCMD", self.update_steamcmd),
            ("branch", "切换版本分支", self.switch_branch)
        ]
        for key, text, cmd in btn_configs:
            btn = Button(button_frame, text=text, command=cmd,
                   bg=self.themes[self.current_theme]["button_bg"], fg=self.themes[self.current_theme]["button_fg"])
            btn.pack(side=LEFT, padx=5)
            self.widgets_to_update.append(('button', btn))
            self.action_buttons[key] = btn
        
        control_frame = Frame(main_frame, bg=self.themes[self.current_theme]["frame_bg"])
        control_frame.pack(fill=X, pady=10)
        self.widgets_to_update.append(('frame', control_frame))
        
        self.start_btn = Button(control_frame, text="启动服务器", command=self.start_server,
                               bg=self.themes[self.current_theme]["button_bg"], fg=self.themes[self.current_theme]["button_fg"])
        self.start_btn.pack(side=LEFT, padx=5)
        
        self.stop_btn = Button(control_frame, text="停止服务器", command=self.stop_server, state=DISABLED,
                              bg=self.themes[self.current_theme]["button_bg"], fg=self.themes[self.current_theme]["button_fg"])
        self.stop_btn.pack(side=LEFT, padx=5)
        
        self.restart_btn = Button(control_frame, text="重启服务器", command=self.restart_server, state=DISABLED,
                                 bg=self.themes[self.current_theme]["button_bg"], fg=self.themes[self.current_theme]["button_fg"])
        self.restart_btn.pack(side=LEFT, padx=5)
        
        content_split_frame = Frame(main_frame, bg=self.themes[self.current_theme]["frame_bg"])
        content_split_frame.pack(fill=BOTH, expand=True, pady=5)
        self.widgets_to_update.append(('frame', content_split_frame))
        
        left_panel = Frame(content_split_frame, bg=self.themes[self.current_theme]["frame_bg"], width=280)
        left_panel.pack(side=LEFT, fill=Y, padx=(0, 10))
        left_panel.pack_propagate(False)
        self.widgets_to_update.append(('frame', left_panel))
        
        status_frame = LabelFrame(left_panel, text="服务器状态监控", 
                                  bg=self.themes[self.current_theme]["frame_bg"], 
                                  fg=self.themes[self.current_theme]["fg"])
        status_frame.pack(fill=BOTH, expand=True)
        self.widgets_to_update.append(('labelframe', status_frame))
        
        backup_status_frame = Frame(status_frame, bg=self.themes[self.current_theme]["frame_bg"])
        backup_status_frame.pack(fill=X, padx=5, pady=5)
        self.widgets_to_update.append(('frame', backup_status_frame))
        
        Label(backup_status_frame, text="下次备份:", 
              bg=self.themes[self.current_theme]["label_bg"], 
              fg=self.themes[self.current_theme]["label_fg"], font=("Arial", 9, "bold")).pack(anchor=W)
        
        self.next_backup_label = Label(backup_status_frame, text="未计划", 
                                       bg=self.themes[self.current_theme]["label_bg"], 
                                       fg="#FF9800", font=("Arial", 9))
        self.next_backup_label.pack(anchor=W)
        self.widgets_to_update.append(('label', self.next_backup_label))

        grid_frame = Frame(status_frame, bg=self.themes[self.current_theme]["frame_bg"])
        grid_frame.pack(fill=BOTH, expand=True, padx=5, pady=5)
        self.widgets_to_update.append(('frame', grid_frame))
        
        self.status_labels = {}
        metrics = [
            ("cpu", "CPU:", "0%"),
            ("mem", "内存:", "0%"),
            ("disk_read", "硬盘读:", "0 MB/s"),
            ("disk_write", "硬盘写:", "0 MB/s"),
            ("ping", "延迟:", "0 ms"),
            ("player", "玩家:", "0/4"),
            ("port", "端口:", "7777/8888") 
        ]
        
        for i, (key, label_text, default_val) in enumerate(metrics):
            f = Frame(grid_frame, bg=self.themes[self.current_theme]["frame_bg"])
            f.grid(row=i, column=0, sticky='ew', padx=2, pady=2) 
            self.widgets_to_update.append(('frame', f))
            
            lbl = Label(f, text=label_text, bg=self.themes[self.current_theme]["label_bg"], 
                        fg=self.themes[self.current_theme]["label_fg"], font=("Arial", 9), width=6, anchor='e') 
            lbl.pack(side=LEFT)
            self.widgets_to_update.append(('label', lbl))
            
            val_lbl = Label(f, text=default_val, bg=self.themes[self.current_theme]["label_bg"], 
                            fg=self.themes[self.current_theme]["label_fg"], font=("Arial", 9, "bold"), anchor='w')
            val_lbl.pack(side=RIGHT, fill=X, expand=True) 
            self.widgets_to_update.append(('label', val_lbl))
            self.status_labels[key] = val_lbl
            
        right_panel = Frame(content_split_frame, bg=self.themes[self.current_theme]["frame_bg"])
        right_panel.pack(side=RIGHT, fill=BOTH, expand=True)
        self.widgets_to_update.append(('frame', right_panel))
        
        log_frame = LabelFrame(right_panel, text="服务器日志 (调试重点)", 
                               bg=self.themes[self.current_theme]["frame_bg"], 
                               fg=self.themes[self.current_theme]["fg"])
        log_frame.pack(fill=BOTH, expand=True)
        self.widgets_to_update.append(('labelframe', log_frame))
        
        self.status_text = Text(log_frame,
                                bg=self.themes[self.current_theme]["text_bg"], 
                                fg=self.themes[self.current_theme]["text_fg"],
                                font=("Consolas", 9))
        self.status_text.pack(fill=BOTH, expand=True, padx=5, pady=5)
        self.widgets_to_update.append(('text', self.status_text))
        
        scrollbar = Scrollbar(self.status_text)
        scrollbar.pack(side=RIGHT, fill=Y)
        self.status_text.config(yscrollcommand=scrollbar.set)
        scrollbar.config(command=self.status_text.yview)
        
        auto_frame = Frame(main_frame, bg=self.themes[self.current_theme]["frame_bg"])
        auto_frame.pack(fill=X, pady=5)
        self.widgets_to_update.append(('frame', auto_frame))
        
        self.auto_restart_var = BooleanVar(value=self.config["auto_restart"])
        Checkbutton(auto_frame, text="崩溃自动重启", variable=self.auto_restart_var,
                   bg=self.themes[self.current_theme]["frame_bg"], fg=self.themes[self.current_theme]["fg"],
                   selectcolor=self.themes[self.current_theme]["highlight_bg"]).pack(side=LEFT)
        
        self.auto_start_var = BooleanVar(value=self.config["auto_start"])
        Checkbutton(auto_frame, text="开机自启", variable=self.auto_start_var,
                   bg=self.themes[self.current_theme]["frame_bg"], fg=self.themes[self.current_theme]["fg"],
                   selectcolor=self.themes[self.current_theme]["highlight_bg"]).pack(side=LEFT, padx=(20,0))
        
        Button(auto_frame, text="保存设置", command=self.save_settings,
               bg=self.themes[self.current_theme]["button_bg"], fg=self.themes[self.current_theme]["button_fg"]).pack(side=RIGHT)
        
        footer_frame = Frame(main_frame, bg=self.themes[self.current_theme]["frame_bg"])
        footer_frame.pack(fill=X, pady=(10, 0))
        self.widgets_to_update.append(('frame', footer_frame))
        
        separator = ttk.Separator(footer_frame, orient='horizontal')
        separator.pack(fill=X, pady=(0, 5))
        
        author_text = f"作者：冰霜蘑菇 & 千问AI   |   交流QQ群：264127585 (点击复制)"
        self.author_label = Label(footer_frame, text=author_text, 
                                  bg=self.themes[self.current_theme]["frame_bg"], 
                                  fg=self.themes[self.current_theme]["footer_fg"],
                                  font=("Microsoft YaHei", 9),
                                  cursor="hand2") 
        self.author_label.pack(pady=5)
        self.widgets_to_update.append(('label', self.author_label))
        
        self.author_label.bind("<Button-1>", self.copy_qq_group)
        self.author_label.bind("<Enter>", lambda e: self.author_label.config(fg="#0078D7"))
        self.author_label.bind("<Leave>", lambda e: self.apply_theme()) 

        self.monitor_thread = threading.Thread(target=self.monitor_server, daemon=True)
        self.monitor_thread.start()
        
        self.status_update_thread = threading.Thread(target=self.update_status_display, daemon=True)
        self.status_update_thread.start()
        
        self.set_auto_start()

    def show_local_history(self):
        if not os.path.exists(LOCAL_HISTORY_FILE):
            messagebox.showinfo("提示", "暂无本地更新历史记录。\n每次成功更新后会自动记录在此。")
            return
        
        try:
            with open(LOCAL_HISTORY_FILE, 'r', encoding='utf-8') as f:
                content = f.read()
            
            top = Toplevel(self.root)
            top.title("本地更新历史")
            top.geometry("600x500")
            
            x = int((self.root.winfo_screenwidth() / 2) - 300)
            y = int((self.root.winfo_screenheight() / 2) - 250)
            top.geometry(f"+{x}+{y}")
            
            bg_color = self.themes[self.current_theme]["bg"]
            text_bg = self.themes[self.current_theme]["text_bg"]
            text_fg = self.themes[self.current_theme]["text_fg"]
            
            top.configure(bg=bg_color)
            
            text_area = Text(top, wrap=WORD, bg=text_bg, fg=text_fg, font=("Consolas", 10))
            text_area.pack(fill=BOTH, expand=True, padx=10, pady=10)
            text_area.insert(END, content)
            text_area.config(state=DISABLED)
            
            Button(top, text="关闭", command=top.destroy, bg=self.themes[self.current_theme]["button_bg"], fg=self.themes[self.current_theme]["button_fg"]).pack(pady=10)
            
        except Exception as e:
            messagebox.showerror("错误", f"读取历史文件失败：{str(e)}")

    def copy_qq_group(self, event=None):
        qq_group = "264127585"
        self.root.clipboard_clear()
        self.root.clipboard_append(qq_group)
        self.root.update() 
        messagebox.showinfo("复制成功", f"QQ群号 {qq_group} 已复制到剪贴板！\n欢迎加入交流群。")

    def set_button_state(self, key, state):
        if key in self.action_buttons:
            self.action_buttons[key].config(state=state)

    def apply_theme(self):
        theme = self.themes[self.current_theme]
        self.root.configure(bg=theme["bg"])
        for widget_type, widget in self.widgets_to_update:
            if widget_type == 'button':
                widget.configure(bg=theme["button_bg"], fg=theme["button_fg"])
            elif widget_type == 'label':
                if widget == self.author_label:
                    widget.configure(bg=theme["frame_bg"], fg=theme["footer_fg"])
                else:
                    widget.configure(bg=theme["label_bg"], fg=theme["label_fg"])
            elif widget_type == 'entry':
                widget.configure(bg=theme["entry_bg"], fg=theme["entry_fg"], insertbackground=theme["entry_fg"])
            elif widget_type == 'text':
                widget.configure(bg=theme["text_bg"], fg=theme["text_fg"])
            elif widget_type == 'frame':
                widget.configure(bg=theme["frame_bg"])
            elif widget_type == 'labelframe':
                widget.configure(bg=theme["frame_bg"], fg=theme["fg"])
            elif widget_type == 'checkbutton':
                widget.configure(bg=theme["frame_bg"], fg=theme["fg"], selectcolor=theme["highlight_bg"])
            elif widget_type == 'radiobutton':
                widget.configure(bg=theme["frame_bg"], fg=theme["fg"], selectcolor=theme["highlight_bg"])
            elif widget_type == 'spinbox':
                widget.configure(bg=theme["entry_bg"], fg=theme["entry_fg"], buttonbackground=theme["button_bg"])
            elif widget_type == 'separator':
                pass

    def change_theme(self, event=None):
        new_theme = self.theme_var.get()
        if new_theme in self.themes:
            self.current_theme = new_theme
            self.config["theme"] = new_theme
            self.apply_theme()
            self.save_config()
        
    def browse_install_path(self):
        path = filedialog.askdirectory()
        if path: self.install_path_var.set(path)
            
    def save_settings(self):
        self.config.update({
            "install_path": self.install_path_var.get(),
            "max_players": self.max_players_var.get(),
            "auto_restart": self.auto_restart_var.get(),
            "auto_start": self.auto_start_var.get(),
            "branch": self.branch_var.get(),
            "theme": self.current_theme,
            "game_port": self.game_port_var.get(),
            "beacon_port": self.beacon_port_var.get(),
            "autosave_count": self.autosave_count_var.get(),
            "backup_interval": self.backup_interval_var.get(),
            "backup_retain": self.backup_retain_var.get(),
            "enable_auto_backup": self.enable_backup_var.get()
        })
        self.save_config()
        self.set_auto_start()
        
        if self.server_process and self.server_process.poll() is None:
            messagebox.showinfo("提示", "部分设置（如自动保存数量）需要重启服务器后才能生效。\n备份间隔设置已即时更新。")
        else:
            messagebox.showinfo("提示", "设置已保存")
        
    def set_auto_start(self):
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Run", 0, winreg.KEY_SET_VALUE)
            if self.config["auto_start"]:
                winreg.SetValueEx(key, "SatisfactoryServer", 0, winreg.REG_SZ, sys.executable + " " + os.path.abspath(sys.argv[0]))
            else:
                try: winreg.DeleteValue(key, "SatisfactoryServer")
                except FileNotFoundError: pass
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

    def perform_backup(self, source_reason="手动"):
        _, server_dir, _, backup_dir = self.get_paths()
        if not server_dir or not os.path.exists(server_dir):
            if source_reason != "ManualButton":
                return
            messagebox.showerror("错误", "服务器目录不存在")
            return

        if not os.path.exists(backup_dir):
            os.makedirs(backup_dir)

        save_game_dir = os.path.join(server_dir, "FactoryGame", "Saved", "SaveGames", "server")
        
        if not os.path.exists(save_game_dir):
            msg = f"未找到存档目录：{save_game_dir}\n可能是服务器从未运行过或未生成存档。"
            self.log_message(f"⚠️ 备份跳过：{msg}")
            if source_reason == "ManualButton":
                messagebox.showwarning("提示", msg)
            return

        sav_files = [f for f in os.listdir(save_game_dir) if f.endswith('.sav')]
        if not sav_files:
            msg = "存档目录中没有 .sav 文件。"
            self.log_message(f"⚠️ 备份跳过：{msg}")
            if source_reason == "ManualButton":
                messagebox.showwarning("提示", msg)
            return

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        zip_filename = f"Backup_{timestamp}.zip"
        zip_path = os.path.join(backup_dir, zip_filename)

        try:
            self.log_message(f"🔄 开始备份 ({source_reason})... 包含 {len(sav_files)} 个存档文件")
            
            with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for file in sav_files:
                    file_path = os.path.join(save_game_dir, file)
                    arcname = os.path.join("SaveGames", "server", file)
                    zipf.write(file_path, arcname)
            
            file_size_mb = round(os.path.getsize(zip_path) / (1024 * 1024), 2)
            self.log_message(f"✅ 备份成功：{zip_filename} ({file_size_mb} MB)")
            
            self.cleanup_old_backups(backup_dir)
            
            if self.enable_backup_var.get() and self.server_process and self.server_process.poll() is None:
                interval = self.backup_interval_var.get()
                self.next_backup_time = datetime.now() + timedelta(minutes=interval)
                self.update_backup_timer_label()
                
            if source_reason == "ManualButton":
                self.root.after(0, lambda: messagebox.showinfo("成功", f"备份已完成！\n位置：{backup_dir}"))
                
        except Exception as e:
            self.log_message(f"❌ 备份失败：{str(e)}")
            if source_reason == "ManualButton":
                self.root.after(0, lambda: messagebox.showerror("错误", f"备份失败：{str(e)}"))

    def cleanup_old_backups(self, backup_dir):
        try:
            retain_count = self.backup_retain_var.get()
            files = [f for f in os.listdir(backup_dir) if f.startswith("Backup_") and f.endswith(".zip")]
            if len(files) <= retain_count:
                return
            
            files.sort()
            files_to_delete = files[:-retain_count]
            
            for f in files_to_delete:
                os.remove(os.path.join(backup_dir, f))
                self.log_message(f"🗑️ 已删除旧备份：{f}")
        except Exception as e:
            self.log_message(f"清理旧备份时出错：{e}")

    def manual_backup(self):
        self.perform_backup(source_reason="ManualButton")

    def open_backup_folder(self):
        _, _, _, backup_dir = self.get_paths()
        if not backup_dir:
            messagebox.showerror("错误", "请先设置安装根目录")
            return
        if not os.path.exists(backup_dir):
            os.makedirs(backup_dir)
        
        os.startfile(backup_dir)

    def check_backup_schedule(self):
        if not self.enable_backup_var.get():
            return
        
        if not self.server_process or self.server_process.poll() is not None:
            return

        if self.next_backup_time is None:
            interval = self.backup_interval_var.get()
            self.next_backup_time = datetime.now() + timedelta(minutes=interval)
            self.update_backup_timer_label()
            return

        if datetime.now() >= self.next_backup_time:
            self.perform_backup(source_reason="自动定时")

    def update_backup_timer_label(self):
        if not self.enable_backup_var.get() or self.next_backup_time is None:
            txt = "未计划"
            col = "#888888"
        else:
            txt = self.next_backup_time.strftime("%H:%M:%S")
            col = "#FF9800"
        
        def _update():
            self.next_backup_label.config(text=txt, fg=col)
        if threading.current_thread() is threading.main_thread():
            _update()
        else:
            self.root.after(0, _update)

    def install_server(self):
        steamcmd_dir, server_dir, steamcmd_exe, _ = self.get_paths()
        
        if not self.install_path_var.get():
            messagebox.showerror("错误", "请先设置安装根目录")
            return
        
        self.log_message("-" * 30)
        self.log_message(">>> 开始诊断与安装流程...")
        
        if not os.path.exists(steamcmd_exe):
            self.log_message(f"未检测到 SteamCMD: {steamcmd_exe}")
            if messagebox.askyesno("未检测到 SteamCMD", 
                                   f"在安装目录下未找到 SteamCMD。\n是否立即下载并安装到:\n{steamcmd_dir}?"):
                self.download_and_install_steamcmd(steamcmd_dir)
                self.log_message("请先等待 SteamCMD 下载完成提示，然后再次点击'一键安装/更新'。")
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
                install_cmd = [
                    steamcmd_exe, 
                    "+login", "anonymous", 
                    "+force_install_dir", server_dir, 
                    "+app_update", "1690800", 
                    "-beta", self.branch_var.get(), 
                    "+quit"
                ]
                
                self.log_message("执行命令：" + " ".join(install_cmd))
                
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                startupinfo.wShowWindow = subprocess.SW_HIDE
                
                self.log_message("SteamCMD 进程已启动，正在连接 Steam... (此过程可能较慢，请耐心等待日志更新)")
                
                result = subprocess.run(
                    install_cmd, 
                    cwd=steamcmd_dir, 
                    check=True, 
                    timeout=3600, 
                    stdout=subprocess.PIPE, 
                    stderr=subprocess.STDOUT, 
                    stdin=subprocess.DEVNULL,
                    text=True, 
                    encoding='utf-8', 
                    errors='ignore',
                    startupinfo=startupinfo
                )
                
                if result.stdout:
                    lines = result.stdout.splitlines()
                    self.log_message("--- SteamCMD 输出开始 ---")
                    for line in lines:
                        if line.strip():
                            self.log_message(line)
                    self.log_message("--- SteamCMD 输出结束 ---")
                
                def on_success():
                    self.log_message(">>> ✅ 服务器安装/更新成功完成！")
                    messagebox.showinfo("成功", "服务器文件已更新完毕！现在可以启动服务器了。")
                    self.set_button_state('install', NORMAL)
                
                self.root.after(0, on_success)

            except subprocess.TimeoutExpired:
                def on_timeout():
                    self.log_message("!!! ❌ 警告：安装操作超时（超过1小时）。")
                    self.log_message("可能原因：网络极慢、Valve服务器拥堵、或被防火墙拦截。")
                    messagebox.showwarning("超时", "安装操作耗时过长，请检查网络连接或防火墙设置。")
                    self.set_button_state('install', NORMAL)
                self.root.after(0, on_timeout)

            except subprocess.CalledProcessError as e:
                def on_error():
                    self.log_message(f"!!! ❌ 安装失败 (退出码 {e.returncode})")
                    if e.output:
                        lines = e.output.splitlines()
                        self.log_message("--- 错误详情 ---")
                        for line in lines[-30:]:
                            self.log_message(line)
                    messagebox.showerror("安装失败", f"SteamCMD 报告错误。\n退出码：{e.returncode}\n请查看日志详情。")
                    self.set_button_state('install', NORMAL)
                self.root.after(0, on_error)

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

    def download_and_install_steamcmd(self, target_path):
        self.log_message(f"正在从官方源下载 SteamCMD 到 {target_path} ...")
        
        def _run_download():
            try:
                if not os.path.exists(target_path):
                    os.makedirs(target_path)
                
                zip_path = os.path.join(target_path, "steamcmd.zip")
                response = requests.get(STEAMCMD_DOWNLOAD_URL, stream=True, timeout=30)
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
                                if int(progress) % 20 == 0:
                                    self.log_message(f"SteamCMD 下载进度：{progress:.1f}%")
                
                self.log_message("SteamCMD 下载完成，正在解压...")
                with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                    zip_ref.extractall(target_path)
                
                if os.path.exists(zip_path):
                    os.remove(zip_path)
                
                steamcmd_exe = os.path.join(target_path, "steamcmd.exe")
                if os.path.exists(steamcmd_exe):
                    self.log_message(f"✅ SteamCMD 已成功安装到：{target_path}")
                    self.root.after(0, lambda: messagebox.showinfo("成功", "SteamCMD 下载并安装成功！\n现在可以点击'一键安装/更新'来安装服务器了。"))
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
            if messagebox.askyesno("未检测到 SteamCMD", 
                                   f"是否立即从 Valve 官方下载并安装到:\n{steamcmd_dir}?"):
                self.download_and_install_steamcmd(steamcmd_dir)
            return
        
        self.set_button_state('steamcmd', DISABLED)
        self.log_message("开始更新 SteamCMD...")
        
        def _run_steamcmd_update():
            try:
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                startupinfo.wShowWindow = subprocess.SW_HIDE
                
                subprocess.run([steamcmd_exe, "+quit"], cwd=steamcmd_dir, check=True, timeout=300, 
                               stdin=subprocess.DEVNULL, startupinfo=startupinfo)
                
                def on_success():
                    self.log_message("SteamCMD 更新完成")
                    messagebox.showinfo("提示", "SteamCMD 更新完成")
                    self.set_button_state('steamcmd', NORMAL)
                self.root.after(0, on_success)
                
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
        messagebox.showinfo("提示", f"已切换到 {self.branch_var.get()} 版本，请点击'一键安装/更新'以下载对应版本文件")
    
    def parse_version(self, version_str):
        try: return [int(part) for part in version_str.replace("v", "").split(".")]
        except: return [0, 0]
    
    def check_remote_version(self):
        try:
            response = requests.get(REMOTE_VERSION_URL, timeout=10)
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
            response = requests.get(REMOTE_CHANGELOG_URL, timeout=10)
            response.raise_for_status()
            data = response.json()
            log = data.get(version, data.get("default", "暂无详细更新日志。"))
            return log
        except:
            return "无法连接到日志服务器，暂无详细更新日志。"

    def download_update_package(self):
        try:
            if not os.path.exists(TEMP_DOWNLOAD_DIR):
                os.makedirs(TEMP_DOWNLOAD_DIR)
            
            download_path = os.path.join(TEMP_DOWNLOAD_DIR, UPDATE_ZIP_NAME)
            self.log_message(f"开始下载更新包...")
            
            response = requests.get(REMOTE_PACKAGE_URL, stream=True, timeout=30)
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
                            if int(progress) % 10 == 0:
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
                if len(files) == 1 and os.path.isdir(os.path.join(source_dir, files[0])):
                    source_dir = os.path.join(source_dir, files[0])
                
                copied_count = 0
                for root, dirs, files_in_dir in os.walk(source_dir):
                    for file in files_in_dir:
                        src_file = os.path.join(root, file)
                        rel_path = os.path.relpath(src_file, source_dir)
                        dst_file = os.path.join(root_dir, rel_path)
                        
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
        except: pass
    
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
                    messagebox.showinfo("提示", "当前已是最新版本")
            
            self.root.after(0, process_result)

        thread = threading.Thread(target=_run_check, daemon=True)
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
    
    def check_update_on_start(self):
        def check():
            has_update, _ = self.check_remote_version()
            if has_update:
                self.root.after(1000, lambda: self.remote_version_label.config(text="有新版本 available"))
        threading.Thread(target=check, daemon=True).start()
        
    def start_server(self):
        _, server_dir, _, _ = self.get_paths()
        if not server_dir or not os.path.exists(server_dir):
            messagebox.showerror("错误", "请先设置安装目录并安装服务器"); return
        
        try:
            server_exe = os.path.join(server_dir, "FactoryServer.exe")
            if not os.path.exists(server_exe):
                messagebox.showerror("错误", f"未找到 FactoryServer.exe\n请检查路径：{server_exe}\n如果尚未安装，请点击'一键安装/更新'"); return
            
            args = [
                server_exe, 
                f"-MaxPlayers={self.max_players_var.get()}",
                f"-autosavecount={self.autosave_count_var.get()}"
            ]
            
            self.log_message("正在启动服务器...")
            self.log_message(f"参数：MaxPlayers={self.max_players_var.get()}, AutoSaveCount={self.autosave_count_var.get()}")
            self.log_message(f"所需端口：{self.game_port_var.get()} (TCP/UDP), {self.beacon_port_var.get()} (TCP)")
            
            self.server_process = subprocess.Popen(args, cwd=server_dir)
            self.server_pid = self.server_process.pid
            self.log_message(f"服务器进程已启动，PID: {self.server_pid}")
            
            self.next_backup_time = None
            if self.enable_backup_var.get():
                interval = self.backup_interval_var.get()
                self.next_backup_time = datetime.now() + timedelta(minutes=interval)
                self.log_message(f"自动备份已启用，将在 {interval} 分钟后进行首次备份。")
            else:
                self.log_message("自动备份已禁用。")
            self.update_backup_timer_label()
            
            self.start_btn.config(state=DISABLED)
            self.stop_btn.config(state=NORMAL)
            self.restart_btn.config(state=NORMAL)
            self.log_message("服务器已启动")
        except Exception as e:
            self.log_message(f"启动失败：{str(e)}")
            messagebox.showerror("错误", f"启动失败：{str(e)}")
            
    def stop_server(self):
        if self.server_process is None and self.server_pid is None:
            self.log_message("没有正在运行的服务器进程。")
            self.reset_buttons()
            return

        self.log_message("正在停止服务器... (尝试多种方法)")
        
        killed = False
        
        if self.server_process and self.server_process.poll() is None:
            try:
                self.log_message("尝试发送终止信号 (terminate)...")
                self.server_process.terminate()
                try:
                    self.server_process.wait(timeout=5)
                    self.log_message("服务器已通过 terminate 正常停止。")
                    killed = True
                except subprocess.TimeoutExpired:
                    self.log_message("terminate 超时，准备强制杀死...")
            except Exception as e:
                self.log_message(f"terminate 出错：{e}")

        if not killed:
            target_pid = self.server_pid
            if self.server_process and self.server_process.pid:
                target_pid = self.server_process.pid
            
            if target_pid:
                try:
                    self.log_message(f"使用 psutil 强制杀死进程 PID: {target_pid} ...")
                    p = psutil.Process(target_pid)
                    p.kill()
                    p.wait(timeout=5)
                    self.log_message("服务器进程已被强制杀死。")
                    killed = True
                except psutil.NoSuchProcess:
                    self.log_message("进程已经不存在。")
                    killed = True
                except psutil.AccessDenied:
                    self.log_message("权限拒绝，无法杀死进程。请尝试以管理员身份运行本管理器。")
                except Exception as e:
                    self.log_message(f"psutil 杀死失败：{e}")

        self.log_message("扫描并清理可能的残留子进程...")
        try:
            for proc in psutil.process_iter(['pid', 'name']):
                try:
                    if proc.info['name'] and 'FactoryServer' in proc.info['name']:
                        if proc.info['pid'] != os.getpid():
                            self.log_message(f"发现残留进程：{proc.info['name']} (PID: {proc.info['pid']}), 正在杀死...")
                            proc.kill()
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
        except Exception as e:
            self.log_message(f"扫描残留进程时出错：{e}")

        time.sleep(1)
        self.server_process = None
        self.server_pid = None
        self.next_backup_time = None
        self.update_backup_timer_label()
        self.log_message("服务器停止流程完成。")
        self.reset_buttons()

    def reset_buttons(self):
        self.start_btn.config(state=NORMAL)
        self.stop_btn.config(state=DISABLED)
        self.restart_btn.config(state=DISABLED)
                
    def restart_server(self):
        self.log_message("正在重启服务器...")
        self.stop_server()
        time.sleep(3)
        self.start_server()
        
    def check_port_status(self):
        ports = [(self.game_port_var.get(), "G"), (self.beacon_port_var.get(), "B")]
        active_ports = []
        for port, name in ports:
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(1)
                result = sock.connect_ex(('localhost', port))
                sock.close()
                if result == 0: active_ports.append(f"{port}({name})")
            except: pass
        
        g, b = self.game_port_var.get(), self.beacon_port_var.get()
        if active_ports: 
            status_str = f"{g}/{b} OK({','.join(active_ports)})"
            if len(status_str) > 22: 
                status_str = status_str[:19] + "..."
            return status_str
        return f"{g}/{b} 关闭"
    
    def get_ping_time(self, host='localhost', port=7777):
        try:
            start_time = time.time()
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5)
            result = sock.connect_ex((host, port))
            end_time = time.time()
            sock.close()
            if result == 0: return round((end_time - start_time) * 1000, 2)
            return 0
        except: return 0
    
    def get_player_count(self):
        if self.server_process and self.server_process.poll() is None:
            return min(4, self.max_players_var.get())
        return 0
    
    def monitor_server(self):
        last_disk_io = psutil.disk_io_counters()
        last_time = time.time()
        while True:
            try:
                self.cpu_usage = psutil.cpu_percent(interval=1)
                self.memory_usage = psutil.virtual_memory().percent
                
                current_disk_io = psutil.disk_io_counters()
                current_time = time.time()
                
                if last_disk_io and (current_time - last_time) > 0:
                    t_diff = current_time - last_time
                    self.disk_read_speed = round((current_disk_io.read_bytes - last_disk_io.read_bytes) / t_diff / (1024*1024), 2)
                    self.disk_write_speed = round((current_disk_io.write_bytes - last_disk_io.write_bytes) / t_diff / (1024*1024), 2)
                
                last_disk_io = current_disk_io
                last_time = current_time
                
                self.check_backup_schedule()
                
                is_running = False
                if self.server_process and self.server_process.poll() is None:
                    is_running = True
                elif self.server_pid:
                    try:
                        p = psutil.Process(self.server_pid)
                        if p.is_running() and 'FactoryServer' in p.name():
                            is_running = True
                        else:
                            self.server_pid = None
                    except:
                        self.server_pid = None

                if is_running:
                    self.ping_value = self.get_ping_time('localhost', self.game_port_var.get())
                    self.player_count = self.get_player_count()
                else:
                    self.ping_value = 0
                    self.player_count = 0
                
                time.sleep(2)
            except Exception as e:
                time.sleep(5)
                
    def update_status_display(self):
        while True:
            try:
                self.status_labels['cpu'].config(text=f"{self.cpu_usage}%")
                self.status_labels['mem'].config(text=f"{self.memory_usage}%")
                self.status_labels['disk_read'].config(text=f"{self.disk_read_speed} MB/s")
                self.status_labels['disk_write'].config(text=f"{self.disk_write_speed} MB/s")
                self.status_labels['ping'].config(text=f"{self.ping_value} ms")
                self.status_labels['player'].config(text=f"{self.player_count}/{self.max_players_var.get()}")
                self.status_labels['port'].config(text=self.check_port_status())
                time.sleep(1)
            except: time.sleep(1)
                
    def run(self):
        self.root.mainloop()

if __name__ == "__main__":
    app = SatisfactoryServerController()
    app.run()
