"""
setup_google.py — Script de configuración inicial para Google OAuth.

Ejecuta este script UNA SOLA VEZ en tu computadora para autenticar
el bot con tu cuenta de Google.

Uso:
    python setup_google.py

Resultado:
    Genera el archivo token.json con tus credenciales de acceso.
    Ese archivo se usa en el bot y también en Railway (como base64).
"""

import os
import sys
import json
import base64
from pathlib import Path

from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

SCOPES = [
    'https://www.googleapis.com/auth/calendar',
    'https://www.googleapis.com/auth/tasks',
    'https://www.googleapis.com/auth/documents',  # Para Google Docs
    'https://www.googleapis.com/auth/drive',       # Para Google Drive
]

CREDENTIALS_FILE = 'credentials.json'
TOKEN_FILE       = 'token.json'


def setup():
    print("=" * 60)
    print("  Configuración de Google para el Bot de Recordatorios")
    print("=" * 60)
    print()

    # Verificar que existe credentials.json
    if not Path(CREDENTIALS_FILE).exists():
        print("❌ ERROR: No se encontró el archivo 'credentials.json'.")
        print()
        print("Sigue estos pasos para obtenerlo:")
        print()
        print("  1. Ve a https://console.cloud.google.com/")
        print("  2. Crea un proyecto nuevo (ej: 'bot-recordatorios')")
        print("  3. Menú → APIs y servicios → Biblioteca")
        print("     - Busca 'Google Calendar API' → Activar")
        print("     - Busca 'Google Tasks API'    → Activar")
        print("     - Busca 'Google Docs API'     → Activar")
        print("     - Busca 'Google Drive API'    → Activar")
        print("  4. Menú → APIs y servicios → Credenciales")
        print("     - Clic en '+ Crear credenciales' → 'ID de cliente OAuth'")
        print("     - Tipo de aplicación: 'Aplicación de escritorio'")
        print("     - Nombre: 'Bot Recordatorios' → Crear")
        print("  5. Descarga el JSON → renómbralo 'credentials.json'")
        print("     y colócalo en esta carpeta.")
        print()
        print("Luego vuelve a ejecutar: python setup_google.py")
        sys.exit(1)

    print("✅ credentials.json encontrado.")
    print()

    creds = None

    # Si ya existe un token válido, verificarlo
    if Path(TOKEN_FILE).exists():
        try:
            creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
            if creds.expired and creds.refresh_token:
                print("🔄 Token expirado. Refrescando...")
                creds.refresh(Request())
                with open(TOKEN_FILE, 'w') as f:
                    f.write(creds.to_json())
                print("✅ Token refrescado correctamente.")
        except Exception as e:
            print(f"⚠️  Error con el token existente: {e}")
            creds = None

    if not creds or not creds.valid:
        print("🌐 Abriendo el navegador para autenticarte con Google...")
        print("   (Si no se abre automáticamente, copia la URL que aparezca)")
        print()

        flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
        creds = flow.run_local_server(
            port=0,
            prompt='consent',
            success_message=(
                '✅ ¡Autenticación exitosa! Puedes cerrar esta ventana y '
                'volver al terminal.'
            ),
        )

        # Guardar token
        with open(TOKEN_FILE, 'w') as f:
            f.write(creds.to_json())

        print()
        print("✅ token.json generado correctamente.")

    print()
    print("=" * 60)
    print("  Autenticación completada")
    print("=" * 60)
    print()
    print("Para usar el bot LOCALMENTE:")
    print("  Simplemente ejecuta: python bot.py")
    print()
    print("Para desplegar en Railway (cloud gratuito):")
    print("-" * 60)

    # Generar versión base64 para Railway
    with open(TOKEN_FILE, 'rb') as f:
        token_b64 = base64.b64encode(f.read()).decode()

    with open(CREDENTIALS_FILE, 'rb') as f:
        creds_b64 = base64.b64encode(f.read()).decode()

    print()
    print("Agrega estas variables de entorno en Railway:")
    print()
    print("  Variable: GOOGLE_TOKEN_BASE64")
    print(f"  Valor:    {token_b64[:60]}...")
    print()
    print("  Variable: GOOGLE_CREDENTIALS_BASE64")
    print(f"  Valor:    {creds_b64[:60]}...")
    print()

    # Guardar en archivo para fácil copia
    output_file = 'railway_env_vars.txt'
    with open(output_file, 'w') as f:
        f.write("# Variables de entorno para Railway\n")
        f.write("# Copia cada valor completo en las variables de entorno de Railway\n\n")
        f.write(f"GOOGLE_TOKEN_BASE64={token_b64}\n\n")
        f.write(f"GOOGLE_CREDENTIALS_BASE64={creds_b64}\n")

    print(f"📄 Los valores completos están guardados en: {output_file}")
    print("   (¡No subas este archivo a GitHub!)")
    print()
    print("✅ ¡Todo listo! Consulta SETUP.md para el siguiente paso: Railway.")
    print()


if __name__ == '__main__':
    setup()
