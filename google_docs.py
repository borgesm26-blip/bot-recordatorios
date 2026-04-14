"""
google_docs.py — Integración con Google Docs para guardar notas.

Todas las notas del usuario se guardan en un documento compartido en Google Docs
que el usuario puede acceder desde cualquier lugar.
"""

import os
import json
import base64
import logging
from typing import Optional
from datetime import datetime

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

logger = logging.getLogger(__name__)

TOKEN_FILE = os.getenv('GOOGLE_TOKEN_FILE', 'token.json')
CREDENTIALS_FILE = os.getenv('GOOGLE_CREDENTIALS_FILE', 'credentials.json')

SCOPES = [
    'https://www.googleapis.com/auth/calendar',
    'https://www.googleapis.com/auth/tasks',
    'https://www.googleapis.com/auth/documents',
    'https://www.googleapis.com/auth/drive',
]


class GoogleDocs:
    """
    Maneja la creación y actualización de documentos en Google Docs.
    Las notas se guardan en un único documento compartido.
    """

    def __init__(self):
        self.creds = None
        self.docs_service = None
        self.drive_service = None
        self.doc_id = None
        self._bootstrap()

    def _bootstrap(self):
        """Carga credenciales desde archivo o variables de entorno."""
        logger.info("=== GoogleDocs._bootstrap() iniciando ===")

        # Opción A: desde variable de entorno base64 (para Railway/cloud)
        self._load_from_env_vars()

        # Opción B: desde archivos locales
        if not self.creds:
            if os.path.exists(TOKEN_FILE):
                logger.info("token.json encontrado, cargando...")
                self._load_from_file()
            else:
                logger.error("token.json NO ENCONTRADO en: %s", TOKEN_FILE)

        if self.creds and self.creds.valid:
            logger.info("Credenciales válidas, construyendo servicios...")
            self._build_services()
            logger.info("Google Docs Services inicializados correctamente.")
        else:
            logger.warning(
                "Google Docs Services NO disponibles. "
                "self.creds=%s, valid=%s",
                self.creds is not None,
                self.creds.valid if self.creds else "N/A"
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
            logger.info("Intentando cargar token.json...")
            self.creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
            logger.info("Token cargado. Valid: %s, Expired: %s", self.creds.valid, self.creds.expired)
            if self.creds.expired and self.creds.refresh_token:
                logger.info("Token expirado, refrescando...")
                self.creds.refresh(Request())
                logger.info("Token de Google refrescado correctamente.")
            logger.info("Credenciales listas. Valid: %s", self.creds.valid)
        except Exception as e:
            logger.error("Error cargando token.json: %s", e)
            import traceback
            logger.error(traceback.format_exc())
            self.creds = None

    def _build_services(self):
        """Construye los servicios de Google Docs y Drive."""
        try:
            self.docs_service = build('docs', 'v1', credentials=self.creds)
            self.drive_service = build('drive', 'v3', credentials=self.creds)
        except Exception as e:
            logger.error("Error construyendo servicios de Docs: %s", e)

    def is_authorized(self) -> bool:
        """Verifica si está autorizado con Google."""
        return self.creds is not None and self.creds.valid

    def get_or_create_notes_doc(self) -> Optional[str]:
        """
        Obtiene o crea el documento de notas.
        Devuelve el ID del documento.
        """
        if not self.is_authorized():
            return None

        try:
            # Buscar documento existente
            results = self.drive_service.files().list(
                q="name='Mis Notas - Cerebrito' and trashed=false",
                spaces='drive',
                fields='files(id, name)',
                pageSize=1
            ).execute()

            files = results.get('files', [])

            if files:
                self.doc_id = files[0]['id']
                logger.info("Documento de notas encontrado: %s", self.doc_id)
                return self.doc_id

            # Si no existe, crear uno nuevo
            file_metadata = {
                'name': 'Mis Notas - Cerebrito',
                'mimeType': 'application/vnd.google-apps.document'
            }

            file = self.drive_service.files().create(
                body=file_metadata, fields='id'
            ).execute()

            self.doc_id = file.get('id')
            logger.info("Documento de notas creado: %s", self.doc_id)

            # Agregar contenido inicial
            self._append_to_doc(
                f"📒 Mis Notas - Cerebrito\n\n"
                f"Creado: {datetime.now().strftime('%d/%m/%Y %H:%M')}\n"
                f"{'='*50}\n\n"
            )

            return self.doc_id

        except HttpError as e:
            logger.error("Error obteniendo/creando documento: %s", e)
            return None

    def add_note(self, title: str, content: str = '') -> bool:
        """
        Agrega una nota al documento de Docs.

        Args:
            title: Título o encabezado de la nota
            content: Contenido de la nota (opcional)

        Returns:
            True si se guardó exitosamente, False si no
        """
        if not self.is_authorized():
            logger.warning("No autorizado para acceder a Google Docs")
            return False

        if not self.doc_id:
            self.get_or_create_notes_doc()

        if not self.doc_id:
            logger.error("No se pudo obtener/crear documento de notas")
            return False

        try:
            # Formato de la nota
            timestamp = datetime.now().strftime('%d/%m/%Y %H:%M')

            note_text = f"\n📌 {title}\n"
            if content:
                note_text += f"   {content}\n"
            note_text += f"   [Guardado: {timestamp}]\n"
            note_text += "-" * 40 + "\n"

            self._append_to_doc(note_text)
            logger.info("Nota agregada a Google Docs: %s", title)
            return True

        except HttpError as e:
            logger.error("Error agregando nota a Docs: %s", e)
            return False

    def _append_to_doc(self, text: str) -> bool:
        """
        Agrega texto al final del documento.
        Método auxiliar privado.
        """
        try:
            # Obtener el documento para encontrar el índice correcto
            doc = self.docs_service.documents().get(
                documentId=self.doc_id
            ).execute()

            # Obtener el índice del final del documento
            # En Google Docs, el índice para inserción debe ser < endIndex
            # Por eso usamos endIndex - 1 para insertar al final
            content = doc.get('body', {}).get('content', [])
            if content:
                end_index = content[-1].get('endIndex', 1)
            else:
                end_index = 1

            # El índice debe ser < endIndex, así que usamos endIndex - 1
            insert_index = max(1, end_index - 1) if end_index > 1 else 1

            logger.info("Document endIndex: %s, insertando en índice: %s", end_index, insert_index)

            # Insertar texto al final
            requests = [
                {
                    'insertText': {
                        'location': {'index': insert_index},
                        'text': text
                    }
                }
            ]

            result = self.docs_service.documents().batchUpdate(
                documentId=self.doc_id,
                body={'requests': requests}
            ).execute()

            logger.info("Texto insertado correctamente: %s", result)
            return True

        except Exception as e:
            logger.error("Error insertando texto en Docs: %s", e)
            import traceback
            logger.error(traceback.format_exc())
            return False

    def get_notes_url(self) -> Optional[str]:
        """
        Devuelve la URL del documento de notas para compartir con el usuario.
        """
        if not self.doc_id:
            self.get_or_create_notes_doc()

        if self.doc_id:
            return f"https://docs.google.com/document/d/{self.doc_id}/edit?usp=sharing"

        return None
