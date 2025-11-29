"""
Azure DevOps MCP Server
Servidor principal que registra todas las herramientas MCP
"""

from fastmcp import FastMCP

from azure_devops_config import AZURE_DEVOPS_ORG, AZURE_DEVOPS_PAT
from tools.repositories import register_repository_tools
from tools.work_items import register_work_item_tools
from tools.projects import register_project_tools
from tools.pipelines import register_pipeline_tools

# Crear servidor MCP
mcp = FastMCP(
    name="Azure DevOps Server",
    on_duplicate_tools="error",
)

# Registrar tools desde los módulos
register_repository_tools(mcp)
register_work_item_tools(mcp)
register_project_tools(mcp)
register_pipeline_tools(mcp)

if __name__ == "__main__":
    if not AZURE_DEVOPS_ORG or not AZURE_DEVOPS_PAT:
        print(
            "Error: AZURE_DEVOPS_ORGANIZATION y AZURE_DEVOPS_PAT deben "
            "estar configurados en el archivo .env"
        )
        raise SystemExit(1)

    print(
        f"Iniciando Azure DevOps MCP Server para la organización: "
        f"{AZURE_DEVOPS_ORG}"
    )
    mcp.run(transport="http", port=8001)
