import os
from pathlib import Path
from typing import Optional


# 從環境變數（或預設值）載入路徑並解析為絕對路徑
def get_env_resolved_path(
    base_dir: Path,
    env_key: str,
    default: str = None,
) -> Path:
    value: Optional[str] = os.getenv(env_key, default)
    if value is None:
        raise ValueError(f"Missing required environment variable: {env_key}")
    return (base_dir / value).resolve()


# 將固定資料夾名稱解析為 base_dir 下的絕對路徑
def get_static_resolved_path(base_dir: Path, dir_name: str) -> Path:
    return (base_dir / dir_name).resolve()
