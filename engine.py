from scenario_data import SCENARIO


BASE_SCORES = {
    "security": 0,
    "rules": 0,
    "code": 0,
    "hypothesis": 0,
}


def init_state(st):
    defaults = {
        "current_node": "intro_intro",
        "history": [],
        "answers": {},
        "evidence": [],
        "visited_nodes": [],
        "hint_nodes_used": [],
        "started": False,
        "case_title": "Дело о странных сообщениях",
        "difficulty": "Базовый уровень",
        "scores": BASE_SCORES.copy(),
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def add_message(st, speaker, text):
    st.session_state.history.append((speaker, text))


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
        push_node_messages(st, node_id)
        _register_visited_node(st, node_id)
        st.session_state.started = True


def get_current_node(st):
    return SCENARIO[st.session_state.current_node]


def get_question(st):
    return get_current_node(st).get("question")


def get_materials(st):
    return get_current_node(st).get("materials", {})


def is_finished(st):
    return get_current_node(st).get("question") is None and len(get_current_node(st).get("branches", {})) == 0


def move_to_node(st, node_id):
    st.session_state.current_node = node_id
    push_node_messages(st, node_id)
    _register_visited_node(st, node_id)


def normalize_text(text: str) -> str:
    return text.lower().replace("ё", "е").strip()


def has_any(text: str, keywords):
    return any(k in text for k in keywords)


def count_any(text: str, keywords):
    return sum(1 for k in keywords if k in text)


def classify_intro(answer: str):
    text = normalize_text(answer)
    if has_any(text, ["да", "ок", "давай", "конечно", "помогу", "готов", "попробуем"]):
        return "good"
    if len(text) > 0:
        return "neutral"
    return "bad"


def classify_t1_suspicious(answer: str):
    text = normalize_text(answer)

    suspicious_refs = 0
    if has_any(text, ["4", "5", "6"]):
        suspicious_refs += 2
    if has_any(text, ["7", "8"]):
        suspicious_refs += 1

    explanation_signs = count_any(
        text,
        [
            "фиш", "логин", "парол", "домен", ".exe", "exe", "влож",
            "личн", "переписк", "скрин", "подозр", "мошенн", "данн",
            "xlsm", "макрос", "лев", "поддель", "срочно", "давлен"
        ]
    )

    if suspicious_refs >= 2 and explanation_signs >= 2:
        return "good"
    if suspicious_refs >= 1 or explanation_signs >= 1:
        return "neutral"
    return "bad"


def classify_t1_actions(answer: str):
    text = normalize_text(answer)

    urgent = count_any(text, ["парол", "2fa", "двухфактор", "общ", "чат", "не откры", "проверить", "выйти"])
    wrong = count_any(text, ["удалить бота", "обвинить", "диму", "выключить уведомления", "ничего не читать"])
    category_words = count_any(text, ["срочно", "позже", "полезно", "лишнее", "мешает"])

    if urgent >= 2 and category_words >= 2:
        return "good"
    if urgent >= 1 or category_words >= 1:
        return "neutral"
    if wrong >= 1 and urgent == 0:
        return "bad"
    return "neutral"


def classify_t1_group_recs(answer: str):
    text = normalize_text(answer)

    signs = count_any(
        text,
        [
            "не откры", "не переход", "подозр", "файл", "ссылк",
            "админ", "взросл", "сообщ", "скрин", "парол", "2fa",
            "сообщить", "переслать", "проверить"
        ]
    )

    if signs >= 4:
        return "good"
    if signs >= 2:
        return "neutral"
    return "bad"


def classify_t2_rule_explanation(answer: str):
    text = normalize_text(answer)

    signs = count_any(
        text,
        [
            "обыч", "личн", "строг", "ничего", "нет сообщ",
            "2", "3", "5", "пропущ", "просроч"
        ]
    )

    if signs >= 5:
        return "good"
    if signs >= 2:
        return "neutral"
    return "bad"


def classify_t2_journal1(answer: str):
    text = normalize_text(answer)

    student_refs = count_any(
        text,
        ["антон", "ася", "варя", "дима", "кирилл", "лена", "паша", "оля", "сереж", "маша", "илья"]
    )
    logic_refs = count_any(text, ["обыч", "личн", "строг", "нет сообщ", "потому", "пропущ", "просроч", "0", "2", "3", "5"])

    if student_refs >= 2 and logic_refs >= 3:
        return "good"
    if student_refs >= 1 and logic_refs >= 1:
        return "neutral"
    return "bad"


def classify_t2_journal2(answer: str):
    text = normalize_text(answer)

    normal_case = has_any(text, ["все логично", "нормально", "по правил", "например"])
    anomalies = count_any(text, ["особ", "не сход", "несоответ", "должно быть", "кирилл", "маша", "ваня"])
    people = count_any(text, ["антон", "ася", "варя", "дима", "кирилл", "лена", "паша", "оля", "сереж", "маша", "илья", "ваня"])

    if anomalies >= 3 and people >= 2:
        return "good"
    if anomalies >= 1 and people >= 1:
        return "neutral"
    if normal_case and anomalies == 0:
        return "bad"
    return "bad"


def classify_t2_assessment(answer: str):
    text = normalize_text(answer)

    risks = count_any(text, ["цифр", "ситуац", "ошиб", "зря", "не замет", "контекст", "несправед", "перегиб"])
    better = count_any(text, ["по человечески", "история", "контекст", "повтор", "динамик", "вручную", "проверять", "не сразу"])
    who_to_touch = count_any(text, ["кого", "трогать", "не трогать", "стоит", "не стоит"])

    if risks >= 2 and better >= 2:
        return "good"
    if risks >= 1 or better >= 1 or who_to_touch >= 1:
        return "neutral"
    return "bad"


def classify_t3_code_intro(answer: str):
    text = normalize_text(answer)

    func = count_any(text, ["функц", "возвращ", "тип сообщ", "classify_user"])
    flag = count_any(text, ["special_flag", "особ", "флаг", "раньше", "сначала", "if"])
    outputs = count_any(text, ["special_message", "personal_warning", "strict_warning", "no_message", "regular_reminder"])
    users = count_any(text, ["anton", "asya", "masha", "vanya", "антон", "ася", "маша", "ваня"])

    if func >= 1 and flag >= 1 and (outputs >= 2 or users >= 2):
        return "good"
    if func >= 1 or flag >= 1 or outputs >= 1:
        return "neutral"
    return "bad"


def classify_t3_code_change(answer: str):
    text = normalize_text(answer)

    review = count_any(text, ["to_review", "review", "список", "вручную", "ручн"])
    no_special = count_any(text, ["не отправ", "не возвращ", "без special_message", "не слать"])
    same_logic = count_any(text, ["остальная логика", "как раньше", "иначе", "остальн"])

    if review >= 1 and no_special >= 1 and same_logic >= 1:
        return "good"
    if review >= 1 or no_special >= 1:
        return "neutral"
    return "bad"


def classify_t3_find_suspicious(answer: str):
    text = normalize_text(answer)

    fn = count_any(text, ["find_suspicious", "events", "список", "вход", "возвращ"])
    rule = count_any(text, ["special_message", "rule_ok", "false", "провер", "фильтр"])
    limits = count_any(text, ["огранич", "не увид", "человек", "вручную", "контекст", "ошиб"])

    if fn >= 1 and rule >= 1 and limits >= 1:
        return "good"
    if fn >= 1 or rule >= 1:
        return "neutral"
    return "bad"


def classify_final(answer: str):
    text = normalize_text(answer)

    names = {
        "kirill": ["кирилл", "kirill", "kiril"],
        "dima": ["дима", "dima"],
        "varya": ["варя", "varya"],
        "ilya": ["илья", "ilya"],
        "asya": ["ася", "asya"],
    }

    mentions_kirill = has_any(text, names["kirill"])
    technical_reasoning = count_any(
        text,
        [
            "код", "репозитор", "доступ", "special_flag", "логик",
            "лог", "журнал", "особое сообщение", "трогал код", "менял"
        ]
    )

    uncertainty = has_any(text, ["не уверен", "не знаю", "сложно сказать", "пока не уверен"])

    if mentions_kirill and technical_reasoning >= 2:
        return "good_kirill"
    if uncertainty:
        return "neutral"
    if technical_reasoning >= 1:
        return "good"
    if len(text) > 0:
        return "neutral"
    return "bad"


def classify_answer(answer: str, node_id: str):
    if node_id == "intro_intro":
        return classify_intro(answer)

    if node_id in ["t1_security_intro", "t1_security_hint"]:
        return classify_t1_suspicious(answer)

    if node_id in ["t1_security_vanya_ideas", "t1_security_ideas_hint"]:
        return classify_t1_actions(answer)

    if node_id == "t1_security_group_recs":
        return classify_t1_group_recs(answer)

    if node_id == "t2_rules_intro":
        return classify_t2_rule_explanation(answer)

    if node_id in ["t2_rules_journal1", "t2_rules_hint"]:
        return classify_t2_journal1(answer)

    if node_id in ["t2_rules_journal2", "t2_rules_journal2_hint"]:
        return classify_t2_journal2(answer)

    if node_id == "t2_rules_assessment":
        return classify_t2_assessment(answer)

    if node_id in ["t3_code_intro", "t3_code_intro_hint"]:
        return classify_t3_code_intro(answer)

    if node_id == "t3_code_change":
        return classify_t3_code_change(answer)

    if node_id == "t3_code_find_suspicious":
        return classify_t3_find_suspicious(answer)

    if node_id == "final_question":
        return classify_final(answer)

    return "default"


def extract_evidence(answer: str):
    text = normalize_text(answer)
    found = []

    if has_any(text, ["фиш", "домен", ".exe", "exe", "подозр", "личн", "скрин", "парол", "xlsm", "макрос"]):
        found.append("Ученик(ца) замечает признаки цифровой угрозы: фишинг, опасные вложения или утечку приватных данных.")

    if has_any(text, ["правил", "журнал", "лог", "не сход", "несоответ", "особое сообщение"]):
        found.append("Ученик(ца) сопоставляет журнал бота с официальным правилом и видит несоответствия.")

    if has_any(text, ["special_flag", "return", "if", "код", "обход", "логик", "to_review"]):
        found.append("Ученик(ца) замечает, что код позволяет обходить основную логику через special_flag.")

    if has_any(text, ["доступ", "репозитор", "трогал код", "кирилл", "дима", "подозреваем", "проверить"]):
        found.append("Ученик(ца) связывает технические факты с кругом доступа и формулирует гипотезу расследования.")

    if has_any(text, ["взросл", "админ", "не откры", "2fa", "сменить пароль", "рекомендац"]):
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

    next_node = node.get("branches", {}).get(branch_type) or node.get("branches", {}).get("default")

    if next_node:
        move_to_node(st, next_node)


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
    if "t3_find_suspicious" in answers:
        return "Появляется версия о злоупотреблении доступом и обходе правил через код."
    if "t3_code_change" in answers:
        return "Ученик(ца) понимает, что special_flag не должен автоматически запускать особые сообщения."
    if "t2_journal2_anomalies" in answers or "t2_journal2_anomalies_hint" in answers:
        return "Ученик(ца) видит несоответствия между правилом и журналом, особенно вокруг особых сообщений."
    if "t1_suspicious_items" in answers or "t1_suspicious_items_hint" in answers:
        return "Гипотеза строится вокруг подозрительных сообщений и угроз приватности."
    return "Гипотеза ещё не сформирована."


def get_teacher_summary(st):
    scores = st.session_state.scores
    return {
        "security": scores.get("security", 0),
        "rules": scores.get("rules", 0),
        "code": scores.get("code", 0),
        "hypothesis": scores.get("hypothesis", 0),
        "hint_nodes_used": st.session_state.hint_nodes_used,
        "visited_nodes": st.session_state.visited_nodes,
    }


def reset_state(st):
    for key in list(st.session_state.keys()):
        del st.session_state[key]


def continue_without_answer(st):
    node = get_current_node(st)
    next_node = node.get("branches", {}).get("default")
    if next_node:
        move_to_node(st, next_node)