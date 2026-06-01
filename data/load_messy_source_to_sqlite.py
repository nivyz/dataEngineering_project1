import pandas as pd
import sqlite3
from pathlib import Path

project_root = Path(__file__).resolve().parents[1]

input_file = project_root / "data" / "source" / "train_FD001.txt"
db_file = project_root / "db" / "manufacturing_etl.db"

columns = (
    ["unit", "cycle"]
    + [f"op_setting_{i}" for i in range(1, 4)]
    + [f"sensor_{i}" for i in range(1, 22)]
)

# Read the TXT correctly using one-or-more whitespace
df = pd.read_csv(
    input_file,
    sep=r"\s+",
    header=None,
    names=columns,
    engine="python"
)

# Convert everything to string to simulate messy source typing
df = df.astype(str)

conn = sqlite3.connect(db_file)
cur = conn.cursor()

cur.execute("DROP TABLE IF EXISTS engine_data_raw_source")

create_sql = """
CREATE TABLE engine_data_raw_source (
    unit TEXT,
    cycle TEXT,
    op_setting_1 TEXT,
    op_setting_2 TEXT,
    op_setting_3 TEXT,
    sensor_1 TEXT,
    sensor_2 TEXT,
    sensor_3 TEXT,
    sensor_4 TEXT,
    sensor_5 TEXT,
    sensor_6 TEXT,
    sensor_7 TEXT,
    sensor_8 TEXT,
    sensor_9 TEXT,
    sensor_10 TEXT,
    sensor_11 TEXT,
    sensor_12 TEXT,
    sensor_13 TEXT,
    sensor_14 TEXT,
    sensor_15 TEXT,
    sensor_16 TEXT,
    sensor_17 TEXT,
    sensor_18 TEXT,
    sensor_19 TEXT,
    sensor_20 TEXT,
    sensor_21 TEXT
)
"""
cur.execute(create_sql)

df.to_sql("engine_data_raw_source", conn, if_exists="append", index=False)

# Simple checks
row_count = pd.read_sql("SELECT COUNT(*) AS cnt FROM engine_data_raw_source", conn)
preview = pd.read_sql("SELECT * FROM engine_data_raw_source LIMIT 5", conn)

print("Loaded rows:")
print(row_count)
print("\nPreview:")
print(preview)

conn.close()