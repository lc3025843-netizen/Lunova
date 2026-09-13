"""Supabase-backed authentication and persistence for Lunova.

The browser-facing client uses the anon key plus the signed-in user's JWT, so
Postgres RLS remains the primary data boundary. A service-role client is only
used for administrator operations and never sent to the browser.
"""
from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4


@dataclass
class AuthUser:
    id: str
    email: str
    display_name: str


class BackendUnavailable(RuntimeError):
    pass


def create_client(url: str, key: str):
    if not url or not key:
        raise BackendUnavailable("Supabase no está configurado.")
    try:
        from supabase import create_client as _create_client
    except ImportError as exc:
        raise BackendUnavailable("Falta instalar el paquete supabase.") from exc
    return _create_client(url, key)


def restore_session(client, access_token: str, refresh_token: str):
    """Restore/refresh a Supabase session and return (user, session)."""
    response = client.auth.set_session(access_token, refresh_token)
    user_resp = client.auth.get_user()
    user = getattr(user_resp, "user", None)
    session = getattr(response, "session", None)
    return user, session


def sign_in(client, email: str, password: str):
    return client.auth.sign_in_with_password({"email": email.strip(), "password": password})


def sign_up(client, email: str, password: str, display_name: str):
    return client.auth.sign_up(
        {
            "email": email.strip(),
            "password": password,
            "options": {"data": {"display_name": display_name.strip()}},
        }
    )


def sign_out(client) -> None:
    try:
        client.auth.sign_out()
    except Exception:
        pass


def session_tokens(session) -> tuple[str, str]:
    return str(session.access_token), str(session.refresh_token)


def auth_user_from_supabase(user) -> AuthUser:
    metadata = getattr(user, "user_metadata", {}) or {}
    email = str(getattr(user, "email", "") or "")
    name = str(metadata.get("display_name") or email.split("@")[0] or "Usuario")
    return AuthUser(id=str(user.id), email=email, display_name=name)


def ensure_profile(client, user: AuthUser) -> None:
    payload = {
        "id": user.id,
        "email": user.email,
        "display_name": user.display_name,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    client.table("profiles").upsert(payload).execute()


def get_profile(client, user_id: str) -> dict[str, Any] | None:
    response = client.table("profiles").select("*").eq("id", user_id).limit(1).execute()
    rows = response.data or []
    return rows[0] if rows else None


def update_profile(client, user_id: str, display_name: str) -> None:
    client.table("profiles").update(
        {
            "display_name": display_name.strip(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
    ).eq("id", user_id).execute()


def get_preferences(client, user_id: str) -> dict[str, Any]:
    response = client.table("preferences").select("*").eq("user_id", user_id).limit(1).execute()
    rows = response.data or []
    return rows[0] if rows else {}


def save_preferences(client, user_id: str, mode: str, level: int, research_mode: bool, options: dict[str, bool]) -> None:
    client.table("preferences").upsert(
        {
            "user_id": user_id,
            "mode": mode,
            "level": int(level),
            "research_mode": bool(research_mode),
            "options": options,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
    ).execute()


def create_document(
    client,
    *,
    user_id: str,
    title: str,
    original_text: str,
    source_type: str = "text",
    storage_path: str | None = None,
) -> dict[str, Any]:
    response = client.table("documents").insert(
        {
            "user_id": user_id,
            "title": title.strip() or "Documento sin título",
            "source_type": source_type,
            "original_text": original_text,
            "latest_text": original_text,
            "storage_path": storage_path,
        }
    ).execute()
    return (response.data or [])[0]


def update_document(client, document_id: str, user_id: str, *, latest_text: str | None = None, title: str | None = None) -> None:
    payload: dict[str, Any] = {"updated_at": datetime.now(timezone.utc).isoformat()}
    if latest_text is not None:
        payload["latest_text"] = latest_text
    if title is not None:
        payload["title"] = title.strip() or "Documento sin título"
    client.table("documents").update(payload).eq("id", document_id).eq("user_id", user_id).execute()


def delete_document(client, document_id: str, user_id: str) -> None:
    # Database row deletion cascades to revisions. Storage deletion is separate and optional.
    client.table("documents").delete().eq("id", document_id).eq("user_id", user_id).execute()


def list_documents(client, user_id: str, limit: int = 50) -> list[dict[str, Any]]:
    response = (
        client.table("documents")
        .select("id,title,source_type,storage_path,created_at,updated_at,latest_text,original_text")
        .eq("user_id", user_id)
        .order("updated_at", desc=True)
        .limit(limit)
        .execute()
    )
    return list(response.data or [])


def get_document(client, document_id: str, user_id: str) -> dict[str, Any] | None:
    response = client.table("documents").select("*").eq("id", document_id).eq("user_id", user_id).limit(1).execute()
    rows = response.data or []
    return rows[0] if rows else None


def save_revision(
    client,
    *,
    document_id: str,
    user_id: str,
    mode: str,
    level: int,
    research_mode: bool,
    original_text: str,
    revised_text: str,
    similarity_score: int,
    passes: int,
) -> dict[str, Any]:
    response = client.table("revisions").insert(
        {
            "document_id": document_id,
            "user_id": user_id,
            "mode": mode,
            "level": int(level),
            "research_mode": bool(research_mode),
            "original_text": original_text,
            "revised_text": revised_text,
            "similarity_score": int(similarity_score),
            "passes": int(passes),
        }
    ).execute()
    return (response.data or [])[0]


def list_revisions(client, user_id: str, limit: int = 50) -> list[dict[str, Any]]:
    response = (
        client.table("revisions")
        .select("id,document_id,mode,level,research_mode,original_text,revised_text,similarity_score,passes,created_at")
        .eq("user_id", user_id)
        .order("created_at", desc=True)
        .limit(limit)
        .execute()
    )
    return list(response.data or [])


def upload_original_docx(client, user_id: str, filename: str, file_bytes: bytes, bucket: str) -> str:
    safe_name = "".join(ch for ch in filename if ch.isalnum() or ch in "._-") or "documento.docx"
    path = f"{user_id}/{uuid4().hex}_{safe_name}"
    client.storage.from_(bucket).upload(
        path=path,
        file=BytesIO(file_bytes),
        file_options={
            "content-type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "upsert": "false",
        },
    )
    return path


def download_docx(client, path: str, bucket: str) -> bytes:
    return client.storage.from_(bucket).download(path)


def delete_docx(client, path: str, bucket: str) -> None:
    if path:
        client.storage.from_(bucket).remove([path])


def unread_announcements(client, user_id: str) -> list[dict[str, Any]]:
    published = (
        client.table("announcements")
        .select("id,version,title,message,published_at")
        .eq("active", True)
        .order("published_at", desc=True)
        .limit(10)
        .execute()
    ).data or []
    if not published:
        return []
    reads = client.table("announcement_reads").select("announcement_id").eq("user_id", user_id).execute().data or []
    read_ids = {str(row["announcement_id"]) for row in reads}
    return [row for row in published if str(row["id"]) not in read_ids]


def mark_announcement_read(client, user_id: str, announcement_id: str) -> None:
    client.table("announcement_reads").upsert(
        {"user_id": user_id, "announcement_id": announcement_id}
    ).execute()


def get_app_settings(client) -> dict[str, Any]:
    response = client.table("app_settings").select("key,value").execute()
    return {row["key"]: row.get("value") for row in (response.data or [])}


# ----------------------- administrator/service-role operations -----------------------

def admin_stats(service_client) -> dict[str, int]:
    stats: dict[str, int] = {}
    for table, key in [("profiles", "users"), ("documents", "documents"), ("revisions", "revisions")]:
        response = service_client.table(table).select("id", count="exact").limit(1).execute()
        stats[key] = int(response.count or 0)
    return stats


def admin_publish_announcement(service_client, *, version: str, title: str, message: str) -> None:
    service_client.table("announcements").insert(
        {"version": version, "title": title.strip(), "message": message.strip(), "active": True}
    ).execute()


def admin_list_announcements(service_client, limit: int = 30) -> list[dict[str, Any]]:
    response = (
        service_client.table("announcements")
        .select("*")
        .order("published_at", desc=True)
        .limit(limit)
        .execute()
    )
    return list(response.data or [])


def admin_set_announcement_active(service_client, announcement_id: str, active: bool) -> None:
    service_client.table("announcements").update({"active": bool(active)}).eq("id", announcement_id).execute()


def admin_set_setting(service_client, key: str, value: Any) -> None:
    service_client.table("app_settings").upsert(
        {"key": key, "value": value, "updated_at": datetime.now(timezone.utc).isoformat()}
    ).execute()
