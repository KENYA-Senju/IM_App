import sqlite3 

DATABASE = "IMDB.db"
from pathlib import Path


def create_table(connection : sqlite3.Connection):

    sql_statements = """ CREATE TABLE IF NOT EXISTS Inventory(
            id INTEGER PRIMARY KEY,
            material TEXT NOT NULL, 
            quantity INTEGER NOT NULL
            );"""

    cursor = connection.cursor()
    cursor.execute(sql_statements)  
    connection.commit()     
    print("Table has been created")

   
def end_table(connection : sqlite3.Connection): 
    cursor = connection.cursor()
    cursor.execute("DELETE FROM Inventory")
    
    
def main():
    try:
     
        with sqlite3.connect(DATABASE) as conn: 
            create_table(conn)
            print("file created")
            
            
    except sqlite3.OperationalError as e :  
        print(f"Error during init of the database: {e}")    
if __name__ == "__main__": 
    main()