import streamlit as st
import google.generativeai as genai
from PIL import Image
import pandas as pd
import json
import fitz  # PyMuPDF

# --- 1. 網頁設定 ---
st.set_page_config(page_title="AI 工程算量平台 (v11.0 診斷版)", page_icon="🏗️", layout="wide")

# --- 2. 側邊欄 ---
with st.sidebar:
    st.header("🔑 啟動金鑰 (BYOK)")
    st.info("請輸入您的 Google API Key (AIza 開頭)")
    api_key = st.text_input("API Key", type="password")
    
    st.divider()
    st.header("🎨 定義規則")
    user_definition = st.text_area("1. 空間/顏色定義", value="黃色是A戶辦公室，紅色是B戶會議室", height=100)
    calc_mode = st.radio("2. 計算模式", ["計算平面面積 (Area)", "計算周長 (Perimeter)"])

# --- 3. 主畫面 ---
st.title("🏗️ AI 工程算量平台 (v11.0 診斷版)")
st.caption("🔴 此版本會顯示完整錯誤訊息，不再隱藏")
st.markdown("---")

col_img, col_data = st.columns([1, 1.5])
image = None

with col_img:
    uploaded_file = st.file_uploader("上傳圖檔 (JPG/PNG/PDF)", type=["jpg", "png", "pdf"])
    if uploaded_file:
        try:
            if uploaded_file.name.lower().endswith('.pdf'):
                with st.spinner("PDF 轉檔中..."):
                    doc = fitz.open(stream=uploaded_file.read(), filetype="pdf")
                    pix = doc[0].get_pixmap(dpi=300)
                    image = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                    st.success(f"已讀取 PDF (共 {len(doc)} 頁)")
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
        if st.button("🚀 執行 AI 辨識", type="primary"):
            
            # 設定 Key
            genai.configure(api_key=api_key)
            
            # 這次我們只測最強的一個模型，並把錯誤直接印出來
            model_name = "gemini-1.5-flash"
            
            try:
                st.info(f"正在嘗試連線模型: {model_name} ...")
                model = genai.GenerativeModel(model_name)
                
                prompt = f"""
                You are a Quantity Surveyor. 
                Analyze this image based on: {user_definition}.
                Return ONLY a JSON list with fields: item, dim1(length/area), dim2(width), note.
                Example: [{{"item": "Office", "dim1": 3.5, "dim2": 5.0, "note": "text"}}]
                """
                
                # 發送請求
                response = model.generate_content([prompt, image])
                
                # 成功了！
                st.toast("✅ 連線成功！")
                clean_json = response.text.replace("```json", "").replace("```", "").strip()
                data = json.loads(clean_json)
                st.session_state.ai_data = pd.DataFrame(data)
                
            except Exception as e:
                # 🔥 這裡是最關鍵的修改：直接把錯誤印出來 🔥
                st.error(f"❌ 發生嚴重錯誤")
                st.error(f"錯誤類型: {type(e).__name__}")
                st.error(f"詳細錯誤訊息: {str(e)}")
                
                # 如果是常見錯誤，給予提示
                err_msg = str(e)
                if "400" in err_msg:
                    st.warning("提示：400 錯誤通常是 API Key 沒開通，或專案設定有誤。")
                elif "429" in err_msg:
                    st.warning("提示：429 錯誤代表額度用完了 (Quota exceeded)。")
                elif "User location is not supported" in err_msg:
                    st.warning("提示：您的 Google Cloud 專案所在的地區不支援 Gemini API。")

    # --- Data Editor ---
    if st.session_state.ai_data is not None:
        edited_df = st.data_editor(st.session_state.ai_data, num_rows="dynamic", use_container_width=True)
