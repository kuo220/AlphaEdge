import math
import os
import sqlite3
from datetime import date, datetime, timedelta

import openai
import pandas as pd
import pytz
import requests
import shioaji as sj
import yfinance as yf
from dateutil.relativedelta import relativedelta
from dotenv import load_dotenv
from quantxlab.strategies.quantx_strategy import QuantxStrategy

from .crawler import (
    crawl_benchmark_return,
    crawl_finance_statement_by_date,
    crawl_margin_balance,
    crawl_margin_transactions,
    crawl_monthly_report,
    crawl_price,
    crawl_tw_business_indicator,
    crawl_tw_total_nmi,
    crawl_tw_total_pmi,
    date_range,
    month_range,
    season_range,
    table_latest_date,
    update_table,
)
from .data import Data
from .mysqldb import Mysqldb
from .shared_list import indu, indu_id, stock_not_for_quantx
from .utlis import portfolio

desired_timezone = pytz.timezone("Asia/Taipei")


def crawl_data():
    conn = sqlite3.connect(os.path.join("data", "data.db"))
    fromd = table_latest_date(conn, "price")
    tod = datetime.now(desired_timezone).date()
    # update price table
    dates = date_range(fromd, tod)
    if len(dates) == 0:
        print("price no data to parse")
    else:
        update_table(conn, "price", crawl_price, dates)

    # update monthly revenue table
    fromd = table_latest_date(conn, "monthly_revenue")
    tod = datetime.now(desired_timezone).date()
    if fromd.date() >= tod:
        fromd = fromd - relativedelta(months=1)
        tod = fromd
    # 過了10號還是爬一下上個月的月報
    else:
        fromd = fromd - relativedelta(months=1)
    dates = month_range(fromd, tod)
    if len(dates) == 0:
        print("monthly_revenue no data to parse")
    else:
        update_table(conn, "monthly_revenue", crawl_monthly_report, dates)

    # update seasonal revenue table 季報更新時間就是3/1~4/15, 4/26~5/31, 7/26~8/31, 10/24~11/30
    tod = datetime.now(desired_timezone).date()
    dates = []
    if (tod.month == 4 and 26 <= tod.day <= 30) or (
        tod.month == 5 and 1 <= tod.day <= 31
    ):
        dates = [datetime(tod.year, 5, 15).date()]
    elif (tod.month == 7 and 26 <= tod.day <= 31) or (
        tod.month == 8 and 1 <= tod.day <= 31
    ):
        dates = [datetime(tod.year, 8, 14).date()]
    elif (
        (tod.month == 10 and 24 <= tod.day <= 31)
        or tod.month == 11
        and 1 <= tod.day <= 30
    ):
        dates = [datetime(tod.year, 11, 14).date()]
    elif (
        tod.month == 3 and 1 <= tod.day <= 31 or (tod.month == 4 and 1 <= tod.day <= 15)
    ):
        dates = [datetime(tod.year, 3, 31).date()]
    if len(dates) == 0:
        print("finance_statement no data to parse")
    else:
        update_table(conn, "finance_statement", crawl_finance_statement_by_date, dates)

    # update benchmark_return
    fromd = table_latest_date(conn, "benchmark_return")
    fromd = fromd.replace(day=1)
    tod = datetime.now(desired_timezone).date()
    dates = month_range(fromd, tod)
    if len(dates) == 0:
        print("benchmark_return no data to parse")
    else:
        update_table(conn, "benchmark_return", crawl_benchmark_return, dates)

    # # update tw_total_pmi tw_total_nmi
    # # tw_total_pmi
    # fromd = table_latest_date(conn, "tw_total_pmi")
    # fromd = fromd - relativedelta(months=1)
    # tod = datetime.now(desired_timezone).date()
    # dates = month_range(fromd, tod)
    # if len(dates) == 0:
    #     print('tw_total_pmi no data to parse')
    # else:
    #     update_table(conn, "tw_total_pmi", crawl_tw_total_pmi, dates)
    #
    # # tw_total_nmi
    # fromd = table_latest_date(conn, "tw_total_nmi")
    # fromd = fromd - relativedelta(months=1)
    # tod = datetime.now(desired_timezone).date()
    # dates = month_range(fromd, tod)
    # if len(dates) == 0:
    #     print('tw_total_nmi no data to parse')
    # else:
    #     update_table(conn, "tw_total_nmi", crawl_tw_total_nmi, dates)
    #
    # # update tw_business_indicator
    # fromd = table_latest_date(conn, "tw_business_indicator")
    # fromd = fromd - relativedelta(months=1)
    # tod = datetime.now(desired_timezone).date()
    # dates = month_range(fromd, tod)
    # if len(dates) == 0:
    #     print('tw_business_indicator no data to parse')
    # else:
    #     update_table(conn, "tw_business_indicator", crawl_tw_business_indicator, dates)

    # update margin_balance
    fromd = table_latest_date(conn, "margin_balance")
    tod = datetime.now(desired_timezone).date()
    # update price table
    dates = date_range(fromd, tod)
    if len(dates) == 0:
        print("margin_balance no data to parse")
    else:
        update_table(conn, "margin_balance", crawl_margin_balance, dates)

    # update margin_transactions
    fromd = table_latest_date(conn, "margin_transactions")
    tod = datetime.now(desired_timezone).date()
    # update price table
    dates = date_range(fromd, tod)
    if len(dates) == 0:
        print("margin_transactions no data to parse")
    else:
        update_table(conn, "margin_transactions", crawl_margin_transactions, dates)

    return


def check_crawl_datanum(data: Data):
    price = data.get("price", "收盤價", 1)
    priceLatestDate = price.index[-1]
    priceDataNum = price.shape[1]

    monReport = data.get("monthly_revenue", "上月比較增減(%)", 1)
    monReportNum = monReport.shape[1]
    monReportLatestDate = monReport.index[-1]

    seasonReport = data.get("balance_sheet", "普通股股本", 1)
    seasonReportNum = seasonReport.shape[1]
    seasonReportLatestDate = seasonReport.index[-1]

    return (
        priceLatestDate,
        priceDataNum,
        monReportLatestDate,
        monReportNum,
        seasonReportLatestDate,
        seasonReportNum,
    )


def calculate_account_financial_num(apiLoginList: list) -> dict:
    year = datetime.now(desired_timezone).year

    revenue_holdDays = []

    for m in range(1, 13):
        # if m == 3:
        #     revenue_holdDays.append(date(year, 3, 12))
        #     revenue_holdDays.append(date(year, 4, 1))
        if m == 2:
            revenue_holdDays.append(date(year, 2, 16))
        elif m == 5:
            revenue_holdDays.append(date(year, 5, 16))
        elif m == 8:
            revenue_holdDays.append(date(year, 8, 15))
        elif m == 11:
            revenue_holdDays.append(date(year, 11, 15))
        else:
            revenue_holdDays.append(date(year, m, 11))

    today = datetime.now(desired_timezone).strftime("%Y-%m-%d")
    # turn the today into datetime.date type
    today = datetime.strptime(today, "%Y-%m-%d").date()

    # check which interval of today in monthly_revenue_holdDays
    for i in range(len(revenue_holdDays)):
        if today <= revenue_holdDays[i]:
            begin = revenue_holdDays[i - 1]
            break

    if today > date(year, 12, 11):
        begin = date(year, 12, 11)
    if today <= date(year, 1, 11):
        begin = date(year - 1, 12, 11)

    begin = (begin + timedelta(days=1)).strftime("%Y-%m-%d")

    print("begin: ", begin)

    today = datetime.now(desired_timezone).strftime("%Y-%m-%d")

    accountBalance = 0
    totalCost = 0
    uCost = 0
    uPnl = 0
    rCost = 0
    rPnl = 0
    deliveryPayment = 0

    unRealizeddict = dict()
    realizeddict = dict()

    for api in apiLoginList:
        accountBalance += api.account_balance().acc_balance
        # print("accountBalance: " + str(accountBalance))

        # 購買紀錄
        # .code => stock_id
        # .pnl  => profit and loss
        list_positions = api.list_positions(api.stock_account)

        noRPnl = False
        try:
            rPnl_list = api.list_profit_loss(api.stock_account, begin, today)
            rPnl_list = pd.DataFrame(pnl.__dict__ for pnl in rPnl_list)
            rPnlGrouped = rPnl_list.groupby("code").sum(numeric_only=False)
            rPnlGrouped = rPnlGrouped.reset_index()

        except:
            # set rPnlGrouped to be empty if there is no deliveryPayment
            rPnlGrouped = pd.DataFrame(columns=["code", "quantity", "price", "pnl"])
            noRPnl = True

        # deliveryPayment
        settlements = api.settlements(api.stock_account)

        # T = 1,2 (T+1, T+2)
        for i in range(1, len(settlements)):
            deliveryPayment += settlements[i].amount

        # stock not for quantx deliverpayment ignore
        stock_not_for_quantx_deliverpayment = 0

        # Unrealized PnL
        for position in list_positions:
            if str(position.code) in stock_not_for_quantx:
                continue
            uPnl += position.pnl
            u_position_cost = position.quantity * position.price * 1000
            uCost += u_position_cost
            if str(position.code) not in unRealizeddict:
                unRealizeddict[str(position.code)] = [
                    position.pnl,
                    u_position_cost,
                    position.quantity,
                ]
            else:
                unRealizeddict[str(position.code)][0] += position.pnl
                unRealizeddict[str(position.code)][1] += u_position_cost
                unRealizeddict[str(position.code)][2] += position.quantity

        # Realized PnL
        if not noRPnl:
            for row in rPnlGrouped.iterrows():
                if row[1]["code"] in stock_not_for_quantx:
                    continue
                # 計算買入成本
                r_position_cost = 0
                for each_sell_row in rPnl_list[
                    rPnl_list["code"] == row[1]["code"]
                ].iterrows():
                    profitloss_detail = api.list_profit_loss_detail(
                        api.stock_account, each_sell_row[1]["id"]
                    )
                    for each_detail in profitloss_detail:
                        r_position_cost += each_detail["cost"]
                if str(row[1]["code"]) not in realizeddict:
                    realizeddict[str(row[1]["code"])] = [row[1]["pnl"], r_position_cost]
                else:
                    realizeddict[str(row[1]["code"])][0] += row[1]["pnl"]
                    realizeddict[str(row[1]["code"])][1] += r_position_cost

                rPnl += row[1]["pnl"]
                rCost += r_position_cost

    # 股息還沒正式入帳之前先手寫存在temp_dividend
    temp_dividend = {}
    temp_dividend_sum = 0
    for _, dividend in temp_dividend.items():
        temp_dividend_sum += dividend

    uNetWorth = uPnl + uCost
    totalPnl = uPnl + rPnl
    totalCost = uCost + rCost
    accountBalance = accountBalance + deliveryPayment
    netWorth = uNetWorth + accountBalance

    # remove dNetWorth
    return {
        "netWorth": netWorth,
        "totalPnl": totalPnl,
        "accountBalance": accountBalance,
        "totalCost": totalCost,
        "uNetWorth": uNetWorth,
        "uPnl": uPnl,
        "rPnl": rPnl,
        "unRealizeddict": unRealizeddict,
        "realizeddict": realizeddict,
        "tempDividendSum": temp_dividend_sum,
    }


def re_evaluate_holding(
    apiLoginList: list, date, earlySellMonth, earlySellSeason
) -> str:
    stockListPosition = []
    for api in apiLoginList:
        list_positions = api.list_positions(api.stock_account)
        for position in list_positions:
            if str(position.code) in stock_not_for_quantx:
                continue
            stockListPosition.append(str(position.code))
    params = {
        "earlySellMonth": earlySellMonth,
        "earlySellSeason": earlySellSeason,
        "initial_capital": 1000000,
    }
    strategy = QuantxStrategy(params)
    strategy.update_data_date(date)
    stockListAll = strategy.run()

    if earlySellMonth is True:
        message = "\nReEvaluate Holding based on monthly report: \n"
    if earlySellSeason is True:
        message = "\nReEvaluate Holding based on seasonal report: \n"

    Res = []
    for i in range(len(stockListPosition)):
        try:
            Res.append(
                str(stockListPosition[i])
                + " : "
                + str(stockListAll[stockListPosition[i]])
            )
        except:
            message += "Missing " + str(stockListPosition[i]) + " in reevaluate.\n"

    # sort by value
    Res.sort(key=lambda x: x.split(":")[1], reverse=True)

    for stock in Res:
        message += stock + "\n"

    return message


def net_worth_ds(
    apiLoginList: list, test=True, strategy_id=1, add_dividend=False, linebot=[]
):
    # The walkaround for quantx pool: qx_strategy + kms_strategy
    # if strategy_id == 1:
    #     # qx pool
    #     financial_num_quantx = calculate_account_financial_num(apiLoginList[:-1])
    #     # kms pool
    #     financial_num_kuo = calculate_account_financial_num([apiLoginList[-1]])
    #     kuo_pool_percentage = 2/3
    #     financial_num = dict()
    #     for key, value in financial_num_quantx.items():
    #         if not isinstance(value, dict):
    #             financial_num[key] = financial_num_quantx[key] + math.floor(financial_num_kuo[key] * kuo_pool_percentage)
    #         else:
    #             financial_num[key] = financial_num_quantx[key]
    # else:
    financial_num = calculate_account_financial_num(apiLoginList)

    stock_datas = list()

    message = f"\nUnrealized Pnl:\n"
    message += f"stockId--quantity--netWorth--PnL--PnL(%)\n"

    for k, v in financial_num["unRealizeddict"].items():
        stock_data = {
            "strategy_id": strategy_id,
            "stock_id": k,
            "quantity": v[2],
            "networth": round(v[0] + v[1], 1),
            "pnl": round(v[0], 1),
            "pnl_percentage": round((float(v[0]) / float(v[1])) * 100, 2),
        }
        stock_datas.append(stock_data)
        message += f"{k}: {v[2]}  {round(v[0] + v[1], 1)}  {round(v[0], 1)}  {round((float(v[0]) / float(v[1])) * 100, 2)}%\n"

    message += f"Total Unrealized Pnl: {financial_num['uPnl']}\n"

    message += f"Realized Pnl:\n"
    message += f"stockId--PnL--PnL(%)\n"

    for k, v in financial_num["realizeddict"].items():
        message += (
            f"{k}: {round(v[0], 1)}  {round((float(v[0]) / float(v[1])) * 100, 2)}%\n"
        )

    message += f"Total Realized Pnl: {financial_num['rPnl']}\n"

    totalPnl = financial_num["totalPnl"]

    # new account may have 0 totalCost and 0 netWorth
    if financial_num["totalCost"] != 0:
        roiOfAlgo = round(totalPnl * 100 / financial_num["totalCost"], 2)
    else:
        roiOfAlgo = 0
    if financial_num["netWorth"] != 0:
        roiOfAllFund = round(totalPnl * 100 / (financial_num["netWorth"]), 2)
    else:
        roiOfAllFund = 0
    remainCash = financial_num["accountBalance"]
    if add_dividend:
        tempDividend = financial_num["tempDividendSum"]
    else:
        tempDividend = 0
    netWorth = financial_num["netWorth"] + tempDividend

    message += f"Total Pnl: {totalPnl}\n"
    message += f"ROI of Algo: {roiOfAlgo}%\n"
    message += f"ROI of all fund: {roiOfAllFund}%\n"
    message += f"Remain Cash: {remainCash}\n"
    message += f"Temp dividend: {tempDividend}\n"
    message += f"Net Worth: {netWorth}\n"
    print(message)

    if not test:
        # write data into cloudsql
        strategy_data = [
            {
                "strategy_id": strategy_id,
                "networth": netWorth,
                "unrealized_pnl": financial_num["uPnl"],
                "realized_pnl": financial_num["rPnl"],
                "pnl": totalPnl,
                "roi_algo": roiOfAlgo,
                "roi_fund": roiOfAllFund,
                "remain_cash": financial_num["accountBalance"],
            },
        ]

        mysqldb = Mysqldb()

        mysqldb.insert_strategy_performance(strategy_data)

        mysqldb.insert_trade_record(stock_datas)

        mysqldb.close_connection()

    # linebot notify
    if len(linebot) > 0:
        for token in linebot:
            line_notify_message(token, message)

    # discord bot message
    return message


def line_notify_message(token, msg):
    headers = {
        "Authorization": "Bearer " + token,
        "Content-Type": "application/x-www-form-urlencoded",
    }

    payload = {"message": msg}
    r = requests.post(
        "https://notify-api.line.me/api/notify", headers=headers, params=payload
    )

    return r.status_code


def stock_list_quantx_ds(
    pool: str, apiLoginList: list, investpercentage: float = 0.9, test=True
):
    return_message = list()
    # 策略清單
    earlySellMonth = False
    earlySellSeason = False
    day = datetime.now(desired_timezone).date()
    # 如果是每月的1~9號就採用那個月10號的月報，其餘用上一次的月報
    # 季報也是從季報開出來前20天就採用最新的季報(3/1, 4/26, 7/26, 10/26)，其餘用上一次的季報
    # monthly_revenue early sell
    if 1 <= day.day < 10:
        diff = 10 - day.day
        day += relativedelta(days=diff)
    # early_sell month 可能10號星期五，所以往後推2天也要通知early_sell
    if 1 <= day.day <= 12:
        earlySellMonth = True
    # seasonal_report early sell
    if day.month == 3 and 1 <= day.day < 31:
        day = datetime(day.year, 3, 31).date()
        earlySellSeason = True
    if (day.month == 4 and 26 <= day.day <= 30) or (
        day.month == 5 and 1 <= day.day <= 15
    ):
        day = datetime(day.year, 5, 15).date()
        earlySellSeason = True
    if (day.month == 7 and 26 <= day.day <= 31) or (
        day.month == 8 and 1 <= day.day <= 14
    ):
        day = datetime(day.year, 8, 14).date()
        earlySellSeason = True
    if (day.month == 10 and 24 <= day.day <= 31) or (
        day.month == 11 and 1 <= day.day <= 14
    ):
        day = datetime(day.year, 11, 14).date()
        earlySellSeason = True

    data = Data(day)

    print("Begin...")

    message = "\n{} price data num: {}\n{} monthly report data num: {}\n{} seasonal report data num: {}".format(
        *check_crawl_datanum(data)
    )

    # early sale reevaluate

    if earlySellMonth:
        message += "\nEarly Sell Month\n"
        message += re_evaluate_holding(apiLoginList, day, earlySellMonth, False)
    if earlySellSeason:
        message += "\nEarly Sell Season\n"
        message += re_evaluate_holding(apiLoginList, day, False, earlySellSeason)

    netWorthQuantXPool = calculate_account_financial_num(apiLoginList)["netWorth"]

    # 選股清單
    strategy = QuantxStrategy(params={"initial_capital": netWorthQuantXPool})
    strategy.update_data_date(day)
    stock_list = strategy.run()
    # 要notify的info
    message += (
        "\n" + datetime.now(desired_timezone).strftime("%Y-%m-%d") + "'s stock list:"
    )
    eps = data.get("income_sheet", "基本每股盈餘合計", 1)
    for i in range(len(stock_list)):
        # 計算該產業季報eps開了幾%
        indu_k = eps.reindex(columns=indu_id[indu[str(stock_list.index[i])][1]]).dropna(
            axis=1
        )
        seasonal_report_announcement_percentage = int(
            len(indu_k.T) / len(indu_id[indu[str(stock_list.index[i])][1]]) * 100
        )

        message += (
            "\n"
            + str(i + 1)
            + ". "
            + str(stock_list.index[i])
            + " "
            + str(stock_list[i])
            + " "
            + indu[str(stock_list.index[i])][0]
            + " "
            + indu[str(stock_list.index[i])][1]
            + " SRAP: "
            + str(seasonal_report_announcement_percentage)
            + "%"
        )

    return_message.append(message)

    if pool == "main":
        # QuantX pool
        # 計算可投入資金
        netWorth = netWorthQuantXPool
        invest_money = netWorthQuantXPool
        total_invest_money = netWorthQuantXPool
        pre_total_invest_money = 0
        while total_invest_money <= netWorth:
            p, total_invest_money = portfolio(stock_list.index, invest_money, data)
            if pre_total_invest_money == total_invest_money:
                invest_money += 50000
                continue
            # 要notify的info
            message = "\n" + "下注比例 : {}% : ".format(
                round(total_invest_money / netWorth * 100)
            )

            message += "\n\n" + "networth : " + str(netWorth)

            message += (
                "\n\n" + "actual investing money : " + str(total_invest_money) + "\n\n"
            )

            message += "預計投資部位:"
            for i, v in p.iteritems():
                message += (
                    "\n" + str(i) + " " + indu[str(i)][0] + " 投資 " + str(v) + "張"
                )

            print(message)

            if not test:
                if netWorth * investpercentage < total_invest_money <= netWorth:
                    return_message.append(message)

            print("Done")

            pre_total_invest_money = total_invest_money
            invest_money += 50000
    elif pool == "boyd":
        # boyD pool
        # 計算可投入資金
        netWorth = 800000
        invest_money = netWorth
        total_invest_money = netWorth
        pre_total_invest_money = 0
        while total_invest_money <= 800000:
            p, total_invest_money = portfolio(stock_list.index, invest_money, data)
            if pre_total_invest_money == total_invest_money:
                invest_money += 50000
                continue
            # 要notify的info
            message = "\n" + "下注比例 : {}% : ".format(
                round(total_invest_money / netWorth * 100)
            )

            message += "\n\n" + "networth : " + str(netWorth)

            message += (
                "\n\n" + "actual investing money : " + str(total_invest_money) + "\n\n"
            )

            message += "預計投資部位:"
            for i, v in p.iteritems():
                message += (
                    "\n" + str(i) + " " + indu[str(i)][0] + " 投資 " + str(v) + "張"
                )

            print(message)

            if not test:
                if netWorth * investpercentage < total_invest_money <= netWorth:
                    return_message.append(message)

            print("Done")

            pre_total_invest_money = total_invest_money
            invest_money += 50000

    return return_message


def compare_roi():
    # For getting the ROI of 0050
    today = datetime.today().strftime("%Y-%m-%d")

    end_day = (datetime.today() - timedelta(days=60)).strftime("%Y-%m-%d")

    yf_df = yf.download("0050.TW", start=end_day, end=today)

    # ROI of last week
    today0050 = yf_df.iloc[-1]["Adj Close"]
    last_one_week0050 = yf_df.iloc[-6]["Adj Close"]

    # ROI of last two week
    last_two_week0050 = yf_df.iloc[-11]["Adj Close"]

    # ROI of last three week
    last_three_week0050 = yf_df.iloc[-16]["Adj Close"]

    # ROI of last four week
    last_four_week0050 = yf_df.iloc[-21]["Adj Close"]

    ROI_of_0050_one = round(
        (today0050 - last_one_week0050) * 100 / last_one_week0050, 2
    )
    ROI_of_0050_two = round(
        (today0050 - last_two_week0050) * 100 / last_two_week0050, 2
    )
    ROI_of_0050_three = round(
        (today0050 - last_three_week0050) * 100 / last_three_week0050, 2
    )
    ROI_of_0050_four = round(
        (today0050 - last_four_week0050) * 100 / last_four_week0050, 2
    )

    # For getting the ROI of QuantX
    QX_df = pd.read_csv("ActualPerformance.csv", index_col=0, parse_dates=True)

    try:
        # ROI of today
        todayQX = QX_df.iloc[-1]["net_worth"]
        # ROI of last week
        last_one_weekQX = QX_df.iloc[-6]["net_worth"]
        ROI_of_QX_one = round((todayQX - last_one_weekQX) * 100 / last_one_weekQX, 2)
    except:
        ROI_of_QX_one = "Nan"

    try:
        # ROI of last two week
        last_two_weekQX = QX_df.iloc[-11]["net_worth"]
        ROI_of_QX_two = round((todayQX - last_two_weekQX) * 100 / last_two_weekQX, 2)
    except:
        ROI_of_QX_two = "Nan"

    try:
        # ROI of last three week
        last_three_weekQX = QX_df.iloc[-16]["net_worth"]
        ROI_of_QX_three = round(
            (todayQX - last_three_weekQX) * 100 / last_three_weekQX, 2
        )
    except:
        ROI_of_QX_three = "Nan"

    try:
        # ROI of last four week
        last_four_weekQX = QX_df.iloc[-21]["net_worth"]
        ROI_of_QX_four = round((todayQX - last_four_weekQX) * 100 / last_four_weekQX, 2)
    except:
        ROI_of_QX_four = "Nan"

    return_message = ""
    return_message += "=====QuantX======0050=====\n"
    return_message += (
        "This week:            "
        + str(ROI_of_QX_one)
        + "% v.s. "
        + str(ROI_of_0050_one)
        + "%\n"
    )
    return_message += (
        "Last week:            "
        + str(ROI_of_QX_two)
        + "% v.s. "
        + str(ROI_of_0050_two)
        + "%\n"
    )
    return_message += (
        "Last two week:    "
        + str(ROI_of_QX_three)
        + "% v.s. "
        + str(ROI_of_0050_three)
        + "%\n"
    )
    return_message += (
        "Last three week: "
        + str(ROI_of_QX_four)
        + "% v.s. "
        + str(ROI_of_0050_four)
        + "%\n"
    )

    return return_message


def api_usage_query(apiLoginList: list):
    return_message = ""
    for i, api in enumerate(apiLoginList):
        return_message += f"{str(i)}th account api usage:\n"
        APIusage_message = api.usage()

        return_message += f"Connections:{APIusage_message.connections} "
        return_message += f"Used:{round(APIusage_message.bytes / (1024**2), 2)} mb "
        return_message += (
            f"Limits:{round(APIusage_message.limit_bytes / (1024**2), 2)} mb "
        )
        return_message += (
            f"Remaining:{round(APIusage_message.remaining_bytes / (1024**2), 2)} mb\n"
        )

    return return_message


def generate_trading_report(apiLoginList: list, test=True):
    load_dotenv()
    openai_api_secret = os.getenv("OPENAI_API_SECRET")
    message = net_worth_ds(apiLoginList, test)
    openai.api_key = openai_api_secret
    template = """
    Based on the provided financial data, here's today's trading report for the investor:

    Today's Trading Report
    Unrealized Profit and Loss (PnL) Details:

    Stock 1220: Shows a decline with an unrealized PnL of -$22,652, which is -2.31% of its net worth.
    Stock 2472: Experienced a significant drop, losing -$56,140, which is -6.22% of its net worth.
    Stock 6206: Minor decline with an unrealized PnL of -$12,387, equating to -1.67%.
    Stock 6261: On a positive note, this stock gained $33,612, about 3.76% of its net worth.
    Stock 8182: Also faced a heavy loss of -$62,302, marking -6.6% of its net worth.
    Stock 2109: Slightly positive with a gain of $497, which is 0.29%.
    Stock 2441: Similar to 8182, facing a loss of -$63,034, which is -6.58%.
    Stock 5356: Performed well with a gain of $40,420, or 4.56%.
    Stock 8150: Decreased by -$33,438, equating to -3.74%.
    Stock 1582: Dropped by -$35,129, or -3.9%.
    Total Unrealized PnL: -$210,553.
    Realized Profit and Loss (PnL) Details:

    Stock 6239: Had a significant realized loss of -$105,128, constituting -11.02% of its value.
    Total Realized PnL: -$105,128.
    Overall Financial Performance:

    Total PnL: -$315,681.
    Return on Investment (ROI) of Algorithm: -3.42%.
    ROI of All Funds: -3.48%.
    Remaining Cash: $1,007,206.
    Net Worth: $9,066,233.

    Summary
    Today's trading reflected a challenging market environment with significant losses in several stocks. Although some gains were noted, the overall financial performance resulted in a negative ROI for both the algorithm and the overall funds. Moving forward, a reassessment of the current investment strategy and risk management practices might be necessary to mitigate further losses and enhance returns.
    """

    prompt = f"Here is the template {template}, Please generate today's trading report for the investor on the data: {message}"

    completion = openai.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[
            {
                "role": "user",
                "content": prompt,
            },
        ],
    )
    print(completion.choices[0].message.content)
    return completion.choices[0].message.content
