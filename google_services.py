"""
google_services.py — Integración con Google Calendar y Google Tasks.

Flujo de autenticación:
  1. Ejecutar setup_google.py UNA VEZ localmente para generar token.json.
  2. En Railway/cloud, usar la variable GOOGLE_TOKEN_BASE64 con el contenido
     de token.json codificado en base64.
"""

import os
import json
import base64
import logging
from datetime import datetime, timedelta
from typing import Optional, List, Dict

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

logger = logging.getLogger(__name__)

# Permisos que solicitamos a Google
SCOPES = [
    'https://www.googleapis.com/auth/calendar',
    'https://www.googleapis.com/auth/tasks',
    'https://www.googleapis.com/auth/documents',  # Para Google Docs
    'https://www.googleapis.com/auth/drive',       # Para Google Drive
]

CREDENTIALS_FILE = os.getenv('GOOGLE_CREDENTIALS_FILE', 'credentials.json')
TOKEN_FILE        = os.getenv('GOOGLE_TOKEN_FILE', 'token.json')


class GoogleServices:
    """
    Wrapper para Google Calendar, Google Tasks, Google Docs y Google Drive.
    Si las credenciales no están disponibles, los métodos devuelven None/[]
    silenciosamente para no romper el bot.
    """

    def __init__(self):
        self.creds            = None
        self.calendar_service = None
        self.tasks_service    = None
        self.docs_service     = None
        self.drive_service    = None
        self._bootstrap()

    # ─── Autenticación ────────────────────────────────────────────────────────

    def _bootstrap(self):
        """Intenta cargar credenciales desde archivo o variable de entorno."""
        # Opción A: desde variable de entorno base64 (para Railway/cloud)
        self._load_from_env_vars()

        # Opción B: desde archivos locales
        if not self.creds and os.path.exists(TOKEN_FILE):
            self._load_from_file()

        if self.creds and self.creds.valid:
            self._build_services()
            logger.info("Google Services inicializados correctamente.")
        else:
            logger.warning(
                "Google Services no disponibles. "
                "Ejecuta setup_google.py para autenticarte."
            )

    def _load_from_env_vars(self):
        """Carga token desde variables de entorno base64 (para cloud)."""
        token_b64 = os.getenv('GOOGLE_TOKEN_BASE64')
        creds_b64 = os.getenv('GOOGLE_CREDENTIALS_BASE64')

        if creds_b64 and not os.path.exists(CREDENTIALS_FILE):
            try:
                data = json.loads(base64.b64decode(creds_b64).decode())
                with open(CREDENTIALS_FILE, 'w') as f:
                    json.dump(data, f)
                logger.info("credentials.json generado desde variable de entorno.")
            except Exception as e:
                logger.error("Error al decodificar GOOGLE_CREDENTIALS_BASE64: %s", e)

        if token_b64:
            try:
                data = json.loads(base64.b64decode(token_b64).decode())
                with open(TOKEN_FILE, 'w') as f:
                    json.dump(data, f)
                logger.info("token.json generado desde variable de entorno.")
            except Exception as e:
                logger.error("Error al decodificar GOOGLE_TOKEN_BASE64: %s", e)

    def _load_from_file(self):
        """Carga credenciales desde token.json y refresca si expiró."""
        try:
            self.creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
            if self.creds.expired and self.creds.refresh_token:
                self.creds.refresh(Request())
                self._save_token()
                logger.info("Token de Google refrescado.")
        except Exception as e:
            logger.error("Error cargando token.json: %s", e)
            self.creds = None

    def _save_token(self):
        """Persiste las credenciales actuales en token.json."""
        if self.creds:
            with open(TOKEN_FILE, 'w') as f:
                f.write(self.creds.to_json())

    def _build_services(self):
        """Construye los clientes de Calendar, Tasks, Docs y Drive."""
        try:
            self.calendar_service = build('calendar', 'v3', credentials=self.creds)
            self.tasks_service    = build('tasks',    'v1', credentials=self.creds)
            self.docs_service     = build('docs',     'v1', credentials=self.creds)
            self.drive_service    = build('drive',    'v3', credentials=self.creds)
        except Exception as e:
            logger.error("Error construyendo servicios de Google: %s", e)
            self.calendar_service = None
            self.tasks_service    = None
            self.docs_service     = None
            self.drive_service    = None

    def is_authorized(self) -> bool:
        """True si las credenciales están disponibles y válidas."""
        return (
            self.creds is not None
            and self.creds.valid
            and self.calendar_service is not None
        )

    def refresh_if_needed(self):
        """Refresca el token si está por expirar (llamar periódicamente)."""
        if self.creds and self.creds.expired and self.creds.refresh_token:
            try:
                self.creds.refresh(Request())
                self._save_token()
                self._build_services()
            except Exception as e:
                logger.error("Error refrescando token: %s", e)

    # ═══════════════════════════════════════════════════════════════════════════
    # GOOGLE CALENDAR
    # ═══════════════════════════════════════════════════════════════════════════

    def create_event(
        self,
        title: str,
        start_dt: datetime,
        end_dt: datetime = None,
        description: str = '',
        reminder_minutes: int = 60
    ) -> Optional[str]:
        """
        Crea un evento en Google Calendar.
        Devuelve el ID del evento o None si falla.
        """
        if not self.is_authorized():
            return None

        if end_dt is None:
            end_dt = start_dt + timedelta(hours=1)

        tz_name = os.getenv('TIMEZONE', 'America/Bogota')

        # Formatear fechas a ISO 8601 con timezone offset
        def fmt(dt):
            if dt.tzinfo is not None:
                return dt.isoformat()
            # Sin timezone: asumir local
            return dt.isoformat()

        event = {
            'summary':     title,
            'description': description,
            'start': {'dateTime': fmt(start_dt), 'timeZone': tz_name},
            'end':   {'dateTime': fmt(end_dt),   'timeZone': tz_name},
            'reminders': {
                'useDefault': False,
                'overrides': [
                    {'method': 'popup', 'minutes': reminder_minutes},
                    {'method': 'popup', 'minutes': 60 * 24},  # 1 día antes
                ],
            },
        }

        try:
            result = self.calendar_service.events().insert(
                calendarId='primary', body=event
            ).execute()
            logger.info("Evento creado en Calendar: %s", result['id'])
            return result['id']
        except HttpError as e:
            logger.error("Error creando evento en Calendar: %s", e)
            return None

    def create_birthday_event(self, name: str, birth_date_str: str) -> Optional[str]:
        """
        Crea un evento de cumpleaños anual en Google Calendar.
        birth_date_str: 'YYYY-MM-DD'
        """
        if not self.is_authorized():
            return None

        event = {
            'summary': f'🎂 Cumpleaños de {name}',
            'start': {'date': birth_date_str},
            'end':   {'date': birth_date_str},
            'recurrence': ['RRULE:FREQ=YEARLY'],
            'reminders': {
                'useDefault': False,
                'overrides': [
                    {'method': 'popup', 'minutes': 60 * 24 * 7},  # 1 semana antes
                    {'method': 'popup', 'minutes': 60 * 24},       # 1 día antes
                    {'method': 'popup', 'minutes': 0},              # El mismo día
                ],
            },
        }

        try:
            result = self.calendar_service.events().insert(
                calendarId='primary', body=event
            ).execute()
            logger.info("Cumpleaños creado en Calendar: %s", result['id'])
            return result['id']
        except HttpError as e:
            logger.error("Error creando cumpleaños en Calendar: %s", e)
            return None

    def get_upcoming_events(self, max_results: int = 10) -> List[Dict]:
        """Lista los próximos eventos del calendario primario."""
        if not self.is_authorized():
            return []

        try:
            now = datetime.utcnow().isoformat() + 'Z'
            result = self.calendar_service.events().list(
                calendarId='primary',
                timeMin=now,
                maxResults=max_results,
                singleEvents=True,
                orderBy='startTime'
            ).execute()
            return result.get('items', [])
        except HttpError as e:
            logger.error("Error obteniendo eventos: %s", e)
            return []

    def delete_event(self, event_id: str) -> bool:
        """Elimina un evento del calendario."""
        if not self.is_authorized():
            return False
        try:
            self.calendar_service.events().delete(
                calendarId='primary', eventId=event_id
            ).execute()
            return True
        except HttpError as e:
            logger.error("Error eliminando evento: %s", e)
            return False

    # ═══════════════════════════════════════════════════════════════════════════
    # GOOGLE TASKS
    # ═══════════════════════════════════════════════════════════════════════════

    def create_task(
        self,
        title: str,
        notes: str = '',
        due_dt: datetime = None
    ) -> Optional[str]:
        """
        Crea una tarea en Google Tasks (lista por defecto).
        Devuelve el ID de la tarea o None si falla.
        """
        if not self.is_authorized():
            return None

        task = {'title': title, 'notes': notes}
        if due_dt:
            # Google Tasks espera fecha RFC 3339 (UTC)
            task['due'] = due_dt.strftime('%Y-%m-%dT00:00:00.000Z')

        try:
            result = self.tasks_service.tasks().insert(
                tasklist='@default', body=task
            ).execute()
            logger.info("Tarea creada en Tasks: %s", result['id'])
            return result['id']
        except HttpError as e:
            logger.error("Error creando tarea en Tasks: %s", e)
            return None

    def get_pending_tasks(self, max_results: int = 20) -> List[Dict]:
        """Lista tareas pendientes."""
        if not self.is_authorized():
            return []

        try:
            result = self.tasks_service.tasks().list(
                tasklist='@default',
                maxResults=max_results,
                showCompleted=False,
                showHidden=False
            ).execute()
            return result.get('items', [])
        except HttpError as e:
            logger.error("Error obteniendo tareas: %s", e)
            return []

    def complete_task(self, task_id: str) -> bool:
        """Marca una tarea como completada en Google Tasks."""
        if not self.is_authorized():
            return False
        try:
            task = self.tasks_service.tasks().get(
                tasklist='@default', task=task_id
            ).execute()
            task['status'] = 'completed'
            self.tasks_service.tasks().update(
                tasklist='@default', task=task_id, body=task
            ).execute()
            return True
        except HttpError as e:
            logger.error("Error completando tarea: %s", e)
            return False

    def delete_task(self, task_id: str) -> bool:
        """Elimina una tarea de Google Tasks."""
        if not self.is_authorized():
            return False
        try:
            self.tasks_service.tasks().delete(
                tasklist='@default', task=task_id
            ).execute()
            return True
        except HttpError as e:
            logger.error("Error eliminando tarea: %s", e)
            return False
