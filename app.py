import streamlit as st
import sqlite3
import pandas as pd
from google import genai # <--- 換成新版的套件
import os
from dotenv import load_dotenv
from datetime import datetime
import json
from datetime import date # 記得確認最上方有 import 這個


# 1. 載入環境變數與設定 Gemini
load_dotenv()
# 使用新版的 Client 初始化方式
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

# 2. 初始化 SQLite 資料庫
def init_db():
    conn = sqlite3.connect('todo.db')
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS todos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT,
            task TEXT,
            status BOOLEAN DEFAULT 0,
            log TEXT DEFAULT ''
        )
    ''')
    conn.commit()
    return conn

conn = init_db()

# 3. Gemini 解析任務的 Agent 邏輯 (新版寫法)
def extract_tasks_from_text(user_input):
    prompt = f"""
    你是一個 TODO List 助理。請從以下使用者的自然語言中，擷取出他要完成的任務。
    請務必只回傳 JSON 格式，不要有任何其他廢話或 Markdown 標記。
    格式範例：{{"tasks": ["任務1", "任務2"]}}
    
    使用者輸入：「{user_input}」
    """
    try:
        # 新版的呼叫方式
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt
        )
        clean_text = response.text.replace('```json', '').replace('```', '').strip()
        result = json.loads(clean_text)
        return result.get("tasks", [])
    except Exception as e:
        st.error(f"解析失敗: {e}")
        return []



# 4. Streamlit 介面
st.title("🚀 Gemini AI TODO & 日誌本")

# --- 區塊 A：日曆選擇器 ---
# 預設顯示今天，並把選擇的日期轉成 YYYY-MM-DD 字串
selected_date = st.date_input("📅 選擇你想查看或新增任務的日期", value=date.today())
selected_date_str = selected_date.strftime("%Y-%m-%d")

# --- 區塊 B：動態過濾的任務清單 ---
st.subheader(f"📋 {selected_date_str} 的任務清單")

# 從資料庫撈出資料 (此時 date 欄位還是字串)
df = pd.read_sql_query("SELECT * FROM todos WHERE date = ?", conn, params=(selected_date_str,))

if not df.empty:
    # 【關鍵修復】把 Pandas DataFrame 裡的 date 欄位，從字串轉成真正的日期物件
    df['date'] = pd.to_datetime(df['date']).dt.date

    # 接下來再丟給 data_editor 就不會報錯了
    edited_df = st.data_editor(
        df,
        column_config={
            "id": None, 
            "date": st.column_config.DateColumn("日期 (可點擊修改)", format="YYYY-MM-DD"),
            "task": "任務內容",
            "status": st.column_config.CheckboxColumn("完成?", default=False),
            "log": "日誌/成效"
        },
        disabled=["task"], 
        hide_index=True,
        key="todo_editor",
        use_container_width=True
    )
    
    # ... 下面的儲存按鈕邏輯保持不變 ...

    if st.button("💾 儲存變更 (包含日期修改)"):
        c = conn.cursor()
        for index, row in edited_df.iterrows():
            # 確保寫回資料庫的日期是字串格式
            new_date = str(row['date'])[:10] 
            c.execute("UPDATE todos SET date = ?, status = ?, log = ? WHERE id = ?", 
                      (new_date, int(row['status']), row['log'], row['id']))
        conn.commit()
        st.success("變更已儲存！")
        st.rerun() # 存檔後重新整理，如果日期被改到其他天，該任務就會從今天的畫面消失
else:
    st.info(f"這天 ({selected_date_str}) 目前沒有任務，請在下方建立！")

# --- 區塊 C：聊天輸入框 ---
# 提示字元跟著日期動態改變
user_input = st.chat_input(f"請輸入 {selected_date_str} 的計畫 (例如：幫我記下下午要推導SVM...)")

if user_input:
    st.toast(f"🧠 AI 正在解析指令：{user_input}")
    
    tasks = extract_tasks_from_text(user_input)
    
    if tasks:
        c = conn.cursor()
        for t in tasks:
            # 【關鍵修改】把任務塞進「你剛剛在日曆上選擇的日期」，而不是永遠塞進今天
            c.execute("INSERT INTO todos (date, task, status, log) VALUES (?, ?, ?, ?)", (selected_date_str, t, False, ""))
        conn.commit()
        st.rerun() 
    else:
        st.error("AI 好像沒有抓到具體的任務，能換個說法嗎？")