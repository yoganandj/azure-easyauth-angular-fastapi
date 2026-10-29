"""Root entrypoint for Azure App Service.

Allows both `uvicorn main:app` and `uvicorn app.main:app` to work seamlessly.
"""

from app.main import app

__all__ = ["app"]
