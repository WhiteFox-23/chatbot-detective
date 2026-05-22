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
        ["бот", "сообщен", "в переписку", "отношен"],
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

    score = suspects + motives + evidence
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


def classify_t3_code_mismatch(answer: str):
    text = normalize_text(answer)
    if is_empty_answer(answer):
        return "bad"

    mentions_special = count_distinct_groups(text, [
        ["special_flag", "флаг"],
        ["обходит правило", "обход", "раньше", "перв", "до остальн"],
    ])
    mentions_sign = count_distinct_groups(text, [
        ["> 2", "больше двух", "строже", "знак"],
        ["должно быть", "должен быть", ">= 2", "больше или равно"],
    ])
    mentions_fix = count_distinct_groups(text, [
        ["исправ", "поменять", "перепис", "изменить условие"],
        ["соответств", "как в правиле"],
    ])

    if mentions_special >= 1 and mentions_sign >= 1 and mentions_fix >= 1:
        return "good"
    if mentions_special >= 1 or mentions_sign >= 1:
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


def classify_t3_logs_observation(answer: str):
    text = normalize_text(answer)
    if is_empty_answer(answer):
        return "bad"

    mentions_patterns = count_distinct_groups(text, [
        ["варя", "почти не", "не появл"],
        ["дима", "ноч", "ночью"],
        ["кирилл", "часто", "logic.py", "логик"],
    ])

    if mentions_patterns >= 2:
        return "good"
    if mentions_patterns >= 1:
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

    names = {
        "kirill": ["кирилл", "kirill", "kiril"],
    }

    mentions_kirill = has_any(text, names["kirill"])
    technical_reasoning = count_distinct_groups(text, [
        ["код", "репозитор", "доступ", "репозиторий"],
        ["special_flag", "флаг", "логик", "logic.py"],
        ["лог", "журнал", "особ", "тип сообщен"],
        ["трогал код", "менял", "изменен"],
    ])

    uncertainty = has_any(text, ["не уверен", "не знаю", "сложно сказать", "не уверена", "сомнева"])

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
        return classify_t3_code_mismatch(answer)

    if node_id == "t3_logs_intro":
        return classify_t3_logs_function(answer)

    if node_id == "t3_logs_results":
        return classify_t3_logs_observation(answer)

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

    if has_any(text, ["special_flag", "return", "if", "код", "обход", "логик", "logic.py", "условие", "знак >"]):
        found.append("Ученик(ца) замечает, что в коде есть баги и специальный флаг, через который можно обойти основную логику.")

    if has_any(text, ["лог", "журнал заходов", "visits", "кто заходил", "какой файл", "logic.py", "ночью", "ночн"]):
        found.append("Ученик(ца) использует журнал заходов в код, чтобы увидеть, кто и когда менял файлы бота.")

    if has_any(text, ["доступ", "репозитор", "трогал код", "кирилл", "дима", "варя", "подозр", "проверить", "главный подозреваем"]):
        found.append("Ученик(ца) связывает технические факты с кругом доступа и формулирует гипотезу расследования.")

    if has_any(text, ["взросл", "админ", "не откры", "2fa", "сменить парол", "рекомендац", "безопасност"]):
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