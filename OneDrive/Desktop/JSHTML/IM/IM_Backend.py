import json
from pathlib import Path
from typing import Any

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, ConfigDict


from database import InventoryDatabase
from inventory import Manager

from contextlib import asynccontextmanager
import os 





BASE_DIR = Path(__file__).resolve().parent
DATABASE = os.getenv("DB_PATH", str(BASE_DIR / "IMDB.db"))

HOST = os.getenv("HOST", "127.0.0.1")
PORT = int(os.getenv("PORT", "8000"))


@asynccontextmanager
async def lifespan(app: FastAPI): 
    InventoryDatabase(DATABASE) 
    yield 

app = FastAPI(lifespan = lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type"],
)





class InventoryRequest(BaseModel):
    model_config = ConfigDict(extra="allow")

    code: str
    item: str | None = None
    materials: str | None = None
    amount: int | str | None = None
    quantity: int | str | None = None
    operation: str | None = None
    project: str | None = None
    id: int | str | None = None
    key: int | None = None
    aspect: str | None = None
    object: str | None = None


class ProjectCreateRequest(BaseModel):
    name: str
    status: str = "active"


class ProjectUpdateRequest(BaseModel):
    name: str | None = None
    status: str | None = None


class ComponentCreateRequest(BaseModel):
    name: str
    sort_order: int = 0


class ComponentUpdateRequest(BaseModel):
    name: str | None = None
    status: str | None = None
    sort_order: int | None = None


class PartCreateRequest(BaseModel):
    material_id: int
    required_quantity: int


class PartUpdateRequest(BaseModel):
    required_quantity: int


def project_database() -> InventoryDatabase:
    return InventoryDatabase(DATABASE)


def project_error(error: Exception) -> HTTPException:
    if isinstance(error, LookupError):
        return HTTPException(status_code=404, detail=str(error))
    if isinstance(error, ValueError):
        status_code = 409 if "already exists" in str(error) else 400
        return HTTPException(status_code=status_code, detail=str(error))
    return HTTPException(status_code=500, detail="Project operation failed")


@app.post("/IM-server")
def process_inventory_request(request: InventoryRequest) -> Any:
    try:
        body = json.dumps(request.model_dump()).encode("utf-8")
        manager = Manager(body, DATABASE)
        manager.create_instructions()
        return manager.resolve()
    except KeyError as error:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown instruction code: {error.args[0]}",
        ) from error
    except (TypeError, ValueError) as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail="Inventory request failed",
        ) from error


@app.get("/api/inventory/materials")
def get_inventory_materials() -> Any:
    return project_database().list_materials()

@app.get("/api/health")
def get_inventory_health() -> Any: 
    return {"status": "recieved"}

@app.get("/api/projects")
def get_projects() -> Any:
    return project_database().list_projects()


@app.post("/api/projects", status_code=201)
def create_project(request: ProjectCreateRequest) -> Any:
    try:
        return project_database().create_project(request.name, request.status)
    except Exception as error:
        raise project_error(error) from error


@app.get("/api/projects/{project_id}")
def get_project(project_id: int) -> Any:
    try:
        return project_database().get_project_tree(project_id)
    except Exception as error:
        raise project_error(error) from error


@app.patch("/api/projects/{project_id}")
def update_project(project_id: int, request: ProjectUpdateRequest) -> Any:
    try:
        return project_database().update_project(project_id, request.name, request.status)
    except Exception as error:
        raise project_error(error) from error


@app.post("/api/projects/{project_id}/components", status_code=201)
def create_component(project_id: int, request: ComponentCreateRequest) -> Any:
    try:
        return project_database().create_component(project_id, request.name, request.sort_order)
    except Exception as error:
        raise project_error(error) from error


@app.patch("/api/components/{component_id}")
def update_component(component_id: int, request: ComponentUpdateRequest) -> Any:
    try:
        return project_database().update_component(
            component_id, request.name, request.status, request.sort_order
        )
    except Exception as error:
        raise project_error(error) from error


@app.post("/api/components/{component_id}/parts", status_code=201)
def add_component_part(component_id: int, request: PartCreateRequest) -> Any:
    try:
        return project_database().add_component_part(
            component_id, request.material_id, request.required_quantity
        )
    except Exception as error:
        raise project_error(error) from error


@app.patch("/api/component-parts/{part_id}")
def update_component_part(part_id: int, request: PartUpdateRequest) -> Any:
    try:
        return project_database().update_component_part(part_id, request.required_quantity)
    except Exception as error:
        raise project_error(error) from error


@app.delete("/api/component-parts/{part_id}", status_code=204)
def delete_component_part(part_id: int) -> None:
    try:
        project_database().delete_component_part(part_id)
    except Exception as error:
        raise project_error(error) from error


@app.post("/api/components/{component_id}/complete")
def complete_component(component_id: int) -> Any:
    try:
        return project_database().set_component_status(component_id, "finished")
    except Exception as error:
        raise project_error(error) from error


@app.post("/api/components/{component_id}/reopen")
def reopen_component(component_id: int) -> Any:
    try:
        return project_database().set_component_status(component_id, "unfinished")
    except Exception as error:
        raise project_error(error) from error


if __name__ == "__main__":
    uvicorn.run(app, host=HOST, port=PORT)

        