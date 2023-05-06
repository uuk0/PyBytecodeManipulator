import sys


with open("setup.py", mode="r") as f:
    data = f.read().split("\n")

assert data[8].strip().startswith('version="')

data[8] = f'    version="{sys.argv[1]}",'

with open("setup.py", mode="w") as f:
    f.write("\n".join(data))

