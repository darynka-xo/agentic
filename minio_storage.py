"""MinIO storage service for file operations."""

import logging
from datetime import timedelta
from typing import Optional

from minio import Minio
from minio.error import S3Error

from config import get_settings

logger = logging.getLogger(__name__)


class MinioServiceException(Exception):
    """Custom exception for MinIO service errors."""
    
    def __init__(
        self,
        message: str,
        status_code: int = 500,
        details: Optional[dict] = None
    ):
        self.message = message
        self.status_code = status_code
        self.details = details or {}
        super().__init__(self.message)


class MinioStorageService:
    """Service for interacting with MinIO object storage."""

    def __init__(self):
        """
        Initialize MinIO client.
        Uses configuration from settings:
        - MINIO_ENDPOINT: MinIO server endpoint (e.g., "localhost:9000")
        - MINIO_ACCESS_KEY: Access key for authentication
        - MINIO_SECRET_KEY: Secret key for authentication
        - MINIO_BUCKET_NAME: Default bucket name
        - MINIO_SECURE: Use HTTPS (default: False)
        - MINIO_REGION: Optional region
        """
        settings = get_settings()
        
        if not settings.MINIO_ENDPOINT:
            raise MinioServiceException(
                message="MINIO_ENDPOINT must be configured",
                status_code=500
            )

        self.client = Minio(
            settings.MINIO_ENDPOINT,
            access_key=settings.MINIO_ACCESS_KEY or None,
            secret_key=settings.MINIO_SECRET_KEY or None,
            secure=settings.MINIO_SECURE,
            region=settings.MINIO_REGION or None,
        )
        self.bucket_name = settings.MINIO_BUCKET_NAME

        if not self.bucket_name:
            raise MinioServiceException(
                message="MINIO_BUCKET_NAME must be configured",
                status_code=500
            )

        logger.info(
            f"MinIO client initialized: endpoint={settings.MINIO_ENDPOINT}, "
            f"bucket={self.bucket_name}, secure={settings.MINIO_SECURE}"
        )

    def download_file(
            self, object_path: str,
            bucket_name: Optional[str] = None
    ) -> bytes:
        """
        Download a file from MinIO as bytes.

        Args:
            object_path: Path to the object in the bucket
            bucket_name: Optional bucket name override

        Returns:
            bytes: File content as bytes

        Raises:
            MinioServiceException: If file doesn't exist or download fails
        """
        bucket = bucket_name or self.bucket_name

        try:
            logger.info(f"Downloading from MinIO: {bucket}/{object_path}")
            response = self.client.get_object(bucket, object_path)
            try:
                data = response.read()
                logger.info(f"Downloaded {len(data)} bytes from {object_path}")
                return data
            finally:
                response.close()
                response.release_conn()

        except S3Error as exc:
            if exc.code == "NoSuchKey":
                logger.error(f"File not found in MinIO: {bucket}/{object_path}")
                raise MinioServiceException(
                    message=f"File not found: {object_path}",
                    status_code=404,
                    details={"bucket": bucket, "path": object_path}
                )
            elif exc.code in {"NoSuchBucket"}:
                logger.error(f"Bucket not found: {bucket}")
                raise MinioServiceException(
                    message=f"Bucket not found: {bucket}",
                    status_code=404,
                    details={"bucket": bucket}
                )
            elif exc.code in {"AccessDenied", "Forbidden"}:
                logger.error(f"Access denied for {bucket}/{object_path}")
                raise MinioServiceException(
                    message=f"Access denied: {object_path}",
                    status_code=403,
                    details={"bucket": bucket, "path": object_path}
                )
            else:
                logger.error(f"MinIO error downloading {object_path}: {exc}")
                raise MinioServiceException(
                    message=f"Failed to download file: {str(exc)}",
                    status_code=500,
                    details={
                        "bucket": bucket,
                        "path": object_path,
                        "error": str(exc)
                    }
                )

        except Exception as exc:
            logger.error(f"Unexpected error downloading {object_path}: {exc}")
            raise MinioServiceException(
                message=f"Failed to download file: {str(exc)}",
                status_code=500,
                details={"bucket": bucket, "path": object_path}
            )

    def file_exists(
            self, object_path: str,
            bucket_name: Optional[str] = None
    ) -> bool:
        """
        Check if a file exists in MinIO.

        Args:
            object_path: Path to the object in the bucket
            bucket_name: Optional bucket name override

        Returns:
            bool: True if file exists, False otherwise
        """
        bucket = bucket_name or self.bucket_name

        try:
            self.client.stat_object(bucket, object_path)
            return True
        except S3Error as exc:
            if exc.code in {"NoSuchKey", "NoSuchBucket"}:
                return False
            logger.error(f"Error checking file existence: {exc}")
            return False
        except Exception as exc:
            logger.error(f"Unexpected error checking file existence: {exc}")
            return False

    def generate_presigned_url(
        self,
        object_path: str,
        expiration_minutes: int = 60,
        bucket_name: Optional[str] = None
    ) -> str:
        """
        Generate a presigned URL for temporary access to a file.

        Args:
            object_path: Path to the object in the bucket
            expiration_minutes: URL expiration time in minutes (default: 60)
            bucket_name: Optional bucket name override

        Returns:
            str: Presigned URL

        Raises:
            MinioServiceException: If URL generation fails
        """
        bucket = bucket_name or self.bucket_name

        try:
            url = self.client.get_presigned_url(
                method="GET",
                bucket_name=bucket,
                object_name=object_path,
                expires=timedelta(minutes=expiration_minutes),
            )
            logger.info(
                f"Generated presigned URL for {object_path}, "
                f"expires in {expiration_minutes}m"
            )
            return url
        except Exception as exc:
            logger.error(f"Failed to generate presigned URL: {exc}")
            raise MinioServiceException(
                message=f"Failed to generate presigned URL: {str(exc)}",
                status_code=500,
                details={"bucket": bucket, "path": object_path}
            )


# Singleton instance
_minio_service: Optional[MinioStorageService] = None


def get_minio_storage_service() -> MinioStorageService:
    """
    Get or create the MinIO storage service singleton.

    Returns:
        MinioStorageService: Initialized MinIO storage service

    Raises:
        MinioServiceException: If MinIO is not properly configured
    """
    global _minio_service
    if _minio_service is None:
        _minio_service = MinioStorageService()
    return _minio_service


def is_minio_configured() -> bool:
    """
    Check if MinIO is properly configured.
    
    Returns:
        bool: True if MinIO is configured, False otherwise
    """
    settings = get_settings()
    return bool(settings.MINIO_ENDPOINT and settings.MINIO_BUCKET_NAME)


