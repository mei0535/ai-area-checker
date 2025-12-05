import streamlit as st
import google.generativeai as genai
from PIL import Image
import pandas as pd
import json

# --- 1. 網頁設定 ---
st.set_page_config(page_title="AI 全能工程算量", page_icon="🏗️", layout="wide")

# --- 2. 側邊欄：設定與規則 ---
with st.sidebar:
    st.header("🔑 系統設定")
    api_key = st.text_input("API Key", type="password", help="請輸入 Google Gemini API Key")
    
    st.divider()
    
    st.header("🎨 自訂顏色與規則")
    st.info("這裡決定了 AI 怎麼看這張圖！")
    
    # 預設提供幾個模板讓使用者選，選了會自動填入下方的文字框
    template_options = {
        "自由定義 (預設)": "請分析圖面內容，列出所有有顏色標示的數值。",
        "工程數量 (長x寬)": "1. 紅色線段代表長度 (L)\n2. 藍色線段代表寬度 (W)\n3. 請計算面積 (Area = L x W)",
        "空間用途檢討": "1. 黃色區塊代表「辦公室」\n2. 綠色區塊代表「會議室」\n3. 請列出各區塊的標示面積",
        "裝修材質統計": "1. 紅色線段代表「踢腳板 Type A」\n2. 藍色線段代表「隔間牆 Type B」\n3. 請統計各材質的總長度"
    }
    
    selected_template = st.selectbox("快速樣板", list(template_options.keys()))
    
    # 核心功能：讓使用者可以改這段文字
    user_rules = st.text_area(
        "詳細規則提示詞 (可自由修改)", 
        value=template_options[selected_template],
        height=150
    )

# --- 3. 主畫面 ---
st.title("🏗️ AI 全能工程算量平台")
st.markdown("---")

col_img, col_result = st.columns([1, 1.5])

with col_img:
    st.subheader("1. 上傳圖說")
    uploaded_file = st.file_uploader("支援 JPG / PNG", type=["jpg", "jpeg", "png"])
    if uploaded_file:
        image = Image.open(uploaded_file)
        st.image(image, caption="圖說預覽", use_column_width=True)

with col_result:
    st.subheader("2. AI 分析結果")
    
    if uploaded_file and api_key and st.button("🚀 執行 AI 辨識", type="primary"):
        try:
            genai.configure(api_key=api_key)
            model = genai.GenerativeModel('gemini-1.5-pro')
            
            with st.spinner("AI 正在依照您的自訂規則讀圖..."):
                # 組合 Prompt：使用者規則 + 強制 JSON 格式
                prompt = f"""
                你是一位專業的工程估算師。請依照以下【使用者自訂規則】來分析這張圖說：

                【使用者自訂規則】
                {user_rules}

                【輸出格式要求】
                請務必輸出一個 JSON 格式的清單 (List of Objects)，包含以下欄位：
                - "item_name": 項目名稱 (例如：辦公室A, 紅色線段1...)
                - "color_type": 顏色/類型 (例如：黃色, 紅色材質...)
                - "value_raw": 圖面標示數值 (數字)
                - "calculation": 計算過程或說明 (例如：5.5 * 3.0)
                - "result": 最終結果數值 (數字)
                - "unit": 單位 (例如：m, m2, 式)

                如果圖面上沒有符合規則的物件，回傳空清單 []。
                請直接輸出 JSON，不要包含 ```json ... ``` 標記。
                """
                
                response = model.generate_content([prompt, image])
                
                # 解析 JSON
                clean_json = response.text.replace("```json", "").replace("```", "").strip()
                data = json.loads(clean_json)
                
                if data:
                    df = pd.DataFrame(data)
                    
                    # 顯示統計 (嘗試將 result 加總)
                    try:
                        total = df["result"].sum()
                        st.metric("總計 (Total)", f"{total:,.2f}")
                    except:
                        pass # 如果單位不同或無法加總，就不顯示總計
                    
                    # 顯示表格
                    st.dataframe(
                        df, 
                        column_config={
                            "item_name": "項目",
                            "color_type": "定義類型",
                            "value_raw": "原始標示",
                            "calculation": "計算說明",
                            "result": "結果",
                            "unit": "單位"
                        },
                        use_container_width=True
                    )
                    
                    # 下載按鈕
                    csv = df.to_csv(index=False).encode('utf-8-sig')
                    st.download_button("📥 下載 Excel (CSV)", csv, "ai_takeoff.csv", "text/csv")
                else:
                    st.warning("AI 沒有找到符合您描述的物件，請嘗試修改規則描述。")

        except Exception as e:
            st.error(f"發生錯誤：{e}")
            st.caption("請檢查 API Key 是否正確。")
