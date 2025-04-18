# class Config:
#     SECRET_KEY = 'your-secret-key'
#     SQLALCHEMY_DATABASE_URI = 'mysql+pymysql://user:password@localhost:3306/etl_db'
#     SQLALCHEMY_TRACK_MODIFICATIONS = False
#
#     MINIO_ENDPOINT = 'localhost:9000'
#     MINIO_ACCESS_KEY = 'minioadmin'
#     MINIO_SECRET_KEY = 'minioadmin'
#     MINIO_BUCKET = 'etl-bucket'
#
#     AIRFLOW_API_URL = 'http://localhost:8080/api/v1'
#     AIRFLOW_API_TOKEN = 'your-airflow-api-token'

class Config:
    SECRET_KEY = '9bc2600042fbb567a5e8d4f6a7819f0790d7a38baf7d993f'
    SQLALCHEMY_DATABASE_URI = 'mysql+pymysql://user:password@localhost:3306/etl_db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    MINIO_ENDPOINT = 'localhost:9000'
    MINIO_ACCESS_KEY = 'minioadmin'
    MINIO_SECRET_KEY = 'minioadmin'
    MINIO_BUCKET = 'etl-bucket'

    AIRFLOW_API_URL = 'http://localhost:8080/api/v1'