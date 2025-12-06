import streamlit as st
import google.generativeai as genai
from PIL import Image
import pandas as pd
import json
import fitz  # PyMuPDF
import time

# --- 1. 網頁設定 ---
st.set_page_config(page_title="AI 工程算量平台 (公開試用版)", page_icon="🏗️", layout="wide")

# --- 2. 側邊欄：BYOK 設定區 ---
with st.sidebar:
    st.header("🔑 啟動金鑰")
    
    st.info("ℹ️ 本系統採用 BYOK 模式 (Bring Your Own Key)。請輸入您自己的 Google API Key 即可免費使用。")
    
    # --- 關鍵修改：不讀取 secrets，強制手動輸入 ---
    api_key = st.text_input("請輸入 Google API Key", type="password", placeholder="貼上您的 Key (sk-...)")
    
    # 貼心功能：提供申請連結
    st.markdown("""
    [👉 點此免費申請 Google API Key](https://aistudio.google.com/app/apikey)
    
    <small>申請步驟：
    1. 登入 Google 帳號
    2. 點擊 'Create API key'
    3. 複製 Key 並貼上欄位</small>
    """, unsafe_allow_html=True)
    
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
st.title("🏗️ AI 工程算量平台 (公開試用版)")
st.caption("v10.0 BYOK: 開放式試用架構，請輸入金鑰以開始")
st.markdown("---")

col_img, col_data = st.columns([1, 1.5])

image = None

with col_img:
    st.subheader("1. 圖說檢視")
    uploaded_file = st.file_uploader("上傳圖檔 (JPG/PNG/PDF)", type=["jpg", "jpeg", "png", "pdf"])
    
    if uploaded_file:
        try:
            if uploaded_file.name.lower().endswith('.pdf'):
                with st.spinner("正在將 PDF 轉為高解析圖片..."):
                    doc = fitz.open(stream=uploaded_file.read(), filetype="pdf")
                    page = doc[0]
                    pix = page.get_pixmap(dpi=300)
                    image = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                    st.success(f"已讀取 PDF 第一頁 (共 {len(doc)} 頁)")
            else:
                image = Image.open(uploaded_file)
            st.image(image, caption=f"預覽：{uploaded_file.name}", use_container_width=True)
        except Exception as e:
            st.error(f"檔案讀取失敗：{e}")

with col_data:
    st.subheader("2. 算量校對表")
    
    if 'ai_data' not in st.session_state:
        st.session_state.ai_data = None

    # 檢查是否有圖檔
    if image:
        # 檢查是否有 Key
        if not api_key:
            st.warning("⚠️ 請先在左側欄位輸入您的 Google API Key 才能開始辨識。")
        else:
            if st.button("🚀 執行 AI 辨識", type="primary"):
                
                # 設定使用者提供的 Key
                genai.configure(api_key=api_key)
                
                candidate_models = [
                    'gemini-1.5-flash',
                    'models/gemini-1.5-flash',
                    'gemini-1.5-flash-001',
                    'gemini-pro',
                    'models/gemini-pro'
                ]
                
                success_model = None
                response = None
                error_log = []

                with st.spinner("正在連線 AI 模型..."):
                    for model_name in candidate_models:
                        try:
                            model = genai.GenerativeModel(model_name)
                            
                            dim_instruction = ""
                            if "面積" in calc_mode:
                                dim_instruction = "請分別抓取該區域的「長度 (Length)」與「寬度 (Width)」。"
                            elif "周長" in calc_mode or "牆面" in calc_mode:
                                dim_instruction = "請抓取該範圍所有邊長的總和做為「長度 (dim1)」，寬度填 0。"

                            prompt = f"""
                            你是一位專業的建築估算師。請分析這張圖。
                            【任務目標】：
                            1. 找到符合使用者描述："{user_definition}" 的線段或區域。
                            2. 讀取該區域的尺寸標註數字。
                            
                            【重要規則】：
                            - **單位換算**：圖紙數字若為 mm (如 3500)，請除以 1000 換算為 m (如 3.5)。
                            - **排除干擾**：忽略標高(FL)、編號、圖號。只抓尺寸。
                            - {dim_instruction}
                            
                            請輸出純 JSON 格式 (無 markdown)：
                            [
                                {{
                                    "item": "項目名稱",
                                    "dim1": 數字(長度/周長, m),
                                    "dim2": 數字(寬度, m, 若無0),
                                    "note": "備註"
                                }}
                            ]
                            """
                            
                            response = model.generate_content([prompt, image])
                            success_model = model_name
                            break 
                            
                        except Exception as e:
                            # 捕捉如果是 Key 錯誤，直接回報給使用者
                            if "API_KEY_INVALID" in str(e) or "403" in str(e):
                                error_log.append(f"API Key 無效或權限不足")
                                break # Key 錯了就不用試其他模型了，直接跳出
                            
                            error_log.append(f"{model_name} 連線失敗")
                            continue

                if success_model and response:
                    st.toast(f"✅ 連線成功！使用模型：{success_model}")
                    try:
                        clean_json = response.text.replace("```json", "").replace("```", "").strip()
                        data = json.loads(clean_json)
                        st.session_state.ai_data = pd.DataFrame(data)
                        st.success("辨識完成！")
                    except:
                        st.error("AI 回傳資料格式有誤，請再試一次。")
                else:
                    if "API Key 無效" in str(error_log):
                        st.error("🚫 您的 API Key 無效。請檢查是否複製完整，或是否已在 Google AI Studio 開通權限。")
                    else:
                        st.error("❌ 連線失敗，請稍後再試。")
                        st.write("Debug info:", error_log)

    # --- Data Editor ---
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
                "計算式": f"{d1} * {d2}" if "面積" in calc_mode else f"{d1}",
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
        csv = result_df.to_csv(index=False).encode('utf-8-sig')
        st.download_button("📥 下載報表", csv, "takeoff.csv", "text/csv")
