import streamlit as st
import google.generativeai as genai
from PIL import Image
import pandas as pd
import json

# --- 1. 網頁設定 ---
st.set_page_config(page_title="AI 工程算量平台 (專業校對版)", page_icon="🏗️", layout="wide")

# --- 2. 側邊欄 ---
with st.sidebar:
    st.header("🔑 系統設定")
    try:
        default_key = st.secrets["GOOGLE_API_KEY"]
    except:
        default_key = ""
    api_key = st.text_input("API Key", value=default_key, type="password")
    
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
st.title("🏗️ AI 工程算量平台 (專業校對版)")
st.caption("v4.0 Update: 新增人工校對與自動重算功能")
st.markdown("---")

col_img, col_data = st.columns([1, 1.5])

with col_img:
    st.subheader("1. 圖說檢視")
    uploaded_file = st.file_uploader("上傳圖檔 (JPG/PNG)", type=["jpg", "jpeg", "png"])
    if uploaded_file:
        image = Image.open(uploaded_file)
        st.image(image, caption="已上傳圖說", use_column_width=True)

with col_data:
    st.subheader("2. 算量校對表")
    
    # 初始化 Session State 來儲存 AI 的結果，避免重新整理後消失
    if 'ai_data' not in st.session_state:
        st.session_state.ai_data = None

    # 按鈕觸發 AI 辨識
    if uploaded_file and api_key:
        if st.button("🚀 執行 AI 辨識", type="primary"):
            try:
                genai.configure(api_key=api_key)
                
                # 自動搜尋模型邏輯
                target_model_name = 'gemini-1.5-flash'
                try:
                    all_models = [m.name for m in genai.list_models()]
                    if 'models/gemini-1.5-pro' in all_models: # Pro 模型視覺能力更強，優先使用
                        target_model_name = 'gemini-1.5-pro'
                    elif 'models/gemini-1.5-flash' in all_models:
                        target_model_name = 'gemini-1.5-flash'
                    elif 'models/gemini-pro-vision' in all_models:
                        target_model_name = 'gemini-pro-vision'
                except:
                    pass
                
                model = genai.GenerativeModel(target_model_name)
                st.toast(f"正在使用模型：{target_model_name} 進行分析...")

                with st.spinner("AI 正在讀取圖面數值..."):
                    
                    # 依據模式調整 Prompt
                    dim_prompt = ""
                    if "面積" in calc_mode:
                        dim_prompt = "請分別抓取「長度 (Length)」與「寬度 (Width)」。"
                    elif "周長" in calc_mode or "牆面" in calc_mode:
                        dim_prompt = "請抓取該範圍所有邊長的總和做為「周長/長度」。"

                    prompt = f"""
                    你是一位專業的估算師。請分析這張圖，並嚴格依照以下步驟：
                    1. 找到符合【使用者定義】顏色的區塊或線段。
                    2. 讀取該線段旁的數字標註（Dimension Text）。
                       - 注意：如果數字是毫米(mm)，請自動換算為公尺(m)。例如 3200 -> 3.2。
                       - 注意：請忽略標高符號或無關的編號。
                    3. {dim_prompt}
                    
                    【使用者定義】: {user_definition}
                    
                    請輸出 JSON 格式，包含欄位：
                    - "item": 項目名稱
                    - "dim1": 長度/周長 (數值, 公尺)
                    - "dim2": 寬度 (數值, 公尺, 若無則填 0)
                    - "note": 備註 (例如：原始標註是 5200mm)
                    """
                    
                    response = model.generate_content([prompt, image])
                    clean_json = response.text.replace("```json", "").replace("```", "").strip()
                    
                    data = json.loads(clean_json)
                    # 存入 Session State
                    st.session_state.ai_data = pd.DataFrame(data)
                    
            except Exception as e:
                st.error(f"辨識失敗：{e}")

    # --- 核心功能：可編輯表格 (Data Editor) ---
    if st.session_state.ai_data is not None:
        
        st.info("💡 提示：點擊表格內的數字可直接修改，總量會自動重算！")
        
        # 顯示可編輯表格
        edited_df = st.data_editor(
            st.session_state.ai_data,
            column_config={
                "item": "項目",
                "dim1": st.column_config.NumberColumn("長度/周長 (m)", format="%.2f"),
                "dim2": st.column_config.NumberColumn("寬度 (m)", format="%.2f"),
                "note": "AI 備註 (原始讀值)"
            },
            num_rows="dynamic", # 允許使用者手動新增列
            use_container_width=True
        )
        
        # --- 自動後端運算 (Self-Check Logic) ---
        # 這裡不依賴 AI 算乘法，而是用 Python 算，保證數學絕對正確
        
        results = []
        for index, row in edited_df.iterrows():
            d1 = float(row.get("dim1", 0) or 0)
            d2 = float(row.get("dim2", 0) or 0)
            
            val = 0.0
            formula = ""
            
            if "面積" in calc_mode:
                val = d1 * d2
                formula = f"{d1} * {d2}"
            elif "周長" in calc_mode:
                val = d1 # 假設 dim1 已經是總周長，或是使用者自己加總
                formula = f"{d1}"
            elif "牆面" in calc_mode:
                val = d1 * wall_height
                formula = f"{d1} * {wall_height}"
            
            results.append({
                "項目": row.get("item", ""),
                "計算式": formula,
                "小計": round(val, 2),
                "單位": "m2" if "周長" not in calc_mode else "m"
            })
            
        result_df = pd.DataFrame(results)
        
        # 顯示最終計算結果
        st.divider()
        st.subheader("3. 最終計算書")
        
        # 總計
        total_val = result_df["小計"].sum()
        st.metric("總數量 (Grand Total)", f"{total_val:,.2f} {result_df['單位'].iloc[0] if not result_df.empty else ''}")
        
        st.dataframe(result_df, use_container_width=True)
        
        # 下載
        csv = result_df.to_csv(index=False).encode('utf-8-sig')
        st.download_button("📥 下載最終報表", csv, "final_takeoff.csv", "text/csv")
