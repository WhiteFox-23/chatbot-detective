import base64
from pathlib import Path
import pandas as pd
import glob
import streamlit as st
import re

from engine import (
    init_state, start_scenario, submit_answer, get_question,
    get_progress, get_hypothesis, get_teacher_summary, get_materials,
    continue_without_answer, is_finished, reset_state, get_ai_teacher_report,
    set_ai_teacher_report, save_run_summary, generate_ai_teacher_report, 
    get_hint_materials,
)

st.set_page_config(page_title="AI-детектив", page_icon="🕵️", layout="wide")

init_state(st)
start_scenario(st)

summary, report_input = get_teacher_summary(st)
progress          = get_progress(st)
ai_report         = get_ai_teacher_report(st)
current_question  = get_question(st)
current_node_id   = st.session_state.current_node
answer_key        = f"answer_input_{current_node_id}"
current_materials = get_materials(st)

for k in ("persisted_materials", "last_nonempty_materials"):
    if k not in st.session_state:
        st.session_state[k] = {}

if current_materials:
    st.session_state.persisted_materials[current_node_id] = current_materials
    st.session_state.last_nonempty_materials = current_materials

current_diaries   = get_hint_materials(current_node_id)
materials_to_show = current_materials or st.session_state.last_nonempty_materials


# ── ASSETS ──────────────────────────────────────────────────────────
def img_b64(path_str):
    p = Path(path_str)
    return base64.b64encode(p.read_bytes()).decode() if p.exists() else None

def data_uri(path_str):
    p = Path(path_str)
    if not p.exists(): return ""
    ext  = p.suffix.lower().lstrip(".")
    mime = {"png":"image/png","webp":"image/webp","svg":"image/svg+xml"}.get(ext,"image/jpeg")
    b64  = img_b64(path_str)
    return f"data:{mime};base64,{b64}" if b64 else ""

_vc = glob.glob("assets/fb177d0a*.jpg") + glob.glob("assets/vanya*.jpg") + glob.glob("assets/*.jpg")
VANYA_PATH       = _vc[0] if _vc else "assets/vanya.jpg"
PAPER_LIGHT_PATH = "assets/08_paper_texture-3.jpg"
PAPER_DARK_PATH  = "assets/07_paper_texture-2.jpg"

vanya_uri       = data_uri(VANYA_PATH)
paper_light_uri = data_uri(PAPER_LIGHT_PATH)
paper_dark_uri  = data_uri(PAPER_DARK_PATH)

def tex(uri, overlay, fallback):
    return f'linear-gradient({overlay},{overlay}),url("{uri}")' if uri else fallback

app_bg_css     = tex(paper_light_uri, "rgba(238,231,214,0.92)", "#EEE7D6")
panel_bg_css   = tex(paper_light_uri, "rgba(250,246,238,0.97)", "#FAF6EE")
chat_dark_bg   = "#2A2621"
chat_inner_bg  = "#32302A"
chat_shell_css = tex(paper_dark_uri, "rgba(42,38,33,0.98)", chat_dark_bg)
chat_inner_css = tex(paper_dark_uri, "rgba(50,45,39,0.98)", chat_inner_bg)
vanya_bg_css   = f'url("{vanya_uri}") center/cover' if vanya_uri else "linear-gradient(145deg,#C49A6C,#8B6340)"

# ── Чат HTML в файл для st.components.v1.iframe ──────────────────────
def write_chat_html(history):
    bubbles = ""
    for speaker, msg in history:
        safe = str(msg).replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")
        if speaker == "Ваня":
            bubbles += f'<div class="w l"><div class="v">{safe}</div></div>\n'
        else:
            bubbles += f'<div class="w r"><div class="y">{safe}</div></div>\n'
    # CSS внутри HTML-файла — одинарные { } безопасны, это не f-string Python
    html = (
        '<!DOCTYPE html><html><head><meta charset="utf-8">'
        '<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500&display=swap" rel="stylesheet">'
        '<style>'
        '*{margin:0;padding:0;box-sizing:border-box;}'
        f'html,body{{height:100%;overflow:hidden;background:{chat_inner_bg};}}'
        f'.area{{height:100vh;overflow-y:auto;overflow-x:hidden;padding:12px 16px;'
        f'background:{chat_inner_css};background-size:cover;border-radius:0 0 20px 20px;}}'
        '.area::-webkit-scrollbar{width:5px;}'
        '.area::-webkit-scrollbar-thumb{background:rgba(200,180,150,.3);border-radius:10px;}'
        '.w{display:flex;width:100%;margin-bottom:8px;}'
        '.l{justify-content:flex-start;}.r{justify-content:flex-end;}'
        '.v{background:#CACBA4;color:#1c1810;border-radius:17px 17px 17px 4px;'
        'padding:9px 13px;max-width:76%;font-size:13px;line-height:1.55;font-family:Inter,sans-serif;word-break:break-word;}'
        '.y{background:#5B78B6;color:#FDFCFA;border-radius:17px 17px 4px 17px;'
        'padding:9px 13px;max-width:76%;font-size:13px;line-height:1.55;font-family:Inter,sans-serif;word-break:break-word;}'
        '</style></head><body>'
        f'<div class="area" id="c">{bubbles}</div>'
        '<script>var c=document.getElementById("c");c.scrollTop=c.scrollHeight;</script>'
        '</body></html>'
    )
    path = Path("assets/chat.html")
    path.parent.mkdir(exist_ok=True)
    path.write_text(html, encoding="utf-8")
    return str(path)

chat_html_path = write_chat_html(st.session_state.get("history", []))

# ── UI STATE ─────────────────────────────────────────────────────────
if "active_view" not in st.session_state:
    st.session_state.active_view = "chat"
if "all_materials_log" not in st.session_state:
    st.session_state.all_materials_log = []
if current_materials:
    existing = {e["node"] for e in st.session_state.all_materials_log}
    if current_node_id not in existing:
        st.session_state.all_materials_log.append({"node": current_node_id, "materials": current_materials})

active_view = st.session_state.active_view

def set_view(v):
    st.session_state.active_view = v

# ── HELPERS ───────────────────────────────────────────────────────────
def level_badge(level):
    c = {"не проявлен":"#9aa6b2","базовый":"#8b5cf6","средний":"#2563eb","высокий":"#16a34a"}.get((level or "").lower(),"#475569")
    s = (level or "—").strip()
    return (f'<span style="display:inline-block;padding:4px 10px;border-radius:999px;'
            f'background:{c}18;color:{c};font-size:.82rem;font-weight:700;'
            f'border:1px solid {c}33;white-space:nowrap;min-width:80px;text-align:center;">{s}</span>')

def pretty_label(n):
    return {"interpretation":"Интерпретация","analysis":"Анализ","inference":"Выводы",
            "evaluation":"Оценка","explanation":"Объяснение","digital_safety":"Цифровая безопасность",
            "algorithms":"Алгоритмы","code":"Код"}.get(n, n.replace("_"," ").capitalize())

def render_ai_report(report):
    if not report:
        st.write("AI-анализ пока не сформирован. Заверши кейс и нажми кнопку выше.")
        return
    ct   = report.get("critical_thinking", {})
    subj = report.get("subject_knowledge", {})
    fh   = report.get("final_hypothesis_quality", {})
    st.markdown('<div class="panel-section-title">Общая картина</div>', unsafe_allow_html=True)
    for item in [
        {"t":"Критическое мышление","l":ct.get("overall_level","—"),"m":f"Балл: {ct.get('score',0)}/15"},
        {"t":"Предметные знания","l":subj.get("overall_level","—"),"m":f"Балл: {subj.get('score',0)}/9"},
        {"t":"Итоговая гипотеза","l":fh.get("level","—"),"m":fh.get("comment","")},
    ]:
        with st.container(border=True):
            c1, c2 = st.columns([2.1, 1.2])
            with c1: st.markdown(f"**{item['t']}**")
            with c2: st.markdown(level_badge(item["l"]), unsafe_allow_html=True)
            st.write(item["m"])
    for lbl, cdict, mx in [
        ("Критическое мышление", ct.get("criteria",{}), 3),
        ("Предметные знания",    subj.get("areas",{}),   3),
    ]:
        if cdict:
            st.markdown(f'<div class="panel-section-title">{lbl}</div>', unsafe_allow_html=True)
            for name, crit in cdict.items():
                st.markdown(
                    f'<div class="ai-detail-card">'
                    f'<div class="ai-detail-top"><div class="ai-detail-title">{pretty_label(name)}</div>'
                    f'<div>{level_badge(crit.get("level","—"))}</div></div>'
                    f'<div class="ai-detail-score">Балл: {crit.get("score",0)}/{mx}</div>'
                    f'<div class="ai-detail-comment">{crit.get("comment","")}</div></div>',
                    unsafe_allow_html=True)
    quotes = list({q for q in (ct.get("evidence_quotes",[]) or []) + (subj.get("evidence_quotes",[]) or [])})
    if quotes:
        st.markdown('<div class="panel-section-title">Опорные фрагменты</div>', unsafe_allow_html=True)
        for q in quotes[:6]:
            st.markdown(f'<div class="ai-quote-card">"{q}"</div>', unsafe_allow_html=True)
    rec = report.get("teacher_recommendation","")
    if rec:
        st.markdown('<div class="panel-section-title">Рекомендация учителю</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="ai-recommendation-card">{rec}</div>', unsafe_allow_html=True)

def render_df_table(data, title):
    if not data: return
    st.markdown(f"#### {title}")
    df = pd.DataFrame(data.get("rows",[]), columns=data.get("columns",[])) if isinstance(data,dict) else pd.DataFrame(data)
    st.table(df)

def render_html_wrap_table(data, title):
    if not data: return
    st.markdown(f"#### {title}")
    df = pd.DataFrame(data.get("rows",[]), columns=data.get("columns",[])) if isinstance(data,dict) else pd.DataFrame(data)
    st.markdown(f'<div class="wrap-table">{df.to_html(index=False,escape=False)}</div>', unsafe_allow_html=True)

def render_materials(materials):
    if not materials: return
    for key, value in materials.items():
        if isinstance(value, dict) and "type" in value:
            t     = value.get("type")
            title = value.get("title", key)
            if t == "bullets":
                st.markdown(f"#### {title}")
                for item in value.get("items", []): st.markdown(f"- {item}")
            elif t == "table":
                (render_html_wrap_table if key == "suspects_table" else render_df_table)(value, title)
            elif t == "text":
                st.markdown(f"#### {title}"); st.write(value.get("content",""))
            elif t == "code":
                st.markdown(f"#### {title}"); st.code(value.get("content",""), language=value.get("language","python"))
            else:
                st.markdown(f"#### {title}"); st.write(value)
        elif key == "messages_and_files":
            st.markdown("#### Сообщения и файлы")
            for item in value:
                title = item.get("title", "Материал")
                content = item["content"]
                # Используем session_state для toggle
                toggle_key = f"msg_open_{item.get('id', title)}"
                if toggle_key not in st.session_state:
                    st.session_state[toggle_key] = False
                
                if st.button(f"{'▼' if st.session_state[toggle_key] else '▶'}  {title}", 
                            key=f"btn_{toggle_key}",
                            use_container_width=True):
                    st.session_state[toggle_key] = not st.session_state[toggle_key]
                
                if st.session_state[toggle_key]:
                    st.markdown(
                        f'<div style="background:#FAF6EE;border:1px solid #DDD0C2;'
                        f'border-radius:0 0 10px 10px;padding:10px 14px;'
                        f'font-size:.85rem;margin-top:-8px;margin-bottom:5px;">'
                        f'{content}</div>',
                        unsafe_allow_html=True)
        elif key == "vanya_action_ideas":
            st.markdown("#### Идеи Вани")
            for item in value: 
                st.markdown(item)
        elif key == "rule_description":
            st.markdown("#### Правило работы бота")
            items = value.get("items", value) if isinstance(value, dict) else value
            for item in items: st.markdown(f"- {item}")
        elif key in ["journal_05_05","journal_0505"]: render_html_wrap_table(value,"Журнал за 05.05")
        elif key in ["journal_06_05","journal_0605"]: render_html_wrap_table(value,"Журнал за 06.05")
        elif key == "repo_access":
            st.markdown("#### Доступ к репозиторию")
            for item in value: st.markdown(f"- {item}")
        elif key == "events_example": st.markdown("#### Пример событий"); st.code(value, language="python")
        elif key == "code_snippet":   st.markdown("#### Фрагмент кода");  st.code(value, language="python")
        elif key == "suspects_table": 
            render_html_wrap_table(value, "Таблица подозреваемых")
        elif key == "suspects_table_updated": 
            render_html_wrap_table(value, "Таблица подозреваемых (обновлено)")
        else: st.markdown(f"#### {key}"); st.write(value)

def md_to_html(text: str) -> str:
    # **жирный** → <strong>жирный</strong>
    text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text)
    # *курсив* → <em>курсив</em>
    text = re.sub(r'\*(.+?)\*', r'<em>\1</em>', text)
    return text

def render_detective_diary(diary):
    title = diary.get("title", "Дневник детектива")
    subtitle = diary.get("subtitle", "")
    
    # Собираем весь контент в HTML
    html = (
        f'<div style="background:#fff;border:1px solid #DDD0C2;border-radius:10px;'
        f'padding:12px 16px;margin-bottom:5px;font-size:.85rem;color:#33271e;">'
        f'<div style="font-weight:600;margin-bottom:8px;">📓 {title} · {subtitle}</div>'
    )
    
    for para in diary.get("content", []):
        html += f'<p style="margin-bottom:6px;">{md_to_html(para)}</p>'
    
    steps = diary.get("steps", [])
    if steps:
        html += '<p style="font-weight:600;margin:8px 0 4px;">Алгоритм:</p><ol style="margin:0;padding-left:20px;">'
        for step in steps:
            html += f'<li style="margin-bottom:4px;">{md_to_html(step)}</li>'
        html += '</ol>'
    
    checklist = diary.get("checklist", [])
    if checklist:
        for item in checklist:
            q = item.get("question", "")
            yes_lbl = item.get("yes_label", "Да")
            no_lbl = item.get("no_label", "Нет")
            html += (
                f'<p style="font-weight:600;margin:8px 0 2px;">{md_to_html(q)}</p>'
                f'<p style="margin:0;">✓ {yes_lbl}: {md_to_html(item.get("yes",""))}</p>'
                f'<p style="margin:0;">✗ {no_lbl}: {md_to_html(item.get("no",""))}</p>'
)
    
    example = diary.get("example")
    if example:
        html += (
            f'<p style="font-style:italic;margin-top:8px;">{example["question"]}</p>'
            f'<p style="margin:2px 0;">Слабо: {example["weak"]}</p>'
            f'<p style="margin:2px 0;">Сильно: {example["strong"]}</p>'
        )
    
    footer = diary.get("footer")
    if footer:
        html += f'<p style="font-style:italic;margin-top:8px;">{footer}</p>'
    
    html += '</div>'
    st.markdown(html, unsafe_allow_html=True)

# ── CSS ───────────────────────────────────────────────────────────────
# ВАЖНО: весь CSS — одна строка-литерал (не f-string),
# поэтому { } внутри CSS не нужно удваивать.
# Только там где нужна Python-интерполяция — используем конкатенацию.
NAV_CSS = """
/* ── NAV — папки по key-wrapper .st-key-tab_* ── */
.game-title {
    font-family:'Manrope',sans-serif!important;
    font-size:1.5rem;font-weight:900;line-height:1.2;
    color:#2e241b;margin-bottom:1.6rem;letter-spacing:-0.025em;
}
.left-divider { height:1px;width:72%;background:#cfc0ad;margin:.9rem 0; }
.nav-label {
    font-size:.81rem;font-weight:500;color:#5c4a38;
    margin-top:3px;margin-bottom:.85rem;line-height:1.3;
}
.nav-label-active { font-weight:700!important;color:#1a1208!important; }

/* Папки — прозрачная кнопка с SVG через ::before/::after */
.st-key-tab_chat .stButton > button,
.st-key-tab_materials .stButton > button,
.st-key-tab_analysis .stButton > button {
    position:relative!important;
    width:92px!important; height:68px!important; min-height:68px!important;
    padding:0!important; border:none!important;
    background:transparent!important; box-shadow:none!important;
    color:transparent!important; overflow:visible!important;
}
.st-key-tab_chat .stButton > button p,
.st-key-tab_materials .stButton > button p,
.st-key-tab_analysis .stButton > button p {
    font-size:0!important; color:transparent!important; line-height:0!important;
}
/* Тело папки */
.st-key-tab_chat .stButton > button::before,
.st-key-tab_materials .stButton > button::before,
.st-key-tab_analysis .stButton > button::before {
    content:""; position:absolute; left:0; bottom:0;
    width:92px; height:52px; border-radius:5px;
    background:#C4A882; transition:background .15s;
}
/* Вкладка папки */
.st-key-tab_chat .stButton > button::after,
.st-key-tab_materials .stButton > button::after,
.st-key-tab_analysis .stButton > button::after {
    content:""; position:absolute; left:0; top:0;
    width:42px; height:14px; border-radius:4px;
    background:#C4A882; transition:background .15s;
}
/* Hover */
.st-key-tab_chat .stButton > button:hover::before,
.st-key-tab_chat .stButton > button:hover::after,
.st-key-tab_materials .stButton > button:hover::before,
.st-key-tab_materials .stButton > button:hover::after,
.st-key-tab_analysis .stButton > button:hover::before,
.st-key-tab_analysis .stButton > button:hover::after { background:#B8945E; }
/* Активная вкладка */
.nav-active-chat .st-key-tab_chat .stButton > button::before,
.nav-active-chat .st-key-tab_chat .stButton > button::after,
.nav-active-materials .st-key-tab_materials .stButton > button::before,
.nav-active-materials .st-key-tab_materials .stButton > button::after,
.nav-active-analysis .st-key-tab_analysis .stButton > button::before,
.nav-active-analysis .st-key-tab_analysis .stButton > button::after { background:#B8945E!important; }

/* "Начать заново" — ссылка-стиль */
.st-key-reset_btn .stButton > button {
    background:none!important; border:none!important; box-shadow:none!important;
    color:#7a6454!important; padding:.2rem 0!important; min-height:auto!important;
}
.st-key-reset_btn .stButton > button p { color:#7a6454!important; font-size:.79rem!important; }
.st-key-reset_btn .stButton > button:hover p { color:#2e241b!important; }
"""

EXPANDER_CSS = """
/* ── EXPANDER — скрываем стрелку ── */
[data-testid="stExpander"] summary svg { 
    display:none!important; 
    visibility:hidden!important;
    width:0!important; 
    height:0!important;
    position:absolute!important;
}
details > summary { list-style:none!important; }
details > summary::-webkit-details-marker { display:none!important; }
summary::marker { display:none!important; }

[data-testid="stExpander"] {
    border:1px solid #DDD0C2!important; border-radius:10px!important;
    background:#FAF6EE!important; margin-bottom:5px!important;
}
[data-testid="stExpander"] summary {
    background:#FAF6EE!important; padding:8px 12px!important;
    cursor:pointer!important; list-style:none!important;
}
[data-testid="stExpander"] summary p {
    font-size:.85rem!important; font-weight:600!important;
    color:#33271e!important; margin:0!important;
}
"""

# f-string только для переменных Python (цвета текстур), всё остальное — литерал
st.markdown(f"""<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=Manrope:wght@600;700;800;900&display=swap');

/* ── BASE ── */
html,body,.stApp,[data-testid="stAppViewContainer"] {{
    background:{app_bg_css}!important;background-size:cover!important;
    background-attachment:fixed!important;
    font-family:'Inter',sans-serif!important;color:#2f241b;font-size:14px;
    color-scheme:light!important;
}}
* {{ color-scheme:light!important; }}
*,p,li,label,input,textarea,button,div,span {{ font-family:'Inter',sans-serif!important; }}
h1,h2,h3,h4,h5,h6 {{ font-family:'Manrope',sans-serif!important;font-weight:800!important;letter-spacing:-0.01em; }}
h4 {{ font-weight:700!important;font-size:.95rem!important;margin:.8rem 0 .35rem 0!important; }}
header[data-testid="stHeader"],[data-testid="stToolbar"],
[data-testid="stDecoration"],[data-testid="stStatusWidget"] {{ display:none!important; }}
.block-container {{
    max-width:1520px;padding-top:1.8rem!important;padding-bottom:1rem;
    padding-left:1.8rem!important;padding-right:1.8rem!important;
}}
section[data-testid="stSidebar"] {{ display:none!important; }}

/* ── КНОПКИ ── */
[data-testid="stBaseButton-primary"] {{
    border-radius:16px!important;background:#5B78B6!important;border:none!important;
    color:#FDFCFA!important;font-weight:600!important;font-size:.875rem!important;
}}
[data-testid="stBaseButton-primary"]:hover {{ background:#4a67a5!important; }}
[data-testid="stBaseButton-secondary"] {{
    border-radius:16px!important;background:#EDE5D8!important;
    border:1px solid #d2c0ac!important;color:#4a3828!important;
    font-weight:500!important;font-size:.84rem!important;
}}
[data-testid="stBaseButton-secondary"]:hover {{ background:#e4dace!important;color:#2e1f14!important; }}
[data-testid="stBaseButton-secondary"] p {{ color:#4a3828!important; }}

/* ── CHAT ── */
.vanya-card {{
    display:flex;gap:16px;align-items:flex-start;
    padding:20px 20px 16px 20px;
    background:{chat_shell_css};background-size:cover;
    border-radius:22px 22px 0 0;
}}
.vanya-avatar {{
    width:70px;height:70px;border-radius:13px;flex-shrink:0;
    background:{vanya_bg_css};background-size:cover;background-position:center;
}}
.vanya-name {{ font-family:'Manrope',sans-serif!important;font-size:1.05rem;font-weight:800;color:#F2EBE0;margin-bottom:5px; }}
.vanya-sub {{ font-size:.84rem;line-height:1.56;color:rgba(242,235,224,.72); }}
[data-testid="stIFrame"] {{
    border-radius:0 0 22px 22px!important;overflow:hidden!important;
    border:none!important;margin-top:0!important;
}}
[data-testid="stIFrame"] > iframe {{
    border-radius:0 0 22px 22px!important;border:none!important;display:block!important;
}}

/* ── INPUT ── */
.stTextArea textarea {{
    border-radius:16px!important;border:none!important;
    background:rgba(250,246,238,.92)!important;color:#2a1f16!important;
    font-size:.875rem!important;padding:10px 14px!important;
    box-shadow:none!important;resize:none!important;
}}
.stTextArea textarea::placeholder {{ color:#a08070!important; }}
.stTextArea textarea:focus {{ outline:none!important;box-shadow:0 0 0 2px rgba(91,120,182,.4)!important; }}

/* ── RIGHT PANEL ── */
.right-panel {{
    background:{panel_bg_css};background-size:cover;
    border-radius:20px;padding:22px 22px 20px 22px;
    box-shadow:0 4px 18px rgba(55,38,20,.09);
}}
.panel-title {{ font-family:'Manrope',sans-serif!important;font-size:1.1rem;font-weight:800;color:#261c13;margin-bottom:14px; }}
.panel-section-title {{ font-family:'Manrope',sans-serif!important;font-size:.97rem;font-weight:700;color:#261c13;margin-top:.2rem;margin-bottom:8px; }}
.panel-divider {{ height:1px;background:#DCCFC0;margin:1.1rem 0; }}
.progress-wrap {{ margin-top:10px;margin-bottom:16px; }}
.progress-track {{ width:100%;height:16px;background:#2A2621;border-radius:20px;overflow:hidden;margin-bottom:7px; }}
.progress-fill {{ height:100%;background:#F8F4EE;border-radius:20px;transition:width .4s ease; }}
.progress-label {{ font-size:.79rem;color:#6b5a4a; }}
.hypothesis-text {{ font-size:.845rem;line-height:1.62;color:#2f241b;background:rgba(255,252,248,.72);border-radius:11px;padding:9px 12px; }}
.material-log-node {{ margin-bottom:1.1rem;padding-bottom:.9rem;border-bottom:1px solid #DDD0C2; }}
.material-log-title {{ font-family:'Manrope',sans-serif!important;font-size:.9rem;font-weight:700;color:#33271e;margin-bottom:.45rem; }}
.wrap-table {{ overflow-x:auto; }}
.wrap-table table {{ border-collapse:collapse;width:100%;font-size:.79rem; }}
.wrap-table th {{ background:#EEE4D5;padding:6px 9px;text-align:left;border:1px solid #D6C8B4;font-weight:600;color:#2f241b; }}
.wrap-table td {{ padding:6px 9px;border:1px solid #E4DDD3;color:#2f241b; }}

/* ── AI REPORT ── */
.ai-detail-card {{ background:rgba(255,253,250,.9);border:1px solid #DECDBC;border-radius:11px;padding:10px 13px;margin-bottom:7px; }}
.ai-detail-top {{ display:flex;justify-content:space-between;align-items:center;margin-bottom:4px; }}
.ai-detail-title {{ font-weight:700;font-size:.84rem;color:#2f241b; }}
.ai-detail-score {{ font-size:.76rem;color:#6b5a4a;margin-bottom:3px; }}
.ai-detail-comment {{ font-size:.81rem;color:#3d3127;line-height:1.5; }}
.ai-quote-card {{ background:#F4EDE2;border-left:3px solid #CACBA4;border-radius:0 10px 10px 0;padding:8px 12px;margin-bottom:5px;font-size:.81rem;color:#33271e;font-style:italic;line-height:1.5; }}
.ai-recommendation-card {{ background:#ECF0FF;border-radius:11px;padding:10px 13px;font-size:.84rem;color:#2c3a6a;line-height:1.6; }}
[data-testid="stAlert"] {{ border-radius:13px!important;font-size:.84rem!important; }}
</style>""", unsafe_allow_html=True)

# NAV_CSS и EXPANDER_CSS — обычные строки (не f-string), { } не нужно удваивать
st.markdown(f"<style>{NAV_CSS}{EXPANDER_CSS}</style>", unsafe_allow_html=True)

# ── LAYOUT ───────────────────────────────────────────────────────────
left_col, center_col, right_col = st.columns([0.68, 2.1, 1.3], gap="large")

# ── LEFT NAV — st.button + CSS ::before/::after = папки без HTML-ссылок ──
with left_col:
    active_cls = {
        "chat":      "nav-active-chat",
        "materials": "nav-active-materials",
        "analysis":  "nav-active-analysis",
    }.get(active_view, "nav-active-chat")

    # Обёртка с классом активного таба — нужна для CSS-селектора папки
    st.markdown(f'<div class="{active_cls}">', unsafe_allow_html=True)
    st.markdown('<div class="game-title">AI-детектив:<br>дело о странных<br>сообщениях</div>', unsafe_allow_html=True)

    for vk, lbl in [("chat","Чат и задание"),("materials","Все материалы"),("analysis","Прогресс и анализ")]:
        # Кнопка с пробелом — текст скрыт CSS, визуал через ::before/::after
        if st.button(" ", key=f"tab_{vk}"):
            set_view(vk); st.rerun()
        lbl_cls = "nav-label nav-label-active" if active_view == vk else "nav-label"
        st.markdown(f'<div class="{lbl_cls}">{lbl}</div>', unsafe_allow_html=True)

    st.markdown('<div class="left-divider"></div>', unsafe_allow_html=True)
    if st.button("↺ Начать заново", key="reset_btn"):
        reset_state(st); st.rerun()

    st.markdown('</div>', unsafe_allow_html=True)

# ── CHAT ─────────────────────────────────────────────────────────────
if active_view == "chat":
    with center_col:
        st.markdown(f"""
        <div class="vanya-card">
          <div class="vanya-avatar"></div>
          <div>
            <div class="vanya-name">Привет! Я — Ваня, твой друг.</div>
            <div class="vanya-sub">Помоги мне понять, что произошло с нашим чат-ботом, кто и каким образом это сделал. Изучай улики и используй свои знания по информатике, чтобы найти правду и убедить меня.</div>
          </div>
        </div>""", unsafe_allow_html=True)

        st.iframe(chat_html_path, height=390)
        st.markdown('<div style="height:6px"></div>', unsafe_allow_html=True)

        if not is_finished(st):
            if current_question:
                user_answer = st.text_area(
                    "Ответ", key=answer_key, height=100,
                    placeholder="Напиши сообщение...", label_visibility="collapsed")
                c1, c2 = st.columns([1.6, 0.55])
                with c1:
                    if st.button("Отправить ответ", type="primary", use_container_width=True):
                        if user_answer.strip():
                            submit_answer(st, user_answer.strip()); st.rerun()
                with c2:
                    if st.button("Сбросить", use_container_width=True):
                        st.session_state[answer_key] = ""; st.rerun()
            else:
                st.success("Этот этап не требует отдельного ответа.")
                if st.button("Продолжить", type="primary", use_container_width=True):
                    continue_without_answer(st); st.rerun()
        else:
            st.success("Расследование завершено.")
            if st.button("Сформировать AI-анализ", type="primary", use_container_width=True):
                try:
                    rep = generate_ai_teacher_report(report_input)
                    set_ai_teacher_report(st, rep)
                    if not st.session_state.get("run_summary_saved", False):
                        save_run_summary(st)
                        st.session_state.run_summary_saved = True
                    st.success("AI-анализ сформирован."); st.rerun()
                except Exception as e:
                    st.error(f"Ошибка: {e}")

    with right_col:
        st.markdown(
            '<div class="right-panel">'
            '<div class="panel-section-title">Прогресс и текущая версия</div>'
            f'<div class="progress-wrap">'
            f'<div class="progress-track"><div class="progress-fill" style="width:{max(progress,2)}%"></div></div>'
            f'<div class="progress-label">{progress}% пройдено</div>'
            f'</div>'
            f'<div class="hypothesis-text">{get_hypothesis(st)}</div>',
            unsafe_allow_html=True)
        st.markdown('<div class="panel-divider"></div>', unsafe_allow_html=True)

        # ✅ ИНСТРУКЦИЯ — теперь СВЕРХУ, перед материалами
        st.markdown('<div class="panel-section-title">Инструкция</div>', unsafe_allow_html=True)
        st.write(current_question if current_question else "На этом шаге отдельного ответа не требуется.")
        st.markdown('<div class="panel-divider"></div>', unsafe_allow_html=True)

        # Материалы дела — теперь НИЖЕ
        st.markdown('<div class="panel-section-title">Текущие материалы дела</div>', unsafe_allow_html=True)
        if current_diaries:
            with st.container(height=260):
                for diary in current_diaries:
                    render_detective_diary(diary)
        elif materials_to_show:
            with st.container(height=260):
                render_materials(materials_to_show)
        else:
            st.markdown('<div style="font-size:.82rem;color:#9a8878;font-style:italic;">Улики появятся здесь по мере расследования…</div>', unsafe_allow_html=True)
        st.markdown("""
        <script>
        setTimeout(function(){
            var containers = window.parent.document.querySelectorAll('[data-testid="stVerticalBlockBorderWrapper"]');
            containers.forEach(function(c){ c.scrollTop = 0; });
        }, 300);
        </script>
        """, unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)

# ── MATERIALS ─────────────────────────────────────────────────────────
elif active_view == "materials":
    with center_col:
        st.markdown(
            '<div class="right-panel">'
            '<div class="panel-title">Все материалы</div>'
            '<div style="font-size:.84rem;color:#6b5a4a;margin-bottom:16px;">'
            'Здесь собраны все материалы по мере их появления в кейсе — улики, таблицы, фрагменты кода.'
            '</div>',
            unsafe_allow_html=True)
        with st.container(key="materials_log_box"):
            if st.session_state.all_materials_log:
                for entry in st.session_state.all_materials_log:
                    st.markdown(
                        f'<div class="material-log-node">'
                        f'<div class="material-log-title">Этап: {entry["node"]}</div>',
                        unsafe_allow_html=True)
                    render_materials(entry["materials"])
                    st.markdown("</div>", unsafe_allow_html=True)
            else:
                st.write("Материалы пока не накоплены.")

# ── ANALYSIS ──────────────────────────────────────────────────────────
elif active_view == "analysis":
    with center_col:
        st.markdown(
            '<div class="right-panel">'
            '<div class="panel-title">Прогресс и анализ</div>'
            '<div class="panel-section-title">Прогресс</div>',
            unsafe_allow_html=True)
        st.markdown(
            f'<div class="progress-wrap">'
            f'<div class="progress-track"><div class="progress-fill" style="width:{max(progress,2)}%"></div></div>'
            f'<div class="progress-label"><b>{progress}%</b> пройдено · '
            f'посещено узлов: {len(summary["visited_nodes"])}</div>'
            f'</div>',
            unsafe_allow_html=True)
        st.markdown('<div class="panel-divider"></div>', unsafe_allow_html=True)
        st.markdown('<div class="panel-section-title">Сводка по баллам</div>', unsafe_allow_html=True)
        st.write(
            f"Безопасность: {summary['security']} · "
            f"Алгоритмы: {summary['rules']} · "
            f"Код: {summary['code']} · "
            f"Гипотеза: {summary['hypothesis']}"
        )
        st.markdown('<div class="panel-divider"></div>', unsafe_allow_html=True)
        st.markdown('<div class="panel-section-title">Использованные подсказки</div>', unsafe_allow_html=True)
        if summary["hint_nodes_used"]:
            for h in summary["hint_nodes_used"]: st.markdown(f"- {h}")
        else:
            st.write("Подсказки не использовались.")
        st.markdown('<div class="panel-divider"></div>', unsafe_allow_html=True)
        render_ai_report(ai_report)
        st.markdown("</div>", unsafe_allow_html=True)

    with right_col:
        st.markdown('<div class="right-panel"><div class="panel-title">Экспорт</div>', unsafe_allow_html=True)
        if is_finished(st):
            if st.button("Сформировать AI-анализ", type="primary",
                         use_container_width=True, key="analysis_report_btn"):
                try:
                    rep = generate_ai_teacher_report(report_input)
                    set_ai_teacher_report(st, rep)
                    if not st.session_state.get("run_summary_saved", False):
                        save_run_summary(st)
                        st.session_state.run_summary_saved = True
                    st.success("AI-анализ сформирован."); st.rerun()
                except Exception as e:
                    st.error(f"Ошибка: {e}")
        for path, lbl, fname in [
            ("data/events_log.csv",    "Скачать events CSV",  "events_log.csv"),
            ("data/runs_summary.csv",  "Скачать summary CSV", "runs_summary.csv"),
        ]:
            p = Path(path)
            if p.exists():
                with open(p, "rb") as f:
                    st.download_button(lbl, data=f, file_name=fname, mime="text/csv")
        st.markdown("</div>", unsafe_allow_html=True)