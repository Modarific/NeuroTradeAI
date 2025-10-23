#!/usr/bin/env python3
"""
NeuroTradeAI Setup Script
Real-time trading data scraper installation and configuration.
"""

from setuptools import setup, find_packages
import os

# Read the README file
def read_readme():
    with open("README.md", "r", encoding="utf-8") as fh:
        return fh.read()

# Read requirements
def read_requirements():
    with open("requirements.txt", "r", encoding="utf-8") as fh:
        return [line.strip() for line in fh if line.strip() and not line.startswith("#")]

setup(
    name="NeuroTradeAI",
    version="1.0.0",
    author="NeuroTradeAI Team",
    author_email="contact@neurotradeai.com",
    description="Real-time trading data scraper with professional dashboard",
    long_description=read_readme(),
    long_description_content_type="text/markdown",
    url="https://github.com/yourusername/NeuroTradeAI",
    project_urls={
        "Bug Reports": "https://github.com/yourusername/NeuroTradeAI/issues",
        "Source": "https://github.com/yourusername/NeuroTradeAI",
        "Documentation": "https://github.com/yourusername/NeuroTradeAI/wiki",
    },
    packages=find_packages(),
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "Intended Audience :: Financial and Insurance Industry",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Operating System :: Microsoft :: Windows",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Programming Language :: Python :: 3.13",
        "Programming Language :: Python :: 3.14",
        "Topic :: Office/Business :: Financial :: Investment",
        "Topic :: Scientific/Engineering :: Information Analysis",
        "Topic :: Software Development :: Libraries :: Python Modules",
    ],
    python_requires=">=3.8",
    install_requires=read_requirements(),
    extras_require={
        "dev": [
            "pytest>=7.0.0",
            "pytest-asyncio>=0.21.0",
            "pytest-cov>=4.0.0",
            "black>=23.0.0",
            "flake8>=6.0.0",
            "mypy>=1.0.0",
        ],
        "test": [
            "pytest>=7.0.0",
            "pytest-asyncio>=0.21.0",
            "pytest-cov>=4.0.0",
            "pytest-mock>=3.10.0",
        ],
    },
    entry_points={
        "console_scripts": [
            "neurotradeai=app.main:main",
        ],
    },
    include_package_data=True,
    package_data={
        "": ["*.md", "*.txt", "*.bat", "*.html", "*.css", "*.js"],
    },
    keywords=[
        "trading",
        "finance",
        "data",
        "scraper",
        "real-time",
        "market-data",
        "stocks",
        "crypto",
        "news",
        "filings",
        "sec",
        "finnhub",
        "api",
        "websocket",
        "fastapi",
        "dashboard",
    ],
    zip_safe=False,
)
