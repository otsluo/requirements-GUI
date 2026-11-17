import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog
import subprocess
import sys
import os
import json
import zipfile
import shutil
import threading
from typing import List, Dict, Optional
import platform

# 尝试导入tkinterdnd2以支持拖放功能
try:
    import tkinterdnd2
    from tkinterdnd2 import DND_FILES
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
        # 如果支持拖放功能，则使用TkinterDnD创建根窗口
        if HAS_DND:
            self.root = root  # 使用传入的root参数
        else:
            self.root = root
        
        # 设置窗口标题和尺寸
        self.root.title("Requirements GUI-可视化管理工具 v0.6.1")
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
            "官方": "https://pypi.org/simple/",
            "清华": "https://pypi.tuna.tsinghua.edu.cn/simple/",
            "阿里": "https://mirrors.aliyun.com/pypi/simple/",
            "豆瓣": "https://pypi.douban.com/simple/",
            "中科大": "https://pypi.mirrors.ustc.edu.cn/simple/"
        }
        self.current_mirror = "默认"
        # 调试窗口相关
        self.debug_window_visible = True
        self.debug_text = None
        # 上次下载目录
        self.last_download_dir = None
        
        # 初始化预设包管理器
        self.preset_manager = PresetManager()
        
        self.setup_ui()
        self.create_menu()
        # 自动检测环境
        self.detect_environment()
        
        # 注册拖放事件（如果支持）
        self.register_drop_target()
    
    def _get_subprocess_kwargs(self):
        """获取 subprocess 调用的参数，在 Windows 上隐藏命令窗口"""
        kwargs = {}
        if sys.platform == 'win32':
            # 使用 CREATE_NO_WINDOW 隐藏命令窗口
            kwargs['creationflags'] = subprocess.CREATE_NO_WINDOW
            # 使用 STARTUPINFO 进一步确保窗口隐藏
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = subprocess.SW_HIDE
            kwargs['startupinfo'] = startupinfo
        return kwargs
    
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
        ttk.Button(venv_frame, text="选择虚拟环境", command=self.select_venv).pack(side=tk.LEFT, padx=5, pady=5)
        self.venv_label = ttk.Label(venv_frame, text="未选择虚拟环境")
        self.venv_label.pack(side=tk.LEFT, padx=2, pady=2)
        
        # 嵌入式环境区域
        embed_frame = ttk.LabelFrame(first_row_frame, text="嵌入式环境")
        embed_frame.pack(side=tk.LEFT, padx=(0, 10))
        
        ttk.Button(embed_frame, text="创建嵌入式", command=self.create_embed_venv).pack(side=tk.LEFT, padx=5, pady=5)
        ttk.Button(embed_frame, text="选择嵌入式环境", command=self.select_embedded_venv).pack(side=tk.LEFT, padx=5, pady=5)
        self.embed_label = ttk.Label(embed_frame, text="")
        self.embed_label.pack(side=tk.LEFT, padx=2, pady=2)
        
        # 镜像源区域
        mirror_frame = ttk.LabelFrame(first_row_frame, text="镜像源")
        mirror_frame.pack(side=tk.LEFT, padx=(0, 10))
        
        ttk.Label(mirror_frame, text="当前下载镜像源:").pack(side=tk.LEFT, padx=5, pady=5)
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
        
        # 启动器创建区域
        launcher_frame = ttk.LabelFrame(second_row_frame, text="启动器创建（bat文件启动）")
        launcher_frame.pack(side=tk.LEFT, padx=(0, 10))
        
        ttk.Button(launcher_frame, text="创建启动器", command=self.create_launcher).pack(side=tk.LEFT, padx=5, pady=5)
        
        # 实用功能区域
        usage_frame = ttk.LabelFrame(second_row_frame, text="实用功能")
        usage_frame.pack(side=tk.LEFT, padx=(0, 10))
        
        ttk.Button(usage_frame, text="GitHub项目下载", command=self.download_from_github).pack(side=tk.LEFT, padx=5, pady=5)
        ttk.Button(usage_frame, text="切换GitHub项目版本", command=self.switch_github_version).pack(side=tk.LEFT, padx=5, pady=5)
        ttk.Button(usage_frame, text="更新项目", command=self.update_project).pack(side=tk.LEFT, padx=5, pady=5)
        ttk.Button(usage_frame, text="打开CMD窗口", command=self.open_cmd_window).pack(side=tk.LEFT, padx=5, pady=5)
        
        # 预设包区域
        preset_frame = ttk.LabelFrame(main_frame, text="预设包集合")
        preset_frame.pack(fill=tk.X, pady=(0, 10))
        
        # 使用可自动换行的框架来容纳所有预设按钮
        preset_container = ttk.Frame(preset_frame)
        preset_container.pack(fill=tk.BOTH, expand=True)
        
        # 创建一个可以自动调整大小的框架来容纳预设按钮
        preset_button_frame = ttk.Frame(preset_container)
        preset_button_frame.pack(fill=tk.BOTH, expand=True)
        
        # 添加预设按钮的框架引用，方便后续更新
        self.preset_button_frame = preset_button_frame
        
        # 动态创建预设按钮
        self.create_preset_buttons()
        
        # 包管理区域
        package_frame = ttk.LabelFrame(main_frame, text="包管理")
        package_frame.pack(fill=tk.BOTH, expand=True)
        
        # 工具栏（分两行，避免窗口宽度不足时按钮被裁掉）
        toolbar_frame = ttk.Frame(package_frame)
        toolbar_frame.pack(fill=tk.X, pady=(0, 5))
        toolbar_row1 = ttk.Frame(toolbar_frame)
        toolbar_row1.pack(fill=tk.X, pady=(0, 2))
        toolbar_row2 = ttk.Frame(toolbar_frame)
        toolbar_row2.pack(fill=tk.X)
        
        ttk.Button(toolbar_row1, text="添加包", command=self.add_package).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar_row1, text="删除选中", command=self.remove_package).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar_row1, text="全选", command=self.select_all).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar_row1, text="取消选择", command=self.deselect_all).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar_row1, text="刷新列表", command=self.refresh_packages).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar_row1, text="搜索包", command=self.search_package).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar_row1, text="安装选中", command=self.install_selected).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar_row2, text="更新选中", command=self.update_selected).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar_row2, text="降级选中", command=self.downgrade_selected).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar_row2, text="卸载选中", command=self.uninstall_selected).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar_row2, text="列出已安装", command=self.list_installed).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar_row2, text="保存已安装", command=self.save_installed_as_requirements).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar_row2, text="批量操作符", command=self.batch_operator).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar_row2, text="冲突检测", command=self.check_conflicts).pack(side=tk.LEFT, padx=2)
        
        # 依赖包列表标题
        ttk.Label(package_frame, text="依赖包列表").pack(fill=tk.X, pady=(5, 2))
        
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
                self.refresh_packages()  # 对比已安装包并标记
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
        
        # 检查是否为Git来源
        if line.startswith('git+'):
            source = 'git'
            # 提取git URL
            git_url = line[4:]  # 移除"git+"前缀
            # 移除#egg=部分
            if '#egg=' in git_url:
                git_url = git_url.split('#egg=')[0]
            name = git_url
            version = git_url
            # 从URL中提取包名
            if 'github.com' in git_url:
                parts = git_url.strip('/').split('/')
                if len(parts) >= 2:
                    name = parts[-1]
            return {
                'name': name,
                'version': version,
                'operator': operator,
                'source': source,
                'description': ''
            }
        
        # 检查是否为本地路径
        if line.startswith('/') or line.startswith('C:\\') or line.startswith('D:\\') or (len(line) > 2 and line[1] == ':'):
            source = '本地'
            name = line
            return {
                'name': name,
                'version': version,
                'operator': operator,
                'source': source,
                'description': ''
            }
            
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
            source = package.get('source', 'pypi')
            name = package['name']
            version = package.get('version', '')
            
            if source == 'git':
                if version:
                    lines.append(f"git+{version}")
                else:
                    lines.append(name)
            elif source == '本地':
                if version:
                    lines.append(version)
                else:
                    lines.append(name)
            else:
                if version:
                    # 正确处理版本操作符，确保格式为 name==version
                    if package['operator'] and version.startswith(package['operator']):
                        line = f"{name}{version}"
                    else:
                        # 如果版本信息不包含操作符，则使用存储的操作符
                        line = f"{name}{package['operator']}{version}"
                else:
                    line = name
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
        
        # 清除高亮标签配置（如果存在）
        self.tree.tag_configure('highlight', background='', foreground='')
            
    def add_package(self):
        """添加新包"""
        dialog = PackageDialog(self.root, "添加包")
        if dialog.result:
            # 处理版本信息，考虑空操作符的情况
            version_str = ''
            source = dialog.result['source']
            if dialog.result['version']:
                if dialog.result['operator']:
                    version_str = dialog.result['operator'] + dialog.result['version']
                else:
                    # 对于本地和git来源，不添加操作符前缀
                    if source == '本地' or source == 'git':
                        version_str = dialog.result['version']
                    else:
                        # 对于pypi来源，如果操作符为空，默认使用==操作符
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
            
            # 清除可能存在的高亮显示
            self.clear_highlight()
            
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
            
            # 清除可能存在的高亮显示
            self.clear_highlight()
            
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
            source = dialog.result['source']
            if dialog.result['version']:
                if dialog.result['operator']:
                    version_str = dialog.result['operator'] + dialog.result['version']
                else:
                    # 对于本地和git来源，不添加操作符前缀
                    if source == '本地' or source == 'git':
                        version_str = dialog.result['version']
                    else:
                        # 对于pypi来源，如果操作符为空，默认使用==操作符
                        version_str = '==' + dialog.result['version']
            
            self.packages[idx] = {
                'name': dialog.result['name'],
                'version': version_str,
                'operator': dialog.result['operator'],
                'source': dialog.result['source'],
                'description': ''
            }
            self.refresh_tree()
            
            # 清除可能存在的高亮显示
            self.clear_highlight()
            
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
            # 根据是否选择了虚拟环境来决定使用哪个环境进行对比
            installed_packages = {}
            
            try:
                # 使用pip freeze命令获取已安装的包,这样会根据当前环境(系统或虚拟环境)正确获取
                cmd = self.get_pip_command() + ["freeze"]
                result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=30, **self._get_subprocess_kwargs())
                
                if result.returncode == 0:
                    # 解析pip freeze的输出
                    for line in result.stdout.strip().split('\n'):
                        if line and '==' in line:
                            name, version = line.split('==', 1)
                            installed_packages[name.lower()] = version
                else:
                    # 如果pip freeze失败，回退到原来的实现
                    if distributions is not None:
                        # 使用importlib.metadata或importlib_metadata
                        installed_packages = {dist.metadata['Name'].lower(): dist.version for dist in distributions()}
                    else:
                        # 回退到pkg_resources
                        installed_packages = {pkg.key: pkg.version for pkg in working_set}
            except Exception:
                # 如果执行pip freeze出现异常，也回退到原来的实现
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
                    package['description'] = ""  # 未安装的包留空
                    
            self.root.after(0, lambda: self.refresh_tree())
            self.root.after(0, lambda: self.update_status("包列表刷新完成"))
        except Exception as e:
            self.root.after(0, lambda: self.update_status(f"刷新失败: {str(e)}"))
            self.root.after(0, lambda: messagebox.showerror("错误", f"刷新包列表失败: {str(e)}"))
    
    def _get_install_string(self, package: dict) -> str:
        """根据包的来源生成安装字符串"""
        source = package.get('source', 'pypi')
        name = package['name']
        version = package.get('version', '')
        
        if source == 'git':
            if version:
                return f"git+{version}#egg={name}"
            else:
                return f"git+https://github.com/{name}.git"
        elif source == '本地':
            if version:
                # 移除可能存在的操作符前缀（如==）
                if version.startswith('=='):
                    return version[2:]
                elif version.startswith('>='):
                    return version[2:]
                elif version.startswith('<='):
                    return version[2:]
                elif version.startswith('>'):
                    return version[1:]
                elif version.startswith('<'):
                    return version[1:]
                elif version.startswith('!='):
                    return version[2:]
                elif version.startswith('~='):
                    return version[2:]
                elif version.startswith('==='):
                    return version[3:]
                else:
                    return version
            else:
                return name
        else:
            if version:
                return f"{name}{version}"
            else:
                return name
            
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
            install_str = self._get_install_string(package)
            packages_to_install.append(install_str)
                
        self.install_packages(packages_to_install)
        
    def install_all(self):
        """安装所有包"""
        if not self.packages:
            messagebox.showwarning("警告", "没有包可以安装")
            return
            
        packages_to_install = []
        for package in self.packages:
            install_str = self._get_install_string(package)
            packages_to_install.append(install_str)
                
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
            
            # 添加镜像源参数到正确位置（在install之后）
            mirror_url = self.mirror_sources.get(self.current_mirror, "")
            if mirror_url:
                cmd.extend(["-i", mirror_url])
            
            returncode, output = self._run_pip_command(cmd, "执行安装命令")
            
            # 检测源码构建失败（常见于新版Python缺少预编译wheel，且环境缺setuptools构建后端）
            if returncode != 0 and self._is_build_backend_error(output):
                self.root.after(0, lambda: self.append_debug_info("检测到构建后端缺失，正在自动安装 setuptools 和 wheel 后重试..."))
                setup_cmd = self.get_pip_command() + ["install", "setuptools", "wheel"]
                if mirror_url:
                    setup_cmd.extend(["-i", mirror_url])
                setup_code, _ = self._run_pip_command(setup_cmd, "执行补装命令")
                if setup_code == 0:
                    # 重试：使用 --no-build-isolation，让构建过程直接使用刚装好的setuptools
                    retry_cmd = self.get_pip_command() + ["install", "--no-build-isolation"] + packages
                    if mirror_url:
                        retry_cmd.extend(["-i", mirror_url])
                    returncode, output = self._run_pip_command(retry_cmd, "执行重试安装命令")
            
            if returncode == 0:
                self.root.after(0, lambda: self.update_status("包安装成功"))
                self.root.after(0, lambda: self.append_debug_info("安装完成"))
                self.root.after(0, lambda: self.refresh_packages())  # 刷新包列表以更新描述信息
            else:
                self.root.after(0, lambda: self.update_status("包安装失败"))
                self.root.after(0, lambda: self.append_debug_info(f"安装失败，返回码: {returncode}"))
                self.root.after(0, lambda: messagebox.showerror("错误", "包安装失败，请查看调试窗口了解详情"))
            
            # 检测pip输出中的依赖冲突提示，询问用户是否一键修复
            conflicts = self._parse_dependency_conflicts(output)
            if conflicts:
                self.root.after(0, lambda c=conflicts: self._prompt_fix_conflicts(c))
        except Exception as e:
            self.root.after(0, lambda: self.update_status(f"安装出错: {str(e)}"))
            self.root.after(0, lambda: self.append_debug_info(f"安装异常: {str(e)}"))
            self.root.after(0, lambda: messagebox.showerror("错误", f"安装过程中出现错误: {str(e)}"))

    @staticmethod
    def _parse_dependency_conflicts(outputs):
        """解析pip输出中的依赖冲突行，返回冲突列表
        兼容两种格式:
        - pip install: 'datasets 4.4.1 requires pyarrow>=21.0.0, but you have pyarrow 20.0.0 which is incompatible.'
        - pip check:   'videocaptioner 1.4.1 has requirement pillow>=12.0.0, but you have pillow 11.3.0.'
        每项: {'requirer': 依赖方描述, 'requirement': 需求字符串(含包名+版本约束), 'installed': 已装版本}
        """
        import re
        conflicts = []
        seen = set()
        # 需求字符串可含逗号（如 websockets<17.0,>=13.0.0），用非贪婪匹配直到 ", but you have"
        # "which is incompatible" 仅出现在pip install输出中，pip check没有，故设为可选
        pattern = re.compile(
            r'(\S+)\s+(\S+)\s+(?:requires|has requirement)\s+([A-Za-z0-9._-]+.+?),\s*but you have\s+(\S+)\s+(\S+)(?:\s+which is incompatible)?',
            re.IGNORECASE)
        for line in outputs:
            m = pattern.search(line)
            if m:
                requirer_name, requirer_ver, requirement, installed_name, installed = m.groups()
                key = requirement.lower()
                if key not in seen:
                    seen.add(key)
                    conflicts.append({
                        'requirer': f"{requirer_name} {requirer_ver}",
                        'requirement': requirement,
                        'installed': installed.rstrip('.'),  # pip check行尾的句号不算版本号
                    })
        return conflicts

    def _prompt_fix_conflicts(self, conflicts):
        """弹出可勾选的冲突列表对话框，用户选择要修复哪些冲突"""
        dialog = tk.Toplevel(self.root)
        dialog.title("依赖冲突")
        dialog.geometry("560x420")
        dialog.transient(self.root)
        dialog.grab_set()
        
        ttk.Label(dialog, text="检测到以下依赖冲突，勾选需要修复的项：", font=("", 10, "bold")).pack(anchor=tk.W, padx=10, pady=(10, 5))
        
        # 冲突列表（带复选框，默认全部勾选）
        list_frame = ttk.Frame(dialog)
        list_frame.pack(fill=tk.BOTH, expand=True, padx=10)
        
        canvas = tk.Canvas(list_frame, borderwidth=1, relief=tk.SOLID)
        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=canvas.yview)
        check_frame = ttk.Frame(canvas)
        check_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=check_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        check_vars = []
        for i, c in enumerate(conflicts):
            var = tk.BooleanVar(master=dialog, value=True)
            text = f"{c['requirer']} 需要 {c['requirement']}（当前: {c['installed']}）"
            ttk.Checkbutton(check_frame, text=text, variable=var).pack(anchor=tk.W, pady=2)
            check_vars.append((var, c))
        
        # 全选/全不选
        def toggle_all(value):
            for var, _ in check_vars:
                var.set(value)
        
        sel_frame = ttk.Frame(dialog)
        sel_frame.pack(fill=tk.X, padx=10, pady=5)
        ttk.Button(sel_frame, text="全选", command=lambda: toggle_all(True), width=8).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(sel_frame, text="全不选", command=lambda: toggle_all(False), width=8).pack(side=tk.LEFT)
        
        # 操作按钮
        def on_fix():
            selected = [c for var, c in check_vars if var.get()]
            if not selected:
                messagebox.showwarning("提示", "请至少勾选一个要修复的冲突", parent=dialog)
                return
            dialog.destroy()
            import threading
            threading.Thread(target=self._fix_conflicts_thread, args=(selected,), daemon=True).start()
        
        def on_ignore():
            dialog.destroy()
            self.root.after(0, lambda: self.update_status("已忽略依赖冲突"))
        
        button_frame = ttk.Frame(dialog)
        button_frame.pack(fill=tk.X, padx=10, pady=(5, 10))
        ttk.Button(button_frame, text="修复选中项", command=on_fix).pack(side=tk.RIGHT, padx=(5, 0))
        ttk.Button(button_frame, text="忽略", command=on_ignore).pack(side=tk.RIGHT)
        
        dialog.wait_window()

    def _fix_conflicts_thread(self, conflicts):
        """后台线程执行依赖冲突一键修复"""
        try:
            env_name = self.embed_label.cget("text") or self.venv_label.cget("text")
            if not self.current_venv:
                env_name = "系统Python环境"
            self.root.after(0, lambda n=env_name: self.append_debug_info(f"修复目标环境: {n}"))
            # 按目标包名合并版本约束，避免重复安装同一个包
            # 例如 pyarrow>=21.0.0 与 pyarrow<22 合并为 pyarrow>=21.0.0,<22
            import re
            merged = {}
            order = []
            for c in conflicts:
                req = c['requirement'].strip()
                m = re.match(r'([A-Za-z0-9._-]+)(.*)', req)
                if not m:
                    continue
                name, spec = m.group(1), m.group(2).strip()
                key = name.lower().replace('_', '-')
                if key not in merged:
                    merged[key] = {'name': name, 'specs': set()}
                    order.append(key)
                if spec:
                    # 拆分逗号分隔的多个约束
                    for s in spec.split(','):
                        s = s.strip()
                        if s:
                            merged[key]['specs'].add(s)
            
            install_args = []
            for key in order:
                item = merged[key]
                req_str = item['name'] + (",".join(sorted(item['specs'])) if item['specs'] else "")
                install_args.append(req_str)
            
            if not install_args:
                self.root.after(0, lambda: messagebox.showinfo("提示", "未能解析出可修复的依赖约束"))
                return
            
            self.root.after(0, lambda: self.update_status("正在修复依赖冲突..."))
            self.root.after(0, lambda: self.append_debug_info(f"修复安装目标: {', '.join(install_args)}"))
            
            cmd = self.get_pip_command() + ["install"] + install_args
            mirror_url = self.mirror_sources.get(self.current_mirror, "")
            if mirror_url:
                cmd.extend(["-i", mirror_url])
            
            returncode, output = self._run_pip_command(cmd, "执行修复命令")
            
            if returncode != 0:
                # 约束之间可能互相矛盾（如一个包要求>=21另一个要求<20），pip会解析失败
                self.root.after(0, lambda: self.update_status("依赖冲突修复失败"))
                self.root.after(0, lambda: messagebox.showerror("错误", "自动修复失败：可能存在互相矛盾的版本约束，请查看调试窗口手动处理"))
                return
            
            # 修复完成后运行 pip check 验证结果
            self.root.after(0, lambda: self.append_debug_info("修复完成，正在验证依赖关系..."))
            check_cmd = self.get_pip_command() + ["check"]
            check_code, check_output = self._run_pip_command(check_cmd, "执行验证命令")
            
            remaining = self._parse_dependency_conflicts(check_output)
            if check_code == 0 and not remaining:
                self.root.after(0, lambda: self.update_status("依赖冲突修复成功"))
                self.root.after(0, lambda: messagebox.showinfo("成功", "依赖冲突已全部修复"))
            else:
                detail = "\n".join(f"• {c['requirement']}" for c in remaining[:10]) if remaining else "请查看调试窗口"
                self.root.after(0, lambda: self.update_status("部分冲突已修复"))
                self.root.after(0, lambda d=detail: messagebox.showwarning("部分修复", f"仍有未解决的冲突:\n{d}"))
            self.root.after(0, lambda: self.refresh_packages())
        except Exception as e:
            self.root.after(0, lambda: self.update_status(f"修复出错: {str(e)}"))
            self.root.after(0, lambda: messagebox.showerror("错误", f"修复依赖冲突时出错: {str(e)}"))

    def check_conflicts(self):
        """手动检测当前环境的依赖冲突（pip check）
        未选择虚拟/嵌入式环境时，检测系统Python环境"""
        import threading
        threading.Thread(target=self._check_conflicts_thread, daemon=True).start()

    def _check_conflicts_thread(self):
        """后台线程执行依赖冲突检测"""
        try:
            if self.current_venv:
                env_desc = self.embed_label.cget("text") or self.venv_label.cget("text")
            else:
                env_desc = "系统Python环境"
            self.root.after(0, lambda e=env_desc: self.append_debug_info(f"检测目标环境: {e}"))
            self.root.after(0, lambda: self.update_status("正在检测依赖冲突..."))
            cmd = self.get_pip_command() + ["check"]
            returncode, output = self._run_pip_command(cmd, "执行检测命令")
            
            conflicts = self._parse_dependency_conflicts(output)
            if returncode == 0 and not conflicts:
                self.root.after(0, lambda: self.update_status("未检测到依赖冲突"))
                self.root.after(0, lambda: messagebox.showinfo("检测完成", "当前环境依赖关系正常，未检测到冲突"))
            elif conflicts:
                self.root.after(0, lambda: self.update_status(f"检测到 {len(conflicts)} 个依赖冲突"))
                self.root.after(0, lambda c=conflicts: self._prompt_fix_conflicts(c))
            else:
                # pip check报错但未能解析出标准格式的冲突行，展示原始输出避免空对话框
                raw = "\n".join(line.strip() for line in output if line.strip())[:800]
                self.root.after(0, lambda: self.update_status("检测到异常但无法解析冲突详情"))
                self.root.after(0, lambda r=raw: messagebox.showwarning("检测完成", f"pip check报告了问题，但输出格式无法自动解析:\n\n{r}\n\n完整内容请查看调试窗口"))
        except Exception as e:
            self.root.after(0, lambda: self.update_status(f"检测出错: {str(e)}"))
            self.root.after(0, lambda: messagebox.showerror("错误", f"依赖冲突检测出错: {str(e)}"))

    def _run_pip_command(self, cmd, log_prefix):
        """执行pip命令并实时输出日志，返回(返回码, 输出内容列表)"""
        self.root.after(0, lambda: self.append_debug_info(f"{log_prefix}: {' '.join(cmd)}"))
        self.root.after(0, lambda: self.append_debug_info("安装过程:"))
        
        # 使用Popen来实时获取输出
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding='utf-8', errors='replace', bufsize=1, **self._get_subprocess_kwargs())
        
        # 实时读取输出
        outputs = []
        while True:
            output = process.stdout.readline()
            if output == '' and process.poll() is not None:
                break
            if output:
                outputs.append(output)
                self.root.after(0, lambda out=output: self.append_debug_info(out.strip()))
        
        # 等待进程结束
        process.wait()
        return process.returncode, outputs

    @staticmethod
    def _is_build_backend_error(outputs):
        """判断pip输出是否为源码构建后端缺失错误（如缺少setuptools）"""
        text = "".join(outputs).lower()
        return ("no module named 'setuptools'" in text
                or "backend-unavailable" in text
                or "cannot import build backend" in text)
            
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
            install_str = self._get_install_string(package)
            packages_to_update.append(install_str)
            
        self.update_packages(packages_to_update)
        
    def downgrade_selected(self):
        """降级选中的包"""
        selected_items = self.tree.selection()
        if not selected_items:
            messagebox.showwarning("警告", "请先选择要降级的包")
            return
            
        packages_to_downgrade = []
        for item in selected_items:
            idx = int(item)
            package = self.packages[idx]
            install_str = self._get_install_string(package)
            packages_to_downgrade.append(install_str)
            
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
            
            # 特殊处理pip包的更新 - 使用正确的命令格式避免权限问题
            if "pip" in packages:
                # 如果要更新pip，使用python -m pip格式确保正确执行
                cmd = self.get_pip_command()
                # 检查是否是直接调用pip命令，如果是则改为使用python -m pip
                if len(cmd) == 1 and (cmd[0].endswith("pip.exe") or cmd[0].endswith("pip")):
                    # 替换为python -m pip格式
                    python_cmd = cmd[0].replace("pip.exe", "python.exe").replace("pip", "python")
                    if not os.path.exists(python_cmd):
                        # 如果找不到对应的python.exe，尝试其他方式
                        if self.current_venv:
                            if sys.platform == "win32":
                                python_cmd = os.path.join(self.current_venv, "Scripts", "python.exe")
                            else:
                                python_cmd = os.path.join(self.current_venv, "bin", "python")
                        else:
                            python_cmd = sys.executable
                    cmd = [python_cmd, "-m", "pip"]
                elif len(cmd) == 3 and cmd[1] == "-m" and cmd[2] == "pip":
                    # 已经是python -m pip格式，无需更改
                    pass
                else:
                    # 其他情况，尝试转换为python -m pip格式
                    if self.current_venv:
                        if sys.platform == "win32":
                            python_cmd = os.path.join(self.current_venv, "Scripts", "python.exe")
                        else:
                            python_cmd = os.path.join(self.current_venv, "bin", "python")
                        if os.path.exists(python_cmd):
                            cmd = [python_cmd, "-m", "pip"]
                        # 如果找不到python，保持原有命令
                    else:
                        cmd = [sys.executable, "-m", "pip"]
                
                # 添加更新命令
                cmd.extend(["install", "--upgrade"])
                cmd.extend(packages)
            else:
                # 非pip包更新，使用原有逻辑
                cmd = self.get_pip_command() + ["install", "--upgrade"] + packages
            
            # 添加镜像源参数到正确位置（在install之后）
            mirror_url = self.mirror_sources.get(self.current_mirror, "")
            if mirror_url:
                cmd.extend(["-i", mirror_url])
            
            self.root.after(0, lambda: self.append_debug_info(f"执行更新命令: {' '.join(cmd)}"))
            self.root.after(0, lambda: self.append_debug_info("更新过程:"))
            
            # 使用Popen来实时获取输出
            process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding='utf-8', errors='replace', bufsize=1, **self._get_subprocess_kwargs())
            
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
            
            # 添加镜像源参数到正确位置（在install之后）
            mirror_url = self.mirror_sources.get(self.current_mirror, "")
            if mirror_url:
                cmd.extend(["-i", mirror_url])
            
            self.root.after(0, lambda: self.append_debug_info(f"执行降级命令: {' '.join(cmd)}"))
            self.root.after(0, lambda: self.append_debug_info("降级过程:"))
            
            # 使用Popen来实时获取输出
            process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding='utf-8', errors='replace', bufsize=1, **self._get_subprocess_kwargs())
            
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
            # 注意：pip uninstall 不支持 -i 镜像源参数（无需联网下载），不能附加
            
            self.root.after(0, lambda: self.append_debug_info(f"执行卸载命令: {' '.join(cmd)}"))
            self.root.after(0, lambda: self.append_debug_info("卸载过程:"))
            
            # 使用Popen来实时获取输出
            process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding='utf-8', errors='replace', bufsize=1, **self._get_subprocess_kwargs())
            
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
            # 注意：pip freeze 不支持 -i 镜像源参数（无需联网下载），不能附加
            
            self.root.after(0, lambda: self.append_debug_info(f"执行生成requirements命令: {' '.join(cmd)}"))
            self.root.after(0, lambda: self.append_debug_info("生成过程:"))
            
            # 使用Popen来实时获取输出
            process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding='utf-8', errors='replace', bufsize=1, **self._get_subprocess_kwargs())
            
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
        ttk.Label(info_frame, text="这是一个用于管理Python包依赖的图形界面工具", wraplength=350).pack(pady=2)
        
        # 添加彩蛋功能：连续点击作者名称5次触发彩蛋
        self.click_count = 0
        self.last_click_time = 0
        
        def on_author_click(event=None):
            import time
            current_time = time.time()
            
            # 如果两次点击间隔超过2秒，重置计数器
            if current_time - self.last_click_time > 2:
                self.click_count = 0
                
            self.click_count += 1
            self.last_click_time = current_time
            
            # 如果点击次数达到5次，触发彩蛋
            if self.click_count >= 5:
                self.show_easter_egg(about_dialog)
                self.click_count = 0  # 重置计数器
                
        author_label = ttk.Label(info_frame, text="作者: otsluo")
        author_label.pack(pady=2)
        author_label.bind("<Button-1>", on_author_click)
        
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

    def show_easter_egg(self, parent):
        """显示彩蛋对话框"""
        # 创建彩蛋对话框
        egg_dialog = tk.Toplevel(parent)
        egg_dialog.title("🎉 恭喜你发现彩蛋！")
        egg_dialog.geometry("400x300")
        egg_dialog.resizable(False, False)
        
        # 居中显示对话框
        egg_dialog.transient(parent)
        egg_dialog.grab_set()
        
        # 创建标签框架用于显示彩蛋内容
        egg_frame = ttk.Frame(egg_dialog)
        egg_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        
        # 显示彩蛋信息
        ttk.Label(egg_frame, text="🎉 恭喜你发现隐藏彩蛋！", font=("微软雅黑", 14, "bold"), foreground="orange").pack(pady=(0, 10))
        
        # 添加有趣的彩蛋内容
        ttk.Label(egg_frame, text="谢谢你使用 Requirements GUI 工具！", font=("微软雅黑", 10)).pack(pady=5)
        ttk.Label(egg_frame, text="希望这个小工具能为你的开发工作带来便利。", wraplength=350).pack(pady=5)
        
        # 添加一个有趣的引用
        quotes = [
            "代码改变世界！",
            "编程是一门艺术！",
            "每个bug都是成长的机会！",
            "保持好奇心，不断学习！",
            "优雅的代码来自精心的设计！"
        ]
        
        import random
        quote = random.choice(quotes)
        ttk.Label(egg_frame, text=f"「{quote}」", font=("微软雅黑", 10, "italic"), foreground="blue").pack(pady=10)
        
        # 添加感谢信息
        ttk.Label(egg_frame, text="感谢你的支持与鼓励！", font=("微软雅黑", 10)).pack(pady=5)
        ttk.Label(egg_frame, text="如果你喜欢这个工具，欢迎在GitHub上给我们一个Star⭐", wraplength=350).pack(pady=5)
        
        # 添加按钮框架
        button_frame = ttk.Frame(egg_dialog)
        button_frame.pack(fill=tk.X, padx=20, pady=(0, 20))
        
        ttk.Button(button_frame, text="关闭", command=egg_dialog.destroy).pack(side=tk.RIGHT)
        
        # 居中对话框
        egg_dialog.update_idletasks()
        x = (egg_dialog.winfo_screenwidth() // 2) - (egg_dialog.winfo_width() // 2)
        y = (egg_dialog.winfo_screenheight() // 2) - (egg_dialog.winfo_height() // 2)
        egg_dialog.geometry(f"+{x}+{y}")

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

    def _create_venv_thread(self, venv_dir, is_embedded=False):
        """在后台线程中创建虚拟环境（is_embedded为True时创建的是嵌入式环境）"""
        env_type_name = "嵌入式环境" if is_embedded else "虚拟环境"
        try:
            self.root.after(0, lambda: self.update_status(f"正在创建{env_type_name}: {venv_dir}"))
            self.root.after(0, lambda: self.append_debug_info(f"开始创建{env_type_name}: {venv_dir}"))
            
            # 按各自的标准方式创建：虚拟环境用venv模块，嵌入式用embeddable标准布局
            if is_embedded:
                self._create_embed_standard(venv_dir)
            else:
                self._create_venv_standard(venv_dir)
            
            if is_embedded:
                # 嵌入式环境：显示到嵌入式环境标签，并清空虚拟环境标签
                self.root.after(0, lambda: setattr(self, 'current_venv', venv_dir))
                self.root.after(0, lambda: self.venv_label.config(text=""))
                self.root.after(0, lambda: self.embed_label.config(text=f"嵌入式环境: {venv_dir}"))
            else:
                # 普通虚拟环境：显示到虚拟环境标签，并清空嵌入式环境标签
                self.root.after(0, lambda: setattr(self, 'current_venv', venv_dir))
                self.root.after(0, lambda: self.embed_label.config(text=""))
                self.root.after(0, lambda: self.venv_label.config(text=f"虚拟环境: {venv_dir}"))
            self.root.after(0, lambda: self.append_debug_info(f"{env_type_name}创建成功: {venv_dir}"))
            self.root.after(0, lambda: self.update_status(f"{env_type_name}创建成功"))
            self.root.after(0, lambda: messagebox.showinfo("成功", f"{env_type_name}创建成功: {venv_dir}"))
            # 自动刷新包列表以显示新环境中的包
            self.root.after(0, lambda: self.refresh_packages())
        except Exception as e:
            self.root.after(0, lambda msg=str(e): self.update_status(f"创建{env_type_name}失败: {msg}"))
            self.root.after(0, lambda msg=str(e): self.append_debug_info(f"创建{env_type_name}失败: {msg}"))
            self.root.after(0, lambda msg=str(e): messagebox.showerror("错误", f"创建{env_type_name}失败: {msg}"))
    
    def _create_venv_standard(self, venv_dir):
        """以标准venv方式创建虚拟环境（轻量，依赖系统Python，不可整体拷走）"""
        real_python = self._get_system_python()
        if not real_python:
            raise Exception("找不到系统中安装的Python解释器，请先安装Python再使用此功能")
        
        self.root.after(0, lambda: self.append_debug_info(f"使用Python: {real_python}"))
        
        # 等价于命令行执行 python -m venv <目录>，会自动生成 pyvenv.cfg、
        # Scripts/python.exe 并通过 ensurepip 安装 pip
        # 显式指定系统Python，避免打包环境下误用自身exe
        result = subprocess.run([real_python, '-m', 'venv', venv_dir],
                                capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=300,
                                **self._get_subprocess_kwargs())
        if result.returncode != 0:
            raise Exception(f"venv创建失败: {result.stderr.strip() or result.stdout.strip()}")
    
    def _create_embed_standard(self, venv_dir):
        """以官方嵌入式（embeddable）标准布局创建环境（自包含，可整体拷走使用）"""
        if sys.platform != 'win32':
            raise Exception("标准嵌入式布局（embeddable）仅支持Windows平台")
        
        real_python = self._get_system_python()
        if not real_python:
            raise Exception("找不到系统中安装的Python解释器，请先安装Python再使用此功能")
        python_home = os.path.dirname(real_python)
        self.root.after(0, lambda: self.append_debug_info(f"使用Python: {real_python}"))
        
        # 查询目标Python版本号（如311），用于命名 pythonXXX.dll / pythonXXX.zip / pythonXXX._pth
        ver_result = subprocess.run(
            [real_python, '-c', 'import sys; print(f"{sys.version_info.major}{sys.version_info.minor}")'],
            capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=30, **self._get_subprocess_kwargs())
        if ver_result.returncode != 0:
            raise Exception("无法获取目标Python版本号")
        ver_tag = ver_result.stdout.strip()
        
        os.makedirs(venv_dir, exist_ok=True)
        
        # 1. 复制解释器可执行文件到根目录（官方嵌入式布局特征：python.exe在根目录而非Scripts）
        for exe in ('python.exe', 'pythonw.exe'):
            src = os.path.join(python_home, exe)
            if os.path.exists(src):
                shutil.copy2(src, os.path.join(venv_dir, exe))
        
        # 2. 复制根目录下的运行时DLL（python3.dll、pythonXXX.dll、vcruntime、libffi等）
        for item in os.listdir(python_home):
            if item.lower().endswith('.dll'):
                shutil.copy2(os.path.join(python_home, item), os.path.join(venv_dir, item))
        
        # 3. 复制DLLs目录（pip需要的_ssl等扩展模块）
        src_dlls = os.path.join(python_home, 'DLLs')
        if os.path.exists(src_dlls):
            shutil.copytree(src_dlls, os.path.join(venv_dir, 'DLLs'), dirs_exist_ok=True)
        
        # 4. 将Lib标准库压缩为 pythonXXX.zip（排除site-packages和缓存），与官方嵌入式包一致
        self.root.after(0, lambda: self.append_debug_info(f"正在压缩标准库到 python{ver_tag}.zip ..."))
        src_lib = os.path.join(python_home, 'Lib')
        zip_path = os.path.join(venv_dir, f'python{ver_tag}.zip')
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
            for root, dirs, files in os.walk(src_lib):
                # 排除第三方包目录和编译缓存
                dirs[:] = [d for d in dirs if d not in ('site-packages', '__pycache__')]
                for fname in files:
                    if fname.endswith(('.pyc', '.pyo')):
                        continue
                    full = os.path.join(root, fname)
                    zf.write(full, os.path.relpath(full, src_lib))
        
        # 5. 创建site-packages目录（安装第三方包的落点）
        os.makedirs(os.path.join(venv_dir, 'Lib', 'site-packages'), exist_ok=True)
        
        # 6. 写入 pythonXXX._pth 路径控制文件（嵌入式布局核心：用.pth控制模块搜索路径，
        #    并启用 import site 使 pip 可用）
        pth_content = f"python{ver_tag}.zip\n.\nDLLs\nLib\\site-packages\nimport site\n"
        with open(os.path.join(venv_dir, f'python{ver_tag}._pth'), 'w') as f:
            f.write(pth_content)
        
        # 7. 安装pip（我们打包的标准库zip中含ensurepip模块，可直接使用）
        self.root.after(0, lambda: self.append_debug_info("正在安装pip..."))
        dst_python = os.path.join(venv_dir, 'python.exe')
        pip_result = subprocess.run([dst_python, '-m', 'ensurepip', '--upgrade'],
                                    capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=300,
                                    cwd=venv_dir, **self._get_subprocess_kwargs())
        if pip_result.returncode != 0:
            self.root.after(0, lambda: self.append_debug_info(f"pip安装失败（可稍后手动安装）: {pip_result.stderr.strip()}"))
    
    def _get_system_python(self):
        """获取系统中真正的Python解释器路径（打包环境下使用）"""
        # 缓存结果
        if hasattr(self, '_system_python_cache'):
            return self._system_python_cache
        
        real_python = None
        
        # 方法1: 从注册表查找（最可靠，Windows）
        if sys.platform == "win32":
            try:
                import winreg
                # 先查64位
                try:
                    key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r'SOFTWARE\Python\PythonCore', 0, winreg.KEY_READ | winreg.KEY_WOW64_64KEY)
                    i = 0
                    best_version = (0, 0, 0)
                    best_path = None
                    while True:
                        try:
                            subkey_name = winreg.EnumKey(key, i)
                            subkey = winreg.OpenKey(key, subkey_name)
                            try:
                                install_path = winreg.QueryValueEx(subkey, 'InstallPath')[0]
                                python_exe = os.path.join(install_path, 'python.exe')
                                if os.path.exists(python_exe):
                                    ver_parts = subkey_name.split('.')
                                    if len(ver_parts) >= 2:
                                        try:
                                            major = int(ver_parts[0])
                                            minor = int(ver_parts[1])
                                            if (major, minor, 0) > best_version:
                                                best_version = (major, minor, 0)
                                                best_path = python_exe
                                        except:
                                            pass
                            except:
                                pass
                            winreg.CloseKey(subkey)
                            i += 1
                        except WindowsError:
                            break
                    winreg.CloseKey(key)
                    if best_path:
                        real_python = best_path
                except:
                    pass
                
                # 如果64位没找到，查32位
                if not real_python:
                    try:
                        key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r'SOFTWARE\Python\PythonCore', 0, winreg.KEY_READ | winreg.KEY_WOW64_32KEY)
                        i = 0
                        best_version = (0, 0, 0)
                        best_path = None
                        while True:
                            try:
                                subkey_name = winreg.EnumKey(key, i)
                                subkey = winreg.OpenKey(key, subkey_name)
                                try:
                                    install_path = winreg.QueryValueEx(subkey, 'InstallPath')[0]
                                    python_exe = os.path.join(install_path, 'python.exe')
                                    if os.path.exists(python_exe):
                                        ver_parts = subkey_name.split('.')
                                        if len(ver_parts) >= 2:
                                            try:
                                                major = int(ver_parts[0])
                                                minor = int(ver_parts[1])
                                                if (major, minor, 0) > best_version:
                                                    best_version = (major, minor, 0)
                                                    best_path = python_exe
                                            except:
                                                pass
                                except:
                                    pass
                                winreg.CloseKey(subkey)
                                i += 1
                            except WindowsError:
                                break
                        winreg.CloseKey(key)
                        if best_path:
                            real_python = best_path
                    except:
                        pass
                
                # 也检查当前用户注册表
                if not real_python:
                    try:
                        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r'SOFTWARE\Python\PythonCore')
                        i = 0
                        best_version = (0, 0, 0)
                        best_path = None
                        while True:
                            try:
                                subkey_name = winreg.EnumKey(key, i)
                                subkey = winreg.OpenKey(key, subkey_name)
                                try:
                                    install_path = winreg.QueryValueEx(subkey, 'InstallPath')[0]
                                    python_exe = os.path.join(install_path, 'python.exe')
                                    if os.path.exists(python_exe):
                                        ver_parts = subkey_name.split('.')
                                        if len(ver_parts) >= 2:
                                            try:
                                                major = int(ver_parts[0])
                                                minor = int(ver_parts[1])
                                                if (major, minor, 0) > best_version:
                                                    best_version = (major, minor, 0)
                                                    best_path = python_exe
                                            except:
                                                pass
                                except:
                                    pass
                                winreg.CloseKey(subkey)
                                i += 1
                            except WindowsError:
                                break
                        winreg.CloseKey(key)
                        if best_path:
                            real_python = best_path
                    except:
                        pass
            except:
                pass
        
        # 方法2: 检查常见安装路径，排除当前exe所在目录
        if not real_python:
            exe_dir = os.path.dirname(os.path.abspath(sys.executable))
            common_paths = [
                r'C:\Python312\python.exe',
                r'C:\Python311\python.exe',
                r'C:\Python310\python.exe',
                r'C:\Python39\python.exe',
                r'C:\Python38\python.exe',
                r'C:\Program Files\Python312\python.exe',
                r'C:\Program Files\Python311\python.exe',
                r'C:\Program Files\Python310\python.exe',
                r'C:\Program Files\Python39\python.exe',
                r'C:\Program Files\Python38\python.exe',
            ]
            for path in common_paths:
                if os.path.exists(path):
                    if os.path.dirname(os.path.abspath(path)) != exe_dir:
                        real_python = path
                        break
        
        # 方法3: 从PATH中查找，但要排除当前exe
        if not real_python:
            import shutil as shutil_module
            exe_dir = os.path.dirname(os.path.abspath(sys.executable))
            python_path = shutil_module.which('python') or shutil_module.which('python3')
            if python_path:
                # 确保不是当前exe所在目录
                if os.path.dirname(os.path.abspath(python_path)) != exe_dir:
                    real_python = python_path
        
        # 方法4: 检查当前exe是否本身就是python
        if not real_python:
            exe_name = os.path.basename(sys.executable).lower()
            if exe_name.startswith('python') and not exe_name.startswith('pythonw'):
                # 检查是否是真正的python（不是打包的）
                # 真正的python旁边应该有DLLs目录等
                if os.path.exists(os.path.join(os.path.dirname(sys.executable), 'DLLs')):
                    real_python = sys.executable
        
        self._system_python_cache = real_python
        return real_python

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
            threading.Thread(target=self._create_venv_thread, args=(venv_dir, True), daemon=True).start()

    def select_venv(self):
        """选择虚拟环境"""
        venv_path = filedialog.askdirectory(title="选择虚拟环境目录")
        if venv_path:
            # 检查是否为有效的虚拟环境
            if os.path.exists(os.path.join(venv_path, "pyvenv.cfg")):
                self.current_venv = venv_path
                self.embed_label.config(text="")  # 清空嵌入式环境标签
                self.venv_label.config(text=f"虚拟环境: {venv_path}")
                self.update_status(f"已选择虚拟环境: {venv_path}")
                # 自动列出该环境中的已安装包
                self.list_installed()
            else:
                messagebox.showwarning("警告", "选择的目录不是有效的虚拟环境")
                
    def select_embedded_venv(self):
        """选择嵌入式环境"""
        venv_path = filedialog.askdirectory(title="选择嵌入式环境目录")
        if venv_path:
            # 严格校验嵌入式环境（embeddable标准布局）特征：
            # 1. 根目录存在python.exe（虚拟环境的python.exe在Scripts/bin子目录下）
            # 2. 不存在pyvenv.cfg（存在则是虚拟环境，不允许从嵌入式入口选择）
            if sys.platform == "win32":
                python_exe = os.path.join(venv_path, "python.exe")
            else:
                python_exe = os.path.join(venv_path, "bin", "python")
            is_embed = os.path.exists(python_exe) and not os.path.exists(os.path.join(venv_path, "pyvenv.cfg"))
                
            if is_embed:
                self.current_venv = venv_path
                self.venv_label.config(text="")  # 清空虚拟环境标签
                self.embed_label.config(text=f"嵌入式环境: {venv_path}")
                self.update_status(f"已选择嵌入式环境: {venv_path}")
                # 自动列出该环境中的已安装包
                self.list_installed()
            else:
                messagebox.showwarning("警告", "选择的目录不是有效的嵌入式环境（虚拟环境请使用'选择虚拟环境'按钮）")

    def detect_environment(self):
        """自动检测当前环境"""
        # 更新系统环境信息
        system_info = f"{platform.system()} {platform.release()}"
        architecture = platform.machine()  # 获取更准确的架构信息
        python_version = f"Python {sys.version.split()[0]} ({platform.architecture()[0]})"
        self.system_label.config(text=f"{system_info} ({architecture}) - {python_version}")
        
        # 如果已经选择了环境（包括嵌入式环境），则不进行自动检测
        if self.current_venv:
            # 检查是否为嵌入式环境（通过标签文本判断）
            current_text = self.embed_label.cget("text")
            if "嵌入式环境:" in current_text:
                self.update_status("使用已选择的嵌入式环境")
                return
            else:
                # 检查虚拟环境标签
                venv_text = self.venv_label.cget("text")
                if "虚拟环境:" in venv_text:
                    self.update_status("使用已选择的虚拟环境")
                    return
        
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
            self.embed_label.config(text="嵌入式环境")
            self.update_status("检测到嵌入式Python环境")
            return

        # 未检测到特殊环境
        self.current_venv = None
        self.venv_label.config(text="未选择虚拟环境")
        self.embed_label.config(text="")
        self.update_status("使用系统Python环境")

    def change_mirror(self, event=None):
        """切换镜像源"""
        self.current_mirror = self.mirror_var.get()
        self.update_status(f"已切换到镜像源: {self.current_mirror}")

    def get_pip_command(self):
        """获取pip命令，考虑虚拟环境"""
        # 基础命令
        if self.current_venv:
            # 检查当前环境标签，判断是否为嵌入式环境
            current_text = self.embed_label.cget("text")
            if "嵌入式环境:" in current_text:
                # 对于嵌入式环境，直接使用根目录的python -m pip（embeddable标准布局）
                python_path = os.path.join(self.current_venv, "python.exe") if sys.platform == "win32" else os.path.join(self.current_venv, "bin", "python")
                if os.path.exists(python_path):
                    cmd = [python_path, "-m", "pip"]
                else:
                    # 如果找不到python可执行文件，回退到系统pip
                    cmd = self._get_system_pip_command()
            else:
                # 对于普通虚拟环境，使用虚拟环境的pip
                if sys.platform == "win32":
                    pip_path = os.path.join(self.current_venv, "Scripts", "pip.exe")
                    python_path = os.path.join(self.current_venv, "Scripts", "python.exe")
                else:
                    pip_path = os.path.join(self.current_venv, "bin", "pip")
                    python_path = os.path.join(self.current_venv, "bin", "python")
                # 检查pip是否存在
                if os.path.exists(pip_path):
                    cmd = [pip_path]
                else:
                    # 如果找不到pip，回退到python -m pip
                    if os.path.exists(python_path):
                        cmd = [python_path, "-m", "pip"]
                    else:
                        # 如果都找不到，回退到系统pip
                        cmd = self._get_system_pip_command()
        else:
            # 否则使用系统pip
            cmd = self._get_system_pip_command()
            
        return cmd
    
    def _get_system_pip_command(self):
        """获取系统pip命令（打包环境下安全版本）"""
        if getattr(sys, 'frozen', False):
            # 打包环境下，使用找到的系统Python
            system_python = self._get_system_python()
            if system_python:
                return [system_python, "-m", "pip"]
            else:
                # 找不到系统Python，返回None
                return None
        else:
            # 开发环境下，直接使用sys.executable
            return [sys.executable, "-m", "pip"]

    def load_preset(self, preset_type):
        """加载预设包集合"""
        # 使用预设包管理器加载预设
        preset = self.preset_manager.get_preset(preset_type)
        
        if preset:
            # 添加预设包到当前列表
            for package in preset['packages']:
                # 检查是否已存在
                exists = False
                for existing_pkg in self.packages:
                    if existing_pkg['name'] == package['name']:
                        exists = True
                        break
                        
                if not exists:
                    self.packages.append(package)
                    
            self.refresh_tree()
            self.update_status(f"已加载预设包集合: {preset['name']}")
        else:
            messagebox.showwarning("警告", f"未知的预设包集合: {preset_type}")

    def add_new_preset(self):
        """添加新的预设包集合"""
        # 创建新增预设对话框
        dialog = AddPresetDialog(self.root)
        if dialog.result:
            # 获取用户输入的预设名称和包列表
            preset_name = dialog.result['name']
            packages = dialog.result['packages']
            
            # 生成预设键名（使用小写并替换空格为下划线）
            preset_key = preset_name.lower().replace(' ', '_')
            
            # 使用PresetManager保存新预设
            if self.preset_manager.add_preset(preset_key, preset_name, packages):
                # 添加预设包到当前列表
                added_count = 0
                for package in packages:
                    # 检查是否已存在
                    exists = False
                    for existing_pkg in self.packages:
                        if existing_pkg['name'] == package['name']:
                            exists = True
                            break
                            
                    if not exists:
                        self.packages.append(package)
                        added_count += 1
                        
                self.refresh_tree()
                self.update_status(f"已从预设'{preset_name}'添加 {added_count} 个新包")
                
                # 显示成功消息
                messagebox.showinfo("成功", f"已从预设'{preset_name}'添加 {added_count} 个新包")
                
                # 更新预设按钮
                self.refresh_preset_buttons()
            else:
                messagebox.showerror("错误", "保存预设失败")

    def create_preset_buttons(self):
        """创建预设按钮"""
        # 清除现有的预设按钮
        for widget in self.preset_button_frame.winfo_children():
            widget.destroy()
        
        # 获取所有预设
        presets = self.preset_manager.get_all_presets()
        
        # 使用网格布局来实现自动换行，按钮向左对齐
        row = 0
        col = 0
        max_cols = 8  # 每行最多显示8个按钮
        
        # 为每个预设创建按钮
        for preset_key, preset_data in presets.items():
            # 创建按钮
            button = ttk.Button(
                self.preset_button_frame, 
                text=preset_data['name'], 
                command=lambda key=preset_key: self.load_preset(key)
            )
            button.grid(row=row, column=col, padx=2, pady=2, sticky="w")
            
            # 使用偏函数来解决闭包问题
            from functools import partial
            
            # 创建右键菜单
            context_menu = tk.Menu(button, tearoff=0)
            
            # 所有预设都支持复制功能
            context_menu.add_command(
                label="复制", 
                command=partial(self.copy_preset, preset_key, preset_data)
            )
            
            # 检查是否为默认预设
            if preset_key not in self.preset_manager.default_presets:
                # 对于自定义预设，额外提供编辑和删除功能
                context_menu.add_command(label="编辑", command=partial(self.edit_preset, preset_key, preset_data))
                context_menu.add_command(label="删除", command=partial(self.delete_preset, preset_key))
            
            # 绑定右键菜单
            button.bind("<Button-3>", lambda e, menu=context_menu: menu.post(e.x_root, e.y_root))
            
            col += 1
            if col >= max_cols:
                col = 0
                row += 1
        
        # 添加"新增预设"按钮
        ttk.Button(
            self.preset_button_frame, 
            text="新增预设", 
            command=self.add_new_preset
        ).grid(row=row, column=col, padx=2, pady=2, sticky="w")
        
        # 配置网格权重，使按钮能够正确左对齐
        # 只给最后一列设置权重，让所有按钮靠左对齐
        self.preset_button_frame.columnconfigure(max_cols-1, weight=1)

    def refresh_preset_buttons(self):
        """刷新预设按钮"""
        self.create_preset_buttons()

    def edit_preset(self, preset_key, preset_data):
        """编辑预设"""
        # 创建编辑预设对话框
        dialog = EditPresetDialog(self.root, preset_key, preset_data)
        if dialog.result:
            if dialog.result == "DELETE":
                # 删除预设
                if self.preset_manager.delete_preset(preset_key):
                    self.refresh_preset_buttons()
                    messagebox.showinfo("成功", f"预设'{preset_data['name']}'已删除")
                else:
                    messagebox.showerror("错误", "删除预设失败")
            else:
                # 更新预设
                preset_name = dialog.result['name']
                packages = dialog.result['packages']
                
                # 生成预设键名（使用小写并替换空格为下划线）
                preset_key_new = preset_name.lower().replace(' ', '_')
                
                # 如果名称改变且新名称已存在，则提示用户
                if preset_key_new != preset_key and preset_key_new in self.preset_manager.get_all_presets():
                    messagebox.showwarning("警告", f"预设名称'{preset_name}'已存在")
                    return
                
                # 使用PresetManager更新预设
                if self.preset_manager.update_preset(preset_key, preset_name, packages):
                    # 更新预设按钮
                    self.refresh_preset_buttons()
                    messagebox.showinfo("成功", f"预设'{preset_name}'已更新")
                else:
                    messagebox.showerror("错误", "更新预设失败")

    def copy_preset(self, preset_key, preset_data):
        """复制预设"""
        # 创建新的预设名称（在原名称后添加"副本"）
        new_name = preset_data['name'] + " 副本"
        
        # 创建编辑预设对话框，用于复制
        dialog = EditPresetDialog(self.root, preset_key, {"name": new_name, "packages": preset_data['packages']})
        if dialog.result and dialog.result != "DELETE":
            # 获取新预设的名称和包列表
            preset_name = dialog.result['name']
            packages = dialog.result['packages']
            
            # 生成预设键名（使用小写并替换空格为下划线）
            preset_key_new = preset_name.lower().replace(' ', '_')
            
            # 检查新名称是否已存在
            if preset_key_new in self.preset_manager.get_all_presets():
                messagebox.showwarning("警告", f"预设名称'{preset_name}'已存在")
                return
            
            # 使用PresetManager添加新预设
            if self.preset_manager.add_preset(preset_key_new, preset_name, packages):
                # 更新预设按钮
                self.refresh_preset_buttons()
                messagebox.showinfo("成功", f"预设'{preset_name}'已创建")
            else:
                messagebox.showerror("错误", "创建预设失败")

    def delete_preset(self, preset_key):
        """删除预设"""
        preset_data = self.preset_manager.get_preset(preset_key)
        if preset_data:
            if messagebox.askyesno("确认删除", f"确定要删除预设 '{preset_data['name']}' 吗？"):
                if self.preset_manager.delete_preset(preset_key):
                    self.refresh_preset_buttons()
                    messagebox.showinfo("成功", f"预设'{preset_data['name']}'已删除")
                else:
                    messagebox.showerror("错误", "删除预设失败")

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
            # 注意：pip list 不支持 -i 镜像源参数（无需联网下载），不能附加
            
            self.root.after(0, lambda: self.append_debug_info(f"执行列出已安装包命令: {' '.join(cmd)}"))
            self.root.after(0, lambda: self.append_debug_info("列出过程:"))
            
            # 使用Popen来实时获取输出
            process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding='utf-8', errors='replace', bufsize=1, **self._get_subprocess_kwargs())
            
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
                                        'operator': '',  # 设置为空字符串，不在显示区使用==
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
        dialog = SaveInstalledDialog(self.root)
        if not dialog.result:
            # 用户点击了取消按钮
            return
            
        include_version = dialog.result['include_version']
        
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
                
    def batch_operator(self):
        """批量操作符管理"""
        try:
            # 创建批量操作符对话框
            dialog = BatchOperatorDialog(self.root)
            result = dialog.result
            
            # 如果用户点击了确定
            if result:
                operator = result['operator']
                scope = result['scope']
                
                # 获取要应用操作符的包列表
                if scope == "selected":
                    # 仅选中项
                    selected_items = self.tree.selection()
                    if not selected_items:
                        messagebox.showwarning("警告", "请至少选择一个包")
                        return
                    items_to_update = selected_items
                else:
                    # 所有项
                    items_to_update = self.tree.get_children()
                    if not items_to_update:
                        messagebox.showwarning("警告", "没有包可供更新")
                        return
                
                # 更新包的操作符
                updated_count = 0
                for item in items_to_update:
                    # 获取当前包的信息
                    values = self.tree.item(item, 'values')
                    if len(values) >= 3:
                        name = values[0]
                        version = values[1]
                        # 更新操作符
                        self.tree.item(item, values=(name, version, operator))
                        updated_count += 1
                
                # 更新manager中的数据
                self._sync_manager_with_tree()
                
                messagebox.showinfo("成功", f"已更新{updated_count}个包的操作符为'{operator}'")
                
        except Exception as e:
            messagebox.showerror("错误", f"批量操作符设置失败: {str(e)}")
            
    def _sync_manager_with_tree(self):
        """同步树形视图和manager中的数据"""
        # 清空当前包列表
        self.packages.clear()
        
        # 从树形视图中获取所有项目并重新填充包列表
        for item in self.tree.get_children():
            values = self.tree.item(item, 'values')
            if len(values) >= 3:
                package = {
                    'name': values[0],
                    'version': values[1],
                    'operator': values[2],
                    'source': values[3] if len(values) > 3 else 'pypi'
                }
                self.packages.append(package)
    
    def search_package(self):
        """搜索包功能"""
        # 创建搜索对话框
        search_dialog = SearchPackageDialog(self.root)
        if search_dialog.result:
            package_name = search_dialog.result.strip()
            if package_name:
                # 检查包是否在当前列表中
                found_indices = []
                for i, package in enumerate(self.packages):
                    if package['name'].lower() == package_name.lower():
                        found_indices.append(i)
                
                if found_indices:
                    # 包存在，直接跳转到对应位置
                    self.tree.selection_set([str(idx) for idx in found_indices])
                    # 滚动到第一个匹配项
                    self.tree.see(str(found_indices[0]))
                    self.update_status(f"找到 {len(found_indices)} 个匹配的包: {package_name}")
                    
                    # 在状态栏显示更多信息
                    if len(found_indices) == 1:
                        item_values = self.tree.item(str(found_indices[0]), 'values')
                        self.update_status(f"找到包: {package_name} | 版本: {item_values[1]} | 来源: {item_values[3]}")
                else:
                    # 包不存在，提示用户
                    messagebox.showinfo("提示", f"在当前依赖列表中未找到包: {package_name}")
                    self.update_status(f"未找到包: {package_name}")
    
    def create_launcher(self):
        """创建启动器功能"""
        # 创建启动器对话框，传递主程序实例
        launcher_dialog = LauncherDialog(self.root, self)
        if launcher_dialog.result:
            try:
                # 获取结果
                result = launcher_dialog.result
                py_file = result['py_file']
                env_type = result['env_type']
                system_python_path = result['system_python_path']
                venv_path = result['venv_path']
                embed_path = result.get('embed_path', '')
                args = result['args']
                output_file = result['output_file']
                
                # 处理参数
                args_str = f" {args}" if args else ""
                
                # 获取相对路径
                try:
                    # 尝试获取相对于批处理文件的Python文件路径
                    output_dir = os.path.dirname(os.path.abspath(output_file))
                    py_file_relative = os.path.relpath(py_file, output_dir)
                except:
                    # 如果相对路径计算失败，使用原始路径
                    py_file_relative = py_file
                
                # 生成批处理文件内容
                if env_type == "venv" and venv_path:
                    # 使用虚拟环境
                    python_path = os.path.join(venv_path, "Scripts", "python.exe")
                    if not os.path.exists(python_path):
                        # 尝试Linux/Mac路径
                        python_path = os.path.join(venv_path, "bin", "python")
                    
                    # 获取虚拟环境的相对路径
                    try:
                        output_dir = os.path.dirname(os.path.abspath(output_file))
                        venv_relative = os.path.relpath(venv_path, output_dir)
                        python_relative = os.path.join(venv_relative, "Scripts", "python.exe")
                    except:
                        python_relative = python_path
                    
                    # 生成虚拟环境启动脚本（简化版）
                    bat_content = f'''@echo off
"{python_relative}" "{py_file_relative}"{args_str}
pause
'''
                elif env_type == "embed" and embed_path:
                    # 使用嵌入式环境（python.exe位于环境根目录）
                    python_path = os.path.join(embed_path, "python.exe")
                    if not os.path.exists(python_path):
                        # 尝试Linux/Mac路径
                        python_path = os.path.join(embed_path, "bin", "python")
                    
                    # 获取嵌入式环境的相对路径
                    try:
                        output_dir = os.path.dirname(os.path.abspath(output_file))
                        embed_relative = os.path.relpath(embed_path, output_dir)
                        python_relative = os.path.join(embed_relative, os.path.basename(python_path))
                    except:
                        python_relative = python_path
                    
                    # 生成嵌入式环境启动脚本（简化版）
                    bat_content = f'''@echo off
"{python_relative}" "{py_file_relative}"{args_str}
pause
'''
                else:
                    # 使用系统Python
                    python_cmd = system_python_path if system_python_path else "python"
                    
                    # 如果是系统Python，尝试简化路径
                    if python_cmd == "python" or python_cmd.endswith("python.exe"):
                        python_display = "python"
                    else:
                        # 尝试获取相对路径
                        try:
                            output_dir = os.path.dirname(os.path.abspath(output_file))
                            python_display = os.path.relpath(python_cmd, output_dir)
                        except:
                            python_display = python_cmd
                    
                    # 生成系统Python启动脚本（简化版）
                    bat_content = f'''@echo off
{python_display} "{py_file_relative}"{args_str}
pause
'''
                
                # 写入批处理文件
                with open(output_file, 'w', encoding='utf-8') as f:
                    f.write(bat_content)
                
                # 显示成功消息
                messagebox.showinfo("成功", f"启动器文件已创建:\n{output_file}")
                self.update_status(f"已创建启动器: {output_file}")
                
            except Exception as e:
                messagebox.showerror("错误", f"创建启动器失败: {str(e)}")
                self.update_status(f"创建启动器失败: {str(e)}")
    
    def open_cmd_window(self):
        """打开CMD命令窗口，如果已选择环境则使用该环境的Python，否则使用系统Python"""
        try:
            # 检查是否选择了虚拟环境或嵌入式环境
            if self.current_venv:
                # 获取当前环境的Scripts目录（Windows）或bin目录（Linux/Mac）
                if sys.platform == "win32":
                    scripts_dir = os.path.join(self.current_venv, "Scripts")
                else:
                    scripts_dir = os.path.join(self.current_venv, "bin")
                
                # 检查Scripts/bin目录是否存在
                if os.path.exists(scripts_dir):
                    # 在当前环境的Scripts/bin目录下打开新的CMD窗口
                    if sys.platform == "win32":
                        subprocess.Popen(["cmd", "/k", "title", "Requirements GUI CMD - Virtual Environment"], 
                                       cwd=scripts_dir, creationflags=subprocess.CREATE_NEW_CONSOLE)
                    else:
                        subprocess.Popen(["gnome-terminal", "--title", "Requirements GUI Terminal - Virtual Environment", "--working-directory", scripts_dir])
                    self.update_status(f"已在环境目录打开新的CMD窗口: {scripts_dir}")
                else:
                    # 如果Scripts/bin目录不存在，就在虚拟环境根目录打开
                    if sys.platform == "win32":
                        subprocess.Popen(["cmd", "/k", "title", "Requirements GUI CMD - Virtual Environment"], 
                                       cwd=self.current_venv, creationflags=subprocess.CREATE_NEW_CONSOLE)
                    else:
                        subprocess.Popen(["gnome-terminal", "--title", "Requirements GUI Terminal - Virtual Environment", "--working-directory", self.current_venv])
                    self.update_status(f"已在环境根目录打开新的CMD窗口: {self.current_venv}")
            else:
                # 没有选择环境，使用系统Python路径
                # 获取系统Python可执行文件所在目录
                python_dir = os.path.dirname(sys.executable)
                if sys.platform == "win32":
                    subprocess.Popen(["cmd", "/k", "title", "Requirements GUI CMD - System Python"], 
                                   cwd=python_dir, creationflags=subprocess.CREATE_NEW_CONSOLE)
                else:
                    subprocess.Popen(["gnome-terminal", "--title", "Requirements GUI Terminal - System Python", "--working-directory", python_dir])
                self.update_status(f"已在系统Python目录打开新的CMD窗口: {python_dir}")
        except Exception as e:
            messagebox.showerror("错误", f"无法打开CMD窗口: {str(e)}")
            self.update_status(f"打开CMD窗口失败: {str(e)}")
    
    def download_from_github(self):
        """从GitHub下载项目功能"""
        # 创建下载对话框，传入上次的下载目录作为默认值
        download_dialog = DownloadDialog(self.root, default_dir=self.last_download_dir)
        if download_dialog.result:
            try:
                # 获取结果
                result = download_dialog.result
                repo_url = result['repo_url']
                target_dir = result['target_dir']
                
                # 保存本次使用的目录，用于下次默认值
                self.last_download_dir = target_dir
                
                # 从GitHub URL中提取仓库名称
                repo_name = self._extract_repo_name(repo_url)
                if not repo_name:
                    messagebox.showerror("错误", "无法从URL中提取仓库名称，请检查URL格式是否正确")
                    self.update_status("URL格式错误，无法提取仓库名称")
                    return
                
                # 在目标目录下创建以仓库名称命名的子目录
                final_target_dir = os.path.join(target_dir, repo_name)
                
                # 检查目标目录是否已存在且不为空
                if os.path.exists(final_target_dir) and os.path.isdir(final_target_dir):
                    if any(os.scandir(final_target_dir)):
                        # 目录不为空，询问用户是否继续
                        if not messagebox.askyesno("确认", f"目标目录 '{final_target_dir}' 已存在且不为空，是否继续下载？\n注意：这可能会覆盖现有文件。"):
                            self.update_status("用户取消了下载操作")
                            return
                
                # 检查git是否可用
                try:
                    subprocess.run(["git", "--version"], check=True, capture_output=True, **self._get_subprocess_kwargs())
                except (subprocess.CalledProcessError, FileNotFoundError):
                    messagebox.showerror("错误", "未找到Git命令，请确保已安装Git并添加到系统PATH中")
                    self.update_status("Git未安装或未添加到PATH")
                    return
                
                # 确保目标目录的父目录存在
                parent_dir = os.path.dirname(final_target_dir)
                if parent_dir and not os.path.exists(parent_dir):
                    try:
                        os.makedirs(parent_dir, exist_ok=True)
                    except Exception as e:
                        messagebox.showerror("错误", f"无法创建目标目录的父目录: {str(e)}")
                        self.update_status(f"创建目录失败: {str(e)}")
                        return
                
                # 执行git clone命令，显示进度
                self.update_status(f"正在从GitHub下载项目: {repo_url}")
                
                # 创建进度窗口
                progress_window = tk.Toplevel(self.root)
                progress_window.title("下载进度")
                progress_window.geometry("400x150")
                progress_window.resizable(False, False)
                progress_window.transient(self.root)
                progress_window.grab_set()
                
                # 居中显示
                progress_window.geometry("+%d+%d" % (self.root.winfo_rootx()+50, self.root.winfo_rooty()+50))
                
                # 创建进度条和标签
                progress_frame = ttk.Frame(progress_window)
                progress_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
                
                progress_label = ttk.Label(progress_frame, text=f"正在下载: {repo_name}")
                progress_label.pack(pady=(0, 10))
                
                progress_bar = ttk.Progressbar(progress_frame, orient="horizontal", length=300, mode="indeterminate")
                progress_bar.pack(pady=(0, 10))
                progress_bar.start(10)  # 启动不确定模式的进度条动画
                
                status_label = ttk.Label(progress_frame, text="准备下载...")
                status_label.pack()
                
                # 更新窗口
                progress_window.update()
                
                # 在新线程中执行下载，避免阻塞UI
                import threading
                download_thread = threading.Thread(
                    target=self._perform_git_clone,
                    args=(repo_url, final_target_dir, parent_dir, progress_window, status_label),
                    daemon=True
                )
                download_thread.start()
                
                # 等待下载完成
                progress_window.wait_window()
                    
            except Exception as e:
                messagebox.showerror("错误", f"下载过程中发生错误: {str(e)}")
                self.update_status(f"项目下载错误: {str(e)}")
    
    def show_retry_dialog(self, error_msg, parent_window):
        """在主线程中显示重试对话框，并返回用户选择"""
        event = threading.Event()
        result = [False]
        
        def create_dialog():
            retry_dialog = tk.Toplevel(parent_window)
            retry_dialog.title("下载失败")
            retry_dialog.geometry("300x150")
            retry_dialog.resizable(False, False)
            retry_dialog.transient(parent_window)
            retry_dialog.grab_set()
            
            # 居中显示
            retry_dialog.geometry("+%d+%d" % (parent_window.winfo_rootx()+50, parent_window.winfo_rooty()+50))
            
            # 创建消息标签
            message_frame = ttk.Frame(retry_dialog)
            message_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
            
            ttk.Label(message_frame, text="下载失败:", foreground="red").pack(anchor=tk.W)
            ttk.Label(message_frame, text=error_msg[:100] + ("..." if len(error_msg) > 100 else "")).pack(anchor=tk.W, pady=(5, 10))
            
            # 创建按钮框架
            button_frame = ttk.Frame(message_frame)
            button_frame.pack(fill=tk.X, pady=(10, 0))
            
            def on_retry():
                result[0] = True
                retry_dialog.destroy()
                event.set()
            
            def on_cancel():
                result[0] = False
                retry_dialog.destroy()
                event.set()
            
            ttk.Button(button_frame, text="重试", command=on_retry).pack(side=tk.LEFT, padx=5)
            ttk.Button(button_frame, text="取消", command=on_cancel).pack(side=tk.LEFT, padx=5)
        
        # 在主线程中创建对话框
        self.root.after(0, create_dialog)
        
        # 等待用户操作完成
        event.wait()
        
        return result[0]

    def _perform_git_clone(self, repo_url, target_dir, parent_dir, progress_window, status_label):
        """执行实际的git clone操作"""
        
        while True:  # 重试循环
            try:
                # 更新状态
                self.root.after(0, lambda: status_label.config(text="正在连接到GitHub..."))
                
                # 执行git clone命令
                process = subprocess.Popen(
                    ["git", "clone", repo_url, target_dir],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    cwd=parent_dir if parent_dir else None,
                    bufsize=1,
                    universal_newlines=True,
                    **self._get_subprocess_kwargs()
                )
                
                # 实时读取输出
                while True:
                    output = process.stdout.readline()
                    if output == '' and process.poll() is not None:
                        break
                    if output:
                        # 更新状态信息
                        self.root.after(0, lambda: status_label.config(text=output.strip()[:50]))  # 限制文本长度
                        
                # 等待进程结束
                return_code = process.poll()
                
                # 显示结果
                if return_code == 0:
                    self.root.after(0, progress_window.destroy)
                    self.root.after(0, lambda: messagebox.showinfo("成功", f"项目已成功下载到:\n{target_dir}"))
                    self.root.after(0, lambda: self.update_status(f"项目下载完成: {target_dir}"))
                    break  # 成功下载，退出重试循环
                else:
                    # 读取错误信息
                    stderr_output = process.stderr.read()
                    error_msg = stderr_output.strip() if stderr_output else "未知错误"
                    # 提供更友好的错误信息
                    if "already exists and is not an empty directory" in error_msg:
                        user_choice = self.show_retry_dialog(f"目标目录 '{target_dir}' 已存在且不为空。\n请选择一个空目录或不存在的目录进行下载。", progress_window)
                    else:
                        user_choice = self.show_retry_dialog(error_msg, progress_window)
                    
                    if not user_choice:  # 用户选择取消
                        self.root.after(0, progress_window.destroy)
                        self.root.after(0, lambda: self.update_status("用户取消了下载操作"))
                        break
                    # 如果用户选择重试，循环会继续
                        
            except Exception as e:
                user_choice = self.show_retry_dialog(str(e), progress_window)
                
                if not user_choice:  # 用户选择取消
                    self.root.after(0, progress_window.destroy)
                    self.root.after(0, lambda: self.update_status(f"项目下载错误: {str(e)}"))
                    break
                # 如果用户选择重试，循环会继续
    
    def _extract_repo_name(self, repo_url):
        """从GitHub仓库URL中提取仓库名称"""
        try:
            # 移除URL末尾可能存在的.git后缀
            if repo_url.endswith('.git'):
                repo_url = repo_url[:-4]
            
            # 提取仓库名称
            # 处理类似 https://github.com/username/repo_name 的URL
            if 'github.com' in repo_url:
                # 分割URL并获取最后部分
                parts = repo_url.strip('/').split('/')
                if len(parts) >= 2:
                    return parts[-1]
            
            return None
        except Exception:
            return None
    
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
                    self.refresh_packages()  # 对比已安装包并标记
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
    
    def clear_highlight(self):
        """清除所有高亮显示"""
        for item in self.tree.get_children():
            self.tree.item(item, tags=())
        self.tree.tag_configure("highlight", background="")
    
    def switch_github_version(self):
        """切换GitHub项目版本功能"""
        try:
            # 弹出目录选择对话框，让用户选择GitHub项目目录
            project_path = filedialog.askdirectory(
                title="选择GitHub项目目录",
                initialdir=os.getcwd()  # 默认使用当前工作目录
            )
            
            # 检查用户是否选择了目录
            if not project_path or not os.path.exists(project_path):
                self.update_status("未选择有效的项目目录")
                return
            
            # 检查所选目录是否为Git仓库
            git_dir = os.path.join(project_path, ".git")
            if not os.path.exists(git_dir):
                messagebox.showerror("错误", "所选目录不是一个Git仓库")
                self.update_status("选择的目录不是Git仓库")
                return
            
            # 创建版本切换对话框
            dialog = SwitchVersionDialog(self.root, project_path)
            
            # 检查是否有结果返回
            if dialog.result:
                version_type = dialog.result['type']
                version_name = dialog.result['name']
                self.update_status(f"已切换到{version_type}: {version_name}")
            else:
                self.update_status("取消了版本切换操作")
                
        except Exception as e:
            messagebox.showerror("错误", f"切换版本时发生错误: {str(e)}")
            self.update_status(f"版本切换失败: {str(e)}")
    
    def update_project(self):
        """更新项目功能 - 让用户选择项目目录并执行git pull命令更新项目"""
        try:
            # 让用户选择项目目录
            project_path = filedialog.askdirectory(
                title="选择要更新的Git项目目录",
                initialdir=self.last_download_dir or os.getcwd()
            )
            
            # 如果用户取消了选择，直接返回
            if not project_path:
                self.update_status("用户取消了项目选择")
                return
            
            # 保存最后选择的目录
            self.last_download_dir = os.path.dirname(project_path)
            
            # 检查项目目录是否为Git仓库
            git_dir = os.path.join(project_path, ".git")
            if not os.path.exists(git_dir):
                messagebox.showerror("错误", "所选目录不是一个Git仓库")
                self.update_status("所选目录不是Git仓库")
                return
            
            # 确认用户是否要更新项目
            if not messagebox.askyesno("确认更新", f"确定要更新项目吗？\n项目路径: {project_path}\n\n这将从远程仓库拉取最新的更改。"):
                self.update_status("用户取消了更新操作")
                return
            
            # 执行git pull命令
            self.update_status("正在更新项目...")
            
            # 创建进度窗口
            progress_window = tk.Toplevel(self.root)
            progress_window.title("更新进度")
            progress_window.geometry("400x150")
            progress_window.resizable(False, False)
            progress_window.transient(self.root)
            progress_window.grab_set()
            
            # 居中显示
            progress_window.geometry("+%d+%d" % (self.root.winfo_rootx()+50, self.root.winfo_rooty()+50))
            
            # 创建进度条和标签
            progress_frame = ttk.Frame(progress_window)
            progress_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
            
            progress_label = ttk.Label(progress_frame, text="正在更新项目...")
            progress_label.pack(pady=(0, 10))
            
            progress_bar = ttk.Progressbar(progress_frame, orient="horizontal", length=300, mode="indeterminate")
            progress_bar.pack(pady=(0, 10))
            progress_bar.start(10)  # 启动不确定模式的进度条动画
            
            status_label = ttk.Label(progress_frame, text="准备更新...")
            status_label.pack()
            
            # 更新窗口
            progress_window.update()
            
            # 在新线程中执行更新，避免阻塞UI
            import threading
            update_thread = threading.Thread(
                target=self._perform_git_pull,
                args=(project_path, progress_window, status_label),
                daemon=True
            )
            update_thread.start()
            
            # 等待更新完成
            progress_window.wait_window()
            
        except Exception as e:
            messagebox.showerror("错误", f"更新项目时发生错误: {str(e)}")
            self.update_status(f"项目更新错误: {str(e)}")
    
    def _perform_git_pull(self, project_path, progress_window, status_label):
        """执行实际的git pull操作，包含重试机制"""
        max_retries = 3  # 最大重试次数
        retry_count = 0
        
        while retry_count <= max_retries:
            try:
                # 更新状态
                if retry_count == 0:
                    self.root.after(0, lambda: status_label.config(text="正在连接到远程仓库..."))
                else:
                    self.root.after(0, lambda: status_label.config(text=f"重试中... (第{retry_count}次)"))
                
                # 执行git pull命令
                process = subprocess.Popen(
                    ["git", "pull"],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    cwd=project_path,
                    bufsize=1,
                    universal_newlines=True,
                    **self._get_subprocess_kwargs()
                )
                
                # 实时读取输出
                output_lines = []
                while True:
                    output = process.stdout.readline()
                    if output == '' and process.poll() is not None:
                        break
                    if output:
                        output_lines.append(output.strip())
                        # 更新状态信息（限制文本长度）
                        self.root.after(0, lambda: status_label.config(text=output.strip()[:50]))
                
                # 等待进程结束
                return_code = process.poll()
                
                # 获取完整的输出
                stdout_output = "\n".join(output_lines)
                stderr_output = process.stderr.read()
                
                # 显示结果
                if return_code == 0:
                    self.root.after(0, progress_window.destroy)
                    self.root.after(0, lambda: messagebox.showinfo("成功", "项目已成功更新"))
                    self.root.after(0, lambda: self.update_status("项目更新完成"))
                    return  # 成功更新，退出循环
                else:
                    error_msg = stderr_output.strip() if stderr_output else "未知错误"
                    retry_count += 1
                    
                    # 如果达到最大重试次数，显示错误
                    if retry_count > max_retries:
                        self.root.after(0, progress_window.destroy)
                        self.root.after(0, lambda: messagebox.showerror("错误", f"项目更新失败，已重试{max_retries}次:\n{error_msg}"))
                        self.root.after(0, lambda: self.update_status(f"项目更新失败: {error_msg}"))
                        return
                    else:
                        # 等待一段时间后重试
                        import time
                        time.sleep(2)
                        
            except Exception as e:
                retry_count += 1
                
                # 如果达到最大重试次数，显示错误
                if retry_count > max_retries:
                    self.root.after(0, progress_window.destroy)
                    self.root.after(0, lambda: messagebox.showerror("错误", f"更新过程中发生异常，已重试{max_retries}次:\n{str(e)}"))
                    self.root.after(0, lambda: self.update_status(f"项目更新异常: {str(e)}"))
                    return
                else:
                    # 等待一段时间后重试
                    import time
                    time.sleep(2)


class PackageDialog:
    def __init__(self, parent, title, name="", version="", operator="", source="pypi"):
        self.result = None
        self.parent = parent
        
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
        self.name_entry = ttk.Entry(frame, textvariable=self.name_var, width=30)
        self.name_entry.grid(row=0, column=1, sticky=tk.EW, pady=5)
        
        # 版本操作符
        ttk.Label(frame, text="操作符:").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.operator_var = tk.StringVar(value=operator)
        operator_combo = ttk.Combobox(frame, textvariable=self.operator_var, width=27)
        operator_combo['values'] = ('==', '>=', '<=', '>', '<', '!=', '~=', '')
        operator_combo.grid(row=1, column=1, sticky=tk.EW, pady=5)
        
        # 版本号
        ttk.Label(frame, text="版本号:").grid(row=2, column=0, sticky=tk.W, pady=5)
        self.version_var = tk.StringVar(value=version)
        self.version_entry = ttk.Entry(frame, textvariable=self.version_var, width=30)
        self.version_entry.grid(row=2, column=1, sticky=tk.EW, pady=5)
        
        # 来源
        ttk.Label(frame, text="来源:").grid(row=3, column=0, sticky=tk.W, pady=5)
        self.source_var = tk.StringVar(value=source)
        source_combo = ttk.Combobox(frame, textvariable=self.source_var, width=27)
        source_combo['values'] = ('pypi', 'git', '本地')
        source_combo.grid(row=3, column=1, sticky=tk.EW, pady=5)
        
        # 按钮
        button_frame = ttk.Frame(frame)
        button_frame.grid(row=4, column=0, columnspan=2, pady=20)
        
        ttk.Button(button_frame, text="对比版本", command=self.compare_version).pack(side=tk.LEFT, padx=10)
        ttk.Button(button_frame, text="确定", command=self.ok).pack(side=tk.LEFT, padx=10)
        ttk.Button(button_frame, text="取消", command=self.cancel).pack(side=tk.LEFT, padx=10)
        
        # 配置列权重
        frame.columnconfigure(1, weight=1)
        
        # 绑定回车键
        self.top.bind("<Return>", lambda e: self.ok())
        self.top.bind("<Escape>", lambda e: self.cancel())
        
        # 等待窗口关闭
        parent.wait_window(self.top)
    
    def get_latest_version(self, package_name):
        """获取包的最新版本"""
        try:
            import urllib.request
            import json
            
            # 使用PyPI的JSON API获取包信息
            url = f"https://pypi.org/pypi/{package_name}/json"
            request = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            
            with urllib.request.urlopen(request, timeout=10) as response:
                data = json.loads(response.read().decode('utf-8'))
                
            # 获取最新版本号
            latest_version = data.get('info', {}).get('version', '')
            return latest_version
        except Exception as e:
            return None
    
    def compare_version(self):
        """对比版本功能"""
        package_name = self.name_var.get().strip()
        
        if not package_name:
            messagebox.showwarning("警告", "请输入包名")
            self.name_entry.focus()
            return
        
        # 显示加载提示
        self.top.config(cursor="watch")
        self.top.update()
        
        import threading
        threading.Thread(target=self._compare_version_thread, args=(package_name,), daemon=True).start()
    
    def _compare_version_thread(self, package_name):
        """在后台线程中对比版本"""
        latest_version = self.get_latest_version(package_name)
        
        self.top.after(0, lambda: self._show_version_comparison(latest_version))
    
    def _show_version_comparison(self, latest_version):
        """显示版本对比结果"""
        self.top.config(cursor="")
        
        if not latest_version:
            messagebox.showerror("错误", "无法获取最新版本信息，请检查包名或网络连接")
            return
        
        current_version = self.version_var.get().strip()
        
        # 构建对比消息
        if current_version:
            message = f"当前版本: {current_version}\n最新版本: {latest_version}\n\n"
            
            # 比较版本
            try:
                from packaging import version
                
                if version.parse(latest_version) > version.parse(current_version):
                    message += "提示: 有新版本可用！建议更新。"
                elif version.parse(latest_version) == version.parse(current_version):
                    message += "提示: 当前版本已是最新。"
                else:
                    message += "提示: 当前版本比最新版本更高。"
            except Exception:
                if latest_version != current_version:
                    message += "提示: 版本不同，请手动确认是否需要更新。"
                else:
                    message += "提示: 版本相同。"
        else:
            message = f"最新版本: {latest_version}\n\n提示: 请设置版本号。"
        
        # 显示对比窗口
        comparison_window = tk.Toplevel(self.top)
        comparison_window.title("版本对比")
        comparison_window.geometry("300x200")
        comparison_window.transient(self.top)
        comparison_window.grab_set()
        
        # 居中显示
        comparison_window.geometry("+%d+%d" % (self.top.winfo_rootx()+50, self.top.winfo_rooty()+50))
        
        # 创建显示区域
        frame = ttk.Frame(comparison_window)
        frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        
        ttk.Label(frame, text="版本对比结果", font=('Arial', 10, 'bold')).pack(pady=(0, 10))
        
        text_widget = tk.Text(frame, height=8, width=40, wrap=tk.WORD)
        text_widget.pack(fill=tk.BOTH, expand=True)
        text_widget.insert('1.0', message)
        text_widget.config(state='disabled')
        
        ttk.Button(frame, text="使用最新版本", command=lambda: self._use_latest_version(latest_version, comparison_window)).pack(pady=(10, 0))
        
        ttk.Button(frame, text="关闭", command=comparison_window.destroy).pack(pady=(5, 0))
    
    def _use_latest_version(self, latest_version, window):
        """使用最新版本"""
        self.version_var.set(latest_version)
        window.destroy()
        self.top.focus()
    
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
        
        ttk.Button(button_frame, text="搜索", command=self.ok).pack(side=tk.LEFT, padx=10)
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


class LauncherDialog:
    def __init__(self, parent, main_app=None):
        self.result = None
        self.main_app = main_app  # 保存主程序实例引用
        
        self.top = tk.Toplevel(parent)
        self.top.title("创建启动器")
        self.top.geometry("500x330")  # 增加窗口高度
        self.top.minsize(500, 330)    # 设置最小尺寸
        self.top.transient(parent)
        self.top.grab_set()
        
        # 居中显示
        self.top.geometry("+%d+%d" % (parent.winfo_rootx()+50, parent.winfo_rooty()+50))
        
        # 创建输入字段
        frame = ttk.Frame(self.top)
        frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        
        # Python文件路径
        ttk.Label(frame, text="Python文件:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.file_var = tk.StringVar()
        file_frame = ttk.Frame(frame)
        file_frame.grid(row=0, column=1, sticky=tk.EW, pady=5)
        
        self.file_entry = ttk.Entry(file_frame, textvariable=self.file_var, width=40)
        self.file_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        ttk.Button(file_frame, text="浏览", command=self.browse_file).pack(side=tk.LEFT, padx=(5, 0))
        
        # 环境选择
        ttk.Label(frame, text="Python环境:").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.env_var = tk.StringVar(value="system")
        env_frame = ttk.Frame(frame)
        env_frame.grid(row=1, column=1, sticky=tk.EW, pady=5)
        
        ttk.Radiobutton(env_frame, text="系统Python", variable=self.env_var, value="system").pack(side=tk.LEFT)
        ttk.Radiobutton(env_frame, text="虚拟环境", variable=self.env_var, value="venv").pack(side=tk.LEFT, padx=(10, 0))
        ttk.Radiobutton(env_frame, text="嵌入式环境", variable=self.env_var, value="embed").pack(side=tk.LEFT, padx=(10, 0))
        
        # 系统Python路径（默认隐藏）
        self.system_frame = ttk.Frame(frame)
        self.system_frame.grid(row=2, column=1, sticky=tk.EW, pady=5)
        self.system_frame.grid_remove()  # 默认隐藏
        
        ttk.Label(self.system_frame, text="系统Python路径:").pack(anchor=tk.W)
        self.system_python_var = tk.StringVar()
        system_entry_frame = ttk.Frame(self.system_frame)
        system_entry_frame.pack(fill=tk.X)
        
        self.system_python_entry = ttk.Entry(system_entry_frame, textvariable=self.system_python_var, width=40)
        self.system_python_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        ttk.Button(system_entry_frame, text="浏览", command=self.browse_system_python).pack(side=tk.LEFT, padx=(5, 0))
        
        # 虚拟环境路径（默认隐藏）
        self.venv_frame = ttk.Frame(frame)
        self.venv_frame.grid(row=3, column=1, sticky=tk.EW, pady=5)
        self.venv_frame.grid_remove()  # 默认隐藏
        
        self.venv_var = tk.StringVar()
        venv_entry_frame = ttk.Frame(self.venv_frame)
        venv_entry_frame.pack(fill=tk.X)
        
        self.venv_entry = ttk.Entry(venv_entry_frame, textvariable=self.venv_var, width=40)
        self.venv_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        ttk.Button(venv_entry_frame, text="浏览", command=self.browse_venv).pack(side=tk.LEFT, padx=(5, 0))
        
        # 嵌入式环境路径（默认隐藏）
        self.embed_frame = ttk.Frame(frame)
        self.embed_frame.grid(row=4, column=1, sticky=tk.EW, pady=5)
        self.embed_frame.grid_remove()  # 默认隐藏
        
        self.embed_var = tk.StringVar()
        embed_entry_frame = ttk.Frame(self.embed_frame)
        embed_entry_frame.pack(fill=tk.X)
        
        self.embed_entry = ttk.Entry(embed_entry_frame, textvariable=self.embed_var, width=40)
        self.embed_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        ttk.Button(embed_entry_frame, text="浏览", command=self.browse_embed).pack(side=tk.LEFT, padx=(5, 0))
        
        # 如果主程序中有已选择的虚拟环境，则自动填充
        if self.main_app and self.main_app.current_venv:
            # 根据主程序当前选择的类型（嵌入式/虚拟环境）自动填充对应选项
            embed_selected = False
            if hasattr(self.main_app, 'embed_label') and "嵌入式环境:" in self.main_app.embed_label.cget("text"):
                embed_selected = True
            if embed_selected:
                self.embed_var.set(self.main_app.current_venv)
                self.env_var.set("embed")
                self.embed_frame.grid()
                self.system_frame.grid_remove()
                self.venv_frame.grid_remove()
            else:
                self.venv_var.set(self.main_app.current_venv)
                self.env_var.set("venv")
                self.venv_frame.grid()
                self.system_frame.grid_remove()
                self.embed_frame.grid_remove()
        else:
            # 自动填充系统Python路径
            self.system_python_var.set(self.get_system_python_path())
        
        # 参数设置
        ttk.Label(frame, text="参数设置:").grid(row=5, column=0, sticky=tk.W, pady=5)
        self.args_var = tk.StringVar()
        args_frame = ttk.Frame(frame)
        args_frame.grid(row=5, column=1, sticky=tk.EW, pady=5)
        
        self.args_entry = ttk.Entry(args_frame, textvariable=self.args_var, width=40)
        self.args_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        # 绑定环境选择变化事件
        self.env_var.trace('w', self.on_env_change)
        
        # 保存位置
        ttk.Label(frame, text="保存位置:").grid(row=6, column=0, sticky=tk.W, pady=5)
        self.output_var = tk.StringVar()
        output_frame = ttk.Frame(frame)
        output_frame.grid(row=6, column=1, sticky=tk.EW, pady=5)
        
        self.output_entry = ttk.Entry(output_frame, textvariable=self.output_var, width=40)
        self.output_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        ttk.Button(output_frame, text="浏览", command=self.browse_output).pack(side=tk.LEFT, padx=(5, 0))
        
        # 按钮
        button_frame = ttk.Frame(frame)
        button_frame.grid(row=7, column=0, columnspan=2, pady=20)
        
        ttk.Button(button_frame, text="创建", command=self.ok).pack(side=tk.LEFT, padx=10)
        ttk.Button(button_frame, text="取消", command=self.cancel).pack(side=tk.LEFT, padx=10)
        
        # 配置列权重
        frame.columnconfigure(1, weight=1)
        file_frame.columnconfigure(0, weight=1)
        env_frame.columnconfigure(0, weight=1)
        system_entry_frame.columnconfigure(0, weight=1)
        venv_entry_frame.columnconfigure(0, weight=1)
        embed_entry_frame.columnconfigure(0, weight=1)
        args_frame.columnconfigure(0, weight=1)
        output_frame.columnconfigure(0, weight=1)
        
        # 绑定回车键
        self.top.bind("<Return>", lambda e: self.ok())
        self.top.bind("<Escape>", lambda e: self.cancel())
        
        # 等待窗口关闭
        parent.wait_window(self.top)
        
    def on_env_change(self, *args):
        """环境选择变化时的处理"""
        env = self.env_var.get()
        if env == "venv":
            self.venv_frame.grid()
            self.embed_frame.grid_remove()
            self.system_frame.grid_remove()
        elif env == "embed":
            self.embed_frame.grid()
            self.venv_frame.grid_remove()
            self.system_frame.grid_remove()
        else:
            self.venv_frame.grid_remove()
            self.embed_frame.grid_remove()
            self.system_frame.grid()
            
            # 自动获取系统Python路径
            if not self.system_python_var.get():
                self.system_python_var.set(self.get_system_python_path())
            
    def browse_file(self):
        """浏览Python文件"""
        file_path = filedialog.askopenfilename(
            title="选择Python文件",
            filetypes=[("Python文件", "*.py"), ("所有文件", "*.*")]
        )
        if file_path:
            self.file_var.set(file_path)
            # 自动设置输出文件名
            if not self.output_var.get():
                output_path = os.path.splitext(file_path)[0] + ".bat"
                self.output_var.set(output_path)
                
    def browse_system_python(self):
        """浏览系统Python可执行文件"""
        python_path = filedialog.askopenfilename(
            title="选择Python可执行文件",
            filetypes=[("Python可执行文件", "python.exe"), ("所有文件", "*.*")]
        )
        if python_path:
            self.system_python_var.set(python_path)
            
    def browse_venv(self):
        """浏览虚拟环境目录"""
        venv_path = filedialog.askdirectory(title="选择虚拟环境目录")
        if venv_path:
            self.venv_var.set(venv_path)

    def browse_embed(self):
        """浏览嵌入式环境目录"""
        embed_path = filedialog.askdirectory(title="选择嵌入式环境目录")
        if embed_path:
            self.embed_var.set(embed_path)
            
    def browse_output(self):
        """浏览输出文件"""
        output_path = filedialog.asksaveasfilename(
            title="保存启动器文件",
            defaultextension=".bat",
            filetypes=[("批处理文件", "*.bat"), ("所有文件", "*.*")]
        )
        if output_path:
            self.output_var.set(output_path)
            
    def _get_subprocess_kwargs(self):
        """获取 subprocess 调用的参数，在 Windows 上隐藏命令窗口"""
        kwargs = {}
        if sys.platform == 'win32':
            # 使用 CREATE_NO_WINDOW 隐藏命令窗口
            kwargs['creationflags'] = subprocess.CREATE_NO_WINDOW
            # 使用 STARTUPINFO 进一步确保窗口隐藏
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = subprocess.SW_HIDE
            kwargs['startupinfo'] = startupinfo
        return kwargs
            
    def get_system_python_path(self):
        """获取系统Python路径"""
        try:
            # 尝试获取系统Python路径
            result = subprocess.run([sys.executable, "-c", "import sys; print(sys.executable)"], 
                                  capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=5, **self._get_subprocess_kwargs())
            if result.returncode == 0:
                return result.stdout.strip()
        except:
            pass
            
        # 如果无法获取，返回默认路径
        return "python"
        
    def ok(self):
        """确定按钮回调"""
        py_file = self.file_var.get().strip()
        if not py_file:
            messagebox.showwarning("警告", "请选择Python文件")
            return
            
        if not os.path.exists(py_file):
            messagebox.showwarning("警告", "选择的Python文件不存在")
            return
            
        output_file = self.output_var.get().strip()
        if not output_file:
            messagebox.showwarning("警告", "请指定保存位置")
            return
            
        env_type = self.env_var.get()
        system_python_path = self.system_python_var.get().strip() if env_type == "system" else ""
        venv_path = self.venv_var.get().strip() if env_type == "venv" else ""
        embed_path = self.embed_var.get().strip() if env_type == "embed" else ""
        args = self.args_var.get().strip()
        
        if env_type == "system" and not system_python_path:
            messagebox.showwarning("警告", "请指定系统Python路径")
            return
            
        if env_type == "venv" and not venv_path:
            messagebox.showwarning("警告", "请选择虚拟环境目录")
            return
            
        if env_type == "venv" and not os.path.exists(venv_path):
            messagebox.showwarning("警告", "选择的虚拟环境目录不存在")
            return

        if env_type == "embed" and not embed_path:
            messagebox.showwarning("警告", "请选择嵌入式环境目录")
            return

        if env_type == "embed":
            if not os.path.exists(embed_path):
                messagebox.showwarning("警告", "选择的嵌入式环境目录不存在")
                return
            # 校验是否为有效的嵌入式环境（根目录存在python可执行文件）
            if sys.platform == "win32":
                embed_python = os.path.join(embed_path, "python.exe")
            else:
                embed_python = os.path.join(embed_path, "bin", "python")
            if not os.path.exists(embed_python):
                messagebox.showwarning("警告", "选择的目录不是有效的嵌入式环境（根目录未找到python可执行文件）")
                return
            
        self.result = {
            'py_file': py_file,
            'env_type': env_type,
            'system_python_path': system_python_path,
            'venv_path': venv_path,
            'embed_path': embed_path,
            'args': args,
            'output_file': output_file
        }
        self.top.destroy()
        
    def cancel(self):
        """取消按钮回调"""
        self.top.destroy()


class AddPresetDialog:
    """新增预设对话框"""
    def __init__(self, parent):
        self.result = None
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("新增预设")
        self.dialog.geometry("400x300")
        self.dialog.resizable(True, True)
        self.dialog.transient(parent)
        self.dialog.grab_set()
        
        # 居中显示
        self.dialog.geometry("+%d+%d" % (parent.winfo_rootx()+50, parent.winfo_rooty()+50))
        
        # 预设名称
        name_frame = ttk.Frame(self.dialog)
        name_frame.pack(fill=tk.X, padx=10, pady=5)
        ttk.Label(name_frame, text="预设名称:").pack(side=tk.LEFT)
        self.name_var = tk.StringVar()
        self.name_entry = ttk.Entry(name_frame, textvariable=self.name_var, width=30)
        self.name_entry.pack(side=tk.LEFT, padx=5)
        
        # 包列表
        list_frame = ttk.LabelFrame(self.dialog, text="包列表 (每行一个包)")
        list_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        # 创建文本框和滚动条
        text_frame = ttk.Frame(list_frame)
        text_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        self.package_text = tk.Text(text_frame, height=10, width=40)
        scrollbar = ttk.Scrollbar(text_frame, orient=tk.VERTICAL, command=self.package_text.yview)
        self.package_text.configure(yscrollcommand=scrollbar.set)
        
        self.package_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # 按钮区域
        button_frame = ttk.Frame(self.dialog)
        button_frame.pack(fill=tk.X, padx=10, pady=10)
        
        self.ok_button = ttk.Button(button_frame, text="确定", command=self.ok)
        self.ok_button.pack(side=tk.RIGHT, padx=5)
        ttk.Button(button_frame, text="取消", command=self.cancel).pack(side=tk.RIGHT, padx=5)
        
        # 绑定ESC键到取消操作
        self.dialog.bind("<Escape>", lambda event: self.cancel())
        
        # 在名称输入框中绑定回车键到确定操作
        self.name_entry.bind("<Return>", lambda event: self.ok())
        
        # 在包列表文本框中绑定Ctrl+Enter到确定操作
        self.package_text.bind("<Control-Return>", lambda event: self.ok())
        
        # 在包列表文本框中绑定Tab键到换行操作
        self.package_text.bind("<Tab>", self.insert_tab)
        
        # 设置焦点
        self.name_entry.focus()
        
        # 等待窗口关闭
        parent.wait_window(self.dialog)
        
    def ok(self):
        """确定按钮回调"""
        name = self.name_var.get().strip()
        packages_text = self.package_text.get(1.0, tk.END).strip()
        
        if not name:
            messagebox.showwarning("警告", "请输入预设名称")
            return
            
        if not packages_text:
            messagebox.showwarning("警告", "请输入至少一个包")
            return
            
        # 解析包列表
        packages = []
        lines = packages_text.split('\n')
        for line in lines:
            line = line.strip()
            if line and not line.startswith('#'):
                # 简单解析包名
                package_name = line.split('==')[0].split('>=')[0].split('<=')[0].split('>')[0].split('<')[0].split('!=')[0]
                if package_name:
                    packages.append({
                        'name': package_name,
                        'version': '',
                        'operator': '',
                        'source': 'pypi'
                    })
        
        if not packages:
            messagebox.showwarning("警告", "未找到有效的包")
            return
            
        self.result = {
            'name': name,
            'packages': packages
        }
        self.dialog.destroy()
        
    def insert_tab(self, event):
        """在文本框中插入Tab字符"""
        # 插入换行符
        self.package_text.insert(tk.INSERT, "\n")
        # 阻止默认的Tab行为（切换焦点）
        return "break"
        
    def cancel(self):
        """取消按钮回调"""
        self.dialog.destroy()


class EditPresetDialog:
    """编辑预设对话框"""
    def __init__(self, parent, preset_key, preset_data):
        self.result = None
        self.preset_key = preset_key
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("编辑预设")
        self.dialog.geometry("400x300")
        self.dialog.resizable(True, True)
        self.dialog.transient(parent)
        self.dialog.grab_set()
        
        # 居中显示
        self.dialog.geometry("+%d+%d" % (parent.winfo_rootx()+50, parent.winfo_rooty()+50))
        
        # 预设名称
        name_frame = ttk.Frame(self.dialog)
        name_frame.pack(fill=tk.X, padx=10, pady=5)
        ttk.Label(name_frame, text="预设名称:").pack(side=tk.LEFT)
        self.name_var = tk.StringVar(value=preset_data['name'])
        self.name_entry = ttk.Entry(name_frame, textvariable=self.name_var, width=30)
        self.name_entry.pack(side=tk.LEFT, padx=5)
        
        # 包列表
        list_frame = ttk.LabelFrame(self.dialog, text="包列表 (每行一个包)")
        list_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        # 创建文本框和滚动条
        text_frame = ttk.Frame(list_frame)
        text_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        self.package_text = tk.Text(text_frame, height=10, width=40)
        scrollbar = ttk.Scrollbar(text_frame, orient=tk.VERTICAL, command=self.package_text.yview)
        self.package_text.configure(yscrollcommand=scrollbar.set)
        
        # 填充现有包列表
        packages_text = "\n".join([pkg['name'] for pkg in preset_data['packages']])
        self.package_text.insert("1.0", packages_text)
        
        self.package_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # 按钮区域
        button_frame = ttk.Frame(self.dialog)
        button_frame.pack(fill=tk.X, padx=10, pady=10)
        
        self.ok_button = ttk.Button(button_frame, text="确定", command=self.ok)
        self.ok_button.pack(side=tk.RIGHT, padx=5)
        ttk.Button(button_frame, text="取消", command=self.cancel).pack(side=tk.RIGHT, padx=5)
        self.delete_button = ttk.Button(button_frame, text="删除", command=self.delete)
        self.delete_button.pack(side=tk.LEFT, padx=5)
        
        # 绑定ESC键到取消操作
        self.dialog.bind("<Escape>", lambda event: self.cancel())
        
        # 在名称输入框中绑定回车键到确定操作
        self.name_entry.bind("<Return>", lambda event: self.ok())
        
        # 在包列表文本框中绑定Ctrl+Enter到确定操作
        self.package_text.bind("<Control-Return>", lambda event: self.ok())
        
        # 在包列表文本框中绑定Tab键到换行操作
        self.package_text.bind("<Tab>", self.insert_tab)
        
        # 设置焦点
        self.name_entry.focus()
        
        # 等待窗口关闭
        parent.wait_window(self.dialog)
        
    def ok(self):
        """确定按钮回调"""
        name = self.name_var.get().strip()
        packages_text = self.package_text.get(1.0, tk.END).strip()
        
        if not name:
            messagebox.showwarning("警告", "请输入预设名称")
            return
            
        if not packages_text:
            messagebox.showwarning("警告", "请输入至少一个包")
            return
            
        # 解析包列表
        packages = []
        lines = packages_text.split('\n')
        for line in lines:
            line = line.strip()
            if line and not line.startswith('#'):
                # 简单解析包名
                package_name = line.split('==')[0].split('>=')[0].split('<=')[0].split('>')[0].split('<')[0].split('!=')[0]
                if package_name:
                    packages.append({
                        'name': package_name,
                        'version': '',
                        'operator': '',
                        'source': 'pypi'
                    })
        
        if not packages:
            messagebox.showwarning("警告", "未找到有效的包")
            return
            
        self.result = {
            'name': name,
            'packages': packages
        }
        self.dialog.destroy()
        
    def delete(self):
        """删除按钮回调"""
        if messagebox.askyesno("确认删除", f"确定要删除预设 '{self.name_var.get()}' 吗？"):
            self.result = "DELETE"
            self.dialog.destroy()
        
    def insert_tab(self, event):
        """在文本框中插入Tab字符"""
        # 插入换行符
        self.package_text.insert(tk.INSERT, "\n")
        # 阻止默认的Tab行为（切换焦点）
        return "break"
        
    def cancel(self):
        """取消按钮回调"""
        self.dialog.destroy()


class SaveInstalledDialog:
    def __init__(self, parent):
        self.result = None
        
        self.top = tk.Toplevel(parent)
        self.top.title("保存已安装的包")
        self.top.geometry("350x200")  # 增大窗口尺寸
        self.top.resizable(False, False)  # 禁止调整窗口大小
        self.top.transient(parent)
        self.top.grab_set()
        
        # 居中显示
        self.top.geometry("+%d+%d" % (parent.winfo_rootx()+50, parent.winfo_rooty()+50))
        
        # 创建输入字段
        frame = ttk.Frame(self.top)
        frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        
        # 保存选项
        ttk.Label(frame, text="请选择保存选项:").grid(row=0, column=0, columnspan=2, sticky=tk.W, pady=(0, 10))
        
        self.include_version_var = tk.BooleanVar(value=True)
        ttk.Radiobutton(frame, text="包含版本信息", variable=self.include_version_var, value=True).grid(row=1, column=0, columnspan=2, sticky=tk.W, pady=5)
        ttk.Radiobutton(frame, text="不包含版本信息", variable=self.include_version_var, value=False).grid(row=2, column=0, columnspan=2, sticky=tk.W, pady=5)
        
        # 按钮
        button_frame = ttk.Frame(frame)
        button_frame.grid(row=3, column=0, columnspan=2, pady=20)
        
        ttk.Button(button_frame, text="确定", command=self.ok, width=10).pack(side=tk.LEFT, padx=10)
        ttk.Button(button_frame, text="取消", command=self.cancel, width=10).pack(side=tk.LEFT, padx=10)
        
        # 绑定回车键和ESC键
        self.top.bind("<Return>", lambda e: self.ok())
        self.top.bind("<Escape>", lambda e: self.cancel())
        
        # 设置焦点到窗口
        self.top.focus()
        
        # 确保窗口完全绘制后调整位置
        self.top.update_idletasks()
        
        # 等待窗口关闭
        parent.wait_window(self.top)
        
    def ok(self):
        """确定按钮回调"""
        self.result = {
            'include_version': self.include_version_var.get()
        }
        self.top.destroy()
        
    def cancel(self):
        """取消按钮回调"""
        self.top.destroy()


class BatchOperatorDialog:
    def __init__(self, parent):
        self.result = None
        
        self.top = tk.Toplevel(parent)
        self.top.title("批量操作符管理")
        self.top.geometry("350x200")  # 进一步增加窗口大小以确保所有控件都能完整显示
        self.top.resizable(False, False)  # 禁止调整窗口大小
        self.top.transient(parent)
        self.top.grab_set()
        
        # 居中显示
        self.top.geometry("+%d+%d" % (parent.winfo_rootx()+50, parent.winfo_rooty()+50))
        
        # 创建输入字段
        frame = ttk.Frame(self.top)
        frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=15)
        
        # 版本操作符
        ttk.Label(frame, text="选择操作符:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.operator_var = tk.StringVar(value="==")
        operator_combo = ttk.Combobox(frame, textvariable=self.operator_var, width=27)
        operator_combo['values'] = ('==', '>=', '<=', '>', '<', '!=', '~=', '')
        operator_combo.grid(row=0, column=1, sticky=tk.EW, pady=5)
        operator_combo.state(['readonly'])  # 设置为只读模式
        
        # 应用范围
        ttk.Label(frame, text="应用范围:").grid(row=1, column=0, sticky=tk.W, pady=10)
        self.scope_var = tk.StringVar(value="selected")
        scope_frame = ttk.Frame(frame)
        scope_frame.grid(row=1, column=1, sticky=tk.EW, pady=10)
        ttk.Radiobutton(scope_frame, text="仅选中项", variable=self.scope_var, value="selected").pack(anchor=tk.W)
        ttk.Radiobutton(scope_frame, text="所有项", variable=self.scope_var, value="all").pack(anchor=tk.W)
        
        # 按钮
        button_frame = ttk.Frame(frame)
        button_frame.grid(row=2, column=0, columnspan=2, pady=15)
        
        ttk.Button(button_frame, text="确定", command=self.ok, width=10).pack(side=tk.LEFT, padx=10)
        ttk.Button(button_frame, text="取消", command=self.cancel, width=10).pack(side=tk.LEFT, padx=10)
        
        # 配置列权重
        frame.columnconfigure(1, weight=1)
        
        # 绑定回车键和ESC键
        self.top.bind("<Return>", lambda e: self.ok())
        self.top.bind("<Escape>", lambda e: self.cancel())
        
        # 设置焦点到操作符下拉框
        operator_combo.focus()
        
        # 确保窗口完全绘制后调整位置
        self.top.update_idletasks()
        
        # 等待窗口关闭
        parent.wait_window(self.top)
        
    def ok(self):
        """确定按钮回调"""
        self.result = {
            'operator': self.operator_var.get(),
            'scope': self.scope_var.get()
        }
        self.top.destroy()
        
    def cancel(self):
        """取消按钮回调"""
        self.top.destroy()


class DownloadDialog:
    def __init__(self, parent, default_dir=None):
        self.result = None
        self.download_process = None
        self.is_downloading = False
        
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("从GitHub下载项目")
        self.dialog.geometry("500x200")
        self.dialog.minsize(500, 200)
        self.dialog.transient(parent)
        self.dialog.grab_set()
        
        # 居中显示
        self.dialog.geometry("+%d+%d" % (parent.winfo_rootx()+50, parent.winfo_rooty()+50))
        
        # 创建输入字段
        frame = ttk.Frame(self.dialog)
        frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        
        # GitHub仓库URL
        ttk.Label(frame, text="仓库URL:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.url_var = tk.StringVar()
        url_frame = ttk.Frame(frame)
        url_frame.grid(row=0, column=1, sticky=tk.EW, pady=5)
        
        self.url_entry = ttk.Entry(url_frame, textvariable=self.url_var, width=40)
        self.url_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.url_entry.focus()
        
        # 示例提示
        ttk.Label(frame, text="例如: https://github.com/username/repository.git", foreground="gray").grid(row=1, column=1, sticky=tk.W, pady=(0, 5))
        
        # 目标目录
        ttk.Label(frame, text="保存位置:").grid(row=2, column=0, sticky=tk.W, pady=5)
        self.dir_var = tk.StringVar()
        dir_frame = ttk.Frame(frame)
        dir_frame.grid(row=2, column=1, sticky=tk.EW, pady=5)
        
        self.dir_entry = ttk.Entry(dir_frame, textvariable=self.dir_var, width=40)
        self.dir_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        # 如果提供了默认目录，则设置
        if default_dir:
            self.dir_var.set(default_dir)
        
        ttk.Button(dir_frame, text="浏览", command=self.browse_directory).pack(side=tk.LEFT, padx=(5, 0))
        
        # 按钮
        button_frame = ttk.Frame(frame)
        button_frame.grid(row=3, column=0, columnspan=2, pady=20)
        
        self.download_btn = ttk.Button(button_frame, text="下载", command=self.ok)
        self.download_btn.pack(side=tk.LEFT, padx=10)
        ttk.Button(button_frame, text="取消", command=self.cancel).pack(side=tk.LEFT, padx=10)
        
        # 配置列权重
        frame.columnconfigure(1, weight=1)
        url_frame.columnconfigure(0, weight=1)
        dir_frame.columnconfigure(0, weight=1)
        
        # 绑定回车键
        self.dialog.bind("<Return>", lambda e: self.ok())
        self.dialog.bind("<Escape>", lambda e: self.cancel())
        
        # 等待窗口关闭
        parent.wait_window(self.dialog)
        
    def browse_directory(self):
        """浏览目录"""
        directory = filedialog.askdirectory(title="选择保存目录")
        if directory:
            self.dir_var.set(directory)
            
    def ok(self):
        """确定按钮回调"""
        repo_url = self.url_var.get().strip()
        target_dir = self.dir_var.get().strip()
        
        if not repo_url:
            messagebox.showwarning("警告", "请输入GitHub仓库URL")
            return
            
        if not target_dir:
            messagebox.showwarning("警告", "请选择保存位置")
            return
            
        # 简单验证URL格式
        if not repo_url.startswith("https://github.com/"):
            if not messagebox.askyesno("确认", "URL似乎不是标准的GitHub仓库地址，是否继续？"):
                return
                
        # 设置结果并关闭对话框
        self.result = {
            'repo_url': repo_url,
            'target_dir': target_dir
        }
        self.dialog.destroy()
        
    def cancel(self):
        """取消按钮回调"""
        self.dialog.destroy()


class SwitchVersionDialog:
    """切换GitHub项目版本对话框"""
    
    def _get_subprocess_kwargs(self):
        """获取 subprocess 调用的参数，在 Windows 上隐藏命令窗口"""
        kwargs = {}
        if sys.platform == 'win32':
            # 使用 CREATE_NO_WINDOW 隐藏命令窗口
            kwargs['creationflags'] = subprocess.CREATE_NO_WINDOW
            # 使用 STARTUPINFO 进一步确保窗口隐藏
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = subprocess.SW_HIDE
            kwargs['startupinfo'] = startupinfo
        return kwargs
    
    def __init__(self, parent, project_path):
        self.result = None
        self.project_path = project_path
        self.branches = []
        self.tags = []
        
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("切换GitHub项目版本")
        self.dialog.geometry("500x450")  # 增加对话框高度
        self.dialog.minsize(500, 450)   # 调整最小高度
        self.dialog.transient(parent)
        self.dialog.grab_set()
        
        # 居中显示
        self.dialog.geometry("+%d+%d" % (parent.winfo_rootx()+50, parent.winfo_rooty()+50))
        
        # 创建主框架
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        
        # 项目路径显示
        ttk.Label(main_frame, text="项目路径:").grid(row=0, column=0, sticky=tk.W, pady=(0, 10))
        ttk.Label(main_frame, text=project_path, foreground="blue").grid(row=0, column=1, sticky=tk.W, pady=(0, 10))
        
        # 分支选择区域
        branch_frame = ttk.LabelFrame(main_frame, text="分支")
        branch_frame.grid(row=1, column=0, columnspan=2, sticky=tk.EW, pady=(0, 10))
        branch_frame.columnconfigure(0, weight=1)
        
        # 分支列表
        self.branch_listbox = tk.Listbox(branch_frame, height=6)
        branch_scrollbar = ttk.Scrollbar(branch_frame, orient=tk.VERTICAL, command=self.branch_listbox.yview)
        self.branch_listbox.configure(yscrollcommand=branch_scrollbar.set)
        
        self.branch_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(5, 0), pady=5)
        branch_scrollbar.pack(side=tk.RIGHT, fill=tk.Y, padx=(0, 5), pady=5)
        
        # 标签选择区域
        tag_frame = ttk.LabelFrame(main_frame, text="标签 (Tags)")
        tag_frame.grid(row=2, column=0, columnspan=2, sticky=tk.EW, pady=(0, 10))
        tag_frame.columnconfigure(0, weight=1)
        
        # 标签列表
        self.tag_listbox = tk.Listbox(tag_frame, height=6)
        tag_scrollbar = ttk.Scrollbar(tag_frame, orient=tk.VERTICAL, command=self.tag_listbox.yview)
        self.tag_listbox.configure(yscrollcommand=tag_scrollbar.set)
        
        self.tag_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(5, 0), pady=5)
        tag_scrollbar.pack(side=tk.RIGHT, fill=tk.Y, padx=(0, 5), pady=5)
        
        # 状态标签
        self.status_label = ttk.Label(main_frame, text="正在获取版本信息...", foreground="orange")
        self.status_label.grid(row=3, column=0, columnspan=2, pady=(0, 10))  # 调整状态标签位置
        
        # 按钮区域
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=4, column=0, columnspan=2, pady=(10, 0))  # 调整按钮区域位置
        
        self.switch_btn = ttk.Button(button_frame, text="切换", command=self.ok, state=tk.DISABLED)
        self.switch_btn.pack(side=tk.LEFT, padx=10)
        ttk.Button(button_frame, text="取消", command=self.cancel).pack(side=tk.LEFT, padx=10)
        
        # 配置列权重
        main_frame.columnconfigure(1, weight=1)
        
        # 绑定列表框选择事件
        self.branch_listbox.bind('<<ListboxSelect>>', self.on_branch_select)
        self.tag_listbox.bind('<<ListboxSelect>>', self.on_tag_select)
        
        # 绑定ESC键
        self.dialog.bind("<Escape>", lambda e: self.cancel())
        
        # 在新线程中获取分支和标签信息
        import threading
        fetch_thread = threading.Thread(target=self.fetch_versions, daemon=True)
        fetch_thread.start()
        
        # 等待窗口关闭
        parent.wait_window(self.dialog)
        
    def fetch_versions(self):
        """获取项目的分支和标签信息"""
        try:
            # 切换到项目目录
            original_cwd = os.getcwd()
            os.chdir(self.project_path)
            
            # 获取所有分支
            result = subprocess.run(["git", "branch", "-a"], capture_output=True, text=True, encoding='utf-8', errors='replace', check=True, **self._get_subprocess_kwargs())
            branches_output = result.stdout.strip()
            
            # 解析分支信息
            self.branches = []
            for line in branches_output.split('\n'):
                line = line.strip()
                if line.startswith('*'):
                    # 当前分支
                    branch_name = line[2:].strip()
                    self.branches.append((branch_name, True))
                elif '->' not in line:  # 过滤掉指向其他引用的符号链接
                    # 远程分支需要去掉remotes/origin/前缀
                    if line.startswith('remotes/origin/'):
                        branch_name = line.replace('remotes/origin/', '')
                        # 过滤掉HEAD引用
                        if branch_name != 'HEAD':
                            self.branches.append((branch_name, False))
                    else:
                        self.branches.append((line, False))
            
            # 获取所有标签
            result = subprocess.run(["git", "tag"], capture_output=True, text=True, encoding='utf-8', errors='replace', check=True, **self._get_subprocess_kwargs())
            tags_output = result.stdout.strip()
            self.tags = [tag.strip() for tag in tags_output.split('\n') if tag.strip()]
            
            # 更新UI
            self.dialog.after(0, self.update_ui)
            
        except subprocess.CalledProcessError as e:
            self.dialog.after(0, lambda: self.show_error(f"Git命令执行失败: {e.stderr}"))
        except Exception as e:
            self.dialog.after(0, lambda: self.show_error(f"获取版本信息时出错: {str(e)}"))
        finally:
            # 恢复原始工作目录
            os.chdir(original_cwd)
    
    def update_ui(self):
        """更新UI显示分支和标签"""
        try:
            # 清空列表
            self.branch_listbox.delete(0, tk.END)
            self.tag_listbox.delete(0, tk.END)
            
            # 添加分支到列表
            for branch_name, is_current in self.branches:
                display_text = f"{branch_name} (当前)" if is_current else branch_name
                self.branch_listbox.insert(tk.END, display_text)
                
            # 添加标签到列表
            for tag in self.tags:
                self.tag_listbox.insert(tk.END, tag)
            
            # 更新状态
            self.status_label.config(text="请选择要切换到的分支或标签", foreground="black")
            
        except Exception as e:
            self.show_error(f"更新界面时出错: {str(e)}")
    
    def on_branch_select(self, event):
        """分支选择事件"""
        selection = self.branch_listbox.curselection()
        if selection:
            # 取消标签选择
            self.tag_listbox.selection_clear(0, tk.END)
            # 启用切换按钮
            self.switch_btn.config(state=tk.NORMAL)
    
    def on_tag_select(self, event):
        """标签选择事件"""
        selection = self.tag_listbox.curselection()
        if selection:
            # 取消分支选择
            self.branch_listbox.selection_clear(0, tk.END)
            # 启用切换按钮
            self.switch_btn.config(state=tk.NORMAL)
    
    def show_error(self, message):
        """显示错误信息"""
        self.status_label.config(text=message, foreground="red")
        self.switch_btn.config(state=tk.DISABLED)
        
    def ok(self):
        """确定按钮回调"""
        try:
            # 获取选择的分支或标签
            branch_selection = self.branch_listbox.curselection()
            tag_selection = self.tag_listbox.curselection()
            
            if branch_selection:
                # 获取选择的分支
                selected_index = branch_selection[0]
                selected_item = self.branches[selected_index]
                branch_name = selected_item[0]
                
                # 切换分支
                self.switch_to_branch(branch_name)
            elif tag_selection:
                # 获取选择的标签
                selected_index = tag_selection[0]
                tag_name = self.tags[selected_index]
                
                # 切换到标签
                self.switch_to_tag(tag_name)
            else:
                messagebox.showwarning("警告", "请先选择一个分支或标签")
                return
                
        except Exception as e:
            messagebox.showerror("错误", f"切换版本时出错: {str(e)}")
    
    def switch_to_branch(self, branch_name):
        """切换到指定分支"""
        try:
            # 切换到项目目录
            original_cwd = os.getcwd()
            os.chdir(self.project_path)
            
            # 执行git checkout命令
            result = subprocess.run(["git", "checkout", branch_name], capture_output=True, text=True, encoding='utf-8', errors='replace', **self._get_subprocess_kwargs())
            
            # 恢复原始工作目录
            os.chdir(original_cwd)
            
            if result.returncode == 0:
                self.result = {'type': 'branch', 'name': branch_name}
                messagebox.showinfo("成功", f"已成功切换到分支: {branch_name}")
                self.dialog.destroy()
            else:
                error_msg = result.stderr.strip() if result.stderr else "未知错误"
                messagebox.showerror("错误", f"切换分支失败: {error_msg}")
                
        except Exception as e:
            # 恢复原始工作目录
            os.chdir(original_cwd)
            messagebox.showerror("错误", f"切换分支时出错: {str(e)}")
    
    def switch_to_tag(self, tag_name):
        """切换到指定标签"""
        try:
            # 切换到项目目录
            original_cwd = os.getcwd()
            os.chdir(self.project_path)
            
            # 执行git checkout命令
            result = subprocess.run(["git", "checkout", tag_name], capture_output=True, text=True, encoding='utf-8', errors='replace', **self._get_subprocess_kwargs())
            
            # 恢复原始工作目录
            os.chdir(original_cwd)
            
            if result.returncode == 0:
                self.result = {'type': 'tag', 'name': tag_name}
                messagebox.showinfo("成功", f"已成功切换到标签: {tag_name}")
                self.dialog.destroy()
            else:
                error_msg = result.stderr.strip() if result.stderr else "未知错误"
                messagebox.showerror("错误", f"切换标签失败: {error_msg}")
                
        except Exception as e:
            # 恢复原始工作目录
            os.chdir(original_cwd)
            messagebox.showerror("错误", f"切换标签时出错: {str(e)}")
    
    def cancel(self):
        """取消按钮回调"""
        self.dialog.destroy()


class PresetManager:
    """预设包管理类，用于读取和写入JSON格式的预设包文件"""
    
    def __init__(self, presets_file="presets.json"):
        self.presets_file = presets_file
        self.default_presets = {
            "ai_essentials": {
                "name": "AI基础必备",
                "packages": [
                    {"name": "numpy", "version": "", "operator": "", "source": "pypi"},
                    {"name": "pandas", "version": "", "operator": "", "source": "pypi"},
                    {"name": "torch", "version": "", "operator": "", "source": "pypi"},
                    {"name": "torchvision", "version": "", "operator": "", "source": "pypi"},
                    {"name": "transformers", "version": "", "operator": "", "source": "pypi"},
                    {"name": "diffusers", "version": "", "operator": "", "source": "pypi"},
                    {"name": "accelerate", "version": "", "operator": "", "source": "pypi"},
                    {"name": "pillow", "version": "", "operator": "", "source": "pypi"},
                    {"name": "opencv-python", "version": "", "operator": "", "source": "pypi"},
                    {"name": "scikit-learn", "version": "", "operator": "", "source": "pypi"},
                    {"name": "matplotlib", "version": "", "operator": "", "source": "pypi"},
                    {"name": "requests", "version": "", "operator": "", "source": "pypi"}
                ]
            },
            "ai_art": {
                "name": "AI绘画",
                "packages": [
                    {"name": "torch", "version": "", "operator": "", "source": "pypi"},
                    {"name": "torchvision", "version": "", "operator": "", "source": "pypi"},
                    {"name": "diffusers", "version": "", "operator": "", "source": "pypi"},
                    {"name": "transformers", "version": "", "operator": "", "source": "pypi"},
                    {"name": "accelerate", "version": "", "operator": "", "source": "pypi"}
                ]
            },
            "ai_image": {
                "name": "AI图像",
                "packages": [
                    {"name": "opencv-python", "version": "", "operator": "", "source": "pypi"},
                    {"name": "Pillow", "version": "", "operator": "", "source": "pypi"},
                    {"name": "scikit-image", "version": "", "operator": "", "source": "pypi"},
                    {"name": "albumentations", "version": "", "operator": "", "source": "pypi"}
                ]
            },
            "ai_audio": {
                "name": "AI音频",
                "packages": [
                    {"name": "librosa", "version": "", "operator": "", "source": "pypi"},
                    {"name": "soundfile", "version": "", "operator": "", "source": "pypi"},
                    {"name": "pydub", "version": "", "operator": "", "source": "pypi"},
                    {"name": "speechbrain", "version": "", "operator": "", "source": "pypi"}
                ]
            },
            "ai_video": {
                "name": "AI视频",
                "packages": [
                    {"name": "moviepy", "version": "", "operator": "", "source": "pypi"},
                    {"name": "opencv-python", "version": "", "operator": "", "source": "pypi"},
                    {"name": "av", "version": "", "operator": "", "source": "pypi"}
                ]
            },
            "data_science": {
                "name": "数据科学",
                "packages": [
                    {"name": "numpy", "version": "", "operator": "", "source": "pypi"},
                    {"name": "pandas", "version": "", "operator": "", "source": "pypi"},
                    {"name": "matplotlib", "version": "", "operator": "", "source": "pypi"},
                    {"name": "seaborn", "version": "", "operator": "", "source": "pypi"},
                    {"name": "scikit-learn", "version": "", "operator": "", "source": "pypi"}
                ]
            },
            "web_dev": {
                "name": "Web开发",
                "packages": [
                    {"name": "flask", "version": "", "operator": "", "source": "pypi"},
                    {"name": "django", "version": "", "operator": "", "source": "pypi"},
                    {"name": "fastapi", "version": "", "operator": "", "source": "pypi"},
                    {"name": "requests", "version": "", "operator": "", "source": "pypi"},
                    {"name": "gunicorn", "version": "", "operator": "", "source": "pypi"}
                ]
            }
        }
        self.presets = self.load_presets()
    
    def load_presets(self):
        """从JSON文件加载预设包集合"""
        try:
            if os.path.exists(self.presets_file):
                with open(self.presets_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    # 合并默认预设和自定义预设
                    presets = self.default_presets.copy()
                    if 'presets' in data:
                        presets.update(data['presets'])
                    return presets
            else:
                # 如果文件不存在，创建默认文件
                self.save_presets(self.default_presets)
                return self.default_presets
        except Exception as e:
            print(f"加载预设文件时出错: {e}")
            return self.default_presets
    
    def save_presets(self, presets):
        """将预设包集合保存到JSON文件"""
        try:
            data = {'presets': presets}
            with open(self.presets_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=4)
            return True
        except Exception as e:
            print(f"保存预设文件时出错: {e}")
            return False
    
    def add_preset(self, preset_key, preset_name, packages):
        """添加新的预设包集合"""
        self.presets[preset_key] = {
            'name': preset_name,
            'packages': packages
        }
        return self.save_presets(self.presets)
    
    def update_preset(self, preset_key, preset_name, packages):
        """更新预设包集合"""
        if preset_key in self.presets:
            self.presets[preset_key] = {
                'name': preset_name,
                'packages': packages
            }
            return self.save_presets(self.presets)
        return False
    
    def delete_preset(self, preset_key):
        """删除预设包集合"""
        if preset_key in self.presets:
            # 不允许删除默认预设
            if preset_key in self.default_presets:
                return False
            del self.presets[preset_key]
            return self.save_presets(self.presets)
        return False
    
    def get_preset(self, preset_key):
        """获取指定的预设包集合"""
        return self.presets.get(preset_key)
    
    def get_all_presets(self):
        """获取所有预设包集合"""
        return self.presets
    
    def get_preset_names(self):
        """获取所有预设包集合的名称"""
        return {key: preset['name'] for key, preset in self.presets.items()}


def main():
    # 防止多进程问题，Windows下打包exe时必须添加
    import multiprocessing
    multiprocessing.freeze_support()
    
    # 如果支持拖放功能，则使用TkinterDnD创建根窗口
    if HAS_DND:
        root = tkinterdnd2.TkinterDnD.Tk()
    else:
        root = tk.Tk()
    
    app = RequirementsManager(root)
    root.mainloop()


if __name__ == "__main__":
    main()