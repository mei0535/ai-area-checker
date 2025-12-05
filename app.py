import streamlit as st
import google.generativeai as genai
from PIL import Image
import pandas as pd
import json

st.set_page_config(page_title="AI 全能工程算量平台 (相容版)", page_icon="🏗️", layout="wide")

with st.sidebar:
    st.header("🔑 系統設定")
    
    # 嘗試讀取 Secrets
    try:
        default_key = st.secrets["GOOGLE_API_KEY"]
    except:
        default_key = ""
        
    api_key = st.text_input("API Key", value=default_key, type="password")
    
    st.divider()
    st.header("🎨 自訂計算規則")
    user_definition = st.text_area("1. 顏色與空間定義", value="例如：\n- 黃色線段範圍是「A戶辦公室」", height=100)
    calc_mode = st.radio("2. 計算目標", ["計算平面面積 (Area)", "計算周長 (Perimeter)", "計算牆面/表面積 (周長 x 高度)"])
    
    wall_height = 0.0
    if "牆面" in calc_mode:
        wall_height = st.number_input("輸入樓層高度 (m)", value=3.0, step=0.1)

st.title("🏗️ AI 全能工程算量平台")

col_img, col_result = st.columns([1, 1.5])

with col_img:
    uploaded_file = st.file_uploader("請上傳圖檔", type=["jpg", "jpeg", "png"])
    if uploaded_file:
        image = Image.open(uploaded_file)
        st.image(image, caption="圖說預覽", use_column_width=True)

with col_result:
    if uploaded_file and api_key and st.button("🚀 執行 AI 辨識"):
        try:
            genai.configure(api_key=api_key)
            
            # --- 關鍵修正：改用 gemini-1.5-flash (這是目前官方主推，如果這個也不行，代表 API Key 有問題) ---
            # 如果還是 404，請手動改回 'gemini-pro-vision'
            model = genai.GenerativeModel('gemini-1.5-flash')
            
            with st.spinner("AI 正在運算中..."):
                math_logic = ""
                if "面積" in calc_mode:
                    math_logic = "請辨識該範圍的標註尺寸，計算其「平面面積 (m2)」。"
                elif "周長" in calc_mode:
                    math_logic = "請辨識該範圍的邊長標註，計算其「總周長 (m)」。"
                elif "牆面" in calc_mode:
                    math_logic = f"請先計算該範圍的「總周長」，再乘以高度 {wall_height} 公尺。"

                prompt = f"""
                你是一位專業的工程估算師。請依照以下規則分析這張圖：
                規則：{user_definition}
                目標：{math_logic}
                
                請直接輸出 JSON 格式結果，包含欄位：item_name, formula, result, unit。
                不要輸出 Markdown 標記。
                """
                
                response = model.generate_content([prompt, image])
                
                # 嘗試清理並解析 JSON
                txt = response.text.replace("```json", "").replace("```", "").strip()
                try:
                    data = json.loads(txt)
                    st.success("✅ 計算完成！")
                    st.dataframe(pd.DataFrame(data), use_container_width=True)
                except:
                    st.warning("AI 回傳了非標準格式，請參考下方原始內容：")
                    st.write(response.text)

        except Exception as e:
            st.error(f"發生錯誤：{e}")
            # 加入除錯資訊
            st.info("💡 建議：請檢查 API Key 是否有開通 Gemini API 權限，或嘗試更換另一個 Google 帳號申請 Key。")
