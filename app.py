import streamlit as st
import google.generativeai as genai
from PIL import Image
import pandas as pd
import json

# --- 1. Page Config ---
st.set_page_config(page_title="AI 全能工程算量平台", page_icon="🏗️", layout="wide")

# --- 2. Sidebar ---
with st.sidebar:
    st.header("🔑 系統設定")
    
    try:
        default_key = st.secrets["GOOGLE_API_KEY"]
    except:
        default_key = ""
        
    api_key = st.text_input("API Key", value=default_key, type="password", help="請輸入 Google Gemini API Key")
    
    st.divider()
    
    st.header("🎨 自訂計算規則")
    user_definition = st.text_area(
        "1. 顏色與空間定義",
        value="例如：\n- 黃色線條範圍是「A戶辦公室」\n- 紅色線條範圍是「B戶會議室」",
        height=100
    )
    
    calc_mode = st.radio(
        "2. 計算目標",
        ["計算平面面積 (Area)", "計算周長 (Perimeter)", "計算牆面/表面積 (周長 x 高度)"]
    )
    
    wall_height = 0.0
    if "牆面" in calc_mode:
        wall_height = st.number_input("輸入樓層高度 (m)", value=3.0, step=0.1)

# --- 3. Main Screen ---
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
    
    if uploaded_file and api_key:
        if st.button("🚀 執行 AI 辨識與計算", type="primary"):
            try:
                genai.configure(api_key=api_key)
                
                # --- AUTO-DETECT MODEL LOGIC ---
                target_model_name = ""
                with st.spinner("正在搜尋可用模型..."):
                    try:
                        all_models = [m.name for m in genai.list_models()]
                        # Priority: Flash -> Pro Vision -> Pro
                        if 'models/gemini-1.5-flash' in all_models:
                            target_model_name = 'gemini-1.5-flash'
                        elif 'models/gemini-pro-vision' in all_models:
                            target_model_name = 'gemini-pro-vision'
                        elif 'models/gemini-1.5-pro' in all_models:
                            target_model_name = 'gemini-1.5-pro'
                        else:
                            # Fallback to the first available model
                            target_model_name = all_models[0].replace('models/', '')
                            
                        st.success(f"✅ 已連線至模型：`{target_model_name}`")
                        
                    except Exception as e:
                        # Hard fallback if listing fails
                        target_model_name = 'gemini-1.5-flash'
                        st.warning(f"⚠️ 無法自動搜尋，嘗試強制使用：`{target_model_name}`")

                # Configure Model
                model = genai.GenerativeModel(target_model_name)
                
                with st.spinner("AI 正在讀圖並進行運算..."):
                    
                    math_logic = ""
                    unit_hint = ""
                    
                    if "平面面積" in calc_mode:
                        math_logic = "請辨識該範圍的長寬標示，計算其「平面面積 (Area, m2)」。"
                        unit_hint = "m2"
                    elif "周長" in calc_mode:
                        math_logic = "請辨識該範圍的邊長標示，計算其「總周長 (Perimeter, m)」。"
                        unit_hint = "m"
                    elif "牆面" in calc_mode:
                        math_logic = f"請先計算該範圍的「總周長」，然後將周長乘以高度 {wall_height} 公尺，得出「垂直牆表面積 (Wall Area, m2)」。"
                        unit_hint = "m2"

                    prompt = f"""
                    你是一位專業的建築估算師。請依照以下規則分析這張圖說：
                    【使用者定義】{user_definition}
                    【計算目標】{math_logic}
                    【輸出格式】請輸出 JSON 格式清單，包含：item_name, description, formula_str, result, unit。
                    不要輸出 Markdown 標記。
                    """
                    
                    response = model.generate_content([prompt, image])
                    clean_json = response.text.replace("```json", "").replace("```", "").strip()
                    
                    try:
                        data = json.loads(clean_json)
                        if data:
                            df = pd.DataFrame(data)
                            st.success("✅ 計算完成！")
                            if "result" in df.columns:
                                try:
                                    st.metric("總數量 (Total)", f"{df['result'].sum():,.2f}")
                                except: pass
                            st.dataframe(df, use_container_width=True)
                            csv = df.to_csv(index=False).encode('utf-8-sig')
                            st.download_button("📥 下載計算書", csv, "takeoff.csv", "text/csv")
                        else:
                            st.warning("AI 無法識別符合規則的物件。")
                    except:
                        st.error("AI 回傳格式解析失敗。")
                        st.code(response.text)

            except Exception as e:
                st.error(f"發生錯誤：{e}")
                st.warning("請確認 API Key 是否正確。")
    
    elif not uploaded_file:
        st.info("👈 請先上傳圖檔")
    elif not api_key:
        st.warning("👈 請輸入 API Key")
