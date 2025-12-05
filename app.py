import streamlit as st
import google.generativeai as genai
from PIL import Image
import pandas as pd
import json

# --- 1. 網頁設定 ---
st.set_page_config(page_title="AI 全能工程算量平台", page_icon="🏗️", layout="wide")

# --- 2. 側邊欄 ---
with st.sidebar:
    st.header("🔑 系統設定")
    api_key = st.text_input("API Key", type="password", help="請輸入 Google Gemini API Key")
    
    st.divider()
    
    st.header("🎨 自訂計算規則")
    
    # [功能 1] 自訂空間/線段定義
    user_definition = st.text_area(
        "1. 顏色與空間定義",
        value="例如：\n- 黃色線段範圍是「A戶辦公室」\n- 紅色線段範圍是「B戶會議室」",
        height=100
    )
    
    # [功能 2] 選擇計算模式
    calc_mode = st.radio(
        "2. 計算目標",
        ["計算面積 (Area)", "計算周長 (Perimeter)", "計算牆面/表面積 (周長 x 高度)"]
    )
    
    # [功能 3] 若算牆面，需輸入高度
    wall_height = 0.0
    if "牆面" in calc_mode:
        wall_height = st.number_input("輸入樓層高度 (m)", value=3.0, step=0.1)

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
            
            # --- 關鍵修正：改用 gemini-pro-vision (這是最穩定的視覺模型名稱) ---
            model = genai.GenerativeModel('gemini-pro-vision')
            
            with st.spinner("AI 正在運算中..."):
                
                math_logic = ""
                if "面積" in calc_mode:
                    math_logic = "請辨識該範圍的標註尺寸，計算其「平面面積 (m2)」。"
                elif "周長" in calc_mode:
                    math_logic = "請辨識該範圍的邊長標註，計算其「總周長 (m)」。"
                elif "牆面" in calc_mode:
                    math_logic = f"請先計算該範圍的「總周長」，再乘以高度 {wall_height} 公尺，得出「牆面垂直表面積 (m2)」。"

                prompt = f"""
                你是一位專業的工程估算師。請依照以下規則分析這張圖說：

                【使用者定義】
                {user_definition}

                【計算目標】
                {math_logic}

                【輸出格式要求】
                請務必輸出一個 JSON 格式的清單，包含以下欄位：
                - "item_name": 項目名稱
                - "calc_method": 計算方式說明
                - "formula": 數值運算式
                - "result": 最終結果數字
                - "unit": 單位

                若圖面模糊無法辨識，請略過。請直接輸出 JSON，不要 Markdown 標記。
                """
                
                response = model.generate_content([prompt, image])
                
                # 解析 JSON
                clean_json = response.text.replace("```json", "").replace("```", "").strip()
                
                try:
                    data = json.loads(clean_json)
                    if data:
                        df = pd.DataFrame(data)
                        st.success("✅ 計算完成！")
                        if "result" in df.columns:
                            try:
                                st.metric("總計", f"{df['result'].sum():,.2f}")
                            except: pass
                        
                        st.dataframe(df, use_container_width=True)
                    else:
                        st.warning("AI 無法識別符合規則的物件。")
                except:
                    # 如果 gemini-pro-vision 回傳純文字，直接顯示出來
                    st.info("AI 回傳了非表格內容：")
                    st.write(response.text)

        except Exception as e:
            st.error(f"發生錯誤：{e}")
            st.info("請確認 API Key 是否正確。")
