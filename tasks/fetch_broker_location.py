"""
Fetch broker location data from FinMind API (sourced directly from TWSE)
Person 3: Broker Location Data
"""

import os
from pathlib import Path
import pandas as pd
import requests
from dotenv import load_dotenv

URL = "https://api.finmindtrade.com/api/v4/data"
DATASET = "TaiwanSecuritiesTraderInfo"

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "Smart-Money-Data" / "raw" / "broker_location"
DATA_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_DIR = DATA_DIR
OUTPUT_FILE = "taiwan_securities_trader_info.csv"


def fetch_broker_location():
    """Fetch broker info from FinMind API as a DataFrame"""
    load_dotenv()
    token = os.environ.get("API_TOKEN")
    if not token:
        raise RuntimeError("API_TOKEN is missing. Please set it in your .env file.")

    headers = {"Authorization": f"Bearer {token}"}
    params = {"dataset": DATASET}
    resp = requests.get(URL, headers=headers, params=params, timeout=30)
    resp.raise_for_status()

    payload = resp.json()
    if "data" not in payload:
        raise ValueError("Unexpected API response: missing 'data' field.")

    data = pd.DataFrame(payload["data"])
    print(data.head(10))
    return data


def save_to_csv(dataframe: pd.DataFrame, output_dir: Path = OUTPUT_DIR) -> Path:
    """Persist the DataFrame to CSV and return the file path."""
    output_dir.mkdir(parents=True, exist_ok=True)
    file_path = output_dir / OUTPUT_FILE
    dataframe.to_csv(file_path, index=False, encoding="utf-8-sig")
    print(f"file saved to: {file_path}")
    return file_path


def validate_csv(file_path: Path):
    """Reload and validate the CSV by printing head and missing value summary."""
    try:
        df = pd.read_csv(file_path)
        print("data import success:")
        df.head()
    except FileNotFoundError:
        print(f"Error: cannot found '{file_path.name}'")
        return


def upload_to_hdfs(local_path, hdfs_path):
    """Upload broker location to HDFS"""
    # TODO: Implement HDFS upload
    pass


if __name__ == "__main__":
    df = fetch_broker_location()
    csv_path = save_to_csv(df)
    validate_csv(csv_path)
