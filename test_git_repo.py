#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import subprocess
import sys
import os

def create_test_repo():
    """创建一个测试用的Git仓库，包含多个分支和标签"""
    # 创建测试目录
    test_dir = "test_repo"
    if not os.path.exists(test_dir):
        os.makedirs(test_dir)
    
    # 进入测试目录
    os.chdir(test_dir)
    
    # 初始化Git仓库
    subprocess.run(["git", "init"])
    
    # 配置用户信息
    subprocess.run(["git", "config", "user.name", "Test User"])
    subprocess.run(["git", "config", "user.email", "test@example.com"])
    
    # 创建初始提交
    with open("README.md", "w") as f:
        f.write("# Test Repository\n\nThis is a test repository for testing branch/tag switching.")
    
    subprocess.run(["git", "add", "README.md"])
    subprocess.run(["git", "commit", "-m", "Initial commit"])
    
    # 创建分支
    subprocess.run(["git", "checkout", "-b", "feature-branch"])
    with open("feature.txt", "w") as f:
        f.write("This is a feature branch file.")
    subprocess.run(["git", "add", "feature.txt"])
    subprocess.run(["git", "commit", "-m", "Add feature file"])
    
    # 创建另一个分支
    subprocess.run(["git", "checkout", "-b", "develop"])
    with open("dev.txt", "w") as f:
        f.write("This is a develop branch file.")
    subprocess.run(["git", "add", "dev.txt"])
    subprocess.run(["git", "commit", "-m", "Add dev file"])
    
    # 切换回master分支
    subprocess.run(["git", "checkout", "master"])
    
    # 创建标签
    subprocess.run(["git", "tag", "v1.0.0"])
    
    # 修改文件并创建另一个标签
    with open("README.md", "a") as f:
        f.write("\n\n## Version 2\n\nUpdated content.")
    subprocess.run(["git", "add", "README.md"])
    subprocess.run(["git", "commit", "-m", "Update README for v2"])
    subprocess.run(["git", "tag", "v2.0.0"])
    
    print("Test repository created with branches and tags.")

if __name__ == "__main__":
    create_test_repo()