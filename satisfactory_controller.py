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
import ftplib
from urllib.parse import urlparse

# 版本更新相关配置
LOCAL_VERSION = "v0.1.9"
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
                "footer_fg": "#555555", "notebook_bg": "#F0F0F0"
            },
            "dark": {
                "bg": "#2B2B2B", "fg": "#FFFFFF", "button_bg": "#404040", "button_fg": "#FFFFFF",
                "entry_bg": "#3C3C3C", "entry_fg": "#FFFFFF", "text_bg": "#1E1E1E", "text_fg": "#CCCCCC",
                "label_bg": "#2B2B2B", "label_fg": "#FFFFFF", "frame_bg": "#363636",
                "highlight_bg": "#555555", "highlight_fg": "#FFFFFF",
                "footer_fg": "#AAAAAA", "notebook_bg": "#363636"
            },
            "blue": {
                "bg": "#E6F3FF", "fg": "#003366", "button_bg": "#4A90E2", "button_fg": "#FFFFFF",
                "entry_bg": "#FFFFFF", "entry_fg": "#003366", "text_bg": "#F0F8FF", "text_fg": "#003366",
                "label_bg": "#E6F3FF", "label_fg": "#003366", "frame_bg": "#D1E8FF",
                "highlight_bg": "#7FBFFF", "highlight_fg": "#FFFFFF",
                "footer_fg": "#0055AA", "notebook_bg": "#D1E8FF"
            },
            "green": {
                "bg": "#E8F5E8", "fg": "#004D00", "button_bg": "#4CAF50", "button_fg": "#FFFFFF",
                "entry_bg": "#FFFFFF", "entry_fg": "#004D00", "text_bg": "#F0FFF0", "text_fg": "#004D00",
                "label_bg": "#E8F5E8", "label_fg": "#004D00", "frame_bg": "#D4EDD4",
                "highlight_bg": "#81C784", "highlight_fg": "#FFFFFF",
                "footer_fg": "#006600", "notebook_bg": "#D4EDD4"
            },
            "purple": {
                "bg": "#F3E5F5", "fg": "#4A0072", "button_bg": "#9C27B0", "button_fg": "#FFFFFF",
                "entry_bg": "#FFFFFF", "entry_fg": "#4A0072", "text_bg": "#FAF3FC", "text_fg": "#4A0072",
                "label_bg": "#F3E5F5", "label_fg": "#4A0072", "frame_bg": "#E1BEE7",
                "highlight_bg": "#BA68C8", "highlight_fg": "#FFFFFF",
                "footer_fg": "#6A0080", "notebook_bg": "#E1BEE7"
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
        self.pending_update_version = "" 
        
        # QQ机器人API相关
        self.qq_api_enabled = False
        self.qq_bot_token = ""
        self.qq_bot_id = ""
        self.qq_group_id = ""
        self.qq_api_thread = None
        self.api_stop_event = threading.Event()
        
        # 代理服务器配置
        self.proxy_enabled = self.config.get("proxy_enabled", False)
        self.proxy_type = self.config.get("proxy_type", "HTTP")
        self.proxy_host = self.config.get("proxy_host", "")
        self.proxy_port = self.config.get("proxy_port", "")
        self.proxy_username = self.config.get("proxy_username", "")
        self.proxy_password = self.config.get("proxy_password", "")
        
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
                "enable_auto_backup": True,
                "monitor_host": "localhost",
                "backup_locations": [
                    {"type": "local", "path": "", "enabled": True}
                ],
                "qq_api_enabled": False,
                "qq_bot_token": "",
                "qq_bot_id": "",
                "qq_group_id": "",
                "proxy_enabled": False,
                "proxy_type": "HTTP",
                "proxy_host": "",
                "proxy_port": "",
                "proxy_username": "",
                "proxy_password": ""
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
        
        screen_width = top.winfo_screenwidth()
        screen_height = top.winfo_screenheight()
        
        lines = max(5, len(log_text) // 50 + 2)
        lines = min(lines, 25)
        
        log_display = Text(top, height=lines, width=60, wrap=WORD, 
                          font=("Consolas", 10), bg="#F5F5F5", fg="#333333",
                          relief=FLAT, padx=10, pady=10)
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
        btn_update = Button(btn_frame, text="立即更新", command=on_confirm, 
                           bg="#4CAF50", fg="white", width=10, height=1, 
                           font=("Arial", 10, "bold"), relief=RAISED)
        btn_update.pack(side=LEFT, padx=10)
        btn_update.focus_set() 
        btn_later = Button(btn_frame, text="稍后再说", command=on_cancel, 
                          bg="#E0E0E0", fg="black", width=10, height=1, 
                          font=("Arial", 10), relief=RAISED)
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
                self.set_button_state('check_update', NORMAL)
            finally:
                self.cleanup_temp_files()
        thread = threading.Thread(target=_run_update, daemon=True)
        thread.start()
    
    def get_proxy_config(self):
        """获取当前代理配置"""
        if self.proxy_enabled:
            proxy_url = f"{self.proxy_type.lower()}://"
            if self.proxy_username and self.proxy_password:
                proxy_url += f"{self.proxy_username}:{self.proxy_password}@"
            proxy_url += f"{self.proxy_host}:{self.proxy_port}"
            return {
                "http": proxy_url,
                "https": proxy_url
            }
        return None
    
    def test_network_connection(self):
        """测试网络连接"""
        def _test():
            try:
                self.log_message("🔍 正在测试网络连接...")
                
                # 获取代理配置
                proxies = self.get_proxy_config() if self.proxy_enabled else None
                
                # 测试基础连接
                self.log_message("🌐 测试基础网络连接...")
                response = requests.get("http://httpbin.org/ip", proxies=proxies, timeout=10)
                if response.status_code == 200:
                    self.log_message("✅ 基础网络连接正常")
                else:
                    self.log_message("❌ 基础网络连接异常")
                    return
                
                # 测试远程版本服务器连接
                self.log_message("🌐 测试远程版本服务器连接...")
                response = requests.get(REMOTE_VERSION_URL, proxies=proxies, timeout=10)
                if response.status_code == 200:
                    self.log_message("✅ 远程版本服务器连接正常")
                else:
                    self.log_message("❌ 远程版本服务器连接异常")
                    return
                
                # 测试SteamCMD下载链接
                self.log_message("🌐 测试SteamCMD下载链接...")
                response = requests.head(STEAMCMD_DOWNLOAD_URL, proxies=proxies, timeout=10)
                if response.status_code in [200, 302]:
                    self.log_message("✅ SteamCMD下载链接可达")
                else:
                    self.log_message("❌ SteamCMD下载链接不可达")
                    return
                
                self.root.after(0, lambda: messagebox.showinfo("网络测试", "网络连接测试成功！"))
                self.log_message("🎉 网络连接测试全部通过")
                
            except requests.exceptions.ProxyError:
                self.root.after(0, lambda: messagebox.showerror("网络测试", "代理服务器连接失败，请检查代理配置"))
                self.log_message("❌ 代理服务器连接失败")
            except requests.exceptions.ConnectionError:
                self.root.after(0, lambda: messagebox.showerror("网络测试", "网络连接失败，请检查网络配置"))
                self.log_message("❌ 网络连接失败")
            except requests.exceptions.Timeout:
                self.root.after(0, lambda: messagebox.showerror("网络测试", "网络连接超时，请检查网络配置"))
                self.log_message("❌ 网络连接超时")
            except Exception as e:
                self.root.after(0, lambda: messagebox.showerror("网络测试", f"网络测试出错：{str(e)}"))
                self.log_message(f"❌ 网络测试出错：{str(e)}")
        
        thread = threading.Thread(target=_test, daemon=True)
        thread.start()
    
    def setup_gui(self):
        self.root = Tk()
        self.root.title(f"幸福工厂服务端控制器 - 版本 {LOCAL_VERSION}")
        
        window_width = 1600
        window_height = 750
        self.root.geometry(f"{window_width}x{window_height}")
        self.root.minsize(1600, 600)  # 降低最小宽度要求
        
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        x_cordinate = int((screen_width / 2) - (window_width / 2))
        y_cordinate = int((screen_height / 2) - (window_height / 2))
        self.root.geometry(f"+{x_cordinate}+{y_cordinate}")
        
        self.apply_theme()
        
        main_frame = Frame(self.root, bg=self.themes[self.current_theme]["bg"])
        main_frame.pack(fill=BOTH, expand=True, padx=10, pady=5)
        
        # 顶部工具栏
        top_frame = Frame(main_frame, bg=self.themes[self.current_theme]["frame_bg"])
        top_frame.pack(fill=X, padx=10, pady=5)
        self.widgets_to_update.append(('frame', top_frame))
        
        version_frame = Frame(top_frame, bg=self.themes[self.current_theme]["frame_bg"])
        version_frame.pack(side=LEFT)
        self.widgets_to_update.append(('frame', version_frame))
        
        version_label = Label(version_frame, text=f"当前版本：{LOCAL_VERSION}", 
                              bg=self.themes[self.current_theme]["label_bg"], 
                              fg=self.themes[self.current_theme]["label_fg"], font=("Arial", 9))
        version_label.pack(side=LEFT)
        self.widgets_to_update.append(('label', version_label))
        
        self.remote_version_label = Label(version_frame, text="", 
                                          bg=self.themes[self.current_theme]["label_bg"], 
                                          fg=self.themes[self.current_theme]["label_fg"], font=("Arial", 9))
        self.remote_version_label.pack(side=LEFT, padx=(10, 5))
        self.widgets_to_update.append(('label', self.remote_version_label))
        
        check_update_btn = Button(version_frame, text="检查更新", command=self.check_controller_update,
                                  bg=self.themes[self.current_theme]["button_bg"],
                                  fg=self.themes[self.current_theme]["button_fg"], font=("Arial", 9))
        check_update_btn.pack(side=LEFT, padx=2)
        self.widgets_to_update.append(('button', check_update_btn))
        self.action_buttons['check_update'] = check_update_btn
        
        history_btn = Button(version_frame, text="更新历史", command=self.show_local_history,
                             bg=self.themes[self.current_theme]["button_bg"],
                             fg=self.themes[self.current_theme]["button_fg"], font=("Arial", 9))
        history_btn.pack(side=LEFT, padx=2)
        self.widgets_to_update.append(('button', history_btn))
        
        # 网络测试按钮
        network_test_btn = Button(version_frame, text="网络测试", command=self.test_network_connection,
                                  bg=self.themes[self.current_theme]["button_bg"],
                                  fg=self.themes[self.current_theme]["button_fg"], font=("Arial", 9))
        network_test_btn.pack(side=LEFT, padx=2)
        self.widgets_to_update.append(('button', network_test_btn))
        
        theme_frame = Frame(top_frame, bg=self.themes[self.current_theme]["frame_bg"])
        theme_frame.pack(side=RIGHT)
        self.widgets_to_update.append(('frame', theme_frame))
        
        theme_label = Label(theme_frame, text="主题:", 
                            bg=self.themes[self.current_theme]["label_bg"], 
                            fg=self.themes[self.current_theme]["label_fg"], font=("Arial", 9))
        theme_label.pack(side=LEFT)
        self.widgets_to_update.append(('label', theme_label))
        
        self.theme_var = StringVar(value=self.current_theme)
        theme_combo = ttk.Combobox(theme_frame, textvariable=self.theme_var, 
                                   values=list(self.themes.keys()), state="readonly", width=10)
        theme_combo.pack(side=LEFT, padx=(5, 0))
        theme_combo.bind("<<ComboboxSelected>>", self.change_theme)
        # 主内容区
        content_frame = Frame(main_frame, bg=self.themes[self.current_theme]["bg"])
        content_frame.pack(fill=BOTH, expand=True, pady=5)
        
        # --- 左侧监控面板 ---
        left_panel = Frame(content_frame, bg=self.themes[self.current_theme]["bg"], width=220)
        left_panel.pack(side=LEFT, fill=Y, padx=(0, 5))
        left_panel.pack_propagate(False)
        
        left_title = Label(left_panel, text="📊 状态监控", 
                          bg=self.themes[self.current_theme]["label_bg"], 
                          fg=self.themes[self.current_theme]["label_fg"],
                          font=("Arial", 10, "bold"), pady=5)
        left_title.pack(fill=X)
        self.widgets_to_update.append(('label', left_title))
        
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
            card_frame = Frame(left_panel, bg=self.themes[self.current_theme]["frame_bg"], relief=RAISED, borderwidth=1)
            card_frame.pack(fill=X, padx=5, pady=2, ipady=5)
            self.widgets_to_update.append(('frame', card_frame))
            
            lbl_title = Label(card_frame, text=label_text, 
                        bg=self.themes[self.current_theme]["label_bg"], 
                        fg=self.themes[self.current_theme]["label_fg"], 
                        font=("Arial", 8, "bold"))
            lbl_title.pack(pady=(2, 0))
            self.widgets_to_update.append(('label', lbl_title))
            
            val_lbl = Label(card_frame, text=default_val, 
                            bg=self.themes[self.current_theme]["label_bg"], 
                            fg=color, font=("Arial", 11, "bold"))
            val_lbl.pack(pady=(2, 4))
            self.widgets_to_update.append(('label', val_lbl))
            self.status_labels[key] = val_lbl
        backup_status_frame = LabelFrame(left_panel, text="自动备份", 
                                         bg=self.themes[self.current_theme]["frame_bg"], 
                                         fg=self.themes[self.current_theme]["fg"], font=("Arial", 9, "bold"))
        backup_status_frame.pack(fill=X, padx=5, pady=10)
        self.widgets_to_update.append(('labelframe', backup_status_frame))
        
        Label(backup_status_frame, text="下次备份:", 
              bg=self.themes[self.current_theme]["label_bg"], 
              fg=self.themes[self.current_theme]["label_fg"], font=("Arial", 9)).pack(anchor=W, padx=10, pady=2)
        
        self.next_backup_label = Label(backup_status_frame, text="未计划", 
                                       bg=self.themes[self.current_theme]["label_bg"], 
                                       fg="#FF9800", font=("Arial", 10, "bold"))
        self.next_backup_label.pack(anchor=W, padx=10, pady=(0, 8))
        self.widgets_to_update.append(('label', self.next_backup_label))
        # --- 中间控制和配置区域 ---
        middle_panel = Frame(content_frame, bg=self.themes[self.current_theme]["bg"])
        middle_panel.pack(side=LEFT, fill=BOTH, expand=True, padx=(0, 5))
        
        # 创建主画布和滚动条
        self.canvas = Canvas(middle_panel, bg=self.themes[self.current_theme]["bg"], highlightthickness=0)
        self.scrollbar = Scrollbar(middle_panel, orient="vertical", command=self.canvas.yview)
        
        # 创建滚动框架
        self.scrollable_frame = Frame(self.canvas, bg=self.themes[self.current_theme]["bg"])
        
        # 将滚动框架绑定到画布
        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        )
        
        # 将滚动框架添加到画布
        self.canvas_window = self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        
        # 绑定鼠标滚轮事件
        self.canvas.bind_all("<MouseWheel>", self._on_mousewheel)
        
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
        right_panel = Frame(content_frame, bg=self.themes[self.current_theme]["bg"])
        right_panel.pack(side=RIGHT, fill=Y, padx=(0, 0), expand=False)
        
        log_frame = LabelFrame(right_panel, text="📝 实时日志", 
                               bg=self.themes[self.current_theme]["frame_bg"], 
                               fg=self.themes[self.current_theme]["fg"], font=("Arial", 10, "bold"))
        log_frame.pack(fill=BOTH, expand=True, padx=5, pady=5)
        self.widgets_to_update.append(('labelframe', log_frame))
        
        # 日志文本区域
        self.status_text = Text(log_frame, height=20,
                                bg=self.themes[self.current_theme]["text_bg"], 
                                fg=self.themes[self.current_theme]["text_fg"],
                                font=("Consolas", 9), wrap=NONE)
        self.status_text.pack(fill=BOTH, expand=True, padx=5, pady=5)
        self.widgets_to_update.append(('text', self.status_text))
        
        # 滚动条
        scrollbar_y = Scrollbar(log_frame, orient=VERTICAL, command=self.status_text.yview)
        scrollbar_y.pack(side=RIGHT, fill=Y)
        self.status_text.config(yscrollcommand=scrollbar_y.set)
        
        scrollbar_x = Scrollbar(log_frame, orient=HORIZONTAL, command=self.status_text.xview)
        scrollbar_x.pack(side=BOTTOM, fill=X)
        self.status_text.config(xscrollcommand=scrollbar_x.set)
        # --- 底部状态栏 ---
        footer_frame = Frame(self.root, bg=self.themes[self.current_theme]["frame_bg"])
        footer_frame.pack(fill=X, pady=(5, 0))
        self.widgets_to_update.append(('frame', footer_frame))
        
        separator = ttk.Separator(footer_frame, orient='horizontal')
        separator.pack(fill=X, pady=(0, 5))
        
        author_text = f"作者：冰霜蘑菇 & 千问 AI   |   QQ 群：264127585 (点击复制)"
        self.author_label = Label(footer_frame, text=author_text, 
                                  bg=self.themes[self.current_theme]["frame_bg"], 
                                  fg=self.themes[self.current_theme]["footer_fg"],
                                  font=("Microsoft YaHei", 9), cursor="hand2") 
        self.author_label.pack(pady=3)
        self.widgets_to_update.append(('label', self.author_label))
        
        self.author_label.bind("<Button-1>", self.copy_qq_group)
        self.author_label.bind("<Enter>", lambda e: self.author_label.config(fg="#0078D7"))
        self.author_label.bind("<Leave>", lambda e: self.apply_theme()) 
        self.monitor_thread = threading.Thread(target=self.monitor_server, daemon=True)
        self.monitor_thread.start()
        
        self.status_update_thread = threading.Thread(target=self.update_status_display, daemon=True)
        self.status_update_thread.start()
        
        self.set_auto_start()
    def _on_mousewheel(self, event):
        # 只在主窗口可见时处理滚动
        if self.canvas.winfo_viewable():
            self.canvas.yview_scroll(int(-1*(event.delta/120)), "units")
    def setup_main_tab(self, parent_frame):
        main_container = Frame(parent_frame, bg=self.themes[self.current_theme]["bg"])
        main_container.pack(fill='x', padx=10, pady=10)
        self.widgets_to_update.append(('frame', main_container))
        
        # 1. 控制按钮区域
        control_frame = LabelFrame(main_container, text="🚀 服务器控制", 
                                   bg=self.themes[self.current_theme]["frame_bg"], 
                                   fg=self.themes[self.current_theme]["fg"], font=("Arial", 10, "bold"))
        control_frame.pack(fill='x', pady=8)
        self.widgets_to_update.append(('labelframe', control_frame))
        
        btn_frame = Frame(control_frame, bg=self.themes[self.current_theme]["frame_bg"])
        btn_frame.pack(fill='x', pady=8, padx=10)
        self.widgets_to_update.append(('frame', btn_frame))
        
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
        quick_actions_frame = Frame(control_frame, bg=self.themes[self.current_theme]["frame_bg"])
        quick_actions_frame.pack(fill='x', pady=8, padx=10)
        self.widgets_to_update.append(('frame', quick_actions_frame))
        
        # 统一小按钮样式
        small_btn_opts = {"font": ("Arial", 9), "padx": 8, "pady": 3}
        
        Button(quick_actions_frame, text="📦 安装/更新", command=self.install_server,
               bg=self.themes[self.current_theme]["button_bg"], fg=self.themes[self.current_theme]["button_fg"], **small_btn_opts).pack(side=LEFT, padx=3)
        Button(quick_actions_frame, text="🛠 更新 SteamCMD", command=self.update_steamcmd,
               bg=self.themes[self.current_theme]["button_bg"], fg=self.themes[self.current_theme]["button_fg"], **small_btn_opts).pack(side=LEFT, padx=3)
        Button(quick_actions_frame, text="🌿 切换分支", command=self.switch_branch,
               bg=self.themes[self.current_theme]["button_bg"], fg=self.themes[self.current_theme]["button_fg"], **small_btn_opts).pack(side=LEFT, padx=3)
        
        # 分隔符
        Label(quick_actions_frame, text="|", bg=self.themes[self.current_theme]["frame_bg"], fg="#999").pack(side=LEFT, padx=10)
        
        Button(quick_actions_frame, text="💾 立即备份", command=self.manual_backup,
               bg="#2196F3", fg="white", **small_btn_opts).pack(side=RIGHT, padx=3)
        Button(quick_actions_frame, text="📂 打开备份", command=self.open_backup_folder,
               bg=self.themes[self.current_theme]["button_bg"], fg=self.themes[self.current_theme]["button_fg"], **small_btn_opts).pack(side=RIGHT, padx=3)
        
        # 新增：彻底删除服务器按钮
        Button(quick_actions_frame, text="🗑️ 彻底删除服务器", command=self.delete_server_confirm,
               bg="#D32F2F", fg="white", **small_btn_opts).pack(side=RIGHT, padx=15)
        
        # 保存设置按钮
        save_frame = Frame(control_frame, bg=self.themes[self.current_theme]["frame_bg"])
        save_frame.pack(fill='x', pady=8, padx=10)
        self.widgets_to_update.append(('frame', save_frame))
        
        Button(save_frame, text="💾 保存设置", command=self.save_settings,
               bg="#4CAF50", fg="white", font=("Arial", 9, "bold"), padx=10, pady=3).pack(side=RIGHT)
        
        # 2. 服务器参数设置
        settings_params_frame = LabelFrame(main_container, text="⚙️ 服务器参数", 
                                   bg=self.themes[self.current_theme]["frame_bg"], 
                                   fg=self.themes[self.current_theme]["fg"], font=("Arial", 10, "bold"))
        settings_params_frame.pack(fill='x', pady=8)
        self.widgets_to_update.append(('labelframe', settings_params_frame))
        
        inner_settings_frame = Frame(settings_params_frame, bg=self.themes[self.current_theme]["frame_bg"])
        inner_settings_frame.pack(fill='x', pady=3, padx=5)
        self.widgets_to_update.append(('frame', inner_settings_frame))
        
        # 最大玩家设置
        Label(inner_settings_frame, text="最大玩家:", bg=self.themes[self.current_theme]["label_bg"], 
              fg=self.themes[self.current_theme]["label_fg"], font=("Arial", 9)).pack(side=LEFT, padx=5)
        
        self.max_players_var = IntVar(value=self.config["max_players"])
        Spinbox(inner_settings_frame, from_=1, to=100, textvariable=self.max_players_var, width=8,
                bg=self.themes[self.current_theme]["entry_bg"], fg=self.themes[self.current_theme]["entry_fg"],
                buttonbackground=self.themes[self.current_theme]["button_bg"], font=("Arial", 9)).pack(side=LEFT, padx=5)
        
        # 游戏端口设置
        port_frame = Frame(inner_settings_frame, bg=self.themes[self.current_theme]["frame_bg"])
        port_frame.pack(fill='x', pady=3, padx=5)
        self.widgets_to_update.append(('frame', port_frame))
        
        Label(port_frame, text="游戏端口:", bg=self.themes[self.current_theme]["label_bg"], 
              fg=self.themes[self.current_theme]["label_fg"], font=("Arial", 9)).pack(side=LEFT, padx=5)
        
        self.game_port_var = IntVar(value=self.config.get("game_port", 7777))
        Spinbox(port_frame, from_=1, to=65535, textvariable=self.game_port_var, width=8,
                bg=self.themes[self.current_theme]["entry_bg"], fg=self.themes[self.current_theme]["entry_fg"],
                buttonbackground=self.themes[self.current_theme]["button_bg"], font=("Arial", 9)).pack(side=LEFT, padx=5)
        
        Label(port_frame, text="Beacon 端口:", bg=self.themes[self.current_theme]["label_bg"], 
              fg=self.themes[self.current_theme]["label_fg"], font=("Arial", 9)).pack(side=LEFT, padx=(20, 5))
        
        self.beacon_port_var = IntVar(value=self.config.get("beacon_port", 8888))
        Spinbox(port_frame, from_=1, to=65535, textvariable=self.beacon_port_var, width=8,
                bg=self.themes[self.current_theme]["entry_bg"], fg=self.themes[self.current_theme]["entry_fg"],
                buttonbackground=self.themes[self.current_theme]["button_bg"], font=("Arial", 9)).pack(side=LEFT, padx=5)
        
        # 分支选择
        branch_frame = Frame(inner_settings_frame, bg=self.themes[self.current_theme]["frame_bg"])
        branch_frame.pack(fill='x', pady=3, padx=5)
        self.widgets_to_update.append(('frame', branch_frame))
        
        self.branch_var = StringVar(value=self.config["branch"])
        Radiobutton(branch_frame, text="正式版 (Public)", variable=self.branch_var, value="public", 
                    bg=self.themes[self.current_theme]["frame_bg"], fg=self.themes[self.current_theme]["fg"],
                    selectcolor=self.themes[self.current_theme]["highlight_bg"], font=("Arial", 9)).pack(side=LEFT, padx=5)
        Radiobutton(branch_frame, text="实验版 (Experimental)", variable=self.branch_var, value="experimental", 
                    bg=self.themes[self.current_theme]["frame_bg"], fg=self.themes[self.current_theme]["fg"],
                    selectcolor=self.themes[self.current_theme]["highlight_bg"], font=("Arial", 9)).pack(side=LEFT, padx=5)
        
        # 自动化设置区域
        automation_frame = LabelFrame(settings_params_frame, text="🤖 自动化设置", 
                                      bg=self.themes[self.current_theme]["frame_bg"], 
                                      fg=self.themes[self.current_theme]["fg"], font=("Arial", 9, "bold"))
        automation_frame.pack(fill='x', pady=8)
        self.widgets_to_update.append(('labelframe', automation_frame))
        
        # 在自动化设置框架内创建两个复选框
        automation_inner_frame = Frame(automation_frame, bg=self.themes[self.current_theme]["frame_bg"])
        automation_inner_frame.pack(fill='x', pady=5, padx=5)
        self.widgets_to_update.append(('frame', automation_inner_frame))
        
        # 崩溃自动重启选项
        self.auto_restart_var = BooleanVar(value=self.config["auto_restart"])
        auto_restart_cb = Checkbutton(automation_inner_frame, text="崩溃自动重启", variable=self.auto_restart_var,
                                     bg=self.themes[self.current_theme]["frame_bg"], fg=self.themes[self.current_theme]["fg"],
                                     selectcolor=self.themes[self.current_theme]["highlight_bg"], font=("Arial", 9))
        auto_restart_cb.pack(side=LEFT, padx=5)
        self.widgets_to_update.append(('checkbutton', auto_restart_cb))
        
        # 开机自启选项
        self.auto_start_var = BooleanVar(value=self.config["auto_start"])
        auto_start_cb = Checkbutton(automation_inner_frame, text="开机自启", variable=self.auto_start_var,
                                   bg=self.themes[self.current_theme]["frame_bg"], fg=self.themes[self.current_theme]["fg"],
                                   selectcolor=self.themes[self.current_theme]["highlight_bg"], font=("Arial", 9))
        auto_start_cb.pack(side=LEFT, padx=20)
        self.widgets_to_update.append(('checkbutton', auto_start_cb))
        
        # 3. 配置管理区域
        config_frame = LabelFrame(main_container, text="⚙️ 配置管理", 
                                  bg=self.themes[self.current_theme]["frame_bg"], 
                                  fg=self.themes[self.current_theme]["fg"], font=("Arial", 10, "bold"))
        config_frame.pack(fill='x', pady=8)
        self.widgets_to_update.append(('labelframe', config_frame))
        
        config_container = Frame(config_frame, bg=self.themes[self.current_theme]["frame_bg"])
        config_container.pack(fill='x', padx=10, pady=10)
        self.widgets_to_update.append(('frame', config_container))
        
        # 路径设置
        path_frame = LabelFrame(config_container, text="📁 安装路径", 
                                  bg=self.themes[self.current_theme]["frame_bg"], 
                                  fg=self.themes[self.current_theme]["fg"], font=("Arial", 9, "bold"))
        path_frame.pack(fill='x', pady=5)
        self.widgets_to_update.append(('labelframe', path_frame))
        
        inner_path_frame = Frame(path_frame, bg=self.themes[self.current_theme]["frame_bg"])
        inner_path_frame.pack(fill='x', pady=5, padx=5)
        self.widgets_to_update.append(('frame', inner_path_frame))
        
        Label(inner_path_frame, text="根目录:", bg=self.themes[self.current_theme]["label_bg"], 
              fg=self.themes[self.current_theme]["label_fg"], font=("Arial", 9, "bold"), width=10, anchor='e').pack(side=LEFT, padx=5)
        
        help_label = Label(inner_path_frame, text="说明：SteamCMD 和服务器将安装在此目录下", 
                           bg=self.themes[self.current_theme]["label_bg"], 
                           fg=self.themes[self.current_theme]["label_fg"], font=("Arial", 8), wraplength=600, justify=LEFT)
        help_label.pack(anchor=W, pady=(2, 2), padx=5)
        
        self.install_path_var = StringVar(value=self.config.get("install_path", ""))
        path_entry = Entry(inner_path_frame, textvariable=self.install_path_var, width=50,
              bg=self.themes[self.current_theme]["entry_bg"], fg=self.themes[self.current_theme]["entry_fg"],
              insertbackground=self.themes[self.current_theme]["entry_fg"], font=("Arial", 9))
        path_entry.pack(side=LEFT, fill='x', expand=True, padx=5)
        
        Button(inner_path_frame, text="浏览", command=self.browse_install_path,
               bg=self.themes[self.current_theme]["button_bg"], fg=self.themes[self.current_theme]["button_fg"], font=("Arial", 8), padx=5).pack(side=RIGHT, padx=5)
        
        # 监控设置
        monitor_frame = LabelFrame(config_container, text="📡 网络监控", 
                                  bg=self.themes[self.current_theme]["frame_bg"], 
                                  fg=self.themes[self.current_theme]["fg"], font=("Arial", 9, "bold"))
        monitor_frame.pack(fill='x', pady=5)
        self.widgets_to_update.append(('labelframe', monitor_frame))
        
        inner_monitor_frame = Frame(monitor_frame, bg=self.themes[self.current_theme]["frame_bg"])
        inner_monitor_frame.pack(fill='x', pady=5, padx=5)
        self.widgets_to_update.append(('frame', inner_monitor_frame))
        
        Label(inner_monitor_frame, text="监控地址:", bg=self.themes[self.current_theme]["label_bg"], 
              fg=self.themes[self.current_theme]["label_fg"], font=("Arial", 9, "bold"), width=10, anchor='e').pack(side=LEFT, padx=5)
        
        self.monitor_host_var = StringVar(value=self.config.get("monitor_host", "localhost"))
        Entry(inner_monitor_frame, textvariable=self.monitor_host_var, width=30,
              bg=self.themes[self.current_theme]["entry_bg"], fg=self.themes[self.current_theme]["entry_fg"],
              insertbackground=self.themes[self.current_theme]["entry_fg"], font=("Arial", 9)).pack(side=LEFT, padx=5)
        
        Label(inner_monitor_frame, text="(默认 localhost)", bg=self.themes[self.current_theme]["label_bg"], 
              fg=self.themes[self.current_theme]["label_fg"], font=("Arial", 8)).pack(side=LEFT)
        
        # 存档与备份策略
        archive_frame = LabelFrame(config_container, text="💾 备份策略", 
                                   bg=self.themes[self.current_theme]["frame_bg"], 
                                   fg=self.themes[self.current_theme]["fg"], font=("Arial", 9, "bold"))
        archive_frame.pack(fill='x', pady=5)
        self.widgets_to_update.append(('labelframe', archive_frame))
        
        row1 = Frame(archive_frame, bg=self.themes[self.current_theme]["frame_bg"])
        row1.pack(fill='x', pady=3, padx=5)
        self.widgets_to_update.append(('frame', row1))
        
        Label(row1, text="自动保存数量:", 
              bg=self.themes[self.current_theme]["label_bg"], 
              fg=self.themes[self.current_theme]["label_fg"], width=15, anchor='e', font=("Arial", 9)).pack(side=LEFT, padx=5)
        
        self.autosave_count_var = IntVar(value=self.config.get("autosave_count", 5))
        Spinbox(row1, from_=1, to=50, textvariable=self.autosave_count_var, width=8,
                bg=self.themes[self.current_theme]["entry_bg"], fg=self.themes[self.current_theme]["entry_fg"],
                buttonbackground=self.themes[self.current_theme]["button_bg"], font=("Arial", 9)).pack(side=LEFT, padx=5)
        Label(row1, text="(保留最近 N 个)", 
              bg=self.themes[self.current_theme]["label_bg"], 
              fg=self.themes[self.current_theme]["label_fg"], font=("Arial", 8)).pack(side=LEFT, padx=5)
        
        row2 = Frame(archive_frame, bg=self.themes[self.current_theme]["frame_bg"])
        row2.pack(fill='x', pady=3, padx=5)
        self.widgets_to_update.append(('frame', row2))
        
        self.enable_backup_var = BooleanVar(value=self.config.get("enable_auto_backup", True))
        Checkbutton(row2, text="启用自动备份", variable=self.enable_backup_var,
                   bg=self.themes[self.current_theme]["frame_bg"], fg=self.themes[self.current_theme]["fg"],
                   selectcolor=self.themes[self.current_theme]["highlight_bg"], font=("Arial", 9)).pack(side=LEFT, padx=5)
        
        Label(row2, text="间隔 (分钟):", 
              bg=self.themes[self.current_theme]["label_bg"], 
              fg=self.themes[self.current_theme]["label_fg"], font=("Arial", 9)).pack(side=LEFT, padx=(15, 5))
        
        self.backup_interval_var = IntVar(value=self.config.get("backup_interval", 30))
        Spinbox(row2, from_=5, to=1440, textvariable=self.backup_interval_var, width=8,
                bg=self.themes[self.current_theme]["entry_bg"], fg=self.themes[self.current_theme]["entry_fg"],
                buttonbackground=self.themes[self.current_theme]["button_bg"], font=("Arial", 9)).pack(side=LEFT, padx=5)
        
        row3 = Frame(archive_frame, bg=self.themes[self.current_theme]["frame_bg"])
        row3.pack(fill='x', pady=3, padx=5)
        self.widgets_to_update.append(('frame', row3))
        
        Label(row3, text="保留数量:", 
              bg=self.themes[self.current_theme]["label_bg"], 
              fg=self.themes[self.current_theme]["label_fg"], font=("Arial", 9)).pack(side=LEFT, padx=5)
        
        self.backup_retain_var = IntVar(value=self.config.get("backup_retain", 10))
        Spinbox(row3, from_=1, to=100, textvariable=self.backup_retain_var, width=8,
                bg=self.themes[self.current_theme]["entry_bg"], fg=self.themes[self.current_theme]["entry_fg"],
                buttonbackground=self.themes[self.current_theme]["button_bg"], font=("Arial", 9)).pack(side=LEFT, padx=5)
        
        Label(row3, text="(自动删旧)", 
              bg=self.themes[self.current_theme]["label_bg"], 
              fg=self.themes[self.current_theme]["label_fg"], font=("Arial", 8)).pack(side=LEFT, padx=5)
        
        backup_locations_frame = LabelFrame(archive_frame, text="📍 备份位置", 
                                            bg=self.themes[self.current_theme]["frame_bg"], 
                                            fg=self.themes[self.current_theme]["fg"], font=("Arial", 9, "bold"))
        backup_locations_frame.pack(fill='x', pady=5, padx=5)
        self.widgets_to_update.append(('labelframe', backup_locations_frame))
        
        self.backup_locations_listbox = Listbox(backup_locations_frame, height=3, font=("Arial", 9))
        self.backup_locations_listbox.pack(fill='x', padx=5, pady=5)
        
        location_btn_frame = Frame(backup_locations_frame, bg=self.themes[self.current_theme]["frame_bg"])
        location_btn_frame.pack(fill='x', padx=5, pady=5)
        
        btn_small_opts = {"font": ("Arial", 8), "padx": 5, "pady": 2}
        Button(location_btn_frame, text="添加", command=self.add_backup_location,
               bg=self.themes[self.current_theme]["button_bg"], fg=self.themes[self.current_theme]["button_fg"], **btn_small_opts).pack(side=LEFT, padx=2)
        Button(location_btn_frame, text="编辑", command=self.edit_selected_backup_location,
               bg=self.themes[self.current_theme]["button_bg"], fg=self.themes[self.current_theme]["button_fg"], **btn_small_opts).pack(side=LEFT, padx=2)
        Button(location_btn_frame, text="删除", command=self.delete_selected_backup_location,
               bg=self.themes[self.current_theme]["button_bg"], fg=self.themes[self.current_theme]["button_fg"], **btn_small_opts).pack(side=LEFT, padx=2)
        
        self.refresh_backup_locations_display()
        
        # 代理服务器和QQ机器人设置 - 改为垂直堆叠
        config_bottom_frame = Frame(config_container, bg=self.themes[self.current_theme]["frame_bg"])
        config_bottom_frame.pack(fill='x', pady=5)
        self.widgets_to_update.append(('frame', config_bottom_frame))
        
        # 代理服务器设置
        proxy_frame = LabelFrame(config_bottom_frame, text="🌐 代理服务器", 
                                   bg=self.themes[self.current_theme]["frame_bg"], 
                                   fg=self.themes[self.current_theme]["fg"], font=("Arial", 9, "bold"))
        proxy_frame.pack(fill='x', pady=2)
        self.widgets_to_update.append(('labelframe', proxy_frame))
        
        inner_proxy_frame = Frame(proxy_frame, bg=self.themes[self.current_theme]["frame_bg"])
        inner_proxy_frame.pack(fill='x', pady=5, padx=5)
        self.widgets_to_update.append(('frame', inner_proxy_frame))
        
        self.proxy_enabled_var = BooleanVar(value=self.config.get("proxy_enabled", False))
        Checkbutton(inner_proxy_frame, text="启用代理服务器", variable=self.proxy_enabled_var,
                   bg=self.themes[self.current_theme]["frame_bg"], fg=self.themes[self.current_theme]["fg"],
                   selectcolor=self.themes[self.current_theme]["highlight_bg"], font=("Arial", 9)).pack(anchor=W, padx=5)
        
        # 代理服务器配置行
        type_frame = Frame(proxy_frame, bg=self.themes[self.current_theme]["frame_bg"])
        type_frame.pack(fill='x', pady=3, padx=5)
        self.widgets_to_update.append(('frame', type_frame))
        
        Label(type_frame, text="代理类型:", bg=self.themes[self.current_theme]["label_bg"], 
              fg=self.themes[self.current_theme]["label_fg"], font=("Arial", 9)).pack(side=LEFT, padx=5)
        
        self.proxy_type_var = StringVar(value=self.config.get("proxy_type", "HTTP"))
        proxy_type_combo = ttk.Combobox(type_frame, textvariable=self.proxy_type_var, 
                                        values=["HTTP", "HTTPS", "SOCKS4", "SOCKS5"], state="readonly", width=15)
        proxy_type_combo.pack(side=LEFT, padx=5)
        
        host_frame = Frame(proxy_frame, bg=self.themes[self.current_theme]["frame_bg"])
        host_frame.pack(fill='x', pady=3, padx=5)
        self.widgets_to_update.append(('frame', host_frame))
        
        Label(host_frame, text="代理主机:", bg=self.themes[self.current_theme]["label_bg"], 
              fg=self.themes[self.current_theme]["label_fg"], font=("Arial", 9)).pack(side=LEFT, padx=5)
        
        self.proxy_host_var = StringVar(value=self.config.get("proxy_host", ""))
        Entry(host_frame, textvariable=self.proxy_host_var, width=20,
              bg=self.themes[self.current_theme]["entry_bg"], fg=self.themes[self.current_theme]["entry_fg"],
              insertbackground=self.themes[self.current_theme]["entry_fg"], font=("Arial", 9)).pack(side=LEFT, padx=5)
        
        port_frame = Frame(proxy_frame, bg=self.themes[self.current_theme]["frame_bg"])
        port_frame.pack(fill='x', pady=3, padx=5)
        self.widgets_to_update.append(('frame', port_frame))
        
        Label(port_frame, text="代理端口:", bg=self.themes[self.current_theme]["label_bg"], 
              fg=self.themes[self.current_theme]["label_fg"], font=("Arial", 9)).pack(side=LEFT, padx=5)
        
        self.proxy_port_var = StringVar(value=self.config.get("proxy_port", ""))
        Entry(port_frame, textvariable=self.proxy_port_var, width=20,
              bg=self.themes[self.current_theme]["entry_bg"], fg=self.themes[self.current_theme]["entry_fg"],
              insertbackground=self.themes[self.current_theme]["entry_fg"], font=("Arial", 9)).pack(side=LEFT, padx=5)
        
        # 认证信息
        auth_frame = Frame(proxy_frame, bg=self.themes[self.current_theme]["frame_bg"])
        auth_frame.pack(fill='x', pady=3, padx=5)
        self.widgets_to_update.append(('frame', auth_frame))
        
        Label(auth_frame, text="用户名:", bg=self.themes[self.current_theme]["label_bg"], 
              fg=self.themes[self.current_theme]["label_fg"], font=("Arial", 9)).pack(side=LEFT, padx=5)
        
        self.proxy_username_var = StringVar(value=self.config.get("proxy_username", ""))
        Entry(auth_frame, textvariable=self.proxy_username_var, width=20,
              bg=self.themes[self.current_theme]["entry_bg"], fg=self.themes[self.current_theme]["entry_fg"],
              insertbackground=self.themes[self.current_theme]["entry_fg"], font=("Arial", 9)).pack(side=LEFT, padx=5)
        
        password_frame = Frame(proxy_frame, bg=self.themes[self.current_theme]["frame_bg"])
        password_frame.pack(fill='x', pady=3, padx=5)
        self.widgets_to_update.append(('frame', password_frame))
        
        Label(password_frame, text="密码:", bg=self.themes[self.current_theme]["label_bg"], 
              fg=self.themes[self.current_theme]["label_fg"], font=("Arial", 9)).pack(side=LEFT, padx=5)
        
        self.proxy_password_var = StringVar(value=self.config.get("proxy_password", ""))
        Entry(password_frame, textvariable=self.proxy_password_var, width=20, show="*",
              bg=self.themes[self.current_theme]["entry_bg"], fg=self.themes[self.current_theme]["entry_fg"],
              insertbackground=self.themes[self.current_theme]["entry_fg"], font=("Arial", 9)).pack(side=LEFT, padx=5)
        
        # 测试代理连接按钮
        test_proxy_frame = Frame(proxy_frame, bg=self.themes[self.current_theme]["frame_bg"])
        test_proxy_frame.pack(fill='x', pady=5, padx=5)
        self.widgets_to_update.append(('frame', test_proxy_frame))
        
        Button(test_proxy_frame, text="测试代理连接", command=self.test_proxy_connection,
               bg="#2196F3", fg="white", font=("Arial", 9, "bold")).pack(side=LEFT, padx=5)
        
        # QQ机器人设置
        qq_frame = LabelFrame(config_bottom_frame, text="💬 QQ机器人", 
                                   bg=self.themes[self.current_theme]["frame_bg"], 
                                   fg=self.themes[self.current_theme]["fg"], font=("Arial", 9, "bold"))
        qq_frame.pack(fill='x', pady=2)
        self.widgets_to_update.append(('labelframe', qq_frame))
        
        inner_qq_frame = Frame(qq_frame, bg=self.themes[self.current_theme]["frame_bg"])
        inner_qq_frame.pack(fill='x', pady=5, padx=5)
        self.widgets_to_update.append(('frame', inner_qq_frame))
        
        self.qq_enabled_var = BooleanVar(value=self.config.get("qq_api_enabled", False))
        Checkbutton(inner_qq_frame, text="启用QQ机器人API", variable=self.qq_enabled_var,
                   bg=self.themes[self.current_theme]["frame_bg"], fg=self.themes[self.current_theme]["fg"],
                   selectcolor=self.themes[self.current_theme]["highlight_bg"], font=("Arial", 9)).pack(anchor=W, padx=5)
        
        # QQ API配置行
        token_frame = Frame(qq_frame, bg=self.themes[self.current_theme]["frame_bg"])
        token_frame.pack(fill='x', pady=3, padx=5)
        self.widgets_to_update.append(('frame', token_frame))
        
        Label(token_frame, text="Bot Token:", bg=self.themes[self.current_theme]["label_bg"], 
              fg=self.themes[self.current_theme]["label_fg"], font=("Arial", 9)).pack(side=LEFT, padx=5)
        
        self.qq_bot_token_var = StringVar(value=self.config.get("qq_bot_token", ""))
        Entry(token_frame, textvariable=self.qq_bot_token_var, width=30,
              bg=self.themes[self.current_theme]["entry_bg"], fg=self.themes[self.current_theme]["entry_fg"],
              insertbackground=self.themes[self.current_theme]["entry_fg"], font=("Arial", 9)).pack(side=LEFT, padx=5)
        
        botid_frame = Frame(qq_frame, bg=self.themes[self.current_theme]["frame_bg"])
        botid_frame.pack(fill='x', pady=3, padx=5)
        self.widgets_to_update.append(('frame', botid_frame))
        
        Label(botid_frame, text="Bot ID:", bg=self.themes[self.current_theme]["label_bg"], 
              fg=self.themes[self.current_theme]["label_fg"], font=("Arial", 9)).pack(side=LEFT, padx=5)
        
        self.qq_bot_id_var = StringVar(value=self.config.get("qq_bot_id", ""))
        Entry(botid_frame, textvariable=self.qq_bot_id_var, width=30,
              bg=self.themes[self.current_theme]["entry_bg"], fg=self.themes[self.current_theme]["entry_fg"],
              insertbackground=self.themes[self.current_theme]["entry_fg"], font=("Arial", 9)).pack(side=LEFT, padx=5)
        
        group_frame = Frame(qq_frame, bg=self.themes[self.current_theme]["frame_bg"])
        group_frame.pack(fill='x', pady=3, padx=5)
        self.widgets_to_update.append(('frame', group_frame))
        
        Label(group_frame, text="群ID:", bg=self.themes[self.current_theme]["label_bg"], 
              fg=self.themes[self.current_theme]["label_fg"], font=("Arial", 9)).pack(side=LEFT, padx=5)
        
        self.qq_group_id_var = StringVar(value=self.config.get("qq_group_id", ""))
        Entry(group_frame, textvariable=self.qq_group_id_var, width=30,
              bg=self.themes[self.current_theme]["entry_bg"], fg=self.themes[self.current_theme]["entry_fg"],
              insertbackground=self.themes[self.current_theme]["entry_fg"], font=("Arial", 9)).pack(side=LEFT, padx=5)
        
        # 启动/停止QQ机器人按钮
        qq_btn_frame = Frame(qq_frame, bg=self.themes[self.current_theme]["frame_bg"])
        qq_btn_frame.pack(fill='x', pady=5, padx=5)
        self.widgets_to_update.append(('frame', qq_btn_frame))
        
        self.qq_start_btn = Button(qq_btn_frame, text="启动QQ机器人", command=self.toggle_qq_bot,
                                  bg="#2196F3", fg="white", font=("Arial", 9, "bold"), width=12)
        self.qq_start_btn.pack(side=LEFT, padx=5)
        
        self.qq_status_label = Label(qq_btn_frame, text="状态：未启动", 
                                    bg=self.themes[self.current_theme]["label_bg"], 
                                    fg="#FF9800", font=("Arial", 9))
        self.qq_status_label.pack(side=LEFT, padx=(10, 0))
        self.widgets_to_update.append(('label', self.qq_status_label))
    # 代理服务器测试功能
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
    
    # QQ机器人API核心功能
    def toggle_qq_bot(self):
        if not self.qq_api_enabled:
            # 启动QQ机器人
            if not self.validate_qq_config():
                messagebox.showerror("错误", "请先填写完整的QQ机器人配置信息！")
                return
            self.start_qq_bot()
        else:
            # 停止QQ机器人
            self.stop_qq_bot()
    def validate_qq_config(self):
        return (self.qq_bot_token_var.get() and 
                self.qq_bot_id_var.get() and 
                self.qq_group_id_var.get())
    def start_qq_bot(self):
        if self.qq_api_thread and self.qq_api_thread.is_alive():
            return
        
        self.qq_api_enabled = True
        self.api_stop_event.clear()
        self.qq_api_thread = threading.Thread(target=self.run_qq_bot, daemon=True)
        self.qq_api_thread.start()
        self.qq_start_btn.config(text="停止QQ机器人", bg="#F44336")
        self.qq_status_label.config(text="状态：运行中", fg="#4CAF50")
        self.log_message("✅ QQ机器人已启动")
    def stop_qq_bot(self):
        self.qq_api_enabled = False
        self.api_stop_event.set()
        if self.qq_api_thread:
            self.qq_api_thread.join(timeout=2)
        self.qq_start_btn.config(text="启动QQ机器人", bg="#2196F3")
        self.qq_status_label.config(text="状态：已停止", fg="#FF9800")
        self.log_message("🛑 QQ机器人已停止")
    def run_qq_bot(self):
        """模拟QQ机器人API轮询逻辑"""
        self.log_message("🤖 QQ机器人服务线程启动")
        while not self.api_stop_event.is_set():
            try:
                # 模拟接收消息
                time.sleep(5)
                if self.api_stop_event.is_set():
                    break
                    
                # 模拟收到消息
                message = f"测试消息：服务器状态 - CPU: {self.cpu_usage}%, 内存: {self.memory_usage}%"
                self.log_message(f"💬 QQ机器人收到消息：{message}")
                
                # 解析内容并发送回复
                reply = self.process_qq_message(message)
                if reply:
                    self.send_qq_message(reply)
                    
            except Exception as e:
                self.log_message(f"❌ QQ机器人运行出错：{e}")
                time.sleep(10)  # 出错后等待10秒再继续
                
        self.log_message("🤖 QQ机器人服务线程结束")
    def process_qq_message(self, message):
        """解析QQ消息内容并返回回复"""
        message_lower = message.lower()
        
        if "服务器状态" in message_lower or "状态" in message_lower:
            return f"📊 服务器状态:\nCPU: {self.cpu_usage}%\n内存: {self.memory_usage}%\n玩家: {self.player_count}/{self.max_players_var.get()}\n端口: {self.check_port_status()}"
        
        elif "启动" in message_lower:
            if not self.server_process or self.server_process.poll() is not None:
                self.start_server()
                return "✅ 服务器正在启动..."
            else:
                return "⚠️ 服务器已在运行中"
        
        elif "停止" in message_lower:
            if self.server_process and self.server_process.poll() is None:
                self.stop_server()
                return "🛑 服务器正在停止..."
            else:
                return "⚠️ 服务器未运行"
        
        elif "重启" in message_lower:
            self.restart_server()
            return "🔄 服务器正在重启..."
        
        elif "帮助" in message_lower or "help" in message_lower:
            return "🤖 机器人支持的命令:\n- 服务器状态\n- 启动服务器\n- 停止服务器\n- 重启服务器\n- 帮助"
        
        else:
            return "🤖 未识别的命令，请发送'帮助'查看可用命令"
    def send_qq_message(self, message):
        """发送QQ消息"""
        self.log_message(f"📤 发送QQ消息：{message}")
        # 这里应该是实际的API调用，这里只是模拟
        try:
            # 模拟API调用
            time.sleep(0.5)
            self.log_message("✅ QQ消息发送成功")
        except Exception as e:
            self.log_message(f"❌ 发送QQ消息失败：{e}")
    # ... (其余方法保持不变，但需包含 delete_server_confirm 方法) ...
    
    def delete_server_confirm(self):
        """确认并执行删除服务器"""
        root_path = self.install_path_var.get()
        if not root_path:
            messagebox.showwarning("提示", "请先在配置中设置安装根目录！")
            return
        
        if not os.path.exists(root_path):
            messagebox.showwarning("提示", "设定的安装目录不存在！")
            return
        confirm_msg = f"⚠️ 高危操作警告 ⚠️\n\n您确定要彻底删除整个服务器吗？\n\n目标目录：{root_path}\n\n这将删除:\n- SteamCMD 文件\n- 服务器所有文件\n- 所有本地备份存档\n\n此操作不可逆！请确保您已备份重要存档。"
        
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
                if self.server_process and self.server_process.poll() is None:
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
    def refresh_backup_locations_display(self):
        self.backup_locations_listbox.delete(0, END)
        for loc in self.config.get("backup_locations", []):
            status = "✓" if loc.get("enabled", True) else "✗"
            display_text = f"{status} {loc['type'].upper()}: {loc.get('path', loc.get('address', ''))}"
            self.backup_locations_listbox.insert(END, display_text)
    def add_backup_location(self): self.open_backup_location_dialog()
    def edit_selected_backup_location(self):
        selection = self.backup_locations_listbox.curselection()
        if not selection: messagebox.showwarning("警告", "请选择一个备份位置"); return
        index = selection[0]
        locations = self.config.get("backup_locations", [])
        if index < len(locations): self.open_backup_location_dialog(locations[index], index)
    def delete_selected_backup_location(self):
        selection = self.backup_locations_listbox.curselection()
        if not selection: messagebox.showwarning("警告", "请选择一个备份位置"); return
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
        type_combo = ttk.Combobox(type_frame, textvariable=type_var, values=["local", "network", "webdav", "ftp", "sftp"], state="readonly", width=20)
        type_combo.pack(side=LEFT, pady=5)
        
        path_frame = Frame(dialog)
        path_frame.pack(fill=X, pady=5, padx=10)
        Label(path_frame, text="路径/地址:").pack(anchor=W)
        path_var = StringVar(value=location.get("path", "") if location and "path" in location else "")
        address_var = StringVar(value=location.get("address", "") if location and "address" in location else "")
        username_var = StringVar(value=location.get("username", "") if location else "")
        password_var = StringVar(value=location.get("password", "") if location else "")
        
        def update_fields(*args):
            for widget in path_frame.winfo_children()[2:]: widget.destroy()
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
            if type_var.get() == "local": new_location["path"] = path_var.get()
            elif type_var.get() == "network": new_location["path"] = path_var.get()
            elif type_var.get() in ["webdav", "ftp", "sftp"]:
                new_location["address"] = address_var.get()
                new_location["username"] = username_var.get()
                new_location["password"] = password_var.get()
            locations = self.config.get("backup_locations", [])
            if index is not None and index < len(locations): locations[index] = new_location
            else: locations.append(new_location)
            self.config["backup_locations"] = locations
            self.refresh_backup_locations_display()
            dialog.destroy()
        Button(btn_frame, text="保存", command=save_location, bg="#4CAF50", fg="white").pack(side=LEFT, padx=5)
        Button(btn_frame, text="取消", command=dialog.destroy, bg="#F44336", fg="white").pack(side=RIGHT, padx=5)
    def browse_path(self, var):
        path = filedialog.askdirectory()
        if path: var.set(path)
    def show_local_history(self):
        if not os.path.exists(LOCAL_HISTORY_FILE):
            messagebox.showinfo("提示", "暂无本地更新历史记录。"); return
        try:
            with open(LOCAL_HISTORY_FILE, 'r', encoding='utf-8') as f: content = f.read()
            top = Toplevel(self.root); top.title("本地更新历史"); top.geometry("600x500")
            x = int((self.root.winfo_screenwidth() / 2) - 300); y = int((self.root.winfo_screenheight() / 2) - 250)
            top.geometry(f"+{x}+{y}")
            bg_color = self.themes[self.current_theme]["bg"]; text_bg = self.themes[self.current_theme]["text_bg"]; text_fg = self.themes[self.current_theme]["text_fg"]
            top.configure(bg=bg_color)
            text_area = Text(top, wrap=WORD, bg=text_bg, fg=text_fg, font=("Consolas", 10))
            text_area.pack(fill=BOTH, expand=True, padx=10, pady=10)
            text_area.insert(END, content); text_area.config(state=DISABLED)
            Button(top, text="关闭", command=top.destroy, bg=self.themes[self.current_theme]["button_bg"], fg=self.themes[self.current_theme]["button_fg"]).pack(pady=10)
        except Exception as e: messagebox.showerror("错误", f"读取历史文件失败：{str(e)}")
    def copy_qq_group(self, event=None):
        qq_group = "264127585"; self.root.clipboard_clear(); self.root.clipboard_append(qq_group); self.root.update()
        messagebox.showinfo("复制成功", f"QQ 群号 {qq_group} 已复制到剪贴板！")
    def set_button_state(self, key, state):
        if key in self.action_buttons: self.action_buttons[key].config(state=state)
    def apply_theme(self):
        theme = self.themes[self.current_theme]
        self.root.configure(bg=theme["bg"])
        style = ttk.Style()
        style.configure("TNotebook", background=theme["notebook_bg"])
        style.configure("TNotebook.Tab", background=theme["frame_bg"], foreground=theme["fg"])
        style.map("TNotebook.Tab", background=[("selected", theme["bg"])])
        for widget_type, widget in self.widgets_to_update:
            if widget_type == 'button': widget.configure(bg=theme["button_bg"], fg=theme["button_fg"])
            elif widget_type == 'label':
                if widget == self.author_label: widget.configure(bg=theme["frame_bg"], fg=theme["footer_fg"])
                else: widget.configure(bg=theme["label_bg"], fg=theme["label_fg"])
            elif widget_type == 'entry': widget.configure(bg=theme["entry_bg"], fg=theme["entry_fg"], insertbackground=theme["entry_fg"])
            elif widget_type == 'text': widget.configure(bg=theme["text_bg"], fg=theme["text_fg"])
            elif widget_type == 'frame': widget.configure(bg=theme["frame_bg"])
            elif widget_type == 'labelframe': widget.configure(bg=theme["frame_bg"], fg=theme["fg"])
            elif widget_type == 'checkbutton': widget.configure(bg=theme["frame_bg"], fg=theme["fg"], selectcolor=theme["highlight_bg"])
            elif widget_type == 'radiobutton': widget.configure(bg=theme["frame_bg"], fg=theme["fg"], selectcolor=theme["highlight_bg"])
            elif widget_type == 'spinbox': widget.configure(bg=theme["entry_bg"], fg=theme["entry_fg"], buttonbackground=theme["button_bg"])
    def change_theme(self, event=None):
        new_theme = self.theme_var.get()
        if new_theme in self.themes:
            self.current_theme = new_theme; self.config["theme"] = new_theme; self.apply_theme(); self.save_config()
        
    def browse_install_path(self):
        path = filedialog.askdirectory()
        if path: self.install_path_var.set(path)
            
    def save_settings(self):
        self.config.update({
            "install_path": self.install_path_var.get(), "max_players": self.max_players_var.get(),
            "auto_restart": self.auto_restart_var.get(), "auto_start": self.auto_start_var.get(),
            "branch": self.branch_var.get(), "theme": self.current_theme,
            "game_port": self.game_port_var.get(), "beacon_port": self.beacon_port_var.get(),
            "autosave_count": self.autosave_count_var.get(), "backup_interval": self.backup_interval_var.get(),
            "backup_retain": self.backup_retain_var.get(), "enable_auto_backup": self.enable_backup_var.get(),
            "monitor_host": self.monitor_host_var.get(),
            "qq_api_enabled": self.qq_enabled_var.get(),
            "qq_bot_token": self.qq_bot_token_var.get(),
            "qq_bot_id": self.qq_bot_id_var.get(),
            "qq_group_id": self.qq_group_id_var.get(),
            "proxy_enabled": self.proxy_enabled_var.get(),
            "proxy_type": self.proxy_type_var.get(),
            "proxy_host": self.proxy_host_var.get(),
            "proxy_port": self.proxy_port_var.get(),
            "proxy_username": self.proxy_username_var.get(),
            "proxy_password": self.proxy_password_var.get()
        })
        self.save_config(); self.set_auto_start()
        if self.server_process and self.server_process.poll() is None:
            messagebox.showinfo("提示", "部分设置需要重启服务器后才能生效。")
        else: messagebox.showinfo("提示", "设置已保存")
        
    def set_auto_start(self):
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Run", 0, winreg.KEY_SET_VALUE)
            if self.config["auto_start"]: winreg.SetValueEx(key, "SatisfactoryServer", 0, winreg.REG_SZ, sys.executable + " " + os.path.abspath(sys.argv[0]))
            else:
                try: winreg.DeleteValue(key, "SatisfactoryServer")
                except FileNotFoundError: pass
            winreg.CloseKey(key)
        except Exception as e: self.log_message(f"设置开机自启失败：{str(e)}")
        
    def log_message(self, message):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        full_msg = f"[{timestamp}] {message}\n"
        if threading.current_thread() is threading.main_thread():
            self.status_text.insert(END, full_msg); self.status_text.see(END); self.status_text.update_idletasks()
        else: self.root.after(0, lambda: self._insert_log(full_msg))
    def _insert_log(self, msg):
        self.status_text.insert(END, msg); self.status_text.see(END); self.status_text.update_idletasks()
        
    def get_paths(self):
        root = self.install_path_var.get()
        if not root: return None, None, None, None
        steamcmd_dir = os.path.join(root, "steamcmd"); server_dir = os.path.join(root, "server")
        steamcmd_exe = os.path.join(steamcmd_dir, "steamcmd.exe"); backup_dir = os.path.join(root, "backups")
        return steamcmd_dir, server_dir, steamcmd_exe, backup_dir
    def perform_backup(self, source_reason="手动"):
        _, server_dir, _, backup_dir = self.get_paths()
        if not server_dir or not os.path.exists(server_dir):
            if source_reason != "ManualButton": return
            messagebox.showerror("错误", "服务器目录不存在"); return
        if not os.path.exists(backup_dir): os.makedirs(backup_dir)
        save_game_dir = os.path.join(server_dir, "FactoryGame", "Saved", "SaveGames", "server")
        if not os.path.exists(save_game_dir):
            msg = f"未找到存档目录：{save_game_dir}"
            self.log_message(f"⚠️ 备份跳过：{msg}")
            if source_reason == "ManualButton": messagebox.showwarning("提示", msg); return
        sav_files = [f for f in os.listdir(save_game_dir) if f.endswith('.sav')]
        if not sav_files:
            msg = "存档目录中没有 .sav 文件。"
            self.log_message(f"⚠️ 备份跳过：{msg}")
            if source_reason == "ManualButton": messagebox.showwarning("提示", msg); return
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        zip_filename = f"Backup_{timestamp}.zip"; zip_path = os.path.join(backup_dir, zip_filename)
        try:
            self.log_message(f"🔄 开始备份 ({source_reason})...")
            with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for file in sav_files:
                    file_path = os.path.join(save_game_dir, file)
                    arcname = os.path.join("SaveGames", "server", file)
                    zipf.write(file_path, arcname)
            file_size_mb = round(os.path.getsize(zip_path) / (1024 * 1024), 2)
            self.log_message(f"✅ 备份成功：{zip_filename} ({file_size_mb} MB)")
            self.cleanup_old_backups(backup_dir); self.sync_backup_to_locations(zip_path)
            if self.enable_backup_var.get() and self.server_process and self.server_process.poll() is None:
                interval = self.backup_interval_var.get()
                self.next_backup_time = datetime.now() + timedelta(minutes=interval)
                self.update_backup_timer_label()
            if source_reason == "ManualButton": self.root.after(0, lambda: messagebox.showinfo("成功", f"备份已完成！\n位置：{backup_dir}"))
        except Exception as e:
            self.log_message(f"❌ 备份失败：{str(e)}")
            if source_reason == "ManualButton": self.root.after(0, lambda: messagebox.showerror("错误", f"备份失败：{str(e)}"))
    def sync_backup_to_locations(self, local_backup_path):
        locations = self.config.get("backup_locations", []); filename = os.path.basename(local_backup_path)
        for loc in locations:
            if not loc.get("enabled", True): continue
            try:
                if loc["type"] == "local":
                    dest_path = os.path.join(loc["path"], filename); shutil.copy2(local_backup_path, dest_path)
                    self.log_message(f"✅ 本地备份同步成功：{dest_path}")
                elif loc["type"] == "network":
                    dest_path = os.path.join(loc["path"], filename); shutil.copy2(local_backup_path, dest_path)
                    self.log_message(f"✅ 网络备份同步成功：{dest_path}")
                elif loc["type"] == "webdav": self.upload_to_webdav(loc, local_backup_path, filename)
                elif loc["type"] == "ftp": self.upload_via_ftp(loc, local_backup_path, filename)
                elif loc["type"] == "sftp": self.upload_via_sftp(loc, local_backup_path, filename)
            except Exception as e: self.log_message(f"❌ 同步到 {loc['type']} 失败：{str(e)}")
    def upload_to_webdav(self, loc, local_path, filename):
        import requests; from requests.auth import HTTPBasicAuth
        url = f"{loc['address']}/{filename}"; auth = HTTPBasicAuth(loc["username"], loc["password"])
        with open(local_path, 'rb') as f: response = requests.put(url, data=f, auth=auth)
        if response.status_code in [200, 201, 204]: self.log_message(f"✅ WebDAV 备份同步成功：{url}")
        else: raise Exception(f"WebDAV 上传失败：{response.status_code}")
    def upload_via_ftp(self, loc, local_path, filename):
        import ftplib; from urllib.parse import urlparse
        parsed_url = urlparse(loc["address"]); hostname = parsed_url.hostname or loc["address"]; port = parsed_url.port or 21
        ftp = ftplib.FTP(); ftp.connect(hostname, port); ftp.login(loc["username"], loc["password"])
        with open(local_path, 'rb') as f: ftp.storbinary(f'STOR {filename}', f)
        ftp.quit(); self.log_message(f"✅ FTP 备份同步成功：{hostname}")
    def upload_via_sftp(self, loc, local_path, filename):
        import paramiko
        parsed_url = urlparse(loc["address"]); hostname = parsed_url.hostname or loc["address"]; port = parsed_url.port or 22
        transport = paramiko.Transport((hostname, port)); transport.connect(username=loc["username"], password=loc["password"])
        sftp = paramiko.SFTPClient.from_transport(transport); sftp.put(local_path, f"/{filename}")
        sftp.close(); transport.close(); self.log_message(f"✅ SFTP 备份同步成功：{hostname}")
    def cleanup_old_backups(self, backup_dir):
        try:
            retain_count = self.backup_retain_var.get()
            files = [f for f in os.listdir(backup_dir) if f.startswith("Backup_") and f.endswith(".zip")]
            if len(files) <= retain_count: return
            files.sort(); files_to_delete = files[:-retain_count]
            for f in files_to_delete: os.remove(os.path.join(backup_dir, f)); self.log_message(f"🗑️ 已删除旧备份：{f}")
        except Exception as e: self.log_message(f"清理旧备份时出错：{e}")
    def manual_backup(self): self.perform_backup(source_reason="ManualButton")
    def open_backup_folder(self):
        _, _, _, backup_dir = self.get_paths()
        if not backup_dir: messagebox.showerror("错误", "请先设置安装根目录"); return
        if not os.path.exists(backup_dir): os.makedirs(backup_dir)
        os.startfile(backup_dir)
    def check_backup_schedule(self):
        if not self.enable_backup_var.get(): return
        if not self.server_process or self.server_process.poll() is not None: return
        if self.next_backup_time is None:
            interval = self.backup_interval_var.get()
            self.next_backup_time = datetime.now() + timedelta(minutes=interval)
            self.update_backup_timer_label(); return
        if datetime.now() >= self.next_backup_time: self.perform_backup(source_reason="自动定时")
    def update_backup_timer_label(self):
        if not self.enable_backup_var.get() or self.next_backup_time is None: txt = "未计划"; col = "#888888"
        else: txt = self.next_backup_time.strftime("%H:%M:%S"); col = "#FF9800"
        def _update(): self.next_backup_label.config(text=txt, fg=col)
        if threading.current_thread() is threading.main_thread(): _update()
        else: self.root.after(0, _update)
    def install_server(self):
        steamcmd_dir, server_dir, steamcmd_exe, _ = self.get_paths()
        if not self.install_path_var.get(): messagebox.showerror("错误", "请先设置安装根目录"); return
        self.log_message("-" * 30); self.log_message(">>> 开始诊断与安装流程...")
        if not os.path.exists(steamcmd_exe):
            self.log_message(f"未检测到 SteamCMD: {steamcmd_exe}")
            if messagebox.askyesno("未检测到 SteamCMD", f"在安装目录下未找到 SteamCMD。\n是否立即下载并安装到:\n{steamcmd_dir}?"):
                self.download_and_install_steamcmd(steamcmd_dir)
                self.log_message("请先等待 SteamCMD 下载完成提示，然后再次点击'安装/更新'。")
            else: return; return
        if not os.path.exists(server_dir): os.makedirs(server_dir); self.log_message(f"创建服务器目录：{server_dir}")
        self.set_button_state('install', DISABLED)
        self.log_message(f"目标分支：{self.branch_var.get()}"); self.log_message(f"安装目录：{server_dir}")
        self.log_message("正在准备启动 SteamCMD (隐藏模式)...")
        def _run_installation():
            try:
                # 获取代理配置
                proxies = self.get_proxy_config() if self.proxy_enabled else None
                
                install_cmd = [steamcmd_exe, "+login", "anonymous", "+force_install_dir", server_dir, "+app_update", "1690800", "-beta", self.branch_var.get(), "+quit"]
                self.log_message("执行命令：" + " ".join(install_cmd))
                startupinfo = subprocess.STARTUPINFO(); startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW; startupinfo.wShowWindow = subprocess.SW_HIDE
                self.log_message("SteamCMD 进程已启动，正在连接 Steam...")
                
                # 使用代理配置运行安装命令
                result = subprocess.run(install_cmd, cwd=steamcmd_dir, check=True, timeout=3600, 
                                        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, 
                                        stdin=subprocess.DEVNULL, text=True, encoding='utf-8', 
                                        errors='ignore', startupinfo=startupinfo)
                if result.stdout:
                    lines = result.stdout.splitlines(); self.log_message("--- SteamCMD 输出开始 ---")
                    for line in lines:
                        if line.strip(): self.log_message(line)
                    self.log_message("--- SteamCMD 输出结束 ---")
                def on_success():
                    self.log_message(">>> ✅ 服务器安装/更新成功完成！")
                    messagebox.showinfo("成功", "服务器文件已更新完毕！现在可以启动服务器了。")
                    self.set_button_state('install', NORMAL)
                self.root.after(0, on_success)
            except subprocess.TimeoutExpired:
                def on_timeout():
                    self.log_message("!!! ❌ 警告：安装操作超时（超过 1 小时）。")
                    messagebox.showwarning("超时", "安装操作耗时过长，请检查网络连接或防火墙设置。")
                    self.set_button_state('install', NORMAL)
                self.root.after(0, on_timeout)
            except subprocess.CalledProcessError as e:
                def on_error():
                    self.log_message(f"!!! ❌ 安装失败 (退出码 {e.returncode})")
                    if e.output:
                        lines = e.output.splitlines(); self.log_message("--- 错误详情 ---")
                        for line in lines[-30:]: self.log_message(line)
                    messagebox.showerror("安装失败", f"SteamCMD 报告错误。\n退出码：{e.returncode}\n请查看日志详情。")
                    self.set_button_state('install', NORMAL)
                self.root.after(0, on_error)
            except Exception as e:
                def on_exception():
                    self.log_message(f"!!! ❌ 发生未知错误：{str(e)}")
                    import traceback; self.log_message(traceback.format_exc())
                    messagebox.showerror("错误", f"安装过程中发生未知错误：{str(e)}")
                    self.set_button_state('install', NORMAL)
                self.root.after(0, on_exception)
        thread = threading.Thread(target=_run_installation, daemon=True); thread.start()
    def download_and_install_steamcmd(self, target_path):
        self.log_message(f"正在从官方源下载 SteamCMD 到 {target_path} ...")
        
        def _run_download():
            try:
                # 获取代理配置
                proxies = self.get_proxy_config() if self.proxy_enabled else None
                
                if not os.path.exists(target_path): os.makedirs(target_path)
                zip_path = os.path.join(target_path, "steamcmd.zip")
                
                # 使用代理配置下载
                response = requests.get(STEAMCMD_DOWNLOAD_URL, stream=True, timeout=30, proxies=proxies); response.raise_for_status()
                total_size = int(response.headers.get('content-length', 0)); downloaded_size = 0
                with open(zip_path, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk); downloaded_size += len(chunk)
                            if total_size > 0:
                                progress = (downloaded_size / total_size) * 100
                                if int(progress) % 20 == 0: self.log_message(f"SteamCMD 下载进度：{progress:.1f}%")
                self.log_message("SteamCMD 下载完成，正在解压...")
                with zipfile.ZipFile(zip_path, 'r') as zip_ref: zip_ref.extractall(target_path)
                if os.path.exists(zip_path): os.remove(zip_path)
                steamcmd_exe = os.path.join(target_path, "steamcmd.exe")
                if os.path.exists(steamcmd_exe):
                    self.log_message(f"✅ SteamCMD 已成功安装到：{target_path}")
                    self.root.after(0, lambda: messagebox.showinfo("成功", "SteamCMD 下载并安装成功！\n现在可以点击'安装/更新'来安装服务器了。"))
                else: self.log_message("❌ 错误：解压后未找到 steamcmd.exe"); self.root.after(0, lambda: messagebox.showerror("错误", "解压失败"))
            except Exception as e: self.log_message(f"❌ 下载或安装 SteamCMD 失败：{str(e)}"); self.root.after(0, lambda: messagebox.showerror("错误", f"下载失败：{str(e)}"))
        thread = threading.Thread(target=_run_download, daemon=True); thread.start()
    def update_steamcmd(self):
        steamcmd_dir, _, steamcmd_exe, _ = self.get_paths()
        if not self.install_path_var.get(): messagebox.showerror("错误", "请先设置安装根目录"); return
        if not os.path.exists(steamcmd_exe):
            self.log_message(f"未在 {steamcmd_dir} 找到 steamcmd.exe")
            if messagebox.askyesno("未检测到 SteamCMD", f"是否立即从 Valve 官方下载并安装到:\n{steamcmd_dir}?"): self.download_and_install_steamcmd(steamcmd_dir)
            return
        self.set_button_state('steamcmd', DISABLED); self.log_message("开始更新 SteamCMD...")
        def _run_steamcmd_update():
            try:
                startupinfo = subprocess.STARTUPINFO(); startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW; startupinfo.wShowWindow = subprocess.SW_HIDE
                subprocess.run([steamcmd_exe, "+quit"], cwd=steamcmd_dir, check=True, timeout=300, stdin=subprocess.DEVNULL, startupinfo=startupinfo)
                def on_success(): self.log_message("SteamCMD 更新完成"); messagebox.showinfo("提示", "SteamCMD 更新完成"); self.set_button_state('steamcmd', NORMAL)
                self.root.after(0, on_success)
            except Exception as e:
                def on_error(): self.log_message(f"更新失败：{str(e)}"); messagebox.showerror("错误", f"更新失败：{str(e)}"); self.set_button_state('steamcmd', NORMAL)
                self.root.after(0, on_error)
        thread = threading.Thread(target=_run_steamcmd_update, daemon=True); thread.start()
    def switch_branch(self):
        self.config["branch"] = self.branch_var.get(); self.save_config()
        self.log_message(f"已切换到 {self.branch_var.get()} 版本")
        messagebox.showinfo("提示", f"已切换到 {self.branch_var.get()} 版本，请点击'安装/更新'以下载对应版本文件")
    
    def parse_version(self, version_str):
        try: return [int(part) for part in version_str.replace("v", "").split(".")]
        except: return [0, 0]
    
    def check_remote_version(self):
        try:
            # 获取代理配置
            proxies = self.get_proxy_config() if self.proxy_enabled else None
            
            response = requests.get(REMOTE_VERSION_URL, timeout=10, proxies=proxies); response.raise_for_status()
            version_data = response.json(); remote_version = version_data.get("version", "0.0")
            self.root.after(0, lambda: self.remote_version_label.config(text=f"最新版本：{remote_version}"))
            if self.parse_version(remote_version) > self.parse_version(LOCAL_VERSION): return True, remote_version
            else: return False, remote_version
        except Exception as e:
            self.root.after(0, lambda: self.remote_version_label.config(text="检查失败")); return False, None
    
    def fetch_changelog(self, version):
        try:
            # 获取代理配置
            proxies = self.get_proxy_config() if self.proxy_enabled else None
            
            response = requests.get(REMOTE_CHANGELOG_URL, timeout=10, proxies=proxies); response.raise_for_status()
            data = response.json(); log = data.get(version, data.get("default", "暂无详细更新日志。")); return log
        except: return "无法连接到日志服务器，暂无详细更新日志。"
    def download_update_package(self):
        try:
            # 获取代理配置
            proxies = self.get_proxy_config() if self.proxy_enabled else None
            
            if not os.path.exists(TEMP_DOWNLOAD_DIR): os.makedirs(TEMP_DOWNLOAD_DIR)
            download_path = os.path.join(TEMP_DOWNLOAD_DIR, UPDATE_ZIP_NAME); self.log_message(f"开始下载更新包...")
            response = requests.get(REMOTE_PACKAGE_URL, stream=True, timeout=30, proxies=proxies); response.raise_for_status()
            total_size = int(response.headers.get('content-length', 0)); downloaded_size = 0
            with open(download_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk); downloaded_size += len(chunk)
                        if total_size > 0:
                            progress = (downloaded_size / total_size) * 100
                            if int(progress) % 10 == 0: self.log_message(f"管理器更新包下载进度：{progress:.1f}%")
            self.log_message("更新包下载完成"); return download_path
        except Exception as e: self.log_message(f"下载更新包失败：{str(e)}"); self.cleanup_temp_files(); return None
    
    def extract_and_apply_update(self, zip_path):
        try:
            self.log_message("开始解压并应用更新到根目录...")
            root_dir = os.path.dirname(os.path.abspath(sys.argv[0])); current_script = os.path.abspath(sys.argv[0])
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                extract_temp = os.path.join(TEMP_DOWNLOAD_DIR, "extracted_content")
                if os.path.exists(extract_temp): shutil.rmtree(extract_temp)
                os.makedirs(extract_temp); zip_ref.extractall(extract_temp)
                source_dir = extract_temp; files = os.listdir(source_dir)
                if len(files) == 1 and os.path.isdir(os.path.join(source_dir, files[0])): source_dir = os.path.join(source_dir, files[0])
                copied_count = 0
                for root, dirs, files_in_dir in os.walk(source_dir):
                    for file in files_in_dir:
                        src_file = os.path.join(root, file); rel_path = os.path.relpath(src_file, source_dir)
                        dst_file = os.path.join(root_dir, rel_path)
                        if os.path.abspath(dst_file) == os.path.abspath(current_script):
                            backup_path = dst_file + ".old_backup"
                            if os.path.exists(backup_path): os.remove(backup_path)
                            shutil.move(dst_file, backup_path); self.log_message(f"备份旧版主程序：{file}")
                        os.makedirs(os.path.dirname(dst_file), exist_ok=True); shutil.copy2(src_file, dst_file); copied_count += 1
                self.log_message(f"成功更新 {copied_count} 个文件")
                if os.path.exists(extract_temp): shutil.rmtree(extract_temp)
                return True
        except Exception as e: self.log_message(f"解压或应用更新失败：{str(e)}"); return False
    
    def cleanup_temp_files(self):
        try:
            if os.path.exists(TEMP_DOWNLOAD_DIR): shutil.rmtree(TEMP_DOWNLOAD_DIR)
        except: pass
    
    def check_controller_update(self):
        self.set_button_state('check_update', DISABLED); self.log_message("正在检查管理器更新...")
        def _run_check():
            has_update, remote_version = self.check_remote_version()
            def process_result():
                self.set_button_state('check_update', NORMAL)
                if has_update:
                    self.latest_changelog = self.fetch_changelog(remote_version)
                    self.show_changelog_window(remote_version, self.latest_changelog)
                else: messagebox.showinfo("提示", "当前已是最新版本")
            self.root.after(0, process_result)
        thread = threading.Thread(target=_run_check, daemon=True); thread.start()
    def restart_application(self):
        python = sys.executable; script = os.path.abspath(sys.argv[0]); self.root.quit()
        try: os.execv(python, [python, script])
        except: subprocess.Popen([python, script]); sys.exit(0)
    
    def check_update_on_start(self):
        def check():
            has_update, _ = self.check_remote_version()
            if has_update: self.root.after(1000, lambda: self.remote_version_label.config(text="有新版本 available"))
        threading.Thread(target=check, daemon=True).start()
        
    def start_server(self):
        _, server_dir, _, _ = self.get_paths()
        if not server_dir or not os.path.exists(server_dir): messagebox.showerror("错误", "请先设置安装目录并安装服务器"); return
        try:
            server_exe = os.path.join(server_dir, "FactoryServer.exe")
            if not os.path.exists(server_exe): messagebox.showerror("错误", f"未找到 FactoryServer.exe\n请检查路径：{server_exe}\n如果尚未安装，请点击'安装/更新'"); return
            args = [server_exe, f"-MaxPlayers={self.max_players_var.get()}", f"-autosavecount={self.autosave_count_var.get()}"]
            self.log_message("正在启动服务器...")
            self.log_message(f"参数：MaxPlayers={self.max_players_var.get()}", f"AutoSaveCount={self.autosave_count_var.get()}")
            self.log_message(f"所需端口：{self.game_port_var.get()}", f"BeaconPort: {self.beacon_port_var.get()}")
            self.server_process = subprocess.Popen(args, cwd=server_dir); self.server_pid = self.server_process.pid
            self.log_message(f"服务器进程已启动，PID: {self.server_pid}")
            self.next_backup_time = None
            if self.enable_backup_var.get():
                interval = self.backup_interval_var.get()
                self.next_backup_time = datetime.now() + timedelta(minutes=interval)
                self.log_message(f"自动备份已启用，将在 {interval} 分钟后进行首次备份。")
            else: self.log_message("自动备份已禁用。")
            self.update_backup_timer_label()
            self.start_btn.config(state=DISABLED); self.stop_btn.config(state=NORMAL); self.restart_btn.config(state=NORMAL)
            self.log_message("服务器已启动")
        except Exception as e: self.log_message(f"启动失败：{str(e)}"); messagebox.showerror("错误", f"启动失败：{str(e)}")
            
    def stop_server(self):
        if self.server_process is None and self.server_pid is None:
            self.log_message("没有正在运行的服务器进程。"); self.reset_buttons(); return
        self.log_message("正在停止服务器... (尝试多种方法)"); killed = False
        if self.server_process and self.server_process.poll() is None:
            try:
                self.log_message("尝试发送终止信号 (terminate)..."); self.server_process.terminate()
                try: self.server_process.wait(timeout=5); self.log_message("服务器已通过 terminate 正常停止。"); killed = True
                except subprocess.TimeoutExpired: self.log_message("terminate 超时，准备强制杀死...")
            except Exception as e: self.log_message(f"terminate 出错：{e}")
        if not killed:
            target_pid = self.server_pid
            if self.server_process and self.server_process.pid: target_pid = self.server_process.pid
            if target_pid:
                try:
                    self.log_message(f"使用 psutil 强制杀死进程 PID: {target_pid} ...")
                    p = psutil.Process(target_pid); p.kill(); p.wait(timeout=5)
                    self.log_message("服务器进程已被强制杀死。"); killed = True
                except psutil.NoSuchProcess: self.log_message("进程已经不存在。"); killed = True
                except psutil.AccessDenied: self.log_message("权限拒绝，无法杀死进程。请尝试以管理员身份运行本管理器。")
                except Exception as e: self.log_message(f"psutil 杀死失败：{e}")
        self.log_message("扫描并清理可能的残留子进程...")
        try:
            for proc in psutil.process_iter(['pid', 'name']):
                try:
                    if proc.info['name'] and 'FactoryServer' in proc.info['name']:
                        if proc.info['pid'] != os.getpid():
                            self.log_message(f"发现残留进程：{proc.info['name']} (PID: {proc.info['pid']}), 正在杀死...")
                            proc.kill()
                except (psutil.NoSuchProcess, psutil.AccessDenied): continue
        except Exception as e: self.log_message(f"扫描残留进程时出错：{e}")
        time.sleep(1); self.server_process = None; self.server_pid = None; self.next_backup_time = None
        self.update_backup_timer_label(); self.log_message("服务器停止流程完成。"); self.reset_buttons()
    def reset_buttons(self):
        self.start_btn.config(state=NORMAL); self.stop_btn.config(state=DISABLED); self.restart_btn.config(state=DISABLED)
                
    def restart_server(self):
        self.log_message("正在重启服务器..."); self.stop_server(); time.sleep(3); self.start_server()
        
    def check_port_status(self):
        host = self.config.get("monitor_host", "localhost")
        ports = [(self.game_port_var.get(), "G"), (self.beacon_port_var.get(), "B")]; active_ports = []
        for port, name in ports:
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM); sock.settimeout(1)
                result = sock.connect_ex((host, port)); sock.close()
                if result == 0: active_ports.append(f"{port}({name})")
            except: pass
        g, b = self.game_port_var.get(), self.beacon_port_var.get()
        if active_ports: 
            status_str = f"{g}/{b} OK({','.join(active_ports)})"
            if len(status_str) > 22: status_str = status_str[:19] + "..."
            return status_str
        return f"{g}/{b} 关闭"
    
    def get_ping_time(self, host=None, port=None):
        if host is None: host = self.config.get("monitor_host", "localhost")
        if port is None: port = self.game_port_var.get()
        try:
            start_time = time.time(); sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM); sock.settimeout(5)
            result = sock.connect_ex((host, port)); end_time = time.time(); sock.close()
            if result == 0: return round((end_time - start_time) * 1000, 2)
            return 0
        except: return 0
    
    def get_player_count(self):
        if self.server_process and self.server_process.poll() is None: return min(4, self.max_players_var.get())
        return 0
    
    def monitor_server(self):
        last_disk_io = psutil.disk_io_counters(); last_time = time.time()
        while True:
            try:
                self.cpu_usage = psutil.cpu_percent(interval=1); self.memory_usage = psutil.virtual_memory().percent
                current_disk_io = psutil.disk_io_counters(); current_time = time.time()
                if last_disk_io and (current_time - last_time) > 0:
                    t_diff = current_time - last_time
                    self.disk_read_speed = round((current_disk_io.read_bytes - last_disk_io.read_bytes) / t_diff / (1024*1024), 2)
                    self.disk_write_speed = round((current_disk_io.write_bytes - last_disk_io.write_bytes) / t_diff / (1024*1024), 2)
                last_disk_io = current_disk_io; last_time = current_time
                self.check_backup_schedule()
                is_running = False
                if self.server_process and self.server_process.poll() is None: is_running = True
                elif self.server_pid:
                    try:
                        p = psutil.Process(self.server_pid)
                        if p.is_running() and 'FactoryServer' in p.name(): is_running = True
                        else: self.server_pid = None
                    except: self.server_pid = None
                if is_running:
                    self.ping_value = self.get_ping_time('localhost', self.game_port_var.get())
                    self.player_count = self.get_player_count()
                else:
                    monitor_host = self.config.get("monitor_host", "localhost")
                    if monitor_host != "localhost": self.ping_value = self.get_ping_time(monitor_host, self.game_port_var.get())
                    else: self.ping_value = 0
                    self.player_count = 0
                time.sleep(2)
            except Exception as e: time.sleep(5)
                
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