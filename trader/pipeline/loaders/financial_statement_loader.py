import shutil
import sqlite3
import pandas as pd
from pathlib import Path

from trader.pipeline.loaders.base import BaseDataLoader
from trader.config import DB_PATH