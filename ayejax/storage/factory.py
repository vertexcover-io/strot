import boto3
from botocore.client import Config

from .interface import LogStorageInterface
from .s3 import S3LogStorage
from .state import StateStorageFactory


class LogStorageFactory:
    """Factory for creating log storage instances."""
    
    @staticmethod
    def create_s3_storage(
        endpoint_url: str,
        access_key_id: str,
        secret_access_key: str,
        region_name: str = "us-east-1",
        state_backend: str = "memory",
        **kwargs
    ) -> LogStorageInterface:
        """Create S3-compatible log storage instance."""
        
        # Create S3 client
        s3_client = boto3.client(
            's3',
            endpoint_url=endpoint_url,
            aws_access_key_id=access_key_id,
            aws_secret_access_key=secret_access_key,
            region_name=region_name,
            config=Config(signature_version='s3v4')
        )
        
        # Create state storage
        state_storage = StateStorageFactory.create_storage(state_backend, **kwargs)
        
        return S3LogStorage(s3_client, state_storage)
    
    @staticmethod
    def create_storage(backend_type: str, **kwargs) -> LogStorageInterface:
        """Create log storage instance based on backend type."""
        if backend_type == "s3":
            return LogStorageFactory.create_s3_storage(**kwargs)
        else:
            raise ValueError(f"Unknown backend type: {backend_type}")