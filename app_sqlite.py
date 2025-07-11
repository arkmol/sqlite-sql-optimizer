import streamlit as st
import openai
import sqlite3
import os
import pandas as pd

# 🔐 OpenAI API Key
openai.api_key = st.secrets.get("OPENAI_API_KEY", "sk-...")

DB_PATH = "demo.db"

# 🔧 Inicjalizacja bazy z danymi
def initialize_sqlite_db():
    if not os.path.exists(DB_PATH):
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.executescript("""
        CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT);
        CREATE TABLE orders (id INTEGER PRIMARY KEY, customer_id INTEGER, total REAL);
        INSERT INTO users (name) VALUES ('Anna'), ('Jan'), ('Ewa');
        INSERT INTO orders (customer_id, total) VALUES (1, 100.0), (2, 50.0), (1, 75.0);
        """)
        conn.commit()
        conn.close()

def get_explain_plan(query):
    try:
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute(f"EXPLAIN QUERY PLAN {query}")
        plan = cur.fetchall()
        conn.close()
        return "\n".join(str(row) for row in plan)
    except Exception as e:
        return f"❌ Błąd przy EXPLAIN QUERY PLAN: {e}"

def optimize_sql_with_gpt(original_sql: str) -> dict:
    prompt = f"""
Zoptymalizuj poniższe zapytanie SQL (SQLite). Zwróć zoptymalizowaną wersję i krótki komentarz, dlaczego jest lepsza. 
Nie zmieniaj logiki działania zapytania.

SQL:
{original_sql}
"""
    response = openai.ChatCompletion.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": "Jesteś ekspertem SQL i optymalizujesz zapytania pod kątem wydajności i czytelności w SQLite."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.2
    )
    return {"optimized_text": response['choices'][0]['message']['content']}

def run_query(query):
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query(query, conn)
    conn.close()
    return df

def update_table(table, df):
    conn = sqlite3.connect(DB_PATH)
    df.to_sql(table, conn, if_exists='replace', index=False)
    conn.close()

# --- UI ---
st.set_page_config(page_title="SQLite SQL Optimizer Pro", layout="wide")
initialize_sqlite_db()

tabs = st.tabs(["🚀 Optymalizacja SQL", "🧾 Edytuj bazę danych", "🕓 Historia zapytań", "📤 Eksport wyników"])

with tabs[0]:
    st.header("🚀 Optymalizacja SQL")

    if "query_history" not in st.session_state:
        st.session_state.query_history = []

    user_query = st.text_area("🔍 Twoje zapytanie SQL", height=200)

    if st.button("Optymalizuj zapytanie"):
        if not user_query.strip():
            st.warning("Wprowadź zapytanie SQL.")
        else:
            with st.spinner("Optymalizacja..."):
                result = optimize_sql_with_gpt(user_query)
                optimized_sql = result["optimized_text"]

            # Zapamiętaj historię
            st.session_state.query_history.append(user_query)

            # Podział kodu i komentarza
            if "```sql" in optimized_sql:
                parts = optimized_sql.split("```sql")[1].split("```")
                optimized_code = parts[0].strip()
                comment = optimized_sql.replace(parts[0], "").replace("```sql", "").replace("```", "").strip()
            else:
                optimized_code = optimized_sql
                comment = ""

            st.subheader("✅ Zoptymalizowane zapytanie")
            st.code(optimized_code, language="sql")

            if comment:
                st.info(comment)

            st.subheader("📊 Porównanie EXPLAIN QUERY PLAN")

            original_explain = get_explain_plan(user_query)
            optimized_explain = get_explain_plan(optimized_code)

            col1, col2 = st.columns(2)
            with col1:
                st.markdown("**📝 Oryginalne EXPLAIN**")
                st.code(original_explain)
            with col2:
                st.markdown("**⚡ Zoptymalizowane EXPLAIN**")
                st.code(optimized_explain)

            if st.button("📤 Zapisz do pliku"):
                with open("explain_result.txt", "w") as f:
                    f.write("ORIGINAL QUERY:\n" + user_query + "\n\n")
                    f.write("EXPLAIN PLAN:\n" + original_explain + "\n\n")
                    f.write("OPTIMIZED QUERY:\n" + optimized_code + "\n\n")
                    f.write("OPTIMIZED EXPLAIN:\n" + optimized_explain + "\n")
                st.success("Zapisano jako explain_result.txt")

with tabs[1]:
    st.header("🧾 Edytuj bazę danych")

    for table in ["users", "orders"]:
        st.subheader(f"Tabela: {table}")
        df = run_query(f"SELECT * FROM {table}")
        edited_df = st.data_editor(df, use_container_width=True, num_rows="dynamic")
        if st.button(f"💾 Zapisz zmiany w {table}"):
            update_table(table, edited_df)
            st.success(f"Zapisano zmiany w tabeli {table}.")

with tabs[2]:
    st.header("🕓 Historia zapytań")
    if st.session_state.query_history:
        for q in reversed(st.session_state.query_history[-10:]):
            if st.button(f"🔁 Użyj ponownie: {q[:60]}...", key=q):
                st.session_state["restore_query"] = q
                st.rerun()
    else:
        st.info("Brak historii zapytań w tej sesji.")

if "restore_query" in st.session_state:
    st.session_state["user_query"] = st.session_state.pop("restore_query")
