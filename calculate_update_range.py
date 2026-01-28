#!/usr/bin/env python3
"""
計算在給定的 API quota 限制下，可以更新多少天的券商分點統計資料
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


def calculate_update_range(
    start_date: datetime.date, api_quota_per_hour: int = 20000, buffer: int = 100
) -> None:
    """
    計算在給定的 API quota 限制下，可以更新多少天的資料

    Args:
        start_date: 開始日期
        api_quota_per_hour: 每小時 API quota（預設 20000）
        buffer: 保留的 quota 緩衝（預設 100）
    """
    print("=" * 80)
    print("券商分點統計資料更新範圍計算")
    print("=" * 80)

    # 連接資料庫
    if not Path(DB_PATH).exists():
        print(f"❌ 資料庫不存在: {DB_PATH}")
        print("請先更新 stock_info 和 broker_info 資料")
        return

    conn = sqlite3.connect(DB_PATH)

    # 取得股票和券商數量（過濾權證）
    stock_count = get_stock_count(conn, filter_warrants=True)
    stock_count_all = get_stock_count(conn, filter_warrants=False)
    trader_count = get_trader_count(conn)

    conn.close()

    if stock_count == 0 or trader_count == 0:
        print(f"❌ 資料庫中沒有股票或券商資料")
        print(f"   股票數量: {stock_count}")
        print(f"   券商數量: {trader_count}")
        print("請先執行以下命令更新資料：")
        print("  python -m tasks.update_db --target stock_info broker_info")
        return

    print(f"\n📊 資料庫統計：")
    print(f"   股票數量（過濾權證後）: {stock_count:,} 檔")
    print(f"   股票數量（含權證）: {stock_count_all:,} 檔")
    print(f"   券商數量: {trader_count:,} 家")

    # 計算每個日期需要的 API 調用次數
    api_calls_per_date = stock_count * trader_count
    print(f"\n📈 每個日期需要的 API 調用次數：")
    print(
        f"   {stock_count:,} 股票 × {trader_count:,} 券商 = {api_calls_per_date:,} 次/天"
    )

    # 計算可用的 quota（扣除緩衝）
    available_quota = api_quota_per_hour - buffer
    print(f"\n💰 API Quota 設定：")
    print(f"   每小時 quota: {api_quota_per_hour:,} 次")
    print(f"   保留緩衝: {buffer} 次")
    print(f"   可用 quota: {available_quota:,} 次/小時")

    # 計算從 start_date 到今天的總天數（提前計算，後面會用到）
    today = datetime.date.today()
    total_days = (today - start_date).days

    # 計算每小時可以更新多少天
    days_per_hour = available_quota / api_calls_per_date
    print(f"\n⏱️  每小時可更新天數：")
    print(
        f"   {available_quota:,} 次 ÷ {api_calls_per_date:,} 次/天 = {days_per_hour:.4f} 天/小時"
    )

    if days_per_hour < 1:
        # 如果每小時無法完成一天，計算需要多少小時才能完成一天
        hours_per_day = api_calls_per_date / available_quota
        print(f"   ⚠️  每小時無法完成一天，需要 {hours_per_day:.2f} 小時才能完成一天")

        # 計算在 1 小時內可以更新到哪個日期
        # 假設從 start_date 開始，在 1 小時內可以更新多少個組合
        combinations_per_hour = available_quota
        dates_per_hour = combinations_per_hour / (stock_count * trader_count)

        if dates_per_hour < 1:
            # 連一天都無法完成，計算可以完成多少比例的日期
            progress_per_hour = dates_per_hour
            print(f"\n📅 更新進度估算（1 小時內）：")
            print(f"   可以完成 {progress_per_hour * 100:.2f}% 的一天資料")
            print(
                f"   從 {start_date.strftime('%Y-%m-%d')} 開始，1 小時內仍停留在同一天"
            )
            print(f"   建議：分批更新，每次更新部分股票或券商")

            # 計算如果每天更新 1 小時，需要多少天
            days_needed_for_one_day = hours_per_day
            print(f"\n⏱️  如果每天更新 1 小時：")
            print(
                f"   完成 1 天的資料需要 {days_needed_for_one_day:.1f} 天（每天更新 1 小時）"
            )
            print(
                f"   完成全部 {total_days:,} 天需要 {total_days * days_needed_for_one_day:.1f} 天（每天更新 1 小時）"
            )

            # 計算 1 小時內可以更新多少股票-券商組合
            combinations_per_hour = available_quota
            print(f"\n📊 1 小時內可更新的組合數：")
            print(f"   可以更新 {combinations_per_hour:,} 個股票-券商組合")
            print(f"   約 {combinations_per_hour / stock_count:.1f} 檔股票 × 所有券商")
            print(
                f"   或約 {combinations_per_hour / trader_count:.1f} 家券商 × 所有股票"
            )

            # 提供實用建議
            print(f"\n💡 實用建議：")
            print(f"   由於每小時只能完成 1% 的一天資料，建議：")
            print(f"   1. 先更新最近 3 個月的資料（約 60 個交易日）")
            print(f"   2. 然後逐步回溯更新歷史資料")
            print(f"   3. 程式會自動追蹤進度，可以中斷後繼續")
            print(f"   4. 或者考慮只更新特定股票或券商（修改程式碼）")
    else:
        # 每小時可以完成多天
        end_date = start_date + datetime.timedelta(days=int(days_per_hour))
        print(f"\n📅 建議更新範圍（1 小時內）：")
        print(f"   開始日期: {start_date.strftime('%Y-%m-%d')}")
        print(
            f"   結束日期: {end_date.strftime('%Y-%m-%d')} (約 {days_per_hour:.2f} 天)"
        )
    print(f"\n📆 總更新範圍：")
    print(f"   從 {start_date.strftime('%Y-%m-%d')} 到 {today.strftime('%Y-%m-%d')}")
    print(f"   總共需要更新: {total_days:,} 天")

    # 計算總共需要的 API 調用次數
    total_api_calls = total_days * api_calls_per_date
    print(f"\n🔢 總 API 調用次數估算：")
    print(
        f"   {total_days:,} 天 × {api_calls_per_date:,} 次/天 = {total_api_calls:,} 次"
    )

    # 計算需要多少小時
    if days_per_hour > 0:
        total_hours = total_days / days_per_hour
    else:
        total_hours = (total_days * api_calls_per_date) / available_quota

    # 轉換為更易讀的時間單位
    total_days_needed = total_hours / 24
    total_weeks_needed = total_days_needed / 7
    total_months_needed = total_days_needed / 30
    total_years_needed = total_days_needed / 365

    print(
        f"\n⏰ 完成全部更新所需時間（從 {start_date.strftime('%Y-%m-%d')} 到 {today.strftime('%Y-%m-%d')}）："
    )
    if days_per_hour > 0:
        print(
            f"   {total_days:,} 天 ÷ {days_per_hour:.4f} 天/小時 = {total_hours:,.1f} 小時"
        )
    else:
        print(
            f"   {total_api_calls:,} 次 ÷ {available_quota:,} 次/小時 = {total_hours:,.1f} 小時"
        )
    print(f"\n   換算為其他時間單位：")
    print(f"   • {total_hours:,.1f} 小時")
    print(f"   • {total_days_needed:,.1f} 天")
    print(f"   • {total_weeks_needed:,.1f} 週（約 {total_weeks_needed / 4:.1f} 個月）")
    print(
        f"   • {total_months_needed:,.1f} 個月（約 {total_months_needed / 12:.1f} 年）"
    )
    print(f"   • {total_years_needed:,.1f} 年")
    print(f"\n   ⚠️  假設連續運行，不間斷使用 API quota")

    print("\n" + "=" * 80)
    print("💡 建議：")
    print("   1. 由於更新量很大，建議分批進行")
    print("   2. 可以先更新最近幾個月的資料（例如最近 3 個月）")
    print("   3. 然後再逐步回溯更新歷史資料")
    print("   4. 程式會自動追蹤已更新的日期，可以中斷後繼續")
    print("=" * 80)


if __name__ == "__main__":
    start_date = datetime.date(2021, 6, 30)
    calculate_update_range(start_date, api_quota_per_hour=20000, buffer=100)
