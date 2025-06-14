import argparse
from typing import Dict, Type
parser = argparse.ArgumentParser(description="Trading System")

print(type(parser.parse_args()))