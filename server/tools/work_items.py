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

    @mcp.tool()
    async def create_work_items(
        project: str,
        type: str,
        title: str,
        description: str,
        priority: int
    ) -> str:
        """
        Crear un Work Item en Azure DevOps.

        Args:
            project: Nombre del proyecto
            type: Tipo de Work Item (ej: "Product Backlog Item", "Task", "Bug")
            title: Título del Work Item
            description: Descripción del Work Item
            priority: Prioridad (1-4)

        Returns:
            Mensaje indicando el resultado de la operación
        """
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:

                headers = {
                    "Authorization": get_auth_header(),
                    "Content-Type": "application/json-patch+json"
                }

                # ===== Obtener Project ID =====
                projects_url = f"{get_base_url()}/_apis/projects?api-version={AZURE_DEVOPS_API_VERSION}"
                projects_response = await client.get(projects_url, headers=headers)
                projects_response.raise_for_status()
                projects = projects_response.json()

                project_id = next(
                    (p["id"] for p in projects.get("value", []) if p["name"] == project),
                    None
                )

                if not project_id:
                    return f"❌ Error: No se encontró el proyecto '{project}'."

                # ===== Body del Work Item =====
                body = [
                    {
                        "op": "add",
                        "path": "/fields/System.Title",
                        "from": None,
                        "value": title
                    },
                    {
                        "op": "add",
                        "path": "/fields/System.Description",
                        "from": None,
                        "value": description
                    },
                    {
                        "op": "add",
                        "path": "/fields/Microsoft.VSTS.Common.Priority",
                        "value": priority
                    }
                ]

                work_item_url = (
                    f"{get_base_url()}/{project}/_apis/wit/workitems/${type}"
                    f"?api-version=7.1"
                )

                workitem_response = await client.post(
                    work_item_url,
                    headers=headers,
                    json=body
                )
                workitem_response.raise_for_status()
                workitem = workitem_response.json()

                workitem_id = workitem.get("id")
                workitem_url = workitem.get("url")

                # ===== Resultado =====
                result = "✅ WORK ITEM CREADO EXITOSAMENTE\n"
                result += "=" * 80 + "\n\n"
                result += f"📁 Proyecto: {project}\n"
                result += f"📝 Tipo: {type}\n"
                result += f"🆔 Project ID: {project_id}\n"
                result += f"🆔 Work Item ID: {workitem_id}\n"
                result += f"🔗 URL Work Item: {workitem_url}\n"

                return result

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return f"❌ Error 404: No se encontró el recurso o el tipo de Work Item '{type}'."
            elif e.response.status_code == 401:
                return "❌ Error 401: No autorizado. Revisa tu PAT."
            elif e.response.status_code == 403:
                return "❌ Error 403: No tienes permisos para crear Work Items."
            else:
                return f"❌ Error HTTP {e.response.status_code}: {e.response.text}"

        except httpx.TimeoutException:
            return "❌ Error: Tiempo de espera agotado al conectar con Azure DevOps."

        except Exception as e:
            return f"❌ Error inesperado: {str(e)}"
