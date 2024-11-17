# check_properties.py
import os
from notion_client import Client
from dotenv import load_dotenv

load_dotenv()

def check_database_properties():
    notion = Client(auth=os.getenv("NOTION_TOKEN"))
    content_db_id = os.getenv("CONTENT_CALENDAR_DB_ID")
    
    print("\n=== Content Calendar Properties ===")
    database = notion.databases.retrieve(content_db_id)
    
    print("\nAvailable properties:")
    for prop_name, prop_details in database["properties"].items():
        print(f"- {prop_name} ({prop_details['type']})")

if __name__ == "__main__":
    check_database_properties()