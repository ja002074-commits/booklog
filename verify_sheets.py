
from streamlit_gsheets import GSheetsConnection
import streamlit as st
import pandas as pd
import toml

# skipped manual read

try:
    conn = st.connection("gsheets", type=GSheetsConnection)
    
    # Try reading the 'categories' sheet
    try:
        df_cat = conn.read(worksheet="categories", ttl=0)
        print("Existing 'categories' sheet found.")
    except:
        print("'categories' sheet not found, creating...")
        defaults = pd.DataFrame([{"name": "技術書"}, {"name": "ビジネス"}, {"name": "小説"}, {"name": "その他"}])
        conn.update(worksheet="categories", data=defaults)
        print("Created 'categories' sheet.")

    # Try reading the 'books' sheet
    try:
        df_books = conn.read(worksheet="books", ttl=0)
        print("Existing 'books' sheet found.")
    except:
        print("'books' sheet not found, it should be empty initially.")
        # Create empty with headers
        expected = ["id", "title", "author", "category", "tags", "status", "notes", "cover_url", "read_date", "isbn", "created_at"]
        df_empty = pd.DataFrame(columns=expected)
        conn.update(worksheet="books", data=df_empty)
        print("Initialized 'books' sheet with headers.")

    print("SUCCESS: Google Sheets connected and initialized!")
    
except Exception as e:
    print(f"ERROR: Could not connect to Google Sheets. {e}")
    exit(1)
