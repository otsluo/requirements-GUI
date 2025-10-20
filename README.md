# Requirements GUI

一个图形化界面的Python包管理工具，支持requirements文件的创建、编辑和管理。

## 功能特性

- 图形化界面操作
- 支持requirements文件的创建、打开、保存
- 预设包集合功能，快速添加常用包组合
- 包搜索和安装功能
- 虚拟环境支持
- 启动器创建功能

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

## 使用方法

1. 运行程序：`python requirements_gui.py`
2. 使用预设按钮快速添加常用包组合
3. 通过"新增预设"创建自定义预设包
4. 使用其他功能管理Python包

## 系统要求

- Python 3.6+
- tkinter (通常随Python一起安装)
- pip

## 许可证

MIT
