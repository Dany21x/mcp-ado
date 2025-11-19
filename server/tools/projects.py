import httpx
from fastmcp import FastMCP

from azure_devops_config import (
    get_base_url,
    get_auth_header,
    AZURE_DEVOPS_API_VERSION,
)

def register_project_tools(mcp: FastMCP) -> None:
    @mcp.tool()
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
