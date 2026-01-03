import streamlit as st
import pandas as pd
import os
import requests
import cv2
import numpy as np
from PIL import Image

# 1. 系統基本設定
st.set_page_config(page_title="雲端圖書館系統", layout="centered", page_icon="📚")

USERS_FILE = "users.csv"
BOOKS_FILE = "books.csv"

# 初始化資料與資料庫
def load_data():
    if os.path.exists(USERS_FILE):
        df = pd.read_csv(USERS_FILE)
        st.session_state.users = dict(zip(df.username.astype(str), df.password.astype(str)))
    else:
        st.session_state.users = {"admin": "1234"}
    
    if os.path.exists(BOOKS_FILE):
        st.session_state.books = pd.read_csv(BOOKS_FILE)
    else:
        st.session_state.books = pd.DataFrame(columns=["書名", "作者", "ISBN", "年份"])

if 'users' not in st.session_state:
    load_data()
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False

# 2. 功能函式區
def fetch_info(isbn):
    """透過 Google Books API 抓取資料"""
    url = f"https://www.googleapis.com/books/v1/volumes?q=isbn:{isbn}"
    try:
        r = requests.get(url, timeout=5).json()
        if "items" in r:
            b = r["items"][0]["volumeInfo"]
            return {
                "title": b.get("title", "未知書名"),
                "authors": ", ".join(b.get("authors", ["未知作者"])),
                "year": b.get("publishedDate", "2024")[:4]
            }
    except: return None
    return None

def scan_barcode_from_image(uploaded_file):
    """將照片轉成 OpenCV 格式進行條碼辨識，修正只回傳座標的問題"""
    img = Image.open(uploaded_file)
    img_array = np.array(img)
    img_bgr = cv2.cvtColor(img_array, cv2.COLOR_RGB2BGR)
    
    detector = cv2.barcode.BarcodeDetector()
    # retval: 成功與否, decoded_info: 內容, points: 座標
    retval, decoded_info, points = detector.detectAndDecode(img_bgr)
    
    # 確保抓取的是 decoded_info (內容) 而不是座標
    if retval and len(decoded_info) > 0:
        for info in decoded_info:
            if info.strip():
                return info.strip()
    return None

# 3. 介面：登入與註冊頁面
def login_page():
    st.title("🔐 會員登入系統")
    tab1, tab2 = st.tabs(["帳號登入", "新會員註冊"])
    
    with tab1:
        u = st.text_input("帳號", key="login_u")
        p = st.text_input("密碼", type="password", key="login_p")
        if st.button("確認登入"):
            if u in st.session_state.users and str(st.session_state.users[u]) == p:
                st.session_state.logged_in = True
                st.session_state.cur_user = u
                st.rerun()
            else: st.error("帳號或密碼錯誤")
                
    with tab2:
        nu = st.text_input("設定新帳號", key="reg_u")
        npw = st.text_input("設定新密碼", type="password", key="reg_p")
        if st.button("完成註冊"):
            if nu and npw:
                st.session_state.users[nu] = str(npw)
                pd.DataFrame(list(st.session_state.users.items()), columns=['username', 'password']).to_csv(USERS_FILE, index=False)
                st.success("註冊成功！請切換到『登入』分頁進入系統。")

# 4. 介面：圖書館主頁面
def main_page():
    st.title(f"📚 {st.session_state.cur_user} 的個人書庫")
    if st.sidebar.button("登出"):
        st.session_state.logged_in = False
        st.rerun()

    # 側邊欄：新增書籍
    st.sidebar.header("➕ 新增藏書")
    
    # 拍照辨識區
    with st.sidebar.expander("📷 拍照辨識條碼"):
        captured_img = st.camera_input("對準 ISBN 條碼拍照")
        if captured_img:
            isbn_res = scan_barcode_from_image(captured_img)
            if isbn_res:
                st.sidebar.success(f"辨識成功: {isbn_res}")
                st.session_state.temp_isbn = isbn_res
            else:
                st.sidebar.warning("辨識失敗，請調整角度或光線重拍")

    # 手動輸入/抓取區
    current_isbn = st.sidebar.text_input("ISBN (13碼)", value=st.session_state.get('temp_isbn', ""))
    
    if st.sidebar.button("🔍 抓取書籍資訊"):
        if current_isbn:
            res = fetch_info(current_isbn)
            if res:
                st.session_state.t = res["title"]
                st.session_state.a = res["authors"]
                st.session_state.y = res["year"]
                st.sidebar.success("資料抓取成功！")
            else: st.sidebar.error("找不到資料，請確認 ISBN 是否正確")
        else: st.sidebar.warning("請先輸入或掃描 ISBN")

    st.sidebar.divider()
    
    # 最終確認與編輯區 (使用 .get 避免報錯)
    f_t = st.sidebar.text_input("書名*", value=st.session_state.get('t', ""))
    f_a = st.sidebar.text_input("作者*", value=st.session_state.get('a', ""))
    f_y = st.sidebar.text_input("年份", value=st.session_state.get('y', "2026"))

    if st.sidebar.button("✅ 確認入庫"):
        if f_t and f_a:
            new_row = pd.DataFrame([{"書名": f_t, "作者": f_a, "ISBN": current_isbn, "年份": f_y}])
            st.session_state.books = pd.concat([st.session_state.books, new_row], ignore_index=True)
            st.session_state.books.to_csv(BOOKS_FILE, index=False)
            st.balloons()
            st.success(f"已加入：{f_t}")
            # 清空暫存變數
            for k in ['t', 'a', 'y', 'temp_isbn']:
                if k in st.session_state: del st.session_state[k]
        else:
            st.sidebar.error("書名與作者不可為空")

    # 顯示主清單
    st.subheader("📖 目前藏書清單")
    if not st.session_state.books.empty:
        st.dataframe(st.session_state.books, use_container_width=True)
        
        # 簡易搜尋
        search = st.text_input("🔎 搜尋藏書 (輸入書名或作者)")
        if search:
            filtered = st.session_state.books[st.session_state.books['書名'].str.contains(search) | st.session_state.books['作者'].str.contains(search)]
            st.table(filtered)

        # 刪除功能
        st.divider()
        target = st.selectbox("選擇要刪除的書", st.session_state.books["書名"])
        if st.button("🗑️ 刪除選中書籍", type="primary"):
            st.session_state.books = st.session_state.books[st.session_state.books["書名"] != target]
            st.session_state.books.to_csv(BOOKS_FILE, index=False)
            st.rerun()
    else:
        st.info("目前還沒有書，快用側邊欄新增第一本吧！")

# 5. 執行入口
if st.session_state.logged_in:
    main_page()
else:
    login_page()
