import os
from pathlib import Path
from typing import Optional


# 從環境變數（或預設值）載入路徑並解析為絕對路徑
def get_env_resolved_path(
    base_dir: Path,
    env_key: str,
    default: str = None,
) -> Path:
    """
    從環境變數載入路徑並解析為絕對路徑。

    Args:
        base_dir: 基礎目錄路徑
        env_key: 環境變數的鍵名
        default: 當環境變數不存在時使用的預設值

    Returns:
        解析後的絕對路徑

    Raises:
        ValueError: 當環境變數不存在且未提供預設值時

    Example:
        >>> base = Path('/home/user/project')
        >>> os.environ['DATA_DIR'] = 'my_data'
        >>> path = get_env_resolved_path(base, 'DATA_DIR')
        >>> # 結果: PosixPath('/home/user/project/my_data')
    """
    value: Optional[str] = os.getenv(env_key, default)
    if value is None:
        raise ValueError(f"Missing required environment variable: {env_key}")
    return (base_dir / value).resolve()


# 將固定資料夾名稱解析為 base_dir 下的絕對路徑
def get_static_resolved_path(base_dir: Path, dir_name: str) -> Path:
    """
    將固定資料夾名稱解析為 base_dir 下的絕對路徑。

    Args:
        base_dir: 基礎目錄路徑
        dir_name: 資料夾名稱或相對路徑字串（可包含子目錄，如 "logs/app"）

    Returns:
        解析後的絕對路徑

    Example:
        >>> base = Path('/home/user/project')
        >>> path = get_static_resolved_path(base, 'logs')
        >>> # 結果: PosixPath('/home/user/project/logs')
    """
    return (base_dir / dir_name).resolve()
