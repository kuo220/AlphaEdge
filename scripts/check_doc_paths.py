import argparse
import re
import sys
from pathlib import Path
from typing import Dict, List, Set, Tuple

"""
文件路徑漂移檢查：找出 `.md` 裡指不到檔案、但同名檔存在於別處的路徑引用

檔案搬家時文件不會自己跟上。**只回報「同名檔確實存在於別處」的引用**——
那才是漂移；指不到又找不到同名檔的多半是規劃中的未來檔案（`backlog/` 常見），
不是錯誤（健檢第三輪 S4）。

- Features:
    1. 抓行內程式碼（`` `core/xxx/yyy.py` ``）與 Markdown 連結中的帶目錄路徑
    2. 指得到就跳過；指不到但全 repo 有同名檔即回報，並列出實際位置
    3. 只寫檔名不寫目錄的簡稱（`` `factory.py` ``）不算——那是行文，不是連結
- 使用場景:
    python scripts/check_doc_paths.py           # 有漂移時以非零狀態碼結束
    python scripts/check_doc_paths.py --list-unknown  # 另列指不到且無同名檔者
"""

_PROJECT_ROOT: Path = Path(__file__).resolve().parent.parent

# 掃描哪些 `.md`
_SCAN_DIRS: Tuple[str, ...] = (
    "docs",
    "backlog",
    "core",
    "tasks",
    "frontend",
    "strategy_lab",
    "scripts",
    "tests",
)
_SCAN_FILES: Tuple[str, ...] = ("CLAUDE.md", "README.md")

# 排除的目錄
_EXCLUDE_PARTS: Set[str] = {".venv", "__pycache__", "node_modules", ".git"}

# 只認這些副檔名；`.md` 的相對連結另有 Markdown 自己的解析規則，不在本檢查範圍
_EXTENSIONS: Tuple[str, ...] = (".py", ".sh", ".yaml", ".yml", ".toml", ".cfg", ".json")

# 行內程式碼與 Markdown 連結目標
_INLINE_CODE: re.Pattern = re.compile(r"`([^`\n]+?)`")

# 歷史紀錄檔：當時的路徑就是那樣，改成現在的路徑反而讓紀錄失真
_HISTORICAL_DOCS: Set[str] = {
    "docs/dev/health-check-2026-09.md",
}

# 敘述搬家這件事本身的句子：舊路徑是主詞，改掉會讓句子不成立
# （例如「`core/config.py` 已拆為套件」）
_NARRATIVE: Set[Tuple[str, str]] = {
    ("docs/dev/runtime-artifacts.md", "core/config.py"),
    ("backlog/PostgreSQL遷移計畫.md", "core/config.py"),
    # 本檢查誕生的那份 backlog：表格裡列的就是「文件寫的舊路徑」
    ("backlog/健檢第三輪收斂.md", "core/config.py"),
    ("backlog/健檢第三輪收斂.md", "core/pipeline/loaders/stock_tick_loader.py"),
}

# 已知待修但暫時擋住的檔案。**解除封鎖後要連同條目一起刪掉**——
# 留著不刪，這份檢查就會對那個檔案永久失明。
#
# 2026-09-13：`docs/futures/tw-futures-platform.md` 的 10 處已全數修正，
# 本清單因此清空。當初擋住的理由是該檔有另一條線的未提交變更，
# 最後是以「只暫存 HEAD＋本次修正、不碰對方工作目錄內容」的方式解掉的。
_PENDING: Dict[str, str] = {}


def _iter_markdown_files() -> List[Path]:
    """取得掃描範圍內所有 `.md`"""

    files: List[Path] = []
    for directory in _SCAN_DIRS:
        root: Path = _PROJECT_ROOT / directory
        if not root.exists():
            continue
        files.extend(
            path for path in root.rglob("*.md") if not _EXCLUDE_PARTS & set(path.parts)
        )
    files.extend(
        _PROJECT_ROOT / name for name in _SCAN_FILES if (_PROJECT_ROOT / name).exists()
    )
    return sorted(set(files))


def _collect_real_paths() -> List[str]:
    """全 repo 中所有原始碼／設定檔的相對路徑"""

    return sorted(
        str(path.relative_to(_PROJECT_ROOT))
        for path in _PROJECT_ROOT.rglob("*")
        if path.is_file()
        and not _EXCLUDE_PARTS & set(path.parts)
        and path.suffix in _EXTENSIONS
    )


def _is_shorthand(reference: str, real_paths: List[str]) -> bool:
    """
    - Description:
        判斷這個引用是不是「真實路徑的尾段簡稱」

        文件常以 `` `report/reporter.py` `` 稱呼
        `core/backtest/report/reporter.py`——那是行文，不是壞掉的連結，
        與只寫檔名的簡稱同性質。比對必須落在**目錄邊界**上，
        否則 `ker.py` 也會被當成 `broker.py` 的簡稱。
    - Parameters:
        - reference: str
            文件裡寫的路徑
        - real_paths: List[str]
            全 repo 的真實路徑
    - Return:
        - bool
            是尾段簡稱即為 True
    """

    suffix: str = "/" + reference
    return any(real.endswith(suffix) for real in real_paths)


def _moved_to(reference: str, real_paths: List[str]) -> List[str]:
    """
    - Description:
        找出這個引用「搬到哪裡去了」

        判準是**最後兩段相同**（父目錄 ＋ 檔名）：`core/api/futures_chip_api.py`
        搬成 `core/api/tw/futures_chip_api.py`，兩者的最後兩段是
        `api/futures_chip_api.py` 與 `tw/futures_chip_api.py`——不相同，
        故改以「檔名相同且引用的父目錄仍是新路徑的一段」收斂。

        只比對檔名太寬：`base.py` 全 repo 有七個，
        `backlog/美股ETL與回測架構規劃.md` 的 `providers/base.py`
        是規劃中的未來檔案，不該被判成漂移。
    - Parameters:
        - reference: str
            文件裡寫的路徑
        - real_paths: List[str]
            全 repo 的真實路徑
    - Return:
        - List[str]
            實際位置；找不到時為空 list
    """

    parts: List[str] = reference.split("/")
    name: str = parts[-1]
    ancestors: Set[str] = set(parts[:-1])

    return [
        real
        for real in real_paths
        if Path(real).name == name and ancestors <= set(Path(real).parts[:-1])
    ]


def _split_into_package(reference: str) -> bool:
    """`core/config.py` → `core/config/` 這類「單檔拆成套件」的漂移"""

    candidate: Path = _PROJECT_ROOT / reference[: -len(".py")]
    return reference.endswith(".py") and candidate.is_dir()


def _extract_paths(text: str) -> Set[str]:
    """抓出一份文件裡所有「帶目錄的路徑引用」"""

    found: Set[str] = set()
    for raw in _INLINE_CODE.findall(text):
        candidate: str = raw.strip().strip("`")
        # 只寫檔名不寫目錄的簡稱不算——那是行文，不是連結
        if "/" not in candidate:
            continue
        # 命令列、含空白或萬用字元的樣式不是單一檔案引用
        if any(ch in candidate for ch in " *?{}()[]<>|"):
            continue
        if not candidate.endswith(_EXTENSIONS):
            continue
        found.add(candidate[2:] if candidate.startswith("./") else candidate)
    return found


def main() -> int:
    """列出搬過家卻沒更新的路徑引用；有漂移時回非零狀態碼"""

    parser = argparse.ArgumentParser(description="文件路徑漂移檢查")
    parser.add_argument(
        "--list-unknown",
        action="store_true",
        help="另外列出指不到且全 repo 也沒有同名檔者（多為規劃中的未來檔案）",
    )
    args = parser.parse_args()

    real_paths: List[str] = _collect_real_paths()

    drifted: List[Tuple[str, str, List[str]]] = []
    unknown: List[Tuple[str, str]] = []
    pending: List[Tuple[str, str, List[str]]] = []

    for doc in _iter_markdown_files():
        rel_doc: str = str(doc.relative_to(_PROJECT_ROOT))
        if rel_doc in _HISTORICAL_DOCS:
            continue

        for reference in sorted(_extract_paths(doc.read_text(encoding="utf-8"))):
            if (_PROJECT_ROOT / reference).exists():
                continue
            # 真實路徑的尾段簡稱：那是行文，不是壞掉的連結
            if _is_shorthand(reference, real_paths):
                continue
            # 敘述搬家這件事本身的句子：舊路徑是主詞，不算漂移
            if (rel_doc, reference) in _NARRATIVE:
                continue

            if _split_into_package(reference):
                elsewhere: List[str] = [f"{reference[:-3]}/（已拆為套件）"]
            else:
                elsewhere = _moved_to(reference, real_paths)

            if not elsewhere:
                unknown.append((rel_doc, reference))
            elif rel_doc in _PENDING:
                pending.append((rel_doc, reference, elsewhere))
            else:
                drifted.append((rel_doc, reference, elsewhere))

    if args.list_unknown:
        print(f"指不到且無同名檔（{len(unknown)} 個，多為規劃中的未來檔案）：")
        for rel_doc, reference in unknown:
            print(f"  {rel_doc}: {reference}")
        print()

    if pending:
        print(f"已知待修、暫時擋住的（{len(pending)} 處，不計入結束碼）：")
        for rel_doc, reference, elsewhere in pending:
            print(f"  {rel_doc}")
            print(f"      寫的是 {reference}")
            print(f"      實際在 {'、'.join(elsewhere)}")
        for rel_doc, reason in _PENDING.items():
            print(f"  擋住的理由（{rel_doc}）：{reason}")
        print()

    if drifted:
        print(f"搬過家卻沒更新的引用（{len(drifted)} 處）：")
        for rel_doc, reference, elsewhere in drifted:
            print(f"  {rel_doc}")
            print(f"      寫的是 {reference}")
            print(f"      實際在 {'、'.join(elsewhere)}")
        return 1

    print("搬過家卻沒更新的引用：0 處")
    return 0


if __name__ == "__main__":
    sys.exit(main())
