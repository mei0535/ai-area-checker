import streamlit as st
import google.generativeai as genai
from PIL import Image
import pandas as pd
import json

# --- 1. 網頁基礎設定 (商業風格) ---
st.set_page_config(
    page_title="AI 工程算量雲端平台",
    page_icon="📐",
    layout="wide",  # 使用寬螢幕模式，適合左右對照
    initial_sidebar_state="expanded"
)

# 自訂 CSS 讓介面看起來更專業 (隱藏 Streamlit 預設選單)
st.markdown("""
    <style>
    .reportview-container {
        background: #f0f2f6
    }
    .main-header {
        font-size: 2.5rem;
        color: #1E3A8A; 
    }
    </style>
""", unsafe_allow_html=True)

# --- 2. 側邊欄：控制台 ---
with st.sidebar:
    st.title("🎛️ 控制台")
    api_key = st.text_input("🔑 API Key (授權金鑰)", type="password")
    
    st.divider()
    st.subheader("🛠️ 計算設定")
    calc_mode = st.selectbox(
        "選擇計算模式",
        ["樓地板面積 (Area)", "牆面粉刷 (Wall Area)", "踢腳板長度 (Linear)"]
    )
    
    st.info("""
    **標註規則說明：**
    🔴 紅色線段：長度 (L)
    🔵 藍色線段：寬度 (W) / 高度 (H)
    """)
    
    st.divider()
    st.caption("v2.0 Commercial Build")

# --- 3. 主畫面邏輯 ---

st.markdown('<p class="main-header">🏗️ AI 工程算量雲端平台</p>', unsafe_allow_html=True)
st.markdown("---")

# 建立兩欄佈局：左邊上傳/看圖，右邊顯示計算書
col_img, col_data = st.columns([1, 1.2])

with col_img:
    st.subheader("1. 圖說上傳")
    uploaded_file = st.file_uploader("請上傳標註好的圖檔 (JPG/PNG)", type=["jpg", "jpeg", "png"])
    
    if uploaded_file:
        image = Image.open(uploaded_file)
        st.image(image, caption="圖說預覽", use_column_width=True)
    else:
        st.info("👈 請先上傳圖片以開始作業")

with col_data:
    st.subheader("2. 計算書與過程")
    
    if uploaded_file and api_key:
        if st.button("🚀 開始 AI 核算", type="primary"):
            try:
                genai.configure(api_key=api_key)
                model = genai.GenerativeModel('gemini-1.5-pro') # 使用最強視覺模型
                
                with st.spinner("🤖 AI 正在讀取圖面數值並生成計算書..."):
                    # 商用級 Prompt：要求詳細的過程
                    prompt = f"""
                    你是一個專業的建築估算師。請分析這張圖說，目標是計算「{calc_mode}」。
                    
                    【視覺規則】
                    1. 尋找圖面上的【紅色線段】數值，視為 Dimension 1 (長度)。
                    2. 尋找圖面上的【藍色線段】數值，視為 Dimension 2 (寬度/高度)。
                    
                    【輸出要求】
                    請輸出一個 JSON 格式的清單，包含以下欄位：
                    - "item": 項目名稱 (例如：臥室A, 客廳)
                    - "dim1": 紅色數值 (數字)
                    - "dim2": 藍色數值 (數字)
                    - "formula": 計算過程字串 (例如：5.5 * 3.2)
                    - "result": 計算結果 (數字)
                    - "unit": 單位 (m2 或 m)
                    
                    請確保數值精確讀取，若有不明顯處請略過。
                    請直接輸出 JSON，不要 Markdown 標記。
                    """
                    
                    response = model.generate_content([prompt, image])
                    
                    # 資料處理
                    clean_json = response.text.replace("```json", "").replace("```", "").strip()
                    data_list = json.loads(clean_json)
                    df = pd.DataFrame(data_list)
                    
                    # 顯示統計指標
                    if not df.empty and "result" in df.columns:
                        total_qty = df["result"].sum()
                        st.success("✅ 計算完成！")
                        st.metric("總數量 (Grand Total)", f"{total_qty:,.2f} {df['unit'][0]}")
                        
                        # 顯示詳細表格 (含計算式)
                        st.markdown("### 📋 詳細計算表")
                        st.dataframe(
                            df.style.format({
                                "dim1": "{:.2f}",
                                "dim2": "{:.2f}",
                                "result": "{:.2f}"
                            }),
                            use_container_width=True,
                            column_config={
                                "item": "空間/項目",
                                "dim1": "長度 (Red)",
                                "dim2": "寬度 (Blue)",
                                "formula": "計算式 (Process)",
                                "result": "小計",
                                "unit": "單位"
                            }
                        )
                        
                        # 商用功能：下載報表
                        csv = df.to_csv(index=False).encode('utf-8-sig')
                        st.download_button(
                            label="📥 下載工程計算書 (Excel/CSV)",
                            data=csv,
                            file_name="quantity_takeoff.csv",
                            mime="text/csv",
                            type="primary"
                        )
                    else:
                        st.warning("AI 無法識別出有效數據，請檢查圖面標示是否清晰。")

            except Exception as e:
                st.error(f"系統錯誤：{e}")
                st.caption("請檢查 API Key 是否正確，或圖片是否過大。")
    
    elif not uploaded_file:
        st.write("等待圖片上傳...")
    elif not api_key:
        st.warning("請在左側輸入 API Key 才能解鎖計算功能。")
