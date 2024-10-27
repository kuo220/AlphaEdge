import os
import time
import atexit
import pandas as pd
import shioaji as sj
from Crawler import stocklist_crawler
from Utils import API_login, API_logout, set_global_api, stockListU20

# 改使用者名稱(Kuo/Jason)
user = "Jason"

# 設定開始與結束日期
start_date = "2020-04-01"
end_date = "2024-05-10"

stockList = stocklist_crawler()

if len(stockList) == 0:
    print("Stock list is empty, check the crawler.")
else:
    print("Get stock list successfully.")
    print("Len of listed company:",len(stockList))

# make stockListU20 a string list
stockListU20 = [str(i) for i in stockListU20]

if user == "Jason":
    # make stockList drop the stock which market value is over 20e
    stockList = list(set(stockList) - set(stockListU20))

    stockList = sorted(stockList)
    print("Len of listed company:",len(stockList))

    skip_list = ["2603","2609"]
    #skip_list = ["2603","2609","2645","3714","3715","4414","4950","6901","6957"]

elif user == "Kuo":
    stockList = stockListU20
    skip_list = ['2073', '2250', '2254', '2348', '2351', '2390', '2397', \
                 '2415', '2417', '2427', '2428', '2432', '2433', '2434', \
                 '2453', '2465', '2471', '2472', '2483', '2484', '2546', \
                 '2596', '2616', '2753', '2756', '2758', '2941', '2947', \
                 '3015', '3027', '3029', '3043', '3057', '3073', '3093', \
                ]

# Check which stock already in /Tick/
path = "Tick/"

if not os.path.exists(path):
    os.makedirs(path)
    
files = os.listdir(path)
files = [f.replace(".csv","") for f in files]

apiKeySecretDict = API_login()

# Use API_Status_List to record the status of each API
API_Status_List = []

for i in range(len(apiKeySecretDict["key"])):
    API_Status_List.append(True)

atexit.register(API_logout)

for i in range(len(stockList)):

    # if all api status is False, break the loop
    if all(status == False for status in API_Status_List):
        print("All API usage out of limit, break the loop.")
        break

    if stockList[i] in files or stockList[i] in skip_list:
        print("Already in tick, skip this stock.")
        # Skip this stock
        continue

    if API_Status_List[i % len(apiKeySecretDict["key"])] == False:
        print("API usage out of limit, use next account.")
        continue

    print("Use the " + str(i % len(apiKeySecretDict["key"])) + "th account to crawl...")
    api = sj.Shioaji()
    set_global_api(api)
    api.login(api_key=apiKeySecretDict['key'][i % len(apiKeySecretDict["key"])],
              secret_key=apiKeySecretDict['secret'][i % len(apiKeySecretDict["key"])])

    print("This is the", i, "th stock:", stockList[i])

    df_list = []
    empty_data_bit = False
    empty_df_count = 0 
    for date in pd.date_range(start=start_date, end=end_date):
        date = date.strftime("%Y-%m-%d")

        time.sleep(0.11)

        #print every 10 days
        if int(date[-2:]) % 10 == 0:
            print("Try", date)

        try:
            ticks = api.ticks(contract=api.Contracts.Stocks[str(stockList[i])], date=date)

            df = pd.DataFrame({**ticks})
            df.ts = pd.to_datetime(df.ts)

            if int(date[-2:]) % 10 == 0:
                print("Shape of df of the date", df.shape)
            
            # Check if the data is empty
            if df.shape[0] == 0:
                
                empty_data_bit = empty_data_bit and True

                # As the first empty data, set empty_df_count to 1 and empty_data_bit to True
                if empty_data_bit == False:
                    empty_df_count = 1
                    empty_data_bit = True   
                
                # As not the first empty data, add empty_df_count by 1 and left empty_data_bit to be && with True
                else:
                    empty_df_count += 1

                if empty_df_count == 60 and empty_data_bit == True:
                    print("Data is empty for 60 days, check if API is run out.")
                    apiusage_message = api.usage()
                    
                    print(f"API quota:{round(apiusage_message.remaining_bytes/(1024**2),2)}mb.")

                    if apiusage_message.remaining_bytes >= 0:
                        print("API isn't run out, keep crawling")
                        # reset the empty_data_bit/empty_df_count
                        empty_data_bit = False
                        empty_df_count = 0
                    else:
                        print("API is run out, skip this API.")
                        API_Status_List[i % len(apiKeySecretDict["key"])] = False
                        API_logout()
                        break
            # IF the data is not empty, reset empty_df_count and empty_data_bit
            else:
                empty_data_bit = False
                empty_df_count = 0

            df_list.append(df)
        except Exception as e:
            print("Error encountered:", e)

            if "StatusCode: 401, Detail: Token is expired" in str(e):
                print("Token is expired, Logout.")

                API_Status_List[i % len(apiKeySecretDict["key"])] = False

                try:
                    API_logout()
                except Exception as logout_error:
                    print("Logout failed:", logout_error)

                break

            print("Skip this date.")
    
    #Avoid noncomplete dataframe 
    if API_Status_List[i % len(apiKeySecretDict["key"])] == False:
        print("API usage out of limit, use next account.")
        continue

    df_list = [df for df in df_list if df.shape[0] != 0]
    if len(df_list) != 0:
        combined_df = pd.concat(df_list, ignore_index=True)
        combined_df.to_csv(path + str(stockList[i]) + '.csv', index=False)
        print("Save", stockList[i], "successfully.")

    print("Crawler finished, Logout.")
    try:
        API_logout()
    except Exception as logout_error:
        print("Logout failed:", logout_error)