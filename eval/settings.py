from typing import Annotated, Literal

from pydantic import UrlConstraints
from pydantic_settings import BaseSettings

WebSocketUrl = Annotated[str, UrlConstraints(allowed_schemes={"ws", "wss"})]


class EnvSettings(BaseSettings):
    model_config = {"env_prefix": "STROT_"}

    # API Configuration
    API_BASE_URL: str = "http://localhost:1337"
    """Base URL for the strot API"""

    # Local evaluation configuration
    BROWSER_MODE_OR_WS_URL: Literal["headed", "headless"] | WebSocketUrl = "headed"
    """Either 'headed' | 'headless' or a ws://|wss:// WebSocket URL"""

    # AWS S3 Configuration
    AWS_ACCESS_KEY_ID: str = "strot-user"
    AWS_SECRET_ACCESS_KEY: str = "secretpassword"
    AWS_REGION: str = "us-east-1"
    AWS_S3_ENDPOINT_URL: str = "http://localhost:9000"
    AWS_S3_LOG_BUCKET: str = "job-logs"

    # Airtable Configuration
    AIRTABLE_TOKEN: str
    """Airtable Personal Access Token"""

    AIRTABLE_BASE_ID: str
    """Airtable base ID (starts with 'app...')"""

    AIRTABLE_METRICS_TABLE: str = "metrics"
    """Name of the evaluation metrics table in Airtable"""

    AIRTABLE_ANALYSIS_STEPS_TABLE: str = "analysis_steps"
    """Name of the analysis steps table in Airtable"""

    AIRTABLE_REQUEST_DETECTION_TABLE: str = "request_detection_eval"
    """Name of the request detection evaluation table in Airtable"""

    AIRTABLE_PAGINATION_DETECTION_TABLE: str = "pagination_detection_eval"
    """Name of the pagination detection evaluation table in Airtable"""

    AIRTABLE_CODE_GENERATION_TABLE: str = "code_generation_eval"
    """Name of the code generation evaluation table in Airtable"""


env_settings = EnvSettings()
