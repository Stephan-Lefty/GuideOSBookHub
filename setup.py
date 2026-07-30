from setuptools import setup, find_packages

setup(
    name="guideosbookhub",
    version="0.1.0",
    packages=find_packages(),
    py_modules=["guideosbookhub"],
    package_data={"assets": ["*.png"]},
    include_package_data=True,
)