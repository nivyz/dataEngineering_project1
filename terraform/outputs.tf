output "bucket_name" {
  value = aws_s3_bucket.etl_bucket.bucket
}

output "glue_job_name" {
  value = aws_glue_job.cmapss_transform.name
}


output "cloudwatch_log_group" {
  value = aws_cloudwatch_log_group.glue_logs.name
}