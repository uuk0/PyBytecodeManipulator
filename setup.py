import setuptools

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()


setuptools.setup(
    name="bytecodemanipulation",
    version="0.2.2",
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
    packages=["bytecodemanipulation"]
    + [
        "bytecodemanipulation." + e
        for e in setuptools.find_packages(where="bytecodemanipulation")
    ],
    package_data={
        "bytecodemanipulation": [
            "data/3_10/builtins.json",
            "data/3_10/instruction_spec.json",
            "data/3_10/opcodes.json",
            "data/3_10/standard_library.json",
        ]
    },
    python_requires=">=3.10",
)
