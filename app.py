import streamlit as st
import pandas as pd
from datetime import datetime, date
import google.generativeai as genai
import os
import json
from PIL import Image, ImageEnhance
import requests
import io
import socket
import re
import qrcode
import time
from streamlit_gsheets import GSheetsConnection
import difflib
try:
    from pyzbar.pyzbar import decode
    PYZBAR_AVAILABLE = True
except ImportError:
    PYZBAR_AVAILABLE = False

# --- 1. Settings & CSS Styling ---
st.set_page_config(layout="wide", page_title="BookLog DB", page_icon="favicon.png")

# Force Japanese Encoding/Lang
st.markdown("""
<meta http-equiv="Content-Language" content="ja">
<script>
    function setLang() {
        document.documentElement.lang = "ja";
    }
    setLang();
    setInterval(setLang, 1000);
</script>
""", unsafe_allow_html=True)

# Custom CSS with ROBUST Device Separation
st.markdown("""
<style>
/* 1. Global Gradient Background (PIVOT Style) & Atmosphere */
@import url('https://fonts.googleapis.com/css2?family=Montserrat:wght@400;600;800&family=Noto+Sans+JP:wght@300;400;500;700&display=swap');

.stApp {
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); /* Deep Purple-Blue Gradient */
    background-attachment: fixed;
    color: #ffffff;
    font-family: "Montserrat", "Hiragino Kaku Gothic ProN", "Noto Sans JP", sans-serif;
    letter-spacing: 0.03em;
}

/* 2. Glassmorphism Sidebar (Dark/Transparent) */
section[data-testid="stSidebar"] {
    background-color: rgba(20, 20, 30, 0.4) !important; /* Dark Glass */
    border-right: 1px solid rgba(255, 255, 255, 0.2);
    box-shadow: 5px 0 25px rgba(0,0,0,0.2);
    backdrop-filter: blur(12px);
}
/* Force Sidebar text to be WHITE */
section[data-testid="stSidebar"] h1,
section[data-testid="stSidebar"] h2,
section[data-testid="stSidebar"] h3,
section[data-testid="stSidebar"] h4,
section[data-testid="stSidebar"] h5,
section[data-testid="stSidebar"] h6,
section[data-testid="stSidebar"] span,
section[data-testid="stSidebar"] label,
section[data-testid="stSidebar"] div[data-testid="stMarkdownContainer"] p,
section[data-testid="stSidebar"] div[data-testid="stMarkdownContainer"] span,
section[data-testid="stSidebar"] div[data-testid="stMarkdownContainer"] small,
section[data-testid="stSidebar"] .stMarkdown {
    color: #ffffff !important;
    font-family: "Montserrat", "Noto Sans JP", sans-serif !important;
}
/* Hide artifacts if needed */
/* Hide artifacts (Robust) */
/* Hide artifacts (Robust - Only target specific elements if needed) */
button[kind="header"] {
    background: transparent !important;
}

/* Fix properties for Sidebar Button (Fundamental Fix + SVG + Visibility Hack) */
/* 1. Use visibility:hidden to nuke the internal text completely */
[data-testid="stSidebarCollapseButton"] > span,
[data-testid="stSidebarCollapseButton"] > svg {
    visibility: hidden !important;
    opacity: 0 !important;
    font-size: 0 !important;
}

[data-testid="stSidebarCollapseButton"] {
    /* Shape & Centering */
    position: relative !important;
    display: flex !important;
    align-items: center;
    justify-content: center;
    width: 36px !important;
    height: 36px !important;
    border: 1px solid rgba(255,255,255,0.2) !important;
    border-radius: 50% !important;
    background: rgba(0,0,0,0.2) !important;
    z-index: 100;
    transition: all 0.3s ease;
    
    /* VITAL: Force text color to transparent and hide content */
    color: transparent !important; 
    text-shadow: none !important;
    user-select: none !important;
    visibility: visible !important; /* Ensure the button itself is visible */
}

/* 2. Re-add the clean icon via SVG Background on ::after */
[data-testid="stSidebarCollapseButton"]::after {
    content: ""; /* No text content */
    position: absolute !important;
    left: 50% !important;
    top: 50% !important;
    transform: translate(-50%, -50%) !important;
    width: 16px;
    height: 16px;
    /* Use encoded SVG for the arrow */
    background-image: url('data:image/svg+xml;utf8,<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><path d="M15 18l-6-6 6-6"/></svg>');
    background-repeat: no-repeat;
    background-position: center;
    background-size: contain;
    pointer-events: none;
    visibility: visible !important; /* Force visibility of the replacement */
}

/* 3. Aggressively target ALL states to prevent text appearing on interaction */
[data-testid="stSidebarCollapseButton"]:hover,
[data-testid="stSidebarCollapseButton"]:active,
[data-testid="stSidebarCollapseButton"]:focus,
[data-testid="stSidebarCollapseButton"]:focus-visible {
    background: rgba(255,255,255,0.1) !important;
    box-shadow: 0 0 10px rgba(255,255,255,0.2) !important;
    color: transparent !important; /* Prevent hover text */
    text-shadow: none !important;
    font-size: 0 !important;
}    
/* 4. Extra safety: Hide the tooltip explicitly if it exists as a data attribute */
[data-testid="stSidebarCollapseButton"][title] {
    color: transparent !important;
}


/* Fix Expander Text Overlap (Fundamental Fix: Rebuild Label) */
/* 1. Hide EVERYTHING inside the summary (glitched text + original label) */
div[data-testid="stExpander"] > details > summary {
    color: transparent !important;
    font-size: 0 !important; /* Collapse all text */
    position: relative;
}
div[data-testid="stExpander"] > details > summary > * {
    display: none !important; /* Hide children elements to prevent ghosts */
}

/* 2. Rebuild the Label using CSS Content */
div[data-testid="stExpander"] > details > summary::after {
    content: "🖥️ Display Mode"; /* The clean label */
    color: #ffffff !important;
    font-size: 0.9rem !important;
    font-weight: 600;
    font-family: "Montserrat", sans-serif;
    
    /* Position it nicely */
    position: absolute;
    left: 40px; /* Space for the chevron if it exists, or just padding */
    top: 50%;
    transform: translateY(-50%);
    visibility: visible !important;
    white-space: nowrap;
}

/* 3. Rebuild the Chevron/Plus icon (Optional, or just keep it clean) */
div[data-testid="stExpander"] > details > summary::before {
    content: "▼";
    color: rgba(255,255,255,0.7);
    font-size: 0.8rem !important;
    position: absolute;
    left: 15px;
    top: 50%;
    transform: translateY(-50%);
    visibility: visible !important;
}
/* Rotate chevron when open? (Hard to do with pure CSS on summary state without :has, 
   but simplistic static icon is better than broken text) */
div[data-testid="stExpander"] > details[open] > summary::before {
    transform: translateY(-50%) rotate(180deg);
}
/* General safety for any broken material icons in headers */
.streamlit-expanderHeader span {
    font-family: inherit !important; /* Prevent font conflict */
}

/* 3. Main Content Headers */
h1, h2, h3 {
    font-family: "Montserrat", "Hiragino Kaku Gothic ProN", "Noto Sans JP", sans-serif !important;
    color: #ffffff !important;
    font-weight: 800 !important; /* Bold like PIVOT */
    text-shadow: 0 4px 10px rgba(0,0,0,0.3);
    text-transform: uppercase;
    letter-spacing: 0.05em;
}

h1 {
    font-size: 2.5rem !important;
    border-bottom: 2px solid rgba(255, 255, 255, 0.3);
    padding-bottom: 15px;
    margin-bottom: 30px;
}

/* 4. Glassy Inputs (Main Area) */
/* Text Input, Selectbox, Text Area */
.stTextInput input, .stTextArea textarea, .stSelectbox div[data-baseweb="select"] > div {
    background-color: rgba(255, 255, 255, 0.15) !important;
    color: #ffffff !important;
    border: 1px solid rgba(255, 255, 255, 0.3) !important;
    border-radius: 12px !important;
    backdrop-filter: blur(12px);
    font-family: "Montserrat", "Noto Sans JP", sans-serif;
}
/* Sidebar Inputs Override (Dark Text) */
section[data-testid="stSidebar"] .stTextInput input, 
section[data-testid="stSidebar"] .stSelectbox div[data-baseweb="select"] > div {
    background-color: #ffffff !important;
    color: #333333 !important;
    border: 1px solid #ccc !important;
}

/* Labels */
.stMarkdown label, .stMarkdown p {
    color: rgba(255, 255, 255, 0.95) !important;
    font-weight: 500;
}
/* Expander (Glassy & Premium) */
.streamlit-expanderHeader {
    background-color: rgba(255, 255, 255, 0.05) !important;
    color: #ffffff !important;
    border-radius: 8px !important;
    font-weight: 600;
    font-family: "Montserrat", sans-serif;
    border: 1px solid rgba(255, 255, 255, 0.1);
    transition: all 0.2s ease;
}
.streamlit-expanderHeader:hover {
    background-color: rgba(255, 255, 255, 0.15) !important;
    border-color: rgba(255, 255, 255, 0.3);
}
div[data-testid="stExpander"] {
    background-color: rgba(0,0,0,0.2) !important;
    border-radius: 8px;
    border: 1px solid rgba(255,255,255,0.1);
    box-shadow: 0 4px 10px rgba(0,0,0,0.1);
}
div[data-testid="stExpander"] p {
    font-size: 0.9rem;
}

/* 5. Buttons (Vibrant Gradient) */
.stButton button {
    background: linear-gradient(90deg, #ff8a00, #e52e71) !important; /* PIVOT Accent Colors */
    color: white !important;
    border: none !important;
    border-radius: 30px !important;
    font-weight: 700 !important;
    padding: 0.6rem 2rem !important;
    box-shadow: 0 4px 15px rgba(229, 46, 113, 0.4) !important;
    font-family: "Montserrat", sans-serif !important;
    transition: all 0.3s ease !important;
    letter-spacing: 0.05em !important;
}
.stButton button:hover {
    transform: translateY(-2px);
    box-shadow: 0 6px 20px rgba(229, 46, 113, 0.6) !important;
}

/* 6. GLASS CARD STYLING */
.glass-card {
    background-color: rgba(255, 255, 255, 0.1);
    border-radius: 16px;
    padding: 20px;
    margin-bottom: 20px;
    border: 1px solid rgba(255, 255, 255, 0.2);
    backdrop-filter: blur(10px);
    display: flex;
    flex-direction: row;
    align-items: flex-start;
    gap: 20px;
    box-shadow: 0 4px 30px rgba(0, 0, 0, 0.1);
}
.glass-card-img-box {
    width: 120px;
    flex-shrink: 0;
    border-radius: 8px;
    overflow: hidden;
    background: transparent;
}
.glass-card-img {
    width: 100%;
    height: auto;
    display: block;
    box-shadow: 0 4px 8px rgba(0,0,0,0.3);
}
.glass-card-content {
    flex-grow: 1;
    color: #ffffff;
}
.glass-card-title {
    font-size: 1.4rem;
    font-weight: 700;
    margin: 0 0 5px 0;
    line-height: 1.3;
}
.glass-card-author {
    font-size: 0.9rem;
    color: rgba(255,255,255,0.8);
    margin-bottom: 10px;
}
.tag-badge {
    background: rgba(255,255,255,0.2);
    padding: 3px 10px;
    border-radius: 12px;
    font-size: 0.75rem;
    margin-right: 5px;
    color: #ffffff;
    border: 1px solid rgba(255,255,255,0.3);
    display: inline-block;
}
.note-box {
    background: rgba(0,0,0,0.25);
    padding: 10px;
    border-radius: 8px;
    border-left: 4px solid #ff8a00;
    color: #f0f0f0;
    font-size: 0.9rem;
    margin-top: 10px;
}

/* Mobile Adjustments */
@media (max-width: 767px) {
    .glass-card {
        flex-direction: column;
        align-items: center;
        text-align: center;
    }
    .glass-card-img-box {
        width: 140px;
        margin-bottom: 15px;
    }
    .note-box {
        text-align: left;
    }
}

/* Device Separation Logic (Robust / Exclusion Based) */
/* Prevent hiding the ROOT container by ensuring we only hide containers that have ONE marker but NOT the other. */

/* Mobile View: Hide PC Container */
/* Logic: Find a block with PC marker, BUT exclude blocks that also have a Mobile marker (like the Root) */
@media (max-width: 767px) {
    div[data-testid="stVerticalBlock"]:has(div.pc-view-marker):not(:has(div.mobile-view-marker)) {
        display: none !important;
    }
}

/* PC View: Hide Mobile Container */
/* Logic: Find a block with Mobile marker, BUT exclude blocks that also have a PC marker */
@media (min-width: 768px) {
    div[data-testid="stVerticalBlock"]:has(div.mobile-view-marker):not(:has(div.pc-view-marker)) {
        display: none !important;
    }
}
</style>
""", unsafe_allow_html=True)

# s --- 2. Database Functions ---
def to_isbn10(isbn13):
    if not isbn13 or len(isbn13) != 13: return None
    body = isbn13[3:12]
    checksum = 0
    for i, digit in enumerate(body):
        checksum += int(digit) * (10 - i)
    remainder = checksum % 11
    check_digit = 11 - remainder
    if check_digit == 10: check_digit = 'X'
    elif check_digit == 11: check_digit = '0'
    else: check_digit = str(check_digit)
    return body + check_digit

def get_conn():
    return st.connection("gsheets", type=GSheetsConnection)

def get_books():
    try:
        conn = get_conn()
        df = conn.read(worksheet="books", ttl=0)
        expected = ["id", "title", "author", "category", "tags", "status", "notes", "cover_url", "read_date", "isbn", "created_at"]
        if df.empty or len(df.columns) == 0:
            return pd.DataFrame(columns=expected)
        if 'id' in df.columns:
            df['id'] = pd.to_numeric(df['id'], errors='coerce').fillna(0).astype(int)
        if 'created_at' in df.columns:
            df = df.sort_values("created_at", ascending=False)
        if 'isbn' in df.columns:
            df['isbn'] = df['isbn'].astype(str).str.replace(r'\.0$', '', regex=True)
        return df
    except Exception as e:
        return pd.DataFrame()

def get_categories():
    try:
        conn = get_conn()
        df = conn.read(worksheet="categories", ttl=0)
        if df.empty: return ["技術書", "ビジネス", "小説", "その他"]
        return df['name'].tolist()
    except:
        return ["技術書", "ビジネス", "小説", "その他"]

def add_book(title, author, category, tags_str, status, notes, cover_url, read_date, isbn):
    try:
        conn = get_conn()
        books_df = get_books()
        new_id = books_df['id'].max() + 1 if not books_df.empty else 1
        new_row = pd.DataFrame([{
            "id": new_id,
            "title": title,
            "author": author,
            "category": category,
            "tags": tags_str,
            "status": status,
            "notes": notes,
            "cover_url": cover_url,
            "read_date": read_date,
            "isbn": isbn,
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }])
        updated_df = pd.concat([books_df, new_row], ignore_index=True)
        conn.update(worksheet="books", data=updated_df)
        return True
    except Exception as e:
        st.error(f"Error: {e}")
        return False

def update_book(book_id, title, author, category, tags, status, notes, read_date):
    try:
        conn = get_conn()
        df = get_books()
        idx = df[df['id'] == book_id].index
        if len(idx) > 0:
            df.at[idx[0], 'title'] = title
            df.at[idx[0], 'author'] = author
            df.at[idx[0], 'category'] = category
            df.at[idx[0], 'tags'] = tags
            df.at[idx[0], 'status'] = status
            df.at[idx[0], 'notes'] = notes
            df.at[idx[0], 'read_date'] = read_date
            conn.update(worksheet="books", data=df)
            return True
    except Exception as e:
        st.error(f"Update Error: {e}")
        return False

def delete_book(book_id):
    try:
        conn = get_conn()
        df = get_books()
        df = df[df['id'] != book_id]
        conn.update(worksheet="books", data=df)
        return True
    except Exception as e:
        st.error(f"Delete Error: {e}")
        return False

# --- 3. API & Helpers ---
def get_google_books_data(isbn):
    try:
        url = f"https://www.googleapis.com/books/v1/volumes?q=isbn:{isbn}"
        r = requests.get(url, timeout=5)
        if r.status_code == 200:
            data = r.json()
            if "items" in data:
                info = data["items"][0]["volumeInfo"]
                return {
                    "title": info.get("title", ""),
                    "author": info.get("authors", [""])[0],
                    "cover_url": info.get("imageLinks", {}).get("thumbnail", "")
                }
    except: pass
    return None

def get_openbd_data(isbn):
    try:
        r = requests.get(f"https://api.openbd.jp/v1/get?isbn={isbn}", timeout=5)
        if r.status_code == 200:
            data = r.json()
            if data and data[0]:
                s = data[0]["summary"]
                return {
                    "title": s.get("title", ""),
                    "author": s.get("author", ""),
                    "cover_url": s.get("cover", "")
                }
    except: pass
    return None

def get_amazon_image_url(isbn):
    """Generate Amazon Image URL from ISBN"""
    isbn = str(isbn).replace('-', '').strip()
    if len(isbn) == 13:
        isbn10 = to_isbn10(isbn)
        if isbn10: return f"https://images-na.ssl-images-amazon.com/images/P/{isbn10}.09.LZZZZZZZ.jpg"
    elif len(isbn) == 10:
        return f"https://images-na.ssl-images-amazon.com/images/P/{isbn}.09.LZZZZZZZ.jpg"
    return ""

def resolve_best_image_url(isbn):
    # 1. Google
    g_data = get_google_books_data(isbn)
    if g_data and g_data.get("cover_url"): return g_data["cover_url"]
    
    # 2. OpenBD
    o_data = get_openbd_data(isbn)
    if o_data and o_data.get("cover_url"): return o_data["cover_url"]
    
    # 3. Amazon
    return get_amazon_image_url(isbn)

def fetch_book_info(isbn):
    """Unified Fetcher for Auto-Search"""
    data = None
    
    # 1. Try Google
    g_data = get_google_books_data(isbn)
    if g_data:
        data = g_data
    else:
        # 2. Try OpenBD
        o_data = get_openbd_data(isbn)
        if o_data:
            data = o_data

    # If we found metadata but no cover, try Amazon fallback
    if data and not data.get("cover_url"):
         data["cover_url"] = get_amazon_image_url(isbn)
         
    return data

def search_books_by_title(query, start_index=0):
    """Search books by title via Google Books API (Hybrid: Relevance + Newest)"""
    url = "https://www.googleapis.com/books/v1/volumes"
    results = []
    debug_log = ""
    raw_items = []
    
    try:
        # Route A: Specialized "Title" Search
        params_title = {
            "q": f"intitle:{query}",
            "maxResults": 40,
            "startIndex": start_index,
            "langRestrict": "ja",
            "printType": "books",
            "country": "JP",
            "orderBy": "relevance"
        }
        try:
            r_title = requests.get(url, params=params_title, timeout=5)
            if r_title.status_code == 200:
                data = r_title.json()
                if "items" in data: raw_items.extend(data["items"])
        except: pass

        # Route B: Standard Relevance (Backup)
        params_rel = params_title.copy()
        params_rel["q"] = query
        try:
            r_rel = requests.get(url, params=params_rel, timeout=5)
            if r_rel.status_code == 200:
                data = r_rel.json()
                if "items" in data: raw_items.extend(data["items"])
        except: pass

        # Process & Deduplicate
        unique_set = set()
        raw_results = []
        current_year = datetime.now().year
        search_keywords = re.split(r'[ 　]+', query.strip().lower())
        search_keywords = [k for k in search_keywords if k]

        for item in raw_items:
            info = item.get("volumeInfo", {})
            title = info.get("title", "")
            if not title: continue

            # Year logic
            pub_date = info.get("publishedDate", "")
            year = int(pub_date[:4]) if pub_date and pub_date[:4].isdigit() else 0
            if year < 1960: continue 

            # Relevance Check
            target_text = (title + " " + " ".join(info.get("authors", []))).lower()
            matches_count = sum(1 for k in search_keywords if k in target_text)
            if matches_count == 0: continue

            # Deduplication
            isbn = ""
            for ident in info.get("industryIdentifiers", []):
                if ident["type"] == "ISBN_13": isbn = ident["identifier"]
                elif ident["type"] == "ISBN_10" and not isbn: isbn = ident["identifier"]
                
            key = f"{title}_{info.get('authors', [])}"
            if key in unique_set: continue
            unique_set.add(key)
            
            cover_url = info.get("imageLinks", {}).get("thumbnail", "")
            if not cover_url and isbn:
                cover_url = get_amazon_image_url(isbn)
            
            raw_results.append({
                "title": title,
                "author": ", ".join(info.get("authors", ["Unknown"])),
                "publisher": info.get("publisher", ""),
                "publishedDate": f"{year}" if year else "",
                "year": year,
                "cover_url": cover_url,
                "isbn": isbn,
                "description": info.get("description", "")
            })
        
        # Simple Sort (Relevance by keyword match + Newest)
        raw_results.sort(key=lambda x: (sum(1 for k in search_keywords if k in (x['title']+x['author']).lower()), x['year']), reverse=True)
        results = raw_results

    except Exception as e:
        debug_log += f"Exception: {str(e)}"
        
    return results, debug_log

# --- 4. UI Components ---
PLACEHOLDER_IMG = "https://placehold.co/400x600/e0e0e0/999999?text=No+Image"

def render_book_card(row, is_mobile=False):
    # Prepare Data
    img_url = row['cover_url'] if row['cover_url'] and str(row['cover_url']) != 'nan' else PLACEHOLDER_IMG
    
    def safe_str(val):
        s = str(val).strip()
        return "" if s == 'nan' or s == 'None' else s

    title = safe_str(row['title'])
    author = safe_str(row['author'])
    category = safe_str(row['category'])
    status = safe_str(row['status'])
    
    tags_html = ""
    if isinstance(row['tags'], str) and row['tags'] and safe_str(row['tags']):
        tags = [t.strip() for t in row['tags'].split(',')]
        tags_html = "".join([f"<span class='tag-badge'>{t}</span>" for t in tags])
    
    note_content = safe_str(row['notes'])
    note_html = ""
    if note_content:
        note_html = f"<div class='note-box'>📝 {note_content}</div>"
    else:
        note_html = "<div style='margin-top:10px; opacity:0.6; font-size:0.8rem;'>（メモなし）</div>"

    # Glass Card HTML
    card_html = f"""
    <div class="glass-card">
        <div class="glass-card-img-box">
            <img src="{img_url}" class="glass-card-img">
        </div>
        <div class="glass-card-content">
            <div class="glass-card-title">{title}</div>
            <div class="glass-card-author">👤 {author}</div>
            <div style="margin-bottom:8px;">
                <span style="font-weight:600; font-size:0.9rem;">{category}</span> 
                <span style="opacity:0.7;"> | {status}</span>
            </div>
            <div style="margin-bottom:10px;">{tags_html}</div>
            {note_html}
        </div>
    </div>
    """
    st.markdown(card_html, unsafe_allow_html=True)
    
    # Edit Button
    btn_key = f"edit_{row['id']}_{'m' if is_mobile else 'p'}"
    if st.button("編集", key=btn_key):
        st.session_state["edit_target"] = row['id']
        st.rerun()

def render_preview_card(isbn, categories, key_suffix):
    if "preview_data" in st.session_state and st.session_state["preview_data"]:
        data = st.session_state["preview_data"]
        st.info("✅ 書籍が見つかりました")
        
        col1, col2 = st.columns([1, 3])
        with col1:
            img_url = data.get("cover_url") if data.get("cover_url") else PLACEHOLDER_IMG
            try:
                st.image(img_url, width=100)
            except:
                st.image(PLACEHOLDER_IMG, width=100)
        with col2:
            st.markdown(f"**{data['title']}**")
            st.caption(f"著者: {data['author']}")
            
            with st.form(key=f"confirm_add_{key_suffix}"):
                c_cat = st.selectbox("カテゴリ", categories)
                c_status = st.selectbox("状態", ["未読", "読書中", "読了"])
                c_point = st.text_area("ポイント", height=100)
                
                if st.form_submit_button("この本を登録する"):
                    if add_book(data['title'], data['author'], c_cat, "", c_status, c_point, data['cover_url'], "", isbn):
                        st.success("登録しました")
                        del st.session_state["preview_data"]
                        time.sleep(1)
                        st.rerun()

def render_edit_form(row, categories, key_suffix):
    with st.form(key=f"edit_form_{row['id']}_{key_suffix}"):
        st.markdown(f"#### 編集: {row['title']}")
        e_title = st.text_input("タイトル", row['title'])
        e_author = st.text_input("著者", row['author'])
        e_cat = st.selectbox("カテゴリ", categories, index=categories.index(row['category']) if row['category'] in categories else 0)
        e_status = st.selectbox("状態", ["未読", "読書中", "読了"], index=["未読", "読書中", "読了"].index(row['status']))
        e_notes = st.text_input("ポイント", row['notes']) 
        
        col1, col2, col3 = st.columns(3)
        with col1:
            if st.form_submit_button("保存"):
                update_book(row['id'], e_title, e_author, e_cat, row['tags'], e_status, e_notes, row['read_date'])
                st.session_state["edit_target"] = None
                st.rerun()
        with col2:
            if st.form_submit_button("キャンセル"):
                st.session_state["edit_target"] = None
                st.rerun()
        with col3:
            if st.form_submit_button("削除", type="primary"):
                delete_book(row['id'])
                st.session_state["edit_target"] = None
                st.success("削除しました")
                time.sleep(1)
                st.rerun()

def render_add_book_form(categories, key_suffix):
    with st.form(key=f"add_book_{key_suffix}"):
        n_isbn = st.text_input("ISBN (任意)")
        n_title = st.text_input("タイトル")
        n_author = st.text_input("著者")
        n_cat = st.selectbox("カテゴリ", categories)
        n_status = st.selectbox("状態", ["未読", "読書中", "読了"])
        
        if st.form_submit_button("登録"):
            c_url = ""
            if n_isbn:
                c_url = resolve_best_image_url(n_isbn)
                
            if add_book(n_title, n_author, n_cat, "", n_status, "", c_url, "", n_isbn):
                st.success("登録しました")
                time.sleep(1)
                st.rerun()

def draw_pc_ui(df, categories):
    """Render PC Exclusive UI"""
    # Logo
    try:
        st.sidebar.image("logo_pivot_white_final.png", use_container_width=True)
    except:
        st.sidebar.markdown(f"### 🏛️ 書籍DB (PC)")
    
    # --- View Control (Sidebar) - Removed from here, moved to main() ---
    
    # st.sidebar.markdown("---")
    
    # PC Search in Sidebar
    
    # PC Search in Sidebar
    st.sidebar.markdown("#### 🔍 新規登録検索")
    search_input = st.sidebar.text_input("ISBN または タイトル、著者名", key="pc_new_book_search")
    st.sidebar.caption("※タイトル検索は候補一覧が表示されます")
    
    if "search_page" not in st.session_state:
        st.session_state["search_page"] = 0
    
    if search_input:
        if "last_search_q" not in st.session_state or st.session_state["last_search_q"] != search_input:
             st.session_state["search_page"] = 0
             st.session_state["last_search_q"] = search_input
             
        current_key = f"{search_input}_{st.session_state['search_page']}"
        
        if "last_fetched_key" not in st.session_state or st.session_state["last_fetched_key"] != current_key:
            with st.spinner(f"検索中... (Page {st.session_state['search_page'] + 1})"):
                clean_input = search_input.replace("-", "").strip()
                if clean_input.isdigit() and (len(clean_input) == 10 or len(clean_input) == 13):
                    info = fetch_book_info(clean_input)
                    if info:
                        st.session_state["preview_data"] = info
                        if "isbn" not in st.session_state["preview_data"]: 
                             st.session_state["preview_data"]["isbn"] = clean_input
                        st.session_state["candidate_list"] = None
                    else:
                        st.sidebar.warning("見つかりませんでした")
                        st.session_state["preview_data"] = None
                else:
                    start_idx = st.session_state["search_page"] * 20
                    candidates, debug_msg = search_books_by_title(search_input, start_index=start_idx)
                    if candidates:
                        st.session_state["candidate_list"] = candidates
                        st.session_state["preview_data"] = None
                    else:
                        st.sidebar.warning(f"結果がありません")
                        st.session_state["candidate_list"] = None
            
            st.session_state["last_fetched_key"] = current_key
    
    # Display Candidates (if any)
    if st.session_state.get("candidate_list"):
        st.markdown(f"### 📚 検索結果 (Page {st.session_state['search_page'] + 1})")
        # CSS for Uniform Cards in Search
        st.markdown("""
        <style>
        .search-card-content {
            height: 280px;
            display: flex; /* ...CSS simplified for brevity... */
            flex-direction: column;
            overflow: hidden;
            background-color: rgba(255, 255, 255, 0.1); 
            border-radius: 12px;
            padding: 10px;
        }
        .search-card-img-box { height: 140px; display: flex; justify-content: center; }
        .search-card-img { max-height: 100%; max-width: 100%; object-fit: contain; }
        </style>
        """, unsafe_allow_html=True)
        
        candidates = st.session_state["candidate_list"]
        cols = st.columns(5) 
        for i, book in enumerate(candidates):
            with cols[i % 5]:
                 # ... Render Candidate ...
                 img_src = book.get("cover_url") if book.get("cover_url") else PLACEHOLDER_IMG
                 st.image(img_src, caption=book['title'][:20], use_container_width=True)
                 if st.button("選択", key=f"sel_cand_{i}", use_container_width=True):
                    st.session_state["preview_data"] = book
                    st.session_state["candidate_list"] = None
                    st.rerun()
        st.markdown("---")

    # Display Preview
    if st.session_state.get("preview_data"):
        st.markdown("### 📝 登録候補")
        target_isbn = st.session_state["preview_data"].get("isbn", "")
        render_preview_card(target_isbn, categories, "pc")
        st.markdown("---")

    # 2. Sidebar Filters
    st.sidebar.markdown("#### 📂 フィルタ")
    search_q = st.sidebar.text_input("キーワード検索", key="pc_search")
    cat_filter = st.sidebar.multiselect("カテゴリ", categories, key="pc_cat_filter")
    
    # Filter Logic
    filtered = df.copy()
    if search_q:
        filtered = filtered[filtered.apply(lambda r: search_q in str(r.values), axis=1)]
    if cat_filter:
        filtered = filtered[filtered['category'].isin(cat_filter)]
    
    # Main Content
    st.markdown(f"# 蔵書一覧 ({len(filtered)}冊)")
    
    for idx, row in filtered.iterrows():
        if st.session_state.get("edit_target") == row['id']:
            render_edit_form(row, categories, key_suffix="pc")
        else:
            render_book_card(row, is_mobile=False)
            
    # PC: Manual Add (Collapsed)
    with st.expander("➕ 手動登録フォーム"):
        render_add_book_form(categories, key_suffix="pc")

def draw_mobile_ui(df, categories):
    """Render Mobile Exclusive UI"""
    st.markdown("### 📱 蔵書一覧")
    
    # 1. Mobile: Camera Scanner (TOP PRIORITY)
    st.markdown("#### 📷 バーコード読取")
    show_camera = st.checkbox("カメラを起動する", key="toggle_camera")
    
    if show_camera and PYZBAR_AVAILABLE:
        img_file = st.camera_input("バーコードを写してください", key="mob_cam")
        if img_file:
            try:
                img = Image.open(img_file)
                decoded = decode(img)
                if decoded:
                    isbn = decoded[0].data.decode('utf-8')
                    st.success(f"ISBN: {isbn}")
                    info = fetch_book_info(isbn)
                    if info:
                        st.session_state["preview_data"] = info
                        render_preview_card(isbn, categories, "mob_cam")
            except:
                st.error("読み取れませんでした")
    elif show_camera and not PYZBAR_AVAILABLE:
        st.warning("⚠️ バーコード読取ライブラリ(zbar)が見つかりません。")
    
    # 2. Results / List
    st.markdown("---")
    
    with st.expander("🔍 検索・フィルタ", expanded=True):
        m_search = st.text_input("キーワード", key="mob_search")
        m_cat = st.selectbox("カテゴリ", ["すべて"] + categories, key="mob_cat")
    
    filtered = df.copy()
    if m_search:
        filtered = filtered[filtered.apply(lambda r: m_search in str(r.values), axis=1)]
    if m_cat != "すべて":
        filtered = filtered[filtered['category'] == m_cat]

    st.caption(f"{len(filtered)} 冊")
    
    for idx, row in filtered.iterrows():
        if st.session_state.get("edit_target") == row['id']:
            render_edit_form(row, categories, key_suffix="mob")
        else:
            render_book_card(row, is_mobile=True)
            
    with st.expander("➕ 手動登録"):
        render_add_book_form(categories, key_suffix="mob")


# --- Main Application Logic ---
def main():
    try:
        df = get_books()
    except Exception as e:
        st.error(f"Data Load Error: {e}")
        df = pd.DataFrame()

    categories = get_categories()
    
    categories = get_categories()
    
    # --- Robust View Control (Sidebar) ---
    # Defined HERE in main scope so it's available for logic below
    with st.sidebar:
        st.markdown("---")
        with st.expander("🖥️ Display Mode", expanded=False):
            view_mode = st.radio("表示モード", ["Auto (自動)", "PC固定", "スマホ固定"], index=0, key="view_mode_main_selector")
        st.sidebar.markdown("---")

    # Render based on selection
    # 1. PC UI
    if view_mode in ["Auto (自動)", "PC固定"]:
        with st.container():
            # Marker for CSS visibility control (Only active in Auto mode)
            if view_mode == "Auto (自動)":
                st.markdown('<div class="pc-view-marker"></div>', unsafe_allow_html=True)
            
            draw_pc_ui(df, categories)

    # 2. Mobile UI
    if view_mode in ["Auto (自動)", "スマホ固定"]:
        with st.container():
            # Marker for CSS visibility control (Only active in Auto mode)
            if view_mode == "Auto (自動)":
                st.markdown('<div class="mobile-view-marker"></div>', unsafe_allow_html=True)
                
            draw_mobile_ui(df, categories)

if __name__ == "__main__":
    main()
