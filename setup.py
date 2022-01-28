import setuptools

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()


setuptools.setup(
    name="bytecodemanipulation",
    version="0.1.1",
    author="uuk",
    author_email="uuk1301@gmail.com",
    description="High level python bytecode manipulation",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/uuk0/PyBytecodeManipulator",
    project_urls={
        "Bug Tracker": "https://github.com/uuk0/PyBytecodeManipulator/issues",
    },
    classifiers=[
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Development Status :: 2 - Pre-Alpha",
        "Programming Language :: Python :: Implementation :: CPython",
    ],
    package_dir={"": "src"},
    packages=setuptools.find_packages(where="bytecodemanipulation"),
    python_requires=">=3.10",
)
