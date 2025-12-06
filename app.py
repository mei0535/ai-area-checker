import streamlit as st
import google.generativeai as genai
from PIL import Image
import pandas as pd
import json
import fitz  # PyMuPDF

# --- 1. 網頁設定 ---
st.set_page_config(page_title="AI 工程算量平台 (v13.0 2025世代版)", page_icon="🏗️", layout="wide")

# --- 2. 側邊欄設定 ---
with st.sidebar:
    st.header("🔑 啟動金鑰 (BYOK)")
    
    st.info("ℹ️ 請輸入您的 Google API Key (AIza 開頭)")
    api_key = st.text_input("API Key", type="password", placeholder="貼上 AIza... 開頭的 Key")
    
    # [檢測按鈕保留]
    if api_key:
        if st.button("🔍 再次列出可用模型"):
            try:
                genai.configure(api_key=api_key)
                models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
                st.success("驗證成功！")
                st.json(models)
            except Exception as e:
                st.error(f"驗證失敗：{e}")

    st.divider()
    
    # --- [關鍵更新] 這裡更新為您帳號實際擁有的模型 ---
    st.header("🤖 選擇模型")
    model_option = st.selectbox(
        "建議優先使用 2.5 Flash",
        [
            "models/gemini-2.5-flash",       # 首選：最新一代 Flash
            "models/gemini-2.5-pro",         # 次選：最新一代 Pro
            "models/gemini-2.0-flash",       # 備用：2.0 穩定版
            "models/gemini-flash-latest",    # 通用：指向最新 Flash
            "models/gemini-1.5-flash"        # 舊版：相容性保留
        ],
        index=0 # 預設選第一個 (2.5-flash)
    )
    
    st.divider()
    
    st.header("🎨 定義規則")
    user_definition = st.text_area(
        "1. 空間/顏色定義", 
        value="例如：\n- 黃色線段範圍是「A戶辦公室」\n- 紅色線段範圍是「B戶會議室」",
        height=100
    )
    
    calc_mode = st.radio(
        "2. 計算模式",
        ["計算平面面積 (Area)", "計算周長 (Perimeter)", "計算牆面/表面積 (周長 x 高度)"]
    )
    
    wall_height = 0.0
    if "牆面" in calc_mode:
        wall_height = st.number_input("樓層高度 (m)", value=3.0, step=0.1)

# --- 3. 主畫面 ---
st.title("🏗️ AI 工程算量平台 (v13.0 2025世代版)")
st.caption(f"✅ 已適配最新 Gemini 2.5/3.0 模型架構 | 當前選擇: {model_option}")
st.markdown("---")

col_img, col_data = st.columns([1, 1.5])
image = None

with col_img:
    st.subheader("1. 圖說檢視")
    uploaded_file = st.file_uploader("上傳圖檔 (JPG/PNG/PDF)", type=["jpg", "jpeg", "png", "pdf"])
    if uploaded_file:
        try:
            if uploaded_file.name.lower().endswith('.pdf'):
                with st.spinner("PDF 轉檔中..."):
                    doc = fitz.open(stream=uploaded_file.read(), filetype="pdf")
                    page = doc[0]
                    pix = page.get_pixmap(dpi=300)
                    image = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                    st.success(f"已讀取 PDF 第一頁 (共 {len(doc)} 頁)")
            else:
                image = Image.open(uploaded_file)
            st.image(image, caption="預覽圖", use_container_width=True)
        except Exception as e:
            st.error(f"圖片讀取失敗: {e}")

with col_data:
    st.subheader("2. 算量校對表")
    
    if 'ai_data' not in st.session_state:
        st.session_state.ai_data = None

    if image and api_key:
        if st.button(f"🚀 執行 AI 辨識 ({model_option})", type="primary"):
            
            genai.configure(api_key=api_key)
            
            try:
                # 使用側邊欄選取的模型
                model = genai.GenerativeModel(model_option)
                st.toast(f"正在連線模型：{model_option} ...")
                
                dim_instruction = ""
                if "面積" in calc_mode:
                    dim_instruction = "請分別抓取「長度 (Length)」與「寬度 (Width)」。"
                elif "周長" in calc_mode or "牆面" in calc_mode:
                    dim_instruction = "請抓取該範圍所有邊長的總和做為「長度 (dim1)」，寬度填 0。"

                prompt = f"""
                You are a Quantity Surveyor. Analyze this image based on user rules: {user_definition}.
                IMPORTANT: If numbers are in mm (e.g., 3500), convert to meters (3.5).
                Task: {dim_instruction}
                Return ONLY a JSON list (no markdown) with keys: "item", "dim1", "dim2", "note".
                Example: [{{"item": "Office A", "dim1": 5.2, "dim2": 3.0, "note": "text"}}]
                """
                
                response = model.generate_content([prompt, image])
                
                try:
                    clean_json = response.text.replace("```json", "").replace("```", "").strip()
                    data = json.loads(clean_json)
                    st.session_state.ai_data = pd.DataFrame(data)
                    st.success("✅ 辨識成功！")
                except:
                    st.error("AI 回傳格式無法解析，請重試或更換模型。")
                    st.write("Raw output:", response.text)
                
            except Exception as e:
                st.error(f"❌ 連線失敗")
                st.warning("建議在左側選單換一個模型試試看 (例如從 2.5-flash 換成 2.5-pro)。")
                st.error(str(e))

    # --- Data Editor & Calculation ---
    if st.session_state.ai_data is not None:
        edited_df = st.data_editor(
            st.session_state.ai_data,
            column_config={
                "item": "項目",
                "dim1": st.column_config.NumberColumn("長度/周長 (m)", format="%.2f"),
                "dim2": st.column_config.NumberColumn("寬度 (m)", format="%.2f"),
                "note": "AI 備註"
            },
            num_rows="dynamic",
            use_container_width=True
        )
        
        results = []
        for index, row in edited_df.iterrows():
            try: d1 = float(row.get("dim1", 0))
            except: d1 = 0.0
            try: d2 = float(row.get("dim2", 0))
            except: d2 = 0.0
            
            val = 0.0
            unit = ""
            
            if "面積" in calc_mode:
                val = d1 * d2
                unit = "m²"
            elif "周長" in calc_mode:
                val = d1 
                unit = "m"
            elif "牆面" in calc_mode:
                val = d1 * wall_height
                unit = "m²"
            
            results.append({
                "項目": row.get("item", ""),
                "計算式": f"{d1}*{d2}" if "面積" in calc_mode else (f"{d1}*{wall_height}" if "牆面" in calc_mode else f"{d1}"),
                "小計": round(val, 2),
                "單位": unit
            })
            
        result_df = pd.DataFrame(results)
        st.divider()
        st.subheader("3. 最終計算書")
        total_val = result_df["小計"].sum()
        first_unit = result_df['單位'].iloc[0] if not result_df.empty else ""
        st.metric("總數量", f"{total_val:,.2f} {first_unit}")
        st.dataframe(result_df, use_container_width=True)
