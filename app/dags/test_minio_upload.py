from airflow import DAG
from airflow.providers.amazon.aws.hooks.s3 import S3Hook
from airflow.operators.python import PythonOperator
from datetime import datetime

def upload_to_minio():
    hook = S3Hook(aws_conn_id='minio_conn')
    hook.load_string(
        string_data="Hello from Airflow to MinIO!",
        key="test-folder/hello.txt",
        bucket_name="etl-bucket",  # đảm bảo đã tạo trong MinIO
        replace=True
    )

with DAG(
    dag_id="test_minio_upload",
    start_date=datetime(2024, 1, 1),
    schedule_interval=None,
    catchup=False
) as dag:
    upload = PythonOperator(
        task_id="upload_task",
        python_callable=upload_to_minio
    )

    upload