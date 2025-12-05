import streamlit as st
import google.generativeai as genai
import sys

st.set_page_config(page_title="AI 系統診斷報告", page_icon="🩺", layout="wide")

st.title("🩺 Google Gemini API 權限診斷")

# 1. 軟體環境檢查
st.subheader("1. 軟體環境檢查")
st.write(f"Python Version: `{sys.version}`")
try:
    lib_version = genai.__version__
    st.write(f"Google AI SDK Version: `{lib_version}`")
    
    # 判斷版本是否合格
    ver_parts = lib_version.split('.')
    if int(ver_parts[1]) >= 7:
        st.success("✅ SDK 版本合格 (>= 0.7.0)，軟體端支援 Flash 模型。")
    else:
        st.error("❌ SDK 版本過舊！這是导致 404 的潛在原因之一。")
        st.info("請檢查 requirements.txt 是否寫入： google-generativeai>=0.7.2")

except Exception as e:
    st.error(f"無法讀取版本號：{e}")

st.divider()

# 2. 檢查 API Key 與可用模型
st.subheader("2. API Key 權限測試")
st.markdown("請輸入您的 API Key，系統將直接詢問 Google 伺服器您擁有哪些權限。")

# 嘗試從 Secrets 讀取預設 Key (方便您不用一直貼)
try:
    default_key = st.secrets["GOOGLE_API_KEY"]
except:
    default_key = ""

api_key = st.text_input("請輸入 API Key 進行測試", value=default_key, type="password")

if st.button("🚀 開始深度診斷"):
    if not api_key:
        st.warning("請先輸入 API Key")
    else:
        try:
            genai.configure(api_key=api_key)
            
            with st.spinner("正在連線 Google 伺服器進行身分驗證..."):
                # 嘗試列出所有可用模型
                models = list(genai.list_models())
                
                st.success("🎉 連線成功！您的 API Key 是有效的 (沒有被 Google 封鎖)。")
                
                st.markdown("### 📋 您的帳號可用模型清單：")
                model_names = [m.name for m in models]
                
                # 顯示原始清單供參考
                st.code(model_names)
                
                # 智慧判斷與建議
                st.markdown("### 💡 診斷結果與建議：")
                
                # 檢查 Flash 模型
                if 'models/gemini-1.5-flash' in model_names:
                    st.success("✅ **完美！** 您的帳號支援 `gemini-1.5-flash`。")
                    st.markdown("👉 請在正式版 `app.py` 中使用： `model = genai.GenerativeModel('gemini-1.5-flash')`")
                
                # 檢查 Pro Vision 模型
                elif 'models/gemini-pro-vision' in model_names:
                    st.warning("⚠️ 您的帳號不支援 Flash，但支援舊版 Vision。")
                    st.markdown("👉 請在正式版 `app.py` 中改用： `model = genai.GenerativeModel('gemini-pro-vision')`")
                
                # 檢查 1.0 Pro (純文字)
                elif 'models/gemini-pro' in model_names:
                    st.error("❌ 您的帳號僅支援「純文字」模型，無法讀取圖片！")
                    st.markdown("這通常是因為 API Key 建立在「非美國/台灣」的受限區域，或專案設定有誤。")
                    st.markdown("**解法：** 請嘗試重新建立一個 Google Cloud 專案，或更換 Google 帳號申請 Key。")
                
                else:
                    st.error("❌ 您的帳號似乎沒有任何 Generative AI 模型的使用權限。")

        except Exception as e:
            st.error("❌ 連線失敗！API Key 無法通過驗證。")
            st.code(f"錯誤訊息：{e}")
            st.markdown("""
            **常見失敗原因：**
            1. **API Key 複製錯誤**：請檢查是否有複製到空格？
            2. **權限未開通**：該 Google Cloud 專案未啟用 "Generative Language API"。
            3. **帳號問題**：某些 Workspace (公司/學校) 帳號可能被管理員鎖住權限。
            """)
