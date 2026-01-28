#!/usr/bin/env python3
"""
計算需要多少個 API 才能完成券商分點統計資料更新
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


def calculate_api_needed(
    start_date: datetime.date,
    target_completion_days: float = None,
    target_completion_hours: float = None,
    api_quota_per_hour: int = 20000,
    buffer: int = 100,
) -> None:
    """
    計算需要多少個 API 才能完成更新

    Args:
        start_date: 開始日期
        target_completion_days: 目標完成天數（例如：30 天內完成）
        target_completion_hours: 目標完成小時數（例如：720 小時內完成）
        api_quota_per_hour: 每個 API 每小時的 quota（預設 20000）
        buffer: 保留的 quota 緩衝（預設 100）
    """
    print("=" * 80)
    print("計算需要多少個 API 才能完成券商分點統計資料更新")
    print("=" * 80)

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

    # 計算每個日期需要的 API 調用次數
    api_calls_per_date = stock_count * trader_count
    print(f"\n📈 每個日期需要的 API 調用次數：")
    print(
        f"   {stock_count:,} 股票 × {trader_count:,} 券商 = {api_calls_per_date:,} 次/天"
    )

    # 計算可用的 quota（扣除緩衝）
    available_quota_per_api = api_quota_per_hour - buffer
    print(f"\n💰 每個 API 的 Quota 設定：")
    print(f"   每小時 quota: {api_quota_per_hour:,} 次")
    print(f"   保留緩衝: {buffer} 次")
    print(f"   可用 quota: {available_quota_per_api:,} 次/小時")

    # 計算從 start_date 到今天的總天數
    today = datetime.date.today()
    total_days = (today - start_date).days
    total_api_calls = total_days * api_calls_per_date

    print(f"\n📆 更新範圍：")
    print(f"   從 {start_date.strftime('%Y-%m-%d')} 到 {today.strftime('%Y-%m-%d')}")
    print(f"   總共需要更新: {total_days:,} 天")
    print(f"   總 API 調用次數: {total_api_calls:,} 次")

    # 計算不同場景下需要的 API 數量
    print(f"\n" + "=" * 80)
    print("📊 不同完成時間所需的 API 數量：")
    print("=" * 80)

    # 場景 1: 1 天內完成
    hours_in_1_day = 24
    api_needed_1_day = (total_api_calls / available_quota_per_api) / hours_in_1_day
    print(f"\n1️⃣  1 天內完成：")
    print(f"   需要 {api_needed_1_day:,.0f} 個 API")
    print(f"   每個 API 每小時調用 {available_quota_per_api:,} 次")
    print(
        f"   總共 {api_needed_1_day * available_quota_per_api * hours_in_1_day:,.0f} 次/小時"
    )

    # 場景 2: 7 天內完成
    hours_in_7_days = 24 * 7
    api_needed_7_days = (total_api_calls / available_quota_per_api) / hours_in_7_days
    print(f"\n2️⃣  7 天內完成：")
    print(f"   需要 {api_needed_7_days:,.0f} 個 API")
    print(f"   每個 API 每小時調用 {available_quota_per_api:,} 次")
    print(
        f"   總共 {api_needed_7_days * available_quota_per_api * hours_in_7_days:,.0f} 次/7天"
    )

    # 場景 3: 30 天內完成
    hours_in_30_days = 24 * 30
    api_needed_30_days = (total_api_calls / available_quota_per_api) / hours_in_30_days
    print(f"\n3️⃣  30 天內完成：")
    print(f"   需要 {api_needed_30_days:,.0f} 個 API")
    print(f"   每個 API 每小時調用 {available_quota_per_api:,} 次")
    print(
        f"   總共 {api_needed_30_days * available_quota_per_api * hours_in_30_days:,.0f} 次/30天"
    )

    # 場景 4: 90 天內完成
    hours_in_90_days = 24 * 90
    api_needed_90_days = (total_api_calls / available_quota_per_api) / hours_in_90_days
    print(f"\n4️⃣  90 天內完成：")
    print(f"   需要 {api_needed_90_days:,.0f} 個 API")
    print(f"   每個 API 每小時調用 {available_quota_per_api:,} 次")
    print(
        f"   總共 {api_needed_90_days * available_quota_per_api * hours_in_90_days:,.0f} 次/90天"
    )

    # 場景 5: 1 年內完成
    hours_in_1_year = 24 * 365
    api_needed_1_year = (total_api_calls / available_quota_per_api) / hours_in_1_year
    print(f"\n5️⃣  1 年內完成：")
    print(f"   需要 {api_needed_1_year:,.0f} 個 API")
    print(f"   每個 API 每小時調用 {available_quota_per_api:,} 次")
    print(
        f"   總共 {api_needed_1_year * available_quota_per_api * hours_in_1_year:,.0f} 次/年"
    )

    # 如果指定了目標完成時間
    if target_completion_days is not None:
        hours_in_target = 24 * target_completion_days
        api_needed = (total_api_calls / available_quota_per_api) / hours_in_target
        print(f"\n🎯 自訂目標：{target_completion_days} 天內完成：")
        print(f"   需要 {api_needed:,.0f} 個 API")
        print(f"   每個 API 每小時調用 {available_quota_per_api:,} 次")

    if target_completion_hours is not None:
        api_needed = (
            total_api_calls / available_quota_per_api
        ) / target_completion_hours
        print(f"\n🎯 自訂目標：{target_completion_hours} 小時內完成：")
        print(f"   需要 {api_needed:,.0f} 個 API")
        print(f"   每個 API 每小時調用 {available_quota_per_api:,} 次")

    # 反向計算：給定 API 數量，需要多少時間
    print(f"\n" + "=" * 80)
    print("📊 給定 API 數量，完成時間估算：")
    print("=" * 80)

    api_counts = [1, 5, 10, 20, 50, 100, 200, 500, 1000]
    for num_apis in api_counts:
        total_quota_per_hour = num_apis * available_quota_per_api
        days_per_hour = total_quota_per_hour / api_calls_per_date
        if days_per_hour > 0:
            hours_needed = total_days / days_per_hour
            days_needed = hours_needed / 24
            weeks_needed = days_needed / 7
            months_needed = days_needed / 30
            years_needed = days_needed / 365

            print(f"\n{num_apis} 個 API：")
            print(f"   總 quota: {total_quota_per_hour:,} 次/小時")
            print(f"   每小時可完成: {days_per_hour:.4f} 天")
            print(
                f"   完成時間: {hours_needed:,.1f} 小時 ({days_needed:,.1f} 天, {weeks_needed:,.1f} 週, {months_needed:,.1f} 個月, {years_needed:.1f} 年)"
            )
        else:
            print(f"\n{num_apis} 個 API：")
            print(f"   總 quota: {total_quota_per_hour:,} 次/小時")
            print(f"   每小時可完成: {days_per_hour:.4f} 天（仍無法完成一天）")

    print("\n" + "=" * 80)
    print("💡 注意事項：")
    print("   1. 以上計算假設所有 API 可以並行運行")
    print("   2. 實際時間可能因網路延遲、錯誤重試等因素而增加")
    print("   3. 建議保留一些 quota 緩衝，避免超過限制")
    print("=" * 80)


if __name__ == "__main__":
    start_date = datetime.date(2021, 6, 30)
    calculate_api_needed(start_date)
