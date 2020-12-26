from setuptools import setup

with open("requirements.txt", "r") as fh:
    install_requires = fh.read().splitlines()

setup(
    name="lockbox",
    version="0.1.1",
    description="",
    packages=["lockbox"],
    install_requires=install_requires,
    python_requires=">=3.6",
    entry_points={
        "console_scripts": ["lockbox=lockbox:main"]
    }
)
