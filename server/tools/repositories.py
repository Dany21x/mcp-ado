import httpx
from fastmcp import FastMCP

from azure_devops_config import (
    get_base_url,
    get_auth_header,
    AZURE_DEVOPS_API_VERSION,
)

def register_repository_tools(mcp: FastMCP) -> None:

    @mcp.tool()
    async def list_repositories(project: str) -> str:
        """
        Lista todos los repositorios Git en un proyecto de Azure DevOps.
        
        Args:
            project: Nombre del proyecto en Azure DevOps
        
        Returns:
            Lista formateada con información de los repositorios
        """
        url = f"{get_base_url()}/{project}/_apis/git/repositories?api-version={AZURE_DEVOPS_API_VERSION}"
        
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    url,
                    headers={"Authorization": get_auth_header()}
                )
                response.raise_for_status()
                data = response.json()
                
                repositories = data.get("value", [])
                
                if not repositories:
                    return f"No se encontraron repositorios en el proyecto '{project}'."
                
                result = f"📁 REPOSITORIOS EN '{project}'\n"
                result += "=" * 80 + "\n\n"
                result += f"Total de repositorios: {len(repositories)}\n\n"
                
                for repo in repositories:
                    result += f"📦 {repo['name']}\n"
                    result += f"   🆔 ID: {repo['id']}\n"
                    result += f"   🌐 URL: {repo['url']}\n"
                    result += f"   🔗 Web URL: {repo.get('webUrl', 'N/A')}\n"
                    result += f"   📊 Tamaño: {repo.get('size', 0)} bytes\n"
                    
                    # Información de la rama por defecto
                    default_branch = repo.get('defaultBranch', 'N/A')
                    if default_branch != 'N/A' and default_branch.startswith('refs/heads/'):
                        default_branch = default_branch.replace('refs/heads/', '')
                    result += f"   🌿 Rama por defecto: {default_branch}\n"
                    
                    # Estado del repositorio
                    is_disabled = repo.get('isDisabled', False)
                    status = "❌ Deshabilitado" if is_disabled else "✅ Activo"
                    result += f"   📌 Estado: {status}\n"
                    
                    result += "\n"
                
                return result
                
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 404:
                    return f"❌ Error: No se encontró el proyecto '{project}'. Verifica que el nombre sea correcto."
                elif e.response.status_code == 401:
                    return "❌ Error de autenticación. Verifica tu Personal Access Token (PAT)."
                elif e.response.status_code == 403:
                    return f"❌ Error: No tienes permisos para acceder a los repositorios del proyecto '{project}'."
                else:
                    return f"❌ Error HTTP {e.response.status_code}: {str(e)}"
            except Exception as e:
                return f"❌ Error inesperado: {str(e)}"