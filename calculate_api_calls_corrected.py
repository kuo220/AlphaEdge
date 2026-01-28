#!/usr/bin/env python3
"""
重新計算 API 調用次數（考慮 API 可以一次調用取得日期區間）
"""
import datetime
import sqlite3
from pathlib import Path

from trader.config import (
    DB_PATH,
    SECURITIES_TRADER_INFO_TABLE_NAME,
    STOCK_INFO_WITH_WARRANT_TABLE_NAME,
)
from trader.utils.instrument import StockUtils


def get_stock_count(conn: sqlite3.Connection, filter_warrants: bool = True) -> int:
    """取得股票數量（可選：過濾權證）"""
    try:
        query = f"SELECT DISTINCT stock_id FROM {STOCK_INFO_WITH_WARRANT_TABLE_NAME}"
        cursor = conn.cursor()
        cursor.execute(query)
        all_stock_ids = [row[0] for row in cursor.fetchall()]

        if filter_warrants:
            # 過濾出一般股票（排除權證、ETF等）
            filtered_stocks = StockUtils.filter_common_stocks(all_stock_ids)
            return len(filtered_stocks)
        else:
            return len(all_stock_ids)
    except Exception as e:
        print(f"❌ 查詢股票數量時發生錯誤: {e}")
        return 0


def get_trader_count(conn: sqlite3.Connection) -> int:
    """取得券商數量"""
    try:
        query = f"SELECT COUNT(DISTINCT securities_trader_id) FROM {SECURITIES_TRADER_INFO_TABLE_NAME}"
        cursor = conn.cursor()
        cursor.execute(query)
        count = cursor.fetchone()[0]
        return count
    except Exception as e:
        print(f"❌ 查詢券商數量時發生錯誤: {e}")
        return 0


def calculate_api_calls_corrected(
    start_date: datetime.date,
    end_date: datetime.date = None,
    api_quota_per_hour: int = 20000,
    buffer: int = 100,
) -> None:
    """
    重新計算 API 調用次數（考慮 API 可以一次調用取得日期區間）

    Args:
        start_date: 開始日期
        end_date: 結束日期（預設為今天）
        api_quota_per_hour: 每個 API 每小時的 quota（預設 20000）
        buffer: 保留的 quota 緩衝（預設 100）
    """
    print("=" * 80)
    print("重新計算 API 調用次數（API 可一次取得日期區間）")
    print("=" * 80)

    if end_date is None:
        end_date = datetime.date.today()

    # 連接資料庫
    if not Path(DB_PATH).exists():
        print(f"❌ 資料庫不存在: {DB_PATH}")
        print("請先更新 stock_info 和 broker_info 資料")
        return

    conn = sqlite3.connect(DB_PATH)

    # 取得股票和券商數量（過濾權證）
    stock_count = get_stock_count(conn, filter_warrants=True)
    trader_count = get_trader_count(conn)

    conn.close()

    if stock_count == 0 or trader_count == 0:
        print(f"❌ 資料庫中沒有股票或券商資料")
        return

    print(f"\n📊 資料庫統計：")
    print(f"   股票數量（過濾權證後）: {stock_count:,} 檔")
    print(f"   券商數量: {trader_count:,} 家")

    # 計算總天數
    total_days = (end_date - start_date).days
    print(f"\n📆 更新範圍：")
    print(f"   從 {start_date.strftime('%Y-%m-%d')} 到 {end_date.strftime('%Y-%m-%d')}")
    print(f"   總共需要更新: {total_days:,} 天")

    # 重要：API 可以一次調用取得整個日期區間
    # 所以每個股票-券商組合只需要 1 次 API 調用
    total_api_calls = stock_count * trader_count
    print(f"\n📈 API 調用次數計算（修正後）：")
    print(f"   每個股票-券商組合需要 1 次 API 調用（可取得整個日期區間）")
    print(
        f"   總 API 調用次數 = {stock_count:,} 股票 × {trader_count:,} 券商 = {total_api_calls:,} 次"
    )
    print(
        f"\n   ⚠️  注意：這與日期範圍無關！無論是 1 天還是 1,672 天，都是 {total_api_calls:,} 次調用"
    )

    # 計算可用的 quota（扣除緩衝）
    available_quota_per_api = api_quota_per_hour - buffer
    print(f"\n💰 每個 API 的 Quota 設定：")
    print(f"   每小時 quota: {api_quota_per_hour:,} 次")
    print(f"   保留緩衝: {buffer} 次")
    print(f"   可用 quota: {available_quota_per_api:,} 次/小時")

    # 計算需要多少小時
    hours_needed = total_api_calls / available_quota_per_api
    days_needed = hours_needed / 24
    weeks_needed = days_needed / 7
    months_needed = days_needed / 30
    years_needed = days_needed / 365

    print(f"\n⏰ 使用 1 個 API 完成全部更新所需時間：")
    print(
        f"   {total_api_calls:,} 次 ÷ {available_quota_per_api:,} 次/小時 = {hours_needed:,.1f} 小時"
    )
    print(f"\n   換算為其他時間單位：")
    print(f"   • {hours_needed:,.1f} 小時")
    print(f"   • {days_needed:,.1f} 天")
    print(f"   • {weeks_needed:,.1f} 週（約 {weeks_needed / 4:.1f} 個月）")
    print(f"   • {months_needed:,.1f} 個月（約 {months_needed / 12:.1f} 年）")
    print(f"   • {years_needed:.2f} 年")

    # 計算不同 API 數量所需的時間
    print(f"\n" + "=" * 80)
    print("📊 不同 API 數量所需的完成時間：")
    print("=" * 80)

    api_counts = [1, 5, 10, 20, 50, 100, 200, 500, 1000]
    for num_apis in api_counts:
        total_quota_per_hour = num_apis * available_quota_per_api
        hours_needed = total_api_calls / total_quota_per_hour
        days_needed = hours_needed / 24
        weeks_needed = days_needed / 7
        months_needed = days_needed / 30

        print(f"\n{num_apis} 個 API：")
        print(f"   總 quota: {total_quota_per_hour:,} 次/小時")
        print(
            f"   完成時間: {hours_needed:,.1f} 小時 ({days_needed:,.1f} 天, {weeks_needed:,.1f} 週, {months_needed:,.1f} 個月)"
        )

    # 反向計算：給定完成時間，需要多少 API
    print(f"\n" + "=" * 80)
    print("📊 不同完成時間所需的 API 數量：")
    print("=" * 80)

    target_times = [
        ("1 小時", 1),
        ("1 天", 24),
        ("7 天", 24 * 7),
        ("30 天", 24 * 30),
        ("90 天", 24 * 90),
        ("1 年", 24 * 365),
    ]

    for time_name, hours in target_times:
        api_needed = total_api_calls / (available_quota_per_api * hours)
        print(f"\n{time_name}內完成：")
        print(f"   需要 {api_needed:,.0f} 個 API")
        if api_needed < 1:
            print(f"   ⚠️  即使只有 1 個 API 也能在 {time_name}內完成！")

    print("\n" + "=" * 80)
    print("💡 重要發現：")
    print("   1. API 可以一次調用取得整個日期區間，所以總調用次數與日期範圍無關")
    print(
        "   2. 只需要 {:,} 次 API 調用就能完成從 {} 到 {} 的所有資料".format(
            total_api_calls,
            start_date.strftime("%Y-%m-%d"),
            end_date.strftime("%Y-%m-%d"),
        )
    )
    single_api_hours = total_api_calls / available_quota_per_api
    single_api_days = single_api_hours / 24
    print(
        "   3. 使用 1 個 API 需要約 {:.1f} 小時（{:.1f} 天）".format(
            single_api_hours, single_api_days
        )
    )
    print("=" * 80)


if __name__ == "__main__":
    start_date = datetime.date(2021, 6, 30)
    calculate_api_calls_corrected(start_date)
