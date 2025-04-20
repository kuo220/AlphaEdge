import os
import numpy as np
import pandas as pd
import datetime
import time
from pathlib import Path
import shutil
import sqlite3
from io import StringIO
from typing import List


"""
Utility class for common SQLite operations: table check, date retrieval, query execution.
Shared across crawlers for reusability and clean separation of logic.
"""

class SQLiteTools:
    @staticmethod
    def check_table_exist(conn: sqlite3.Connection, table_name: str) -> bool:
        query = "SELECT count(*) FROM sqlite_master WHERE type='table' AND name=?"
        result = conn.execute(query, (table_name,)).fetchone()
        return result[0] == 1
