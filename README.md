# Requirements GUI-可视化管理工具

一个用于管理Python项目依赖的图形界面工具，支持所有pip requirements的功能。

![界面预览](screenshots/main_window.png)

## 功能特性

- 📄 **可视化编辑**: 直观地查看和编辑requirements文件
- ➕ **包管理**: 添加、删除、修改包依赖
- ⬇️ **包操作**: 安装、更新、卸载Python包
- 📦 **环境同步**: 生成当前环境的requirements文件
- 📋 **状态查看**: 实时查看包的安装状态
- 🔄 **版本控制**: 支持各种版本操作符（==, >=, <=, >, <, !=, ~=）
- 🌐 **镜像源切换**: 支持多种国内镜像源（清华、阿里、豆瓣等）
- 📦 **预设包集合**: 内置AI绘画、AI图像、AI音频、AI视频、数据科学、Web开发等常用包集合
- 🌲 **虚拟环境管理**: 创建和切换Python虚拟环境
- 🔧 **跨平台**: 支持Windows、macOS和Linux

## 安装和运行

### 方法一：直接运行（推荐）
1. 确保已安装Python 3.6+
2. 克隆或下载此项目
3. 运行程序：
   ```bash
   python requirements_gui.py
   ```
   或在Windows上双击`start.bat`

### 方法二：使用pip安装
```bash
# 克隆项目
git clone https://github.com/otsluo/requirements-GUI.git
cd requirements-gui

# 安装依赖
pip install -r requirements.txt

# 运行程序
python requirements_gui.py
```

### 方法三：开发者安装
```bash
# 克隆项目
git clone https://github.com/otsluo/requirements-GUI.git
cd requirements-GUI

# 开发者模式安装
pip install -e .
```

## 使用方法

### 主界面介绍

主界面分为以下几个区域：
1. **文件操作区**: 新建、打开、保存requirements文件
2. **包管理区**: 添加、删除、编辑包依赖
3. **包列表区**: 显示所有包及其状态
4. **状态栏**: 显示当前操作状态

### 文件操作
- **新建**: 创建一个新的空requirements文件
- **打开**: 打开现有的requirements文件（.txt格式）
- **保存**: 保存当前编辑的requirements文件
- **另存为**: 将当前文件保存到新位置

### 包管理操作
- **添加包**: 点击"添加包"按钮，在弹出对话框中输入包名、版本等信息
- **删除选中**: 选择一个或多个包，点击"删除选中"按钮将其删除
- **编辑包**: 双击包名或选中后按回车键，可编辑包信息
- **刷新列表**: 更新包列表，显示最新的安装状态

### 包安装操作
- **安装选中**: 选择一个或多个包，点击"安装选中"按钮进行安装
- **更新选中**: 选择一个或多个包，点击"更新选中"按钮更新到最新版本
- **卸载选中**: 选择一个或多个包，点击"卸载选中"按钮从环境卸载
- **安装所有包**: 点击菜单"操作"->"安装所有包"，安装所有列出的包
- **列出已安装**: 点击"列出已安装"按钮，显示当前环境中已安装的所有包

### 高级功能
- **生成当前环境的requirements**: 点击菜单"操作"->"生成当前环境的requirements"，自动生成当前Python环境的所有包依赖
- **版本操作符支持**: 支持所有标准版本操作符（==, >=, <=, >, <, !=, ~=）
- **包状态显示**: 显示包是否已安装及安装的版本

### 虚拟环境管理
- **创建虚拟环境**: 点击"创建虚拟环境"按钮，选择目录创建新的Python虚拟环境
- **选择虚拟环境**: 点击"选择虚拟环境"按钮，选择现有虚拟环境进行包管理操作
- **环境隔离**: 在虚拟环境中安装的包不会影响系统Python环境

### 镜像源切换
- **多源支持**: 支持默认、清华、阿里、豆瓣、中科大等多个镜像源
- **快速切换**: 通过下拉菜单快速切换pip包安装的镜像源
- **加速下载**: 使用国内镜像源加速包的下载和安装

### 预设包集合
- **AI绘画**: 包含torch、torchvision、diffusers、transformers等AI绘画相关包
- **AI图像**: 包含opencv-python、Pillow、scikit-image等图像处理相关包
- **AI音频**: 包含librosa、soundfile、pydub等音频处理相关包
- **AI视频**: 包含moviepy、opencv-python、av等视频处理相关包
- **数据科学**: 包含numpy、pandas、matplotlib、scikit-learn等数据科学常用包
- **Web开发**: 包含flask、django、fastapi、requests等Web开发常用包
- **一键加载**: 点击对应按钮一键加载预设包集合到当前项目

## 系统要求

- **操作系统**: Windows 7+/macOS 10.9+/Linux (任何支持Python的系统)
- **Python版本**: 3.6 或更高版本
- **依赖**: pip 包管理器（通常随Python一起安装）

## 兼容性说明

- **Python 3.8+**: 使用内置的`importlib.metadata`模块
- **Python 3.6-3.7**: 需要额外安装`importlib-metadata`包
  ```bash
  pip install importlib-metadata
  ```

## 项目结构

```
requirements-GUI/
├── requirements_gui.py     # 主程序文件
├── requirements.txt        # 项目依赖文件
├── setup.py               # 安装配置文件
├── README.md              # 说明文档
├── EXAMPLES.md            # 使用示例
├── start.bat              # Windows启动脚本
└── screenshots/           # 界面截图目录
    └── main_window.png    # 主界面预览图
```

## 开发指南

### 项目特点
1. 使用纯Python和tkinter构建，无需额外GUI框架
2. 兼容Python 3.6到最新版本
3. 使用现代Python API处理包信息
4. 符合Python最佳实践

### 扩展功能
开发者可以通过以下方式扩展功能：
1. 添加新的包源支持（如conda、pipenv等）
2. 增加依赖关系图可视化
3. 添加包冲突检测功能
4. 添加更多预设包集合
5. 支持requirements文件的版本管理
6. 增加包依赖关系分析功能

## 常见问题

### Q: 程序启动时报错"没有找到指定模块"？
A: 确保已正确安装Python，并且pip可用。如果使用Python 3.6或3.7，请安装importlib-metadata：
```bash
pip install importlib-metadata
```

### Q: 如何从Git仓库安装包？
A: 在添加包时，可以在版本号处填写Git URL，例如：
```
package_name @ git+https://github.com/user/repo.git
```

### Q: 如何指定包的 extras？
A: 在包名后添加extras，例如：
```
requests[security]==2.28.1
```

## 许可证

MIT License

Copyright (c) 2023 otsluo

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.