import streamlit as st
import google.generativeai as genai
import sys

st.set_page_config(page_title="系統診斷工具", page_icon="🩺")

st.title("🩺 AI 系統自我診斷報告")

# 1. 檢查軟體版本
st.subheader("1. 軟體環境檢查")
st.write(f"Python Version: `{sys.version}`")
try:
    lib_version = genai.__version__
    st.write(f"Google AI SDK Version: `{lib_version}`")
    
    # 判斷版本是否合格
    ver_parts = lib_version.split('.')
    if int(ver_parts[1]) >= 7:
        st.success("✅ SDK 版本合格 (>= 0.7.0)，應該支援 Flash 模型。")
    else:
        st.error("❌ SDK 版本過舊！這就是導致 404 的元兇。")
        st.info("請檢查 requirements.txt 是否寫入： google-generativeai>=0.7.2")

except Exception as e:
    st.error(f"無法讀取版本號：{e}")

st.divider()

# 2. 檢查 API Key 與可用模型
st.subheader("2. API Key 連線測試")
api_key = st.text_input("請輸入 API Key 進行測試", type="password")

if st.button("🚀 開始連線測試"):
    if not api_key:
        st.warning("請輸入 Key")
    else:
        try:
            genai.configure(api_key=api_key)
            
            st.write("正在嘗試連線 Google 伺服器...")
            
            # 列出所有可用模型
            models = list(genai.list_models())
            
            st.success("🎉 連線成功！您的 API Key 是有效的。")
            st.write("您的帳號可以使用以下模型：")
            
            # 整理並顯示模型清單
            model_names = [m.name for m in models]
            st.code(model_names)
            
            # 幫使用者判斷該用哪個
            if 'models/gemini-1.5-flash' in model_names:
                st.markdown("### ✅ 推薦設定：")
                st.markdown("請在程式碼中使用 `model = genai.GenerativeModel('gemini-1.5-flash')`")
            elif 'models/gemini-pro-vision' in model_names:
                st.markdown("### ⚠️ Flash 不可用，請改用：")
                st.markdown("請在程式碼中使用 `model = genai.GenerativeModel('gemini-pro-vision')`")
            else:
                st.error("您的帳號似乎沒有任何視覺模型的使用權限。")

        except Exception as e:
            st.error("❌ 連線失敗！")
            st.error(f"錯誤代碼：{e}")
            st.markdown("""
            **可能原因：**
            1. API Key 複製錯誤 (有多餘空格？)
            2. 該 Google 帳號未開通 Generative Language API。
            3. Google Cloud 專案未設定 Billing (雖然 Flash 通常免費，但部分帳號需綁卡)。
            """)
