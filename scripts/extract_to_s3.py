import sqlite3
from pathlib import Path
import pandas as pd
import boto3

DB_PATH = Path("../manufacturing_etl.db")
TABLE_NAME = "train_FD001"

LOCAL_OUTPUT = Path("../output/train_fd001_raw.csv")

BUCKET_NAME = "cmapss-etl-2026-xyz123"
S3_KEY = "raw/train_fd001_raw.csv"


def main():
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query(f"SELECT * FROM {TABLE_NAME}", conn)
    conn.close()

    LOCAL_OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(LOCAL_OUTPUT, index=False)

    s3 = boto3.client("s3")
    s3.upload_file(str(LOCAL_OUTPUT), BUCKET_NAME, S3_KEY)

    print(f"Rows extracted: {len(df)}")
    print(f"Uploaded to s3://{BUCKET_NAME}/{S3_KEY}")


if __name__ == "__main__":
    main()