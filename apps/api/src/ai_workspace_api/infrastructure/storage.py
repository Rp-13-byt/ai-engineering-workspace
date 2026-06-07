from pathlib import Path

import boto3

from ai_workspace_api.core.config import Settings


class ObjectStorage:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.client = boto3.client(
            "s3",
            endpoint_url=settings.s3_endpoint_url,
            aws_access_key_id=settings.s3_access_key_id,
            aws_secret_access_key=settings.s3_secret_access_key.get_secret_value(),
        )

    def put_text(self, key: str, content: str, content_type: str = "text/plain") -> None:
        self.client.put_object(
            Bucket=self.settings.s3_bucket,
            Key=key,
            Body=content.encode("utf-8"),
            ContentType=content_type,
        )

    def upload_file(self, path: Path, key: str, content_type: str = "application/octet-stream") -> None:
        self.client.upload_file(
            str(path),
            self.settings.s3_bucket,
            key,
            ExtraArgs={"ContentType": content_type},
        )
