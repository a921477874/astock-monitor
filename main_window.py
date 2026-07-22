#!/usr/bin/env python3
"""
宝宝量化系统 — 桌面启动程序 (exe入口)
双击运行，显示一个简单窗口，一键更新Dashboard。
"""
import sys
import os
import json
import re
import subprocess
import webbrowser
from datetime import datetime

# 确保工作目录在A股报告
DESKTOP = os.path.dirname(os.path.abspath(__file__))
os.chdir(DESKTOP)

# 加入Python路径
sys.path.insert(0, DESKTOP)

try:
    import tkinter as tk
    from tkinter import ttk, scrolledtext
    HAS_TK = True
except:
    HAS_TK = False

try:
    from db_manager import DB
    from datasource import DataSource
    HAS_MODULES = True
except:
    HAS_MODULES = False


class StdoutRedirect:
    """把print输出重定向到文本框"""
    def __init__(self, text_widget):
        self.text_widget = text_widget
        self.buffer = ""

    def write(self, s):
        self.buffer += s
        if self.text_widget:
            try:
                self.text_widget.insert(tk.END, s)
                self.text_widget.see(tk.END)
                self.text_widget.update()
            except:
                pass

    def flush(self):
        pass


class BabyApp:
    def __init__(self, root):
        self.root = root
        self.root.title("宝宝量化系统 — 本地数据平台")
        self.root.geometry("680x580")
        self.root.resizable(True, True)

        # 图标设置（用默认）
        try:
            self.root.iconbitmap(default=os.path.join(DESKTOP, "icon.ico"))
        except:
            pass

        # 配色
        self.bg = "#f5f0eb"
        self.card_bg = "#ffffff"
        self.accent = "#c0392b"
        self.root.configure(bg=self.bg)

        # 标题
        title_frame = tk.Frame(root, bg=self.bg)
        title_frame.pack(fill=tk.X, padx=15, pady=(15, 5))
        tk.Label(title_frame, text="🐣 宝宝量化系统", font=("Microsoft YaHei", 18, "bold"),
                 bg=self.bg, fg="#2c3e50").pack(anchor=tk.W)
        tk.Label(title_frame, text="本地数据平台 · 断网可用", font=("Microsoft YaHei", 10),
                 bg=self.bg, fg="#7f8c8d").pack(anchor=tk.W)

        # 状态栏
        status_frame = tk.Frame(root, bg=self.card_bg, highlightbackground="#ddd", highlightthickness=1)
        status_frame.pack(fill=tk.X, padx=15, pady=5)
        self.status_label = tk.Label(status_frame, text="等待操作...", font=("Microsoft YaHei", 9),
                                     bg=self.card_bg, fg="#555", anchor=tk.W, padx=10, pady=8)
        self.status_label.pack(fill=tk.X)

        # 按钮行
        btn_frame = tk.Frame(root, bg=self.bg)
        btn_frame.pack(fill=tk.X, padx=15, pady=5)

        btn_style = {"font": ("Microsoft YaHei", 10), "padx": 12, "pady": 6, "bd": 0,
                     "cursor": "hand2"}

        self.btn_update = tk.Button(btn_frame, text="📦 更新Dashboard", bg="#27ae60", fg="white",
                                    command=self.run_update, **btn_style)
        self.btn_update.pack(side=tk.LEFT, padx=(0, 8))

        self.btn_status = tk.Button(btn_frame, text="📊 数据状态", bg="#2980b9", fg="white",
                                    command=self.run_status, **btn_style)
        self.btn_status.pack(side=tk.LEFT, padx=(0, 8))

        self.btn_open = tk.Button(btn_frame, text="🌐 打开网页", bg="#8e44ad", fg="white",
                                  command=self.open_web, **btn_style)
        self.btn_open.pack(side=tk.LEFT, padx=(0, 8))

        self.btn_about = tk.Button(btn_frame, text="ℹ️ 关于", bg="#95a5a6", fg="white",
                                   command=self.show_about, **btn_style)
        self.btn_about.pack(side=tk.LEFT)

        # 输出区域
        out_frame = tk.Frame(root, bg=self.bg)
        out_frame.pack(fill=tk.BOTH, expand=True, padx=15, pady=5)

        tk.Label(out_frame, text="运行输出：", font=("Microsoft YaHei", 9, "bold"),
                 bg=self.bg, fg="#555").pack(anchor=tk.W)

        self.output = scrolledtext.ScrolledText(
            out_frame, wrap=tk.WORD, font=("Consolas", 10),
            bg="#1e1e1e", fg="#d4d4d4", insertbackground="white",
            height=15, bd=1, relief=tk.SOLID
        )
        self.output.pack(fill=tk.BOTH, expand=True)

        self.stdout_redirect = StdoutRedirect(self.output)
        sys.stdout = self.stdout_redirect

        # 启动时自动显示状态
        self.root.after(300, self.run_status)

    def run_update(self):
        self._clear_output()
        self._disable_buttons()
        self.status_label.config(text="⏳ 正在更新Dashboard...", fg="#e67e22")
        self.root.update()

        print("=" * 50)
        print("  📦 宝宝量化系统 — 更新Dashboard")
        print(f"  🕐 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 50)

        # 跑 update_dashboard
        try:
            r = subprocess.run(
                [sys.executable, "/home/ran/.hermes/scripts/update_dashboard.py"],
                capture_output=True, text=True, timeout=30,
                cwd=DESKTOP
            )
            print(r.stdout)
            if r.stderr:
                print(f"[错误] {r.stderr[:300]}")
            if r.returncode == 0:
                self.status_label.config(text="✅ Dashboard更新完成！", fg="#27ae60")
            else:
                self.status_label.config(text="⚠️ 更新有错误，看输出", fg="#c0392b")
        except Exception as e:
            print(f"❌ 运行出错: {e}")
            self.status_label.config(text="❌ 更新失败", fg="#c0392b")

        self._enable_buttons()

    def run_status(self):
        self._clear_output()
        print("=" * 50)
        print("  📊 宝宝量化系统 — 数据状态")
        print(f"  🕐 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 50)

        try:
            from db_manager import DB
            db = DB()
            st = db.stats()

            tables_info = [
                ("📈 大盘指数", st.get('index_daily', {})),
                ("📊 个股日线", st.get('stock_daily', {})),
                ("🏆 推荐记录", st.get('picks_history', {})),
                ("🏭 板块行情", st.get('sector_daily', {})),
                ("🧠 情绪评分", st.get('mood_daily', {})),
            ]

            total = 0
            for name, info in tables_info:
                cnt = info.get('count', 0)
                total += cnt
                period = f"{info.get('earliest','--')} → {info.get('latest','--')}" if cnt > 0 else "⚠️ 空"
                status = "✅" if cnt > 0 else "⬜"
                print(f"  {status} {name:12s} {cnt:5d}条  {period}")

            print(f"\n  📦 总计 {total} 条记录")
            print(f"  💾 {os.path.getsize(db.db_path)/1024:.0f} KB")

            # dashboard信息
            dp = os.path.join(DESKTOP, "dashboard.html")
            if os.path.exists(dp):
                mtime = os.path.getmtime(dp)
                mt_str = datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M")
                sz = os.path.getsize(dp)
                print(f"\n  📄 dashboard.html ({sz/1024:.0f} KB) — {mt_str}")
                try:
                    with open(dp) as f:
                        h = f.read()
                    m = re.search(r'const DAILY_REPORT = ({.*?});', h, re.DOTALL)
                    if m:
                        dr = json.loads(m.group(1))
                        print(f"  🎯 面板日期: {dr.get('date','?')}  评分: {dr.get('moodCycle',{}).get('score','?')}")
                except:
                    pass

        except Exception as e:
            print(f"❌ 读取状态失败: {e}")

        print("\n" + "=" * 50)
        print("  ✅ 网络正常时自动拉最新数据")
        print("  🔌 断网时自动用本地缓存")
        print("=" * 50)

        self.status_label.config(text="✅ 状态已刷新", fg="#27ae60")

    def open_web(self):
        dp = os.path.join(DESKTOP, "dashboard.html")
        if os.path.exists(dp):
            webbrowser.open(f"file://{os.path.abspath(dp)}")
            self.status_label.config(text="🌐 已打开本地Dashboard", fg="#8e44ad")
        else:
            self.status_label.config(text="⚠️ dashboard.html 不存在", fg="#c0392b")

    def show_about(self):
        self._clear_output()
        print("=" * 50)
        print("  宝宝量化系统 v1.0")
        print("=" * 50)
        print()
        print("  功能：")
        print("  ✅ 一键更新Dashboard")
        print("  ✅ 数据优先读本地SQLite")
        print("  ✅ 断网时自动用缓存数据")
        print("  ✅ 2168条本地数据积累")
        print()
        print("  文件位置：")
        print(f"  📁 {DESKTOP}")
        print()
        print("  提示：")
        print("  每天跑一次「更新Dashboard」即可")
        print("  数据自动缓存到 market_data.db")
        print("=" * 50)
        self.status_label.config(text="ℹ️ 关于", fg="#95a5a6")

    def _clear_output(self):
        try:
            self.output.delete(1.0, tk.END)
        except:
            pass

    def _disable_buttons(self):
        for btn in [self.btn_update, self.btn_status, self.btn_open]:
            btn.config(state=tk.DISABLED)

    def _enable_buttons(self):
        for btn in [self.btn_update, self.btn_status, self.btn_open]:
            btn.config(state=tk.NORMAL)


if __name__ == "__main__":
    if HAS_TK:
        root = tk.Tk()
        app = BabyApp(root)
        root.mainloop()
    else:
        # 无GUI模式，命令行运行
        print("⚠️ Tkinter不可用，使用命令行模式")
        sys.argv = [sys.argv[0], "--status"]
        cmd = sys.argv[1] if len(sys.argv) > 1 else "--status"
        if cmd == "--status":
            from db_manager import DB
            db = DB()
            st = db.stats()
            for tbl, info in st.items():
                print(f"{tbl:20s} {info['count']:6d}条  {info.get('earliest','')} → {info.get('latest','')}")
        else:
            print("宝宝量化系统 — 请在终端运行: python3 宝宝启动.py --status")
