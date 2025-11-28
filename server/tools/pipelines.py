# tools/pipelines.py
import time
import httpx
from fastmcp import FastMCP

mcp = FastMCP()

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
            create_url = f"{get_base_url()}/{project}/_apis/pipelines?api-version={AZURE_DEVOPS_API_VERSION}"
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
            run_url = f"{get_base_url()}/{project}/_apis/pipelines/{pipeline_id}/runs?api-version={AZURE_DEVOPS_API_VERSION}"
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

@mcp.tool()
async def get_pipeline_run_report(
    project: str
) -> str:
    """
    Retrieves the latest pipeline run for a given project,
    dynamically resolving project_id, pipeline_id and run_id.
    Returns a full formatted report.
    """
    try:
        headers = {"Authorization": get_auth_header()}

        async with httpx.AsyncClient() as client:

            # ============================================================
            # 1. Resolve project_id from project name
            # ============================================================
            projects_url = f"{get_base_url()}/_apis/projects?api-version={AZURE_DEVOPS_API_VERSION}"
            res = await client.get(projects_url, headers=headers)
            res.raise_for_status()

            project_id = next(
                (p["id"] for p in res.json().get("value", []) if p["name"].lower() == project.lower()),
                None
            )

            if not project_id:
                return f"❌ Project '{project}' not found."

            # ============================================================
            # 2. Get all pipelines for this project
            # ============================================================
            pipelines_url = f"{get_base_url()}/{project}/_apis/pipelines?api-version={AZURE_DEVOPS_API_VERSION}"
            res = await client.get(pipelines_url, headers=headers)
            res.raise_for_status()

            pipelines = res.json().get("value", [])
            if not pipelines:
                return f"❌ No pipelines found in project '{project}'."

            # Select the first pipeline (or adjust selection logic)
            pipeline = pipelines[0]
            pipeline_id = pipeline["id"]

            # ============================================================
            # 3. Get the latest run for the selected pipeline
            # ============================================================
            runs_url = f"{get_base_url()}/{project}/_apis/pipelines/{pipeline_id}/runs?api-version={AZURE_DEVOPS_API_VERSION}"
            res = await client.get(runs_url, headers=headers)
            res.raise_for_status()

            runs = res.json().get("value", [])
            if not runs:
                return f"❌ No runs found for pipeline {pipeline_id} in project '{project}'."

            latest_run = runs[0]  # Always the latest execution
            run_id = latest_run["id"]

            # ============================================================
            # 4. Fetch full run details
            # ============================================================
            run_detail_url = (
                f"{get_base_url()}/{project}/_apis/pipelines/{pipeline_id}/runs/{run_id}"
                f"?api-version={AZURE_DEVOPS_API_VERSION}"
            )

            res = await client.get(run_detail_url, headers=headers)
            res.raise_for_status()
            run_info = res.json()

            # Helper
            def safe(key):
                return run_info.get(key, "N/A")

            # ============================================================
            # 5. Build formatted report
            # ============================================================
            report = []
            report.append("✅ PIPELINE RUN REPORT")
            report.append("=" * 80)
            report.append("")
            report.append(f"Project: {project}")
            report.append(f"Pipeline: {pipeline.get('name', 'N/A')} (ID: {pipeline_id})")
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
        return f"❌ Error obtaining pipeline run report: {str(ex)}"
