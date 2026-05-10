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
    node = get_current_node(st)
    return node.get("node_type") in ["ending"]


def move_to_node(st, node_id):
    st.session_state.current_node = node_id
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

    # номера и упоминания
    suspicious_ids = count_any(text, ["4", "5", "6", "8"])
    # фишинг, домен, выманивание данных
    phishing = count_distinct_groups(text, [
        ["фиш", "поддельн", "левый", "домен", "ссылк", "подозр ссылк"],
        ["логин", "парол", "данн", "выман", "мошенн"],
    ])
    # вложения и опасные файлы
    attachments = count_distinct_groups(text, [
        [".exe", "exe", "запуск", "вложен"],
        ["xlsm", "макрос", "макросы"],
    ])
    # приватность
    privacy = count_distinct_groups(text, [
        ["личн", "переписк", "скрин", "приват", "утеч"],
        ["контакт", "контактов", "список номеров"],
    ])

    signals = phishing + attachments + privacy

    if suspicious_ids >= 2 and signals >= 2:
        return "good"
    if suspicious_ids >= 1 and signals >= 1:
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
        ["сообщить", "предупред", "написать", "модератор", "учител", "классн"],
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


def classify_t1_group_recs(answer: str):
    text = normalize_text(answer)
    if is_empty_answer(answer):
        return "bad"

    # базовая цифровая гигиена
    hygiene = count_distinct_groups(text, [
        ["не открыв", "не скачив", "не запуск"],
        ["не переход", "подозр", "странн ссылк"],
        ["обновить парол", "менять парол"],
        ["2fa", "двухфактор"],
    ])
    help = count_distinct_groups(text, [
        ["админ", "модератор", "учител", "классн"],
        ["позвать взросл", "позвать взрослого"],
        ["сообщить", "написать", "предупред"],
    ])
    privacy = count_distinct_groups(text, [
        ["личн", "переписк", "скрин", "приват"],
        ["контакт", "телефон", "номеров", "email"],
    ])

    signals = hygiene + help + privacy

    if signals >= 4:
        return "good"
    if signals >= 2:
        return "neutral"
    return "bad"


def classify_t2_rule_explanation(answer: str):
    text = normalize_text(answer)
    if is_empty_answer(answer):
        return "bad"

    parts = count_distinct_groups(text, [
        ["обыч", "обычное напоминание"],
        ["личн", "personal_warning", "личное напоминание"],
        ["строг", "strict", "строгое"],
        ["ничего", "no_message", "не отправ"],
        ["пропущ", "подряд"],
        ["просроч", "за месяц"],
        [">= 2", "две", "2"],
        [">= 3", "три", "3"],
        [">= 5", "пять", "5"],
    ])

    if parts >= 5:
        return "good"
    if parts >= 2:
        return "neutral"
    return "bad"


def classify_t2_journal1(answer: str):
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


def classify_t3_code_intro(answer: str):
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
        ["special_flag", "спешал флаг", "особ", "флаг"],
        ["раньше", "сначала", "первым"],
        ["обходит правило", "обход"],
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
        ["to_review", "review", "список", "списке"],
        ["вручную", "ручн", "человек", "проверять человеком"],
    ])

    no_special = count_distinct_groups(text, [
        ["не отправ", "не слать"],
        ["не возвращ", "не return"],
        ["не special_message", "без special_message", "без особого сообщения"],
    ])

    same_logic = count_distinct_groups(text, [
        ["остальная логика"],
        ["как раньше"],
        ["иначе", "else", "остальн"],
    ])

    if review >= 1 and no_special >= 1 and same_logic >= 1:
        return "good"
    if review >= 1 or no_special >= 1:
        return "neutral"
    return "bad"


def classify_t3_find_suspicious(answer: str):
    text = normalize_text(answer)
    if is_empty_answer(answer):
        return "bad"

    fn = count_distinct_groups(text, [
        ["find_suspicious"],
        ["events", "список событий", "журнал"],
        ["вход", "на вход", "параметр"],
        ["возвращ", "список имен", "список имён", "результат"],
    ])

    rule = count_distinct_groups(text, [
        ["special_message", "особое сообщение"],
        ["rule_ok", "не по правилу", "нарушает правило"],
        ["фильтр", "провер", "отбирать"],
    ])

    limits = count_distinct_groups(text, [
        ["огранич", "не увид", "не видит"],
        ["человек", "вручную", "проверять человеком"],
        ["контекст", "ошиб", "ложн"],
    ])

    if fn >= 1 and rule >= 1 and limits >= 1:
        return "good"
    if fn >= 1 or rule >= 1:
        return "neutral"
    return "bad"


def classify_final(answer: str):
    text = normalize_text(answer)
    if is_empty_answer(answer):
        return "bad"

    names = {
        "kirill": ["кирилл", "kirill", "kiril"],
    }

    mentions_kirill = has_any(text, names["kirill"])
    technical_reasoning = count_distinct_groups(text, [
        ["код", "репозитор", "доступ", "репозиторий"],
        ["special_flag", "флаг", "логик", "логика"],
        ["лог", "журнал", "особое сообщение"],
        ["трогал код", "менял", "коммит", "изменен"],
    ])

    uncertainty = has_any(text, ["не уверен", "не знаю", "сложно сказать", "не уверенна", "не уверена"])

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


# --- СБОР УЛИК И СКОРОРИНГ --- #

def extract_evidence(answer: str):
    text = normalize_text(answer)
    found = []

    if has_any(text, ["фиш", "домен", ".exe", "exe", "подозр", "личн", "скрин", "парол", "xlsm", "макрос"]):
        found.append("Ученик(ца) замечает признаки цифровой угрозы: фишинг, опасные вложения или утечку приватных данных.")

    if has_any(text, ["правил", "журнал", "лог", "не сход", "несоответ", "особое сообщение"]):
        found.append("Ученик(ца) сопоставляет журнал бота с официальным правилом и видит несоответствия.")

    if has_any(text, ["special_flag", "return", "if", "код", "обход", "логик", "to_review", "find_suspicious"]):
        found.append("Ученик(ца) замечает, что код позволяет обходить основную логику через специальный флаг и функции анализа.")

    if has_any(text, ["доступ", "репозитор", "трогал код", "кирилл", "дима", "подозреваем", "проверить"]):
        found.append("Ученик(ца) связывает технические факты с кругом доступа и формулирует гипотезу расследования.")

    if has_any(text, ["взросл", "админ", "не откры", "2fa", "сменить парол", "рекомендац"]):
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

    return branch_type  # <- добавили


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