import streamlit as st
import google.generativeai as genai
from PIL import Image
import pandas as pd
import json

st.set_page_config(page_title="AI 工程算量平台 (除錯版)", page_icon="🛠️", layout="wide")

with st.sidebar:
    st.header("🔑 系統設定")
    api_key = st.text_input("API Key", type="password")
    
    # --- 新增功能：檢查可用模型 ---
    if api_key:
        try:
            genai.configure(api_key=api_key)
            st.success("API Key 格式正確")
            if st.button("🔍 檢查可用模型列表"):
                st.write("正在查詢 Google 伺服器...")
                models = [m.name for m in genai.list_models()]
                st.write("您的帳號可用模型：")
                st.code(models)
        except Exception as e:
            st.error(f"API 連線失敗：{e}")

    st.divider()
    st.header("🎨 自訂計算規則")
    user_definition = st.text_area("1. 顏色與空間定義", value="例如：\n- 黃色線段範圍是「A戶辦公室」", height=100)
    calc_mode = st.radio("2. 計算目標", ["計算面積 (Area)", "計算周長 (Perimeter)"])

st.title("🛠️ AI 工程算量平台 (除錯模式)")

uploaded_file = st.file_uploader("上傳圖說", type=["jpg", "jpeg", "png"])
if uploaded_file:
    image = Image.open(uploaded_file)
    st.image(image, caption="圖說預覽", use_column_width=True)

if uploaded_file and api_key and st.button("🚀 執行 AI 辨識"):
    try:
        genai.configure(api_key=api_key)
        
        # 這裡先暫時用 gemini-pro 試試看，因為它最基本
        # 如果還是不行，我們看側邊欄查出來的列表再改
        target_model = 'gemini-1.5-flash' 
        
        model = genai.GenerativeModel(target_model)
        
        with st.spinner(f"正在使用模型 {target_model} 運算中..."):
            prompt = f"""
            請分析這張圖。
            規則：{user_definition}
            目標：{calc_mode}
            請輸出 JSON 格式結果。
            """
            response = model.generate_content([prompt, image])
            st.write(response.text)

    except Exception as e:
        st.error(f"發生錯誤：{e}")
        st.warning("請先使用側邊欄的「檢查可用模型列表」按鈕，看看您的帳號到底支援哪些模型名稱。")
