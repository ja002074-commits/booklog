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

try:
    from pyzbar.pyzbar import decode
    PYZBAR_AVAILABLE = True
except ImportError:
    PYZBAR_AVAILABLE = False

# --- 1. Settings & CSS Styling ---
st.set_page_config(layout="wide", page_title="読書DB", page_icon="🏛️")

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

# Custom CSS with Device Separation
st.markdown("""
<style>
/* 1. Typography & Atmosphere */
@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+JP:wght@300;400;500;700&display=swap');

.stApp {
    background: linear-gradient(180deg, #FDFBF7 0%, #F2F0EB 100%);
    color: #444444;
    font-family: "Hiragino Kaku Gothic ProN", "Noto Sans JP", sans-serif;
    letter-spacing: 0.03em;
}

/* 2. Headings */
h1, h2, h3 {
    font-family: "Hiragino Kaku Gothic ProN", "Noto Sans JP", serif !important;
    color: #333333 !important;
    font-weight: 500 !important;
}

h1 {
    font-size: 2.2rem !important;
    border-bottom: 1px solid #D8D2C0;
    padding-bottom: 15px;
    margin-bottom: 30px;
}

/* 3. Device Separation Logic */
@media (max-width: 767px) {
    .pc-only { display: none !important; }
    .mobile-only { display: block !important; }
    
    /* Mobile Adjustments */
    .stApp { padding-top: 20px; }
    h1 { font-size: 1.5rem !important; }
}

@media (min-width: 768px) {
    .pc-only { display: block !important; }
    .mobile-only { display: none !important; }
}

/* 4. Common Inputs Styling (MUJI Minimalist) */
div[data-baseweb="select"] > div,
div[data-baseweb="input"] > div {
    background-color: #FFFFFF !important;
    border: 1px solid #CCCCCC !important;
    border-radius: 4px !important;
    box-shadow: none !important;
    padding: 0 !important;
}

input, textarea, select {
    border: none !important; 
    box-shadow: none !important;
    background-color: transparent !important;
}

div[data-baseweb="select"] > div > div, 
div[data-baseweb="select"] > div span {
    border: none !important;
    background-color: transparent !important;
    margin: 0 !important;
    box-shadow: none !important;
}

div[data-baseweb="select"] > div > div:last-child > div:first-child {
     display: none !important;
}

div[data-baseweb="input"] > div:focus-within,
div[data-baseweb="select"] > div:focus-within {
    border-color: #8C7B70 !important;
    outline: 1px solid #8C7B70 !important;
}

div[data-baseweb="select"] svg {
    fill: #999999 !important;
}

/* 5. Buttons */
.stButton > button {
    background-color: #FFFFFF;
    border: 1px solid #C0C0C0;
    color: #555555;
    border-radius: 4px;
    font-weight: 400;
    padding: 0.5rem 1.2rem;
    transition: all 0.3s ease;
    box-shadow: 0 1px 2px rgba(0,0,0,0.05);
}
.stButton > button:hover {
    background-color: #8C7B70;
    color: #FFFFFF;
    border-color: #8C7B70;
    box-shadow: 0 2px 5px rgba(0,0,0,0.1);
}

/* 6. Layout */
.note-box {
    background: linear-gradient(to right bottom, #FFFFFF, #FAFAFA);
    border: 1px solid #E0E0E0;
    border-left: 4px solid #9E2A2B;
    padding: 20px;
    color: #444444;
    border-radius: 4px;
    margin-bottom: 20px;
    box-shadow: 0 2px 10px rgba(0,0,0,0.03);
}

.tag-badge {
    background-color: #F0EFE9;
    color: #555555;
    border: 1px solid #E0E0E0;
    border-radius: 4px;
    padding: 3px 10px;
    font-size: 0.8rem;
}

img {
    border-radius: 2px;
    box-shadow: 0 4px 12px rgba(0,0,0,0.08); /* Soft floating shadow */
    border: none;
}
</style>
""", unsafe_allow_html=True)

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

def update_cover_url_db(book_id, new_url):
    try:
        conn = get_conn()
        df = get_books()
        idx = df[df['id'] == book_id].index
        if len(idx) > 0:
            df.at[idx[0], 'cover_url'] = new_url
            conn.update(worksheet="books", data=df)
    except: pass

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

def resolve_best_image_url(isbn):
    # 1. Google
    g_data = get_google_books_data(isbn)
    if g_data and g_data.get("cover_url"): return g_data["cover_url"]
    
    # 2. OpenBD
    o_data = get_openbd_data(isbn)
    if o_data and o_data.get("cover_url"): return o_data["cover_url"]
    
    # 3. Amazon
    isbn = str(isbn).replace('-', '').strip()
    if len(isbn) == 13:
        isbn10 = to_isbn10(isbn)
        if isbn10: return f"https://images-na.ssl-images-amazon.com/images/P/{isbn10}.09.LZZZZZZZ.jpg"
    elif len(isbn) == 10:
        return f"https://images-na.ssl-images-amazon.com/images/P/{isbn}.09.LZZZZZZZ.jpg"
    
    return ""

def fetch_book_info(isbn):
    """Unified Fetcher for Auto-Search"""
    # 1. Try Google
    data = get_google_books_data(isbn)
    if data: return data
    # 2. Try OpenBD
    data = get_openbd_data(isbn)
    if data: return data
    return None

# --- UI COMPONENTS ---

def render_book_card(row, is_mobile=False):
    with st.container():
        if is_mobile:
            c_img, c_info = st.columns([1, 2])
        else:
            c_img, c_info, c_note = st.columns([1, 2, 3])
            
        with c_img:
            if row['cover_url']:
                st.image(row['cover_url'], use_container_width=True)
            else:
                st.markdown("<div style='height:120px; background:#eee; display:flex; align-items:center; justify-content:center; color:#999; font-size:0.8rem;'>No Image</div>", unsafe_allow_html=True)
        
        with c_info:
            st.markdown(f"### {row['title']}")
            st.caption(f"著者: {row['author']}")
            if isinstance(row['tags'], str) and row['tags']:
                tags = [t.strip() for t in row['tags'].split(',')]
                t_html = "".join([f"<span class='tag-badge'>{t}</span>" for t in tags])
                st.markdown(t_html, unsafe_allow_html=True)
            st.markdown(f"**{row['category']}** | {row['status']}")
            
            btn_key = f"edit_{row['id']}_{'m' if is_mobile else 'p'}"
            if st.button("編集", key=btn_key):
                st.session_state["edit_target"] = row['id']
                st.rerun()

        if not is_mobile:
            with c_note:
                st.caption("要点・メモ")
                note_content = row['notes'] if isinstance(row['notes'], str) and row['notes'].strip() != 'nan' else "（メモなし）"
                if note_content == "（メモなし）":
                     st.markdown(f"<div style='color:#999; font-style:italic;'>{note_content}</div>", unsafe_allow_html=True)
                else:
                     st.markdown(f"<div class='note-box'>{note_content}</div>", unsafe_allow_html=True)

        if is_mobile:
             st.caption("要点・メモ")
             st.info(row['notes'] if isinstance(row['notes'], str) and row['notes'].strip() != 'nan' else "（メモなし）")

        st.markdown("---")

def render_preview_card(isbn, categories, key_suffix):
    """Show preview of book found via ISBN before adding"""
    if "preview_data" in st.session_state and st.session_state["preview_data"]:
        data = st.session_state["preview_data"]
        st.info("✅ 書籍が見つかりました")
        
        col1, col2 = st.columns([1, 3])
        with col1:
            if data.get("cover_url"):
                st.image(data["cover_url"], width=100)
            else:
                st.write("No Image")
        with col2:
            st.markdown(f"**{data['title']}**")
            st.caption(f"著者: {data['author']}")
            
            # Registration Form inside Preview
            with st.form(key=f"confirm_add_{key_suffix}"):
                c_cat = st.selectbox("カテゴリ", categories)
                c_status = st.selectbox("状態", ["未読", "読書中", "読了"])
                if st.form_submit_button("この本を登録する"):
                    if add_book(data['title'], data['author'], c_cat, "", c_status, "", data['cover_url'], "", isbn):
                        st.success("登録しました")
                        del st.session_state["preview_data"]
                        time.sleep(1)
                        st.rerun()

def draw_pc_ui(df, categories):
    """Render PC Exclusive UI"""
    st.sidebar.markdown(f"### 🏛️ 書籍DB (PC)")
    
    # 1. PC: Auto-Search via ISBN
    st.sidebar.markdown("#### 🔍 ISBN自動検索")
    isbn_input = st.sidebar.text_input("ISBNを入力 (Enter)", key="pc_isbn_search")
    
    # Search Logic
    if isbn_input:
        # Avoid re-fetching if same ISBN
        if "last_isbn" not in st.session_state or st.session_state["last_isbn"] != isbn_input:
            with st.spinner("検索中..."):
                info = fetch_book_info(isbn_input)
                if info:
                    st.session_state["preview_data"] = info
                    st.session_state["last_isbn"] = isbn_input
                else:
                    st.sidebar.warning("見つかりませんでした")
                    st.session_state["preview_data"] = None
    
    # Show Preview in Main Area if exists
    if "preview_data" in st.session_state and st.session_state["preview_data"]:
        render_preview_card(isbn_input, categories, "pc")
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
    st.markdown("### 📱 読書録")
    
    # 1. Mobile: Camera Scanner (TOP PRIORITY)
    if PYZBAR_AVAILABLE:
        st.markdown("#### 📷 バーコード読取")
        img_file = st.camera_input("バーコードを写してください", key="mob_cam")
        if img_file:
            try:
                img = Image.open(img_file)
                decoded = decode(img)
                if decoded:
                    isbn = decoded[0].data.decode('utf-8')
                    st.success(f"ISBN: {isbn}")
                    # Auto-check logic
                    info = fetch_book_info(isbn)
                    if info:
                        st.session_state["preview_data"] = info
                        # Mobile Preview
                        render_preview_card(isbn, categories, "mob_cam")
            except:
                st.error("読み取れませんでした")
    
    # 2. Results / List
    st.markdown("---")
    
    with st.expander("🔍 検索・フィルタ"):
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

def render_edit_form(row, categories, key_suffix):
    with st.form(key=f"edit_form_{row['id']}_{key_suffix}"):
        st.markdown(f"#### 編集: {row['title']}")
        e_title = st.text_input("タイトル", row['title'])
        e_author = st.text_input("著者", row['author'])
        e_cat = st.selectbox("カテゴリ", categories, index=categories.index(row['category']) if row['category'] in categories else 0)
        e_status = st.selectbox("状態", ["未読", "読書中", "読了"], index=["未読", "読書中", "読了"].index(row['status']))
        e_notes = st.text_area("メモ", row['notes'])
        
        col1, col2 = st.columns(2)
        with col1:
            if st.form_submit_button("保存"):
                update_book(row['id'], e_title, e_author, e_cat, row['tags'], e_status, e_notes, row['read_date'])
                st.session_state["edit_target"] = None
                st.rerun()
        with col2:
            if st.form_submit_button("キャンセル"):
                st.session_state["edit_target"] = None
                st.rerun()

def render_add_book_form(categories, key_suffix):
    with st.form(key=f"add_book_{key_suffix}"):
        n_isbn = st.text_input("ISBN (任意)")
        n_title = st.text_input("タイトル")
        n_author = st.text_input("著者")
        n_cat = st.selectbox("カテゴリ", categories)
        n_status = st.selectbox("状態", ["未読", "読書中", "読了"])
        
        if st.form_submit_button("登録"):
            # Check if ISBN is provided, try to get cover
            c_url = ""
            if n_isbn:
                c_url = resolve_best_image_url(n_isbn)
                
            if add_book(n_title, n_author, n_cat, "", n_status, "", c_url, "", n_isbn):
                st.success("登録しました")
                time.sleep(1)
                st.rerun()

# --- Main Application Logic ---
def main():
    df = get_books()
    categories = get_categories()
    
    st.markdown('<div class="pc-only">', unsafe_allow_html=True)
    draw_pc_ui(df, categories)
    st.markdown('</div>', unsafe_allow_html=True)
    
    st.markdown('<div class="mobile-only">', unsafe_allow_html=True)
    draw_mobile_ui(df, categories)
    st.markdown('</div>', unsafe_allow_html=True)

if __name__ == "__main__":
    main()
