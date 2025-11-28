import httpx
from fastmcp import FastMCP

from azure_devops_config import (
    get_base_url,
    get_auth_header,
    AZURE_DEVOPS_ORG,
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
            
    
    @mcp.tool()
    async def assign_contribute_permission(
        project: str,
        repository: str,
        user_email: str,
        user_name: str
    ) -> str:
        """
        Asigna permisos de contribuidor a un usuario en un repositorio de Azure DevOps.
        
        Args:
            project: Nombre del proyecto en Azure DevOps
            repository: Nombre del repositorio
            user_email: Email del usuario al que se le asignarán permisos
            user_name: Nombre completo del usuario
        
        Returns:
            Mensaje indicando el resultado de la operación
        """
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                headers = {"Authorization": get_auth_header()}
                organization = AZURE_DEVOPS_ORG
                
                # ===== 1. Obtener Project ID =====
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
                
                # ===== 2. Obtener Repository ID =====
                repos_url = f"{get_base_url()}/{project}/_apis/git/repositories?api-version={AZURE_DEVOPS_API_VERSION}"
                repos_response = await client.get(repos_url, headers=headers)
                repos_response.raise_for_status()
                repos = repos_response.json()
                
                repo_id = next(
                    (r["id"] for r in repos.get("value", []) if r["name"] == repository),
                    None
                )
                
                if not repo_id:
                    return f"❌ Error: No se encontró el repositorio '{repository}' en el proyecto '{project}'."
                
                # ===== 3. Obtener Security Namespace para Git Repositories =====
                namespaces_url = f"{get_base_url()}/_apis/securitynamespaces?api-version={AZURE_DEVOPS_API_VERSION}"
                namespaces_response = await client.get(namespaces_url, headers=headers)
                namespaces_response.raise_for_status()
                namespaces = namespaces_response.json()
                
                git_namespace = next(
                    (n for n in namespaces.get("value", []) if n["displayName"] == "Git Repositories"),
                    None
                )
                
                if not git_namespace:
                    return "❌ Error: No se encontró el namespace de Git Repositories."
                
                namespace_id_git_repos = git_namespace["namespaceId"]
                contribute_action = next(
                    (a for a in git_namespace["actions"] if a["displayName"] == "Contribute"),
                    None
                )
                
                if not contribute_action:
                    print("❌ Error: No se encontró el permiso 'Contribute")
                    return "❌ Error: No se encontró el permiso 'Contribute'."
                
                contribute_bit = contribute_action["bit"]
                
                # ===== 4. Obtener User Identity =====
                identities_url = (
                    f"https://vssps.dev.azure.com/{organization}/_apis/identities"
                    f"?searchFilter=General&filterValue={user_email}&queryMembership=None&api-version={AZURE_DEVOPS_API_VERSION}"
                )
                user_response = await client.get(identities_url, headers=headers)
                user_response.raise_for_status()
                user_data = user_response.json()
                
                user_descriptor = next(
                    (u["descriptor"] for u in user_data.get("value", [])
                     if u.get("providerDisplayName") == user_name),
                    None
                )
                
                if not user_descriptor:
                    return f"❌ Error: No se encontró el usuario '{user_name}' con email '{user_email}'."
                
                # ===== 5. Asignar Permiso de Contribute =====
                ace_url = (
                    f"{get_base_url()}/_apis/accesscontrolentries/"
                    f"{namespace_id_git_repos}?api-version={AZURE_DEVOPS_API_VERSION}"
                )
                
                body = {
                    "token": f"repoV2/{project_id}/{repo_id}",
                    "merge": True,
                    "accessControlEntries": [
                        {
                            "descriptor": user_descriptor,
                            "allow": contribute_bit,
                            "deny": 0,
                            "extendedInfo": {
                                "effectiveAllow": contribute_bit,
                                "effectiveDeny": 0,
                                "inheritedAllow": contribute_bit,
                                "inheritedDeny": 0
                            }
                        }
                    ]
                }
                
                ace_response = await client.post(
                    ace_url,
                    headers={**headers, "Content-Type": "application/json"},
                    json=body
                )
                ace_response.raise_for_status()
                
                # ===== Resultado exitoso =====
                result = "✅ PERMISO ASIGNADO EXITOSAMENTE\n"
                result += "=" * 80 + "\n\n"
                result += f"👤 Usuario: {user_name} ({user_email})\n"
                result += f"📦 Repositorio: {repository}\n"
                result += f"📁 Proyecto: {project}\n"
                result += f"🔐 Permiso: Contribute\n"
                result += f"🆔 Project ID: {project_id}\n"
                result += f"🆔 Repo ID: {repo_id}\n"
                result += f"🆔 User Descriptor: {user_descriptor}\n\n"
                result += "El usuario ahora puede contribuir al repositorio.\n"
                
                return result
                
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return f"❌ Error 404: Recurso no encontrado. Verifica los nombres del proyecto y repositorio."
            elif e.response.status_code == 401:
                return "❌ Error de autenticación. Verifica tu Personal Access Token (PAT)."
            elif e.response.status_code == 403:
                return f"❌ Error 403: No tienes permisos para asignar permisos en este repositorio."
            else:
                return f"❌ Error HTTP {e.response.status_code}: {e.response.text}"
        except httpx.TimeoutException:
            return "❌ Error: Tiempo de espera agotado al conectar con Azure DevOps."
        except Exception as e:
            return f"❌ Error inesperado: {str(e)}"

    @mcp.tool()
    async def assign_reviewers_policies(
        project: str,
        repository: str,
        branch: str,
        reviewers: int
    ) -> str:
        """
        Asigna la política 'Minimum number of reviewers' en un repositorio Azure DevOps.
        """
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:

                headers = {
                    "Authorization": get_auth_header(),
                    "Content-Type": "application/json"
                }

                # ===== Obtener Project ID =====
                projects_url = f"{get_base_url()}/_apis/projects?api-version={AZURE_DEVOPS_API_VERSION}"
                projects_response = await client.get(projects_url, headers=headers)
                projects_response.raise_for_status()
                project_id = next(
                    (p["id"] for p in projects_response.json().get("value", []) if p["name"] == project),
                    None
                )

                if not project_id:
                    return f"❌ Error: No se encontró el proyecto '{project}'."

                # ===== Obtener Repository ID =====
                repos_url = f"{get_base_url()}/_apis/git/repositories?api-version={AZURE_DEVOPS_API_VERSION}"
                repos_response = await client.get(repos_url, headers=headers)
                repos_response.raise_for_status()
                repo_id = next(
                    (r["id"] for r in repos_response.json().get("value", []) if r["name"] == repository),
                    None
                )

                if not repo_id:
                    return f"❌ Error: No se encontró el repositorio '{repository}'."

                # ===== Obtener ID del tipo de política =====
                policy_types_url = f"{get_base_url()}/{project}/_apis/policy/types?api-version={AZURE_DEVOPS_API_VERSION}"
                policy_types = (await client.get(policy_types_url, headers=headers)).json()["value"]

                reviewer_policy_type_id = next(
                    (t["id"] for t in policy_types if t["displayName"] == "Minimum number of reviewers"),
                    None
                )

                if not reviewer_policy_type_id:
                    return "❌ No se pudo encontrar el tipo de política 'Minimum number of reviewers'."

                # ===== Obtener políticas existentes =====
                policies_url = (
                    f"{get_base_url()}/{project}/_apis/policy/configurations?"
                    f"api-version={AZURE_DEVOPS_API_VERSION}&repositoryId={repo_id}&refName=refs/heads/{branch}"
                )
                policies_response = await client.get(policies_url, headers=headers)
                policies_response.raise_for_status()

                existing_policy = next(
                    (p for p in policies_response.json().get("value", [])
                    if p.get("type", {}).get("id") == reviewer_policy_type_id),
                    None
                )

                existing_policy_id = existing_policy["id"] if existing_policy else None                

                # ===== Crear o actualizar política =====
                body = {
                    "isEnabled": True,
                    "isBlocking": True,
                    "type": {"id": reviewer_policy_type_id},
                    "settings": {
                        "minimumApproverCount": reviewers,
                        "creatorVoteCounts": False,
                        "allowDownvotes": False,
                        "scope": [
                            {
                                "refName": f"refs/heads/{branch}",
                                "repositoryId": repo_id,
                                "matchKind": "Exact"
                            }
                        ]
                    }
                }

                if existing_policy_id:
                    upsert_url = (
                        f"{get_base_url()}/{project}/_apis/policy/configurations/"
                        f"{existing_policy_id}?api-version={AZURE_DEVOPS_API_VERSION}"
                    )
                    upsert_response = await client.put(upsert_url, headers=headers, json=body)

                else:
                    upsert_url = (
                        f"{get_base_url()}/{project}/_apis/policy/configurations"
                        f"?api-version={AZURE_DEVOPS_API_VERSION}"
                    )
                    upsert_response = await client.post(upsert_url, headers=headers, json=body)

                upsert_response.raise_for_status()

                # ===== Resultado =====
                result = "✅ POLÍTICA ASIGNADA EXITOSAMENTE\n"
                result += "=" * 80 + "\n\n"
                result += f"📁 Proyecto: {project}\n"
                result += f"📦 Repositorio: {repository}\n"
                result += f"🔐 Política: Minimum number of reviewers\n"
                result += f"🆔 Project ID: {project_id}\n"
                result += f"🆔 Repo ID: {repo_id}\n"

                return result

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return "❌ 404: Recurso no encontrado."
            if e.response.status_code == 401:
                return "❌ 401: No autorizado. Verifica tu PAT."
            if e.response.status_code == 403:
                return "❌ 403: No tienes permisos."
            return f"❌ Error HTTP {e.response.status_code}: {e.response.text}"

        except httpx.TimeoutException:
            return "❌ Error: Tiempo de espera agotado."

        except Exception as e:
            return f"❌ Error inesperado: {str(e)}"


    @mcp.tool()
    async def create_and_import(
        project: str,
        repository: str,
        repository_url_import: str
    ) -> str:
        """
        Crea e importa un repositorio de Azure DevOps.
        
        Args:
            project: Nombre del proyecto en Azure DevOps.
            repository: Nombre del repositorio a crear.
            repository_url_import: URL del repositorio Git origen (HTTP/HTTPS).
        
        Returns:
            Mensaje indicando el resultado de la operación.
        """
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:

                headers = {
                    "Authorization": get_auth_header(),
                    "Content-Type": "application/json"
                }

                # ===== 1. Buscar el proyecto =====
                projects_url = f"{get_base_url()}/_apis/projects?api-version={AZURE_DEVOPS_API_VERSION}"
                resp = await client.get(projects_url, headers=headers)
                resp.raise_for_status()

                print(f'resp: {resp}')

                projects = resp.json().get("value", [])
                project_id = next((p["id"] for p in projects if p["name"] == project), None)

                print(f'project_id: {project_id}')

                if not project_id:
                    return f"❌ Error: Proyecto '{project}' no encontrado."

                # ===== 2. Verificar si el repositorio ya existe =====
                repos_url = f"{get_base_url()}/_apis/git/repositories?api-version={AZURE_DEVOPS_API_VERSION}"
                resp = await client.get(repos_url, headers=headers)
                resp.raise_for_status()

                

                existing = next((r for r in resp.json().get("value", []) if r["name"] == repository), None)

                if existing:
                    return f"❌ Error: El repositorio '{repository}' ya existe en el proyecto '{project}'."

                # ===== 3. Crear el repositorio vacío =====
                create_body = { "name": repository }

                create_url = f"{get_base_url()}/{project}/_apis/git/repositories?api-version={AZURE_DEVOPS_API_VERSION}"
                resp = await client.post(create_url, headers=headers, json=create_body)
                resp.raise_for_status()

                print(f'resp2: {resp}')

                repo_id = resp.json()["id"]

                print(f'repo_id: {repo_id}')


                # ===== 4. Importar código desde la URL =====
                import_body = {
                    "parameters": {
                        "deleteServiceEndpointAfterImport": True,
                        "gitSource": { 
                            "url": repository_url_import
                        }
                    }
                }

                import_url = f"{get_base_url()}/{project}/_apis/git/repositories/{repo_id}/importRequests?api-version={AZURE_DEVOPS_API_VERSION}"
                
                print(f'import_url: {import_url}')

                resp = await client.post(import_url, headers=headers, json=import_body)
                resp.raise_for_status()

                import_result = resp.json()
                repo_url = import_result["repository"]["remoteUrl"]                

                workitem_id, workitem_url = await create_work_item(
                    client=client,
                    project=project,
                    type="Task",
                    title=f"As a development team member, I want to create a new repository with name {repository} " +
                          f"and import source code from an external location {repository_url_import} so that I can quickly initialize the project — automatically handled by NexusDesk Copilot.",
                    description=f"Request to create a repository {repository} and import source code from an external source",
                    priority=2,
                    state="Done"
                )

                # ===== 5. Éxito =====
                result = (
                    "✅ REPOSITORIO CREADO E IMPORTADO EXITOSAMENTE\n"
                    + "=" * 80 + "\n\n"
                    + f"📁 Proyecto: {project}\n"
                    + f"📦 Repositorio: {repository}\n"
                    + f"🆔 Project ID: {project_id}\n"
                    + f"🆔 Repo ID: {repo_id}\n"
                    + f"🔗 URL Remota: {repo_url}\n"
                    + f"🔗 PBI Remota: {repo_url}\n"
                )

                return result

        # ===== Manejo de Errores =====
        except httpx.HTTPStatusError as e:
            code = e.response.status_code
            msg = e.response.text

            if code == 401:
                return "❌ Error 401: Autenticación fallida. Verifica tu PAT."
            if code == 403:
                return "❌ Error 403: No tienes permisos para crear o importar repositorios."
            if code == 404:
                return "❌ Error 404: Recurso no encontrado. Revisa proyecto o URL de importación."

            return f"❌ Error HTTP {code}: {msg}"

        except httpx.TimeoutException:
            return "❌ Error: Tiempo de espera agotado conectando a Azure DevOps."

        except Exception as e:
            return f"❌ Error inesperado: {str(e)}"
