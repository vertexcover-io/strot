from typing import Annotated

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from ayejax._interface.api.settings import settings

security = HTTPBearer()
security_dependency = Depends(security)


def authenticate(credentials: HTTPAuthorizationCredentials = security_dependency):
    """Verify the API key from the Authorization header"""
    if credentials.credentials != settings.API_KEY:
        raise HTTPException(status_code=403, detail="Invalid API key")

    return credentials.credentials


AuthDependency = Annotated[str, Depends(authenticate)]
