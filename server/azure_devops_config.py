import os
import base64
from dotenv import load_dotenv

load_dotenv()

AZURE_DEVOPS_ORG = os.getenv("AZURE_DEVOPS_ORGANIZATION")
AZURE_DEVOPS_PAT = os.getenv("AZURE_DEVOPS_PAT")
AZURE_DEVOPS_API_VERSION = "7.1"


def get_auth_header() -> str:
    """Genera el header de autenticación para Azure DevOps."""
    credentials = f":{AZURE_DEVOPS_PAT}"
    encoded = base64.b64encode(credentials.encode()).decode()
    return f"Basic {encoded}"


def get_base_url() -> str:
    """Retorna la URL base de la API de Azure DevOps."""
    return f"https://dev.azure.com/{AZURE_DEVOPS_ORG}"