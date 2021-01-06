from setuptools import setup

with open("requirements.txt", "r") as fh:
    install_requires = fh.read().splitlines()

setup(
    name="fenetre",
    version="0.1.6",
    description="",
    packages=["fenetre"],
    install_requires=install_requires,
    python_requires=">=3.6",
    zip_safe=False,
    include_package_data=True
)
