from scenario_data import SCENARIO
import json
import requests
import streamlit as st
import csv
import uuid
from datetime import datetime
from pathlib import Path


BASE_SCORES = {
    "security": 0,
    "rules": 0,
    "code": 0,
    "hypothesis": 0,
}


def init_state(st):
    defaults = {
        "current_node": "intro_intro",
        "session_id": str(uuid.uuid4()),
        "history": [],
        "answers": {},
        "evidence": [],
        "visited_nodes": [],
        "hint_nodes_used": [],
        "started": False,
        "case_title": "Дело о странных сообщениях",
        "difficulty": "Базовый уровень",
        "scores": BASE_SCORES.copy(),
        "current_materials": {},
        "materials_by_node": {},
        "answer_evaluations": [],
        "run_summary_saved": False,
        "ai_teacher_report": None,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def add_message(st, speaker, text):
    st.session_state.history.append((speaker, text))


def _store_node_materials(st, node_id):
    node = SCENARIO[node_id]
    materials = node.get("materials", {}) or {}
    st.session_state.current_materials = materials
    st.session_state.materials_by_node[node_id] = materials


def push_node_messages(st, node_id):
    node = SCENARIO[node_id]
    speaker = node["speaker"]
    for msg in node.get("messages", []):
        add_message(st, speaker, msg)


def _register_visited_node(st, node_id):
    if node_id not in st.session_state.visited_nodes:
        st.session_state.visited_nodes.append(node_id)

    node = SCENARIO[node_id]
    if node.get("is_hint") and node_id not in st.session_state.hint_nodes_used:
        st.session_state.hint_nodes_used.append(node_id)


def start_scenario(st):
    if not st.session_state.started:
        node_id = st.session_state.current_node
        _store_node_materials(st, node_id)
        push_node_messages(st, node_id)
        _register_visited_node(st, node_id)
        st.session_state.started = True
        log_event(st, "start")


def get_current_node(st):
    return SCENARIO[st.session_state.current_node]


def get_question(st):
    return get_current_node(st).get("question")


def get_materials(st):
    node_id = st.session_state.current_node
    node_materials = get_current_node(st).get("materials", {})
    if node_materials:
        return node_materials
    return st.session_state.materials_by_node.get(node_id, st.session_state.current_materials)


def is_finished(st):
    node = get_current_node(st)
    return node.get("node_type") in ["ending"]


def move_to_node(st, node_id):
    st.session_state.current_node = node_id
    _store_node_materials(st, node_id)
    push_node_messages(st, node_id)
    _register_visited_node(st, node_id)


def normalize_text(text: str) -> str:
    return (text or "").lower().replace("ё", "е").strip()


def is_empty_answer(answer: str):
    return len(normalize_text(answer)) == 0


def has_any(text: str, keywords):
    return any(k in text for k in keywords)


def count_any(text: str, keywords):
    return sum(1 for k in keywords if k in text)


def count_distinct_groups(text: str, groups):
    score = 0
    for group in groups:
        if has_any(text, group):
            score += 1
    return score


# --- КЛАССИФИКАТОРЫ ПО УЗЛАМ --- #


def classify_intro(answer: str):
    text = normalize_text(answer)
    if is_empty_answer(answer):
        return "bad"
    if has_any(text, ["да", "ок", "хорошо", "ага", "конечно", "помогу", "давай", "погнали", "ну да"]):
        return "good"
    return "neutral"


def classify_t1_suspicious(answer: str):
    text = normalize_text(answer)
    if is_empty_answer(answer):
        return "bad"

    suspicious_ids = count_any(text, ["4", "5", "6", "7", "8"])
    phishing = count_distinct_groups(text, [
        ["фиш", "поддельн", "левый", "домен", "ссылк"],
        ["логин", "парол", "данн", "выман", "мошенн"],
    ])
    attachments = count_distinct_groups(text, [
        [".exe", "exe", "запуск", "вложен"],
        ["xlsm", "макрос"],
    ])
    privacy = count_distinct_groups(text, [
        ["личн", "переписк", "скрин", "приват", "утеч"],
        ["контакт", "список", "номеров", "связи"],
    ])

    signals = phishing + attachments + privacy

    if suspicious_ids >= 2 and signals >= 2:
        return "good"
    if suspicious_ids >= 1 and signals >= 1:
        return "neutral"
    return "bad"


def classify_t1_reflect(answer: str):
    text = normalize_text(answer)
    if is_empty_answer(answer):
        return "bad"

    weirdness = count_distinct_groups(text, [
        ["не сход", "странн", "нелогич"],
        ["угроз", "шантаж", "слив", "приват"],
        ["бот", "сообщен", "переписк", "отношен"],
    ])

    if weirdness >= 2:
        return "good"
    if weirdness >= 1:
        return "neutral"
    return "bad"


def classify_t1_actions(answer: str):
    text = normalize_text(answer)
    if is_empty_answer(answer):
        return "bad"

    urgent = count_distinct_groups(text, [
        ["сменить парол", "смена парол"],
        ["2fa", "двухфактор"],
        ["срочно", "прямо сейчас"],
        ["выйти из всех", "других устройств"],
    ])
    helpful = count_distinct_groups(text, [
        ["проверить", "проверка", "авторизац", "привязан"],
        ["сообщить", "предупред", "написать", "чат", "групп"],
        ["не открыв", "не скачив", "не запуск"],
        ["не переход", "не переходить"],
    ])
    harmful = count_distinct_groups(text, [
        ["удалить бота", "сразу удалить"],
        ["обвинить", "публично обвинить"],
        ["выключить уведомления", "ничего не читать"],
    ])

    if urgent >= 1 and helpful >= 2:
        return "good"
    if urgent >= 1 or helpful >= 1:
        return "neutral"
    if harmful >= 1 and urgent == 0 and helpful == 0:
        return "bad"
    return "neutral"


def classify_t1_hypothesis(answer: str):
    text = normalize_text(answer)
    if is_empty_answer(answer):
        return "bad"

    suspects = count_any(text, ["варя", "дима", "кирилл", "илья", "ася", "бот"])
    motives = count_distinct_groups(text, [
        ["выгод", "мотив", "захотел", "обидел", "ревност", "симпат"],
        ["контроль", "следить", "подстав", "пошутить", "тролл"],
    ])
    evidence = count_distinct_groups(text, [
        ["сообщен", "угроз", "слив", "таблиц", "журнал"],
        ["бот", "доступ", "код"],
    ])

    if suspects >= 1 and (motives + evidence) >= 2:
        return "good"
    if suspects >= 1 and (motives + evidence) >= 1:
        return "neutral"
    return "bad"


def classify_t2_rule_apply_journal1(answer: str):
    text = normalize_text(answer)
    if is_empty_answer(answer):
        return "bad"

    students = count_any(text, [
        "антон", "ася", "варя", "дима", "кирилл", "лена",
        "паша", "оля", "сереж", "серёжа", "маша", "илья",
    ])

    logic = count_distinct_groups(text, [
        ["обыч", "regular", "обычное напоминание"],
        ["личн", "personal", "личное напоминание"],
        ["строг", "strict", "строгое предупреждение"],
        ["ничего", "нет сообщ", "no_message"],
        ["пропущ", "подряд"],
        ["просроч", "за месяц"],
        ["по правил", "согласно правилу"],
    ])

    if students >= 2 and logic >= 3:
        return "good"
    if students >= 1 and logic >= 1:
        return "neutral"
    return "bad"


def classify_t2_journal2(answer: str):
    text = normalize_text(answer)
    if is_empty_answer(answer):
        return "bad"

    normal_case = has_any(text, ["логичн", "нормальн", "по правилу", "все сходится"])
    anomalies = count_distinct_groups(text, [
        ["не сход", "несоответ", "не совпад", "странн"],
        ["должен был", "по идее", "по правилу должен"],
        ["особ", "special_message"],
        ["кирилл"],
        ["маша"],
        ["ваня"],
    ])
    people = count_any(text, [
        "антон", "ася", "варя", "дима", "кирилл", "лена",
        "паша", "оля", "сереж", "серёжа", "маша", "илья", "ваня",
    ])

    if anomalies >= 3 and people >= 2:
        return "good"
    if anomalies >= 1 and people >= 1:
        return "neutral"
    if normal_case and anomalies == 0:
        return "bad"
    return "bad"


def classify_t2_assessment(answer: str):
    text = normalize_text(answer)
    if is_empty_answer(answer):
        return "bad"

    risks = count_distinct_groups(text, [
        ["цифр", "только числа", "только цифр"],
        ["ситуац", "контекст"],
        ["ошиб", "ошибоч", "ложн", "несправед"],
        ["тревож", "зря", "перегиб", "слишком жестко"],
        ["не замет", "пропуст"],
    ])

    improvements = count_distinct_groups(text, [
        ["контекст", "история"],
        ["повтор", "динамик", "несколько дн"],
        ["вручную", "человеком", "ручн"],
        ["мягк", "по человечески", "по-человечески"],
        ["кого трогать", "кого не трогать", "кого тревожить"],
    ])

    if risks >= 2 and improvements >= 2:
        return "good"
    if risks >= 1 or improvements >= 1:
        return "neutral"
    return "bad"


def classify_t2_update_hypothesis(answer: str):
    text = normalize_text(answer)
    if is_empty_answer(answer):
        return "bad"

    suspects = count_any(text, ["варя", "дима", "кирилл", "илья", "ася", "бот"])
    evidence = count_distinct_groups(text, [
        ["журнал", "таблиц", "05.05", "06.05"],
        ["правил", "услов", "тип сообщ"],
        ["особое сообщен", "особые сообщения"],
    ])

    if suspects >= 1 and evidence >= 2:
        return "good"
    if suspects >= 1 and evidence >= 1:
        return "neutral"
    return "bad"


def classify_t3_code_explanation(answer: str):
    text = normalize_text(answer)
    if is_empty_answer(answer):
        return "bad"

    func = count_distinct_groups(text, [
        ["classify_user"],
        ["функц", "функция"],
        ["возвращ", "return"],
        ["тип сообщ", "какие сообщени"],
    ])

    flag = count_distinct_groups(text, [
        ["special_flag", "спешал", "особ", "флаг"],
        ["раньше", "сначала", "первым"],
        ["влияет", "отдельно", "особая обработка"],
    ])

    outputs = count_any(text, [
        "special_message", "personal_warning",
        "strict_warning", "no_message", "regular_reminder",
        "особое сообщение", "личное", "строгое",
    ])

    users = count_any(text, ["anton", "asya", "masha", "vanya", "антон", "ася", "маша", "ваня"])

    if func >= 1 and flag >= 1 and (outputs >= 2 or users >= 2):
        return "good"
    if func >= 1 or flag >= 1 or outputs >= 1:
        return "neutral"
    return "bad"


def classify_t3_code_change(answer: str):
    text = normalize_text(answer)
    if is_empty_answer(answer):
        return "bad"

    review = count_distinct_groups(text, [
        ["вручную", "ручн", "человек", "проверять человеком"],
        ["проверять", "проверка"],
        ["подозрительн", "особые случаи"],
    ])
    no_special = count_distinct_groups(text, [
        ["special_flag", "флаг"],
        ["раньше", "сначала", "до остального"],
        ["не должен", "убрать", "перенести", "не обходил"],
    ])
    same_logic = count_distinct_groups(text, [
        ["как в правиле"],
        ["остальная логика"],
        ["иначе", "else", "дальше", "после этого"],
    ])

    if review >= 1 and no_special >= 1 and same_logic >= 1:
        return "good"
    if review >= 1 or no_special >= 1:
        return "neutral"
    return "bad"


def classify_t3_logs_function(answer: str):
    text = normalize_text(answer)
    if is_empty_answer(answer):
        return "bad"

    mentions_fn = count_distinct_groups(text, [
        ["def", "функц", "function"],
        ["visits"],
        ["n", "последн"],
    ])
    mentions_fields = count_distinct_groups(text, [
        ["user", "пользовател"],
        ["time", "время", "дата"],
        ["file", "файл"],
    ])

    if mentions_fn >= 1 and mentions_fields >= 1:
        return "good"
    if mentions_fn >= 1 or mentions_fields >= 1:
        return "neutral"
    return "bad"


def classify_t3_logs_results(answer: str):
    text = normalize_text(answer)
    if is_empty_answer(answer):
        return "bad"

    review = count_distinct_groups(text, [
        ["kiril", "кирил", "kiril"],
        ["special_message", "особое сообщение"],
        ["rule_ok", "не по правилу", "false", "ложь"],
    ])
    manual = count_distinct_groups(text, [
        ["проверить вручную", "вручную", "проверка"],
        ["подозрительн", "странн"],
        ["добавил", "список"],
    ])

    if review >= 2 and manual >= 1:
        return "good"
    if review >= 1 or manual >= 1:
        return "neutral"
    return "bad"


def classify_t3_final_hypothesis(answer: str):
    text = normalize_text(answer)
    if is_empty_answer(answer):
        return "bad"

    suspects = count_any(text, ["варя", "дима", "кирилл", "илья", "ася", "бот"])
    evidence = count_distinct_groups(text, [
        ["сообщен", "угроз", "слив"],
        ["журнал", "таблиц", "лог"],
        ["код", "флаг", "special_flag", "logic.py"],
        ["доступ", "репозитор"],
    ])

    if suspects >= 1 and evidence >= 2:
        return "good"
    if suspects >= 1 and evidence >= 1:
        return "neutral"
    return "bad"


def classify_final(answer: str):
    text = normalize_text(answer)
    if is_empty_answer(answer):
        return "bad"

    mentions_kirill = has_any(text, ["кирилл", "kirill", "kiril"])
    any_suspect = has_any(text, ["варя", "дима", "кирилл", "илья", "ася", "бот"])

    technical_reasoning = count_distinct_groups(text, [
        ["код", "репозитор", "доступ", "репозиторий"],
        ["special_flag", "флаг", "логик", "logic.py"],
        ["лог", "журнал", "особ", "тип сообщен"],
        ["трогал код", "менял", "изменен", "заходил"],
    ])

    uncertainty = has_any(text, ["не уверен", "не знаю", "сложно сказать", "не уверена", "сомнева"])
    asks_for_more = has_any(text, ["не хватает", "мало фактов", "нужно проверить", "нужны доказательства"])

    if mentions_kirill and technical_reasoning >= 2:
        return "good_kirill"
    if any_suspect and technical_reasoning >= 2:
        return "good"
    if uncertainty or asks_for_more:
        return "neutral"
    if any_suspect or technical_reasoning >= 1:
        return "neutral"
    return "bad"


def classify_answer(answer: str, node_id: str):
    if node_id == "intro_intro":
        return classify_intro(answer)

    if node_id in ["t1_security_intro", "t1_security_hint"]:
        return classify_t1_suspicious(answer)

    if node_id == "t1_security_reflect":
        return classify_t1_reflect(answer)

    if node_id in ["t1_security_vanya_ideas", "t1_security_ideas_hint"]:
        return classify_t1_actions(answer)

    if node_id == "t1_security_hypothesis":
        return classify_t1_hypothesis(answer)

    if node_id in ["t2_rules_intro", "t2_rules_journal1_answer", "t2_rules_hint"]:
        return classify_t2_rule_apply_journal1(answer)

    if node_id in ["t2_rules_journal2", "t2_rules_journal2_hint"]:
        return classify_t2_journal2(answer)

    if node_id == "t2_rules_assessment":
        return classify_t2_assessment(answer)

    if node_id == "t2_update_hypothesis":
        return classify_t2_update_hypothesis(answer)

    if node_id in ["t3_code_intro", "t3_code_intro_hint"]:
        return classify_t3_code_explanation(answer)

    if node_id == "t3_code_change":
        return classify_t3_code_change(answer)

    if node_id == "t3_logs_intro":
        return classify_t3_logs_function(answer)

    if node_id == "t3_logs_results":
        return classify_t3_logs_results(answer)

    if node_id == "t3_logs_hypothesis_update":
        return classify_t3_final_hypothesis(answer)

    if node_id == "final_question":
        return classify_final(answer)

    return "default"


# --- СБОР УЛИК И СКОРИНГ --- #


def extract_evidence(answer: str):
    text = normalize_text(answer)
    found = []

    if has_any(text, ["фиш", "домен", ".exe", "exe", "подозр", "личн", "скрин", "парол", "xlsm", "макрос"]):
        found.append("Ученик(ца) замечает признаки цифровой угрозы: фишинг, опасные вложения или утечку приватных данных.")

    if has_any(text, ["правил", "услов", "журнал", "таблиц", "не сход", "несоответ", "особое сообщ"]):
        found.append("Ученик(ца) сопоставляет журналы работы бота с официальным правилом и видит несоответствия.")

    if has_any(text, ["special_flag", "return", "if", "код", "обход", "логик", "logic.py", "условие", "знак", "функц"]):
        found.append("Ученик(ца) анализирует код бота и замечает, как отдельные условия и специальный флаг влияют на логику сообщений.")

    if has_any(text, ["лог", "журнал заходов", "visits", "кто заходил", "какой файл", "logic.py", "ночью", "ночн", "rule_ok"]):
        found.append("Ученик(ца) использует журнал заходов и событий, чтобы увидеть, кто и когда менял файлы или вызывал подозрительные сообщения.")

    if has_any(text, ["доступ", "репозитор", "трогал код", "кирилл", "дима", "варя", "подозр", "проверить", "главный подозреваем"]):
        found.append("Ученик(ца) связывает технические факты с кругом доступа и формулирует гипотезу расследования.")

    if has_any(text, ["2fa", "сменить парол", "не откры", "не переход", "предупред", "безопасност"]):
        found.append("Ученик(ца) предлагает осмысленные рекомендации по цифровой безопасности для группы.")

    return found


def update_scores(st, node_id: str, branch_type: str):
    node = SCENARIO[node_id]
    tags = node.get("score_tags", [])

    if branch_type == "good_kirill":
        delta = 3
    elif branch_type == "good":
        delta = 2
    elif branch_type == "neutral":
        delta = 1
    else:
        delta = 0

    for tag in tags:
        st.session_state.scores[tag] = st.session_state.scores.get(tag, 0) + delta


def submit_answer(st, answer: str):
    node = get_current_node(st)
    node_id = node["id"]
    answer_key = node.get("answer_key")

    clean_answer = answer.strip()

    if answer_key:
        st.session_state.answers[answer_key] = clean_answer

    add_message(st, "Ты", clean_answer)

    new_evidence = extract_evidence(clean_answer)
    for item in new_evidence:
        if item not in st.session_state.evidence:
            st.session_state.evidence.append(item)

    branch_type = classify_answer(clean_answer, node_id)
    update_scores(st, node_id, branch_type)

    st.session_state.answer_evaluations.append({
        "node_id": node_id,
        "answer_key": answer_key,
        "question": node.get("question"),
        "student_answer": clean_answer,
        "classification": branch_type,
        "score_tags": node.get("score_tags", []),
        "is_hint": node.get("is_hint", False),
    })

    next_node = node.get("branches", {}).get(branch_type) or node.get("branches", {}).get("default")

    log_event(
    st,
    "answer_submitted",
    {
        "question": node.get("question", ""),
        "student_answer": clean_answer,
        "classification": branch_type,
        "next_node": next_node or "",
        "is_hint": node.get("is_hint", False),
    },
)

    if next_node:
        move_to_node(st, next_node)

    return branch_type


def get_progress(st):
    learning_nodes = [
        node_id for node_id, node in SCENARIO.items()
        if node.get("question") is not None
    ]
    visited_learning = [n for n in st.session_state.visited_nodes if n in learning_nodes]

    total = len(learning_nodes)
    visited = len(visited_learning)
    if total == 0:
        return 0
    return int((visited / total) * 100)


def get_hypothesis(st):
    answers = st.session_state.answers

    if "final_suspect" in answers:
        return answers["final_suspect"]
    if "t3_final_hypothesis" in answers:
        return answers["t3_final_hypothesis"]
    if "t2_updated_hypothesis" in answers:
        return answers["t2_updated_hypothesis"]
    if "t1_first_hypothesis" in answers:
        return answers["t1_first_hypothesis"]
    if "t1_suspicious_items" in answers or "t1_suspicious_items_hint" in answers:
        return "Гипотеза строится вокруг подозрительных сообщений и угроз приватности."
    return "Гипотеза ещё не сформирована."


def get_teacher_summary(st):
    """
    Возвращает:
    - summary: то, что уже сейчас нужно интерфейсу (числа, hints, visited_nodes)
    - report_input: полный пакет данных для AI-анализа
    """
    scores = st.session_state.scores
    answers = st.session_state.answers
    evidence = st.session_state.evidence
    visited_nodes = st.session_state.visited_nodes
    hint_nodes_used = st.session_state.hint_nodes_used
    answer_evaluations = st.session_state.answer_evaluations

    summary = {
        "security": scores.get("security", 0),
        "rules": scores.get("rules", 0),
        "code": scores.get("code", 0),
        "hypothesis": scores.get("hypothesis", 0),
        "hint_nodes_used": hint_nodes_used,
        "visited_nodes": visited_nodes,
    }

    report_input = {
        "case_title": st.session_state.case_title,
        "difficulty": st.session_state.difficulty,
        "scores": scores,
        "answers": answers,
        "evidence_signals": evidence,
        "visited_nodes": visited_nodes,
        "hint_nodes_used": hint_nodes_used,
        "answer_evaluations": answer_evaluations,
        "final_hypothesis_text": get_hypothesis(st),
    }

    return summary, report_input


def reset_state(st):
    for key in list(st.session_state.keys()):
        del st.session_state[key]


def continue_without_answer(st):
    node = get_current_node(st)
    next_node = node.get("branches", {}).get("default")
    if next_node:
        log_event(
            st,
            "continue_without_answer",
            {
                "question": node.get("question", ""),
                "next_node": next_node or "",
                "is_hint": node.get("is_hint", False),
            },
        )
        move_to_node(st, next_node)


DATA_DIR = Path("data")
EVENTS_FILE = DATA_DIR / "events_log.csv"
RUNS_FILE = DATA_DIR / "runs_summary.csv"


def ensure_data_dir():
    DATA_DIR.mkdir(exist_ok=True)


def append_csv_row(file_path: Path, fieldnames: list, row: dict):
    ensure_data_dir()
    file_exists = file_path.exists()

    with open(file_path, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        if not file_exists:
            writer.writeheader()
        writer.writerow(row)


def log_event(st, event_type: str, extra: dict | None = None):
    extra = extra or {}
    fieldnames = [
        "timestamp",
        "session_id",
        "case_title",
        "current_node",
        "event_type",
        "question",
        "student_answer",
        "classification",
        "next_node",
        "is_hint",
        "security_score",
        "rules_score",
        "code_score",
        "hypothesis_score",
    ]

    row = {
        "timestamp": datetime.utcnow().isoformat(timespec="seconds"),
        "session_id": st.session_state.get("session_id"),
        "case_title": st.session_state.get("case_title"),
        "current_node": st.session_state.get("current_node"),
        "event_type": event_type,
        "question": extra.get("question", ""),
        "student_answer": extra.get("student_answer", ""),
        "classification": extra.get("classification", ""),
        "next_node": extra.get("next_node", ""),
        "is_hint": extra.get("is_hint", False),
        "security_score": st.session_state.get("scores", {}).get("security", 0),
        "rules_score": st.session_state.get("scores", {}).get("rules", 0),
        "code_score": st.session_state.get("scores", {}).get("code", 0),
        "hypothesis_score": st.session_state.get("scores", {}).get("hypothesis", 0),
    }

    append_csv_row(EVENTS_FILE, fieldnames, row)

def save_run_summary(st):
    ai_report = st.session_state.get("ai_teacher_report") or {}

    ct = ai_report.get("critical_thinking", {}) or {}
    subj = ai_report.get("subject_knowledge", {}) or {}

    fieldnames = [
        "timestamp",
        "session_id",
        "case_title",
        "difficulty",
        "visited_nodes_count",
        "hint_count",
        "final_hypothesis",
        "security_score",
        "rules_score",
        "code_score",
        "hypothesis_score",
        "critical_thinking_level",
        "critical_thinking_score",
        "subject_knowledge_level",
        "subject_knowledge_score",
    ]

    row = {
        "timestamp": datetime.utcnow().isoformat(),
        "session_id": st.session_state.get("session_id"),
        "case_title": st.session_state.get("case_title"),
        "difficulty": st.session_state.get("difficulty"),
        "visited_nodes_count": len(st.session_state.get("visited_nodes", [])),
        "hint_count": len(st.session_state.get("hint_nodes_used", [])),
        "final_hypothesis": get_hypothesis(st),
        "security_score": st.session_state.get("scores", {}).get("security", 0),
        "rules_score": st.session_state.get("scores", {}).get("rules", 0),
        "code_score": st.session_state.get("scores", {}).get("code", 0),
        "hypothesis_score": st.session_state.get("scores", {}).get("hypothesis", 0),
        "critical_thinking_level": ct.get("overall_level", ""),
        "critical_thinking_score": ct.get("score", 0),
        "subject_knowledge_level": subj.get("overall_level", ""),
        "subject_knowledge_score": subj.get("score", 0),
    }

    append_csv_row(RUNS_FILE, fieldnames, row)

def set_ai_teacher_report(st, report: dict):
    """Сохраняет AI-отчёт в state (на будущее — для вывода и экспорта)."""
    st.session_state.ai_teacher_report = report


def get_ai_teacher_report(st):
    """Возвращает сохранённый AI-отчёт, если он уже есть."""
    return st.session_state.get("ai_teacher_report")

def safe_level_from_score(score: int) -> str:
    if score >= 10:
        return "высокий"
    if score >= 6:
        return "средний"
    if score >= 3:
        return "базовый"
    return "не проявлен"

def generate_ai_teacher_report(report_input: dict) -> dict:
    api_key = st.secrets.get("OPENROUTER_API_KEY")
    model_name = st.secrets.get("OPENROUTER_MODEL", "openrouter/free")

    if not api_key:
        raise ValueError("Не найден OPENROUTER_API_KEY в st.secrets")

    system_prompt = """
Ты — помощник-аналитик для учителя. 
Нужно проанализировать прохождение учебной AI-игры учеником и вернуть СТРОГО JSON.

Оцени по двум линиям:
1) critical_thinking:
- interpretation
- analysis
- inference
- evaluation
- explanation

2) subject_knowledge:
- digital_safety
- algorithms
- code

Для каждого критерия и блока:
- score: 0-3
- level: "не проявлен", "базовый", "средний", "высокий"
- comment: 1-2 предложения

Также верни:
- evidence_quotes: список коротких цитат или кратких фрагментов ответов ученика
- final_hypothesis_quality: level + comment
- teacher_recommendation: 2-4 предложения

Важно:
- опирайся только на данные из report_input
- не выдумывай факты
- если данных мало, так и скажи в comments
- верни только JSON, без markdown и без пояснений вокруг
"""

    user_prompt = f"""
Вот данные прохождения игры:

{json.dumps(report_input, ensure_ascii=False, indent=2)}

Верни JSON строго в такой структуре:
{{
  "critical_thinking": {{
    "overall_level": "не проявлен | базовый | средний | высокий",
    "score": 0,
    "criteria": {{
      "interpretation": {{"level": "", "score": 0, "comment": ""}},
      "analysis": {{"level": "", "score": 0, "comment": ""}},
      "inference": {{"level": "", "score": 0, "comment": ""}},
      "evaluation": {{"level": "", "score": 0, "comment": ""}},
      "explanation": {{"level": "", "score": 0, "comment": ""}}
    }},
    "evidence_quotes": []
  }},
  "subject_knowledge": {{
    "overall_level": "не проявлен | базовый | средний | высокий",
    "score": 0,
    "areas": {{
      "digital_safety": {{"level": "", "score": 0, "comment": ""}},
      "algorithms": {{"level": "", "score": 0, "comment": ""}},
      "code": {{"level": "", "score": 0, "comment": ""}}
    }},
    "evidence_quotes": []
  }},
  "final_hypothesis_quality": {{
    "level": "не проявлен | базовый | средний | высокий",
    "comment": ""
  }},
  "teacher_recommendation": ""
}}
"""

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://streamlit.app",
        "X-Title": "AI Detective Teacher Report",
    }

    payload = {
        "model": model_name,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.2,
    }

    response = requests.post(
        "https://openrouter.ai/api/v1/chat/completions",
        headers=headers,
        json=payload,
        timeout=60,
    )

    if response.status_code != 200:
        raise ValueError(f"OpenRouter error {response.status_code}: {response.text}")
    data = response.json()

    content = data["choices"][0]["message"]["content"].strip()

    try:
        return json.loads(content)
    except json.JSONDecodeError:
        return {
            "critical_thinking": {
                "overall_level": safe_level_from_score(
                    report_input.get("scores", {}).get("rules", 0)
                    + report_input.get("scores", {}).get("hypothesis", 0)
                ),
                "score": 0,
                "criteria": {},
                "evidence_quotes": report_input.get("evidence_signals", [])[:3],
            },
            "subject_knowledge": {
                "overall_level": safe_level_from_score(
                    report_input.get("scores", {}).get("security", 0)
                    + report_input.get("scores", {}).get("rules", 0)
                    + report_input.get("scores", {}).get("code", 0)
                ),
                "score": 0,
                "areas": {},
                "evidence_quotes": report_input.get("evidence_signals", [])[3:6],
            },
            "final_hypothesis_quality": {
                "level": safe_level_from_score(report_input.get("scores", {}).get("hypothesis", 0)),
                "comment": "Модель вернула ответ не в JSON, поэтому показан запасной вариант.",
            },
            "teacher_recommendation": "Проверьте ответы ученика вручную: API вернул нестандартный формат.",
        }