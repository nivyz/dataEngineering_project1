from pathlib import Path
import pandas as pd
import boto3
import time

# ---------- CONFIG ----------
BUCKET_NAME = "cmapss-etl-2026-xyz123"

RAW_S3_KEY = "raw/train_fd001_raw.csv"
LOCAL_RAW = Path("../output/train_fd001_raw.csv")
LOCAL_PROCESSED = Path("../output/engine_health_summary.csv")
LOCAL_CYCLE_FACT = Path("../output/fact_engine_cycles.csv")

PROCESSED_S3_KEY = "processed/engine_health_summary.csv"
FACT_S3_KEY = "processed/fact_engine_cycles.csv"

LOG_GROUP = "/etl/cmapss"
LOG_STREAM = "local-etl-run"
# ----------------------------


def cloudwatch_log(message: str):
    logs = boto3.client("logs")

    response = logs.describe_log_streams(
        logGroupName=LOG_GROUP,
        logStreamNamePrefix=LOG_STREAM
    )

    streams = response.get("logStreams", [])
    token = streams[0].get("uploadSequenceToken") if streams else None

    event = {
        "timestamp": int(time.time() * 1000),
        "message": message
    }

    kwargs = {
        "logGroupName": LOG_GROUP,
        "logStreamName": LOG_STREAM,
        "logEvents": [event]
    }

    if token:
        kwargs["sequenceToken"] = token

    logs.put_log_events(**kwargs)


def main():
    print("Starting transformation...")
    cloudwatch_log("Starting transformation")

    s3 = boto3.client("s3")

    # Download raw from S3 to local
    s3.download_file(BUCKET_NAME, RAW_S3_KEY, str(LOCAL_RAW))

    df = pd.read_csv(LOCAL_RAW)

    # Rename columns if imported as field1, field2...
    expected_columns = (
        ["engine_id", "cycle", "op_setting_1", "op_setting_2", "op_setting_3"]
        + [f"sensor_{i}" for i in range(1, 22)]
    )

    if len(df.columns) >= 26:
        df = df.iloc[:, :26]
        df.columns = expected_columns

    # Basic cleanup
    df = df.drop_duplicates()
    df = df.dropna()

    # Make sure numeric columns are numeric
    for col in df.columns:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    df = df.dropna()

    # Calculate RUL
    max_cycle = df.groupby("engine_id")["cycle"].max().reset_index()
    max_cycle.columns = ["engine_id", "max_cycle"]

    df = df.merge(max_cycle, on="engine_id", how="left")
    df["rul"] = df["max_cycle"] - df["cycle"]

    # Fact table: cycle-level analytics data
    fact_engine_cycles = df[
        [
            "engine_id",
            "cycle",
            "rul",
            "sensor_2",
            "sensor_3",
            "sensor_4",
            "sensor_7",
            "sensor_11",
            "sensor_12",
            "sensor_15",
            "sensor_20",
            "sensor_21",
        ]
    ]

    # Engine-level model / summary table
    summary = df.groupby("engine_id").agg(
        total_cycles=("cycle", "max"),
        avg_sensor_2=("sensor_2", "mean"),
        avg_sensor_3=("sensor_3", "mean"),
        avg_sensor_4=("sensor_4", "mean"),
        avg_sensor_11=("sensor_11", "mean"),
        avg_sensor_12=("sensor_12", "mean"),
        avg_sensor_15=("sensor_15", "mean"),
        avg_sensor_20=("sensor_20", "mean"),
        avg_sensor_21=("sensor_21", "mean"),
    ).reset_index()

    # Simple health bucket based on total lifecycle length
    q1 = summary["total_cycles"].quantile(0.33)
    q2 = summary["total_cycles"].quantile(0.66)

    def health_bucket(cycles):
        if cycles <= q1:
            return "healthy"
        elif cycles <= q2:
            return "warning"
        else:
            return "critical"

    summary["health_bucket"] = summary["total_cycles"].apply(health_bucket)

    # Save local outputs
    LOCAL_PROCESSED.parent.mkdir(parents=True, exist_ok=True)
    summary.to_csv(LOCAL_PROCESSED, index=False)
    fact_engine_cycles.to_csv(LOCAL_CYCLE_FACT, index=False)

    # Upload processed outputs
    s3.upload_file(str(LOCAL_PROCESSED), BUCKET_NAME, PROCESSED_S3_KEY)
    s3.upload_file(str(LOCAL_CYCLE_FACT), BUCKET_NAME, FACT_S3_KEY)

    print("Transformation complete.")
    print(f"Processed summary rows: {len(summary)}")
    print(f"Fact table rows: {len(fact_engine_cycles)}")

    cloudwatch_log(f"Transformation complete. Summary rows: {len(summary)}")
    cloudwatch_log(f"Uploaded processed files to s3://{BUCKET_NAME}/processed/")


if __name__ == "__main__":
    main()