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
st.set_page_config(page_title="AI 工程算量平台 (v14.0 邏輯修正版)", page_icon="🏗️", layout="wide")

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
        "建議使用 Pro 版本以處理複雜邏輯",
        [
            "models/gemini-2.5-pro",       # 推薦：邏輯推理最強
            "models/gemini-2.0-flash",     # 速度快
            "models/gemini-1.5-pro"
        ],
        index=0 
    )
    
    st.divider()
    
    st.header("🎨 定義規則")
    
    # 這裡將邏輯升級為「多色層」選取
    st.subheader("1. 辨識目標顏色")
    st.info("系統預設同時搜尋：綠色(Green) 與 紅色(Red)")
    
    target_colors = "Green, Red" 
    dim_color = "Magenta (Purple)"

    st.subheader("2. 空間/其他定義")
    user_definition = st.text_area(
        "補充說明", 
        value="例如：最右邊的紅色區塊 (Red Box) 需獨立計算，不要漏項。",
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
st.title("🏗️ AI 工程算量平台 (v14.0 邏輯修正版)")
st.caption(f"✅ 修復縮排錯誤 | 支援紅/綠多區塊計算 | 當前模型: {model_option}")
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
                st.toast(f"正在分析多區塊 (Green/Red) 與尺寸邏輯...")
                
                # --- v14.0 Prompt: 多重邏輯修正 ---
                dim_instruction = ""
                if "面積" in calc_mode:
                    dim_instruction = f"""
                    1. **Target Identification**: 
                       - Identify ALL closed shapes drawn in **GREEN** OR **RED**.
                       - The **RED box** on the right is a separate room/area. DO NOT ignore it.
                       
                    2. **Dimension Logic (CRITICAL)**:
                       - Dimensions are in **{dim_color}**.
                       - Units are mm. Convert to meters (e.g., 1600 -> 1.6).
                       - **Association Rule**: Only use dimensions that physically span the length/width of the specific block.
                       - **Rightmost Block (Red)**: Its width is likely 1600. Look carefully for its Height. If a vertical dimension (like 3375) spans a larger range, DO NOT use it directly as the height of the Red box unless it matches. If height is missing, note it.
                       - **Bottom Green Block**: It has a chamfer (slanted corner). Use Trapezoid logic: ((Top_W + Bottom_W)/2) * H.
                       
                    3. **Output Format**:
                       - Return a JSON list.
                       - Keys: "item" (Name/Location), "dim1" (Length/Net Area), "dim2" (Width/1), "note" (FORMULA used).
                       - **IMPORTANT**: In the 'note', strictly write the math you did. Example: "1.6 * 2.5 (estimated)" or "Trapezoid: ((2.545+2.175)/2)*0.73".
                    """
                elif "周長" in calc_mode or "牆面" in calc_mode:
                    dim_instruction = f"""
                    1. Trace all GREEN and RED boundaries.
                    2. Sum segments to get Perimeter.
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
                "item": "項目/位置",
                "dim1": st.column_config.NumberColumn("長度/面積 (m)", format="%.3f"),
                "dim2": st.column_config.NumberColumn("寬度/系數", format="%.3f"),
                "note": "AI 計算式 (請核對)"
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
                "計算式": f"{d1}*{d2}" if "面積" in calc_mode else f"{d1}",
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
        
        # --- [v14.0 穩定匯出模組] ---
        if not result_df.empty:
            st.subheader("4. 匯出選項")
            
            # 使用正確縮排的 if-else 結構
            if HAS_OPENPYXL:
                # 方案 A: 有 Excel 引擎
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
                # 方案 B: 沒有 Excel 引擎 (Fallback)
                st.warning("⚠️ 系統偵測到環境缺少 'openpyxl'，已自動切換為 CSV 格式 (可用 Excel 開啟)。")
                csv_data = result_df.to_csv(index=False).encode('utf-8-sig')
                
                st.download_button(
                    label="📥 下載 CSV 報表 (.csv)",
                    data=csv_data,
                    file_name="AI_Quantity_Takeoff.csv",
                    mime="text/csv",
                    type="primary"
                )
