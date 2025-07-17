from dataclasses import dataclass, asdict
from typing import Dict, Optional


@dataclass
class Payload:
    """HTTP payload 結構"""

    firstin: Optional[str] = "1"  # default: 1
    step: Optional[str] = "1"  # default: 1
    TYPEK: Optional[str] = (
        None  # {sii: 上市, otc: 上櫃, all: 全部, sii0: 國內上市, sii1: 國外上市, otc0: 國內上櫃, otc1: 國外上貴}
    )

    co_id: Optional[str] = None  # Stock code
    year: Optional[str] = None  # ROC year
    month: Optional[str] = None  # Month (mm)
    season: Optional[str] = None  # Season

    def convert_to_clean_dict(self) -> Dict[str, str]:
        """Return a dict with all non-None fields"""
        return {key: value for key, value in asdict(self).items() if value is not None}
