import streamlit as st
import google.generativeai as genai
from PIL import Image
import pandas as pd
import json

# --- 1. 網頁設定 ---
st.set_page_config(page_title="AI 工程算量平台 (Pro/Ultra 最終修復版)", page_icon="🏗️", layout="wide")

# --- 2. 側邊欄：設定與規則 ---
with st.sidebar:
    st.header("🔑 系統設定")
    # 嘗試從 secrets 讀取 key，如果沒有就留空讓使用者填
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
st.title("🏗️ AI 工程算量平台 (最終修復版)")
st.caption("v5.0 Ultra: 修復模型連線錯誤，增強數字辨識準確度")
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
    
    # 初始化 Session State (讓資料不會因為點擊其他按鈕而消失)
    if 'ai_data' not in st.session_state:
        st.session_state.ai_data = None

    # 按鈕觸發 AI 辨識
    if uploaded_file and api_key:
        if st.button("🚀 執行 AI 辨識", type="primary"):
            try:
                # 設定 API Key
                genai.configure(api_key=api_key)
                
                # --- 關鍵修正：直接指定模型，不讓程式自己猜 ---
                model = genai.GenerativeModel('gemini-1.5-flash')
                st.toast("連線成功！正在使用 gemini-1.5-flash 進行分析...")

                with st.spinner("AI 正在讀取圖面數值... (請稍候約 5-10 秒)"):
                    
                    # 依據模式調整 Prompt 提示詞
                    dim_instruction = ""
                    if "面積" in calc_mode:
                        dim_instruction = "請分別抓取該區域的「長度 (Length)」與「寬度 (Width)」。"
                    elif "周長" in calc_mode or "牆面" in calc_mode:
                        dim_instruction = "請抓取該範圍所有邊長的總和做為「長度 (dim1)」，寬度填 0。"

                    # --- 關鍵修正：更聰明的 Prompt ---
                    prompt = f"""
                    你是一位專業的建築估算師 (Quantity Surveyor)。請分析這張圖。
                    
                    【任務目標】：
                    1. 找到符合使用者描述："{user_definition}" 的線段或區域。
                    2. 讀取該區域的尺寸標註數字。
                    
                    【重要規則 - 必讀】：
                    - **單位換算**：圖紙上的數字若為毫米 (mm) (例如 3500, 520)，請務必除以 1000 換算為「公尺 (m)」(例如 3.5, 0.52)。
                    - **排除干擾**：請忽略樓層標高(FL)、門窗編號、圖號。只看尺寸標註線。
                    - {dim_instruction}
                    
                    請輸出純 JSON 格式，格式如下 (不要加 markdown 標籤)：
                    [
                        {{
                            "item": "項目名稱",
                            "dim1": 數字(長度/周長, 公尺),
                            "dim2": 數字(寬度, 公尺, 若無則填0),
                            "note": "備註(例如: 原始標註3500mm)"
                        }}
                    ]
                    """
                    
                    # 發送請求
                    response = model.generate_content([prompt, image])
                    
                    # 清理回傳的文字，確保是純 JSON
                    clean_json = response.text.replace("```json", "").replace("```", "").strip()
                    
                    # 轉成資料表
                    data = json.loads(clean_json)
                    st.session_state.ai_data = pd.DataFrame(data)
                    st.success("✅ 辨識完成！請在下方表格檢查數據。")
                    
            except Exception as e:
                st.error(f"發生錯誤：{e}")
                st.info("如果是 404 錯誤，請檢查 API Key 是否正確，或該帳號是否已開通 Gemini API 權限。")

    # --- 核心功能：可編輯表格 (Data Editor) ---
    if st.session_state.ai_data is not None:
        
        st.info("💡 提示：AI 偶爾會看錯，您可以直接點擊表格內的數字修改，下方的總金額會自動重算！")
        
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
        
        # --- 自動後端運算 (絕對準確的 Python 計算) ---
        results = []
        for index, row in edited_df.iterrows():
            # 確保抓出來的是數字，如果是空的就當作 0
            try:
                d1 = float(row.get("dim1", 0))
            except: d1 = 0.0
            
            try:
                d2 = float(row.get("dim2", 0))
            except: d2 = 0.0
            
            val = 0.0
            formula = ""
            
            # 根據模式計算
            if "面積" in calc_mode:
                val = d1 * d2
                formula = f"{d1} * {d2}"
                unit = "m²"
            elif "周長" in calc_mode:
                val = d1 
                formula = f"{d1}"
                unit = "m"
            elif "牆面" in calc_mode:
                val = d1 * wall_height
                formula = f"{d1} * {wall_height}"
                unit = "m²"
            
            results.append({
                "項目": row.get("item", "未命名"),
                "計算式": formula,
                "小計": round(val, 2),
                "單位": unit
            })
            
        result_df = pd.DataFrame(results)
        
        # 顯示最終計算書
        st.divider()
        st.subheader("3. 最終計算書 (自動重算)")
        
        # 總計
        total_val = result_df["小計"].sum()
        first_unit = result_df['單位'].iloc[0] if not result_df.empty else ""
        
        # 顯示大大的總數字
        st.metric(label="總數量 (Grand Total)", value=f"{total_val:,.2f} {first_unit}")
        
        st.dataframe(result_df, use_container_width=True)
        
        # 下載按鈕
        csv = result_df.to_csv(index=False).encode('utf-8-sig')
        st.download_button(
            label="📥 下載最終 Excel/CSV 報表",
            data=csv,
            file_name="final_takeoff.csv",
            mime="text/csv"
        )
