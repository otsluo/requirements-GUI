# Requirements GUI

一个图形化界面的Python包管理工具，支持requirements文件的创建、编辑和管理。
## 原生调用
    基于原生pip命令行工具，增加了可视化的操作界面，用户可以通过界面进行包的管理。适合新手小白快速上手，同时和用户简单的包管理需求。
    不用专门安装conda等工具，这类适合专业人士的工具。


## 界面预览

![界面预览](screenshots/main_window.png)
## 功能特性

- 图形化界面操作，简单直观
- 支持 requirements 文件的创建、编辑、保存
- 支持从现有环境生成 requirements 文件
- 支持一键安装、更新、卸载包
- 支持预设包管理，快速添加常用包
- 支持虚拟环境管理，包括创建、选择和嵌入式环境支持
- 支持requirements文件管理（加载、保存、合并）
- 支持预设包管理（默认预设包、自定义预设包）
- 支持批量操作符管理，可统一设置包版本操作符
- 支持镜像源切换（官方、清华、阿里、豆瓣、中科大等）
- 支持包的安装、升级、卸载操作
- 支持包信息查看（版本、描述、依赖等）
- 支持实用功能（清空列表、复制包名、导出列表、打开CMD窗口）

## 预设包管理

### 预设包集合

本工具支持通过JSON文件管理预设包集合，用户可以自定义和编辑预设包。

### 默认预设包

工具内置以下默认预设包集合：
- AI绘画：torch, torchvision, diffusers, transformers, accelerate
- AI图像：opencv-python, Pillow, scikit-image, albumentations
- AI音频：librosa, soundfile, pydub, speechbrain
- AI视频：moviepy, opencv-python, av
- 数据科学：numpy, pandas, matplotlib, seaborn, scikit-learn
- Web开发：flask, django, fastapi, requests, gunicorn

### 自定义预设包

用户可以通过"新增预设"功能创建自定义预设包集合，这些预设会保存在`presets.json`文件中。

### 预设复制功能

所有预设（包括默认预设和自定义预设）都支持复制功能。用户可以右键点击任何预设按钮，选择"复制"选项来创建一个新的预设。复制的预设将带有"副本"后缀，用户可以在创建时修改预设名称和包列表。

### presets.json文件格式

```json
{
    "presets": {
        "preset_key": {
            "name": "预设名称",
            "packages": [
                {
                    "name": "包名",
                    "version": "版本号",
                    "operator": "操作符",
                    "source": "来源"
                }
            ]
        }
    }
}
```

## 安装方法

### 方法一：直接下载运行（推荐）

```bash
git clone https://github.com/otsluo/requirements-GUI.git
```
```bash
# 加速镜像
git clone https://gitcode.com/weixin_45738527/comfyui-xnantool.git
```

## 使用方法

1. 运行程序：`python requirements_gui.py` 或双击 `start.bat`
2. 使用预设按钮快速添加常用包组合
3. 通过"新增预设"创建自定义预设包
4. 使用其他功能管理Python包


## 系统要求

- Python 3.6+
- tkinter (通常随Python一起安装)
- pip

## 许可证

MIT
