import streamlit as st
import sqlite3
import pandas as pd
import google.generativeai as genai
import os
from dotenv import load_dotenv
from datetime import datetime
import json

# 1. 載入環境變數與設定 Gemini
load_dotenv()
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

# 2. 初始化 SQLite 資料庫
def init_db():
    conn = sqlite3.connect('todo.db')
    c = conn.cursor()
    # 建立 todos 資料表
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

# 3. Gemini 解析任務的 Agent 邏輯
def extract_tasks_from_text(user_input):
    # 使用 Gemini Flash 模型，因為它速度快、適合做這種文本解析
    model = genai.GenerativeModel('gemini-2.5-flash')
    prompt = f"""
    你是一個 TODO List 助理。請從以下使用者的自然語言中，擷取出他要完成的任務。
    請務必只回傳 JSON 格式，不要有任何其他廢話或 Markdown 標記。
    格式範例：{{"tasks": ["任務1", "任務2"]}}
    
    使用者輸入：「{user_input}」
    """
    response = model.generate_content(prompt)
    try:
        # 清理可能帶有的 markdown json 標籤
        clean_text = response.text.replace('```json', '').replace('```', '').strip()
        result = json.loads(clean_text)
        return result.get("tasks", [])
    except Exception as e:
        st.error(f"解析失敗: {e}")
        return []

# 4. Streamlit 介面
st.title("🚀 Gemini AI TODO & 日記本")

# 區塊 A：透過自然語言輸入任務
with st.expander("🗣️ 對 AI 說出你的計畫", expanded=True):
    user_input = st.text_input("例如：幫我記下明天早上要寫趨勢OA，下午要看RTOS影片")
    if st.button("讓 AI 幫我建立任務"):
        if user_input:
            tasks = extract_tasks_from_text(user_input)
            today_str = datetime.now().strftime("%Y-%m-%d")
            c = conn.cursor()
            for t in tasks:
                c.execute("INSERT INTO todos (date, task, status, log) VALUES (?, ?, ?, ?)", (today_str, t, False, ""))
            conn.commit()
            st.success(f"成功新增 {len(tasks)} 筆任務！")
            st.rerun() # 重新載入頁面以更新表格

# 區塊 B：TODO List 與 日記 Log 區
st.subheader("📋 今日任務清單與回顧")
df = pd.read_sql_query("SELECT * FROM todos", conn)

if not df.empty:
    # 使用 Streamlit 強大的 data_editor 讓你可以直接在表格上打勾和打字
    edited_df = st.data_editor(
        df,
        column_config={
            "id": None, # 隱藏 ID 欄位
            "date": "日期",
            "task": "任務內容",
            "status": st.column_config.CheckboxColumn("是否完成?", default=False),
            "log": "日誌/成效回顧"
        },
        disabled=["date", "task"], # 不允許修改日期和任務內容
        hide_index=True,
        key="todo_editor"
    )

    # 儲存修改按鈕
    if st.button("💾 儲存今日進度與日誌"):
        c = conn.cursor()
        for index, row in edited_df.iterrows():
            c.execute("UPDATE todos SET status = ?, log = ? WHERE id = ?", 
                      (int(row['status']), row['log'], row['id']))
        conn.commit()
        st.success("進度與日誌已儲存！")
else:
    st.info("目前沒有任務，趕快對 AI 許願吧！")