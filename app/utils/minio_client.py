from minio import Minio
from minio.error import S3Error
from config import Config
import logging
from datetime import timedelta

logger = logging.getLogger(__name__)

def get_minio_client():
    return Minio(
        Config.MINIO_ENDPOINT,
        access_key=Config.MINIO_ACCESS_KEY,
        secret_key=Config.MINIO_SECRET_KEY,
        secure=False
    )

def ensure_bucket():
    client = get_minio_client()
    try:
        if not client.bucket_exists(Config.MINIO_BUCKET):
            client.make_bucket(Config.MINIO_BUCKET)
            logger.info(f"Created bucket {Config.MINIO_BUCKET}")
        else:
            logger.debug(f"Bucket {Config.MINIO_BUCKET} already exists")
    except S3Error as e:
        logger.error(f"Failed to ensure bucket {Config.MINIO_BUCKET}: {e}")
        raise

def upload_to_minio(file, filename):
    ensure_bucket()  # Đảm bảo bucket tồn tại
    client = get_minio_client()
    try:
        file.seek(0)
        client.put_object(
            Config.MINIO_BUCKET,
            filename,
            file,
            length=-1,
            part_size=10*1024*1024
        )
        logger.debug(f"Uploaded {filename} to MinIO")
    except S3Error as e:
        logger.error(f"Failed to upload {filename} to MinIO: {e}")
        raise

def list_user_files(user_id):
    ensure_bucket()  # Đảm bảo bucket tồn tại
    client = get_minio_client()
    try:
        objects = client.list_objects(
            Config.MINIO_BUCKET,
            prefix=f"{user_id}/",
            recursive=True
        )
        files = [
            {
                'name': obj.object_name,
                'size': obj.size,
                'last_modified': obj.last_modified
            }
            for obj in objects
        ]
        logger.debug(f"Listed {len(files)} files for user {user_id}")
        return files
    except S3Error as e:
        logger.error(f"Failed to list files for user {user_id}: {e}")
        raise

def generate_download_url(filename, expires=3600):
    client = get_minio_client()
    try:
        url = client.presigned_get_object(
            Config.MINIO_BUCKET,
            filename,
            expires=timedelta(seconds=expires)
        )
        logger.debug(f"Generated download URL for {filename}")
        return url
    except S3Error as e:
        logger.error(f"Failed to generate download URL for {filename}: {e}")
        raise