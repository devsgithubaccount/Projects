from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="dashgas",
    version="1.0.0",
    author="Dev",
    description="Production-ready gas station inventory management system",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/devsgithubaccount/Projects",
    packages=find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "Development Status :: 5 - Production/Stable",
    ],
    python_requires=">=3.7",
    install_requires=[],
    extras_require={
        "dev": [
            "pytest>=7.0.0",
            "pytest-cov>=4.0.0",
            "black>=22.0.0",
            "flake8>=4.0.0",
        ],
    },
)
