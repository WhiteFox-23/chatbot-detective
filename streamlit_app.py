import streamlit as st
import pandas as pd

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
    get_ai_teacher_report,
    set_ai_teacher_report,
    generate_ai_teacher_report,
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

summary, report_input = get_teacher_summary(st)
progress = get_progress(st)
ai_report = get_ai_teacher_report(st)
current_question = get_question(st)
current_node_id = st.session_state.current_node
answer_key = f"answer_input_{current_node_id}"

current_materials = get_materials(st)

if "persisted_materials" not in st.session_state:
    st.session_state.persisted_materials = {}

if "last_nonempty_materials" not in st.session_state:
    st.session_state.last_nonempty_materials = {}

if current_materials:
    st.session_state.persisted_materials[current_node_id] = current_materials
    st.session_state.last_nonempty_materials = current_materials

materials_to_show = current_materials or st.session_state.last_nonempty_materials

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

def pretty_label(name: str) -> str:
    mapping = {
        "interpretation": "Интерпретация",
        "analysis": "Анализ",
        "inference": "Выводы",
        "evaluation": "Оценка",
        "explanation": "Объяснение",
        "digital_safety": "Цифровая безопасность",
        "algorithms": "Алгоритмы",
        "code": "Код",
    }
    return mapping.get(name, name.replace("_", " ").capitalize())


def level_badge(level: str) -> str:
    colors = {
        "не проявлен": "#9aa6b2",
        "базовый": "#8b5cf6",
        "средний": "#2563eb",
        "высокий": "#16a34a",
    }
    color = colors.get((level or "").lower(), "#475569")
    return f"""
    <span style="
        display:inline-block;
        padding:4px 10px;
        border-radius:999px;
        background:{color}15;
        color:{color};
        font-size:0.78rem;
        font-weight:700;
        border:1px solid {color}33;
    ">
        {level}
    </span>
    """


def render_ai_report(report: dict):
    if not report:
        st.write("AI-анализ пока не сформирован. Заверши кейс и нажми кнопку выше.")
        return

    ct = report.get("critical_thinking", {}) or {}
    subj = report.get("subject_knowledge", {}) or {}
    final_h = report.get("final_hypothesis_quality", {}) or {}

    st.markdown("### Общая картина")

    summary_items = [
        {
            "title": "Критическое мышление",
            "level": ct.get("overall_level", "—"),
            "meta": f"Балл: {ct.get('score', 0)}",
        },
        {
            "title": "Предметные знания",
            "level": subj.get("overall_level", "—"),
            "meta": f"Балл: {subj.get('score', 0)}",
        },
        {
            "title": "Итоговая гипотеза",
            "level": final_h.get("level", "—"),
            "meta": final_h.get("comment", "Комментарий пока отсутствует."),
        },
    ]

    for item in summary_items:
        with st.container(border=True):
            col1, col2 = st.columns([2.3, 1])

            with col1:
                st.markdown(f"**{item.get('title', 'Без названия')}**")

            with col2:
                st.markdown(level_badge(item.get("level", "—")), unsafe_allow_html=True)

            st.write(item.get("meta", ""))

    ct_criteria = ct.get("criteria", {}) or {}
    if ct_criteria:
        st.markdown("### Критическое мышление")
        for name, crit in ct_criteria.items():
            level = crit.get("level", "—")
            score = crit.get("score", 0)
            comment = crit.get("comment", "")
            st.markdown(
                f"""
                <div class="ai-detail-card">
                    <div class="ai-detail-top">
                        <div class="ai-detail-title">{pretty_label(name)}</div>
                        <div>{level_badge(level)}</div>
                    </div>
                    <div class="ai-detail-score">Балл: {score}</div>
                    <div class="ai-detail-comment">{comment}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

    subj_areas = subj.get("areas", {}) or {}
    if subj_areas:
        st.markdown("### Предметные знания")
        for name, area in subj_areas.items():
            level = area.get("level", "—")
            score = area.get("score", 0)
            comment = area.get("comment", "")
            st.markdown(
                f"""
                <div class="ai-detail-card">
                    <div class="ai-detail-top">
                        <div class="ai-detail-title">{pretty_label(name)}</div>
                        <div>{level_badge(level)}</div>
                    </div>
                    <div class="ai-detail-score">Балл: {score}</div>
                    <div class="ai-detail-comment">{comment}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

    evidence_quotes = []
    evidence_quotes.extend(ct.get("evidence_quotes", []) or [])
    evidence_quotes.extend(subj.get("evidence_quotes", []) or [])

    if evidence_quotes:
        unique_quotes = []
        for q in evidence_quotes:
            if q not in unique_quotes:
                unique_quotes.append(q)

        st.markdown("### Опорные фрагменты")
        for quote in unique_quotes[:6]:
            st.markdown(
                f"""
                <div class="ai-quote-card">
                    “{quote}”
                </div>
                """,
                unsafe_allow_html=True,
            )

    teacher_rec = report.get("teacher_recommendation", "")
    if teacher_rec:
        st.markdown("### Рекомендация учителю")
        st.markdown(
            f"""
            <div class="ai-recommendation-card">
                {teacher_rec}
            </div>
            """,
            unsafe_allow_html=True,
        )

def render_df_table(data, title: str):
    if not data:
        return

    st.markdown(f"#### {title}")

    if isinstance(data, dict):
        columns = data.get("columns", [])
        rows = data.get("rows", [])
        df = pd.DataFrame(rows, columns=columns)
    else:
        df = pd.DataFrame(data)

    st.table(df)


def render_html_wrap_table(data, title: str):
    if not data:
        return

    st.markdown(f"#### {title}")

    if isinstance(data, dict):
        columns = data.get("columns", [])
        rows = data.get("rows", [])
        df = pd.DataFrame(rows, columns=columns)
    else:
        df = pd.DataFrame(data)

    html = df.to_html(index=False, escape=False)

    st.markdown(
        f"""
        <div class="wrap-table">
            {html}
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_materials(materials: dict):
    if not materials:
        return

    st.markdown("## Материалы расследования")
    st.caption("Все артефакты, которые доступны на текущем этапе.")

    for key, value in materials.items():

        # --- новый универсальный формат материалов ---
        if isinstance(value, dict) and "type" in value:
            item_type = value.get("type")
            title = value.get("title", key)

            if item_type == "bullets":
                st.markdown(f"#### {title}")
                for item in value.get("items", []):
                    st.markdown(f"- {item}")

            elif item_type == "table":
                if key == "suspects_table":
                    render_html_wrap_table(value, title)
                else:
                    render_df_table(value, title)

            elif item_type == "text":
                st.markdown(f"#### {title}")
                st.write(value.get("content", ""))

            elif item_type == "code":
                st.markdown(f"#### {title}")
                st.code(
                    value.get("content", ""),
                    language=value.get("language", "python"),
                )

            else:
                st.markdown(f"#### {title}")
                st.write(value)

        # --- старый / спецформат материалов ---
        elif key == "messages_and_files":
            st.markdown("#### Сообщения и файлы")
            for item in value:
                with st.expander(item.get("title", "Материал"), expanded=False):
                    st.write(item["content"])

        elif key == "vanya_action_ideas":
            st.markdown("#### Идеи Вани")
            for item in value:
                st.markdown(f"- {item}")

        elif key == "rule_description":
            st.markdown("#### Правило работы бота")
            if isinstance(value, dict):
                for item in value.get("items", []):
                    st.markdown(f"- {item}")
            else:
                for item in value:
                    st.markdown(f"- {item}")

        elif key in ["journal_05_05", "journal_0505"]:
            render_df_table(value, "Журнал за 05.05")

        elif key in ["journal_06_05", "journal_0605"]:
            render_df_table(value, "Журнал за 06.05")

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
            # fallback, если вдруг придёт в старом формате
            render_html_wrap_table(value, "Таблица подозреваемых")

        else:
            st.markdown(f"#### {key}")
            st.write(value)


# =========================
# STYLES
# =========================
st.markdown(
    """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

html, body, [class*="css"] {
    font-family: 'Inter', sans-serif;
}

html, body, .stApp, [data-testid="stAppViewContainer"] {
    background: linear-gradient(180deg, #f4f7fb 0%, #edf2f8 100%);
    color: #152033;
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

[data-testid="stStatusWidget"] {
    display: none;
}

.block-container {
    max-width: 1520px;
    padding-top: 0.35rem;
    padding-bottom: 1.4rem;
}

.top-banner {
    background: linear-gradient(135deg, #162338 0%, #21456e 100%);
    border-radius: 28px;
    padding: 24px 30px;
    color: white;
    box-shadow: 0 18px 45px rgba(15, 23, 42, 0.16);
    margin-bottom: 20px;
}

.top-kicker {
    font-size: 0.76rem;
    opacity: 0.8;
    margin-bottom: 7px;
    text-transform: uppercase;
    letter-spacing: 0.14em;
    font-weight: 700;
}

.top-title {
    font-size: 2.1rem;
    font-weight: 800;
    margin-bottom: 8px;
    line-height: 1.15;
}

.top-subtitle {
    font-size: 0.98rem;
    opacity: 0.94;
    max-width: 920px;
    line-height: 1.55;
}

.chat-shell {
    background: #ffffff;
    border: 1px solid #ccd7e7;
    border-radius: 26px;
    overflow: hidden;
    box-shadow:
        0 2px 8px rgba(15, 23, 42, 0.05),
        0 18px 42px rgba(15, 23, 42, 0.10);
    outline: 4px solid rgba(59, 130, 246, 0.05);
}

.chat-header {
    padding: 16px 18px 12px 18px;
    border-bottom: 1px solid #d9e3f0;
    background: linear-gradient(180deg, #ffffff 0%, #f2f7ff 100%);
}

.chat-title {
    font-size: 1.08rem;
    font-weight: 800;
    color: #102136;
    margin-bottom: 4px;
}

.chat-subtitle {
    font-size: 0.92rem;
    color: #607089;
    line-height: 1.45;
}

.chat-stage {
    display: inline-block;
    margin-top: 10px;
    padding: 6px 11px;
    border-radius: 999px;
    background: #e6edff;
    color: #3741a8;
    font-size: 0.76rem;
    font-weight: 700;
}

.chat-scroll {
    padding: 18px 20px 12px 20px;
    background:
        radial-gradient(circle at top right, rgba(59,130,246,0.05), transparent 18%),
        #f8fbff;
    min-height: 100%;
}

.chat-footer {
    padding: 18px 22px 20px 22px;
    border-top: 1px solid #d9e3f0;
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
    background: #edf4ff;
    color: #16253d;
    border: 1px solid #d9e7ff;
    border-radius: 18px 18px 18px 8px;
    padding: 10px 13px;
    max-width: 68%;
    line-height: 1.42;
    font-size: 0.95rem;
    box-shadow: 0 3px 8px rgba(15, 23, 42, 0.03);
}

.msg-you {
    background: linear-gradient(135deg, #2457d6 0%, #1f46b5 100%);
    color: white;
    border-radius: 18px 18px 8px 18px;
    padding: 10px 13px;
    max-width: 68%;
    line-height: 1.42;
    font-size: 0.95rem;
    box-shadow: 0 6px 14px rgba(37, 87, 214, 0.18);
}

.msg-name {
    font-size: 0.71rem;
    font-weight: 800;
    margin-bottom: 5px;
    opacity: 0.82;
    text-transform: uppercase;
    letter-spacing: 0.06em;
}

.stTextArea textarea {
    border-radius: 16px !important;
    border: 1px solid #ccd7e7 !important;
    background: #ffffff !important;
    color: #132134 !important;
    box-shadow: none !important;
}

.stTextArea label {
    color: #4a5b73 !important;
    font-weight: 600;
}

button[kind="primary"] {
    border-radius: 14px !important;
    background: linear-gradient(135deg, #2457d6 0%, #1f46b5 100%) !important;
    border: none !important;
    color: white !important;
}

button[kind="secondary"] {
    border-radius: 14px !important;
}

[data-testid="stDataFrame"] {
    border: 1px solid #dbe4f0;
    border-radius: 14px;
    overflow: hidden;
    background: #ffffff;
}

/* обычные streamlit-блоки в боковых колонках */
.side-section {
    background: rgba(255,255,255,0.78);
    border: 1px solid #dce5f1;
    border-radius: 18px;
    padding: 12px 14px;
    margin-bottom: 12px;
    box-shadow: 0 8px 18px rgba(15, 23, 42, 0.035);
}

.side-section h4 {
    margin: 0 0 6px 0;
    color: #122136;
}

.muted {
    color: #6b7a8f;
    font-size: 0.92rem;
}

/* таблицы с переносом строк (подозреваемые и др.) */
.wrap-table table {
    width: 100%;
    border-collapse: collapse;
    table-layout: fixed;
    background: #ffffff;
    border: 1px solid #dbe4f0;
    border-radius: 14px;
    overflow: hidden;
}

.wrap-table th,
.wrap-table td {
    border: 1px solid #dbe4f0;
    padding: 10px 12px;
    vertical-align: top;
    text-align: left;
    white-space: normal !important;
    word-break: break-word;
    overflow-wrap: anywhere;
    font-size: 0.93rem;
    line-height: 1.4;
}

.wrap-table th {
    background: #f3f7fd;
    font-weight: 700;
    color: #132134;
}

.ai-summary-card,
.ai-detail-card,
.ai-quote-card,
.ai-recommendation-card {
    background: rgba(255,255,255,0.88);
    border: 1px solid #dce5f1;
    border-radius: 18px;
    padding: 14px 15px;
    margin-bottom: 12px;
    box-shadow: 0 8px 18px rgba(15, 23, 42, 0.035);
}

.ai-summary-row,
.ai-detail-top {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    gap: 10px;
}

.ai-summary-label,
.ai-detail-title {
    font-weight: 800;
    color: #122136;
    line-height: 1.3;
}

.ai-summary-meta,
.ai-detail-score {
    margin-top: 4px;
    font-size: 0.9rem;
    color: #5d6d83;
}

.ai-detail-comment {
    margin-top: 8px;
    color: #223046;
    line-height: 1.5;
    font-size: 0.95rem;
}

.ai-quote-card {
    border-left: 4px solid #93c5fd;
    color: #223046;
    line-height: 1.5;
    font-size: 0.94rem;
    background: #f8fbff;
}

.ai-recommendation-card {
    background: linear-gradient(180deg, #f8fbff 0%, #eef5ff 100%);
    color: #1d2d44;
    line-height: 1.55;
}
</style>
""",
    unsafe_allow_html=True,
)

# =========================
# TOP BANNER
# =========================
st.markdown(
    """
<div class="top-banner">
    <div class="top-kicker">Учебный сценарий · расследование</div>
    <div class="top-title">AI-детектив: дело о странных сообщениях</div>
    <div class="top-subtitle">
        Ты помогаешь Ване разобраться, почему студенческий бот начал присылать странные сообщения,
        как это связано с данными, логами и кодом, и кому в итоге можно доверять.
    </div>
</div>
""",
    unsafe_allow_html=True,
)

left_col, center_col, right_col = st.columns([0.9, 2.7, 1.0], gap="large")

# =========================
# LEFT
# =========================
with left_col:
    st.markdown("#### Прогресс")
    st.progress(max(progress, 1) / 100)
    st.write(f"**{progress}%**")

    st.markdown("#### Кейс")
    st.write(st.session_state.case_title)

    st.markdown("#### Уровень")
    st.write(st.session_state.difficulty)

    st.markdown("#### Навыки")
    st.caption("Как продвигается разбор кейса.")
    st.write(f"Безопасность: {format_score(summary['security'])}")
    st.write(f"Алгоритмы: {format_score(summary['rules'])}")
    st.write(f"Код: {format_score(summary['code'])}")
    st.write(f"Гипотеза: {format_score(summary['hypothesis'])}")

    st.markdown("#### Улики")
    if st.session_state.evidence:
        for item in st.session_state.evidence:
            st.markdown(f"- {item}")
    else:
        st.write("Пока улик ещё нет.")

    if st.button("Начать заново", use_container_width=True):
        reset_state(st)
        st.rerun()

# =========================
# CENTER
# =========================
with center_col:
    st.markdown('<div class="chat-shell">', unsafe_allow_html=True)
    st.markdown(
        """
    <div class="chat-header">
        <div class="chat-title">Диалог с Ваней</div>
        <div class="chat-subtitle">Следи за сообщениями, смотри материалы и отвечай как участник расследования.</div>
        <div class="chat-stage">Центральная линия расследования</div>
    </div>
    """,
        unsafe_allow_html=True,
    )

    chat_history_box = st.container(height=500)
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
                    unsafe_allow_html=True,
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
                    unsafe_allow_html=True,
                )

        st.markdown("</div>", unsafe_allow_html=True)

    if materials_to_show:
        render_materials(materials_to_show)

    if not is_finished(st):
        if current_question:
            st.markdown("### Твой ответ")
            st.info(current_question)

            user_answer = st.text_area(
                "Напиши ответ",
                key=answer_key,
                height=140,
                placeholder="Напиши здесь свой ответ...",
            )

            btn_col1, btn_col2 = st.columns([1, 1])

            with btn_col1:
                if st.button(
                    "Отправить ответ",
                    type="primary",
                    use_container_width=True,
                ):
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
            if st.button(
                "Продолжить",
                type="primary",
                use_container_width=True,
            ):
                continue_without_answer(st)
                st.rerun()
    else:
        st.success("Расследование завершено.")

        # Кнопка для формирования AI-отчёта
    if st.button(
        "Сформировать AI-анализ прохождения",
        type="primary",
        use_container_width=True,
    ):
        try:
            report = generate_ai_teacher_report(report_input)
            set_ai_teacher_report(st, report)
            st.success("AI-анализ сформирован.")
            st.rerun()
        except Exception as e:
            st.error(f"Не удалось получить AI-анализ: {e}")

        if st.button(
            "Пройти кейс заново",
            use_container_width=True,
        ):
            reset_state(st)
            st.rerun()

    st.markdown("</div>", unsafe_allow_html=True)

# =========================
# RIGHT
# =========================
with right_col:
    st.markdown("#### Гипотеза")
    st.write(get_hypothesis(st))

    st.markdown("#### Подсказки")
    if summary["hint_nodes_used"]:
        for hint_id in summary["hint_nodes_used"]:
            st.markdown(f"- {hint_id}")
    else:
        st.write("Пока не использовались.")

    st.markdown("#### Сводка")
    st.caption("Краткая картина прохождения.")
    st.write(f"Безопасность: {summary['security']}")
    st.write(f"Алгоритмы и данные: {summary['rules']}")
    st.write(f"Код: {summary['code']}")
    st.write(f"Гипотеза: {summary['hypothesis']}")
    st.write(f"Посещено узлов: {len(summary['visited_nodes'])}")

    st.markdown("#### AI-анализ")
    st.caption("Автоматический отчёт по ответам ученика и ходу расследования.")
    render_ai_report(ai_report)