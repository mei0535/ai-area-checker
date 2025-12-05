import streamlit as st
import google.generativeai as genai
from PIL import Image
import pandas as pd
import json

# --- 1. 網頁設定 ---
st.set_page_config(page_title="AI 全能工程算量平台", page_icon="🏗️", layout="wide")

# --- 2. 側邊欄 ---
with st.sidebar:
    st.header("🔑 系統設定")
    
    try:
        default_key = st.secrets["GOOGLE_API_KEY"]
    except:
        default_key = ""
        
    api_key = st.text_input("API Key", value=default_key, type="password", help="請輸入 Google Gemini API Key")
    
    st.divider()
    
    st.header("🎨 自訂計算規則")
    st.info("請定義圖面顏色與計算目標")
    
    # [功能 1] 自訂空間/線條定義
    user_definition = st.text_area(
        "1. 顏色與空間定義 (請自由描述)",
        value="例如：\n- 黃色線條範圍是「A戶辦公室」\n- 紅色線條範圍是「B戶會議室」",
        height=100
    )
    
    # [功能 2] 選擇計算模式
    calc_mode = st.radio(
        "2. 計算目標",
        ["計算平面面積 (Area)", "計算周長 (Perimeter)", "計算牆面/表面積 (周長 x 高度)"]
    )
    
    # [功能 3] 若算牆面，需輸入高度
    wall_height = 0.0
    if "牆面" in calc_mode:
        st.write("---")
        st.markdown("#### 📏 設定樓高")
        wall_height = st.number_input("請輸入樓層高度 (m)", value=3.0, step=0.1, format="%.2f")
        st.caption(f"計算公式將為：周長 × {wall_height} m")

# --- 3. 主畫面 ---
st.title("🏗️ AI 全能工程算量平台")
st.markdown("---")

col_img, col_result = st.columns([1, 1.5])

with col_img:
    st.subheader("1. 上傳圖說")
    st.caption("支援 JPG / PNG 格式")
    uploaded_file = st.file_uploader("請上傳已標示顏色的圖檔", type=["jpg", "jpeg", "png"])
    
    if uploaded_file:
        image = Image.open(uploaded_file)
        st.image(image, caption="圖說預覽", use_column_width=True)

with col_result:
    st.subheader("2. AI 分析結果")
    
    if uploaded_file and api_key:
        if st.button("🚀 執行 AI 辨識與計算", type="primary"):
            try:
                genai.configure(api_key=api_key)
                
                with st.spinner("正在搜尋您帳號可用的最佳模型..."):
                    # --- 自動導航：搜尋可用模型 ---
                    target_model_name = ""
                    try:
                        # 取得所有可用模型
                        all_models = [m.name for m in genai.list_models()]
                        
                        # 優先順序：Flash -> Pro Vision -> Pro
                        if 'models/gemini-1.5-flash' in all_models:
                            target_model_name = 'gemini-1.5-flash'
                        elif 'models/gemini-pro-vision' in all_models:
                            target_model_name = 'gemini-pro-vision'
                        elif 'models/gemini-1.5-pro' in all_models:
                            target_model_name = 'gemini-1.5-pro'
                        else:
                            # 如果都沒有，就抓列表裡的第一個
                            target_model_name = all_models[0].replace('models/', '')
                            
                        st.caption(f"✅ 已自動連線至模型：`{target_model_name}`")
                        
                    except Exception as e:
                        # 如果連搜尋都失敗，直接盲猜一個最舊的保底
                        target_model_name = 'gemini-pro-vision'
                        st.caption(f"⚠️ 搜尋模型失敗，嘗試使用預設模型：`{target_model_name}`")

                # 設定模型
                model = genai.GenerativeModel(target_model_name)
                
                with st.spinner("AI 正在讀圖並進行運算..."):
                    
                    math_logic = ""
                    unit_hint = ""
                    
                    if "平面面積" in calc_mode:
                        math_logic = "請辨識該範圍的長寬標示，計算其「平面面積 (Area, m2)」。"
                        unit_hint = "m2"
                    elif "周長" in calc_mode:
                        math_logic = "請辨識該範圍的邊長標示，計算其「總周長 (Perimeter, m)」。"
                        unit_hint = "m"
                    elif "牆面" in calc_mode:
                        math_logic = f"請先計算該範圍的「總周長」，然後將周長乘以高度 {wall_height} 公尺，得出「垂直牆表面積 (Wall Area, m2)」。"
                        unit_hint = "m2"

                    # 這裡的 Prompt 也全部改成繁體中文，確保 AI 回應也是繁體
                    prompt = f"""
                    你是一位專業的建築估算師。請依照以下規則分析這張圖說：

                    【使用者定義 (顏色代表意義)】
                    {user_definition}

                    【計算目標與公式】
                    {math_logic}

                    【輸出格式要求】
                    請務必輸出一個 JSON 格式的清單 (Array of Objects)，包含以下欄位：
                    - "item_name": 項目名稱 (依據顏色定義)
                    - "description": 計算邏輯說明 (例如：周長 x {wall_height})
                    - "formula_str": 數值運算式 (例如：(10+5)*2 * {wall_height})
                    - "result": 最終結果數字 (浮點數)
                    - "unit": 單位 ({unit_hint})

                    若圖面模糊無法辨識，請略過。請直接輸出 JSON，不要 Markdown 標記。
                    """
                    
                    response = model.generate_content([prompt, image])
                    
                    # 解析 JSON
                    clean_json = response.text.replace("```json", "").replace("```", "").strip()
                    
                    try:
                        data = json.loads(clean_json)
                        if data:
                            df = pd.DataFrame(data)
                            
                            st.success("✅ 計算完成！")
                            
                            # 顯示總計
                            if "result" in df.columns:
                                try:
                                    total_val = df['result'].sum()
                                    st.metric("總數量 (Total)", f"{total_val:,.2f} {df['unit'].iloc[0]}")
                                except: pass
                            
                            # 顯示詳細表格
                            st.dataframe(
                                df, 
                                column_config={
                                    "item_name": "項目/空間",
                                    "description": "計算邏輯",
                                    "formula_str": "算式過程",
                                    "result": "小計",
                                    "unit": "單位"
                                },
                                use_container_width=True
                            )
                            
                            # 下載按鈕
                            csv = df.to_csv(index=False).encode('utf-8-sig')
                            st.download_button("📥 下載計算書 (CSV)", csv, "takeoff_report.csv", "text/csv")
                        else:
                            st.warning("AI 無法識別符合規則的物件，請檢查圖面顏色是否清晰。")
                    except Exception as json_err:
                        st.error("AI 回傳格式解析失敗，可能是圖面過於複雜。")
                        st.caption("原始回傳內容：")
                        st.code(response.text)

            except Exception as e:
                st.error(f"發生錯誤：{e}")
                st.warning("請確認 API Key 是否正確，或嘗試重新整理網頁。")
    
    elif not uploaded_file:
        st.info("👈 請先上傳圖檔")
    elif not api_key:
        st.warning("👈 請輸入 API Key")
