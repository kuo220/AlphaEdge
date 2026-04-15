#!/usr/bin/env python3
"""
Rewrite DataFrame-like column access from attr syntax to subscript:
  df.col -> df["col"], merged_df.x -> merged_df["x"]

Only touches bases named `df` or ending with `_df`. Skips names in
pandas.DataFrame API (dir, no leading underscore).
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SKIP_DIRS = {".git", ".venv", "venv", "__pycache__", "node_modules"}


def is_df_like(name: str) -> bool:
    return name == "df" or name.endswith("_df")


# pandas.DataFrame public names (Python 3.14 + pandas 2.x); avoids import at codemod time.
_STATIC_DATAFRAME_RESERVED: frozenset[str] = frozenset(
    x
    for x in (
        "T",
        "abs",
        "add",
        "add_prefix",
        "add_suffix",
        "agg",
        "aggregate",
        "align",
        "all",
        "any",
        "apply",
        "asfreq",
        "asof",
        "assign",
        "astype",
        "at",
        "at_time",
        "attrs",
        "axes",
        "between_time",
        "bfill",
        "boxplot",
        "clip",
        "columns",
        "combine",
        "combine_first",
        "compare",
        "convert_dtypes",
        "copy",
        "corr",
        "corrwith",
        "count",
        "cov",
        "cummax",
        "cummin",
        "cumprod",
        "cumsum",
        "describe",
        "diff",
        "div",
        "divide",
        "dot",
        "drop",
        "drop_duplicates",
        "droplevel",
        "dropna",
        "dtypes",
        "duplicated",
        "empty",
        "eq",
        "equals",
        "eval",
        "ewm",
        "expanding",
        "explode",
        "ffill",
        "fillna",
        "filter",
        "first_valid_index",
        "flags",
        "floordiv",
        "from_arrow",
        "from_dict",
        "from_records",
        "ge",
        "get",
        "groupby",
        "gt",
        "head",
        "hist",
        "iat",
        "idxmax",
        "idxmin",
        "iloc",
        "index",
        "infer_objects",
        "info",
        "insert",
        "interpolate",
        "isetitem",
        "isin",
        "isna",
        "isnull",
        "items",
        "iterrows",
        "itertuples",
        "join",
        "keys",
        "kurt",
        "kurtosis",
        "last_valid_index",
        "le",
        "loc",
        "lt",
        "map",
        "mask",
        "max",
        "mean",
        "median",
        "melt",
        "memory_usage",
        "merge",
        "min",
        "mod",
        "mode",
        "mul",
        "multiply",
        "ndim",
        "ne",
        "nlargest",
        "notna",
        "notnull",
        "nsmallest",
        "nunique",
        "pct_change",
        "pipe",
        "pivot",
        "pivot_table",
        "plot",
        "pop",
        "pow",
        "prod",
        "product",
        "quantile",
        "query",
        "radd",
        "rank",
        "rdiv",
        "reindex",
        "reindex_like",
        "rename",
        "rename_axis",
        "reorder_levels",
        "replace",
        "resample",
        "reset_index",
        "rfloordiv",
        "rmod",
        "rmul",
        "rolling",
        "round",
        "rpow",
        "rsub",
        "rtruediv",
        "sample",
        "select_dtypes",
        "sem",
        "set_axis",
        "set_flags",
        "set_index",
        "shape",
        "shift",
        "size",
        "skew",
        "sort_index",
        "sort_values",
        "sparse",
        "squeeze",
        "stack",
        "std",
        "style",
        "sub",
        "subtract",
        "sum",
        "swaplevel",
        "tail",
        "take",
        "to_clipboard",
        "to_csv",
        "to_dict",
        "to_excel",
        "to_feather",
        "to_hdf",
        "to_html",
        "to_iceberg",
        "to_json",
        "to_latex",
        "to_markdown",
        "to_numpy",
        "to_orc",
        "to_parquet",
        "to_period",
        "to_pickle",
        "to_records",
        "to_sql",
        "to_stata",
        "to_string",
        "to_timestamp",
        "to_xarray",
        "to_xml",
        "transform",
        "transpose",
        "truediv",
        "truncate",
        "tz_convert",
        "tz_localize",
        "unstack",
        "update",
        "value_counts",
        "values",
        "var",
        "where",
        "xs",
    )
)


def dataframe_reserved_names() -> frozenset[str]:
    try:
        import pandas as pd

        return frozenset(n for n in dir(pd.DataFrame) if not n.startswith("_"))
    except ImportError:
        return _STATIC_DATAFRAME_RESERVED


def line_start_offsets(source: str) -> list[int]:
    offsets: list[int] = []
    pos = 0
    for line in source.splitlines(keepends=True):
        offsets.append(pos)
        pos += len(line)
    return offsets


def node_char_span(source: str, node: ast.AST, starts: list[int]) -> tuple[int, int]:
    start = starts[node.lineno - 1] + node.col_offset
    end = starts[node.end_lineno - 1] + node.end_col_offset  # type: ignore[attr-defined]
    return start, end


def build_parents(tree: ast.AST) -> dict[ast.AST, ast.AST | None]:
    parents: dict[ast.AST, ast.AST | None] = {tree: None}

    def visit(node: ast.AST, parent: ast.AST | None) -> None:
        for child in ast.iter_child_nodes(node):
            parents[child] = node
            visit(child, node)

    visit(tree, None)
    return parents


def should_replace(
    node: ast.Attribute,
    parents: dict[ast.AST, ast.AST | None],
    reserved: set[str],
) -> bool:
    if not isinstance(node.value, ast.Name):
        return False
    if not is_df_like(node.value.id):
        return False
    if node.attr in reserved:
        return False
    parent = parents.get(node)
    if isinstance(parent, ast.Call) and parent.func is node:
        return False
    return True


def transform_source(source: str, path: Path, reserved: set[str]) -> str | None:
    try:
        tree = ast.parse(source)
    except SyntaxError as e:
        print(f"SKIP (syntax): {path}: {e}", file=sys.stderr)
        return None

    parents = build_parents(tree)
    candidates: list[ast.Attribute] = []
    for n in ast.walk(tree):
        if isinstance(n, ast.Attribute) and should_replace(n, parents, reserved):
            candidates.append(n)

    if not candidates:
        return source

    try:
        starts = line_start_offsets(source)
        spans: list[tuple[int, int, str]] = []
        for node in candidates:
            start, end = node_char_span(source, node, starts)
            old = source[start:end]
            base = node.value.id  # type: ignore[union-attr]
            key = node.attr
            new = f'{base}["{key}"]'
            if old != new:
                spans.append((start, end, new))
    except (TypeError, IndexError, AttributeError) as e:
        print(f"SKIP (span): {path}: {e}", file=sys.stderr)
        return None

    spans.sort(key=lambda x: x[0], reverse=True)
    out = source
    for start, end, new in spans:
        out = out[:start] + new + out[end:]
    return out


def main() -> int:
    reserved = dataframe_reserved_names()
    changed = 0
    for path in sorted(ROOT.rglob("*.py")):
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        rel = path.relative_to(ROOT)
        if str(rel).startswith("dev/scripts/dataframe_dot_to_bracket.py"):
            continue
        text = path.read_text(encoding="utf-8")
        new_text = transform_source(text, path, reserved)
        if new_text is None:
            continue
        if new_text != text:
            path.write_text(new_text, encoding="utf-8")
            print(rel)
            changed += 1
    print(f"Updated {changed} file(s).", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
