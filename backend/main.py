"""LifeBoard's FastAPI application: auth, module/integration registries,
and the API surface documented in docs/ARCHITECTURE.md.

Configuration via environment variables (all optional with sane
defaults for a real Docker deployment; the test suite overrides every
one of them to point at temp dirs):

    LIFEBOARD_SECRET_KEY         (required — no default, fails loudly)
    LIFEBOARD_DATA_DIR           default: backend/data
    LIFEBOARD_MODULES_DIR        default: backend/modules
    LIFEBOARD_INTEGRATIONS_DIR   default: backend/integrations
    LIFEBOARD_LAYOUT_PATH        default: config/dashboard.yaml
"""
import os
import sqlite3
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Response
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from backend.core.auth import AuthStore
from backend.core.crypto import CredentialCipher, DecryptionError
from backend.core.integration_registry import IntegrationRegistry
from backend.core.layout_store import LayoutStore
from backend.core.module_registry import ModuleRegistry
from backend.core.scheduler import IntegrationScheduler

_REPO_ROOT = Path(__file__).resolve().parent.parent
_SESSION_COOKIE_NAME = "lifeboard_session"


class SetupRequest(BaseModel):
    full_name: str
    date_of_birth: str
    email: str
    password: str


class LoginRequest(BaseModel):
    email: str
    password: str
    remember_me: bool = True


class DashboardLayout(BaseModel):
    modules: list[dict]


def create_app() -> FastAPI:
    secret_key = os.environ.get("LIFEBOARD_SECRET_KEY")
    if not secret_key:
        raise RuntimeError(
            "LIFEBOARD_SECRET_KEY is required. Set it in .env (see .env.example)."
        )

    data_dir = Path(os.environ.get("LIFEBOARD_DATA_DIR", _REPO_ROOT / "backend" / "data"))
    modules_dir = Path(os.environ.get("LIFEBOARD_MODULES_DIR", _REPO_ROOT / "backend" / "modules"))
    integrations_dir = Path(
        os.environ.get("LIFEBOARD_INTEGRATIONS_DIR", _REPO_ROOT / "backend" / "integrations")
    )
    layout_path = Path(
        os.environ.get("LIFEBOARD_LAYOUT_PATH", _REPO_ROOT / "config" / "dashboard.yaml")
    )

    data_dir.mkdir(parents=True, exist_ok=True)
    app_db_path = data_dir / "app.db"

    auth_store = AuthStore(app_db_path, secret_key=secret_key)
    cipher = CredentialCipher(secret_key=secret_key)
    layout_store = LayoutStore(layout_path)

    module_registry = ModuleRegistry(modules_dir)
    module_registry.discover()
    integration_registry = IntegrationRegistry(integrations_dir)
    integration_registry.discover()

    def _credentials_db_connection() -> sqlite3.Connection:
        """One shared connection for integration-owned tables and the
        encrypted credentials table. Integrations get this handle in
        sync()/get_data() and own whatever tables they create in it."""
        conn = sqlite3.connect(app_db_path)
        conn.execute(
            "CREATE TABLE IF NOT EXISTS integration_credentials "
            "(integration_id TEXT PRIMARY KEY, encrypted_payload TEXT NOT NULL)"
        )
        conn.execute(
            "CREATE TABLE IF NOT EXISTS integration_sync_status "
            "(integration_id TEXT PRIMARY KEY, last_synced_at TEXT, last_error TEXT)"
        )
        conn.commit()
        return conn

    def _record_sync_result(integration_id: str, success: bool, error_message: str | None) -> None:
        from datetime import datetime, timezone

        conn = _credentials_db_connection()
        if success:
            now = datetime.now(timezone.utc).isoformat()
            conn.execute(
                "INSERT INTO integration_sync_status (integration_id, last_synced_at, last_error) "
                "VALUES (?, ?, NULL) "
                "ON CONFLICT(integration_id) DO UPDATE SET last_synced_at = ?, last_error = NULL",
                (integration_id, now, now),
            )
        else:
            # A failed sync doesn't erase the last successful sync time —
            # only the error message is updated, so the admin panel can
            # show both "last synced 2h ago" and "last error: ...".
            conn.execute(
                "INSERT INTO integration_sync_status (integration_id, last_synced_at, last_error) "
                "VALUES (?, NULL, ?) "
                "ON CONFLICT(integration_id) DO UPDATE SET last_error = ?",
                (integration_id, error_message, error_message),
            )
        conn.commit()
        conn.close()

    def _load_sync_status(integration_id: str) -> dict:
        conn = _credentials_db_connection()
        row = conn.execute(
            "SELECT last_synced_at, last_error FROM integration_sync_status WHERE integration_id = ?",
            (integration_id,),
        ).fetchone()
        conn.close()
        if row is None:
            return {"last_synced_at": None, "last_error": None}
        return {"last_synced_at": row[0], "last_error": row[1]}

    def _require_session(session_token: str | None) -> str:
        if session_token is None:
            raise HTTPException(status_code=401, detail="Not authenticated.")
        email = auth_store.verify_session_token(session_token)
        if email is None:
            raise HTTPException(status_code=401, detail="Invalid or expired session.")
        return email

    def _load_credentials(integration_id: str) -> dict:
        import json

        conn = _credentials_db_connection()
        row = conn.execute(
            "SELECT encrypted_payload FROM integration_credentials WHERE integration_id = ?",
            (integration_id,),
        ).fetchone()
        conn.close()
        if row is None:
            return {}
        try:
            return json.loads(cipher.decrypt(row[0]))
        except DecryptionError:
            return {}

    scheduler = IntegrationScheduler(
        integration_registry=integration_registry,
        load_credentials=_load_credentials,
        open_db=_credentials_db_connection,
        on_sync_result=_record_sync_result,
    )

    @asynccontextmanager
    async def _lifespan(_app: FastAPI):
        scheduler.start()
        # Schedule every integration that already has saved credentials
        # (e.g. restarting the container shouldn't require re-saving
        # credentials to resume scheduled sync).
        for integration_id, manifest in integration_registry.list_integrations().items():
            if _load_credentials(integration_id):
                scheduler.schedule(integration_id, manifest["sync_interval_seconds"])
        yield
        scheduler.shutdown()

    app = FastAPI(title="LifeBoard", lifespan=_lifespan)

    @app.get("/healthz")
    def healthz():
        return {"status": "ok"}

    @app.get("/api/account/status")
    def account_status():
        """Public (no-auth) status check the frontend uses to decide
        whether to show the setup wizard, the login form, or (combined
        with a protected-route 401) redirect an expired session back to
        login. Not part of the documented API surface in
        docs/ARCHITECTURE.md's original table, but required by Phase 2's
        setup -> login -> dashboard flow and the frontend widget
        contract's "a 401 mid-session redirects to /login.html" rule."""
        return {"has_account": auth_store.has_account()}

    @app.post("/api/setup")
    def setup(body: SetupRequest):
        try:
            auth_store.create_account(
                full_name=body.full_name,
                date_of_birth=body.date_of_birth,
                email=body.email,
                password=body.password,
            )
        except AuthStore.AlreadyOnboardedError:
            raise HTTPException(status_code=409, detail="Setup has already been completed.")
        return {"status": "ok"}

    @app.post("/api/login")
    def login(body: LoginRequest, response: Response):
        if not auth_store.verify_login(body.email, body.password):
            raise HTTPException(status_code=401, detail="Invalid email or password.")
        token = auth_store.create_session_token(body.email)
        # remember_me=False sets a session cookie (no max_age — cleared
        # when the browser closes); remember_me=True (default, matches
        # decision 4's "phone home-screen shortcut doesn't re-prompt
        # every time") persists for 30 days, matching the token's own
        # max_age in auth.py.
        cookie_kwargs = {"httponly": True, "samesite": "lax"}
        if body.remember_me:
            cookie_kwargs["max_age"] = 60 * 60 * 24 * 30
        response.set_cookie(_SESSION_COOKIE_NAME, token, **cookie_kwargs)
        return {"status": "ok"}

    @app.post("/api/logout")
    def logout(response: Response):
        response.delete_cookie(_SESSION_COOKIE_NAME)
        return {"status": "ok"}

    @app.get("/api/modules")
    def list_modules():
        result = {}
        for module_id, manifest in module_registry.list_modules().items():
            requires = manifest.get("requires_integration")
            satisfied = requires is None or bool(_load_credentials(requires))
            result[module_id] = {**manifest, "requirement_satisfied": satisfied}
        return result

    @app.get("/api/modules/{module_id}/data")
    def get_module_data(module_id: str):
        db = _credentials_db_connection()
        try:
            return module_registry.get_module_data(module_id, db=db)
        finally:
            db.close()

    @app.get("/api/integrations")
    def list_integrations():
        result = {}
        for integration_id, manifest in integration_registry.list_integrations().items():
            status = _load_sync_status(integration_id)
            result[integration_id] = {
                **manifest,
                "configured": bool(_load_credentials(integration_id)),
                "last_synced_at": status["last_synced_at"],
                "last_error": status["last_error"],
            }
        return result

    @app.post("/api/integrations/{integration_id}/credentials")
    def save_credentials(integration_id: str, credentials: dict):
        import json

        if not integration_registry.test_connection(integration_id, credentials):
            raise HTTPException(status_code=400, detail="Connection test failed.")

        encrypted = cipher.encrypt(json.dumps(credentials))
        conn = _credentials_db_connection()
        conn.execute(
            "INSERT INTO integration_credentials (integration_id, encrypted_payload) "
            "VALUES (?, ?) ON CONFLICT(integration_id) DO UPDATE SET encrypted_payload = ?",
            (integration_id, encrypted, encrypted),
        )
        conn.commit()
        conn.close()

        manifest = integration_registry.list_integrations().get(integration_id)
        if manifest is not None:
            scheduler.schedule(integration_id, manifest["sync_interval_seconds"])
        return {"status": "ok"}

    @app.delete("/api/integrations/{integration_id}/credentials")
    def delete_credentials(integration_id: str):
        conn = _credentials_db_connection()
        conn.execute(
            "DELETE FROM integration_credentials WHERE integration_id = ?",
            (integration_id,),
        )
        conn.commit()
        conn.close()
        scheduler.unschedule(integration_id)
        return {"status": "ok"}

    @app.post("/api/integrations/{integration_id}/sync-now")
    def sync_now(integration_id: str):
        credentials = _load_credentials(integration_id)
        db = _credentials_db_connection()
        try:
            success, error_message = integration_registry.sync(
                integration_id, credentials=credentials, db=db
            )
        finally:
            db.close()
        _record_sync_result(integration_id, success, error_message)
        if not success:
            raise HTTPException(status_code=502, detail=error_message or "Sync failed.")
        return {"status": "ok"}

    @app.get("/api/dashboard")
    def get_dashboard():
        return {"modules": layout_store.load()}

    @app.post("/api/dashboard")
    def save_dashboard(body: DashboardLayout):
        layout_store.save(body.modules)
        return {"status": "ok"}

    # Auth gate: every /api/* route except setup/login/logout requires a
    # valid session. Applied via middleware so each route above stays free
    # of repeated auth boilerplate.
    @app.middleware("http")
    async def require_auth_for_protected_routes(request, call_next):
        public_paths = {
            "/healthz",
            "/api/setup",
            "/api/login",
            "/api/logout",
            "/api/account/status",
        }
        if request.url.path in public_paths or not request.url.path.startswith("/api"):
            return await call_next(request)

        token = request.cookies.get(_SESSION_COOKIE_NAME)
        try:
            _require_session(token)
        except HTTPException as exc:
            from fastapi.responses import JSONResponse

            return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})
        return await call_next(request)

    # Static frontend. No build step (see docs/ARCHITECTURE.md): vanilla
    # JS/CSS served directly. HTML pages are not auth-gated themselves —
    # each page's own JS calls the (auth-gated) API and redirects to
    # /login.html on a 401, per the frontend widget contract.
    frontend_dir = _REPO_ROOT / "frontend"
    if frontend_dir.is_dir():
        app.mount("/src", StaticFiles(directory=frontend_dir / "src"), name="frontend-src")
        app.mount("/icons", StaticFiles(directory=frontend_dir / "icons"), name="frontend-icons")

        @app.get("/manifest.json")
        def manifest_json():
            return FileResponse(frontend_dir / "manifest.json")

        @app.get("/login.html")
        def login_page():
            return FileResponse(frontend_dir / "login.html")

        @app.get("/setup.html")
        def setup_page():
            return FileResponse(frontend_dir / "setup.html")

        @app.get("/admin/integrations.html")
        def admin_integrations_page():
            return FileResponse(frontend_dir / "admin" / "integrations.html")

        @app.get("/")
        def index_page():
            return FileResponse(frontend_dir / "index.html")

    return app
