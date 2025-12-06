import streamlit as st
import google.generativeai as genai
from PIL import Image
import pandas as pd
import json
import fitz  # PyMuPDF 用來讀 PDF

# --- 1. 網頁設定 ---
st.set_page_config(page_title="AI 工程算量平台 (PDF/圖檔通用版)", page_icon="🏗️", layout="wide")

# --- 2. 側邊欄 ---
with st.sidebar:
    st.header("🔑 系統設定")
    try:
        default_key = st.secrets["GOOGLE_API_KEY"]
    except:
        default_key = ""
    api_key = st.text_input("輸入 Google API Key", value=default_key, type="password")
    
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
st.title("🏗️ AI 工程算量平台 (PDF 支援版)")
st.caption("v6.1 Ultra: 修正模型連線 404 錯誤")
st.markdown("---")

col_img, col_data = st.columns([1, 1.5])

# 初始化 image 變數
image = None

with col_img:
    st.subheader("1. 圖說檢視")
    uploaded_file = st.file_uploader("上傳圖檔 (JPG/PNG/PDF)", type=["jpg", "jpeg", "png", "pdf"])
    
    if uploaded_file:
        try:
            # --- 判斷檔案類型 ---
            if uploaded_file.name.lower().endswith('.pdf'):
                # 處理 PDF
                with st.spinner("正在將 PDF 轉為高解析圖片..."):
                    doc = fitz.open(stream=uploaded_file.read(), filetype="pdf")
                    page = doc[0]  # 讀取第一頁
                    pix = page.get_pixmap(dpi=300)
                    image = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                    st.success(f"已讀取 PDF 第一頁 (共 {len(doc)} 頁)")
            else:
                # 處理一般圖片
                image = Image.open(uploaded_file)
            
            st.image(image, caption=f"預覽：{uploaded_file.name}", use_column_width=True)
            
        except Exception as e:
            st.error(f"檔案讀取失敗：{e}")

with col_data:
    st.subheader("2. 算量校對表")
    
    if 'ai_data' not in st.session_state:
        st.session_state.ai_data = None

    if image and api_key:
        if st.button("🚀 執行 AI 辨識", type="primary"):
            try:
                genai.configure(api_key=api_key)
                
                # --- 【關鍵修正】使用更精確的模型名稱 ---
                # 如果 1.5-flash 報錯，通常改用 1.5-flash-001 或 gemini-pro-vision 就能解決
                try:
                    model = genai.GenerativeModel('gemini-1.5-flash-001') # 嘗試精確版號
                except:
                    model = genai.GenerativeModel('gemini-1.5-flash') # 退回通用版號

                st.toast("連線成功！正在分析圖面...")

                with st.spinner("AI 正在解讀圖面資訊..."):
                    
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
                    clean_json = response.text.replace("```json", "").replace("```", "").strip()
                    data = json.loads(clean_json)
                    st.session_state.ai_data = pd.DataFrame(data)
                    st.success("✅ 辨識完成！")
                    
            except Exception as e:
                st.error(f"AI 發生錯誤：{e}")
                st.info("建議檢查 API Key 是否正確，或稍後再試。")

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
