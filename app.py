import streamlit as st
import google.generativeai as genai
from PIL import Image
import pandas as pd
import json
import fitz  # PyMuPDF
import io    # 處理資料流

# --- [防呆機制] 檢測 Excel 引擎 ---
try:
    import openpyxl
    HAS_OPENPYXL = True
except ImportError:
    HAS_OPENPYXL = False

# --- 1. 網頁設定 ---
st.set_page_config(page_title="AI 工程算量平台 (v14.3 自適應修正版)", page_icon="🏗️", layout="wide")

# --- 2. 側邊欄設定 ---
with st.sidebar:
    st.header("🔑 啟動金鑰 (BYOK)")
    
    st.info("ℹ️ 請輸入您的 Google API Key (AIza 開頭)")
    api_key = st.text_input("API Key", type="password", placeholder="貼上 AIza... 開頭的 Key")
    
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
    
    st.header("🤖 選擇模型")
    model_option = st.selectbox(
        "建議使用 Pro 版本以進行幾何分類",
        [
            "models/gemini-2.5-pro",       # 推薦：幾何邏輯最強
            "models/gemini-2.0-flash",     # 速度快
            "models/gemini-1.5-pro"
        ],
        index=0 
    )
    
    st.divider()
    
    st.header("🎨 定義規則")
    
    st.subheader("1. 辨識目標")
    st.info("系統將自動分類：L型 / 矩形 / 梯形")
    
    st.subheader("2. 空間/其他定義")
    user_definition = st.text_area(
        "補充說明", 
        value="1. 簡單L型 (L-Shape) 請拆成兩個矩形相加。\n2. 看到斜角才用梯形公式。\n3. 紅色區塊獨立計算。",
        height=100
    )
    
    calc_mode = st.radio(
        "3. 計算模式",
        ["計算平面面積 (Area)", "計算周長 (Perimeter)", "計算牆面/表面積 (周長 x 高度)"]
    )
    
    wall_height = 0.0
    if "牆面" in calc_mode:
        wall_height = st.number_input("樓層高度 (m)", value=3.0, step=0.1)

# --- 3. 主畫面 ---
st.title("🏗️ AI 工程算量平台 (v14.3 自適應修正版)")
st.caption(f"✅ 新增形狀分類器 (L-Shape/Rect/Trap) | 修正簡單圖形誤判 | 當前模型: {model_option}")
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
                model = genai.GenerativeModel(model_option)
                st.toast(f"正在進行幾何分類與運算...")
                
                # --- v14.3 Prompt: 自適應幾何分類 ---
                dim_instruction = ""
                if "面積" in calc_mode:
                    dim_instruction = f"""
                    1. **STEP 1: Shape Classification (CRITICAL)**:
                       - Scan the image for closed shapes (Green/Red).
                       - Classify each shape as: "Rectangle", "L-Shape" (combination of 2 rects), or "Trapezoid" (slanted edge).
                       
                    2. **STEP 2: Apply Specific Math**:
                       - **IF L-Shape**: You MUST split it into Rectangle A and Rectangle B. 
                         - Math: `(Length_A * Width_A) + (Length_B * Width_B)`.
                         - Note example: "Split: (2.4*1.1) + (1.2*0.8)".
                       - **IF Trapezoid** (Slanted corner): 
                         - Math: `((Top + Bottom) / 2) * Height`.
                       - **IF Simple Rectangle**:
                         - Math: `Length * Width`.
                         
                    3. **STEP 3: Dimension Extraction**:
                       - Dimensions are in mm. Convert to meters (e.g., 2425 -> 2.425).
                       - Use Magenta/Purple lines for numbers.
                       
                    4. **Output Format**:
                       - JSON list with keys: "shape_type", "item", "dim1", "dim2", "note".
                       - 'dim1' = Calculated Net Area. 'dim2' = 1.
                    """
                elif "周長" in calc_mode or "牆面" in calc_mode:
                    dim_instruction = f"""
                    1. Trace boundaries of all shapes.
                    2. Sum segments.
                    3. Set 'dim1' = Total Perimeter (m), 'dim2' = 0.
                    """

                prompt = f"""
                You are a Senior Quantity Surveyor. Analyze this image.
                User Rules: {user_definition}
                
                TASK:
                {dim_instruction}
                
                Return ONLY a JSON list (no markdown).
                """
                
                response = model.generate_content([prompt, image])
                
                try:
                    clean_json = response.text.replace("```json", "").replace("```", "").strip()
                    data = json.loads(clean_json)
                    st.session_state.ai_data = pd.DataFrame(data)
                    st.success(f"✅ 辨識完成")
                except:
                    st.error("AI 回傳格式無法解析")
                    st.write("Raw output:", response.text)
                
            except Exception as e:
                st.error(f"❌ 連線失敗: {e}")

    # --- Data Editor & Calculation ---
    if st.session_state.ai_data is not None:
        edited_df = st.data_editor(
            st.session_state.ai_data,
            column_config={
                "shape_type": "形狀分類",
                "item": "項目說明",
                "dim1": st.column_config.NumberColumn("長度/淨面積 (m/m²)", format="%.3f"),
                "dim2": st.column_config.NumberColumn("寬度/系數", format="%.3f"),
                "note": "AI 計算依據"
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
            formula_str = ""
            
            if "面積" in calc_mode:
                val = d1 * d2 
                unit = "m²"
                # 顯示邏輯：若 dim2=1 且 note 中有 + 號，代表是組合運算
                if d2 == 1.0:
                    formula_str = f"Net Area ({row.get('shape_type','Custom')})"
                else:
                    formula_str = f"{d1} * {d2}"
                    
            elif "周長" in calc_mode:
                val = d1 
                unit = "m"
                formula_str = f"{d1}"
            elif "牆面" in calc_mode:
                val = d1 * wall_height
                unit = "m²"
                formula_str = f"{d1} * {wall_height}"
            
            results.append({
                "形狀": row.get("shape_type", ""),
                "項目": row.get("item", ""),
                "計算式": formula_str,
                "小計": round(val, 2),
                "單位": unit,
                "備註": row.get("note", "")
            })
            
        result_df = pd.DataFrame(results)
        st.divider()
        st.subheader("3. 最終計算書")
        
        total_val = result_df["小計"].sum()
        first_unit = result_df['單位'].iloc[0] if not result_df.empty else ""
        st.metric("總數量", f"{total_val:,.2f} {first_unit}")
        st.dataframe(result_df, use_container_width=True)
        
        # --- [v14.3 穩定匯出模組] ---
        if not result_df.empty:
            st.subheader("4. 匯出選項")
            
            if HAS_OPENPYXL:
                output = io.BytesIO()
                with pd.ExcelWriter(output, engine='openpyxl') as writer:
                    result_df.to_excel(writer, index=False, sheet_name='算量明細')
                
                st.download_button(
                    label="📥 下載 Excel 報表 (.xlsx)",
                    data=output.getvalue(),
                    file_name="AI_Quantity_Takeoff.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    type="primary"
                )
            else:
                st.warning("⚠️ 系統偵測到環境缺少 'openpyxl'，已自動切換為 CSV 格式。")
                csv_data = result_df.to_csv(index=False).encode('utf-8-sig')
                
                st.download_button(
                    label="📥 下載 CSV 報表 (.csv)",
                    data=csv_data,
                    file_name="AI_Quantity_Takeoff.csv",
                    mime="text/csv",
                    type="primary"
                )
