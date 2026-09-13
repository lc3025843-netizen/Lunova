from __future__ import annotations

import base64
import hashlib
from datetime import datetime
from pathlib import Path
from typing import Any

import streamlit as st

from lunova.ai import rewrite_text
from lunova.analysis import similarity, writing_metrics
from lunova.backend import (
    BackendUnavailable,
    admin_list_announcements,
    admin_publish_announcement,
    admin_set_announcement_active,
    admin_set_setting,
    admin_stats,
    auth_user_from_supabase,
    create_client,
    create_document,
    delete_document,
    delete_docx,
    download_docx,
    ensure_profile,
    get_app_settings,
    get_document,
    get_preferences,
    get_profile,
    list_documents,
    list_revisions,
    mark_announcement_read,
    restore_session,
    save_preferences,
    save_revision,
    session_tokens,
    sign_in,
    sign_out,
    sign_up,
    unread_announcements,
    update_document,
    update_profile,
    upload_original_docx,
)
from lunova.config import APP_TITLE, APP_VERSION, DOC_BUCKET, MAX_TEXT_CHARS
from lunova.documents import extract_docx_text, export_revised_docx

ROOT = Path(__file__).parent
ASSETS = ROOT / "assets"


def secret(name: str, default: str = "") -> str:
    try:
        value = st.secrets.get(name, default)
        return str(value) if value is not None else default
    except Exception:
        return default


def bool_secret(name: str, default: bool = False) -> bool:
    return secret(name, str(default)).strip().lower() in {"1", "true", "yes", "on"}


def admin_emails() -> set[str]:
    raw = secret("ADMIN_EMAILS", "")
    return {part.strip().lower() for part in raw.split(",") if part.strip()}


st.set_page_config(
    page_title=APP_TITLE,
    page_icon=str(ASSETS / "favicon.png"),
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={"About": f"**Lunova v{APP_VERSION}** — Transforma tus ideas. Conserva tu esencia."},
)


def svg_data_uri(path: Path) -> str:
    raw = path.read_text(encoding="utf-8")
    encoded = base64.b64encode(raw.encode("utf-8")).decode("ascii")
    return f"data:image/svg+xml;base64,{encoded}"


LOGO = svg_data_uri(ASSETS / "logo.svg")

CSS = r"""
<style>
:root{--ln-navy:#102047;--ln-ink:#16264d;--ln-muted:#71809f;--ln-blue:#4b67f2;--ln-violet:#8464f4;--ln-bg:#f5f7fb;--ln-border:#e5e9f3;--ln-card:#fff}
[data-testid="stAppViewContainer"]{background:linear-gradient(180deg,#f8faff 0%,#f4f6fb 100%)}
[data-testid="stHeader"]{background:rgba(255,255,255,.82);backdrop-filter:blur(14px)}
.block-container{padding-top:1.15rem;padding-bottom:3rem;max-width:1450px}
[data-testid="stSidebar"]{background:linear-gradient(180deg,#102248 0%,#132a55 70%,#1c2f5c 100%);border-right:0}
[data-testid="stSidebar"] *{color:#edf2ff}
[data-testid="stSidebar"] .stRadio label{padding:.35rem .55rem;border-radius:10px}
[data-testid="stSidebar"] .stRadio label:hover{background:rgba(255,255,255,.08)}
.ln-brand{padding:.25rem .15rem 1.25rem}.ln-brand img{width:215px;max-width:95%;filter:brightness(0) invert(1);opacity:.98}
.ln-brand p{margin:.45rem 0 0;color:#b9c5e0!important;line-height:1.45;font-size:.9rem}
.ln-kicker{letter-spacing:.24em;text-transform:uppercase;color:#8b96b0;font-size:.72rem;text-align:center;margin-bottom:.55rem}
.ln-hero h1{font-size:2.35rem;line-height:1.05;color:var(--ln-navy);margin:0 0 .35rem}.ln-gradient{background:linear-gradient(90deg,var(--ln-blue),var(--ln-violet));-webkit-background-clip:text;color:transparent}
.ln-hero p{font-size:1.16rem;color:#344a78;margin:0 0 1rem}.ln-quote{background:#fff;border:1px solid var(--ln-border);border-radius:16px;padding:1rem 1.15rem;box-shadow:0 8px 30px rgba(22,38,77,.06);color:#43557d;font-style:italic}
.ln-card{background:var(--ln-card);border:1px solid var(--ln-border);border-radius:16px;padding:1rem 1rem .9rem;box-shadow:0 8px 28px rgba(30,46,90,.055);min-height:115px}.ln-card .icon{font-size:1.6rem}.ln-card h3{font-size:1rem;margin:.4rem 0 .2rem;color:var(--ln-navy)}.ln-card p{font-size:.86rem;color:var(--ln-muted);margin:0;line-height:1.35}
.ln-section-title{font-size:1.15rem;font-weight:750;color:var(--ln-navy);margin:.35rem 0 .7rem}.ln-panel{background:#fff;border:1px solid var(--ln-border);border-radius:18px;padding:1.1rem 1.15rem;box-shadow:0 7px 28px rgba(32,50,96,.045)}
.ln-small{font-size:.82rem;color:var(--ln-muted)}.ln-pill{display:inline-block;border:1px solid #dbe1f1;border-radius:999px;padding:.25rem .55rem;font-size:.77rem;color:#5c6b8a;background:#f8faff;margin-right:.3rem}
.ln-footer{margin-top:2rem;padding-top:1.1rem;border-top:1px solid var(--ln-border);color:#8b96ad;font-size:.82rem;display:flex;justify-content:space-between;gap:1rem}
.ln-auth{max-width:540px;margin:5vh auto 0;background:#fff;border:1px solid var(--ln-border);border-radius:22px;padding:1.4rem 1.5rem;box-shadow:0 16px 48px rgba(20,39,84,.10)}.ln-auth-logo{text-align:center}.ln-auth-logo img{width:230px}.ln-version{font-size:.78rem;color:#8290ad;text-align:center;margin-top:.25rem}
.ln-update{background:linear-gradient(90deg,#f2f5ff,#f6f1ff);border:1px solid #dfe4ff;border-radius:15px;padding:.9rem 1rem;margin-bottom:1rem}
.ln-admin{background:#fff;border:1px solid #e5e9f3;border-radius:15px;padding:1rem}
div.stButton>button[kind="primary"],div.stDownloadButton>button[kind="primary"]{background:linear-gradient(90deg,var(--ln-blue),var(--ln-violet));border:none;border-radius:11px;font-weight:700;min-height:44px}div.stButton>button,div.stDownloadButton>button{border-radius:11px}
[data-testid="stTextArea"] textarea{border-radius:12px;border-color:#dfe4ef;line-height:1.55}[data-testid="stMetric"]{background:#fff;border:1px solid var(--ln-border);padding:.65rem .8rem;border-radius:12px}hr{border-color:#e9edf5!important}
/* Auth screen */
.ln-auth-shell{max-width:1180px;margin:3.5vh auto 0}.ln-auth-visual{background:linear-gradient(145deg,#102248 0%,#17356d 62%,#5d56e8 145%);border-radius:28px;padding:2.1rem 2.2rem;min-height:590px;box-shadow:0 24px 70px rgba(16,34,72,.20);position:relative;overflow:hidden}.ln-auth-visual:before,.ln-auth-visual:after{content:"";position:absolute;border-radius:999px;filter:blur(2px);opacity:.22}.ln-auth-visual:before{width:330px;height:330px;background:#7c6cff;right:-130px;top:-95px}.ln-auth-visual:after{width:290px;height:290px;background:#4b93ff;left:-145px;bottom:-125px}.ln-auth-visual-inner{position:relative;z-index:1}.ln-auth-visual img{width:220px;filter:brightness(0) invert(1)}.ln-auth-eyebrow{color:#b9c8ec;font-size:.76rem;letter-spacing:.22em;text-transform:uppercase;margin-top:2.7rem}.ln-auth-visual h1{color:white;font-size:2.7rem;line-height:1.06;margin:.6rem 0 .75rem}.ln-auth-visual p{color:#d8e2f8;font-size:1.02rem;line-height:1.55;max-width:540px}.ln-auth-benefit{display:flex;gap:.75rem;align-items:flex-start;background:rgba(255,255,255,.08);border:1px solid rgba(255,255,255,.10);border-radius:15px;padding:.82rem .9rem;margin:.72rem 0;color:#eff4ff}.ln-auth-benefit b{display:block;font-size:.93rem}.ln-auth-benefit span{display:block;color:#c5d2ec;font-size:.82rem;margin-top:.08rem}.ln-auth-note{margin-top:1.2rem;color:#b9c8e8!important;font-size:.8rem!important}.ln-auth-card-head{text-align:center;padding:.45rem 0 .9rem}.ln-auth-card-head img{width:205px}.ln-auth-card-title{font-size:1.55rem;font-weight:800;color:#102047;margin:.35rem 0 .18rem}.ln-auth-card-sub{color:#71809f;font-size:.9rem;margin:0 0 .3rem}.ln-auth-badge{display:inline-block;margin-top:.45rem;padding:.27rem .58rem;border-radius:999px;background:#eef1ff;color:#5a61d7;font-size:.74rem;font-weight:700}.ln-auth-helper{background:#f6f8ff;border:1px solid #e3e8fb;border-radius:13px;padding:.72rem .82rem;color:#667594;font-size:.82rem;margin:.65rem 0 .2rem}.ln-auth-legal{color:#8b96ad;font-size:.75rem;text-align:center;margin-top:.8rem}.ln-auth-success{background:#eefbf5;border:1px solid #d8f3e6;border-radius:13px;padding:.75rem .85rem;color:#24704f;font-size:.86rem}.ln-auth-switch-title{font-size:.83rem;font-weight:700;color:#42547a;margin:.2rem 0 .35rem}.ln-auth-separator{height:1px;background:#e8ecf4;margin:.95rem 0}.stTextInput label p,.stTextArea label p{color:#24375f!important;font-weight:650!important}.stTextInput input{background:#ffffff!important;color:#17264b!important;border:1px solid #d9e0ee!important;border-radius:12px!important;min-height:46px!important;box-shadow:none!important}.stTextInput input:focus{border-color:#6877ef!important;box-shadow:0 0 0 3px rgba(88,104,244,.12)!important}.stTextInput input::placeholder{color:#9ba6bd!important}.stTextInput [data-baseweb="input"]{background:#fff!important}.stTextInput [data-baseweb="base-input"]{background:#fff!important}.stTextInput svg{fill:#657493!important}.stForm{border:0!important;padding:0!important}.stSegmentedControl{width:100%!important}.stSegmentedControl [data-baseweb="button-group"]{background:#f4f6fb;border-radius:12px;padding:4px;width:100%!important}.stSegmentedControl button{border-radius:9px!important;font-weight:700!important;flex:1!important}.stSegmentedControl button[aria-pressed="true"]{background:#fff!important;box-shadow:0 2px 8px rgba(20,37,78,.10)!important;color:#334bd2!important}.ln-auth-mobile{display:none}
@media(max-width:850px){.ln-hero h1{font-size:1.9rem}.block-container{padding-left:1rem;padding-right:1rem}.ln-footer{display:block}.ln-auth-shell{margin-top:.5rem}.ln-auth-visual{min-height:auto;padding:1.35rem;border-radius:20px}.ln-auth-visual h1{font-size:2rem}.ln-auth-eyebrow{margin-top:1.4rem}.ln-auth-benefit{display:none}.ln-auth-note{display:none}.ln-auth-mobile{display:block}.ln-auth-card-head{padding-top:0}.ln-auth-card-head img{width:180px}}
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)


def init_state() -> None:
    defaults: dict[str, Any] = {
        "access_token": "",
        "refresh_token": "",
        "auth_user": None,
        "source_text": "",
        "result_text": "",
        "current_doc_id": None,
        "current_doc_title": "",
        "current_source_type": "text",
        "docx_bytes": None,
        "docx_name": None,
        "docx_storage_path": None,
        "docx_signature": None,
        "research_mode": True,
        "mode": "Académico",
        "level": 2,
        "smart_options": {
            "keep_citations": True,
            "keep_data": True,
            "respect_names": True,
            "improve_connectors": True,
            "avoid_repetition": True,
            "optimize_sentences": True,
        },
        "prefs_loaded": False,
        "last_warning": None,
        "last_save_message": None,
        "last_passes": 0,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


init_state()

SUPABASE_URL = secret("SUPABASE_URL")
SUPABASE_ANON_KEY = secret("SUPABASE_ANON_KEY")
SUPABASE_SERVICE_ROLE_KEY = secret("SUPABASE_SERVICE_ROLE_KEY")


def backend_ready() -> bool:
    return bool(SUPABASE_URL and SUPABASE_ANON_KEY)


def make_user_client():
    return create_client(SUPABASE_URL, SUPABASE_ANON_KEY)


def make_service_client():
    if not SUPABASE_SERVICE_ROLE_KEY:
        raise BackendUnavailable("Falta SUPABASE_SERVICE_ROLE_KEY.")
    return create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)


def reset_auth_state() -> None:
    for key in ["access_token", "refresh_token", "auth_user"]:
        st.session_state[key] = "" if key != "auth_user" else None
    st.session_state.prefs_loaded = False


def setup_required_page() -> None:
    st.markdown(f'<div class="ln-auth"><div class="ln-auth-logo"><img src="{LOGO}"></div>', unsafe_allow_html=True)
    st.markdown("### Configuración inicial necesaria")
    st.info("La interfaz está lista, pero para esta v0.1 persistente debes conectar Supabase antes de permitir usuarios.")
    st.code(
        'SUPABASE_URL = "https://...supabase.co"\n'
        'SUPABASE_ANON_KEY = "..."\n'
        'SUPABASE_SERVICE_ROLE_KEY = "..."\n'
        'ADMIN_EMAILS = "tu-correo@ejemplo.com"\n'
        'OPENAI_API_KEY = "..."\n'
        'OPENAI_MODEL = "gpt-5.6-terra"',
        language="toml",
    )
    st.caption("Ejecuta primero `supabase_setup.sql` en el SQL Editor de tu proyecto y luego agrega estos secretos en Streamlit Cloud.")
    st.markdown('</div>', unsafe_allow_html=True)
    st.stop()


def auth_gate():
    if not backend_ready():
        setup_required_page()

    client = make_user_client()

    # Restore the authenticated Supabase JWT on every Streamlit rerun.
    if st.session_state.access_token and st.session_state.refresh_token:
        try:
            raw_user, session = restore_session(client, st.session_state.access_token, st.session_state.refresh_token)
            if raw_user and session:
                st.session_state.access_token, st.session_state.refresh_token = session_tokens(session)
                st.session_state.auth_user = auth_user_from_supabase(raw_user)
                return client, st.session_state.auth_user
        except Exception:
            reset_auth_state()

    # Two-column access screen. Both login and sign-up remain visible through
    # the selector, avoiding Streamlit tab overflow on narrower displays.
    st.markdown('<div class="ln-auth-shell">', unsafe_allow_html=True)
    visual, access = st.columns([1.08, .92], gap="large", vertical_alignment="top")

    with visual:
        st.markdown(
            f'''<div class="ln-auth-visual"><div class="ln-auth-visual-inner">
                <img src="{LOGO}" alt="Lunova">
                <div class="ln-auth-eyebrow">ESCRIBE · MEJORA · DESTACA</div>
                <h1>Transforma tus ideas.<br>Conserva tu esencia.</h1>
                <p>Un espacio de escritura pensado para revisar, organizar y mejorar textos académicos sin perder tus citas, cifras ni el sentido original.</p>
                <div class="ln-auth-benefit"><div>🎓</div><div><b>Modo Investigación</b><span>Protección especial para citas, referencias y datos.</span></div></div>
                <div class="ln-auth-benefit"><div>📄</div><div><b>Documentos protegidos</b><span>Tus borradores y revisiones se guardan en tu cuenta.</span></div></div>
                <div class="ln-auth-benefit"><div>✨</div><div><b>Revisión por etapas</b><span>Naturalidad, claridad y estructura en un solo proceso.</span></div></div>
                <p class="ln-auth-note">Lunova v{APP_VERSION} · Tus documentos permanecen separados del código de la aplicación.</p>
            </div></div>''',
            unsafe_allow_html=True,
        )

    with access:
        with st.container(border=True):
            st.markdown(
                f'''<div class="ln-auth-card-head">
                    <img src="{LOGO}" alt="Lunova">
                    <div class="ln-auth-card-title">Bienvenido a Lunova</div>
                    <p class="ln-auth-card-sub">Accede a tu espacio de escritura inteligente.</p>
                    <span class="ln-auth-badge">Versión {APP_VERSION}</span>
                </div>''',
                unsafe_allow_html=True,
            )

            if "auth_mode" not in st.session_state:
                st.session_state.auth_mode = "Iniciar sesión"

            selected = st.segmented_control(
                "Acceso",
                ["Iniciar sesión", "Crear cuenta"],
                default=st.session_state.auth_mode,
                key="auth_selector",
                label_visibility="collapsed",
            ) or "Iniciar sesión"
            st.session_state.auth_mode = selected

            if selected == "Iniciar sesión":
                st.markdown('<div class="ln-auth-switch-title">Inicia sesión con tu cuenta</div>', unsafe_allow_html=True)
                with st.form("login_form", clear_on_submit=False):
                    email = st.text_input("Correo electrónico", key="login_email", placeholder="nombre@correo.com")
                    password = st.text_input("Contraseña", type="password", key="login_password", placeholder="Tu contraseña")
                    submitted = st.form_submit_button("Entrar a Lunova", type="primary", use_container_width=True)
                if submitted:
                    if not email.strip() or not password:
                        st.warning("Escribe tu correo y contraseña para continuar.")
                    else:
                        try:
                            response = sign_in(client, email.strip(), password)
                            if not response.session or not response.user:
                                st.error("No se pudo iniciar sesión. Revisa tus datos e inténtalo otra vez.")
                            else:
                                st.session_state.access_token, st.session_state.refresh_token = session_tokens(response.session)
                                user = auth_user_from_supabase(response.user)
                                st.session_state.auth_user = user
                                ensure_profile(client, user)
                                st.rerun()
                        except Exception:
                            st.error("Correo o contraseña incorrectos, o la cuenta todavía no está confirmada.")

                st.markdown('<div class="ln-auth-helper"><b>¿Todavía no tienes cuenta?</b><br>Selecciona <b>Crear cuenta</b> en el control de arriba. La opción siempre permanece visible.</div>', unsafe_allow_html=True)

            else:
                st.markdown('<div class="ln-auth-switch-title">Crea tu cuenta de Lunova</div>', unsafe_allow_html=True)
                with st.form("signup_form", clear_on_submit=False):
                    name = st.text_input("Nombre", key="signup_name", placeholder="Tu nombre")
                    email2 = st.text_input("Correo electrónico", key="signup_email", placeholder="nombre@correo.com")
                    password2 = st.text_input("Contraseña", type="password", key="signup_password", placeholder="Mínimo 8 caracteres", help="Usa al menos 8 caracteres.")
                    password3 = st.text_input("Repetir contraseña", type="password", key="signup_password2", placeholder="Repite tu contraseña")
                    created = st.form_submit_button("Crear mi cuenta", type="primary", use_container_width=True)
                if created:
                    if len(password2) < 8:
                        st.warning("La contraseña debe tener al menos 8 caracteres.")
                    elif password2 != password3:
                        st.warning("Las contraseñas no coinciden.")
                    elif not name.strip() or "@" not in email2:
                        st.warning("Completa tu nombre y escribe un correo válido.")
                    else:
                        try:
                            response = sign_up(client, email2.strip(), password2, name.strip())
                            if response.session and response.user:
                                st.session_state.access_token, st.session_state.refresh_token = session_tokens(response.session)
                                user = auth_user_from_supabase(response.user)
                                st.session_state.auth_user = user
                                ensure_profile(client, user)
                                st.rerun()
                            else:
                                st.markdown('<div class="ln-auth-success"><b>Cuenta creada.</b><br>Revisa tu correo para confirmar la cuenta y luego vuelve a iniciar sesión.</div>', unsafe_allow_html=True)
                        except Exception:
                            st.error("No se pudo crear la cuenta. Verifica el correo o intenta con otro.")

                st.markdown('<div class="ln-auth-helper"><b>¿Ya tienes una cuenta?</b><br>Selecciona <b>Iniciar sesión</b> arriba.</div>', unsafe_allow_html=True)

            st.markdown('<div class="ln-auth-legal">Al continuar, tus documentos se asocian únicamente a tu cuenta de Lunova.</div>', unsafe_allow_html=True)

    st.markdown('</div>', unsafe_allow_html=True)
    st.stop()


CLIENT, USER = auth_gate()
IS_ADMIN = USER.email.lower() in admin_emails()

try:
    ensure_profile(CLIENT, USER)
except Exception:
    pass


def load_preferences_once() -> None:
    if st.session_state.prefs_loaded:
        return
    try:
        prefs = get_preferences(CLIENT, USER.id)
        if prefs:
            st.session_state.mode = prefs.get("mode") or "Académico"
            st.session_state.level = int(prefs.get("level") or 2)
            st.session_state.research_mode = bool(prefs.get("research_mode", True))
            options = prefs.get("options") or {}
            st.session_state.smart_options.update(options)
    except Exception:
        pass
    st.session_state.prefs_loaded = True


load_preferences_once()

try:
    APP_SETTINGS = get_app_settings(CLIENT)
except Exception:
    APP_SETTINGS = {}


def setting_value(key: str, default: Any = None) -> Any:
    value = APP_SETTINGS.get(key, default)
    return default if value is None else value


if bool(setting_value("maintenance_enabled", False)) and not IS_ADMIN:
    st.warning(str(setting_value("maintenance_message", "Lunova está realizando mejoras. Intenta nuevamente más tarde.")), icon="🛠️")
    st.stop()


def top_header(title: str = "Bienvenido a", highlight: str = "Lunova") -> None:
    st.markdown('<div class="ln-kicker">ESCRIBE · MEJORA · DESTACA</div>', unsafe_allow_html=True)
    left, right = st.columns([3.2, 1.4], gap="large")
    with left:
        st.markdown(
            f'<div class="ln-hero"><h1>{title} <span class="ln-gradient">{highlight}</span></h1>'
            '<p>Transforma tus ideas. Conserva tu esencia.</p></div>',
            unsafe_allow_html=True,
        )
    with right:
        st.markdown('<div class="ln-quote">“Una mejor redacción también es una mejor forma de expresar tus ideas.”</div>', unsafe_allow_html=True)


def render_updates() -> None:
    banner = str(setting_value("global_banner", "") or "").strip()
    if banner:
        st.info(banner, icon="📣")
    try:
        announcements = unread_announcements(CLIENT, USER.id)
    except Exception:
        announcements = []
    for item in announcements[:2]:
        st.markdown(
            f'<div class="ln-update"><b>✨ {item.get("title", "Nueva actualización disponible")}</b><br>'
            f'<span class="ln-small">Lunova v{item.get("version", APP_VERSION)}</span><br><br>{item.get("message", "")}</div>',
            unsafe_allow_html=True,
        )
        if st.button("Entendido", key=f"read_{item['id']}"):
            try:
                mark_announcement_read(CLIENT, USER.id, str(item["id"]))
                st.rerun()
            except Exception:
                st.warning("No pude guardar que ya viste este aviso.")


def render_sidebar() -> str:
    with st.sidebar:
        st.markdown(
            f'<div class="ln-brand"><img src="{LOGO}" alt="Lunova"><p>Transforma tus ideas.<br>Conserva tu esencia.</p></div>',
            unsafe_allow_html=True,
        )
        nav = ["Inicio", "Humanizar", "Investigación", "Documentos", "Comparar", "Historial", "Configuración"]
        if IS_ADMIN:
            nav.append("Administración")
        page = st.radio("Navegación", nav, label_visibility="collapsed")
        st.markdown("---")
        st.caption(f"Sesión: {USER.display_name}")
        st.caption(f"Lunova v{APP_VERSION}")
        if secret("OPENAI_API_KEY"):
            st.success("Motor conectado", icon="✅")
        else:
            st.warning("Falta conectar IA", icon="🔌")
        if st.button("Cerrar sesión", use_container_width=True):
            sign_out(CLIENT)
            reset_auth_state()
            st.rerun()
    return page


PAGE = render_sidebar()


def feature_cards() -> None:
    cols = st.columns(4, gap="medium")
    cards = [
        ("✍️", "Humanizar texto", "Redacción más natural, fluida y original."),
        ("📄", "Subir documento", "Trabaja con archivos Word (.docx)."),
        ("🎓", "Modo Investigación", "Pensado para tesis y trabajos académicos."),
        ("✨", "Mejorar redacción", "Claridad, coherencia, conectores y fluidez."),
    ]
    for col, (icon, title, text) in zip(cols, cards):
        with col:
            st.markdown(f'<div class="ln-card"><div class="icon">{icon}</div><h3>{title}</h3><p>{text}</p></div>', unsafe_allow_html=True)


def input_options(force_research: bool = False) -> tuple[str, int, bool, dict[str, bool]]:
    c1, c2 = st.columns([1.2, 1], gap="large")
    with c1:
        mode = st.segmented_control(
            "Tipo de transformación",
            ["Natural", "Académico", "Profundo"],
            default=st.session_state.mode,
            key="mode_control",
        ) or "Académico"
    with c2:
        current = f"{st.session_state.level} · " + {1: "Suave", 2: "Equilibrado", 3: "Profundo"}[st.session_state.level]
        level_label = st.segmented_control(
            "Nivel de modificación",
            ["1 · Suave", "2 · Equilibrado", "3 · Profundo"],
            default=current,
            key="level_control",
        ) or "2 · Equilibrado"
        level = int(level_label[0])

    if force_research:
        research = True
        st.session_state.research_mode = True
    else:
        research = st.toggle(
            "Modo Investigación",
            value=st.session_state.research_mode,
            help="Protege la estructura académica y aplica reglas especiales para investigación.",
        )

    saved = st.session_state.smart_options
    with st.expander("Opciones inteligentes", expanded=True):
        a, b = st.columns(2)
        with a:
            keep_citations = st.checkbox("Mantener citas y referencias", value=bool(saved.get("keep_citations", True)))
            keep_data = st.checkbox("Conservar datos y porcentajes", value=bool(saved.get("keep_data", True)))
            respect_names = st.checkbox("Respetar nombres propios", value=bool(saved.get("respect_names", True)))
        with b:
            improve_connectors = st.checkbox("Mejorar conectores", value=bool(saved.get("improve_connectors", True)))
            avoid_repetition = st.checkbox("Evitar repeticiones", value=bool(saved.get("avoid_repetition", True)))
            optimize_sentences = st.checkbox("Optimizar estructura de oraciones", value=bool(saved.get("optimize_sentences", True)))

    options = {
        "keep_citations": keep_citations,
        "keep_data": keep_data,
        "respect_names": respect_names,
        "improve_connectors": improve_connectors,
        "avoid_repetition": avoid_repetition,
        "optimize_sentences": optimize_sentences,
    }
    st.session_state.mode = mode
    st.session_state.level = level
    st.session_state.research_mode = research
    st.session_state.smart_options = options
    return mode, level, research, options


def auto_title(text: str) -> str:
    clean = " ".join(text.strip().split())
    if not clean:
        return "Documento sin título"
    return (clean[:62] + "…") if len(clean) > 63 else clean


def persist_rewrite(mode: str, level: int, research: bool, options: dict[str, bool], revised: str, passes: int) -> None:
    try:
        doc_id = st.session_state.current_doc_id
        if not doc_id:
            created = create_document(
                CLIENT,
                user_id=USER.id,
                title=st.session_state.current_doc_title or auto_title(st.session_state.source_text),
                original_text=st.session_state.source_text,
                source_type=st.session_state.current_source_type,
                storage_path=st.session_state.docx_storage_path,
            )
            doc_id = str(created["id"])
            st.session_state.current_doc_id = doc_id
            st.session_state.current_doc_title = str(created.get("title") or "Documento")
        score = similarity(st.session_state.source_text, revised)
        save_revision(
            CLIENT,
            document_id=doc_id,
            user_id=USER.id,
            mode=mode,
            level=level,
            research_mode=research,
            original_text=st.session_state.source_text,
            revised_text=revised,
            similarity_score=score,
            passes=passes,
        )
        update_document(CLIENT, doc_id, USER.id, latest_text=revised)
        save_preferences(CLIENT, USER.id, mode, level, research, options)
        st.session_state.last_save_message = "Guardado automáticamente en tu historial."
    except Exception:
        st.session_state.last_save_message = "La revisión se generó, pero no pude guardarla en la nube. No cierres esta página hasta copiarla."




def save_draft() -> None:
    """Persist the text currently in the editor without requiring an AI rewrite."""
    try:
        if not st.session_state.source_text.strip():
            st.warning("No hay texto para guardar.")
            return
        if not st.session_state.current_doc_id:
            created = create_document(
                CLIENT,
                user_id=USER.id,
                title=st.session_state.current_doc_title or auto_title(st.session_state.source_text),
                original_text=st.session_state.source_text,
                source_type=st.session_state.current_source_type,
                storage_path=st.session_state.docx_storage_path,
            )
            st.session_state.current_doc_id = str(created["id"])
            st.session_state.current_doc_title = str(created.get("title") or "Documento")
        else:
            update_document(
                CLIENT,
                st.session_state.current_doc_id,
                USER.id,
                latest_text=st.session_state.source_text,
            )
        st.success("Borrador guardado en tu cuenta.")
    except Exception:
        st.error("No pude guardar el borrador en la nube.")

def run_rewrite(mode: str, level: int, research: bool, options: dict[str, bool]) -> None:
    result = rewrite_text(
        st.session_state.source_text,
        api_key=secret("OPENAI_API_KEY"),
        model=secret("OPENAI_MODEL", "gpt-5.6-terra"),
        mode=mode,
        level=level,
        research_mode=research,
        options=options,
        editorial_instruction=str(setting_value("editorial_instruction", "") or ""),
    )
    st.session_state.result_text = result.text
    st.session_state.last_warning = result.warning
    st.session_state.last_passes = result.passes
    if result.text.strip() and result.text.strip() != st.session_state.source_text.strip() and not result.warning:
        persist_rewrite(mode, level, research, options, result.text, result.passes)


def metrics_panel(text: str) -> None:
    metrics = writing_metrics(text)
    st.markdown('<div class="ln-section-title">📊 Análisis Lunova</div>', unsafe_allow_html=True)
    for label, key in [("Naturalidad", "naturalidad"), ("Claridad", "claridad"), ("Variación estructural", "variacion")]:
        value = int(metrics[key])
        st.write(f"**{label}** · {value}%")
        st.progress(value / 100)
    st.write(f"**Repeticiones** · {metrics['repeticiones']}")
    if st.session_state.last_passes:
        st.caption(f"Pasadas internas realizadas: {st.session_state.last_passes}")
    st.caption("Estos indicadores son heurísticos de redacción; no son un detector de IA ni un informe de plagio.")


def clear_current_document() -> None:
    st.session_state.current_doc_id = None
    st.session_state.current_doc_title = ""
    st.session_state.current_source_type = "text"
    st.session_state.docx_bytes = None
    st.session_state.docx_name = None
    st.session_state.docx_storage_path = None
    st.session_state.docx_signature = None


def process_uploaded_doc(uploaded) -> None:
    data = uploaded.getvalue()
    signature = hashlib.sha256(data).hexdigest()
    if signature == st.session_state.docx_signature:
        return
    extracted, blocks = extract_docx_text(data)
    # Upload first; if storage fails, do not pretend the file is durable.
    path = upload_original_docx(CLIENT, USER.id, uploaded.name, data, DOC_BUCKET)
    created = create_document(
        CLIENT,
        user_id=USER.id,
        title=Path(uploaded.name).stem,
        original_text=extracted,
        source_type="docx",
        storage_path=path,
    )
    st.session_state.docx_bytes = data
    st.session_state.docx_name = uploaded.name
    st.session_state.docx_storage_path = path
    st.session_state.docx_signature = signature
    st.session_state.source_text = extracted
    st.session_state.result_text = ""
    st.session_state.current_doc_id = str(created["id"])
    st.session_state.current_doc_title = str(created.get("title") or Path(uploaded.name).stem)
    st.session_state.current_source_type = "docx"
    st.success(f"Documento guardado en tu cuenta: {blocks} bloques de texto detectados.")


def editor(force_research: bool = False, document_mode: bool = False) -> None:
    st.markdown('<div class="ln-section-title">📝 Editor de texto</div>', unsafe_allow_html=True)

    if document_mode:
        uploaded = st.file_uploader("Subir documento Word", type=["docx"], help="El original se conserva en almacenamiento privado.")
        if uploaded is not None:
            try:
                process_uploaded_doc(uploaded)
            except Exception:
                st.error("No pude guardar o leer ese archivo. Verifica la configuración de Supabase Storage y que sea un .docx válido.")

    if st.session_state.current_doc_id:
        title_cols = st.columns([4, 1])
        with title_cols[0]:
            st.caption(f"Documento activo: **{st.session_state.current_doc_title or 'Sin título'}**")
        with title_cols[1]:
            if st.button("Nuevo texto", use_container_width=True):
                clear_current_document()
                st.session_state.source_text = ""
                st.session_state.result_text = ""
                st.rerun()

    left, right = st.columns([3.2, 1.15], gap="large")
    with left:
        source = st.text_area(
            "Texto original",
            value=st.session_state.source_text,
            height=310,
            placeholder="Pega aquí el texto que deseas mejorar...",
            max_chars=MAX_TEXT_CHARS,
            key="source_editor",
        )
        st.session_state.source_text = source
        st.caption(f"{len(source):,}/{MAX_TEXT_CHARS:,} caracteres")
        mode, level, research, options = input_options(force_research=force_research)
        action_a, action_b = st.columns([1, 2])
        with action_a:
            if st.button("💾 Guardar borrador", use_container_width=True):
                save_draft()
        with action_b:
            if st.button("✨ Mejorar con Lunova", type="primary", use_container_width=True):
                if not source.strip():
                    st.warning("Primero escribe o pega un texto.")
                else:
                    with st.spinner("Lunova está realizando sus pasadas internas de revisión..."):
                        run_rewrite(mode, level, research, options)

        if st.session_state.last_warning:
            st.warning(st.session_state.last_warning)
        if st.session_state.last_save_message:
            st.caption(st.session_state.last_save_message)

    with right:
        metrics_panel(st.session_state.result_text or source)
        st.markdown("#### Protección activa")
        st.markdown('<span class="ln-pill">Citas</span><span class="ln-pill">Cifras</span><span class="ln-pill">Nombres</span>', unsafe_allow_html=True)

    st.markdown("---")
    comparison_block()

    if document_mode and st.session_state.docx_bytes and st.session_state.result_text.strip():
        revised_docx = export_revised_docx(st.session_state.docx_bytes, st.session_state.result_text)
        stem = Path(st.session_state.docx_name or "documento").stem
        st.download_button(
            "📄 Descargar copia Word revisada",
            data=revised_docx,
            file_name=f"{stem}_Lunova.docx",
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            type="primary",
        )


def comparison_block() -> None:
    st.markdown('<div class="ln-section-title">⚖️ Comparación de resultados</div>', unsafe_allow_html=True)
    original = st.session_state.source_text
    revised = st.session_state.result_text
    c1, c2 = st.columns(2, gap="large")
    with c1:
        st.text_area("Texto original", value=original, height=220, disabled=True, key="cmp_original")
    with c2:
        edited = st.text_area("Versión Lunova", value=revised, height=220, key="cmp_revised")
        if edited != revised:
            st.session_state.result_text = edited
    if st.session_state.result_text.strip() and original.strip():
        sim = similarity(original, st.session_state.result_text)
        st.caption(f"Coincidencia textual aproximada entre ambas versiones: **{sim}%**. Solo compara original y revisión; no representa plagio ni similitud con fuentes externas.")
        d1, d2, d3 = st.columns(3)
        with d1:
            st.download_button("⬇️ Guardar TXT", st.session_state.result_text, file_name="version_lunova.txt", mime="text/plain", use_container_width=True)
        with d2:
            if st.button("💾 Guardar edición", use_container_width=True):
                if st.session_state.current_doc_id:
                    try:
                        update_document(CLIENT, st.session_state.current_doc_id, USER.id, latest_text=st.session_state.result_text)
                        st.success("Edición guardada.")
                    except Exception:
                        st.error("No pude guardar la edición.")
                else:
                    st.info("Procesa el texto primero para crear su documento en el historial.")
        with d3:
            if st.button("↩️ Usar como nuevo original", use_container_width=True):
                st.session_state.source_text = st.session_state.result_text
                st.session_state.result_text = ""
                st.rerun()


def home() -> None:
    top_header()
    render_updates()
    feature_cards()
    st.write("")
    editor()


def research_page() -> None:
    top_header("Modo", "Investigación")
    render_updates()
    st.info("Prioriza citas, cifras, coherencia académica y conectores naturales. Lunova no añade fuentes que no existan en el texto.")
    editor(force_research=True)


def open_saved_document(doc: dict[str, Any]) -> None:
    st.session_state.current_doc_id = str(doc["id"])
    st.session_state.current_doc_title = str(doc.get("title") or "Documento")
    st.session_state.current_source_type = str(doc.get("source_type") or "text")
    st.session_state.source_text = str(doc.get("latest_text") or doc.get("original_text") or "")
    st.session_state.result_text = ""
    st.session_state.docx_storage_path = doc.get("storage_path")
    st.session_state.docx_bytes = None
    st.session_state.docx_name = None
    if doc.get("storage_path"):
        try:
            data = download_docx(CLIENT, str(doc["storage_path"]), DOC_BUCKET)
            st.session_state.docx_bytes = data
            st.session_state.docx_name = f"{doc.get('title') or 'documento'}.docx"
            st.session_state.docx_signature = hashlib.sha256(data).hexdigest()
        except Exception:
            pass


def documents_page() -> None:
    top_header("Trabaja con", "Documentos")
    render_updates()
    st.caption("El original queda en almacenamiento privado y las revisiones se guardan aparte, para que una actualización de Lunova no borre el trabajo del usuario.")
    tab_editor, tab_saved = st.tabs(["Subir / editar", "Mis documentos"])
    with tab_editor:
        editor(force_research=True, document_mode=True)
    with tab_saved:
        try:
            docs = list_documents(CLIENT, USER.id)
        except Exception:
            docs = []
            st.error("No pude consultar tus documentos.")
        if not docs:
            st.info("Todavía no tienes documentos guardados.")
        for idx, doc in enumerate(docs):
            title = str(doc.get("title") or "Documento sin título")
            with st.container(border=True):
                c1, c2, c3 = st.columns([4, 1, 1])
                with c1:
                    st.markdown(f"**{title}**")
                    st.caption(f"Tipo: {doc.get('source_type', 'text')} · Actualizado: {str(doc.get('updated_at',''))[:16].replace('T',' ')}")
                with c2:
                    if st.button("Abrir", key=f"open_doc_{idx}", use_container_width=True):
                        open_saved_document(doc)
                        st.rerun()
                with c3:
                    if st.button("Eliminar", key=f"delete_doc_{idx}", use_container_width=True):
                        try:
                            if doc.get("storage_path"):
                                delete_docx(CLIENT, str(doc["storage_path"]), DOC_BUCKET)
                            delete_document(CLIENT, str(doc["id"]), USER.id)
                            if st.session_state.current_doc_id == str(doc["id"]):
                                clear_current_document()
                            st.rerun()
                        except Exception:
                            st.error("No pude eliminar el documento.")


def compare_page() -> None:
    top_header("Compara tus", "Versiones")
    comparison_block()


def history_page() -> None:
    top_header("Historial de", "Revisiones")
    render_updates()
    try:
        history = list_revisions(CLIENT, USER.id)
    except Exception:
        history = []
        st.error("No pude cargar el historial.")
    if not history:
        st.info("Todavía no hay revisiones guardadas.")
        return
    for idx, item in enumerate(history):
        stamp = str(item.get("created_at", ""))[:16].replace("T", " ")
        with st.expander(f"{stamp} · {item.get('mode','')} · nivel {item.get('level','')} · {item.get('passes',0)} pasadas"):
            c1, c2 = st.columns(2)
            with c1:
                st.markdown("**Original**")
                st.write(item.get("original_text", ""))
            with c2:
                st.markdown("**Lunova**")
                st.write(item.get("revised_text", ""))
            st.caption(f"Coincidencia original/revisión: {item.get('similarity_score', 0)}%")
            if st.button("Recuperar esta revisión", key=f"restore_{idx}"):
                st.session_state.source_text = str(item.get("original_text", ""))
                st.session_state.result_text = str(item.get("revised_text", ""))
                st.session_state.current_doc_id = str(item.get("document_id") or "") or None
                st.rerun()


def settings_page() -> None:
    top_header("Configuración de", "Lunova")
    c1, c2 = st.columns(2, gap="large")
    with c1:
        st.markdown("### Tu cuenta")
        profile = get_profile(CLIENT, USER.id) or {}
        with st.form("profile_form"):
            display_name = st.text_input("Nombre visible", value=str(profile.get("display_name") or USER.display_name))
            st.text_input("Correo", value=USER.email, disabled=True)
            save_profile = st.form_submit_button("Guardar perfil")
        if save_profile:
            try:
                update_profile(CLIENT, USER.id, display_name)
                st.session_state.auth_user.display_name = display_name.strip() or USER.display_name
                st.success("Perfil actualizado.")
            except Exception:
                st.error("No pude actualizar el perfil.")
        st.markdown("### Motor")
        if secret("OPENAI_API_KEY"):
            st.success("Motor de IA configurado en el servidor.")
        else:
            st.warning("OPENAI_API_KEY todavía no está configurada.")
        st.caption(f"Modelo: {secret('OPENAI_MODEL', 'gpt-5.6-terra')}")
    with c2:
        st.markdown("### Privacidad y guardado")
        st.markdown(
            "- Tus documentos y revisiones se guardan fuera del código de Lunova.\n"
            "- Las actualizaciones de la aplicación no eliminan tus registros de la base de datos.\n"
            "- Los archivos Word se almacenan en un bucket privado por usuario.\n"
            "- El acceso se limita mediante Row Level Security (RLS)."
        )
        st.markdown("### Principios de Lunova")
        st.markdown(
            "- Mantener significado, datos y citas.\n"
            "- Evitar paráfrasis mecánicas.\n"
            "- Mejorar cohesión y naturalidad.\n"
            "- No prometer evasión de detectores ni sustituir la revisión del autor."
        )


def admin_page() -> None:
    if not IS_ADMIN:
        st.error("No autorizado.")
        return
    top_header("Panel de", "Administración")
    st.warning("Este panel modifica configuración global. La información de usuarios permanece separada del código de la aplicación.", icon="🔐")
    try:
        svc = make_service_client()
    except Exception as exc:
        st.error(str(exc))
        return

    try:
        stats = admin_stats(svc)
        c1, c2, c3 = st.columns(3)
        c1.metric("Usuarios", stats["users"])
        c2.metric("Documentos", stats["documents"])
        c3.metric("Revisiones", stats["revisions"])
    except Exception:
        st.warning("No pude cargar estadísticas.")

    tab_updates, tab_editorial, tab_system = st.tabs(["Avisos", "Editor Lunova", "Sistema"])
    with tab_updates:
        st.markdown(f"### Publicar novedad · v{APP_VERSION}")
        with st.form("announcement_form"):
            title = st.text_input("Título", value="Nueva actualización disponible")
            message = st.text_area("Mensaje para los usuarios", placeholder="Ej.: Mejoramos el modo Investigación y la conservación de citas.")
            publish = st.form_submit_button("Publicar aviso", type="primary")
        if publish:
            if not message.strip():
                st.warning("Escribe el contenido del aviso.")
            else:
                try:
                    admin_publish_announcement(svc, version=APP_VERSION, title=title, message=message)
                    st.success("Aviso publicado. Cada usuario lo verá hasta pulsar “Entendido”.")
                except Exception:
                    st.error("No pude publicar el aviso.")
        st.markdown("#### Avisos existentes")
        try:
            items = admin_list_announcements(svc)
        except Exception:
            items = []
        for idx, item in enumerate(items):
            c1, c2 = st.columns([5, 1])
            with c1:
                status = "Activo" if item.get("active") else "Oculto"
                st.write(f"**{item.get('title')}** · {status}")
                st.caption(str(item.get("message") or ""))
            with c2:
                desired = not bool(item.get("active"))
                if st.button("Ocultar" if not desired else "Activar", key=f"announce_toggle_{idx}"):
                    admin_set_announcement_active(svc, str(item["id"]), desired)
                    st.rerun()

    with tab_editorial:
        st.markdown("### Comportamiento editorial")
        current_instruction = str(setting_value("editorial_instruction", "") or "")
        with st.form("editorial_form"):
            instruction = st.text_area(
                "Instrucción adicional del motor",
                value=current_instruction,
                height=180,
                help="Se agrega al motor sin modificar ni volver a desplegar el código.",
            )
            save_instruction = st.form_submit_button("Guardar instrucción")
        if save_instruction:
            try:
                admin_set_setting(svc, "editorial_instruction", instruction.strip())
                st.success("Instrucción guardada. Se aplicará a nuevas revisiones.")
            except Exception:
                st.error("No pude guardar la instrucción.")
        st.caption("Úsalo para ajustar tono, conectores o criterios académicos. No debe pedir inventar fuentes ni evadir controles académicos.")

    with tab_system:
        st.markdown("### Mensaje global")
        with st.form("banner_form"):
            banner = st.text_input("Banner", value=str(setting_value("global_banner", "") or ""), placeholder="Ej.: Hoy mejoramos el procesamiento de documentos.")
            save_banner = st.form_submit_button("Guardar banner")
        if save_banner:
            admin_set_setting(svc, "global_banner", banner.strip())
            st.success("Banner actualizado.")

        st.markdown("### Modo mantenimiento")
        maintenance_now = bool(setting_value("maintenance_enabled", False))
        with st.form("maintenance_form"):
            enabled = st.toggle("Activar mantenimiento para usuarios", value=maintenance_now)
            message = st.text_input("Mensaje", value=str(setting_value("maintenance_message", "Lunova está realizando mejoras. Intenta nuevamente más tarde.")))
            save_maintenance = st.form_submit_button("Guardar estado")
        if save_maintenance:
            admin_set_setting(svc, "maintenance_enabled", enabled)
            admin_set_setting(svc, "maintenance_message", message)
            st.success("Estado actualizado. Tu cuenta administradora seguirá teniendo acceso.")
        st.info(f"La versión visible continúa siendo **v{APP_VERSION}**. No cambiaremos la numeración hasta que esta base quede aprobada.")


render_updates() if PAGE not in {"Inicio", "Investigación", "Documentos", "Historial", "Administración"} else None

if PAGE == "Inicio":
    home()
elif PAGE == "Humanizar":
    top_header("Mejora tu", "Redacción")
    editor()
elif PAGE == "Investigación":
    research_page()
elif PAGE == "Documentos":
    documents_page()
elif PAGE == "Comparar":
    compare_page()
elif PAGE == "Historial":
    history_page()
elif PAGE == "Configuración":
    settings_page()
else:
    admin_page()

st.markdown(
    f'<div class="ln-footer"><span><b>Lunova</b> · Escritura Inteligente · v{APP_VERSION}</span><span>Ideas más claras para un trabajo mejor construido.</span></div>',
    unsafe_allow_html=True,
)
