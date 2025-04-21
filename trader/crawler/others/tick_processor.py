import os
from pathlib import Path
from dolphinDB import DolphinDB



if __name__ == '__main__':
    print("* Start save files in database...")
    
    # 設定要處理的目錄
    dir_num = 6
    dir_path = Path.cwd() / 'Tick_dir' / f'Tick_{dir_num}'
    db_path = "dfs://tickDB"
    db_name = "tickDB"
    table_name = "tick"

    # 遍歷目錄中的所有 .csv 文件
    print("Start formatting time...")
    for file in os.listdir(dir_path):
        if file.endswith('.csv'):
            csv_path = str(dir_path / file).replace('\\', '/')
            DolphinDB.format_csv_time_to_microsec(csv_path)
        
    print("Finish formatting time!")
    
    DolphinDB.create_dolphinDB(db_name, table_name)
    db = DolphinDB(db_path, db_name, table_name)
    db.add_all_csv_to_dolphinDB(dir_path)
    
    print(f"Tick_{dir_num}'s csv files have been saved in the database.")
    