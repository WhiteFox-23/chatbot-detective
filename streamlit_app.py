import streamlit as st

from engine import (
    init_state,
    start_scenario,
    submit_answer,
    get_question,
    get_progress,
    get_hypothesis,
    get_teacher_summary,
    get_materials,
    continue_without_answer,
    is_finished,
    reset_state,
)

st.set_page_config(
    page_title="AI-детектив",
    page_icon="🕵️",
    layout="wide"
)

# =========================
# INIT
# =========================
init_state(st)
start_scenario(st)

summary = get_teacher_summary(st)
progress = get_progress(st)
current_question = get_question(st)
current_materials = get_materials(st)
current_node_id = st.session_state.current_node
answer_key = f"answer_input_{current_node_id}"


# =========================
# HELPERS
# =========================
def format_score(value: int) -> str:
    if value >= 8:
        return "высокий"
    if value >= 4:
        return "средний"
    if value >= 1:
        return "базовый"
    return "не проявлен"


def render_materials(materials: dict):
    if not materials:
        return

    st.markdown('<div class="panel">', unsafe_allow_html=True)
    st.markdown('<div class="panel-title">Материалы</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="panel-subtitle">То, что Ваня показывает на текущем этапе расследования.</div>',
        unsafe_allow_html=True
    )

    for key, value in materials.items():
        if key == "messages_and_files":
            st.markdown("#### Сообщения и файлы")
            for item in value:
                with st.expander(item.get("title", "Материал")):
                    st.write(item["content"])

        elif key == "vanya_action_ideas":
            st.markdown("#### Список идей Вани")
            for item in value:
                st.markdown(f"- {item}")

        elif key == "rule_description":
            st.markdown("#### Описание правила работы бота")
            for item in value:
                st.markdown(f"- {item}")

        elif key == "journal_05_05":
            st.markdown("#### Журнал за 05.05")
            st.table(value)

        elif key == "journal_06_05":
            st.markdown("#### Журнал за 06.05")
            st.table(value)

        elif key == "repo_access":
            st.markdown("#### Доступ к репозиторию")
            for item in value:
                st.markdown(f"- {item}")

        elif key == "events_example":
            st.markdown("#### Пример событий")
            st.code(value, language="python")

        elif key == "code_snippet":
            st.markdown("#### Фрагмент кода")
            st.code(value, language="python")

        elif key == "suspects_table":
            st.markdown("#### Таблица подозреваемых")
            st.table(value)

        else:
            st.markdown(f"#### {key}")
            st.write(value)

    st.markdown("</div>", unsafe_allow_html=True)


# =========================
# STYLES
# =========================
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

html, body, [class*="css"] {
    font-family: 'Inter', sans-serif;
}

html, body, .stApp {
    background: linear-gradient(180deg, #f4f7fb 0%, #eef3f9 100%);
    color: #162033;
}

header[data-testid="stHeader"] {
    height: 0rem;
    background: transparent;
}

[data-testid="stToolbar"] {
    display: none;
}

[data-testid="stDecoration"] {
    display: none;
}

.block-container {
    max-width: 1450px;
    padding-top: 0.2rem;
    padding-bottom: 1.5rem;
}

.top-banner {
    background: linear-gradient(135deg, #0f172a 0%, #15345f 100%);
    border-radius: 24px;
    padding: 24px 28px;
    color: white;
    box-shadow: 0 18px 40px rgba(15, 23, 42, 0.14);
    margin-bottom: 18px;
}

.top-kicker {
    font-size: 0.78rem;
    opacity: 0.82;
    margin-bottom: 8px;
    text-transform: uppercase;
    letter-spacing: 0.12em;
    font-weight: 700;
}

.top-title {
    font-size: 2rem;
    font-weight: 800;
    margin-bottom: 8px;
}

.top-subtitle {
    font-size: 0.98rem;
    opacity: 0.92;
    max-width: 880px;
    line-height: 1.55;
}

.metric-card {
    background: rgba(255,255,255,0.97);
    border: 1px solid #dbe3ee;
    border-radius: 18px;
    padding: 14px 16px;
    box-shadow: 0 8px 20px rgba(15, 23, 42, 0.04);
    margin-bottom: 12px;
}

.metric-label {
    font-size: 0.82rem;
    color: #6b7b93;
    margin-bottom: 6px;
    font-weight: 600;
}

.metric-value {
    font-size: 1.14rem;
    font-weight: 800;
    color: #0f172a;
}

.panel {
    background: rgba(255,255,255,0.97);
    border: 1px solid #dbe3ee;
    border-radius: 22px;
    padding: 18px;
    box-shadow: 0 12px 28px rgba(15, 23, 42, 0.05);
    margin-bottom: 14px;
}

.panel-title {
    font-size: 1.03rem;
    font-weight: 800;
    margin-bottom: 4px;
    color: #0f172a;
}

.panel-subtitle {
    font-size: 0.92rem;
    color: #64748b;
    margin-bottom: 12px;
}

.tag {
    display: inline-block;
    background: #e8edff;
    color: #3730a3;
    border-radius: 999px;
    padding: 6px 10px;
    font-size: 0.8rem;
    font-weight: 700;
    margin: 0 6px 6px 0;
}

.chat-shell {
    background: #ffffff;
    border: 1.5px solid #cfd9e8;
    border-radius: 24px;
    overflow: hidden;
    box-shadow:
        0 2px 8px rgba(15, 23, 42, 0.05),
        0 18px 42px rgba(15, 23, 42, 0.10);
    outline: 3px solid rgba(59, 130, 246, 0.08);
}

.chat-header {
    padding: 18px 20px 14px 20px;
    border-bottom: 1px solid #d8e2f0;
    background: linear-gradient(180deg, #ffffff 0%, #f4f8ff 100%);
}

.chat-stage {
    display: inline-block;
    margin-top: 8px;
    padding: 5px 10px;
    border-radius: 999px;
    background: #e0e7ff;
    color: #3730a3;
    font-size: 0.76rem;
    font-weight: 700;
}

.chat-scroll {
    padding: 16px 18px 12px 18px;
    background: #f8fbff;
    min-height: 100%;
}

.chat-footer {
    padding: 16px 20px 18px 20px;
    border-top: 1px solid #d8e2f0;
    background: #ffffff;
}

.msg-wrap {
    margin-bottom: 8px;
    display: flex;
    width: 100%;
}

.msg-left {
    justify-content: flex-start;
}

.msg-right {
    justify-content: flex-end;
}

.msg-vanya {
    background: #eef4ff;
    color: #18253d;
    border: 1px solid #dbe7ff;
    border-radius: 18px 18px 18px 8px;
    padding: 12px 14px;
    max-width: 78%;
    line-height: 1.5;
}

.msg-you {
    background: linear-gradient(135deg, #1d4ed8 0%, #1e40af 100%);
    color: white;
    border-radius: 18px 18px 8px 18px;
    padding: 12px 14px;
    max-width: 78%;
    line-height: 1.5;
}

.msg-name {
    font-size: 0.76rem;
    font-weight: 800;
    margin-bottom: 5px;
    opacity: 0.85;
    text-transform: uppercase;
    letter-spacing: 0.06em;
}

.answer-box {
    background: rgba(255,255,255,0.97);
    border: 1px solid #dbe3ee;
    border-radius: 18px;
    padding: 14px 15px;
    box-shadow: 0 8px 20px rgba(15, 23, 42, 0.04);
    margin-bottom: 12px;
}

.answer-label {
    font-size: 0.8rem;
    color: #64748b;
    font-weight: 700;
    margin-bottom: 6px;
    text-transform: uppercase;
    letter-spacing: 0.04em;
}

.answer-value {
    font-size: 0.98rem;
    color: #0f172a;
    font-weight: 600;
    line-height: 1.45;
}
</style>
""", unsafe_allow_html=True)

# =========================
# TOP BANNER
# =========================
st.markdown("""
<div class="top-banner">
    <div class="top-kicker">Учебный сценарий · расследование</div>
    <div class="top-title">AI-детектив: дело о странных сообщениях</div>
    <div class="top-subtitle">
        Ты помогаешь Ване разобраться, почему студенческий бот начал присылать странные сообщения,
        как это связано с данными, логами и кодом, и кому в итоге можно доверять.
    </div>
</div>
""", unsafe_allow_html=True)

left_col, center_col, right_col = st.columns([1.05, 2.3, 1.2], gap="large")

# =========================
# LEFT
# =========================
with left_col:
    st.markdown(
        f'<div class="metric-card"><div class="metric-label">Прогресс</div><div class="metric-value">{progress}%</div></div>',
        unsafe_allow_html=True
    )
    st.markdown(
        f'<div class="metric-card"><div class="metric-label">Кейс</div><div class="metric-value">{st.session_state.case_title}</div></div>',
        unsafe_allow_html=True
    )
    st.markdown(
        f'<div class="metric-card"><div class="metric-label">Уровень</div><div class="metric-value">{st.session_state.difficulty}</div></div>',
        unsafe_allow_html=True
    )

    st.markdown('<div class="panel">', unsafe_allow_html=True)
    st.markdown('<div class="panel-title">Навыки</div>', unsafe_allow_html=True)
    st.markdown('<div class="panel-subtitle">Промежуточная оценка прохождения.</div>', unsafe_allow_html=True)
    st.markdown(f'<span class="tag">Безопасность: {format_score(summary["security"])}</span>', unsafe_allow_html=True)
    st.markdown(f'<span class="tag">Алгоритмы: {format_score(summary["rules"])}</span>', unsafe_allow_html=True)
    st.markdown(f'<span class="tag">Код: {format_score(summary["code"])}</span>', unsafe_allow_html=True)
    st.markdown(f'<span class="tag">Гипотеза: {format_score(summary["hypothesis"])}</span>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('<div class="panel">', unsafe_allow_html=True)
    st.markdown('<div class="panel-title">Факты и улики</div>', unsafe_allow_html=True)
    st.markdown('<div class="panel-subtitle">Что уже удалось зафиксировать.</div>', unsafe_allow_html=True)
    if st.session_state.evidence:
        for item in st.session_state.evidence:
            st.markdown(f"- {item}")
    else:
        st.write("Пока улик ещё нет.")
    st.markdown('</div>', unsafe_allow_html=True)

    if st.button("Начать заново", use_container_width=True):
        reset_state(st)
        st.rerun()

# =========================
# CENTER
# =========================
with center_col:
    st.markdown('<div class="chat-shell">', unsafe_allow_html=True)
    st.markdown("""
    <div class="chat-header">
        <div class="panel-title">Диалог с Ваней</div>
        <div class="panel-subtitle">Смотри реплики, изучай материалы и отвечай как участник расследования.</div>
        <div class="chat-stage">Текущее состояние расследования</div>
    </div>
    """, unsafe_allow_html=True)

    chat_history_box = st.container(height=520)
    with chat_history_box:
        st.markdown('<div class="chat-scroll">', unsafe_allow_html=True)

        for speaker, msg in st.session_state.history:
            if speaker == "Ваня":
                st.markdown(
                    f"""
                    <div class="msg-wrap msg-left">
                        <div class="msg-vanya">
                            <div class="msg-name">Ваня</div>
                            <div>{msg}</div>
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True
                )
            else:
                st.markdown(
                    f"""
                    <div class="msg-wrap msg-right">
                        <div class="msg-you">
                            <div class="msg-name">Ты</div>
                            <div>{msg}</div>
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True
                )

        st.markdown('</div>', unsafe_allow_html=True)

    if current_materials:
        render_materials(current_materials)

    st.markdown('<div class="chat-footer">', unsafe_allow_html=True)

    if not is_finished(st):
        if current_question:
            st.markdown("### Твой ответ")
            st.info(current_question)

            user_answer = st.text_area(
                "Напиши ответ",
                key=answer_key,
                height=160,
                placeholder="Напиши здесь свой ответ..."
            )

            btn_col1, btn_col2 = st.columns([1, 1.2])

            with btn_col1:
                if st.button("Отправить ответ", type="primary", use_container_width=True):
                    answer = user_answer.strip()
                    if answer:
                        submit_answer(st, answer)
                        st.rerun()

            with btn_col2:
                if st.button("Сбросить текст", use_container_width=True):
                    st.session_state[answer_key] = ""
                    st.rerun()

        else:
            st.success("Этот этап не требует ответа.")
            if st.button("Продолжить", type="primary", use_container_width=True):
                continue_without_answer(st)
                st.rerun()

    else:
        st.success("Расследование завершено.")
        if st.button("Пройти кейс заново", type="primary", use_container_width=True):
            reset_state(st)
            st.rerun()

    st.markdown('</div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

# =========================
# RIGHT
# =========================
with right_col:
    st.markdown('<div class="answer-box">', unsafe_allow_html=True)
    st.markdown('<div class="answer-label">Текущая гипотеза</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="answer-value">{get_hypothesis(st)}</div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('<div class="answer-box">', unsafe_allow_html=True)
    st.markdown('<div class="answer-label">Подсказочные узлы</div>', unsafe_allow_html=True)
    if summary["hint_nodes_used"]:
        for hint_id in summary["hint_nodes_used"]:
            st.markdown(f"- {hint_id}")
    else:
        st.write("Подсказки пока не использовались.")
    st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('<div class="answer-box">', unsafe_allow_html=True)
    st.markdown('<div class="answer-label">Исследовательский режим</div>', unsafe_allow_html=True)
    st.markdown(
        f'<div class="answer-value">Посещено узлов: {len(summary["visited_nodes"])}<br>Использовано подсказок: {len(summary["hint_nodes_used"])}</div>',
        unsafe_allow_html=True
    )
    st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('<div class="panel">', unsafe_allow_html=True)
    st.markdown('<div class="panel-title">Teacher summary</div>', unsafe_allow_html=True)
    st.markdown('<div class="panel-subtitle">Краткая сводка для анализа прохождения.</div>', unsafe_allow_html=True)

    st.markdown(f"- Безопасность: {summary['security']}")
    st.markdown(f"- Алгоритмы и данные: {summary['rules']}")
    st.markdown(f"- Код: {summary['code']}")
    st.markdown(f"- Гипотеза: {summary['hypothesis']}")

    st.markdown("#### Узлы с подсказками")
    if summary["hint_nodes_used"]:
        for node_id in summary["hint_nodes_used"]:
            st.markdown(f"- {node_id}")
    else:
        st.write("Нет.")

    st.markdown("#### Посещённые узлы")
    if summary["visited_nodes"]:
        for node_id in summary["visited_nodes"]:
            st.markdown(f"- {node_id}")
    else:
        st.write("Пока пусто.")

    st.markdown('</div>', unsafe_allow_html=True)