import streamlit as st
import google.generativeai as genai
from PIL import Image
import pandas as pd
import json

# --- 1. 网页设定 ---
st.set_page_config(page_title="AI 全能工程算量平台", page_icon="🏗️", layout="wide")

# --- 2. 侧边栏：设定与规则 ---
with st.sidebar:
    st.header("🔑 系统设定")
    
    # 尝试自动读取 API Key (如果以后有设定 Secrets 的话)
    try:
        default_key = st.secrets["GOOGLE_API_KEY"]
    except:
        default_key = ""
        
    api_key = st.text_input("API Key", value=default_key, type="password", help="请输入 Google Gemini API Key")
    
    st.divider()
    
    st.header("🎨 自订计算规则")
    st.info("请定义图面颜色与计算目标")
    
    # [功能 1] 自订空间/线条定义
    user_definition = st.text_area(
        "1. 颜色与空间定义 (请自由描述)",
        value="例如：\n- 黄色线条范围是「A户办公室」\n- 红色线条范围是「B户会议室」",
        height=100
    )
    
    # [功能 2] 选择计算模式
    calc_mode = st.radio(
        "2. 计算目标",
        ["计算平面面积 (Area)", "计算周长 (Perimeter)", "计算墙面/表面积 (周长 x 高度)"]
    )
    
    # [功能 3] 如果选墙面，跳出高度输入框
    wall_height = 0.0
    if "墙面" in calc_mode:
        st.write("---")
        st.markdown("#### 📏 设定楼高")
        wall_height = st.number_input("请输入楼层高度 (m)", value=3.0, step=0.1, format="%.2f")
        st.caption(f"计算公式将为：周长 × {wall_height} m")

# --- 3. 主画面 ---
st.title("🏗️ AI 全能工程算量平台")
st.markdown("---")

col_img, col_result = st.columns([1, 1.5])

with col_img:
    st.subheader("1. 上传图说")
    st.caption("支援 JPG / PNG 格式")
    uploaded_file = st.file_uploader("请上传已标示颜色的图档", type=["jpg", "jpeg", "png"])
    
    if uploaded_file:
        image = Image.open(uploaded_file)
        st.image(image, caption="图说预览", use_column_width=True)

with col_result:
    st.subheader("2. AI 分析结果")
    
    if uploaded_file and api_key:
        if st.button("🚀 执行 AI 辨识与计算", type="primary"):
            try:
                genai.configure(api_key=api_key)
                
                # --- 这里设定为您帐号确定可用的模型 ---
                model = genai.GenerativeModel('gemini-1.5-flash')
                
                with st.spinner("AI 正在读图并进行运算..."):
                    
                    # --- 动态生成指令 (核心逻辑) ---
                    math_logic = ""
                    unit_hint = ""
                    
                    if "平面面积" in calc_mode:
                        math_logic = "请辨识该范围的长宽标示，计算其「平面面积 (Area, m2)」。"
                        unit_hint = "m2"
                    elif "周长" in calc_mode:
                        math_logic = "请辨识该范围的边长标示，计算其「总周长 (Perimeter, m)」。"
                        unit_hint = "m"
                    elif "墙面" in calc_mode:
                        math_logic = f"请先计算该范围的「总周长」，然后将周长乘以高度 {wall_height} 公尺，得出「垂直墙表面积 (Wall Area, m2)」。"
                        unit_hint = "m2"

                    prompt = f"""
                    你是一位专业的建筑估算师。请依照以下规则分析这张图说：

                    【使用者定义 (颜色代表意义)】
                    {user_definition}

                    【计算目标与公式】
                    {math_logic}

                    【输出格式要求】
                    请务必输出一个 JSON 格式的清单 (Array of Objects)，包含以下栏位：
                    - "item_name": 项目名称 (依据颜色定义)
                    - "description": 计算逻辑说明 (例如：周长 x {wall_height})
                    - "formula_str": 数值运算式 (例如：(10+5)*2 * {wall_height})
                    - "result": 最终结果数字 (浮点数)
                    - "unit": 单位 ({unit_hint})

                    若图面模糊无法辨识，请略过。请直接输出 JSON，不要 Markdown 标记。
                    """
                    
                    response = model.generate_content([prompt, image])
                    
                    # 解析 JSON
                    clean_json = response.text.replace("```json", "").replace("```", "").strip()
                    
                    try:
                        data = json.loads(clean_json)
                        if data:
                            df = pd.DataFrame(data)
                            
                            st.success("✅ 计算完成！")
                            
                            # 显示总计
                            if "result" in df.columns:
                                try:
                                    total_val = df['result'].sum()
                                    st.metric("总数量 (Total)", f"{total_val:,.2f} {df['unit'].iloc[0]}")
                                except: pass
                            
                            # 显示详细表格
                            st.dataframe(
                                df, 
                                column_config={
                                    "item_name": "项目/空间",
                                    "description": "计算逻辑",
                                    "formula_str": "算式过程",
                                    "result": "小计",
                                    "unit": "单位"
                                },
                                use_container_width=True
                            )
                            
                            # 下载按钮
                            csv = df.to_csv(index=False).encode('utf-8-sig')
                            st.download_button("📥 下载计算书 (CSV)", csv, "takeoff_report.csv", "text/csv")
                        else:
                            st.warning("AI 无法识别符合规则的物件，请检查图面颜色是否清晰。")
                    except Exception as json_err:
                        st.error("AI 回传格式解析失败，可能是图面过于复杂。")
                        st.caption("原始回传内容：")
                        st.code(response.text)

            except Exception as e:
                st.error(f"发生错误：{e}")
                st.warning("请确认 API Key 是否正确，或尝试重新整理网页。")
    
    elif not uploaded_file:
        st.info("👈 请先上传图档")
    elif not api_key:
        st.warning("👈 请输入 API Key")
