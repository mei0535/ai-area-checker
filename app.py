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
st.set_page_config(page_title="AI 工程算量平台 (v14.1 結構拆解版)", page_icon="🏗️", layout="wide")

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
        "建議使用 Pro 版本以執行空間拆解",
        [
            "models/gemini-2.5-pro",       # 推薦：邏輯最強
            "models/gemini-2.0-flash",     # 速度快
            "models/gemini-1.5-pro"
        ],
        index=0 
    )
    
    st.divider()
    
    st.header("🎨 定義規則")
    
    st.subheader("1. 辨識目標顏色")
    st.info("系統將搜尋綠色 (Green) 與紅色 (Red) 區域")
    
    st.subheader("2. 空間/其他定義")
    user_definition = st.text_area(
        "補充說明", 
        value="1. 將綠色區域拆解為：頂部(Top)、中間(Middle)、底部(Bottom)。\n2. 紅色區域(Red Box)獨立計算。\n3. 注意下方綠色區塊有斜角(Chamfer)。",
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
st.title("🏗️ AI 工程算量平台 (v14.1 結構拆解版)")
st.caption(f"✅ 強制分區掃描 (Top/Mid/Bot/Right) | 修正連通域誤判 | 當前模型: {model_option}")
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
                st.toast(f"正在執行 v14.1 結構拆解分析...")
                
                # --- v14.1 Prompt: 強制拆解邏輯 ---
                dim_instruction = ""
                if "面積" in calc_mode:
                    dim_instruction = f"""
                    1. **DECOMPOSITION STRATEGY (CRITICAL)**: 
                       - The Green lines look connected, but they form THREE distinct zones. DO NOT calculate as one big shape.
                       - **Zone A (Top Green)**: Look for dimensions 1100, 650, 675, 2425. It's an L-shape or rectangle cluster.
                       - **Zone B (Middle Green)**: The vertical connecting corridor.
                       - **Zone C (Bottom Green)**: The shape with width 2175/2545 and height 730. Note the SLANTED corner (Trapezoid).
                       - **Zone D (Right Red)**: The separate RED box (width ~1600).
                       
                    2. **Dimension Logic**:
                       - Units are mm. Convert to meters (e.g., 2545 -> 2.545).
                       - **Zone C (Trapezoid)**: Use formula ((Top+Bottom)/2)*Height -> ((2.545+2.175)/2)*0.73.
                       - **Zone D (Red Box)**: Width is ~1.6m. Estimate Height based on grid if not explicitly labeled (likely aligns with adjacent elements).
                       
                    3. **Output Requirements**:
                       - You MUST return at least 3-4 separate items.
                       - JSON keys: "zone_hint" (e.g., Top, Bottom, RedBox), "item", "dim1", "dim2", "note".
                       - 'dim1' = Net Area (m²). 'dim2' = 1.
                       - In 'note', show the formula used (e.g., "1.1*0.8 + 0.65*0.45").
                    """
                elif "周長" in calc_mode or "牆面" in calc_mode:
                    dim_instruction = f"""
                    1. Trace boundaries of Top Green, Bottom Green, and Red Box separately.
                    2. Sum segments.
                    3. Set 'dim1' = Perimeter (m), 'dim2' = 0.
                    """

                prompt = f"""
                You are a Senior Quantity Surveyor. Analyze this image using the Decomposition Strategy.
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
                    st.success(f"✅ 辨識完成 (已拆解為多個區域)")
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
                "zone_hint": "區域 (Zone)",
                "item": "項目說明",
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
                "區域": row.get("zone_hint", ""),
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
        
        # --- [v14.1 穩定匯出模組] ---
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
