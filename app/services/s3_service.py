import uuid
import boto3
from botocore.exceptions import ClientError

from app.config import settings


def _client():
    return boto3.client(
        "s3",
        region_name=settings.AWS_REGION,
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
    )


def build_s3_key(business_id: uuid.UUID, document_id: uuid.UUID, filename: str) -> str:
    """
    Deterministic S3 key.
    Example: businesses/abc123/knowledge/def456/product_catalogue.pdf
    """
    return f"businesses/{business_id}/knowledge/{document_id}/{filename}"


def generate_presigned_upload_url(
    s3_key: str,
    content_type: str,
    expires_in: int = 300,
) -> str:
    """
    Returns a presigned PUT URL.
    The frontend uploads the file directly to S3 using this URL.
    No file ever passes through your FastAPI server.
    """
    client = _client()
    url = client.generate_presigned_url(
        "put_object",
        Params={
            "Bucket": settings.S3_BUCKET_NAME,
            "Key": s3_key,
            "ContentType": content_type,
        },
        ExpiresIn=expires_in,
    )
    return url


def generate_presigned_download_url(s3_key: str, expires_in: int = 300) -> str:
    """Presigned GET URL — useful for letting users preview uploaded documents."""
    client = _client()
    return client.generate_presigned_url(
        "get_object",
        Params={"Bucket": settings.S3_BUCKET_NAME, "Key": s3_key},
        ExpiresIn=expires_in,
    )


def read_object_bytes(s3_key: str) -> bytes:
    """
    Download the full object into memory.
    Called by the chunking service after upload confirmation.
    50 MB limit is enforced at the schema level so this is safe.
    """
    client = _client()
    response = client.get_object(Bucket=settings.S3_BUCKET_NAME, Key=s3_key)
    return response["Body"].read()


def delete_object(s3_key: str) -> None:
    """Delete an object from S3 when its KnowledgeDocument row is deleted."""
    client = _client()
    try:
        client.delete_object(Bucket=settings.S3_BUCKET_NAME, Key=s3_key)
    except ClientError:
        # Log but don't raise — DB record deletion should still succeed
        pass