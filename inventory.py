DATABASE = "IMDB.db"

import sys
from pathlib import Path
from typing import Any, Dict, Union
from datetime import datetime
import json 
sys.path.append(str(Path(__file__).resolve().parent))

from database import InventoryDatabase, Utilities

"""
Inventory.py can only receive instructions from the JSON object sent to the file
on how to go about the inventory. As we scale the project, the information will grow.
"""


class Manager:
    def __init__(self, body: bytes, db_file_path: str = "IMDB.db"):
        self.util = Utilities()
       
        self.database = InventoryDatabase(db_file_path)
       
        self.feed_forward = self.util.parse_json_request(body)
    
        self.feed_back = {}
    
    def create_instructions(self) -> None:
        self.manual = {
            "a": self.a,
            "b": self.b,
            "c": self.c,
            "d":self.d, 
            "e":self.e,
            "f": self.f, 
            "g": self.g,
            "refresh":self.refresh
        }

    def resolve(self) -> Dict[str, Any]:
        """Take the feed-forward instruction and execute the corresponding function."""
        return self.manual[self.feed_forward["code"]]()
    #only a is needed of the three classes to do this
    def a(self) -> Dict[str, Any]:
        mat = self.util.normalize_material(self.feed_forward.get("item", ""))
        proj = self.feed_forward.get("project", "")
        quan = int(self.feed_forward.get("amount", 0))
        item_id = self.feed_forward.get("id")
        
        item_id = int(item_id) if item_id is not None else None
        current_time = datetime.now().strftime("%Y-%m-%d, %H:%M:%S")
        res = self.database.update_inventory(item_id, self.feed_forward.get("operation", "Add"), quan, current_time,material=mat, project = proj)
        self.feed_back = self.util.build_api_response(res)
        #return a copy of database for refresh
        self.feed_back["data"] = self.database.get_inventory()
        return self.feed_back

    def b(self) -> Dict[str, Any]:
        mat = self.util.normalize_material(self.feed_forward.get("materials", ""))
        quan = int(self.feed_forward.get("quantity", 0))
        proj = self.feed_forward.get("project", "")
        item_id = self.feed_forward.get("id")
        item_id = int(item_id) if item_id is not None else None
        res = self.database.update_inventory(item_id, "Remove", quan, material=mat, project = proj)
        self.feed_back = self.util.build_api_response(res)
        self.feed_back["data"] = self.database.get_inventory()
        return self.feed_back

    def c(self) -> Dict[str, Any]:
        mat = self.util.normalize_material(self.feed_forward.get("materials", ""))
        quan = int(self.feed_forward.get("quantity", 0))
        item_id = self.feed_forward.get("id")
        item_id = int(item_id) if item_id is not None else None
        proj = self.feed_forward.get("project", "")
        res = self.database.update_inventory(item_id, "Set", quan, material=mat, project = proj)
        self.feed_back = self.util.build_api_response(res)
        self.feed_back["data"] = self.database.get_inventory()
        return self.feed_back
    def d(self) -> Dict[str,Any]: 
        """Return Sorted Copy of The Log Database (Inverse List At the End if descending)"""
        reverse = self.feed_forward["key"] 
        res= self.database.get_sorted_transactions(reverse)
        self.feed_back = self.util.build_api_response(res)  
        return self.feed_back
    def e(self) -> Dict[str, Any]: 
        """Return Ramdomized List of Logs from Database"""  
        res = self.database.get_randomized_transactions()
        self.feed_back = self.util.build_api_response(res)
        return self.feed_back
    def f(self) -> Dict[str,Any]: 
        res = self.database.get_log()  
        aspect = self.read() 
        if aspect is None: return None
        """ I can do this! """
        x = sorted(res, key = lambda d: d[aspect])
        self.feed_back = self.util.build_api_response({"success": True, "operation": f"{aspect}_grouping", "log": x})
        return self.feed_back
    def g(self) -> Dict[str,Any]:
        #Filter all logs that aren't of material or project
        
        if self.read()  == "project": 
            res =  self.database.get_filtered_transaction_project(k = self.feed_forward.get("object", ""))
        else:
            res = self.database.get_filtered_transactions(k = self.feed_forward.get("object",''))

        
        self.feed_back = self.util.build_api_response(res)
        return self.feed_back
    def refresh(self) -> Dict[str,Any]:     
        self.feed_back = self.util.build_api_response({})
        self.feed_back["data"] = self.database.get_inventory()
        return self.feed_back
    def read(self)-> Union[str, None]:
        aspect = None
        match self.feed_forward.get("aspect",""): 
            case "Material": 
                aspect = "material_id"
            case "Project": 
                aspect = "project"
        return aspect
        

    """ 
    CHECK: 
    f implementation
    g implementation 
    refresh implementation 
    database "Log" updating
    """
   
