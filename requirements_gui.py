import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog
import subprocess
import sys
import os
import json
import venv
import shutil
import threading
from typing import List, Dict, Optional
import platform

# 尝试导入tkinterdnd2以支持拖放功能
try:
    from tkinterdnd2 import DND_FILES, TkinterDnD
    HAS_DND = True
except ImportError:
    HAS_DND = False
    print("未安装tkinterdnd2库，拖放功能不可用。请运行: pip install tkinterdnd2")

# 用于获取已安装包信息
try:
    # Python 3.8+
    from importlib.metadata import distributions
except ImportError:
    # Python < 3.8, 需要安装importlib-metadata包
    try:
        from importlib_metadata import distributions
    except ImportError:
        # 回退到pkg_resources
        from pkg_resources import working_set
        distributions = None


class RequirementsManager:
    def __init__(self, root):
        self.root = root
        self.root.title("Requirements GUI-可视化管理工具 v0.0.1")
        self.root.geometry("1200x800")
        
        # 当前打开的requirements文件路径
        self.current_file = None
        # 包信息列表
        self.packages = []
        # 当前虚拟环境路径
        self.current_venv = None
        # 镜像源配置
        self.mirror_sources = {
            "默认": "",
            "清华": "https://pypi.tuna.tsinghua.edu.cn/simple/",
            "阿里": "https://mirrors.aliyun.com/pypi/simple/",
            "豆瓣": "https://pypi.douban.com/simple/",
            "中科大": "https://pypi.mirrors.ustc.edu.cn/simple/"
        }
        self.current_mirror = "默认"
        # 调试窗口相关
        self.debug_window_visible = True
        self.debug_text = None
        
        self.setup_ui()
        self.create_menu()
        # 自动检测环境
        self.detect_environment()
        
        # 注册拖放事件（如果支持）
        self.register_drop_target()
        
    def setup_ui(self):
        # 创建主框架
        main_frame = ttk.Frame(self.root)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # 顶部控制区域
        control_frame = ttk.Frame(main_frame)
        control_frame.pack(fill=tk.X, pady=(0, 10))
        
        # 第一行控制区域
        first_row_frame = ttk.Frame(control_frame)
        first_row_frame.pack(fill=tk.X, pady=(0, 5))
        
        # 系统环境信息区域
        system_frame = ttk.LabelFrame(first_row_frame, text="系统环境")
        system_frame.pack(side=tk.LEFT, padx=(0, 10))
        
        # 获取系统信息
        system_info = f"{platform.system()} {platform.release()}"
        architecture = platform.machine()  # 获取更准确的架构信息
        python_version = f"Python {sys.version.split()[0]} ({platform.architecture()[0]})"
        self.system_label = ttk.Label(system_frame, text=f"{system_info} ({architecture}) - {python_version}")
        self.system_label.pack(side=tk.LEFT, padx=5, pady=5)
        
        # 虚拟环境区域
        venv_frame = ttk.LabelFrame(first_row_frame, text="虚拟环境")
        venv_frame.pack(side=tk.LEFT, padx=(0, 10))
        
        ttk.Button(venv_frame, text="创建虚拟环境（venv）", command=self.create_venv).pack(side=tk.LEFT, padx=5, pady=5)
        ttk.Button(venv_frame, text="指定名称创建", command=self.create_named_venv).pack(side=tk.LEFT, padx=5, pady=5)
        ttk.Button(venv_frame, text="创建嵌入式", command=self.create_embed_venv).pack(side=tk.LEFT, padx=5, pady=5)
        ttk.Button(venv_frame, text="选择虚拟环境", command=self.select_venv).pack(side=tk.LEFT, padx=5, pady=5)
        self.venv_label = ttk.Label(venv_frame, text="未选择虚拟环境")
        self.venv_label.pack(side=tk.LEFT, padx=2, pady=2)
        
        # 镜像源区域
        mirror_frame = ttk.LabelFrame(first_row_frame, text="镜像源")
        mirror_frame.pack(side=tk.LEFT, padx=(0, 10))
        
        ttk.Label(mirror_frame, text="当前镜像:").pack(side=tk.LEFT, padx=5, pady=5)
        self.mirror_var = tk.StringVar(value=self.current_mirror)
        mirror_combo = ttk.Combobox(mirror_frame, textvariable=self.mirror_var, width=10, state="readonly")
        mirror_combo['values'] = list(self.mirror_sources.keys())
        mirror_combo.pack(side=tk.LEFT, padx=2, pady=2)
        mirror_combo.bind("<<ComboboxSelected>>", self.change_mirror)
        
        # 第二行控制区域
        second_row_frame = ttk.Frame(control_frame)
        second_row_frame.pack(fill=tk.X, pady=(5, 0))
        
        # 文件操作区域
        file_frame = ttk.LabelFrame(second_row_frame, text="requirements文件操作")
        file_frame.pack(side=tk.LEFT)
        
        ttk.Button(file_frame, text="新建", command=self.new_file).pack(side=tk.LEFT, padx=5, pady=5)
        ttk.Button(file_frame, text="打开", command=self.open_file).pack(side=tk.LEFT, padx=5, pady=5)
        ttk.Button(file_frame, text="保存", command=self.save_file).pack(side=tk.LEFT, padx=5, pady=5)
        ttk.Button(file_frame, text="另存为", command=self.save_as_file).pack(side=tk.LEFT, padx=5, pady=5)
        
        # 预设包区域
        preset_frame = ttk.LabelFrame(main_frame, text="预设包集合")
        preset_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Button(preset_frame, text="AI绘画", command=lambda: self.load_preset("ai_art")).pack(side=tk.LEFT, padx=2, pady=2)
        ttk.Button(preset_frame, text="AI图像", command=lambda: self.load_preset("ai_image")).pack(side=tk.LEFT, padx=2, pady=2)
        ttk.Button(preset_frame, text="AI音频", command=lambda: self.load_preset("ai_audio")).pack(side=tk.LEFT, padx=2, pady=2)
        ttk.Button(preset_frame, text="AI视频", command=lambda: self.load_preset("ai_video")).pack(side=tk.LEFT, padx=2, pady=2)
        ttk.Button(preset_frame, text="数据科学", command=lambda: self.load_preset("data_science")).pack(side=tk.LEFT, padx=2, pady=2)
        ttk.Button(preset_frame, text="Web开发", command=lambda: self.load_preset("web_dev")).pack(side=tk.LEFT, padx=2, pady=2)
        
        # 包管理区域
        package_frame = ttk.LabelFrame(main_frame, text="包管理")
        package_frame.pack(fill=tk.BOTH, expand=True)
        
        # 工具栏
        toolbar_frame = ttk.Frame(package_frame)
        toolbar_frame.pack(fill=tk.X, pady=(0, 5))
        
        ttk.Button(toolbar_frame, text="添加包", command=self.add_package).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar_frame, text="删除选中", command=self.remove_package).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar_frame, text="全选", command=self.select_all).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar_frame, text="取消选择", command=self.deselect_all).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar_frame, text="刷新列表", command=self.refresh_packages).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar_frame, text="搜索包", command=self.search_package).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar_frame, text="安装选中", command=self.install_selected).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar_frame, text="更新选中", command=self.update_selected).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar_frame, text="降级选中", command=self.downgrade_selected).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar_frame, text="卸载选中", command=self.uninstall_selected).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar_frame, text="列出已安装", command=self.list_installed).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar_frame, text="保存已安装", command=self.save_installed_as_requirements).pack(side=tk.LEFT, padx=2)
        
        # 包列表
        columns = ("名称", "版本", "操作符", "来源", "描述")
        self.tree = ttk.Treeview(package_frame, columns=columns, show="headings", height=15)
        
        # 设置列标题
        for col in columns:
            self.tree.heading(col, text=col)
            self.tree.column(col, width=150)
            
        # 添加滚动条
        scrollbar_y = ttk.Scrollbar(package_frame, orient=tk.VERTICAL, command=self.tree.yview)
        scrollbar_x = ttk.Scrollbar(package_frame, orient=tk.HORIZONTAL, command=self.tree.xview)
        self.tree.configure(yscrollcommand=scrollbar_y.set, xscrollcommand=scrollbar_x.set)
        
        # 布局
        self.tree.pack(fill=tk.BOTH, expand=True, side=tk.LEFT)
        scrollbar_y.pack(side=tk.RIGHT, fill=tk.Y)
        scrollbar_x.pack(side=tk.BOTTOM, fill=tk.X)
        
        # 调试窗口区域（默认显示）
        self.debug_frame = ttk.LabelFrame(package_frame, text="调试窗口")
        self.debug_frame.pack(fill=tk.BOTH, expand=True, side=tk.BOTTOM, pady=(10, 0))  # 默认显示
        
        self.debug_text = tk.Text(self.debug_frame, height=10, wrap=tk.WORD)
        debug_scrollbar = ttk.Scrollbar(self.debug_frame, orient=tk.VERTICAL, command=self.debug_text.yview)
        self.debug_text.configure(yscrollcommand=debug_scrollbar.set)
        
        self.debug_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        debug_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # 调试窗口控制按钮
        debug_control_frame = ttk.Frame(package_frame)
        debug_control_frame.pack(fill=tk.X)
        self.debug_toggle_btn = ttk.Button(debug_control_frame, text="隐藏调试窗口", command=self.toggle_debug_window)
        self.debug_toggle_btn.pack(side=tk.LEFT, padx=5, pady=5)
        ttk.Button(debug_control_frame, text="清空调试信息", command=self.clear_debug_info).pack(side=tk.LEFT, padx=5, pady=5)
        
        # 初始化调试窗口状态
        self.debug_window_visible = True
        
        # 状态栏
        self.status_var = tk.StringVar()
        self.status_var.set("就绪")
        status_bar = ttk.Label(self.root, textvariable=self.status_var, relief=tk.SUNKEN, anchor=tk.W)
        status_bar.pack(side=tk.BOTTOM, fill=tk.X)
        
        # 绑定双击事件
        self.tree.bind("<Double-1>", self.edit_package)
        
    def create_menu(self):
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)
        
        # 文件菜单
        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="文件", menu=file_menu)
        file_menu.add_command(label="新建", command=self.new_file)
        file_menu.add_command(label="打开", command=self.open_file)
        file_menu.add_command(label="保存", command=self.save_file)
        file_menu.add_command(label="另存为", command=self.save_as_file)
        file_menu.add_separator()
        file_menu.add_command(label="退出", command=self.root.quit)
        
        # 操作菜单
        action_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="操作", menu=action_menu)
        action_menu.add_command(label="安装所有包", command=self.install_all)
        action_menu.add_command(label="生成当前环境的requirements", command=self.generate_requirements)
        action_menu.add_command(label="保存已安装包为requirements", command=self.save_installed_as_requirements)
        action_menu.add_separator()
        action_menu.add_command(label="刷新包列表", command=self.refresh_packages)
        
        # 帮助菜单
        help_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="帮助", menu=help_menu)
        help_menu.add_command(label="关于", command=self.show_about)
        
    def update_status(self, message: str):
        """更新状态栏"""
        self.status_var.set(message)
        self.root.update_idletasks()
        
    def toggle_debug_window(self):
        """切换调试窗口显示/隐藏"""
        if self.debug_window_visible:
            # 隐藏调试窗口
            self.debug_frame.pack_forget()
            self.debug_toggle_btn.config(text="显示调试窗口")
            self.debug_window_visible = False
        else:
            # 显示调试窗口
            self.debug_frame.pack(fill=tk.BOTH, expand=True, side=tk.BOTTOM, pady=(10, 0))
            self.debug_toggle_btn.config(text="隐藏调试窗口")
            self.debug_window_visible = True
            
    def clear_debug_info(self):
        """清空调试信息"""
        if self.debug_text:
            self.debug_text.delete(1.0, tk.END)
            
    def append_debug_info(self, message: str):
        """追加调试信息"""
        if self.debug_text:
            self.debug_text.insert(tk.END, message + "\n")
            self.debug_text.see(tk.END)  # 滚动到最后一行
            self.root.update_idletasks()
        
    def new_file(self):
        """新建requirements文件"""
        self.current_file = None
        self.packages = []
        self.refresh_tree()
        self.update_status("已创建新文件")
        
    def open_file(self):
        """打开requirements文件"""
        file_path = filedialog.askopenfilename(
            title="选择requirements文件",
            filetypes=[("Requirements files", "*.txt"), ("All files", "*.*")]
        )
        
        if file_path:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    
                self.current_file = file_path
                self.parse_requirements(content)
                self.refresh_tree()
                self.update_status(f"已打开文件: {file_path}")
                
            except Exception as e:
                messagebox.showerror("错误", f"无法打开文件: {str(e)}")
                
    def save_file(self):
        """保存requirements文件"""
        if self.current_file:
            try:
                content = self.generate_requirements_content()
                with open(self.current_file, 'w', encoding='utf-8') as f:
                    f.write(content)
                self.update_status(f"已保存文件: {self.current_file}")
            except Exception as e:
                messagebox.showerror("错误", f"无法保存文件: {str(e)}")
        else:
            self.save_as_file()
            
    def save_as_file(self):
        """另存为requirements文件"""
        file_path = filedialog.asksaveasfilename(
            title="保存requirements文件",
            initialfile="requirements",
            defaultextension=".txt",
            filetypes=[("Requirements files", "*.txt"), ("All files", "*.*")]
        )
        
        if file_path:
            try:
                content = self.generate_requirements_content()
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(content)
                self.current_file = file_path
                self.update_status(f"已保存文件: {file_path}")
            except Exception as e:
                messagebox.showerror("错误", f"无法保存文件: {str(e)}")
                
    def parse_requirements(self, content: str):
        """解析requirements内容"""
        self.packages = []
        lines = content.strip().split('\n')
        
        for line in lines:
            line = line.strip()
            if line and not line.startswith('#'):
                # 解析包信息
                package_info = self.parse_package_line(line)
                if package_info:
                    self.packages.append(package_info)
                    
    def parse_package_line(self, line: str) -> Optional[Dict]:
        """解析单个包行"""
        # 处理注释
        if '#' in line:
            line = line.split('#')[0].strip()
            
        if not line:
            return None
            
        # 简单解析包名和版本
        name = line
        version = ""
        operator = ""
        source = "pypi"
        
        # 检查是否有版本操作符
        operators = ['==', '>=', '<=', '>', '<', '!=', '~=', '===']
        for op in operators:
            if op in line:
                parts = line.split(op)
                name = parts[0].strip()
                version = op + parts[1].strip()
                operator = op
                break
                
        return {
            'name': name,
            'version': version,
            'operator': operator,
            'source': source,
            'description': ''
        }
        
    def generate_requirements_content(self) -> str:
        """生成requirements文件内容"""
        lines = []
        for package in self.packages:
            if package['version']:
                # 正确处理版本操作符，确保格式为 name==version
                if package['operator'] and package['version'].startswith(package['operator']):
                    line = f"{package['name']}{package['version']}"
                else:
                    # 如果版本信息不包含操作符，则使用存储的操作符
                    line = f"{package['name']}{package['operator']}{package['version']}"
            else:
                line = package['name']
            lines.append(line)
        return '\n'.join(lines)
        
    def refresh_tree(self):
        """刷新包列表显示"""
        # 清空现有项
        for item in self.tree.get_children():
            self.tree.delete(item)
            
        # 添加包项
        for i, package in enumerate(self.packages):
            # 确保包字典包含所有必需的键
            if 'description' not in package:
                package['description'] = ''
            if 'operator' not in package:
                package['operator'] = ''
            if 'source' not in package:
                package['source'] = 'pypi'
                
            # 处理版本显示，考虑空操作符的情况
            version_display = ''
            if package['version']:
                if package['operator']:
                    version_display = package['version'].replace(package['operator'], '', 1)
                else:
                    version_display = package['version'].replace('==', '', 1) if package['version'].startswith('==') else package['version']
            
            self.tree.insert("", tk.END, iid=i, values=(
                package['name'],
                version_display,
                package['operator'],
                package['source'],
                package['description']
            ))
            
    def add_package(self):
        """添加新包"""
        dialog = PackageDialog(self.root, "添加包")
        if dialog.result:
            # 处理版本信息，考虑空操作符的情况
            version_str = ''
            if dialog.result['version']:
                if dialog.result['operator']:
                    version_str = dialog.result['operator'] + dialog.result['version']
                else:
                    # 如果操作符为空，默认使用==操作符
                    version_str = '==' + dialog.result['version']
            
            package = {
                'name': dialog.result['name'],
                'version': version_str,
                'operator': dialog.result['operator'],
                'source': dialog.result['source'],
                'description': ''
            }
            self.packages.append(package)
            self.refresh_tree()
            
    def remove_package(self):
        """删除选中的包"""
        selected_items = self.tree.selection()
        if not selected_items:
            messagebox.showwarning("警告", "请先选择要删除的包")
            return
            
        if messagebox.askyesno("确认", "确定要删除选中的包吗？"):
            # 从后往前删除，避免索引变化
            indices = sorted([int(i) for i in selected_items], reverse=True)
            for idx in indices:
                del self.packages[idx]
            self.refresh_tree()
            
    def edit_package(self, event=None):
        """编辑选中的包"""
        selected_items = self.tree.selection()
        if not selected_items:
            return
            
        idx = int(selected_items[0])
        package = self.packages[idx]
        
        # 解析版本信息，考虑空操作符的情况
        version_value = ''
        if package['version']:
            if package['operator']:
                version_value = package['version'].replace(package['operator'], '', 1)
            else:
                # 如果操作符为空，尝试移除默认的==操作符
                version_value = package['version'].replace('==', '', 1) if package['version'].startswith('==') else package['version']
        
        dialog = PackageDialog(
            self.root, 
            "编辑包",
            name=package['name'],
            version=version_value,
            operator=package['operator'],
            source=package['source']
        )
        
        if dialog.result:
            # 处理版本信息，考虑空操作符的情况
            version_str = ''
            if dialog.result['version']:
                if dialog.result['operator']:
                    version_str = dialog.result['operator'] + dialog.result['version']
                else:
                    # 如果操作符为空，默认使用==操作符
                    version_str = '==' + dialog.result['version']
            
            self.packages[idx] = {
                'name': dialog.result['name'],
                'version': version_str,
                'operator': dialog.result['operator'],
                'source': dialog.result['source'],
                'description': ''
            }
            self.refresh_tree()
            
    def refresh_packages(self):
        """刷新包列表"""
        # 使用多线程执行刷新操作，避免阻塞GUI主线程
        import threading
        threading.Thread(target=self._refresh_packages_thread, daemon=True).start()
        
    def _refresh_packages_thread(self):
        """在后台线程中执行包列表刷新操作"""
        self.root.after(0, lambda: self.update_status("正在刷新包列表..."))
        try:
            # 获取已安装的包信息
            installed_packages = {}
            if distributions is not None:
                # 使用importlib.metadata或importlib_metadata
                installed_packages = {dist.metadata['Name'].lower(): dist.version for dist in distributions()}
            else:
                # 回退到pkg_resources
                installed_packages = {pkg.key: pkg.version for pkg in working_set}
            
            # 更新包信息
            for package in self.packages:
                # 确保包字典包含所有必需的键
                if 'description' not in package:
                    package['description'] = ''
                if 'operator' not in package:
                    package['operator'] = ''
                if 'source' not in package:
                    package['source'] = 'pypi'
                    
                pkg_key = package['name'].lower()
                if pkg_key in installed_packages:
                    package['description'] = f"已安装: {installed_packages[pkg_key]}"
                else:
                    package['description'] = "未安装"
                    
            self.root.after(0, lambda: self.refresh_tree())
            self.root.after(0, lambda: self.update_status("包列表刷新完成"))
        except Exception as e:
            self.root.after(0, lambda: self.update_status(f"刷新失败: {str(e)}"))
            self.root.after(0, lambda: messagebox.showerror("错误", f"刷新包列表失败: {str(e)}"))
            
    def install_selected(self):
        """安装选中的包"""
        selected_items = self.tree.selection()
        if not selected_items:
            messagebox.showwarning("警告", "请先选择要安装的包")
            return
            
        packages_to_install = []
        for item in selected_items:
            idx = int(item)
            package = self.packages[idx]
            if package['version']:
                packages_to_install.append(f"{package['name']}{package['version']}")
            else:
                packages_to_install.append(package['name'])
                
        self.install_packages(packages_to_install)
        
    def install_all(self):
        """安装所有包"""
        if not self.packages:
            messagebox.showwarning("警告", "没有包可以安装")
            return
            
        packages_to_install = []
        for package in self.packages:
            if package['version']:
                packages_to_install.append(f"{package['name']}{package['version']}")
            else:
                packages_to_install.append(package['name'])
                
        self.install_packages(packages_to_install)
        
    def install_packages(self, packages: List[str]):
        """安装指定的包"""
        if not packages:
            return
            
        # 使用多线程执行安装操作，避免阻塞GUI主线程
        import threading
        threading.Thread(target=self._install_packages_thread, args=(packages,), daemon=True).start()
        
    def _install_packages_thread(self, packages: List[str]):
        """在后台线程中执行包安装操作"""
        try:
            self.root.after(0, lambda: self.update_status(f"正在安装包: {', '.join(packages)}"))
            cmd = self.get_pip_command() + ["install"] + packages
            
            self.root.after(0, lambda: self.append_debug_info(f"执行安装命令: {' '.join(cmd)}"))
            self.root.after(0, lambda: self.append_debug_info("安装过程:"))
            
            # 使用Popen来实时获取输出
            process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
            
            # 实时读取输出
            while True:
                output = process.stdout.readline()
                if output == '' and process.poll() is not None:
                    break
                if output:
                    self.root.after(0, lambda out=output: self.append_debug_info(out.strip()))
            
            # 等待进程结束
            process.wait()
            
            if process.returncode == 0:
                self.root.after(0, lambda: self.update_status("包安装成功"))
                self.root.after(0, lambda: self.append_debug_info("安装完成"))
                self.root.after(0, lambda: messagebox.showinfo("成功", "包安装成功"))
                self.root.after(0, lambda: self.refresh_packages())  # 刷新包列表以更新描述信息
            else:
                self.root.after(0, lambda: self.update_status("包安装失败"))
                self.root.after(0, lambda: self.append_debug_info(f"安装失败，返回码: {process.returncode}"))
                self.root.after(0, lambda: messagebox.showerror("错误", "包安装失败，请查看调试窗口了解详情"))
        except Exception as e:
            self.root.after(0, lambda: self.update_status(f"安装出错: {str(e)}"))
            self.root.after(0, lambda: self.append_debug_info(f"安装异常: {str(e)}"))
            self.root.after(0, lambda: messagebox.showerror("错误", f"安装过程中出现错误: {str(e)}"))
            
    def update_selected(self):
        """更新选中的包"""
        selected_items = self.tree.selection()
        if not selected_items:
            messagebox.showwarning("警告", "请先选择要更新的包")
            return
            
        packages_to_update = []
        for item in selected_items:
            idx = int(item)
            package = self.packages[idx]
            packages_to_update.append(package['name'])
            
        self.update_packages(packages_to_update)
        
    def downgrade_selected(self):
        """降级选中的包"""
        selected_items = self.tree.selection()
        if not selected_items:
            messagebox.showwarning("警告", "请先选择要降级的包")
            return
            
        # 提取选中包的名称
        packages_to_downgrade = []
        for item in selected_items:
            idx = int(item)
            package = self.packages[idx]
            packages_to_downgrade.append(package['name'])
            
        self.downgrade_packages(packages_to_downgrade)
        
    def update_packages(self, packages: List[str]):
        """更新指定的包"""
        if not packages:
            return
            
        # 使用多线程执行更新操作，避免阻塞GUI主线程
        import threading
        threading.Thread(target=self._update_packages_thread, args=(packages,), daemon=True).start()
        
    def _update_packages_thread(self, packages: List[str]):
        """在后台线程中执行包更新操作"""
        try:
            self.root.after(0, lambda: self.update_status(f"正在更新包: {', '.join(packages)}"))
            cmd = self.get_pip_command() + ["install", "--upgrade"] + packages
            
            self.root.after(0, lambda: self.append_debug_info(f"执行更新命令: {' '.join(cmd)}"))
            self.root.after(0, lambda: self.append_debug_info("更新过程:"))
            
            # 使用Popen来实时获取输出
            process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
            
            # 实时读取输出
            while True:
                output = process.stdout.readline()
                if output == '' and process.poll() is not None:
                    break
                if output:
                    self.root.after(0, lambda out=output: self.append_debug_info(out.strip()))
            
            # 等待进程结束
            process.wait()
            
            if process.returncode == 0:
                self.root.after(0, lambda: self.update_status("包更新成功"))
                self.root.after(0, lambda: self.append_debug_info("更新完成"))
                self.root.after(0, lambda: self.refresh_packages())  # 刷新包列表以更新描述信息
            else:
                self.root.after(0, lambda: self.update_status("包更新失败"))
                self.root.after(0, lambda: self.append_debug_info(f"更新失败，返回码: {process.returncode}"))
        except Exception as e:
            self.root.after(0, lambda: self.update_status(f"更新出错: {str(e)}"))
            self.root.after(0, lambda: self.append_debug_info(f"更新异常: {str(e)}"))

    def downgrade_packages(self, packages: List[str]):
        """降级指定的包"""
        if not packages:
            return
            
        # 获取当前包的版本信息（在主线程中进行）
        downgrade_list = []
        for item in self.tree.selection():
            idx = int(item)
            package = self.packages[idx]
            # 显示版本选择对话框（必须在主线程中进行）
            version = simpledialog.askstring("降级包", f"请输入 {package['name']} 的目标版本:")
            if version:
                downgrade_list.append(f"{package['name']}=={version}")
        
        if not downgrade_list:
            return
            
        # 使用多线程执行降级操作，避免阻塞GUI主线程
        import threading
        threading.Thread(target=self._downgrade_packages_thread, args=(downgrade_list,), daemon=True).start()
        
    def _downgrade_packages_thread(self, downgrade_list: List[str]):
        """在后台线程中执行包降级操作"""
        try:
            self.root.after(0, lambda: self.update_status(f"正在降级包: {', '.join(downgrade_list)}"))
            cmd = self.get_pip_command() + ["install"] + downgrade_list
            
            self.root.after(0, lambda: self.append_debug_info(f"执行降级命令: {' '.join(cmd)}"))
            self.root.after(0, lambda: self.append_debug_info("降级过程:"))
            
            # 使用Popen来实时获取输出
            process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
            
            # 实时读取输出
            while True:
                output = process.stdout.readline()
                if output == '' and process.poll() is not None:
                    break
                if output:
                    self.root.after(0, lambda out=output: self.append_debug_info(out.strip()))
            
            # 等待进程结束
            process.wait()
            
            if process.returncode == 0:
                self.root.after(0, lambda: self.update_status("包降级成功"))
                self.root.after(0, lambda: self.append_debug_info("降级完成"))
                # 重新加载包信息以确保版本信息正确更新
                self.root.after(0, lambda: self._refresh_packages_thread())  # 刷新包列表以更新描述信息
            else:
                self.root.after(0, lambda: self.update_status("包降级失败"))
                self.root.after(0, lambda: self.append_debug_info(f"降级失败，返回码: {process.returncode}"))
        except Exception as e:
            self.root.after(0, lambda: self.update_status(f"降级出错: {str(e)}"))
            self.root.after(0, lambda: self.append_debug_info(f"降级异常: {str(e)}"))
            
    def uninstall_selected(self):
        """卸载选中的包"""
        selected_items = self.tree.selection()
        if not selected_items:
            messagebox.showwarning("警告", "请先选择要卸载的包")
            return
            
        packages_to_uninstall = []
        for item in selected_items:
            idx = int(item)
            package = self.packages[idx]
            packages_to_uninstall.append(package['name'])
            
        if messagebox.askyesno("确认", f"确定要卸载以下包吗？\n{', '.join(packages_to_uninstall)}"):
            self.uninstall_packages(packages_to_uninstall)
            
    def uninstall_packages(self, packages: List[str]):
        """卸载指定的包"""
        if not packages:
            return
            
        # 使用多线程执行卸载操作，避免阻塞GUI主线程
        import threading
        threading.Thread(target=self._uninstall_packages_thread, args=(packages,), daemon=True).start()
        
    def _uninstall_packages_thread(self, packages: List[str]):
        """在后台线程中执行包卸载操作"""
        try:
            self.root.after(0, lambda: self.update_status(f"正在卸载包: {', '.join(packages)}"))
            cmd = self.get_pip_command() + ["uninstall", "-y"] + packages
            
            self.root.after(0, lambda: self.append_debug_info(f"执行卸载命令: {' '.join(cmd)}"))
            self.root.after(0, lambda: self.append_debug_info("卸载过程:"))
            
            # 使用Popen来实时获取输出
            process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
            
            # 实时读取输出
            while True:
                output = process.stdout.readline()
                if output == '' and process.poll() is not None:
                    break
                if output:
                    self.root.after(0, lambda out=output: self.append_debug_info(out.strip()))
            
            # 等待进程结束
            process.wait()
            
            if process.returncode == 0:
                self.root.after(0, lambda: self.update_status("包卸载成功"))
                self.root.after(0, lambda: self.append_debug_info("卸载完成"))
                self.root.after(0, lambda: self.refresh_packages())  # 刷新包列表
            else:
                self.root.after(0, lambda: self.update_status("包卸载失败"))
                self.root.after(0, lambda: self.append_debug_info(f"卸载失败，返回码: {process.returncode}"))
        except Exception as e:
            self.root.after(0, lambda: self.update_status(f"卸载出错: {str(e)}"))
            self.root.after(0, lambda: self.append_debug_info(f"卸载异常: {str(e)}"))
            
    def generate_requirements(self):
        """生成当前环境的requirements文件"""
        # 使用多线程执行生成requirements操作，避免阻塞GUI主线程
        import threading
        threading.Thread(target=self._generate_requirements_thread, daemon=True).start()
        
    def _generate_requirements_thread(self):
        """在后台线程中执行生成requirements操作"""
        try:
            self.root.after(0, lambda: self.update_status("正在生成requirements文件..."))
            cmd = self.get_pip_command() + ["freeze"]
            
            self.root.after(0, lambda: self.append_debug_info(f"执行生成requirements命令: {' '.join(cmd)}"))
            self.root.after(0, lambda: self.append_debug_info("生成过程:"))
            
            # 使用Popen来实时获取输出
            process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
            
            # 实时读取输出
            output_lines = []
            while True:
                output = process.stdout.readline()
                if output == '' and process.poll() is not None:
                    break
                if output:
                    self.root.after(0, lambda out=output: self.append_debug_info(out.strip()))
                    output_lines.append(output.strip())
            
            # 等待进程结束
            process.wait()
            
            if process.returncode == 0:
                # 解析输出
                content = '\n'.join(output_lines)
                self.root.after(0, lambda: self.parse_requirements(content))
                self.root.after(0, lambda: self.refresh_tree())
                self.root.after(0, lambda: self.update_status("requirements文件生成完成"))
                self.root.after(0, lambda: self.append_debug_info("requirements文件生成完成"))
            else:
                self.root.after(0, lambda: self.update_status("生成失败"))
                self.root.after(0, lambda: self.append_debug_info(f"生成失败，返回码: {process.returncode}"))
                self.root.after(0, lambda: messagebox.showerror("错误", f"生成requirements失败"))
        except Exception as e:
            self.root.after(0, lambda: self.update_status(f"生成出错: {str(e)}"))
            self.root.after(0, lambda: self.append_debug_info(f"生成异常: {str(e)}"))
            self.root.after(0, lambda: messagebox.showerror("错误", f"生成过程中出现错误: {str(e)}"))
            
    def show_about(self):
        """显示关于信息"""
        # 创建一个带按钮的关于对话框
        about_dialog = tk.Toplevel(self.root)
        about_dialog.title("关于")
        about_dialog.geometry("400x250")
        about_dialog.resizable(False, False)
        
        # 居中显示对话框
        about_dialog.transient(self.root)
        about_dialog.grab_set()
        
        # 创建标签框架用于显示信息
        info_frame = ttk.Frame(about_dialog)
        info_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        
        # 显示软件信息
        ttk.Label(info_frame, text="Requirements GUI-可视化管理工具", font=("微软雅黑", 12, "bold")).pack(pady=(0, 5))
        ttk.Label(info_frame, text="版本: 0.0.1").pack(pady=2)
        ttk.Label(info_frame, text="这是一个用于管理Python包依赖的图形界面工具", wraplength=350).pack(pady=2)
        ttk.Label(info_frame, text="作者: otsluo").pack(pady=2)
        
        # 添加项目地址按钮
        ttk.Label(info_frame, text="项目地址:").pack(pady=(10, 5))
        project_url = "https://github.com/otsluo/requirements-GUI/"
        url_button = ttk.Button(info_frame, text=project_url, command=lambda: self.open_url(project_url), width=40)
        url_button.pack(pady=2)
        
        ttk.Label(info_frame, text="许可证: MIT").pack(pady=(10, 5))
        
        # 添加按钮框架
        button_frame = ttk.Frame(about_dialog)
        button_frame.pack(fill=tk.X, padx=20, pady=(0, 20))
        
        ttk.Button(button_frame, text="关闭", command=about_dialog.destroy).pack(side=tk.RIGHT)
        
        # 居中对话框
        about_dialog.update_idletasks()
        x = (about_dialog.winfo_screenwidth() // 2) - (about_dialog.winfo_width() // 2)
        y = (about_dialog.winfo_screenheight() // 2) - (about_dialog.winfo_height() // 2)
        about_dialog.geometry(f"+{x}+{y}")

    def open_url(self, url):
        """在浏览器中打开URL"""
        try:
            import webbrowser
            webbrowser.open(url)
        except Exception as e:
            messagebox.showerror("错误", f"无法打开链接: {str(e)}")

    def create_venv(self):
        """创建默认虚拟环境"""
        venv_path = filedialog.askdirectory(title="选择虚拟环境创建位置")
        if venv_path:
            venv_name = "venv"  # 默认名称
            venv_dir = os.path.join(venv_path, venv_name)
            # 在新线程中执行创建虚拟环境的操作
            threading.Thread(target=self._create_venv_thread, args=(venv_dir,), daemon=True).start()

    def _create_venv_thread(self, venv_dir):
        """在后台线程中创建虚拟环境"""
        try:
            self.root.after(0, lambda: self.update_status(f"正在创建虚拟环境: {venv_dir}"))
            self.root.after(0, lambda: self.append_debug_info(f"开始创建虚拟环境: {venv_dir}"))
            venv.create(venv_dir, with_pip=True)
            self.root.after(0, lambda: setattr(self, 'current_venv', venv_dir))
            self.root.after(0, lambda: self.venv_label.config(text=f"虚拟环境: {venv_dir}"))
            self.root.after(0, lambda: self.append_debug_info(f"虚拟环境创建成功: {venv_dir}"))
            self.root.after(0, lambda: self.update_status("虚拟环境创建成功"))
            self.root.after(0, lambda: messagebox.showinfo("成功", f"虚拟环境创建成功: {venv_dir}"))
            # 自动刷新包列表以显示新环境中的包
            self.root.after(0, lambda: self.refresh_packages())
        except Exception as e:
            self.root.after(0, lambda msg=str(e): self.update_status(f"创建虚拟环境失败: {msg}"))
            self.root.after(0, lambda msg=str(e): self.append_debug_info(f"创建虚拟环境失败: {msg}"))
            self.root.after(0, lambda msg=str(e): messagebox.showerror("错误", f"虚拟环境创建失败: {msg}"))

    def create_named_venv(self):
        """创建指定名称的虚拟环境"""
        venv_path = filedialog.askdirectory(title="选择虚拟环境创建位置")
        if venv_path:
            # 弹出对话框让用户输入虚拟环境名称
            venv_name = simpledialog.askstring("虚拟环境名称", "请输入虚拟环境名称:", initialvalue="venv")
            if venv_name:
                venv_dir = os.path.join(venv_path, venv_name)
                # 在新线程中执行创建虚拟环境的操作
                threading.Thread(target=self._create_venv_thread, args=(venv_dir,), daemon=True).start()

    def create_embed_venv(self):
        """创建嵌入式虚拟环境"""
        venv_path = filedialog.askdirectory(title="选择嵌入式环境创建位置")
        if venv_path:
            venv_name = "embed_env"  # 嵌入式环境名称
            venv_dir = os.path.join(venv_path, venv_name)
            # 在新线程中执行创建嵌入式环境的操作
            threading.Thread(target=self._create_venv_thread, args=(venv_dir,), daemon=True).start()

    def select_venv(self):
        """选择虚拟环境"""
        venv_path = filedialog.askdirectory(title="选择虚拟环境目录")
        if venv_path:
            # 检查是否为有效的虚拟环境
            if os.path.exists(os.path.join(venv_path, "pyvenv.cfg")):
                self.current_venv = venv_path
                self.venv_label.config(text=f"虚拟环境: {venv_path}")
                self.update_status(f"已选择虚拟环境: {venv_path}")
                # 自动列出该环境中的已安装包
                self.list_installed()
            else:
                messagebox.showwarning("警告", "选择的目录不是有效的虚拟环境")

    def detect_environment(self):
        """自动检测当前环境"""
        # 更新系统环境信息
        system_info = f"{platform.system()} {platform.release()}"
        architecture = platform.machine()  # 获取更准确的架构信息
        python_version = f"Python {sys.version.split()[0]} ({platform.architecture()[0]})"
        self.system_label.config(text=f"{system_info} ({architecture}) - {python_version}")
        
        # 检查是否在虚拟环境中
        if hasattr(sys, 'real_prefix') or (hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix):
            # 在虚拟环境中
            self.current_venv = sys.prefix
            self.venv_label.config(text=f"虚拟环境: {sys.prefix}")
            self.update_status("检测到虚拟环境")
            # 自动列出该环境中的已安装包
            self.list_installed()
            return

        # 检查当前目录下是否有虚拟环境
        possible_venv_paths = ["venv", ".venv", "env", ".env"]
        for venv_name in possible_venv_paths:
            venv_path = os.path.join(os.getcwd(), venv_name)
            if os.path.exists(os.path.join(venv_path, "pyvenv.cfg")):
                self.current_venv = venv_path
                self.venv_label.config(text=f"虚拟环境: {venv_path}")
                self.update_status(f"检测到本地虚拟环境: {venv_name}")
                # 自动列出该环境中的已安装包
                self.list_installed()
                return

        # 检查是否为嵌入式Python环境
        if "embed" in sys.executable.lower() or "embedded" in sys.executable.lower():
            self.venv_label.config(text="嵌入式环境")
            self.update_status("检测到嵌入式Python环境")
            return

        # 未检测到特殊环境
        self.current_venv = None
        self.venv_label.config(text="未选择虚拟环境")
        self.update_status("使用系统Python环境")

    def change_mirror(self, event=None):
        """切换镜像源"""
        self.current_mirror = self.mirror_var.get()
        self.update_status(f"已切换到镜像源: {self.current_mirror}")

    def get_pip_command(self):
        """获取pip命令，考虑虚拟环境和镜像源"""
        # 基础命令
        if self.current_venv:
            # 如果在虚拟环境中，使用虚拟环境的pip
            if sys.platform == "win32":
                pip_path = os.path.join(self.current_venv, "Scripts", "pip.exe")
            else:
                pip_path = os.path.join(self.current_venv, "bin", "pip")
            cmd = [pip_path]
        else:
            # 否则使用系统pip
            cmd = [sys.executable, "-m", "pip"]
            
        # 添加镜像源参数
        mirror_url = self.mirror_sources.get(self.current_mirror, "")
        if mirror_url:
            cmd.extend(["-i", mirror_url])
            
        return cmd

    def load_preset(self, preset_type):
        """加载预设包集合"""
        presets = {
            "ai_art": [
                {"name": "torch", "version": "", "operator": "", "source": "pypi"},
                {"name": "torchvision", "version": "", "operator": "", "source": "pypi"},
                {"name": "diffusers", "version": "", "operator": "", "source": "pypi"},
                {"name": "transformers", "version": "", "operator": "", "source": "pypi"},
                {"name": "accelerate", "version": "", "operator": "", "source": "pypi"}
            ],
            "ai_image": [
                {"name": "opencv-python", "version": "", "operator": "", "source": "pypi"},
                {"name": "Pillow", "version": "", "operator": "", "source": "pypi"},
                {"name": "scikit-image", "version": "", "operator": "", "source": "pypi"},
                {"name": "albumentations", "version": "", "operator": "", "source": "pypi"}
            ],
            "ai_audio": [
                {"name": "librosa", "version": "", "operator": "", "source": "pypi"},
                {"name": "soundfile", "version": "", "operator": "", "source": "pypi"},
                {"name": "pydub", "version": "", "operator": "", "source": "pypi"},
                {"name": "speechbrain", "version": "", "operator": "", "source": "pypi"}
            ],
            "ai_video": [
                {"name": "moviepy", "version": "", "operator": "", "source": "pypi"},
                {"name": "opencv-python", "version": "", "operator": "", "source": "pypi"},
                {"name": "av", "version": "", "operator": "", "source": "pypi"},
                {"name": "decord", "version": "", "operator": "", "source": "pypi"}
            ],
            "data_science": [
                {"name": "numpy", "version": "", "operator": "", "source": "pypi"},
                {"name": "pandas", "version": "", "operator": "", "source": "pypi"},
                {"name": "matplotlib", "version": "", "operator": "", "source": "pypi"},
                {"name": "seaborn", "version": "", "operator": "", "source": "pypi"},
                {"name": "scikit-learn", "version": "", "operator": "", "source": "pypi"}
            ],
            "web_dev": [
                {"name": "flask", "version": "", "operator": "", "source": "pypi"},
                {"name": "django", "version": "", "operator": "", "source": "pypi"},
                {"name": "fastapi", "version": "", "operator": "", "source": "pypi"},
                {"name": "requests", "version": "", "operator": "", "source": "pypi"},
                {"name": "gunicorn", "version": "", "operator": "", "source": "pypi"}
            ]
        }
        
        if preset_type in presets:
            # 添加预设包到当前列表
            for package in presets[preset_type]:
                # 检查是否已存在
                exists = False
                for existing_pkg in self.packages:
                    if existing_pkg['name'] == package['name']:
                        exists = True
                        break
                        
                if not exists:
                    self.packages.append(package)
                    
            self.refresh_tree()
            self.update_status(f"已加载预设包集合: {preset_type}")
        else:
            messagebox.showwarning("警告", f"未知的预设包集合: {preset_type}")

    def select_all(self):
        """选择所有包"""
        # 清除当前选择
        self.tree.selection_remove(self.tree.selection())
        # 选择所有项目
        for i in range(len(self.packages)):
            self.tree.selection_add(str(i))
        self.update_status(f"已选择 {len(self.packages)} 个项目")
    
    def deselect_all(self):
        """取消选择所有包"""
        self.tree.selection_remove(self.tree.selection())
        self.update_status("已取消所有选择")
        
    def list_installed(self):
        """列出已安装的包"""
        # 在新线程中执行列出已安装包的操作
        threading.Thread(target=self._list_installed_thread, daemon=True).start()

    def _list_installed_thread(self):
        """在后台线程中列出已安装的包"""
        try:
            # 使用after方法在主线程中更新UI
            self.root.after(0, lambda: self.update_status("正在获取已安装的包列表..."))
            cmd = self.get_pip_command() + ["list"]
            
            self.root.after(0, lambda: self.append_debug_info(f"执行列出已安装包命令: {' '.join(cmd)}"))
            self.root.after(0, lambda: self.append_debug_info("列出过程:"))
            
            # 使用Popen来实时获取输出
            process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
            
            # 实时读取输出
            output_lines = []
            while True:
                output = process.stdout.readline()
                if output == '' and process.poll() is not None:
                    break
                if output:
                    # 使用after方法在主线程中更新UI
                    self.root.after(0, lambda msg=output.strip(): self.append_debug_info(msg))
                    output_lines.append(output.strip())
            
            # 等待进程结束
            process.wait()
            
            if process.returncode == 0:
                # 解析输出
                # 跳过前两行标题
                packages_data = []
                for line in output_lines[2:]:
                    if line.strip():
                        # 过滤掉非包信息行（如notice信息）
                        if not line.startswith("[") and not line.startswith("WARNING"):
                            parts = line.split()
                            if len(parts) >= 2:
                                # 确保包名和版本号是有效的
                                name = parts[0]
                                version = parts[1]
                                # 检查包名是否包含非法字符
                                if "=" not in name and " " not in name:
                                    package_info = {
                                        'name': name,
                                        'version': version,
                                        'operator': '==',
                                        'source': 'pypi',
                                        'description': '已安装'
                                    }
                                    packages_data.append(package_info)
                
                # 更新显示
                self.root.after(0, lambda: setattr(self, 'packages', packages_data))
                self.root.after(0, lambda: self.refresh_tree())
                self.root.after(0, lambda count=len(packages_data): self.update_status(f"已列出 {count} 个已安装的包"))
                self.root.after(0, lambda count=len(packages_data): self.append_debug_info(f"已列出 {count} 个已安装的包"))
            else:
                self.root.after(0, lambda: self.update_status("获取已安装包列表失败"))
                self.root.after(0, lambda code=process.returncode: self.append_debug_info(f"获取已安装包列表失败，返回码: {code}"))
                self.root.after(0, lambda: messagebox.showerror("错误", f"获取已安装包列表失败"))
        except Exception as e:
            self.root.after(0, lambda msg=str(e): self.update_status(f"获取已安装包列表出错: {msg}"))
            self.root.after(0, lambda msg=str(e): self.append_debug_info(f"获取已安装包列表异常: {msg}"))
            self.root.after(0, lambda msg=str(e): messagebox.showerror("错误", f"获取已安装包列表出错: {msg}"))

    def save_installed_as_requirements(self):
        """将已安装的包保存为requirements文件"""
        # 弹出对话框让用户选择保存选项
        save_options = [("包含版本", True), ("不包含版本", False)]
        choice = messagebox.askyesno("保存选项", "是否包含版本信息？\n点击'是'包含版本，点击'否'不包含版本")
        
        # 选择保存位置
        file_path = filedialog.asksaveasfilename(
            title="保存已安装的包为requirements文件",
            initialfile="requirements",
            defaultextension=".txt",
            filetypes=[("Requirements files", "*.txt"), ("All files", "*.*")]
        )
        
        if file_path:
            try:
                # 生成内容
                lines = []
                include_version = choice  # True表示包含版本，False表示不包含
                
                for package in self.packages:
                    if include_version and package['version']:
                        # 如果操作符为空，则只使用包名和版本号
                        if package['operator']:
                            line = f"{package['name']}{package['operator']}{package['version']}"
                        else:
                            line = f"{package['name']}=={package['version']}"  # 默认使用==
                    else:
                        line = package['name']
                    lines.append(line)
                
                content = '\n'.join(lines)
                
                # 保存文件
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(content)
                    
                self.update_status(f"已安装包已保存到: {file_path}")
                messagebox.showinfo("成功", f"已安装包已保存到: {file_path}")
            except Exception as e:
                self.update_status(f"保存失败: {str(e)}")
                messagebox.showerror("错误", f"保存失败: {str(e)}")
    
    def search_package(self):
        """搜索包功能"""
        # 创建搜索对话框
        search_dialog = SearchPackageDialog(self.root)
        if search_dialog.result:
            package_name = search_dialog.result.strip()
            if package_name:
                # 检查包是否已安装
                description = self.check_package_installed(package_name)
                
                # 添加包到列表
                package = {
                    'name': package_name,
                    'version': '',
                    'operator': '',
                    'source': 'pypi',
                    'description': description
                }
                self.packages.append(package)
                self.refresh_tree()
                self.update_status(f"已添加包: {package_name}")
    
    def check_package_installed(self, package_name):
        """检查包是否已安装"""
        try:
            # 获取已安装的包信息
            installed_packages = {}
            if distributions is not None:
                # 使用importlib.metadata或importlib_metadata
                installed_packages = {dist.metadata['Name'].lower(): dist.version for dist in distributions()}
            else:
                # 回退到pkg_resources
                installed_packages = {pkg.key: pkg.version for pkg in working_set}
            
            # 检查包是否已安装
            pkg_key = package_name.lower()
            if pkg_key in installed_packages:
                return f"已安装: {installed_packages[pkg_key]}"
            else:
                return "未安装"
        except Exception as e:
            # 如果检查失败，返回未知状态
            return "状态未知"
    
    def register_drop_target(self):
        """注册拖放目标"""
        if HAS_DND:
            # 注册文件拖放事件
            self.root.drop_target_register(DND_FILES)
            self.root.dnd_bind('<<Drop>>', self.on_drop)
            # 添加视觉反馈
            self.root.dnd_bind('<<DragEnter>>', self.on_drag_enter)
            self.root.dnd_bind('<<DragLeave>>', self.on_drag_leave)
    
    def on_drag_enter(self, event):
        """拖拽进入窗口时的处理"""
        # 改变光标以提供视觉反馈
        self.root.configure(cursor="copy")
        self.update_status("拖入文件以导入requirements.txt")
    
    def on_drag_leave(self, event):
        """拖拽离开窗口时的处理"""
        # 恢复光标
        self.root.configure(cursor="")
        self.update_status("就绪")
    
    def on_drop(self, event):
        """处理文件拖放事件"""
        # 恢复光标
        self.root.configure(cursor="")
        
        try:
            # 获取拖放的文件路径
            file_path = event.data
            
            # 如果是多个文件，只处理第一个
            if isinstance(file_path, str):
                # 移除花括号（如果有）
                if file_path.startswith('{') and file_path.endswith('}'):
                    file_path = file_path[1:-1]
                
                # 检查文件扩展名
                if file_path.lower().endswith('.txt') or 'requirements' in file_path.lower():
                    # 打开并解析文件
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                    
                    self.current_file = file_path
                    self.parse_requirements(content)
                    self.refresh_tree()
                    self.update_status(f"已通过拖放导入文件: {file_path}")
                else:
                    messagebox.showwarning("警告", "请拖放requirements.txt文件")
                    self.update_status("拖放的文件不是requirements.txt文件")
            else:
                messagebox.showwarning("警告", "请拖放单个文件")
                self.update_status("拖放了多个文件")
                
        except Exception as e:
            messagebox.showerror("错误", f"拖放文件处理失败: {str(e)}")
            self.update_status(f"拖放文件处理失败: {str(e)}")


class PackageDialog:
    def __init__(self, parent, title, name="", version="", operator="==", source="pypi"):
        self.result = None
        
        self.top = tk.Toplevel(parent)
        self.top.title(title)
        self.top.geometry("400x250")
        self.top.transient(parent)
        self.top.grab_set()
        
        # 居中显示
        self.top.geometry("+%d+%d" % (parent.winfo_rootx()+50, parent.winfo_rooty()+50))
        
        # 创建输入字段
        frame = ttk.Frame(self.top)
        frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        
        # 包名
        ttk.Label(frame, text="包名:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.name_var = tk.StringVar(value=name)
        ttk.Entry(frame, textvariable=self.name_var, width=30).grid(row=0, column=1, sticky=tk.EW, pady=5)
        
        # 版本操作符
        ttk.Label(frame, text="操作符:").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.operator_var = tk.StringVar(value=operator)
        operator_combo = ttk.Combobox(frame, textvariable=self.operator_var, width=27)
        operator_combo['values'] = ('==', '>=', '<=', '>', '<', '!=', '~=', '')
        operator_combo.grid(row=1, column=1, sticky=tk.EW, pady=5)
        
        # 版本号
        ttk.Label(frame, text="版本号:").grid(row=2, column=0, sticky=tk.W, pady=5)
        self.version_var = tk.StringVar(value=version)
        ttk.Entry(frame, textvariable=self.version_var, width=30).grid(row=2, column=1, sticky=tk.EW, pady=5)
        
        # 来源
        ttk.Label(frame, text="来源:").grid(row=3, column=0, sticky=tk.W, pady=5)
        self.source_var = tk.StringVar(value=source)
        source_combo = ttk.Combobox(frame, textvariable=self.source_var, width=27)
        source_combo['values'] = ('pypi', 'git', '本地')
        source_combo.grid(row=3, column=1, sticky=tk.EW, pady=5)
        
        # 按钮
        button_frame = ttk.Frame(frame)
        button_frame.grid(row=4, column=0, columnspan=2, pady=20)
        
        ttk.Button(button_frame, text="确定", command=self.ok).pack(side=tk.LEFT, padx=10)
        ttk.Button(button_frame, text="取消", command=self.cancel).pack(side=tk.LEFT, padx=10)
        
        # 配置列权重
        frame.columnconfigure(1, weight=1)
        
        # 绑定回车键
        self.top.bind("<Return>", lambda e: self.ok())
        self.top.bind("<Escape>", lambda e: self.cancel())
        
        # 等待窗口关闭
        parent.wait_window(self.top)
        
    def ok(self):
        """确定按钮回调"""
        name = self.name_var.get().strip()
        if not name:
            messagebox.showwarning("警告", "请输入包名")
            return
            
        self.result = {
            'name': name,
            'version': self.version_var.get().strip(),
            'operator': self.operator_var.get(),
            'source': self.source_var.get()
        }
        self.top.destroy()
        
    def cancel(self):
        """取消按钮回调"""
        self.top.destroy()


class SearchPackageDialog:
    def __init__(self, parent):
        self.result = None
        
        self.top = tk.Toplevel(parent)
        self.top.title("搜索包")
        self.top.geometry("400x120")
        self.top.transient(parent)
        self.top.grab_set()
        
        # 居中显示
        self.top.geometry("+%d+%d" % (parent.winfo_rootx()+50, parent.winfo_rooty()+50))
        
        # 创建输入字段
        frame = ttk.Frame(self.top)
        frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        
        # 包名
        ttk.Label(frame, text="包名:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.name_var = tk.StringVar()
        entry = ttk.Entry(frame, textvariable=self.name_var, width=30)
        entry.grid(row=0, column=1, sticky=tk.EW, pady=5)
        entry.focus()
        
        # 按钮
        button_frame = ttk.Frame(frame)
        button_frame.grid(row=1, column=0, columnspan=2, pady=20)
        
        ttk.Button(button_frame, text="添加", command=self.ok).pack(side=tk.LEFT, padx=10)
        ttk.Button(button_frame, text="取消", command=self.cancel).pack(side=tk.LEFT, padx=10)
        
        # 配置列权重
        frame.columnconfigure(1, weight=1)
        
        # 绑定回车键
        self.top.bind("<Return>", lambda e: self.ok())
        self.top.bind("<Escape>", lambda e: self.cancel())
        
        # 等待窗口关闭
        parent.wait_window(self.top)
        
    def ok(self):
        """确定按钮回调"""
        name = self.name_var.get().strip()
        if not name:
            messagebox.showwarning("警告", "请输入包名")
            return
            
        self.result = name
        self.top.destroy()
        
    def cancel(self):
        """取消按钮回调"""
        self.top.destroy()


def main():
    # 如果支持拖放功能，则使用TkinterDnD创建根窗口
    if HAS_DND:
        root = TkinterDnD.Tk()
    else:
        root = tk.Tk()
    
    app = RequirementsManager(root)
    
    # 如果支持拖放功能，则注册拖放事件
    if HAS_DND:
        app.register_drop_target()
    
    root.mainloop()


if __name__ == "__main__":
    main()