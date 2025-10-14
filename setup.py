from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

with open("requirements.txt", "r", encoding="utf-8") as fh:
    install_requires = [line.strip() for line in fh.readlines() if line.strip() and not line.startswith("#")]

setup(
    name="requirements-gui",
    version="1.0.0",
    author="Python Developer",
    author_email="developer@example.com",
    description="A GUI tool for managing Python requirements",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/yourusername/requirements-gui",
    packages=find_packages(),
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
    ],
    python_requires=">=3.6",
    install_requires=install_requires,
    entry_points={
        "console_scripts": [
            "requirements-gui=requirements_gui:main",
        ],
    },
    package_data={
        "": ["README.md", "requirements.txt"],
    },
    include_package_data=True,
)