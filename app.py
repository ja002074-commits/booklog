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
    // Enforce Japanese lang attribute
    function setLang() {
        document.documentElement.lang = "ja";
    }
    setLang();
    // Repeat just in case Streamlit overwrites it
    setInterval(setLang, 1000);
</script>
""", unsafe_allow_html=True)

# Custom CSS (MUJI Minimalist Report Style)
st.markdown("""
<style>
/* 1. Typography & Grid */
@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+JP:wght@300;400;500;700&display=swap');

.stApp {
    background-color: #FFFFFF;
    color: #333333;
    font-family: "Hiragino Kaku Gothic ProN", "Hiragino Sans", "Noto Sans JP", Arial, sans-serif;
    line-height: 1.8; /* Breathable spacing */
}

/* 2. Headings - Pure Hierarchy */
h1, h2, h3, h4, h5, h6 {
    font-family: "Hiragino Kaku Gothic ProN", "Noto Sans JP", sans-serif !important;
    font-weight: 700 !important;
    color: #333333 !important;
    margin-bottom: 1.5rem !important;
    letter-spacing: 0.05em;
}

h1 {
    font-size: 2.4rem !important;
    border: none !important;
    margin-top: 1rem;
}

h3 {
    font-size: 1.3rem !important;
    margin-top: 2rem !important;
}

/* 3. Sidebar - Seamless & Clean */
section[data-testid="stSidebar"] {
    background-color: #F8F8F8; /* Very pale grey */
    border-right: 1px solid #EEEEEE;
}
section[data-testid="stSidebar"] .block-container {
    padding-top: 3rem;
}

/* 4. Inputs - Functional Beauty (No shadow, just lines) */
div[data-baseweb="select"] > div,
div[data-baseweb="input"] > div,
input, textarea, select {
    background-color: #FFFFFF !important;
    color: #333333 !important;
    border: 1px solid #DDDDDD !important;
    border-radius: 0px !important;
    font-size: 0.95rem;
    padding: 0.5rem;
}

/* Focus: MUJI Red Accent only on interaction */
div[data-baseweb="input"] > div:focus-within,
div[data-baseweb="select"] > div:focus-within {
    border-color: #7F0019 !important;
    box-shadow: none !important;
    outline: 1px solid #7F0019 !important;
}

/* Remove artifact icons */
div[data-baseweb="select"] svg {
    fill: #999999 !important;
}

/* 5. Buttons - Minimalist */
.stButton > button {
    background-color: #FFFFFF;
    border: 1px solid #CCCCCC;
    color: #333333;
    border-radius: 0px;
    font-weight: 500;
    padding: 0.6rem 1.5rem;
    transition: all 0.2s ease;
    box-shadow: none;
}
.stButton > button:hover {
    background-color: #7F0019;
    color: #FFFFFF;
    border-color: #7F0019;
}

/* 6. Cards & Layout (The "Report" Feel) */
/* Reset Expander style to be seamless */
.streamlit-expanderHeader {
    background-color: #FFFFFF;
    border: none;
    border-bottom: 1px solid #EEEEEE;
    color: #333333;
    font-size: 0.9rem;
    border-radius: 0;
}
div[data-testid="stExpander"] {
    border: none;
    box-shadow: none;
    background-color: #FFFFFF;
}

/* Note Box - The "Main Content" */
.note-box {
    background-color: #F9F9F9; /* Slight contrast for content area */
    border: none;
    border-left: 3px solid #7F0019; /* The only strong accent */
    padding: 24px;
    color: #444444;
    border-radius: 0px;
    margin-bottom: 24px;
    font-size: 0.95rem;
    line-height: 2.0;
}

/* Tags - Minimal labels */
.tag-badge {
    display: inline-block;
    padding: 4px 10px;
    margin: 0 6px 6px 0;
    background: #FFFFFF;
    color: #666666;
    font-size: 0.8rem;
    border: 1px solid #E0E0E0;
    border-radius: 0px;
}

/* Horizontal List Divider */
hr {
    border: 0;
    border-top: 1px solid #EEEEEE;
    margin: 40px 0;
}

/* Images - Clean, no border/shadow unless necessary */
img {
    border: 1px solid #F0F0F0;
}

/* Responsive Utilities */
@media (min-width: 768px) {
    div[data-testid="stExpander"]:has(div#mobile-only-marker) {
        display: none !important;
    }
}
</style>
""", unsafe_allow_html=True)

def to_isbn10(isbn13):
    """Convert ISBN13 to ISBN10."""
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

# --- Google Sheets DB ---
def get_conn():
    return st.connection("gsheets", type=GSheetsConnection)

def get_books():
    try:
        conn = get_conn()
        df = conn.read(worksheet="books", ttl=0)
        # Verify columns and init if empty
        expected = ["id", "title", "author", "category", "tags", "status", "notes", "cover_url", "read_date", "isbn", "created_at"]
        if df.empty or len(df.columns) == 0:
            return pd.DataFrame(columns=expected)
        
        # Ensure ID is numeric
        if 'id' in df.columns:
            df['id'] = pd.to_numeric(df['id'], errors='coerce').fillna(0).astype(int)
        
        # Ensure created_at consistency
        if 'created_at' in df.columns:
            df = df.sort_values("created_at", ascending=False)
            
        # Clean ISBNs (handle floats)
        if 'isbn' in df.columns:
            df['isbn'] = df['isbn'].astype(str).str.replace(r'\.0$', '', regex=True)
            
        return df
    except Exception as e:
        # If sheet doesn't exist or other error
        st.error(f"DB Error (Books): {e}")
        return pd.DataFrame()

def get_categories():
    try:
        conn = get_conn()
        df = conn.read(worksheet="categories", ttl=0)
        if df.empty: return ["技術書", "ビジネス", "小説", "その他"]
        return df['name'].tolist()
    except:
        return ["技術書", "ビジネス", "小説", "その他"]

def add_category(name):
    try:
        conn = get_conn()
        df = conn.read(worksheet="categories", ttl=0)
        new_row = pd.DataFrame([{"name": name}])
        updated = pd.concat([df, new_row], ignore_index=True)
        conn.update(worksheet="categories", data=updated)
        return True
    except Exception as e:
        st.error(f"Category Error: {e}")
        return False

def delete_category(name):
    try:
        conn = get_conn()
        df = conn.read(worksheet="categories", ttl=0)
        df = df[df['name'] != name]
        conn.update(worksheet="categories", data=df)
    except: pass

def add_book(title, author, category, tags, status, notes, cover_url, read_date, isbn):
    conn = get_conn()
    df = get_books()
    
    # ID Generation
    new_id = 1
    if not df.empty and 'id' in df.columns:
        ids = pd.to_numeric(df['id'], errors='coerce').fillna(0)
        if not ids.empty: new_id = int(ids.max()) + 1
    
    new_data = {
        "id": new_id,
        "title": title,
        "author": author,
        "category": category,
        "tags": tags,
        "status": status,
        "notes": notes,
        "cover_url": cover_url,
        "read_date": read_date,
        "isbn": isbn,
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    
    updated = pd.concat([df, pd.DataFrame([new_data])], ignore_index=True)
    conn.update(worksheet="books", data=updated)

def update_book(book_id, title, author, category, tags, status, notes, read_date):
    conn = get_conn()
    df = get_books()
    
    # Cast ID for safe comparison
    df['id'] = pd.to_numeric(df['id'], errors='coerce').fillna(0).astype(int)
    
    idx = df[df['id'] == int(book_id)].index
    if not idx.empty:
        i = idx[0]
        df.at[i, 'title'] = title
        df.at[i, 'author'] = author
        df.at[i, 'category'] = category
        df.at[i, 'tags'] = tags
        df.at[i, 'status'] = status
        df.at[i, 'notes'] = notes
        df.at[i, 'read_date'] = read_date
        conn.update(worksheet="books", data=df)

def update_book_cover(book_id, new_cover_url):
    conn = get_conn()
    df = get_books()
    df['id'] = pd.to_numeric(df['id'], errors='coerce').fillna(0).astype(int)
    
    idx = df[df['id'] == int(book_id)].index
    if not idx.empty:
        df.at[idx[0], 'cover_url'] = new_cover_url
        conn.update(worksheet="books", data=df)

def delete_book(book_id):
    conn = get_conn()
    df = get_books()
    df['id'] = pd.to_numeric(df['id'], errors='coerce').fillna(0).astype(int)
    df = df[df['id'] != int(book_id)]
    conn.update(worksheet="books", data=df)

# --- External APIs: Enhanced Image Retrieval ---
def fetch_book_data_with_image(isbn):
    """
    Fetch book data using ISBN.
    Priority for Image:
    1. Google Books (High quality if available)
    2. OpenBD (Alternative)
    3. Amazon (Fallback)
    
    Returns dict: {title, author, notes, cover_url, isbn}
    """
    
    # Clean ISBN
    isbn = str(isbn).replace('-', '').strip()
    # Normalize: Extract digits only
    isbn = "".join(filter(str.isdigit, isbn))
    
    # 1. Fetch Basic Info & Google Image
    info_dict = {"title": "", "author": "", "notes": "", "cover_url": "", "isbn": isbn}
    
    # Try Google Books First (for Metadata + Image)
    google_data = get_google_books_data(isbn)
    if google_data:
        info_dict.update(google_data)
        
    # Try OpenBD (Overwrite metadata if Google failed, or fill gaps)
    # OpenBD often has good Japanese metadata
    openbd_data = get_openbd_data(isbn)
    if openbd_data:
        if not info_dict["title"]: info_dict.update(openbd_data)
        # If Google didn't have cover but OpenBD does, use OpenBD
        if not info_dict["cover_url"] and openbd_data["cover_url"]:
            info_dict["cover_url"] = openbd_data["cover_url"]
            
    # Force notes to be empty as per user request
    info_dict["notes"] = ""

    # 3. Amazon Fallback for Image
    if not info_dict["cover_url"]:
        if len(isbn) == 13:
            isbn10 = to_isbn10(isbn)
            if isbn10:
                amazon_url = f"https://images-na.ssl-images-amazon.com/images/P/{isbn10}.09.LZZZZZZZ.jpg"
                info_dict["cover_url"] = amazon_url
        elif len(isbn) == 10:
             info_dict["cover_url"] = f"https://images-na.ssl-images-amazon.com/images/P/{isbn}.09.LZZZZZZZ.jpg"

    return info_dict

def get_google_books_data(isbn):
    try:
        url = f"https://www.googleapis.com/books/v1/volumes?q=isbn:{isbn}"
        resp = requests.get(url)
        if resp.status_code == 200:
            data = resp.json()
            if "items" in data:
                info = data["items"][0].get("volumeInfo", {})
                return {
                    "title": info.get("title", ""),
                    "author": ", ".join(info.get("authors", [])),
                    "notes": info.get("description", ""),
                    "cover_url": info.get("imageLinks", {}).get("thumbnail", "")
                }
    except Exception as e:
        st.warning(f"Google Books APIエラー: {e}")
    return None

def get_openbd_data(isbn):
    try:
        url = f"https://api.openbd.jp/v1/get?isbn={isbn}"
        resp = requests.get(url)
        if resp.status_code == 200:
            data = resp.json()
            if data and data[0]:
                summary = data[0].get('summary', {})
                # Safely get description
                desc = ""
                try:
                    desc = data[0].get('onix', {}).get('CollateralDetail', {}).get('TextContent', [{}])[0].get('Text', '')
                except: pass
                
                return {
                    "title": summary.get('title', ''),
                    "author": summary.get('author', ''),
                    "notes": desc,
                    "cover_url": summary.get('cover', '')
                }
    except Exception as e:
        st.warning(f"OpenBDエラー: {e}")
    return None

# Only for fetching image URL specifically (for re-fetch logic)
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

import cv2
import numpy as np

def decode_image_isbn(image):
    """
    Hybrid Barcode Scanner with OpenCV Preprocessing:
    1. Try Original (PIL).
    2. Try OpenCV Grayscale.
    3. Try OpenCV Thresholding (Binarization).
    4. Try AI (Gemini) if available.
    """
    results = set()
    
    # helper
    def scan_frame(frame_img):
        if not PYZBAR_AVAILABLE: return None
        try:
            decoded = decode(frame_img)
            for obj in decoded:
                if obj.type == 'EAN13':
                    return obj.data.decode('utf-8')
        except: pass
        return None

    # 1. PIL Original
    res = scan_frame(image)
    if res: return res

    # Convert to OpenCV format
    try:
        img_np = np.array(image.convert('RGB')) 
        # Convert RGB to BGR
        img_cv = img_np[:, :, ::-1].copy()
    except:
        return None

    # 2. Grayscale
    gray = cv2.cvtColor(img_cv, cv2.COLOR_BGR2GRAY)
    res = scan_frame(gray)
    if res: return res

    # 3. Thresholding (Binarization) - Good for strong shadows
    _, thresh = cv2.threshold(gray, 128, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU)
    res = scan_frame(thresh)
    if res: return res
    
    # 4. Sharpening
    # (Skip simple sharpening, rely on crop/rotate combinations below)

    # --- Advanced Multi-Pass Scan ---
    attempts = []
    
    # helper to add image versions
    h, w = img_cv.shape[:2]
    
    # A. Rotation (0, 90, 270)
    img_90 = cv2.rotate(img_cv, cv2.ROTATE_90_CLOCKWISE)
    
    # B. Central Crop (Zoom effect) - Focus on center 50%
    cy, cx = h // 2, w // 2
    ch, cw = h // 2, w // 2
    y1, x1 = cy - ch//2, cx - cw//2
    img_crop = img_cv[y1:y1+ch, x1:x1+cw]
    
    # Create grayscale versions
    gray_full = cv2.cvtColor(img_cv, cv2.COLOR_BGR2GRAY)
    gray_90 = cv2.cvtColor(img_90, cv2.COLOR_BGR2GRAY)
    gray_crop = cv2.cvtColor(img_crop, cv2.COLOR_BGR2GRAY)
    
    # Create Threshold versions
    _, thresh_full = cv2.threshold(gray_full, 128, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU)
    _, thresh_90 = cv2.threshold(gray_90, 128, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU)
    _, thresh_crop = cv2.threshold(gray_crop, 128, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU)

    # Queue attempts (Priority: Crop -> Full -> 90 -> Thresholds)
    # Crop is often best for focused scanning on phone
    attempts.extend([gray_crop, thresh_crop, gray_full, thresh_full, gray_90, thresh_90])
    
    for i, frame in enumerate(attempts):
        res = scan_frame(frame)
        if res: return res

    # 5. AI Scan (Gemini Fallback)
    api_key = st.session_state.get("gemini_api_key", "")
    
    if not PYZBAR_AVAILABLE:
         # Log only if not found
         pass
         
    if api_key:
        try:
            genai.configure(api_key=api_key)
            model = genai.GenerativeModel('gemini-1.5-flash')
            # Use original high-res image for AI
            prompt = """
            Read the EAN-13 barcode (ISBN) from this image. 
            Output ONLY the 13-digit number starting with 978. 
            If unreadable, output NOTHING.
            """
            resp = model.generate_content([prompt, image])
            text = resp.text.strip()
            digits = "".join(filter(str.isdigit, text))
            
            # Robust Extraction
            matches = re.findall(r'978\d{10}', digits)
            if matches:
                st.success(f"AIスキャン成功: {matches[0]}")
                return matches[0]
                
            if len(digits) == 13 and digits.startswith("978"):
                st.success(f"AIスキャン成功: {digits}")
                return digits
                
        except Exception as e:
            st.warning(f"AI解析エラー: {e}")
    else:
        # If no result and no API Key
        # st.warning("バーコード検出失敗。設定からGemini APIキーを入れるとAI解析が可能です。")
        pass
            
    return None

# init_db() removed for Cloud

# --- Components ---
def render_registration_form(parent, key_prefix="sidebar", enable_camera=True):
    if "gemini_api_key" not in st.session_state:
        st.session_state["gemini_api_key"] = os.environ.get("GEMINI_API_KEY", "")
        
    for k in ["title", "author", "category", "tags", "notes", "cover_url", "isbn"]:
        if f"form_{k}" not in st.session_state: st.session_state[f"form_{k}"] = ""

    def update_form_state(data):
        # Update backing store
        st.session_state["form_title"] = data.get("title", "")
        st.session_state["form_author"] = data.get("author", "")
        st.session_state["form_notes"] = data.get("notes", "")
        st.session_state["form_cover_url"] = data.get("cover_url", "")
        st.session_state["form_isbn"] = data.get("isbn", "")
        if "tags" in data: st.session_state["form_tags"] = data.get("tags", "")
        if "category" in data and data["category"] in get_categories(): 
             st.session_state["form_category"] = data["category"]

        # Update Widget Keys directly to force refresh
        st.session_state[f"{key_prefix}_title"] = data.get("title", "")
        st.session_state[f"{key_prefix}_author"] = data.get("author", "")
        st.session_state[f"{key_prefix}_notes"] = data.get("notes", "")
        st.session_state[f"{key_prefix}_cover"] = data.get("cover_url", "")
        st.session_state[f"{key_prefix}_isbn"] = data.get("isbn", "")
        if "tags" in data: st.session_state[f"{key_prefix}_tags"] = data.get("tags", "")
        if "category" in data and data["category"] in get_categories():
             st.session_state[f"{key_prefix}_cat"] = data["category"]

    # Settings (AI Key) - No form needed, instant update
    if enable_camera:
        with st.expander("⚙️ 設定 (AIスキャン用)", expanded=False):
             api_key = st.text_input("Gemini API Key", value=st.session_state.get("gemini_api_key", ""), type="password", key=f"{key_prefix}_api_key_input", help="AIフォールバック利用に必要です")
             if api_key: st.session_state["gemini_api_key"] = api_key

    # Dynamic Tabs
    tabs_list = ["⌨️ 手動・ISBN"]
    if enable_camera: tabs_list.append("📷 バーコード読み取り")
    tabs_objs = parent.tabs(tabs_list)
    
    with tabs_objs[0]:
        with parent.form(f"{key_prefix}_isbn_manual_form"):
             isbn_val = st.text_input("ISBN検索", key=f"{key_prefix}_isbn_input", placeholder="978...")
             if st.form_submit_button("検索"):
                 if isbn_val:
                    info = fetch_book_data_with_image(isbn_val)
                    if info:
                        update_form_state(info)
                        st.success("見つかりました！")
                        st.rerun()
                    else: st.error("見つかりません")

    if enable_camera and len(tabs_objs) > 1:
        with tabs_objs[1]:
            st.caption("バーコードを撮影すると、自動でISBNを読み取り書籍情報を検索します。")
            
            # Camera container for stability
            cam_container = st.empty()
            cam_bar = cam_container.camera_input("バーコードを撮影", key=f"{key_prefix}_cam_bar")
            
            if cam_bar:
                proc_key_bar = f"processed_bar_{key_prefix}"
                if proc_key_bar not in st.session_state: st.session_state[proc_key_bar] = None
                
                if st.session_state[proc_key_bar] != cam_bar.name:
                    try:
                        with st.spinner("解析中..."):
                            img = Image.open(cam_bar)
                            isbn_res = decode_image_isbn(img)
                            
                            if isbn_res:
                                st.success(f"ISBN読み取り成功: {isbn_res}")
                                info = fetch_book_data_with_image(isbn_res)
                                
                                if not info:
                                     info = {"title": "", "author": "", "notes": "", "cover_url": "", "isbn": isbn_res}
                                     st.warning("書籍情報が見つかりませんでしたが、ISBNは入力しました。")
                                else:
                                     st.success(f"書籍データ取得: {info.get('title', 'タイトル不明')}")
        
                                update_form_state(info)
                                st.session_state[proc_key_bar] = cam_bar.name
                                
                                # Wait for browser to process DOM removal safely
                                time.sleep(1.0) 
                                st.rerun()
                            else:
                                st.error("バーコードを読み取れませんでした。")
                                st.session_state[proc_key_bar] = cam_bar.name
                    except Exception as e:
                        st.warning(f"エラーが発生しました。もう一度試してください。 ({e})")
                        # Prevent crash loop
                        st.session_state[proc_key_bar] = cam_bar.name

    parent.markdown("---")
    cats = get_categories()
    
    with parent.form(f"{key_prefix}_reg_form"):
        st.caption("書籍詳細")
        title = st.text_input("タイトル", value=st.session_state["form_title"], key=f"{key_prefix}_title")
        author = st.text_input("著者", value=st.session_state["form_author"], key=f"{key_prefix}_author")
        
        c1, c2 = st.columns([2, 1])
        with c1:
            cat_idx = 0
            cur = st.session_state.get("form_category", "")
            if cur in cats: cat_idx = cats.index(cur)
            category = st.selectbox("カテゴリ", cats, index=cat_idx, key=f"{key_prefix}_cat")
        
        tags = st.text_input("タグ", value=st.session_state["form_tags"], key=f"{key_prefix}_tags", placeholder="AI, Python, 歴史...")
        status = st.selectbox("状態", ["未読", "読書中", "読了"], key=f"{key_prefix}_status")
        read_date = st.date_input("読了日", value=date.today(), key=f"{key_prefix}_date")
        
        notes = st.text_area("要点・メモ", value=st.session_state["form_notes"], height=150, key=f"{key_prefix}_notes")
        cover_url = st.text_input("表紙URL", value=st.session_state["form_cover_url"], key=f"{key_prefix}_cover")
        isbn_input = st.text_input("ISBN", value=st.session_state["form_isbn"], key=f"{key_prefix}_isbn")
        new_cat_inline = st.text_input("新規カテゴリ (任意)", key=f"{key_prefix}_new_cat")

        if st.form_submit_button("📚 書籍を登録"):
            if title:
                final_cat = category
                if new_cat_inline:
                    if add_category(new_cat_inline): final_cat = new_cat_inline
                
                read_date_str = ""
                if status == "読了": read_date_str = read_date.strftime("%Y-%m-%d")
                    
                add_book(title, author, final_cat, tags, status, notes, cover_url, read_date_str, isbn_input)
                st.snow()
                # Clear
                for k in ["title", "author", "category", "tags", "notes", "cover_url", "isbn"]: 
                    st.session_state[f"form_{k}"] = ""
                st.rerun()
            else:
                st.error("タイトルは必須です。")

# --- Main Layout ---
page = st.sidebar.radio("ナビゲーション", ["ライブラリ", "カテゴリ管理", "設定・データ"])

if page == "カテゴリ管理":
    st.header("📂 カテゴリ管理")
    new_cat = st.text_input("新規カテゴリ追加")
    if st.button("追加"):
        if new_cat and add_category(new_cat): st.success(f"{new_cat} を追加しました"); st.rerun()
    st.markdown("---")
    for cat in get_categories():
        c1, c2 = st.columns([4, 1])
        c1.write(f"**{cat}**")
        if c2.button("削除", key=f"del_{cat}"): delete_category(cat); st.rerun()

elif page == "設定・データ":
    st.header("💾 データ管理")
    df = get_books()
    if not df.empty:
        st.download_button("CSVエクスポート", df.to_csv(index=False).encode('utf-8-sig'), "booklog_export.csv", "text/csv")
    st.markdown("---")
    uploaded_file = st.file_uploader("CSVインポート", type=['csv'])
    if uploaded_file and st.button("インポート"):
        try:
            import_df = pd.read_csv(uploaded_file)
            conn = sqlite3.connect(DB_PATH)
            # Ensure new columns exist by running a dummy select
            get_books()
            import_df.to_sql('books', conn, if_exists='append', index=False)
            st.success("インポート完了！"); conn.close()
        except Exception as e: st.error(f"エラー: {e}")

else:
    # --- Library View ---
    st.sidebar.markdown("### 🏛️ 書籍登録")
    render_registration_form(st.sidebar, key_prefix="sb", enable_camera=False)

    st.title("読書DB")
    
    # Responsive Registration Form (Mobile Only)
    with st.expander("➕ 書籍を登録", expanded=False):
        # Marker inside to target parent expander via CSS :has()
        st.markdown('<div id="mobile-only-marker"></div>', unsafe_allow_html=True)
        render_registration_form(st, key_prefix="mobile_top")
    
    # Check for Tunnel URL
    if os.path.exists("tunnel_url.txt"):
        with open("tunnel_url.txt", "r") as f:
            tunnel_url = f.read().strip()
        if tunnel_url:
            with st.expander("📱 iPhone用 HTTPSアクセス (QRコード)", expanded=True):
                st.info(f"URL: {tunnel_url}")
                try:
                    qr = qrcode.make(tunnel_url)
                    # Resize for display
                    qr = qr.resize((200, 200))
                    # Convert to bytes for st.image? actually st.image accepts PIL image
                    st.image(qr, caption="iPhoneで読み取ってください")
                    st.caption("※HTTPS接続によりカメラが利用可能になります。")
                except Exception as e:
                    st.error(f"QR生成エラー: {e}")
    
# ip = get_local_ip() removed
    # Mobile Access Section removed as requested

    df = get_books()
    
    # --- Advanced Search & Filter ---
    st.markdown("### 🔍 蔵書検索・フィルタ")
    
    # 1. Extract all unique tags
    all_tags = set()
    if not df.empty:
        for t_str in df['tags'].dropna():
            for t in t_str.split(','):
                if t.strip(): all_tags.add(t.strip())
    
    # 2. Filter UI
    with st.container():
        # Use columns for compact layout
        fs1, fs2, fs3 = st.columns([2, 1, 1])
        with fs1:
            q = st.text_input("キーワード検索", placeholder="タイトル, 著者, メモ...", label_visibility="collapsed")
        with fs2:
            # Tag Filter
            filter_tags = st.multiselect("🏷 タグ絞り込み", sorted(list(all_tags)), label_visibility="collapsed", placeholder="タグを選択")
        with fs3:
            # Category Filter
            filter_cats = st.multiselect("📂 カテゴリ", get_categories(), label_visibility="collapsed", placeholder="カテゴリ")

    # 3. Apply Filters
    if not df.empty:
        # Text Search
        if q:
            mask = (
                df['title'].str.contains(q, case=False, na=False) |
                df['author'].str.contains(q, case=False, na=False) |
                df['tags'].str.contains(q, case=False, na=False) |
                df['notes'].str.contains(q, case=False, na=False)
            )
            df = df[mask]
        
        # Tag Filter (OR logic: Show if book has ANY of selected tags)
        if filter_tags:
            def has_any_tag(row_tags_str, target_tags):
                if not isinstance(row_tags_str, str): return False
                row_tags = [t.strip() for t in row_tags_str.split(',')]
                return not set(row_tags).isdisjoint(target_tags)
            
            df = df[df['tags'].apply(lambda x: has_any_tag(x, filter_tags))]
            
        # Category Filter
        if filter_cats:
            df = df[df['category'].isin(filter_cats)]
    
    st.caption(f"所蔵数: {len(df)} 冊")
    
    if not df.empty:
        # Loop through books (Horizontal List Layout)
        for i, (index, row) in enumerate(df.iterrows()):
            with st.container():
                
                # Check for Edit Mode
                is_editing = (st.session_state.get("edit_target") == row['id'])
                
                if is_editing:
                    st.markdown(f"#### ✏️ 編集: {row['title']}")
                    with st.form(key=f"edit_form_{row['id']}"):
                        e_title = st.text_input("タイトル", value=row['title'])
                        
                        ec1, ec2 = st.columns(2)
                        with ec1:
                            e_author = st.text_input("著者", value=row['author'])
                            # Category logic
                            cats = get_categories()
                            c_idx = 0
                            if row['category'] in cats: c_idx = cats.index(row['category'])
                            e_cat = st.selectbox("カテゴリ", cats, index=c_idx)
                        with ec2:
                            e_tags = st.text_input("タグ", value=row['tags'])
                            s_idx = ["未読", "読書中", "読了"].index(row['status']) if row['status'] in ["未読", "読書中", "読了"] else 0
                            e_status = st.selectbox("状態", ["未読", "読書中", "読了"], index=s_idx)
                            
                        # Date parsing
                        d_val = date.today()
                        if row['read_date']:
                            try: d_val = datetime.strptime(row['read_date'], "%Y-%m-%d").date()
                            except: pass
                        e_date = st.date_input("読了日", value=d_val)
                        
                        e_notes = st.text_area("要点・メモ", value=row['notes'], height=150)
                        
                        bc1, bc2 = st.columns([1, 1])
                        with bc1:
                            if st.form_submit_button("💾 保存"):
                                r_date_str = ""
                                if e_status == "読了": r_date_str = e_date.strftime("%Y-%m-%d")
                                update_book(row['id'], e_title, e_author, e_cat, e_tags, e_status, e_notes, r_date_str)
                                st.session_state["edit_target"] = None
                                st.toast("変更を保存しました")
                                time.sleep(0.5)
                                st.rerun()
                        with bc2:
                             if st.form_submit_button("キャンセル"):
                                 st.session_state["edit_target"] = None
                                 st.rerun()
                
                else:
                    # NORMAL VIEW (Horizontal Layout)
                    c1, c2, c3 = st.columns([1, 1.5, 3])
                    
                    with c1:
                        # Cover Image
                        img_src = row['cover_url'] if row['cover_url'] else ""
                        if img_src:
                            st.markdown(f'<img src="{img_src}" style="width:100%; height:180px; object-fit: contain; border-radius: 2px;">', unsafe_allow_html=True)
                        else:
                            st.markdown("<div style='height:180px; background:rgba(255,255,255,0.05); display:flex; align-items:center; justify-content:center; color:#5D6D7E; border-radius:2px; font-size:0.8rem;'>No Cover</div>", unsafe_allow_html=True)
                    
                    with c2:
                        # Metadata
                        st.markdown(f"### {row['title']}")
                        st.markdown(f"**著者**: {row['author']}")
                        
                        # Badges
                        st.markdown(f"<span class='tag-badge'>{row['category']}</span> <span class='tag-badge'>{row['status']}</span>", unsafe_allow_html=True)
                        if isinstance(row['tags'], str) and row['tags'].strip():
                            tags_html = "".join([f"<span class='tag-badge'>{t.strip()}</span>" for t in row['tags'].split(',')])
                            st.markdown(f"<div style='margin-top:4px;'>{tags_html}</div>", unsafe_allow_html=True)
                            
                        if row.get('read_date') and row['status'] == '読了':
                            st.caption(f"🗓 読了日: {row['read_date']}")

                        # Actions
                        with st.expander("操作"):
                            if st.button("✏️ 編集", key=f"edit_btn_{row['id']}"):
                                st.session_state["edit_target"] = row['id']
                                st.rerun()
                                
                            if row.get('isbn'):
                                 if st.button("🔄 表紙更新", key=f"refetch_{row['id']}"):
                                    new_img = resolve_best_image_url(row['isbn'])
                                    if new_img:
                                        update_book_cover(row['id'], new_img)
                                        st.toast("画像を更新しました")
                                        time.sleep(1.0)
                                        st.rerun()
                                    else:
                                        st.warning("画像が見つかりませんでした")
                            if st.button("削除", key=f"del_{row['id']}"):
                                delete_book(row['id'])
                                st.rerun()

                    with c3:
                        # Notes (Primary Content)
                        st.caption("📝 要点・メモ")
                        note_content = row['notes'] if isinstance(row['notes'], str) and row['notes'].strip() != 'nan' else "（メモなし）"
                        if note_content == "（メモなし）":
                             st.markdown(f"<div style='color:#999; font-style:italic; padding:10px;'>{note_content}</div>", unsafe_allow_html=True)
                        else:
                             st.markdown(f"<div class='note-box'>{note_content}</div>", unsafe_allow_html=True)
                
                st.markdown("<hr style='border: 0; border-top: 1px solid rgba(255,255,255,0.1); margin: 16px 0;'>", unsafe_allow_html=True)
