print("Starting building & uploading to PyPy")
# todo: read token from local config file
# todo: run unit tests before upload

import subprocess
import os
import sys

local = os.path.dirname(__file__)

version = input("version: ")

with open("setup.py", mode="r") as f:
    data = f.read().split("\n")

assert data[8].strip().startswith("version=\"")

data[8] = f'    version="{version}",'

with open("setup.py", mode="w") as f:
    f.write("\n".join(data))

subprocess.call([sys.executable, "-m", "pip", "install", "--upgrade", "build", "twine"])
subprocess.call([sys.executable, "-m", "build"])
subprocess.call([sys.executable, "-m", "twine", "upload", "dist/*"])

