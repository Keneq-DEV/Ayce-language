from setuptools import setup, find_packages
setup(
    name="ayce",
    version="0.5.1",
    description="Intérprete del lenguaje de programación ayce",
    author="Proyecto ayce",
    license="MIT",
    python_requires=">=3.10",
    packages=find_packages(where="."),
    entry_points={"console_scripts": ["ayce=ayce.__main__:main"]},
)
