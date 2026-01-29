#!/usr/bin/env python3
"""
自動生成 API 文檔的輔助腳本

此腳本可以從 Python 原始碼中提取 docstring 並更新文檔
"""

import ast
import inspect
from pathlib import Path
from typing import Dict, List, Optional


def extract_docstring_from_file(file_path: Path) -> Dict[str, str]:
    """從 Python 檔案中提取類別和方法的 docstring"""
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()

    tree = ast.parse(content)
    docstrings = {}

    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            class_doc = ast.get_docstring(node)
            if class_doc:
                docstrings[node.name] = {"class": class_doc, "methods": {}}

            # 提取方法 docstring
            for item in node.body:
                if isinstance(item, ast.FunctionDef):
                    method_doc = ast.get_docstring(item)
                    if method_doc and node.name in docstrings:
                        docstrings[node.name]["methods"][item.name] = method_doc

    return docstrings


def generate_api_doc_markdown(api_class_name: str, docstrings: Dict) -> str:
    """生成 API 文檔的 Markdown 內容"""
    if api_class_name not in docstrings:
        return ""

    class_info = docstrings[api_class_name]
    markdown = f"# {api_class_name}\n\n"

    # 類別說明
    if "class" in class_info:
        markdown += f"{class_info['class']}\n\n"

    # 方法說明
    if "methods" in class_info:
        markdown += "## 方法\n\n"
        for method_name, method_doc in class_info["methods"].items():
            markdown += f"### `{method_name}()`\n\n"
            markdown += f"{method_doc}\n\n"
            markdown += "---\n\n"

    return markdown


def main():
    """主函數"""
    # 從 dev/scripts/ 回到專案根目錄（需要上三層）
    project_root = Path(__file__).parent.parent.parent
    api_dir = project_root / "trader" / "api"
    docs_dir = project_root / "docs" / "api" / "data"

    print("正在掃描 API 檔案...")

    # 掃描所有 API 檔案
    api_files = {
        "stock_price_api.py": "StockPriceAPI",
        "stock_tick_api.py": "StockTickAPI",
        "stock_chip_api.py": "StockChipAPI",
        "monthly_revenue_report_api.py": "MonthlyRevenueReportAPI",
        "financial_statement_api.py": "FinancialStatementAPI",
    }

    for filename, class_name in api_files.items():
        file_path = api_dir / filename
        if file_path.exists():
            print(f"處理 {filename}...")
            docstrings = extract_docstring_from_file(file_path)

            # 這裡可以選擇更新現有文檔或生成新文檔
            # 目前只是示範，實際使用時可以根據需要調整
            print(f"  找到 {len(docstrings)} 個類別")
            if class_name in docstrings:
                print(f"  ✓ {class_name} 的文檔已提取")
        else:
            print(f"  ⚠ {filename} 不存在")

    print("\n完成！")
    print("注意：此腳本僅示範如何提取 docstring。")
    print("實際使用時，建議手動維護文檔以確保品質。")


if __name__ == "__main__":
    main()
