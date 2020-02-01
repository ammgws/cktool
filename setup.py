#!/usr/bin/env python
# -*- coding: utf-8 -*-

from os import path
from setuptools import setup, find_packages  # Always prefer setuptools over distutils

here = path.abspath(path.dirname(__file__))
with open(path.join(here, 'README.md'), encoding='utf-8') as f:
    long_description = f.read()

setup(
    name="cktool",
    version="0.0.2",
    description="Command line tool for dealing with clubkatsudo.com chores",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/ammgws/cktool",
    packages=find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires='>=3.7',
    install_requires=[
        "click",
        "reportlab",
        "requests",
        "requests-html",
        "svglib",
        "toml",
    ],
    entry_points='''
        [console_scripts]
        cktool=cktool.cktool:cli
    ''',
    package_data={'cktool': ['formation.svg']},
    include_package_data=True,
    keywords='clubkatsudo clubkatsudo.com',
)
