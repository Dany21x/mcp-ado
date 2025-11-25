# tools/pipelines.py
import time
import httpx
from fastmcp import FastMCP

mcp = FastMCP()

# -------------------------------------------------------------------
# 1. Crear y ejecutar el pipeline
# -------------------------------------------------------------------
@mcp.tool()
async def create_and_run_pipeline(
    project: str,
    repository: str,
    pipeline_name: str,
    branch: str
) -> dict:
    """
    Crea (si no existe) y ejecuta un pipeline YAML en Azure DevOps.
    Retorna pipeline_id y run_id para consultar luego el estado.
    """
    try:
        headers = {
            "Authorization": get_auth_header(),
            "Content-Type": "application/json"
        }

        async with httpx.AsyncClient(timeout=None) as client:

            # ===== Obtener Project ID =====
            projects_url = f"{get_base_url()}/_apis/projects?api-version={AZURE_DEVOPS_API_VERSION}"
            res = await client.get(projects_url, headers=headers)
            res.raise_for_status()
            project_id = next(
                (p["id"] for p in res.json().get("value", []) if p["name"] == project),
                None
            )
            if not project_id:
                return {"error": f"No se encontró el proyecto '{project}'"}

            # ===== Obtener Repository ID =====
            repos_url = f"{get_base_url()}/{project}/_apis/git/repositories?api-version={AZURE_DEVOPS_API_VERSION}"
            res = await client.get(repos_url, headers=headers)
            res.raise_for_status()
            repo_id = next(
                (r["id"] for r in res.json().get("value", []) if r["name"] == repository),
                None
            )
            if not repo_id:
                return {"error": f"No se encontró el repositorio '{repository}'"}

            # ===== Crear pipeline =====
            create_url = f"{get_base_url()}/_apis/pipelines?api-version={AZURE_DEVOPS_API_VERSION}"
            create_body = {
                "name": pipeline_name,
                "configuration": {
                    "type": "yaml",
                    "path": ".azure-pipelines/ci.yml",
                    "repository": {"id": repo_id, "type": "azureReposGit"}
                }
            }
            res = await client.post(create_url, headers=headers, json=create_body)
            res.raise_for_status()
            pipeline_id = res.json().get("id")

            # ===== Ejecutar pipeline =====
            run_url = f"{get_base_url()}/_apis/pipelines/{pipeline_id}/runs?api-version={AZURE_DEVOPS_API_VERSION}"
            run_body = {
                "resources": {
                    "repositories": {
                        "self": {"refName": f"refs/heads/{branch}"}
                    }
                }
            }
            res = await client.post(run_url, headers=headers, json=run_body)
            res.raise_for_status()
            run_id = res.json().get("id")

            return {
                "pipeline_id": pipeline_id,
                "run_id": run_id,
                "message": "Pipeline creado y ejecutado exitosamente"
            }

    except Exception as ex:
        return {"error": str(ex)}


# -------------------------------------------------------------------
# 2. Consultar estado del run
# -------------------------------------------------------------------
@mcp.tool()
async def get_pipeline_run_status(
    pipeline_id: int,
    run_id: int
) -> dict:
    """
    Obtiene el estado actual del run (en ejecución, completado, fallado, etc.)
    """
    try:
        headers = {"Authorization": get_auth_header()}
        async with httpx.AsyncClient() as client:

            url = f"{get_base_url()}/_apis/pipelines/{pipeline_id}/runs/{run_id}?api-version={AZURE_DEVOPS_API_VERSION}"
            res = await client.get(url, headers=headers)
            res.raise_for_status()

            data = res.json()

            return {
                "state": data.get("state"),
                "result": data.get("result"),
                "createdDate": data.get("createdDate"),
                "finishedDate": data.get("finishedDate"),
                "raw": data
            }

    except Exception as ex:
        return {"error": str(ex)}


# -------------------------------------------------------------------
# 3. Obtener reporte completo del pipeline (más demorado)
# -------------------------------------------------------------------
@mcp.tool()
async def get_pipeline_run_report(
    pipeline_id: int,
    run_id: int
) -> str:
    """
    Devuelve el reporte completo del pipeline, con resumen, fechas y resultados.
    Este método puede tardar más.
    """
    try:
        headers = {"Authorization": get_auth_header()}

        async with httpx.AsyncClient() as client:

            url = f"{get_base_url()}/_apis/pipelines/{pipeline_id}/runs/{run_id}?api-version={AZURE_DEVOPS_API_VERSION}"
            res = await client.get(url, headers=headers)
            res.raise_for_status()

            run_info = res.json()

            def safe(key):
                return run_info.get(key, "N/A")

            # === Formato del reporte ===
            report = []
            report.append("✅ PIPELINE RUN REPORT")
            report.append("=" * 80)
            report.append("")
            report.append(f"Pipeline ID: {pipeline_id}")
            report.append(f"Run ID: {run_id}")
            report.append(f"State: {safe('state')}")
            report.append(f"Result: {safe('result')}")
            report.append(f"Created: {safe('createdDate')}")
            report.append(f"Finished: {safe('finishedDate')}")
            report.append("")
            report.append("RAW DATA:")
            report.append("=" * 80)
            report.append(str(run_info))

            return "\n".join(report)

    except Exception as ex:
        return f"❌ Error obteniendo reporte: {str(ex)}"
