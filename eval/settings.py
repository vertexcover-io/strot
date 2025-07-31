from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    model_config = {"env_prefix": "STROT_"}

    # API Configuration
    API_BASE_URL: str = "http://localhost:1337"
    """Base URL for the strot API"""

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

    AIRTABLE_OVERVIEW_TABLE: str = "overview"
    """Name of the overview table in Airtable"""

    AIRTABLE_ANALYSIS_STEPS_TABLE: str = "analysis_steps"
    """Name of the analysis steps table in Airtable"""


settings = Settings()
