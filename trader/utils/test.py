from pathlib import Path




def getPath():
    print(f"This file path: {str(Path(__file__).resolve())}")
    print(f"This file parent path: {str(Path(__file__).resolve().parents[1])}")


for path in Path(__file__).parents:
    print(f"Path: {path}")