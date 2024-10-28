import sys
from pathlib import Path
from utils.test import getPath
# print(Path(__file__).parents[2] / 'Data' / 'data.db')
# print(str(Path(__file__).resolve().parents[1] / 'Data' / 'financial_statement'))
getPath()

print(f"* This file path: {str(Path(__file__).resolve())}")