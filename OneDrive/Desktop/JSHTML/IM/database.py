import json
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional
import random
from datetime import datetime, timezone
import re
import unicodedata


""" 
Project Attribute: 

Inventory -> project TEXT NOT NULL 

project:Dict[str,int] 

Insertion: 
    serialized = json.dumps(project_request)
    INSERT INTO Inventory(..., project) VALUES (...,?) (...,serialized)

    ect. 
Addition/Subtraction: 
    delta, request
    currentStock = self.get_item_by_id_str(idormaterial)["project"][request]
    new_stock = currentStock + delta

    if new_stock >= 0: 
        adjusted_dict = self.get_item_by_id_str(idormaterial)["project"]
        adjusted_dict[request] = new_stock
        serialized = json.dumps(adjusted_dict)
        UPDATE Inventory SET .... project = ?  (....,serialized )
    


Log -> project TEXT NOT NULL 
project:str (only one at a time)



"""
class InventoryDatabase:
    """SQLite-backed inventory database helper for IM backend operations."""

    def __init__(self, database_path: str = "IMDB.db"):
        self.database_path = str(database_path)
        self._ensure_inventory_table()
        self._ensure_log_table()
        self._ensure_project_tables()
        self._migrate_legacy_project_allocations()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path)
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def _ensure_inventory_table(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS Inventory (
                    id INTEGER PRIMARY KEY,
                    material TEXT NOT NULL,
                    quantity INTEGER NOT NULL, 
                    time TEXT NOT NULL,
                    project TEXT NOT NULL
                );
                """
            )# With the inclusion of projects, were not tracking total stock for transactions, but only stock for project
    def _ensure_log_table(self) -> None: 
        with self._connect() as conn: 
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS Log (
                    id INTEGER PRIMARY KEY,
                    material_id INTEGER NOT NULL, 
                    operation TEXT NOT NULL, 
                    quantity INTEGER NOT NULL, 
                    time TEXT NOT NULL,
                    project TEXT NOT NULL, 
                    before INTEGER NOT NULL, 
                    change TEXT NOT NULL
                );
                """
            )

    def _ensure_project_tables(self) -> None:
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS Projects (
                    id INTEGER PRIMARY KEY,
                    name TEXT NOT NULL,
                    normalized_name TEXT NOT NULL UNIQUE,
                    status TEXT NOT NULL DEFAULT 'active',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS ProjectComponents (
                    id INTEGER PRIMARY KEY,
                    project_id INTEGER NOT NULL,
                    name TEXT NOT NULL,
                    normalized_name TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'unfinished',
                    sort_order INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    UNIQUE(project_id, normalized_name),
                    FOREIGN KEY(project_id) REFERENCES Projects(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS ComponentParts (
                    id INTEGER PRIMARY KEY,
                    component_id INTEGER NOT NULL,
                    material_id INTEGER NOT NULL,
                    required_quantity INTEGER NOT NULL CHECK(required_quantity > 0),
                    completed_quantity INTEGER NOT NULL DEFAULT 0 CHECK(completed_quantity >= 0),
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    UNIQUE(component_id, material_id),
                    FOREIGN KEY(component_id) REFERENCES ProjectComponents(id) ON DELETE CASCADE,
                    FOREIGN KEY(material_id) REFERENCES Inventory(id)
                );

                CREATE TABLE IF NOT EXISTS ProjectAllocations (
                    id INTEGER PRIMARY KEY,
                    project_id INTEGER NOT NULL,
                    material_id INTEGER NOT NULL,
                    quantity INTEGER NOT NULL CHECK(quantity >= 0),
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    UNIQUE(project_id, material_id),
                    FOREIGN KEY(project_id) REFERENCES Projects(id) ON DELETE CASCADE,
                    FOREIGN KEY(material_id) REFERENCES Inventory(id) ON DELETE CASCADE
                );
                """
            )

    def _migrate_legacy_project_allocations(self) -> None:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT id, project FROM Inventory WHERE project IS NOT NULL"
            ).fetchall()
            for material_id, project_json in rows:
                try:
                    allocations = json.loads(project_json or "{}")
                except (TypeError, ValueError):
                    continue
                if not isinstance(allocations, dict):
                    continue
                for project_name, quantity in allocations.items():
                    try:
                        quantity = int(quantity)
                    except (TypeError, ValueError):
                        continue
                    if quantity < 0 or not str(project_name).strip():
                        continue
                    project = self._find_or_create_project(conn, str(project_name))
                    timestamp = utc_timestamp()
                    conn.execute(
                        """
                        INSERT INTO ProjectAllocations
                            (project_id, material_id, quantity, created_at, updated_at)
                        VALUES (?, ?, ?, ?, ?)
                        ON CONFLICT(project_id, material_id) DO UPDATE SET
                            quantity = excluded.quantity,
                            updated_at = excluded.updated_at
                        """,
                        (project["id"], material_id, quantity, timestamp, timestamp),
                    )
                conn.execute("UPDATE Inventory SET project = '{}' WHERE id = ?", (material_id,))

    def _find_or_create_project(self, conn: sqlite3.Connection, name: str) -> Dict[str, Any]:
        display_name = normalize_project_name(name)
        normalized_name = canonical_name(name)
        row = conn.execute(
            "SELECT id, name, normalized_name, status FROM Projects WHERE normalized_name = ?",
            (normalized_name,),
        ).fetchone()
        if row is not None:
            return {"id": row[0], "name": row[1], "normalized_name": row[2], "status": row[3]}
        timestamp = utc_timestamp()
        cursor = conn.execute(
            """
            INSERT INTO Projects(name, normalized_name, status, created_at, updated_at)
            VALUES (?, ?, 'active', ?, ?)
            """,
            (display_name, normalized_name, timestamp, timestamp),
        )
        return {
            "id": cursor.lastrowid,
            "name": display_name,
            "normalized_name": normalized_name,
            "status": "active",
        }

    def list_projects(self) -> List[Dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT id, name, normalized_name, status FROM Projects ORDER BY name"
            ).fetchall()
        return [dict(id=row[0], name=row[1], normalized_name=row[2], status=row[3]) for row in rows]

    def create_project(self, name: str, status: str = "active") -> Dict[str, Any]:
        display_name = normalize_project_name(name)
        normalized_name = canonical_name(name)
        if not normalized_name:
            raise ValueError("Project name cannot be empty")
        if status not in {"active", "paused", "archived"}:
            raise ValueError("Invalid project status")
        timestamp = utc_timestamp()
        with self._connect() as conn:
            try:
                cursor = conn.execute(
                    """
                    INSERT INTO Projects(name, normalized_name, status, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (display_name, normalized_name, status, timestamp, timestamp),
                )
            except sqlite3.IntegrityError as error:
                raise ValueError("Project name already exists") from error
            return {
                "id": cursor.lastrowid,
                "name": display_name,
                "normalized_name": normalized_name,
                "status": status,
            }

    def update_project(self, project_id: int, name: Optional[str] = None, status: Optional[str] = None) -> Dict[str, Any]:
        with self._connect() as conn:
            project = conn.execute(
                "SELECT id, name, normalized_name, status FROM Projects WHERE id = ?",
                (project_id,),
            ).fetchone()
            if project is None:
                raise LookupError("Project not found")
            next_name = normalize_project_name(name) if name is not None else project[1]
            next_normalized = canonical_name(name) if name is not None else project[2]
            next_status = status if status is not None else project[3]
            if not next_normalized:
                raise ValueError("Project name cannot be empty")
            if next_status not in {"active", "paused", "archived"}:
                raise ValueError("Invalid project status")
            try:
                conn.execute(
                    """
                    UPDATE Projects SET name = ?, normalized_name = ?, status = ?, updated_at = ?
                    WHERE id = ?
                    """,
                    (next_name, next_normalized, next_status, utc_timestamp(), project_id),
                )
            except sqlite3.IntegrityError as error:
                raise ValueError("Project name already exists") from error
            return {"id": project_id, "name": next_name, "normalized_name": next_normalized, "status": next_status}

    def get_project_tree(self, project_id: int) -> Dict[str, Any]:
        with self._connect() as conn:
            project = conn.execute(
                "SELECT id, name, normalized_name, status FROM Projects WHERE id = ?",
                (project_id,),
            ).fetchone()
            if project is None:
                raise LookupError("Project not found")
            components = conn.execute(
                """
                SELECT id, name, normalized_name, status, sort_order
                FROM ProjectComponents WHERE project_id = ? ORDER BY sort_order, name
                """,
                (project_id,),
            ).fetchall()
            result = dict(id=project[0], name=project[1], normalized_name=project[2], status=project[3], components=[])
            for component in components:
                parts = conn.execute(
                    """
                    SELECT cp.id, cp.material_id, i.material, cp.required_quantity,
                                                     cp.completed_quantity,
                                                     COALESCE((
                                                             SELECT SUM(pa.quantity)
                                                             FROM ProjectAllocations pa
                                                             WHERE pa.material_id = cp.material_id
                                                                 AND pa.project_id IN (?, (
                                                                         SELECT id FROM Projects WHERE normalized_name = 'any'
                                                                 ))
                                                     ), 0)
                    FROM ComponentParts cp
                    JOIN Inventory i ON i.id = cp.material_id
                    WHERE cp.component_id = ?
                    ORDER BY i.material
                    """,
                    (project_id, component[0]),
                ).fetchall()
                part_data = []
                for part in parts:
                    available = int(part[5])
                    required = int(part[3])
                    completed = int(part[4])
                    part_data.append({
                        "id": part[0], "material_id": part[1], "material": part[2],
                        "required_quantity": required, "available_quantity": available,
                        "completed_quantity": completed,
                        "available": available >= required,
                        "completed": completed >= required,
                    })
                result["components"].append({
                    "id": component[0], "name": component[1],
                    "normalized_name": component[2], "status": component[3],
                    "sort_order": component[4], "parts": part_data,
                })
            return result

    def create_component(self, project_id: int, name: str, sort_order: int = 0) -> Dict[str, Any]:
        display_name = normalize_project_name(name)
        normalized_name = canonical_name(name)
        if not normalized_name:
            raise ValueError("Component name cannot be empty")
        timestamp = utc_timestamp()
        with self._connect() as conn:
            if conn.execute("SELECT 1 FROM Projects WHERE id = ?", (project_id,)).fetchone() is None:
                raise LookupError("Project not found")
            try:
                cursor = conn.execute(
                    """
                    INSERT INTO ProjectComponents
                        (project_id, name, normalized_name, sort_order, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (project_id, display_name, normalized_name, int(sort_order), timestamp, timestamp),
                )
            except sqlite3.IntegrityError as error:
                raise ValueError("Component name already exists in this project") from error
            return {"id": cursor.lastrowid, "project_id": project_id, "name": display_name,
                    "normalized_name": normalized_name, "status": "unfinished", "sort_order": int(sort_order)}

    def update_component(self, component_id: int, name: Optional[str] = None,
                         status: Optional[str] = None, sort_order: Optional[int] = None) -> Dict[str, Any]:
        with self._connect() as conn:
            component = conn.execute(
                "SELECT project_id, name, normalized_name, status, sort_order FROM ProjectComponents WHERE id = ?",
                (component_id,),
            ).fetchone()
            if component is None:
                raise LookupError("Component not found")
            next_name = normalize_project_name(name) if name is not None else component[1]
            next_normalized = canonical_name(name) if name is not None else component[2]
            next_status = status if status is not None else component[3]
            next_order = int(sort_order) if sort_order is not None else component[4]
            if next_status not in {"unfinished", "finished"}:
                raise ValueError("Invalid component status")
            try:
                conn.execute(
                    """
                    UPDATE ProjectComponents
                    SET name = ?, normalized_name = ?, status = ?, sort_order = ?, updated_at = ?
                    WHERE id = ?
                    """,
                    (next_name, next_normalized, next_status, next_order, utc_timestamp(), component_id),
                )
            except sqlite3.IntegrityError as error:
                raise ValueError("Component name already exists in this project") from error
            return {"id": component_id, "project_id": component[0], "name": next_name,
                    "normalized_name": next_normalized, "status": next_status, "sort_order": next_order}

    def add_component_part(self, component_id: int, material_id: int, required_quantity: int) -> Dict[str, Any]:
        required_quantity = int(required_quantity)
        if required_quantity <= 0:
            raise ValueError("Required quantity must be greater than zero")
        timestamp = utc_timestamp()
        with self._connect() as conn:
            if conn.execute("SELECT 1 FROM ProjectComponents WHERE id = ?", (component_id,)).fetchone() is None:
                raise LookupError("Component not found")
            material = conn.execute("SELECT id, material FROM Inventory WHERE id = ?", (material_id,)).fetchone()
            if material is None:
                raise LookupError("Inventory material not found")
            try:
                cursor = conn.execute(
                    """
                    INSERT INTO ComponentParts
                        (component_id, material_id, required_quantity, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (component_id, material_id, required_quantity, timestamp, timestamp),
                )
            except sqlite3.IntegrityError as error:
                raise ValueError("This material is already assigned to the component") from error
            return {"id": cursor.lastrowid, "component_id": component_id, "material_id": material[0],
                    "material": material[1], "required_quantity": required_quantity,
                    "completed_quantity": 0, "completed": False}

    def update_component_part(self, part_id: int, required_quantity: int) -> Dict[str, Any]:
        required_quantity = int(required_quantity)
        if required_quantity <= 0:
            raise ValueError("Required quantity must be greater than zero")
        with self._connect() as conn:
            part = conn.execute("SELECT id, completed_quantity FROM ComponentParts WHERE id = ?", (part_id,)).fetchone()
            if part is None:
                raise LookupError("Component part not found")
            conn.execute(
                "UPDATE ComponentParts SET required_quantity = ?, updated_at = ? WHERE id = ?",
                (required_quantity, utc_timestamp(), part_id),
            )
            return {"id": part_id, "required_quantity": required_quantity,
                    "completed_quantity": int(part[1]), "completed": int(part[1]) >= required_quantity}

    def delete_component_part(self, part_id: int) -> None:
        with self._connect() as conn:
            cursor = conn.execute("DELETE FROM ComponentParts WHERE id = ?", (part_id,))
            if cursor.rowcount == 0:
                raise LookupError("Component part not found")

    def set_component_status(self, component_id: int, status: str) -> Dict[str, Any]:
        return self.update_component(component_id, status=status)

    def list_materials(self) -> List[Dict[str, Any]]:
        return self.get_inventory()

        
    def get_randomized_transactions(self) -> Dict[str,Any]: 
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id, material_id, operation, quantity, time FROM Log ORDER BY id"
            )
            r = cursor.fetchall()
            random.shuffle(r)
            
            return {
                    "success": True,
                    "operation": "Logging-Random",
                    "log": r
                }

    def get_filtered_transactions(self, k:str)-> Dict[str, Any]:
        commodity = self.get_item_by_id_str(item_id_str=k )["id"] #TODO: we are looking for the material_id
        
        if commodity is None:   
            #Raise an Error in the response 
            #Because the user was trying to filter the transactions, Just return the log as is the order 
            return { 
                "success": False, 
                "error": "Unknown Material Keyword",
                "log": self.get_log()
            }
        
        with self._connect() as conn: 
            cursor = conn.cursor() 
            cursor.execute(f"SELECT id, material_id, operation, quantity, time, project FROM Log WHERE material_id = {commodity}")
            rows = cursor.fetchall() 
            return { 
                "success": True, 
                "operation": f"Filter by Keyword: {commodity}",
                "log": rows
            }
    def get_filtered_transaction_project(self, k: str) -> Dict[str, Any]:
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, material_id, operation, quantity, time, project FROM Log ORDER BY id")
            rows = cursor.fetchall()
      
        filtered_rows = []
        for row in rows:
            try:
                project_dict = row[5] if row[5] is not None else {}
            except (TypeError, ValueError) as e:
                print("Error: ", e)
                continue
            
           
            if isinstance(project_dict, str) and k ==  project_dict:
                filtered_rows.append(row)

        return {
            "success": True,
            "operation": f"Filter by Project : {k}",
            "log": filtered_rows
        }
        
    def get_sorted_transactions(self,inv: int) -> Dict[str,Any]: 
        #Sort in reverse order if instructed to 
        #id's are always allocated in ascending order, so there is no need to write additional algorithms to sort by timestamps 
        #if you want to try that, be my guest
        r = self.get_log()[::inv]
        return {
                "success": True,
                "operation": f"Logging-{"Ascending" if inv == 1 else "Descending"}",
                "log": r
            }

    def get_item_by_id_str(self, item_id_str: int | str) -> Optional[Dict[str, Any]]:
        with self._connect() as conn:
            cursor = conn.cursor()
            it = None
            if (type(item_id_str) == int): 
                it = "id" 
            else: 
                it = "material"
                    #maybe other statements that could be later added on
            #the request must be apart of the dictionary keys of project 
            if it == None: return None 
            cursor.execute(f"SELECT id, material, quantity, time, project FROM Inventory WHERE {it} = ?", (item_id_str,))
            row = cursor.fetchone()
            if row is None:
                return None
            allocation_rows = conn.execute(
                """
                SELECT p.name, pa.quantity
                FROM ProjectAllocations pa
                JOIN Projects p ON p.id = pa.project_id
                WHERE pa.material_id = ?
                """,
                (row[0],),
            ).fetchall()
            allocations = {allocation[0]: int(allocation[1]) for allocation in allocation_rows}
            return {"id": int(row[0]), "material": row[1], "quantity": int(row[2]), "time":str(row[3]), "project": allocations}
        
        
    

    
        
    def get_project(self, item_id:int)-> Dict[str,int] | None: 
        item = self.get_item_by_id_str(item_id)
        return None if item is None else item["project"]

    



    def update_log(self,cursor: sqlite3.Cursor, material_id:int, magnitude:int, operation: str, time:str, project:str, before:int, change:str)-> None: 
        cursor.execute(
            "INSERT INTO Log(material_id, quantity, time, operation, project, before, change) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (material_id, magnitude, time, operation, project, before, change)  
        )
        
        """ The Function Stack Passes This Method in This Order:

        --> set_quantity/adjust_quantity 
            cursor object created 
            -->  update_log(sqlite3.Cursor cursor) (on success)
            cursor.close() 

            ONLY ONE PROJECT FOR A PARTICULAR REQUEST CAN BE LOGGED AT A TIME (NOT MULTIPLE)
            
        """

    def _project_for_name(self, conn: sqlite3.Connection, name: str) -> Dict[str, Any]:
        normalized_name = canonical_name(name)
        row = conn.execute(
            "SELECT id, name FROM Projects WHERE normalized_name = ?",
            (normalized_name,),
        ).fetchone()
        if row is None:
            raise LookupError("Project not found")
        return {"id": row[0], "name": row[1]}

    def _allocation_quantity(self, conn: sqlite3.Connection, project_id: int, material_id: int) -> int:
        row = conn.execute(
            "SELECT quantity FROM ProjectAllocations WHERE project_id = ? AND material_id = ?",
            (project_id, material_id),
        ).fetchone()
        return 0 if row is None else int(row[0])

    def _set_allocation(self, conn: sqlite3.Connection, project_id: int, material_id: int, quantity: int) -> None:
        timestamp = utc_timestamp()
        conn.execute(
            """
            INSERT INTO ProjectAllocations(project_id, material_id, quantity, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(project_id, material_id) DO UPDATE SET
                quantity = excluded.quantity, updated_at = excluded.updated_at
            """,
            (project_id, material_id, quantity, timestamp, timestamp),
        )

    def _total_allocated(self, conn: sqlite3.Connection, material_id: int) -> int:
        row = conn.execute(
            "SELECT COALESCE(SUM(quantity), 0) FROM ProjectAllocations WHERE material_id = ?",
            (material_id,),
        ).fetchone()
        return int(row[0])

    def set_quantity(self, item_id: Optional[int], material: str, quantity: int, ISO_8601: str, project:str,operation: Optional[str] = None) -> Dict[str, Any]:
        normalized_material = normalize_material(material)
        proj = normalize_project_name(project)
        total_stock = 0
        quantity = int(quantity)
        #serialize the dictionary 
        method = operation if operation is not None else "Null"
        
        with self._connect() as conn:
            cursor = conn.cursor()
            project_record = self._project_for_name(conn, project)
            if item_id is None:
                bf = 0 
                cursor.execute(
                    "INSERT INTO Inventory(material, quantity, time, project) VALUES (?, ?, ?, ?)",
                    (normalized_material, quantity, ISO_8601, "{}"),
                )
                item_id = cursor.lastrowid
                latest_item = True
            else:
                existing = self.get_item_by_id_str(item_id)
                if existing is None:
                    bf = 0
                    cursor.execute(
                        "INSERT INTO Inventory(id, material, quantity, time, project) VALUES (?, ?, ?, ?, ?)",
                        (item_id, normalized_material, quantity, ISO_8601, "{}"),
                    )
                    latest_item = True
                else:
                    bf = existing["quantity"]
                    cursor.execute(
                        "UPDATE Inventory SET material = ?, time = ? WHERE id = ?",
                        (normalized_material, ISO_8601, item_id),
                    )
                    latest_item = False

            self._set_allocation(conn, project_record["id"], item_id, quantity)
            total_stock = self._total_allocated(conn, item_id)
            cursor.execute("UPDATE Inventory SET quantity = ? WHERE id = ?", (total_stock, item_id))
            self.update_log(cursor, item_id, quantity, method, ISO_8601, proj,bf, "—"  ) #this is an em dash
            conn.commit()
        
        return {
            "success": True,
            "operation": "Set",
            "id": item_id,
            "material": normalized_material,
            "quantity": quantity,
            "stock": total_stock,
            "latest_item": latest_item,
            "time":ISO_8601, 
            "project": proj
        }
    """ 
    Addition/Subtraction: 
    delta, request
    currentStock = self.get_item_by_id_str(idormaterial)["project"][request]
    new_stock = currentStock + delta

    if new_stock >= 0: 
        adjusted_dict = self.get_item_by_id_str(idormaterial)["project"]
        adjusted_dict[request] = new_stock
        serialized = json.dumps(adjusted_dict)
        UPDATE Inventory SET .... project = ?  (....,serialized )
    
    """
    def adjust_quantity(self, item_id: int, delta: int, ISO_8601: str,operation: str,request:str,material: Optional[str] = None ) -> Dict[str, Any]:
        item = self.get_item_by_id_str(item_id)
        normalized_request = normalize_project_name(request)
        method = operation 
        normalized_material = normalize_material(material) if material is not None else (item["material"] if item is not None else "")

        with self._connect() as conn:
            cursor = conn.cursor()
            project_record = self._project_for_name(conn, request)
            current_quantity = self._allocation_quantity(conn, project_record["id"], item_id)
            new_stock = current_quantity + delta
            if new_stock < 0:
                return {
                    "success": False, "error": "INSUFFICIENT_STOCK", "requested": delta,
                    "project": normalized_request, "available": current_quantity, "id": item_id,
                }
            if item is None:
                if not normalized_material:
                    return {
                        "success": False,
                        "error": "MATERIAL_REQUIRED_FOR_NEW_ITEM",
                        "id": item_id,
                    }
                cursor.execute(
                    "INSERT INTO Inventory(id, material, quantity, time, project) VALUES (?, ?, ?, ?, ?)",
                    (item_id, normalized_material, new_stock, ISO_8601, "{}"),
                )
                latest_item = True
            else:
                cursor.execute("UPDATE Inventory SET time = ? WHERE id = ?", (ISO_8601, item_id))
                latest_item = False
            self._set_allocation(conn, project_record["id"], item_id, new_stock)
            total_stock = self._total_allocated(conn, item_id)
            cursor.execute("UPDATE Inventory SET quantity = ? WHERE id = ?", (total_stock, item_id))
            adjusted_dict = self.get_item_by_id_str(item_id)["project"]
            self.update_log(cursor, item_id,new_stock, method, ISO_8601 ,normalized_request, current_quantity,str(delta))
            conn.commit()
        

        return {
            "success": True,
            "operation": "Add" if delta >= 0 else "Remove",
            "id": item_id,
            "material": normalized_material,
            "quantity": delta,
            "stock": total_stock,
            "latest_item": latest_item,
            "time": ISO_8601, 
            "project": adjusted_dict, 
        }

    def update_inventory(self, item_id: Optional[int], operation: str, amount: int, ISO_8601:str,project:str, material: Optional[str] = None) -> Dict[str, Any]:
        operation = operation.strip().title()
        if operation == "Add":
            if item_id is None:
                return self.set_quantity(item_id, material or "", amount,ISO_8601,project = project ,operation= operation)
            return self.adjust_quantity(item_id, amount,ISO_8601,material=material,request = project,operation = operation)
        if operation == "Remove":
            if item_id is None:
                return {
                    "success": False,
                    "error": "ID_REQUIRED_FOR_REMOVE",
                    "operation": operation,
                    "material": material,
                    "amount": amount,
                    "project":project
                }
            return self.adjust_quantity(item_id, -amount, ISO_8601, request = project,operation = operation)
        if operation == "Set":
            return self.set_quantity(item_id, material or "", amount, ISO_8601, project = project,operation = operation)
        return {
            "success": False,
            "error": "INVALID_OPERATION",
            "operation": operation,
            "material": material,
            "amount": amount,
            "project": project
        }
    
        

    def get_inventory(self) -> List[Dict[str, Any]]:
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, material, quantity, time, project FROM Inventory ORDER BY id")
            rows = cursor.fetchall()
        inventory = []
        for row in rows:
            item = self.get_item_by_id_str(int(row[0]))
            allocations = item["project"] if item is not None else {}
            inventory.append({"id": int(row[0]), "material": row[1], "quantity": int(row[2]),
                              "time": str(row[3]), "project": allocations,
                              "stock": sum(allocations.values())})
        return inventory
    def get_log(self) -> List[Dict[str, Any]]: 
        with self._connect() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT id, material_id, operation, quantity, time, project, before, change FROM Log ORDER BY id")
                rows = cursor.fetchall()
        a = [{"id": int(row[0]), "material_id": int(row[1]), "operation": str(row[2]), "quantity": int(row[3]),"time": str(row[4]), "project":str(row[5]), "before": int(row[6]), "change":str(row[7])} for row in rows] 
        return a


    def delete_material(self, item_id: int) -> Dict[str, Any]:
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM Inventory WHERE id = ?", (item_id,))
            conn.commit()
        
        return {"success": True, "id": item_id, "deleted": cursor.rowcount > 0}

class Utilities:
    def parse_json_request(self, body: bytes) -> Dict[str, Any]:
        return json.loads(body.decode("utf-8"))

    def build_api_response(self, payload: Dict[str, Any], status: str = "received") -> Dict[str, Any]:
        payload["status"] = status
        return payload

    def normalize_material(self, material: str) -> str:
        return str(material).strip().title()


def parse_json_request(body: bytes) -> Dict[str, Any]:
    return Utilities().parse_json_request(body)


def build_api_response(payload: Dict[str, Any], status: str = "received") -> Dict[str, Any]:
    return Utilities().build_api_response(payload, status=status)


def normalize_material(material: str) -> str:
    return Utilities().normalize_material(material)


def canonical_name(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", str(value)).strip().casefold()
    normalized = re.sub(r"[\s_]+", "-", normalized)
    normalized = re.sub(r"-+", "-", normalized)
    return normalized.strip("-")


def normalize_project_name(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", str(value)).strip()
    normalized = re.sub(r"\s+", " ", normalized)
    return normalized.title()


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")

def reveal_total_stocks(d: Dict[str, Any]) -> int:
    if not isinstance(d, dict):
        return 0

    total = 0
    for value in d.values():
        if isinstance(value, str):
            try:
                value = json.loads(value)
            except Exception:
                value = value

        if isinstance(value, dict):
            total += reveal_total_stocks(value)
        else:
            try:
                total += int(value)
            except (TypeError, ValueError):
                total += 0

    return total

""" 
The user should be capable of reserving items from the Any project into their own specific project
"""




