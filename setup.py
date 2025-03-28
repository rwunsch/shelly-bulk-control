from setuptools import setup, find_packages

setup(
    name="shelly-manager",
    version="0.1.0",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    install_requires=[
        "fastapi>=0.104.1",
        "uvicorn>=0.24.0",
        "zeroconf>=0.131.0",
        "pydantic>=2.4.2",
        "typer>=0.9.0",
        "rich>=13.7.0",
        "pyyaml>=6.0.1",
        "aiohttp>=3.9.1",
        "python-multipart>=0.0.6",
        "aiocoap>=0.4.6",
    ],
    extras_require={
        "dev": [
            "pytest>=7.4.3",
            "pytest-asyncio>=0.21.1",
            "httpx>=0.25.1",
        ],
    },
    entry_points={
        "console_scripts": [
            "shelly-manager=shelly_manager.interfaces.cli.main:app",
        ],
    },
    python_requires=">=3.10",
    author="Your Name",
    author_email="your.email@example.com",
    description="Enterprise-Grade Shelly Device Management Tool",
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
    url="https://github.com/yourusername/shelly-manager",
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
    ],
) 