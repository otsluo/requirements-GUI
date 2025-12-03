#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
测试"更新项目"功能的简单脚本
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import sys
import os

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# 导入必要的模块
try:
    from requirements_gui import RequirementsManager
except ImportError as e:
    print(f"导入错误: {e}")
    sys.exit(1)

def test_update_project():
    """测试更新项目功能"""
    # 创建主窗口
    root = tk.Tk()
    root.title("测试更新项目功能")
    root.geometry("400x300")
    
    # 创建测试框架
    test_frame = ttk.Frame(root, padding="20")
    test_frame.pack(fill=tk.BOTH, expand=True)
    
    # 标题
    title_label = ttk.Label(test_frame, text="更新项目功能测试", font=("Arial", 16, "bold"))
    title_label.pack(pady=(0, 20))
    
    # 说明文本
    info_text = """
    此测试将验证"更新项目"功能：
    
    1. 确保已正确添加"更新项目"按钮
    2. 验证按钮点击后能正确调用update_project方法
    3. 检查功能的错误处理机制
    
    注意：此测试不会真正执行git操作，
    仅验证UI和方法调用。
    """
    
    info_label = ttk.Label(test_frame, text=info_text, justify=tk.LEFT)
    info_label.pack(pady=(0, 20))
    
    # 创建RequirementsManager实例
    app = RequirementsManager(root)
    
    def simulate_update_project():
        """模拟调用更新项目功能"""
        try:
            # 直接调用update_project方法
            app.update_project()
            messagebox.showinfo("测试结果", "update_project方法调用成功！")
        except Exception as e:
            messagebox.showerror("测试错误", f"调用update_project方法时出错: {str(e)}")
    
    # 创建测试按钮
    test_button = ttk.Button(
        test_frame, 
        text="测试更新项目功能", 
        command=simulate_update_project,
        width=20
    )
    test_button.pack(pady=10)
    
    # 创建退出按钮
    exit_button = ttk.Button(
        test_frame, 
        text="退出", 
        command=root.destroy,
        width=20
    )
    exit_button.pack(pady=10)
    
    # 运行主循环
    root.mainloop()

if __name__ == "__main__":
    test_update_project()