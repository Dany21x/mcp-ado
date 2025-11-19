# tools/work_items.py
import httpx
from fastmcp import FastMCP
from typing import Optional

from azure_devops_config import (
    get_base_url,
    get_auth_header,
    AZURE_DEVOPS_API_VERSION,
)

def register_work_item_tools(mcp: FastMCP) -> None:
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
