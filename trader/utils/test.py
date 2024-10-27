from pathlib import Path


# print(Path(__file__).parents[2] / 'Data' / 'data.db')
print(str(Path(__file__).resolve().parents[1]))