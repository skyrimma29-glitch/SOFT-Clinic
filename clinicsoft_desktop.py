"""Desktop launcher for ClinicSoft.

Starts Django locally and displays it in a native WebView2 window.
"""
from __future__ import annotations

import os
import socket
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
import ctypes
import base64


HOST = "127.0.0.1"
DB_NAME = "soft_clinic_db"
DB_USER = "postgres"
DB_HOST = "127.0.0.1"
DB_PORT = "5432"


def set_console_visible(visible):
    if sys.platform != "win32":
        return
    console_window = ctypes.windll.kernel32.GetConsoleWindow()
    if console_window:
        ctypes.windll.user32.ShowWindow(console_window, 5 if visible else 0)


class DesktopApi:
    def __init__(self):
        self.console_visible = False

    def toggle_console(self):
        self.console_visible = not self.console_visible
        set_console_visible(self.console_visible)
        return self.console_visible

    def save_export(self, filename, content_base64):
        import webview

        selected_path = webview.windows[0].create_file_dialog(
            webview.SAVE_DIALOG,
            save_filename=filename,
            file_types=('Excel files (*.xlsx)',),
        )
        if not selected_path:
            return False
        if isinstance(selected_path, (list, tuple)):
            selected_path = selected_path[0]
        with open(selected_path, 'wb') as export_file:
            export_file.write(base64.b64decode(content_base64))
        return True


def project_dir():
    if getattr(sys, "frozen", False):
        return getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
    return os.path.dirname(os.path.abspath(__file__))


def available_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind((HOST, 0))
        return sock.getsockname()[1]


def wait_for_server(url, timeout=30):
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=1) as response:
                if response.status < 500:
                    return
        except (OSError, urllib.error.URLError):
            time.sleep(0.2)
    raise RuntimeError("ClinicSoft no pudo iniciar el servidor local.")


def ensure_database_ready():
    """Verifica que PostgreSQL esté disponible y prepara la base de datos de la app."""
    try:
        import psycopg
    except ModuleNotFoundError:
        try:
            import psycopg2 as psycopg
        except ModuleNotFoundError as exc:
            raise RuntimeError("Falta psycopg/psycopg2 para conectar a PostgreSQL.") from exc
    except ImportError as exc:
        raise RuntimeError("Falta psycopg/psycopg2 para conectar a PostgreSQL.") from exc

    conn = None
    try:
        conn = psycopg.connect(
            dbname="postgres",
            user=DB_USER,
            host=DB_HOST,
            port=DB_PORT,
            password="Wnjr9367",
        )
        conn.autocommit = True
        with conn.cursor() as cur:
            cur.execute(
                "SELECT 1 FROM pg_database WHERE datname = %s;",
                (DB_NAME,),
            )
            exists = cur.fetchone()
            if not exists:
                subprocess.run(
                    ["createdb", "-h", DB_HOST, "-U", DB_USER, "-p", DB_PORT, DB_NAME],
                    check=True,
                    env={**os.environ, "PGPASSWORD": "Wnjr9367"},
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
    except Exception as exc:
        raise RuntimeError(
            "No se pudo conectar a PostgreSQL. Instale PostgreSQL y cree la base soft_clinic_db antes de abrir ClinicSoft."
        ) from exc
    finally:
        if conn is not None:
            conn.close()

    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")
    os.environ.setdefault("DJANGO_ALLOW_ASYNC_UNSAFE", "true")

    import django
    django.setup()

    from django.core.management import call_command
    call_command("migrate", interactive=False, verbosity=0)


def start_server(port):
    os.chdir(project_dir())
    ensure_database_ready()

    import django
    django.setup()

    from waitress import serve
    from core.wsgi import application
    serve(application, host=HOST, port=port, threads=4)


def main():
    import webview

    set_console_visible(False)
    api = DesktopApi()
    port = available_port()
    url = f"http://{HOST}:{port}/"
    server = threading.Thread(target=start_server, args=(port,), daemon=True)
    server.start()
    wait_for_server(url)
    webview.create_window(
        "ClinicSoft-IPS",
        url,
        js_api=api,
        width=1440,
        height=900,
        min_size=(1024, 680),
        resizable=True,
    )
    webview.start(gui="edgechromium")


if __name__ == "__main__":
    main()
