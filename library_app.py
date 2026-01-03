import streamlit as st
import pandas as pd
import os
import requests
import cv2
import numpy as np
from PIL import Image
# 引入即時掃描組件
from streamlit_barcode_scanner import st_barcode_scanner

# 1. 基本設定
st.set_page_config(page_title="秒掃圖書館", layout="centered", page_icon="🚀")

USERS_FILE = "users.csv"
BOOKS_FILE = "books.csv"

# --- 資料持久化載入 ---
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

if 'users' not in st.session_state: load_data()
if 'logged_in' not in st.session_state: st.session_state.logged_in = False

# --- 功能：條碼辨識 (用於上傳照片) ---
def decode_barcode(image):
    img_array = np.array(image)
    img_bgr = cv2.cvtColor(img_array, cv2.COLOR_RGB2BGR)
    detector = cv2.barcode.BarcodeDetector()
    retval, decoded_info, points = detector.detectAndDecode(img_bgr)
    if retval and len(decoded_info) > 0:
        return str(decoded_info[0])
    return None

# --- 功能：抓取書籍資料 ---
def fetch_and_save(isbn):
    if not isbn: return
    with st.spinner(f"正在抓取 ISBN: {isbn} ..."):
        url = f"https://www.googleapis.com/books/v1/volumes?q=isbn:{isbn}"
        try:
            r = requests.get(url, timeout=5).json()
            if "items" in r:
                info = r["items"][0]["volumeInfo"]
                title = info.get("title", "未知書名")
                author = ", ".join(info.get("authors", ["未知作者"]))
                year = info.get("publishedDate", "2026")[:4]
                
                # 存入資料庫
                new_book = pd.DataFrame([{"書名": title, "作者": author, "ISBN": isbn, "年份": year}])
                st.session_state.books = pd.concat([st.session_state.books, new_row], ignore_index=True)
                st.session_state.books.to_csv(BOOKS_FILE, index=False)
                st.success(f"✅ 已成功加入：《{title}》")
                st.balloons()
            else:
                st.warning("辨識成功，但 Google 資料庫找不到這本書。")
        except:
            st.error("網路連線失敗。")

# --- 2. 登入介面 ---
if not st.session_state.logged_in:
    st.title("🔐 會員系統")
    u = st.text_input("帳號")
    p = st.text_input("密碼", type="password")
    if st.button("進入系統"):
        if u in st.session_state.users and str(st.session_state.users[u]) == p:
            st.session_state.logged_in = True
            st.session_state.cur_user = u
            st.rerun()
        else: st.error("錯誤")

# --- 3. 主程式介面 ---
else:
    st.title(f"🚀 {st.session_state.cur_user} 的秒掃書庫")
    
    # 模式切換
    mode = st.radio("選擇模式", ["即時掃描 (掃發票感)", "上傳照片辨識"], horizontal=True)

    if mode == "即時掃描 (掃發票感)":
        st.write("請對準條碼，系統會自動捕捉：")
        # 這個組件會自動開啟手機的原生掃描感應
        barcode = st_barcode_scanner()
        if barcode:
            if 'last_code' not in st.session_state or st.session_state.last_code != barcode:
                st.session_state.last_code = barcode
                fetch_and_save(barcode)

    else:
        st.write("請上傳條碼照片或直接拍照：")
        uploaded_file = st.file_uploader("選擇圖片...", type=['jpg', 'jpeg', 'png'])
        if uploaded_file:
            img = Image.open(uploaded_file)
            st.image(img, caption='已上傳', width=200)
            isbn_res = decode_barcode(img)
            if isbn_res:
                st.success(f"辨識到 ISBN: {isbn_res}")
                if st.button("確認加入"):
                    fetch_and_save(isbn_res)
            else:
                st.error("無法辨識照片中的條碼，請換個角度。")

    # 4. 顯示館藏
    st.divider()
    st.subheader("📖 我的館藏")
    st.dataframe(st.session_state.books, use_container_width=True)
    if st.sidebar.button("登出"):
        st.session_state.logged_in = False
        st.rerun()
