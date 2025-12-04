import streamlit as st
import google.generativeai as genai
from PIL import Image
import pandas as pd
import json

# --- 設定頁面 ---
st.set_page_config(page_title="AI 工程數量計算大師", page_icon="🏗️", layout="wide")

st.title("🏗️ AI 視覺化工程數量計算器 (Pro)")
st.markdown("""
**目標：** 利用 AI 視覺辨識，依據「線段顏色」自動提取數值並計算數量。
**支援格式：** JPG, PNG, JPEG
""")

# --- 側邊欄：API 設定 ---
with st.sidebar:
    st.header("🔑 系統設定")
    # 這裡讓您可以輸入 API Key
    api_key = st.text_input("請輸入 Google Gemini API Key", type="password")
    
    st.divider()
    st.header("🎨 定義計算規則")
    st.info("請告訴 AI 不同顏色代表什麼意義")
    
    color_logic = st.text_area(
        "顏色定義提示詞 (Prompt)",
        value="""
        請分析這張建築圖說，規則如下：
        1. 【紅色線段】代表「長度 (Length)」。
        2. 【藍色線段】代表「寬度 (Width)」。
        3. 請找出圖面上所有標示在紅色線段旁的數字，以及藍色線段旁的數字。
        4. 計算目標：請計算「面積 (Area)」，公式為 長度 x 寬度。
        """,
        height=200
    )

# --- 主功能區 ---

# 關鍵修正：這裡的 type 已經改成 jpg, png, jpeg 了！
uploaded_file = st.file_uploader("上傳有標示顏色的圖說", type=["jpg", "jpeg", "png"])

if uploaded_file and api_key:
    image = Image.open(uploaded_file)
    st.image(image, caption="已上傳的圖說", use_column_width=True)
    
    if st.button("🤖 開始 AI 視覺辨識與計算", type="primary"):
        try:
            genai.configure(api_key=api_key)
            model = genai.GenerativeModel('gemini-1.5-pro')
            
            with st.spinner("AI 正在讀圖中..."):
                full_prompt = f"""
                {color_logic}
                請嚴格依照 JSON 格式輸出：
                [
                    {{
                        "項目": "名稱",
                        "數值": 10.5,
                        "單位": "m"
                    }}
                ]
                """
                response = model.generate_content([full_prompt, image])
                st.write(response.text) # 直接顯示結果
                st.success("✅ 計算完成！")

        except Exception as e:
            st.error(f"發生錯誤：{e}")

elif not api_key:
    st.warning("👈 請先在左側輸入 API Key 才能啟動 AI 大腦。")
