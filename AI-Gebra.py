import os
import base64
import openai
import pandas as pd
from dotenv import load_dotenv
import streamlit as st
from PIL import Image
from io import BytesIO
from streamlit_drawable_canvas import st_canvas
from fpdf import FPDF
from datetime import datetime
from langchain.prompts import ChatPromptTemplate
from langchain.schema import HumanMessage
import random
from datetime import datetime
import re

st.set_page_config(page_title="📐 AI-Gebra", layout="wide") 
# --- Настройка бюджета ---
BUDGET_FILE = "budget.csv"
if os.path.exists(BUDGET_FILE):
    df_budget = pd.read_csv(BUDGET_FILE)
else:
    df_budget = pd.DataFrame(columns=["username", "spent_usd"])

# Хранилище пользователей в session_state (эмуляция базы) 
if "users" not in st.session_state:
    st.session_state.users = {
        "aidana": {"password": "1234", "role": "student"},
        "bekzat": {"password": "abcd", "role": "student"},
        "teacher": {"password": "admin", "role": "teacher"}
    }

if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
    st.session_state.username = ""
# счетчик   
if "budget_usd" not in st.session_state:
    st.session_state.budget_usd = 10.00  # 💵 Стартовый бюджет
if "spent_usd" not in st.session_state:
    st.session_state.spent_usd = 0.00

COST_GENERATE = 0.00275
COST_CHECK = 0.02000
# --- Регистрация ---
def registration_form():
    with st.form("register_form"):
        st.subheader("📝 Регистрация")
        new_username = st.text_input("Новый логин")
        new_password = st.text_input("Новый пароль", type="password")
        role = st.selectbox("Роль", ["student", "teacher"])
        submitted = st.form_submit_button("Зарегистрироваться")
        if submitted:
            if new_username in st.session_state.users:
                st.error("Пользователь уже существует")
            else:
                st.session_state.users[new_username] = {"password": new_password, "role": role}
                st.success(f"Пользователь '{new_username}' зарегистрирован как {role}")

# --- Смена пароля ---
def password_change_form():
    with st.form("change_pass_form"):
        st.subheader("🔐 Сменить пароль")
        current = st.text_input("Текущий пароль", type="password")
        new_pass = st.text_input("Новый пароль", type="password")
        submit = st.form_submit_button("Сменить")
        if submit:
            user = st.session_state.username
            if st.session_state.users[user]["password"] == current:
                st.session_state.users[user]["password"] = new_pass
                st.success("Пароль успешно изменён")
            else:
                st.error("Неверный текущий пароль")

# --- АВТОРИЗАЦИЯ ---
if not st.session_state.authenticated:
    st.title("🔐 Вход или регистрация")
    auth_tab, reg_tab = st.tabs(["Войти", "Регистрация"])

    with auth_tab:
        username = st.text_input("Логин")
        password = st.text_input("Пароль", type="password")
        role = st.selectbox("Роль при входе", ["student", "teacher"])
        if st.button("Войти"):
            users = st.session_state.users
            if username in users and users[username]["password"] == password:
                if users[username]["role"] != role:
                    st.error(f"Роль не совпадает: вы зарегистрированы как {users[username]['role']}")
                else:
                    st.session_state.authenticated = True
                    st.session_state.username = username
                    st.session_state.role = role
                    st.stop()
            else:
                st.error("Неверный логин или пароль")

    with reg_tab:
        registration_form()

else:
    username = st.session_state.username
    role = st.session_state.role
    st.sidebar.success(f"Добро пожаловать, {username} ({role})!")
    if st.sidebar.button("Выйти"):
        st.session_state.authenticated = False
        st.session_state.username = ""
        st.stop()

     # --- Бюджет на пользователя ---
    user_row = df_budget[df_budget["username"] == username]
    if not user_row.empty:
        st.session_state.spent_usd = float(user_row.iloc[0]["spent_usd"])
    else:
        st.session_state.spent_usd = 0.0
        df_budget = pd.concat([
            df_budget,
            pd.DataFrame([{"username": username, "spent_usd": 0.0}])
        ], ignore_index=True)
        df_budget.to_csv(BUDGET_FILE, index=False)


    if st.sidebar.button("Сменить пароль"):
        st.session_state.show_password_form = not st.session_state.get("show_password_form", False)

    remaining = st.session_state.budget_usd - st.session_state.spent_usd
    st.sidebar.markdown(f"💰 *Остаток бюджета:* **${remaining:.2f}**")
    if remaining < 1.00:
        st.sidebar.error("⚠️ Осталось меньше $1 — будь осторожна с использованием!")


    if st.session_state.get("show_password_form"):
        password_change_form()
# подключение к апи
    load_dotenv()
    openai.api_key = os.getenv("OPENAI_API_KEY")

    st.markdown("## 🎲 Выбери тему и получи задание")

    unit = st.selectbox("Раздел", [
        "Интегралы", "Производные", "Прямоугольная система координат на плоскости"
])

    topic = st.selectbox("Тема", {
        "Интегралы": [
            "Интегрирование по частям",
            "Интегрирование по подстановке",
            "Прямое интегрирование"
        ],
        "Производные": [
            "Производная произведения",
            "Цепное правило",
            "Предел через определение"
        ],
        "Прямоугольная система координат на плоскости": [
            "Расстояние между точками",
            "Нахождение координат середины",
            "Деление отрезка в заданном соотношении"
        ]
    }[unit])
#кнопка генерации задачи по выбранным разделам 
    
    difficulty = st.selectbox("Сложность задания", ["Лёгкая", "Средняя", "Сложная"])

    if st.button("Получить задание"):
    # 🎲 Случайная подсказка для разнообразия
        phrases = [
        "Сделай задачу немного сложнее.",
        "Сделай задачу практической.",
        "Измени числовые параметры.",
        "Придумай интересную формулу.",
        "Измени тип функции или выражения."
        ]
        random_phrase = random.choice(phrases)

        system_message = {
            "role": "system",
            "content": "Ты — учитель математики. Отвечай на русском. Формулы — только в LaTeX, внутри двойных $$...$$."
        }
    # 🎯 Финальный prompt
        prompt = f"""
    Сгенерируй одну задачу по математике на тему: {topic}, в разделе: {unit}.
    Сложность: {difficulty}
    {random_phrase}
    Формат ответа:

**Условие задачи:**  
Формулируй задачу на русском языке. Формулы — строго в LaTeX внутри двойных $$...$$.
Количество баллов за решение, не генерируй задачи, которые были в предыдущих 20 случаях повторно или как минимум меняй значения параметров.

**Критерии успеха:**  
Напиши общие действия, которые должен выполнить ученик для решения этой задачи.  
Не пиши само решение и не включай формулы. Только краткие описания шагов.  
Каждый шаг — с новой строки. 
Используй формат:
1. <действие> — N балл  
2. <действие> — N балла  
...
**Итого: X баллов**

**Марк-схема:**  
Опиши шаги решения задачи и укажи, сколько баллов даётся за каждый.  
Используй стиль Cambridge (IGCSE / AS / A-Level). В конце добавь строку с общей суммой баллов.  
Формулы — только в LaTeX: $$...$$.
**Итого: X баллов**

Правила по сложности:
- Лёгкая задача: 1–3 балла  
- Средняя задача: 1–5 баллов  
- Сложная задача: 1–8 баллов  

🔴 Важно:
- Не используй скобки ( ... ) в формулах — только $$...$$
- Следуй структуре:
  1. <действие> — N баллов  
  2. <...> — N баллов  
  ...
  **Итого: X баллов**

Пример:
**Условие задачи:**  
Найди интеграл функции $$x e^x$$

**Критерии успеха:**  
1. Определить метод решения  1 балл
2. Разложить задачу на этапы  2 балла
3. Последовательно выполнить вычисления 1 балл  
4. Привести ответ к удобной форме 1 балл

**Марк-схема:**  
1. Применить метод интегрирования по частям — 2 балла  
2. Найти первообразную $$\\int e^x dx$$ — 1 балл  
3. Подставить и упростить выражение — 2 балла  
**Итого: 5 баллов**

❗ Не повторяй формулировку задачи, структуру или числовые значения. Сделай задачу уникальной.
❗Никогда не используй обычные скобки ( ... ) для формул. Все математические выражения пиши строго в формате LaTeX внутри двойных знаков $$...$$. 
Например:
Неправильно: (\\sin(x) + C)  
Правильно: $$\\sin(x) + C$$
    """
        user_message = {"role": "user", "content": prompt}

        with st.spinner("🎲 Генерация уникального задания..."):
            try:
                response = openai.chat.completions.create(
                    model="gpt-4o",
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=300,
                    temperature=0.7,  # 📈 Больше разнообразия
                    seed=random.randint(1, 10**6)  # 🔀 Новый результат каждый раз
                )
                generated_problem = response.choices[0].message.content.strip()
                st.session_state.generated_problem = generated_problem

                parts = generated_problem.split("**Критерии успеха:**")
                problem_text = parts[0].strip()
                rest = parts[1].split("**Марк-схема:**")
                success_criteria = rest[0].strip()
                mark_scheme = rest[1].strip() if len(rest) > 1 else ""

                #st.code(mark_scheme, language="markdown")

                #match = re.search(r"\*\*Итого:\s*(\d+)\s*", mark_scheme)
                #total_points = int(match.group(1)) if match else 0
            
                st.session_state.generated_problem = problem_text
                st.session_state.success_criteria = success_criteria
                st.session_state.mark_scheme_text = mark_scheme
                #st.session_state.total_points = total_points
                #st.info(f"🔎 Распознано {total_points} баллов")
                # 💰 Только если успешно сгенерировано
                st.session_state.spent_usd += COST_GENERATE
                df_budget.loc[df_budget["username"] == username, "spent_usd"] = st.session_state.spent_usd
                df_budget.to_csv(BUDGET_FILE, index=False)
            except Exception as e:
                st.error(f"Ошибка: {str(e)}")

    if "generated_problem" in st.session_state:
        st.markdown("### 🧠 Читайте внимательно:")
        st.markdown(st.session_state.generated_problem, unsafe_allow_html=True)
    if "success_criteria" in st.session_state:
        st.markdown("### ✅ Критерии успеха:")
        st.markdown(st.session_state.success_criteria)
    #if "total_points" in st.session_state:
        #st.markdown(f"### 🎯 Итого: **{st.session_state.total_points} баллов**")
    
     #if "mark_scheme_text" in st.session_state:
       #  st.markdown("### 📋 Марк-схема:")
         #st.markdown(st.session_state.mark_scheme_text)

    # Важно! сохранить в переменной, как будто selected_problem:
        selected_problem = st.session_state.generated_problem

    
    if role == "student":
        st.markdown("### ✏️ Запиши свое решение:")

        # Настройки рисования
        col1, col2, = st.columns(2)
        col3, = st.columns(1)
        with col1:
            drawing_mode = st.selectbox("🛠 Режим рисования", [
                "freedraw", "line", "rect", "circle", "transform"
            ], key="drawing_mode_select")

        with col2:
            stroke_color = st.color_picker("🎨 Цвет пера", "#000000", key="stroke_color_picker")

        with col3:
            stroke_width = st.slider("✏️ Толщина", 1, 20, 4, key="stroke_width_slider")

        eraser_mode = st.checkbox("🧼 Ластик", key="eraser_checkbox")
        actual_color = "#FFFFFF" if eraser_mode else stroke_color

        canvas_key = f"canvas_{drawing_mode}"   

        canvas_result = st_canvas(
            fill_color="rgba(255, 255, 255, 1)",
            stroke_width=stroke_width,
            stroke_color=actual_color,
            background_color="#FFFFFF",
            height=1000,
            width=2000,
            drawing_mode=drawing_mode,
            key=canvas_key,
            update_streamlit=True
        )

        def encode_image_from_canvas(canvas_img):
            buffer = BytesIO()
            canvas_img.save(buffer, format="JPEG")
            return base64.b64encode(buffer.getvalue()).decode("utf-8"), buffer

        # Шаблон запроса
        prompt_template = ChatPromptTemplate.from_messages([
            ("system", "Ты — учитель математики. Отвечай на русском. Формулы — только в LaTeX с двойными $$...$$"),
            ("human", "{question}")
        ])

        def analyze_with_gpt_vision(problem_text,mark_scheme_text, base64_img):
            full_prompt = f"""
Твоя задача — оценить решение ученика по задаче: **{problem_text}**
📋 Используй следующую марк-схему для оценивания (стиль Cambridge): {mark_scheme_text}

🖼️ Ученик решил задачу на изображении (см. ниже).

🔍 Что нужно сделать:
1. Сам реши задачу.
2. Проанализируй изображение и определи, что ученик написал.
3. Сравни действия ученика с шагами в марк-схеме.
4. За каждый правильный шаг начисли соответствующее количество баллов.
5. Укажи обоснование, если какой-то шаг отсутствует или выполнен неверно.
6. В конце обязательно выведи строку вида:  
**Оценка: X из Y баллов**

📘 Формат ответа:

**Решение задачи:**  
<твоя формула и объяснение>

**Анализ решения ученика:**  
<что написал ученик>

**Сравнение с марк-схемой:**  
<по шагам — какие действия выполнены правильно/неправильно и сколько баллов начислено>
<если решение альтернативное и верное, засчитывать даже если не соответствует марк схеме>
**Итог:**  
Правильно ли решено? Поддержи ученика.

**Тип ошибки:**  
Один из вариантов: правильно / логическая / вычислительная / неправильное прочтение

**Оценка: X из Y баллов**

❗Никогда не используй обычные скобки ( ... ) для формул. Все математические выражения пиши строго в формате LaTeX внутри двойных знаков $$...$$. 
Например:
Неправильно: (\\sin(x) + C)  
Правильно: $$\\sin(x) + C$$
"""
            try:
                chain = prompt_template
                messages = chain.format_messages(question=full_prompt)

                vision_payload = {
                    "model": "gpt-4o",
                    "messages": [
                        {
                            "role": "user",
                            "content": [
                                {"type": "text", "text": messages[1].content},  # только human часть
                                {
                                    "type": "image_url",
                                    "image_url": {
                                        "url": f"data:image/jpeg;base64,{base64_img}",
                                        "detail": "high"
                                    }
                                }
                            ]
                        }
                    ],
                    "max_tokens": 1000
                }

                response = openai.chat.completions.create(**vision_payload)
                return response.choices[0].message.content.strip()
            except Exception as e:
                return f"❌ Ошибка (LangChain + Vision): {str(e)[:300]}"


        def save_to_pdf(problem_text, gpt_response, image_bytes, filename="решение.pdf"):
            pdf = FPDF()
            pdf.add_page()
            pdf.set_font("Arial", size=12)
            pdf.multi_cell(0, 10, f"Задача:\n{problem_text}", align="L")

            with open("temp_image.jpg", "wb") as f:
                f.write(image_bytes.getvalue())
            pdf.image("temp_image.jpg", x=10, y=pdf.get_y(), w=180)
            pdf.ln(85)
            pdf.multi_cell(0, 10, f"Ответ GPT:\n{gpt_response}", align="L")
            pdf.output(filename)
            return filename

        if canvas_result.image_data is not None:
            image = Image.fromarray(canvas_result.image_data.astype("uint8"), mode="RGBA").convert("RGB")
            if st.button("🚀 Отправить на проверку"):
                base64_img, buffer = encode_image_from_canvas(image)
                with st.spinner("GPT анализирует..."):
                    result = analyze_with_gpt_vision(selected_problem, st.session_state.mark_scheme_text, base64_img)
                # 💰 Только если успешно сгенерировано
                    st.session_state.spent_usd += COST_GENERATE
                    df_budget.loc[df_budget["username"] == username, "spent_usd"] = st.session_state.spent_usd
                    df_budget.to_csv(BUDGET_FILE, index=False)
                if "Тип ошибки:" in result:
                    error_line = [line for line in result.split("\n") if "Тип ошибки:" in line]
                    error_type = error_line[0].split("Тип ошибки:")[-1].strip() if error_line else "неизвестно"
                else:
                    error_type = "неизвестно"
                log = {
                    "username": username,
                    "unit": unit,
                    "task": selected_problem,
                    "gpt_response": result,
                    "error_type": error_type,
                    "difficulty": difficulty,  # ← добавили сюда!
                    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                }
                df_entry = pd.DataFrame([log])
                history_path = "history.csv"

                if os.path.exists(history_path):
                    df_history = pd.read_csv(history_path)
                    df_history = pd.concat([df_history, df_entry], ignore_index=True)
                else:
                    df_history = df_entry

                df_history.to_csv(history_path, index=False)
                st.markdown("### 🔍 Ответ от GPT:")
                for block in result.split("\n\n"):
                    if "$$" in block:
                        st.markdown(block, unsafe_allow_html=True) # чтобы нормально формулы показывал
                    else:
                        st.markdown(f"> {block}") 


                log = {
                    "username": username,
                    "task": selected_problem,
                    "gpt_response": result,
                    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                }
                df_log = pd.DataFrame([log])
                if os.path.exists("history.csv"):
                    df_log.to_csv("history.csv", mode="a", header=False, index=False)
                else:
                    df_log.to_csv("history.csv", index=False)

                if st.button("💾 Сохранить в PDF"):
                    filename = save_to_pdf(selected_problem, result, buffer)
                    with open(filename, "rb") as pdf_file:
                        st.download_button(
                            label="📥 Скачать PDF",
                            data=pdf_file,
                            file_name=filename,
                            mime="application/pdf"
                        )

    if role == "teacher":
        st.markdown("## 👨‍🏫 Профиль учителя")

        if os.path.exists("history.csv"):
            df_history = pd.read_csv("history.csv")

        # Показываем только уникальных учеников
            all_students = df_history["username"].unique().tolist()
            selected_student = st.selectbox("👤 Выберите ученика", all_students)

        # Фильтруем по выбранному ученику
            student_df = df_history[df_history["username"] == selected_student]
            student_df["timestamp"] = pd.to_datetime(student_df["timestamp"])

            st.markdown(f"### 🧠 История решений: {selected_student}")
            st.dataframe(student_df)

            st.markdown("### 📈 Прогресс по дням")
            daily_counts = student_df["timestamp"].dt.date.value_counts().sort_index()
            st.line_chart(daily_counts)

            if "error_type" in student_df.columns:
                st.markdown("### 🧠 Типы ошибок")
                st.bar_chart(student_df["error_type"].value_counts())
        else:
            st.info("Пока нет данных. Ученики ещё не решали задачи.")

        def export_student_history_to_pdf(student_name, df):
            pdf = FPDF()
            pdf.add_page()
            pdf.set_font("Arial", size=12)
            pdf.cell(200, 10, txt=f"Отчёт по ученику: {student_name}", ln=True)

            for i, row in df.iterrows():
                pdf.ln(10)
                pdf.multi_cell(0, 10, f"📘 Задача: {row['task']}")
                pdf.multi_cell(0, 10, f"🧠 Ответ GPT:\n{row['gpt_response']}")
                if 'error_type' in row:
                    pdf.cell(0, 10, f"Тип ошибки: {row['error_type']}", ln=True)
                pdf.cell(0, 10, f"🕓 Время: {row['timestamp']}", ln=True)

            filename = f"{student_name}_report.pdf"
            pdf.output(filename)
            return filename

# 📤 Кнопка экспорта
        if st.button("📄 Скачать PDF-отчёт по ученику"):
            pdf_path = export_student_history_to_pdf(selected_student, student_df)
            with open(pdf_path, "rb") as f:
                st.download_button(
                    label="📥 Скачать PDF",
                    data=f,
                    file_name=pdf_path,
                    mime="application/pdf"
                )


