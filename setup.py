#!/usr/bin/env python3
from setuptools import setup

setup(
    name="huedo",
    version="0.0.1",
    description="Command line tool for Phillips Hue lights",
    author="Will Smith",
    author_email="wsmith@akamai.com",
    packages=[
        "huedo",
    ],
    license="BSD 3-Clause License",
    install_requires=[
        "requests",
        "PyYAML",
    ],
    entry_points={
        "console_scripts": [
            "huedo = huedo:main",
        ]
    },
    python_requires=">=3.6",
)
