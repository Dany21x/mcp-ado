"""
Azure DevOps MCP Server
Servidor principal que registra todas las herramientas MCP
"""

import os
from fastmcp import FastMCP
import httpx
from dotenv import load_dotenv
import base64
from typing import Optional

# Importar todas las tools
'''
from tools.projects import register_project_tools
from tools.work_items import register_work_item_tools
from tools.boards import register_board_tools
'''

# Cargar variables de entorno
load_dotenv()

# Configuración de Azure DevOps
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


# Crear servidor MCP
mcp = FastMCP(
    name="Azure DevOps Server",
    on_duplicate_tools="error")


@mcp.tool
async def list_projects() -> str:
    """
    Lista todos los proyectos en la organización de Azure DevOps.

    Returns:
        JSON string con la lista de proyectos
    """
    url = f"{get_base_url()}/_apis/projects?api-version={AZURE_DEVOPS_API_VERSION}"

    async with httpx.AsyncClient() as client:
        response = await client.get(
            url,
            headers={"Authorization": get_auth_header()}
        )
        response.raise_for_status()
        data = response.json()

        projects = data.get("value", [])
        result = "Proyectos encontrados:\n\n"
        for project in projects:
            result += f"- {project['name']} (ID: {project['id']})\n"
            result += f"  Estado: {project['state']}\n"
            result += f"  URL: {project['url']}\n\n"

        return result


@mcp.tool()
async def get_work_items(
        project: str,
        work_item_type: Optional[str] = None,
        state: Optional[str] = None,
        assigned_to: Optional[str] = None,
        max_results: int = 50
) -> str:
    """
    Busca work items en un proyecto de Azure DevOps.

    Args:
        project: Nombre del proyecto
        work_item_type: Tipo de work item (Bug, Task, User Story, etc.)
        state: Estado del work item (New, Active, Resolved, Closed, etc.)
        assigned_to: Email o nombre del asignado
        max_results: Número máximo de resultados a retornar

    Returns:
        JSON string con los work items encontrados
    """
    # Construir la consulta WIQL (Work Item Query Language)
    query = f"SELECT [System.Id], [System.Title], [System.State], [System.AssignedTo] FROM WorkItems WHERE [System.TeamProject] = '{project}'"

    if work_item_type:
        query += f" AND [System.WorkItemType] = '{work_item_type}'"

    if state:
        query += f" AND [System.State] = '{state}'"

    if assigned_to:
        query += f" AND [System.AssignedTo] = '{assigned_to}'"

    url = f"{get_base_url()}/{project}/_apis/wit/wiql?api-version={AZURE_DEVOPS_API_VERSION}"

    async with httpx.AsyncClient() as client:
        # Ejecutar la consulta
        response = await client.post(
            url,
            headers={
                "Authorization": get_auth_header(),
                "Content-Type": "application/json"
            },
            json={"query": query}
        )
        response.raise_for_status()
        data = response.json()

        work_items = data.get("workItems", [])[:max_results]

        if not work_items:
            return "No se encontraron work items con los criterios especificados."

        # Obtener detalles de los work items
        ids = [str(wi["id"]) for wi in work_items]
        details_url = f"{get_base_url()}/{project}/_apis/wit/workitems?ids={','.join(ids)}&api-version={AZURE_DEVOPS_API_VERSION}"

        details_response = await client.get(
            details_url,
            headers={"Authorization": get_auth_header()}
        )
        details_response.raise_for_status()
        details_data = details_response.json()

        result = f"Work Items encontrados ({len(work_items)}):\n\n"
        for item in details_data.get("value", []):
            fields = item.get("fields", {})
            result += f"ID: {item['id']}\n"
            result += f"Tipo: {fields.get('System.WorkItemType', 'N/A')}\n"
            result += f"Título: {fields.get('System.Title', 'N/A')}\n"
            result += f"Estado: {fields.get('System.State', 'N/A')}\n"
            result += f"Asignado a: {fields.get('System.AssignedTo', {}).get('displayName', 'Sin asignar')}\n"
            result += f"URL: {item.get('_links', {}).get('html', {}).get('href', 'N/A')}\n\n"

        return result


if __name__ == "__main__":
    # Verificar que las credenciales estén configuradas
    if not AZURE_DEVOPS_ORG or not AZURE_DEVOPS_PAT:
        print("Error: AZURE_DEVOPS_ORGANIZATION y AZURE_DEVOPS_PAT deben estar configurados en el archivo .env")
        exit(1)

    print(f"Iniciando Azure DevOps MCP Server para la organización: {AZURE_DEVOPS_ORG}")
    mcp.run(transport="http", port=8000)