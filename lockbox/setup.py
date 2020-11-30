import setuptools

with open("requirements.txt", "r") as fh:
    install_requires = fh.read().splitlines()

setuptools.setup(
    name="lockbox",
    version="0.0.0",
    description="",
    packages=setuptools.find_packages(),
    install_requires=install_requires,
    python_requires=">=3.6",
    entry_points={
        "console_scripts": ["lockbox=lockbox:main"]
    }
)
