import streamlit as st
import google.generativeai as genai
from PIL import Image
import pandas as pd
import json
import fitz  # PyMuPDF
import io    # 新增：用於處理二進制流 (Excel 匯出)

# --- 1. 網頁設定 ---
st.set_page_config(page_title="AI 工程算量平台 (v13.4 Excel 匯出版)", page_icon="🏗️", layout="wide")

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
        "建議使用 Pro 版本以精準識別顏色",
        [
            "models/gemini-2.5-pro",       # 推薦：顏色與幾何邏輯最強
            "models/gemini-2.5-flash",     # 速度快
            "models/gemini-2.0-flash",     # 備用
            "models/gemini-1.5-pro"
        ],
        index=0 
    )
    
    st.divider()
    
    st.header("🎨 定義規則")
    
    # 尺寸顏色選擇器
    st.subheader("1. 尺寸標註顏色")
    st.caption("請指定圖面上「尺寸線/數字」的顏色：")
    dim_color_ui = st.selectbox(
        "選擇顏色 (Dimension Color)",
        [
            "Magenta (紫紅/洋紅)", 
            "Red (紅)", 
            "Yellow (黃)", 
            "Green (綠)", 
            "Cyan (青)", 
            "Blue (藍)", 
            "White/Black (白/黑)",
            "Orange (橘)"
        ],
        index=0 
    )
    
    # 顏色映射字典
    color_map = {
        "Magenta (紫紅/洋紅)": "Magenta/Purple",
        "Red (紅)": "Red",
        "Yellow (黃)": "Yellow",
        "Green (綠)": "Green",
        "Cyan (青)": "Cyan",
        "Blue (藍)": "Blue",
        "White/Black (白/黑)": "White or Black",
        "Orange (橘)": "Orange"
    }
    selected_dim_color = color_map[dim_color_ui]

    st.subheader("2. 空間/其他定義")
    user_definition = st.text_area(
        "補充說明 (例如：綠色線是牆心...)", 
        value="例如：綠色線 (Green Lines) 是房間邊界範圍",
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
st.title("🏗️ AI 工程算量平台 (v13.4 Excel 匯出版)")
st.caption(f"✅ 已鎖定尺寸顏色: {selected_dim_color} | 支援 .xlsx 匯出 | 模型: {model_option}")
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
                st.toast(f"正在鎖定 {selected_dim_color} 色層進行分析...")
                
                # Prompt 邏輯
                dim_instruction = ""
                if "面積" in calc_mode:
                    dim_instruction = f"""
                    1. **STRICT COLOR RULE**: 
                       - ONLY look for numbers and dimension lines in **{selected_dim_color}** color.
                       - Ignore numbers in other colors.
                    2. **Unit Conversion**: Dimensions are in mm. Convert to meters (e.g., 2545 -> 2.545).
                    3. **Geometry Logic**:
                       - **Irregular/Chamfered Shapes**: Use the dimension lines ({selected_dim_color}) to calculate the Net Area.
                       - **Trapezoids**: (Top + Bottom)/2 * Height.
                       - **Output**: Set 'dim1' = Net Area (m²), Set 'dim2' = 1.
                       - **Note**: Write the formula you used.
                    """
                elif "周長" in calc_mode or "牆面" in calc_mode:
                    dim_instruction = f"""
                    1. Trace the boundary lines (defined in user rules).
                    2. Use the **{selected_dim_color}** numbers to determine segment lengths.
                    3. Sum all segments.
                    4. Set 'dim1' = Total Perimeter (m), 'dim2' = 0.
                    """

                prompt = f"""
                You are a Senior Quantity Surveyor. Analyze this image.
                
                USER DEFINED RULES:
                - Dimension Color: **{selected_dim_color}** (Primary Source of Truth for lengths)
                - Other Rules: {user_definition}
                
                TASK:
                {dim_instruction}
                
                Return ONLY a JSON list (no markdown) with keys: "item", "dim1", "dim2", "note".
                Example: [{{"item": "Room A", "dim1": 1.722, "dim2": 1.0, "note": "Trapezoid calc using {selected_dim_color} dims"}}]
                """
                
                response = model.generate_content([prompt, image])
                
                try:
                    clean_json = response.text.replace("```json", "").replace("```", "").strip()
                    data = json.loads(clean_json)
                    st.session_state.ai_data = pd.DataFrame(data)
                    st.success(f"✅ 辨識完成 (已過濾 {selected_dim_color} 尺寸)")
                except:
                    st.error("AI 回傳格式無法解析，請重試或更換模型。")
                    st.write("Raw output:", response.text)
                
            except Exception as e:
                st.error(f"❌ 連線失敗")
                st.error(str(e))

    # --- Data Editor & Calculation ---
    if st.session_state.ai_data is not None:
        edited_df = st.data_editor(
            st.session_state.ai_data,
            column_config={
                "item": "項目",
                "dim1": st.column_config.NumberColumn("長度/面積 (m/m²)", format="%.3f"),
                "dim2": st.column_config.NumberColumn("寬度/系數", format="%.3f"),
                "note": "AI 計算說明"
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
                "計算式": f"{d1} * {d2}" if "面積" in calc_mode else (f"{d1} * {wall_height}" if "牆面" in calc_mode else f"{d1}"),
                "小計": round(val, 2),
                "單位": unit,
                "備註": row.get("note", "")
            })
            
        result_df = pd.DataFrame(results)
        st.divider()
        st.subheader("3. 最終計算書")
        
        # 顯示總計
        total_val = result_df["小計"].sum()
        first_unit = result_df['單位'].iloc[0] if not result_df.empty else ""
        st.metric("總數量", f"{total_val:,.2f} {first_unit}")
        
        # 顯示表格
        st.dataframe(result_df, use_container_width=True)
        
        # --- [新增] Excel 匯出功能 ---
        if not result_df.empty:
            # 建立 Excel Buffer
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                result_df.to_excel(writer, index=False, sheet_name='工程算量')
                # 這裡可以加入更多 Sheet，例如原始數據等
            
            excel_data = output.getvalue()
            
            st.download_button(
                label="📥 下載 Excel 計算書",
                data=excel_data,
                file_name="AI_Quantity_Takeoff.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
