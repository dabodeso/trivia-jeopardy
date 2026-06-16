"""
Trivia Emprendimiento (Jeopardy) - Aplicación multidispositivo en tiempo real.

Roles:
  - Pantalla Principal (?role=display)  → tablero proyectado
  - Presentador       (?role=presenter) → controla el juego (contraseña 654321)
  - Concursante       (?role=contestant&pid=<id>) → pulsador

Preguntas y categorías: edita questions.json
Estado del juego en curso: game_state.json (se genera automáticamente)
"""

import json
import os
import time
import uuid
import streamlit as st
import streamlit.components.v1 as components
from streamlit_autorefresh import st_autorefresh

# ──────────────────────────────────────────────────────────────────────────────
# Constantes
# ──────────────────────────────────────────────────────────────────────────────
STATE_FILE = "game_state.json"
QUESTIONS_FILE = "questions.json"
PRESENTER_PASSWORD = "654321"
GAME_TITLE = "TRIVIA EMPRENDIMIENTO"
GAME_SUBTITLE = "Trivia Jeopardy"
NUM_CATEGORIES = 4
QUESTIONS_PER_CATEGORY = 4
POINT_VALUES = [100, 200, 300, 400]

# ──────────────────────────────────────────────────────────────────────────────
# Preguntas (questions.json)
# ──────────────────────────────────────────────────────────────────────────────

def load_questions_config():
    """Lee categorías y preguntas desde questions.json."""
    if not os.path.exists(QUESTIONS_FILE):
        raise FileNotFoundError(
            f"No se encontró {QUESTIONS_FILE}. "
            "Crea el archivo con tus categorías y preguntas."
        )
    with open(QUESTIONS_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    categories = data.get("categories", [])
    if len(categories) != NUM_CATEGORIES:
        raise ValueError(
            f"{QUESTIONS_FILE} debe tener {NUM_CATEGORIES} categorías "
            f"(tiene {len(categories)})."
        )
    for i, cat in enumerate(categories):
        qs = cat.get("questions", [])
        if len(qs) != QUESTIONS_PER_CATEGORY:
            raise ValueError(
                f"Categoría «{cat.get('name', i)}»: se esperan "
                f"{QUESTIONS_PER_CATEGORY} preguntas (tiene {len(qs)})."
            )
    return categories


def build_categories_from_config():
    """Convierte questions.json al formato interno del juego."""
    categories = []
    for i, cat in enumerate(load_questions_config()):
        questions = []
        for j, q in enumerate(cat["questions"]):
            points = q.get("points", POINT_VALUES[j])
            questions.append({
                "id": f"c{i}q{j}",
                "text": q["text"],
                "points": points,
                "answered": False,
            })
        categories.append({"name": cat["name"], "questions": questions})
    return categories


# ──────────────────────────────────────────────────────────────────────────────
# Gestión del estado compartido
# ──────────────────────────────────────────────────────────────────────────────

def default_state():
    return {
        "players": [],
        "categories": build_categories_from_config(),
        # board | question_active | buzzed
        "game_phase": "board",
        "current_question": None,   # {"cat": int, "q": int}
        "buzzed_player_id": None,
        "buzzers_active": False,
        "failed_players": [],       # IDs de jugadores que ya fallaron esta ronda
        "last_update": 0.0,
    }


def load_state():
    try:
        if os.path.exists(STATE_FILE):
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                state = json.load(f)
            cats = state.get("categories", [])
            if (
                len(cats) != NUM_CATEGORIES
                or any(
                    len(c.get("questions", [])) != QUESTIONS_PER_CATEGORY
                    for c in cats
                )
            ):
                # Tablero desactualizado → regenerar preguntas desde questions.json
                new = default_state()
                new["players"] = state.get("players", [])
                save_state(new)
                return new
            return state
    except Exception:
        pass
    s = default_state()
    save_state(s)
    return s


def save_state(state):
    """Escritura atómica: escribe en .tmp y luego renombra."""
    state["last_update"] = time.time()
    tmp = STATE_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)
    os.replace(tmp, STATE_FILE)


def find_player(state, pid):
    for p in state["players"]:
        if p["id"] == pid:
            return p
    return None


def player_name(state, pid):
    p = find_player(state, pid)
    return p["name"] if p else "?"


def reset_round(state):
    """Limpia el estado de la ronda actual (sin modificar preguntas)."""
    state.update({
        "game_phase": "board",
        "current_question": None,
        "buzzed_player_id": None,
        "buzzers_active": False,
        "failed_players": [],
    })


# ──────────────────────────────────────────────────────────────────────────────
# CSS global
# ──────────────────────────────────────────────────────────────────────────────
CSS = """
<style>
#MainMenu, header, footer { visibility: hidden !important; }
[data-testid="stSidebar"] { display: none !important; }

html, body, [data-testid="stAppViewContainer"] {
    background-color: #050e1f !important;
    color: #e8f0fe !important;
    font-family: 'Segoe UI', Tahoma, Geneva, sans-serif;
}
[data-testid="block-container"] {
    padding: 0.7rem 1.2rem !important;
    max-width: 100% !important;
}

/* Botones por defecto */
.stButton > button {
    background-color: #1565c0 !important;
    color: white !important;
    border: 2px solid #42a5f5 !important;
    border-radius: 8px !important;
    font-weight: 700 !important;
    transition: background 0.15s, border 0.15s;
}
.stButton > button:hover {
    background-color: #1976d2 !important;
    border-color: #90caf9 !important;
}

/* Inputs */
.stTextInput > div > div > input {
    background-color: #0d2040 !important;
    color: white !important;
    border: 2px solid #42a5f5 !important;
    border-radius: 8px !important;
}
.stTextInput > label { color: #90caf9 !important; }

/* ── Componentes personalizados ── */
.game-title {
    text-align: center;
    font-size: 2.6em;
    font-weight: 900;
    color: #ffd54f;
    letter-spacing: 3px;
    margin-bottom: 6px;
}
.cat-header {
    background: linear-gradient(155deg, #1565c0, #0d47a1);
    color: white;
    text-align: center;
    padding: 12px 6px;
    font-weight: 800;
    font-size: 0.92em;
    border: 2px solid #42a5f5;
    border-radius: 6px;
    text-transform: uppercase;
    letter-spacing: 1px;
    min-height: 56px;
    display: flex;
    align-items: center;
    justify-content: center;
}
.q-cell {
    background: linear-gradient(155deg, #1565c0, #0d47a1);
    color: #ffd54f;
    text-align: center;
    padding: 8px 4px;
    font-size: 1.9em;
    font-weight: 900;
    border: 2px solid #42a5f5;
    border-radius: 6px;
    min-height: 66px;
    display: flex;
    align-items: center;
    justify-content: center;
}
.q-cell.answered {
    background: linear-gradient(155deg, #1e2a32, #141e24);
    color: #2c3e50;
    border-color: #2c3e50;
}
.player-card {
    background: linear-gradient(155deg, #1565c0, #0d47a1);
    border: 2px solid #42a5f5;
    border-radius: 12px;
    text-align: center;
    padding: 10px 6px;
}
.player-card .p-name  { font-size: 1.05em; font-weight: 700; color: #e3f2fd; }
.player-card .p-score { font-size: 2em;    font-weight: 900; color: #ffd54f; line-height: 1.1; }
.player-card .p-label { font-size: 0.7em;  color: #90caf9; }

.question-box {
    background: linear-gradient(155deg, #1565c0, #0d47a1);
    border: 4px solid #42a5f5;
    border-radius: 20px;
    text-align: center;
    padding: 55px 40px;
    font-size: 2.4em;
    font-weight: 700;
    color: white;
    line-height: 1.4;
    margin: 8px 0;
}
.status-box {
    background: linear-gradient(155deg, #0d2040, #071428);
    border: 3px solid #42a5f5;
    border-radius: 16px;
    padding: 22px 20px;
    text-align: center;
}
.big-score {
    font-size: 4.5em;
    font-weight: 900;
    color: #ffd54f;
    text-align: center;
    line-height: 1;
}
.label-sm {
    color: #90caf9;
    font-size: 0.8em;
    text-transform: uppercase;
    letter-spacing: 2px;
    margin-bottom: 4px;
}
</style>
"""


# ──────────────────────────────────────────────────────────────────────────────
# Widget QR (usa iframe → window.parent.location)
# ──────────────────────────────────────────────────────────────────────────────
def show_qr(size=160):
    components.html(f"""
    <div style="text-align:center;font-family:Segoe UI,sans-serif;">
        <div id="qr"></div>
        <p id="lnk" style="color:#42a5f5;font-size:0.85em;
           word-break:break-all;margin-top:6px;"></p>
    </div>
    <script>
        try {{
            var base = window.parent.location.origin
                     + window.parent.location.pathname;
            var img = document.createElement('img');
            img.src = 'https://api.qrserver.com/v1/create-qr-code/'
                    + '?size={size}x{size}&data=' + encodeURIComponent(base);
            img.style.borderRadius = '10px';
            document.getElementById('qr').appendChild(img);
            document.getElementById('lnk').textContent = base;
        }} catch(e) {{
            document.getElementById('lnk').textContent =
                'Usa la barra de direcciones del navegador para la URL';
        }}
    </script>
    """, height=size + 50)


# ──────────────────────────────────────────────────────────────────────────────
# Tablero HTML (solo lectura — pantalla principal)
# ──────────────────────────────────────────────────────────────────────────────
def board_html(state):
    cats = state["categories"]
    html = ('<div style="display:grid;'
            'grid-template-columns:repeat(4,1fr);gap:5px;">')
    for cat in cats:
        html += f'<div class="cat-header">{cat["name"]}</div>'
    for j in range(QUESTIONS_PER_CATEGORY):
        for cat in cats:
            q = cat["questions"][j]
            if q["answered"]:
                html += '<div class="q-cell answered">&nbsp;</div>'
            else:
                html += f'<div class="q-cell">{q["points"]}</div>'
    html += '</div>'
    return html


# ──────────────────────────────────────────────────────────────────────────────
# Pantallas
# ──────────────────────────────────────────────────────────────────────────────

# ── Lobby ─────────────────────────────────────────────────────────────────────
def screen_lobby():
    st.markdown(
        f'<div class="game-title">🎯 {GAME_TITLE}</div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        f'<p style="text-align:center;color:#90caf9;font-size:1.1em;">'
        f'{GAME_SUBTITLE} · Selecciona tu rol para unirte al concurso</p>',
        unsafe_allow_html=True,
    )
    st.markdown("<br>", unsafe_allow_html=True)

    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown(
            '<div class="label-sm" style="text-align:center">PROYECCIÓN</div>',
            unsafe_allow_html=True,
        )
        if st.button("📺  Pantalla Principal", use_container_width=True):
            st.query_params["role"] = "display"
            st.rerun()
    with c2:
        st.markdown(
            '<div class="label-sm" style="text-align:center">STAFF</div>',
            unsafe_allow_html=True,
        )
        if st.button("🎙️  Presentador", use_container_width=True):
            st.query_params["role"] = "presenter_login"
            st.rerun()
    with c3:
        st.markdown(
            '<div class="label-sm" style="text-align:center">JUGADOR</div>',
            unsafe_allow_html=True,
        )
        if st.button("🙋  Soy Concursante", use_container_width=True):
            st.query_params["role"] = "contestant_login"
            st.rerun()

    st.markdown("---")
    st.markdown(
        '<p class="label-sm" style="text-align:center">'
        'ESCANEA EL QR PARA UNIRTE</p>',
        unsafe_allow_html=True,
    )
    _, col_qr, _ = st.columns([1, 2, 1])
    with col_qr:
        show_qr(size=170)


# ── Login presentador ─────────────────────────────────────────────────────────
def screen_presenter_login():
    st.markdown(
        '<div class="game-title">🎙️ Acceso Presentador</div>',
        unsafe_allow_html=True,
    )
    st.markdown("<br>", unsafe_allow_html=True)
    _, col, _ = st.columns([1, 2, 1])
    with col:
        pw = st.text_input("Contraseña:", type="password", key="pres_pw")
        if st.button("Entrar →", use_container_width=True):
            if pw == PRESENTER_PASSWORD:
                st.query_params["role"] = "presenter"
                st.rerun()
            else:
                st.error("Contraseña incorrecta.")
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("← Volver", use_container_width=True):
            st.query_params.clear()
            st.rerun()


# ── Login concursante ─────────────────────────────────────────────────────────
def screen_contestant_login():
    st.markdown(
        '<div class="game-title">🙋 Unirte al Concurso</div>',
        unsafe_allow_html=True,
    )
    st.markdown("<br>", unsafe_allow_html=True)
    _, col, _ = st.columns([1, 2, 1])
    with col:
        name = st.text_input(
            "¿Cómo te llamas?",
            key="cname",
            max_chars=20,
            placeholder="Escribe tu nombre...",
        )
        if st.button("¡Unirme!", use_container_width=True):
            name = name.strip()
            if not name:
                st.warning("Por favor, escribe tu nombre.")
            else:
                state = load_state()
                taken = {p["name"].lower() for p in state["players"]}
                if name.lower() in taken:
                    st.error(f"El nombre «{name}» ya está en uso. Elige otro.")
                elif len(state["players"]) >= 3:
                    st.error(
                        "Ya hay 3 concursantes registrados. "
                        "Espera a que el presentador reinicie la partida."
                    )
                else:
                    pid = str(uuid.uuid4())[:8]
                    state["players"].append(
                        {"id": pid, "name": name, "points": 0}
                    )
                    save_state(state)
                    st.query_params["role"] = "contestant"
                    st.query_params["pid"] = pid
                    st.rerun()
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("← Volver", use_container_width=True):
            st.query_params.clear()
            st.rerun()


# ── Pantalla principal (proyectada) ──────────────────────────────────────────
def screen_display():
    st_autorefresh(interval=1000, key="disp_ref")
    state = load_state()
    phase = state["game_phase"]

    # ── Puntuaciones (parte superior) ──
    players = state["players"]
    if players:
        cols = st.columns(max(len(players), 1))
        for i, p in enumerate(players):
            with cols[i]:
                st.markdown(
                    f"""
                    <div class="player-card">
                        <div class="p-name">{p['name']}</div>
                        <div class="p-score">{p['points']}</div>
                        <div class="p-label">puntos</div>
                    </div>""",
                    unsafe_allow_html=True,
                )
    else:
        st.markdown(
            '<p style="text-align:center;color:#42a5f5;font-size:1em;">'
            '⏳ Esperando concursantes...</p>',
            unsafe_allow_html=True,
        )
        _, cq, _ = st.columns([2, 1, 2])
        with cq:
            show_qr(size=140)

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Contenido principal (80 % de la pantalla) ──
    if phase == "question_active" and state.get("current_question"):
        cq = state["current_question"]
        q = state["categories"][cq["cat"]]["questions"][cq["q"]]
        st.markdown(
            f'<div class="question-box">{q["text"]}</div>',
            unsafe_allow_html=True,
        )
        st.markdown(
            f'<p style="text-align:center;color:#42a5f5;font-size:1.2em;'
            f'margin-top:6px;">Valor: <strong>{q["points"]} puntos</strong></p>',
            unsafe_allow_html=True,
        )
    else:
        # Tablero de categorías
        st.markdown(board_html(state), unsafe_allow_html=True)


# ── Panel del presentador ─────────────────────────────────────────────────────
def screen_presenter():
    st_autorefresh(interval=1000, key="pres_ref")
    state = load_state()
    phase = state["game_phase"]

    st.markdown(
        '<div style="color:#ffd54f;font-size:1.3em;font-weight:800;">'
        '🎙️ PANEL DEL PRESENTADOR</div>',
        unsafe_allow_html=True,
    )
    st.markdown("<br>", unsafe_allow_html=True)

    # ── Fase: tablero ──
    if phase == "board":
        _presenter_board(state)
        st.markdown("---")
        c1, c2 = st.columns(2)
        with c1:
            if st.button(
                "🔄 Reiniciar tablero (mantener jugadores y puntos)",
                use_container_width=True,
            ):
                ns = default_state()
                ns["players"] = state["players"]
                save_state(ns)
                st.rerun()
        with c2:
            if st.button(
                "🗑️ Reiniciar todo (nueva partida desde cero)",
                use_container_width=True,
            ):
                save_state(default_state())
                st.rerun()

    # ── Fase: pregunta activa ──
    elif phase == "question_active":
        cq = state["current_question"]
        q = state["categories"][cq["cat"]]["questions"][cq["q"]]
        st.markdown(
            f"""
            <div class="status-box">
                <div class="label-sm">PREGUNTA ACTIVA — {q['points']} pts</div>
                <div style="font-size:1.3em;color:white;margin-top:8px;">
                    {q['text']}
                </div>
            </div>""",
            unsafe_allow_html=True,
        )
        st.markdown(
            '<p style="text-align:center;color:#42a5f5;margin-top:12px;">'
            '⏳ Esperando que alguien pulse su pulsador...</p>',
            unsafe_allow_html=True,
        )
        # Mostrar quién ya falló
        if state["failed_players"]:
            failed_names = ", ".join(
                player_name(state, pid) for pid in state["failed_players"]
            )
            st.markdown(
                f'<p style="text-align:center;color:#ef5350;font-size:0.9em;">'
                f'Ya fallaron: {failed_names}</p>',
                unsafe_allow_html=True,
            )
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("⏭️  Saltar pregunta", use_container_width=True):
            s = load_state()
            c = s["current_question"]
            s["categories"][c["cat"]]["questions"][c["q"]]["answered"] = True
            reset_round(s)
            save_state(s)
            st.rerun()

    # ── Fase: alguien ha pulsado ──
    elif phase == "buzzed":
        cq = state["current_question"]
        q = state["categories"][cq["cat"]]["questions"][cq["q"]]
        bid = state["buzzed_player_id"]
        bname = player_name(state, bid)

        st.markdown(
            f"""
            <div class="status-box">
                <div class="label-sm">HA PULSADO</div>
                <div style="font-size:2.2em;font-weight:900;color:#ffd54f;">
                    {bname}
                </div>
                <div style="color:#90caf9;font-size:1em;margin-top:8px;">
                    {q['text']}
                </div>
                <div style="color:#42a5f5;margin-top:4px;">
                    Valor: {q['points']} pts
                </div>
            </div>""",
            unsafe_allow_html=True,
        )
        st.markdown("<br>", unsafe_allow_html=True)

        c1, c2, c3 = st.columns(3)

        with c1:
            if st.button("✅  CORRECTO", use_container_width=True):
                s = load_state()
                c = s["current_question"]
                pts = s["categories"][c["cat"]]["questions"][c["q"]]["points"]
                for p in s["players"]:
                    if p["id"] == s["buzzed_player_id"]:
                        p["points"] += pts
                        break
                s["categories"][c["cat"]]["questions"][c["q"]]["answered"] = True
                reset_round(s)
                save_state(s)
                st.rerun()

        with c2:
            if st.button("❌  INCORRECTO (rebote)", use_container_width=True):
                s = load_state()
                c = s["current_question"]
                pts = s["categories"][c["cat"]]["questions"][c["q"]]["points"]
                failed_id = s["buzzed_player_id"]
                for p in s["players"]:
                    if p["id"] == failed_id:
                        p["points"] -= pts
                        break
                s["failed_players"].append(failed_id)
                s["buzzed_player_id"] = None
                remaining = [
                    p for p in s["players"]
                    if p["id"] not in s["failed_players"]
                ]
                if remaining:
                    # Rebote: reactivar pulsadores del resto
                    s["game_phase"] = "question_active"
                    s["buzzers_active"] = True
                else:
                    # Todos fallaron → pregunta respondida
                    s["categories"][c["cat"]]["questions"][c["q"]]["answered"] = True
                    reset_round(s)
                save_state(s)
                st.rerun()

        with c3:
            if st.button("⏭️  SIGUIENTE", use_container_width=True):
                s = load_state()
                c = s["current_question"]
                s["categories"][c["cat"]]["questions"][c["q"]]["answered"] = True
                reset_round(s)
                save_state(s)
                st.rerun()


def _presenter_board(state):
    """Tablero interactivo para que el presentador seleccione preguntas."""
    cats = state["categories"]

    # Cabeceras de categorías
    hcols = st.columns(NUM_CATEGORIES)
    for i, cat in enumerate(cats):
        with hcols[i]:
            st.markdown(
                f'<div class="cat-header">{cat["name"]}</div>',
                unsafe_allow_html=True,
            )

    # Preguntas
    for j in range(QUESTIONS_PER_CATEGORY):
        qcols = st.columns(NUM_CATEGORIES)
        for i, cat in enumerate(cats):
            with qcols[i]:
                q = cat["questions"][j]
                if q["answered"]:
                    st.markdown(
                        '<div class="q-cell answered">&nbsp;</div>',
                        unsafe_allow_html=True,
                    )
                else:
                    if st.button(
                        str(q["points"]),
                        key=f"pq_{i}_{j}",
                        use_container_width=True,
                    ):
                        s = load_state()
                        s.update({
                            "game_phase": "question_active",
                            "current_question": {"cat": i, "q": j},
                            "buzzers_active": True,
                            "buzzed_player_id": None,
                            "failed_players": [],
                        })
                        save_state(s)
                        st.rerun()


# ── Pulsador del concursante ──────────────────────────────────────────────────
def screen_contestant(pid):
    st_autorefresh(interval=800, key="cont_ref")
    state = load_state()
    player = find_player(state, pid)

    if not player:
        st.error("No se encontró tu perfil. Vuelve al inicio y regístrate de nuevo.")
        if st.button("← Inicio"):
            st.query_params.clear()
            st.rerun()
        return

    phase = state["game_phase"]
    name  = player["name"]
    pts   = player["points"]

    # ── Fase tablero: mostrar solo puntos ──
    if phase == "board":
        st.markdown(
            f"""
            <div style="text-align:center;padding:50px 20px;">
                <div style="font-size:1.4em;color:#90caf9;font-weight:700;">
                    ¡Hola, {name}!
                </div>
                <div class="label-sm" style="margin-top:24px;">TUS PUNTOS</div>
                <div class="big-score">{pts}</div>
                <div style="color:#37474f;margin-top:30px;font-size:0.9em;">
                    ⏳ Esperando la siguiente pregunta...
                </div>
            </div>""",
            unsafe_allow_html=True,
        )

    # ── Fase pregunta activa ──
    elif phase == "question_active":
        failed        = state.get("failed_players", [])
        buzzers_active = state.get("buzzers_active", False)

        if pid in failed:
            # Este jugador ya falló en esta ronda
            st.markdown(
                f"""
                <div style="text-align:center;padding:50px 20px;">
                    <div style="font-size:1.5em;color:#ef5350;font-weight:700;">
                        Ya respondiste esta ronda ❌
                    </div>
                    <div class="label-sm" style="margin-top:24px;">TUS PUNTOS</div>
                    <div class="big-score">{pts}</div>
                </div>""",
                unsafe_allow_html=True,
            )
        elif buzzers_active:
            # ── PULSADOR ──
            st.markdown(
                f'<div style="text-align:center;padding:10px 0;'
                f'color:#90caf9;font-size:1.2em;font-weight:700;">{name}</div>',
                unsafe_allow_html=True,
            )
            # Sobreescribir estilos de botón solo en esta vista
            st.markdown(
                """
                <style>
                div[data-testid="stButton"] > button {
                    height: 250px !important;
                    font-size: 2.8em !important;
                    background: linear-gradient(135deg,#b71c1c,#c62828) !important;
                    border: 4px solid #ef5350 !important;
                    border-radius: 20px !important;
                    letter-spacing: 4px;
                }
                div[data-testid="stButton"] > button:hover {
                    background: linear-gradient(135deg,#c62828,#d32f2f) !important;
                    border-color: #ff5252 !important;
                }
                </style>""",
                unsafe_allow_html=True,
            )
            if st.button("🔔  PULSA  🔔", use_container_width=True, key="buzz_btn"):
                # Recargar estado justo antes de escribir (reducir race conditions)
                s = load_state()
                if (
                    s["game_phase"] == "question_active"
                    and s.get("buzzers_active")
                    and pid not in s.get("failed_players", [])
                    and s.get("buzzed_player_id") is None
                ):
                    s["buzzed_player_id"] = pid
                    s["game_phase"] = "buzzed"
                    s["buzzers_active"] = False
                    save_state(s)
                st.rerun()
        else:
            st.markdown(
                f"""
                <div style="text-align:center;padding:50px 20px;">
                    <div style="font-size:1.2em;color:#42a5f5;">Preparando...</div>
                    <div class="big-score">{pts}</div>
                </div>""",
                unsafe_allow_html=True,
            )

    # ── Fase: alguien pulsó ──
    elif phase == "buzzed":
        if state.get("buzzed_player_id") == pid:
            st.markdown(
                f"""
                <div style="text-align:center;padding:50px 20px;">
                    <div style="font-size:2.4em;font-weight:900;color:#66bb6a;
                                line-height:1.2;">
                        🔔<br>¡HAS PULSADO!
                    </div>
                    <div style="font-size:0.95em;color:#a5d6a7;margin-top:12px;">
                        Esperando la valoración del presentador...
                    </div>
                    <div class="label-sm" style="margin-top:28px;">TUS PUNTOS</div>
                    <div class="big-score">{pts}</div>
                </div>""",
                unsafe_allow_html=True,
            )
        else:
            bname = player_name(state, state.get("buzzed_player_id", ""))
            st.markdown(
                f"""
                <div style="text-align:center;padding:50px 20px;">
                    <div style="font-size:1.5em;color:#42a5f5;">
                        🔔 <strong>{bname}</strong> ha pulsado
                    </div>
                    <div style="color:#546e7a;margin-top:10px;font-size:0.9em;">
                        Esperando resolución...
                    </div>
                    <div class="label-sm" style="margin-top:28px;">TUS PUNTOS</div>
                    <div class="big-score">{pts}</div>
                </div>""",
                unsafe_allow_html=True,
            )


# ──────────────────────────────────────────────────────────────────────────────
# Enrutador principal
# ──────────────────────────────────────────────────────────────────────────────
def main():
    st.set_page_config(
        page_title="Trivia Emprendimiento",
        page_icon="🎯",
        layout="wide",
        initial_sidebar_state="collapsed",
    )
    st.markdown(CSS, unsafe_allow_html=True)

    role = st.query_params.get("role", "")

    if role == "display":
        screen_display()
    elif role == "presenter_login":
        screen_presenter_login()
    elif role == "presenter":
        screen_presenter()
    elif role == "contestant_login":
        screen_contestant_login()
    elif role == "contestant":
        pid = st.query_params.get("pid", "")
        if pid:
            screen_contestant(pid)
        else:
            st.query_params.clear()
            st.rerun()
    else:
        screen_lobby()


if __name__ == "__main__":
    main()
