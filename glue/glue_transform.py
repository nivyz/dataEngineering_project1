import sys
from awsglue.utils import getResolvedOptions
from pyspark.sql import SparkSession
from pyspark.sql.functions import col, max as spark_max, avg, when
from pyspark.sql.window import Window

args = getResolvedOptions(
    sys.argv,
    ["RAW_S3_PATH", "PROCESSED_S3_PATH"]
)

raw_s3_path = args["RAW_S3_PATH"]
processed_s3_path = args["PROCESSED_S3_PATH"]

spark = SparkSession.builder.appName("CMAPSS Glue ETL").getOrCreate()

print("Starting Glue transformation")
print(f"Reading raw data from: {raw_s3_path}")

df = spark.read.option("header", "true").csv(raw_s3_path)

expected_columns = (
    ["engine_id", "cycle", "op_setting_1", "op_setting_2", "op_setting_3"]
    + [f"sensor_{i}" for i in range(1, 22)]
)

df = df.select(df.columns[:26])

for old_col, new_col in zip(df.columns, expected_columns):
    df = df.withColumnRenamed(old_col, new_col)

for c in expected_columns:
    df = df.withColumn(c, col(c).cast("double"))

df = df.dropDuplicates().dropna()

df = df.withColumn("engine_id", col("engine_id").cast("int"))
df = df.withColumn("cycle", col("cycle").cast("int"))

engine_window = Window.partitionBy("engine_id")
df = df.withColumn("max_cycle", spark_max("cycle").over(engine_window))
df = df.withColumn("rul", col("max_cycle") - col("cycle"))

fact_engine_cycles = df.select(
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
    "sensor_21"
)

summary = df.groupBy("engine_id").agg(
    spark_max("cycle").alias("total_cycles"),
    avg("sensor_2").alias("avg_sensor_2"),
    avg("sensor_3").alias("avg_sensor_3"),
    avg("sensor_4").alias("avg_sensor_4"),
    avg("sensor_11").alias("avg_sensor_11"),
    avg("sensor_12").alias("avg_sensor_12"),
    avg("sensor_15").alias("avg_sensor_15"),
    avg("sensor_20").alias("avg_sensor_20"),
    avg("sensor_21").alias("avg_sensor_21")
)

quantiles = summary.approxQuantile("total_cycles", [0.33, 0.66], 0.01)
q1 = quantiles[0]
q2 = quantiles[1]

summary = summary.withColumn(
    "health_bucket",
    when(col("total_cycles") <= q1, "critical")
    .when(col("total_cycles") <= q2, "warning")
    .otherwise("healthy")
)

summary = summary.withColumn(
    "anomaly_flag",
    when(col("total_cycles") <= q1, 1).otherwise(0)
)

print("Writing processed outputs")

summary.coalesce(1).write.mode("overwrite").option("header", "true").csv(
    processed_s3_path + "engine_health_summary/"
)

fact_engine_cycles.coalesce(1).write.mode("overwrite").option("header", "true").csv(
    processed_s3_path + "fact_engine_cycles/"
)

print("Glue transformation completed successfully")
print(f"Summary rows: {summary.count()}")
print(f"Fact rows: {fact_engine_cycles.count()}")