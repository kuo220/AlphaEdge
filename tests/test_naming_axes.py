from typing import Set

from core.pipeline.utils import IssuerOrigin, ListingBoard
from core.utils import InstrumentType, Market

"""
命名軸線的防迴歸護欄（四條軸的定案見 `docs/dev/naming-axes.md`）

全專案曾用「市場／market」一個詞同時指四條互相正交的軸，導致相依的兩份架構文件
講「多市場」時指的不是同一件事。本檔把四條軸的邊界釘住——**軸之間的值一旦出現
交集，就代表又有人把兩條軸壓回同一個名字裡**，那是靜默的語意汙染，不會有任何
執行期徵兆，只能靠測試擋。
"""


def _values(enum_cls) -> Set[str]:
    """取得 Enum 的所有成員值（含 alias 也只算一次）"""

    return {member.value for member in enum_cls}


def test_market_and_instrument_type_are_disjoint() -> None:
    """軸 A（地區）與軸 B（商品類別）的值不得有交集"""

    assert not _values(Market) & _values(InstrumentType)


def test_market_holds_only_regions() -> None:
    """軸 A 只放地區；`STOCK`／`FUTURE`／`OPTION` 屬軸 B"""

    assert _values(Market) == {"TW", "US"}


def test_instrument_type_holds_only_instruments() -> None:
    """軸 B 只放商品類別；`TW`／`US` 屬軸 A"""

    assert _values(InstrumentType) == {"Stock", "Future", "Option"}


def test_listing_board_and_issuer_origin_are_disjoint() -> None:
    """軸 C（掛牌板別）與軸 D（發行人國別）的值不得有交集"""

    assert not _values(ListingBoard) & _values(IssuerOrigin)


def test_listing_board_has_no_issuer_origin_members() -> None:
    """
    軸 C 不得再混入發行人國別

    這正是舊 `MarketType` 的坑：`SII0 = "0"` 與 `OTC0 = "0"` 值相同，
    Python Enum 會讓後者變成前者的 alias，`MarketType.OTC0 is MarketType.SII0`
    為 True。拆成兩條軸後 alias 自然消失，本測試防止它被合併回去。
    """

    assert _values(ListingBoard) == {"sii", "otc", "rotc", "pub", "all"}
    assert len(ListingBoard.__members__) == len(_values(ListingBoard))


def test_issuer_origin_has_no_alias() -> None:
    """軸 D 的成員數與值數相同，代表沒有任何成員被摺成 alias"""

    assert len(IssuerOrigin.__members__) == len(_values(IssuerOrigin))
