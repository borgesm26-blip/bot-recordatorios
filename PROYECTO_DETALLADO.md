# 🤖 Proyecto Bot Recordatorios - Guía Completa

## 📋 Resumen del Proyecto

Creamos un **bot de Telegram inteligente** que:
- ✅ Guarda tareas, notas, citas y cumpleaños
- ✅ Sincroniza con Google Calendar, Tasks y Docs
- ✅ Envía recordatorios automáticos 24/7
- ✅ Usa IA (Gemini) para análisis inteligente
- ✅ Corre en la nube (Railway) sin necesidad de tu computadora

---

## 🏗️ FASE 1: DESARROLLO LOCAL

### 1.1 Crear la estructura del proyecto

**Objetivo:** Organizar archivos de código

**Archivos creados:**
- `bot.py` - Código principal del bot (1137+ líneas)
- `db.py` - Gestión de base de datos SQLite
- `google_services.py` - Integración con Google APIs
- `google_docs.py` - Manejo de documentos en Google Docs
- `gemini_helper.py` - Integración con IA Gemini
- `requirements.txt` - Dependencias Python
- `.env` - Variables de entorno (SECRETO)
- `.gitignore` - Archivos que NO subir a GitHub

**Concepto:** Separar el código en módulos hace que sea más fácil de mantener

### 1.2 Instalar dependencias

```bash
pip install python-telegram-bot[job-queue]==20.7
pip install google-auth-oauthlib==1.2.0
pip install google-api-python-client==2.116.0
pip install google-generativeai==0.3.0
pip install dateparser==1.2.0
pip install python-dotenv==1.0.0
```

**Qué hace cada una:**
- `python-telegram-bot`: Comunica con Telegram API
- `google-auth-oauthlib`: Autenticación con Google
- `google-api-python-client`: Acceso a Google Calendar/Tasks
- `google-generativeai`: Acceso a IA Gemini
- `dateparser`: Entiende fechas en español ("mañana a las 9am")
- `python-dotenv`: Lee variables de entorno del `.env`

### 1.3 Configurar Google OAuth 2.0

**Pasos:**
1. Ve a [Google Cloud Console](https://console.cloud.google.com)
2. Crea un proyecto nuevo
3. Activa estas APIs:
   - Google Calendar API
   - Google Tasks API
   - Google Drive API
   - Google Docs API
4. Crea credenciales OAuth 2.0 (Desktop app)
5. Descarga `credentials.json`

**Concepto:** OAuth permite que tu bot acceda a Google en tu nombre, sin guardar contraseña

### 1.4 Configurar variables de entorno

**Archivo: `.env`**
```
TELEGRAM_TOKEN=tu_token_del_botfather
AUTHORIZED_USER_ID=tu_id_de_telegram
TIMEZONE=America/Bogota
REMINDER_MINUTES_BEFORE=60
GOOGLE_CREDENTIALS_FILE=credentials.json
GOOGLE_TOKEN_FILE=token.json
```

**Dónde obtener:**
- `TELEGRAM_TOKEN`: @BotFather en Telegram `/newbot`
- `AUTHORIZED_USER_ID`: @userinfobot en Telegram

### 1.5 Ejecutar localmente

```bash
cd ~/Desktop/bot-recordatorios
python bot.py
```

**Qué sucede:**
1. Lee las variables del `.env`
2. Conecta con Google (abre navegador para autorizar)
3. Crea `token.json` (guarda permisos)
4. Se conecta a Telegram
5. Comienza a escuchar mensajes

**Concepto:** En local, ejecutas el bot en tu terminal. Corre solo mientras ejecutes este comando.

---

## 🔑 FASE 2: INTEGRACIÓN DE GOOGLE

### 2.1 OAuth Flow (autenticación)

**Concepto:** Google necesita confirmar que eres tú

**Proceso:**
1. Bot pide: "Necesito acceso a tu Google"
2. Te redirige a Google (navegador se abre)
3. Aceptas los permisos
4. Google genera `token.json` con permiso permanente

**Por qué es seguro:**
- Nunca guardamos tu contraseña
- Token expira después de un tiempo
- Puedes revocar acceso en cualquier momento

### 2.2 Sincronización de datos

**Qué se sincroniza:**
- **Tareas** → Google Tasks
- **Citas** → Google Calendar
- **Notas** → Google Docs
- **Cumpleaños** → Google Calendar (eventos anuales)

**Flujo:**
1. Usuario crea tarea en Telegram: "Comprar leche - mañana a las 9am"
2. Bot guarda en BD local (SQLite)
3. Bot envía a Google Tasks automáticamente
4. Todo sincronizado

### 2.3 Recordatorios automáticos

**Cómo funciona:**
1. APScheduler verifica cada 60 segundos
2. Busca tareas vencidas en BD
3. Si está próxima (dentro de 60 minutos), envía alerta a Telegram
4. Usuario recibe mensaje: "Recordatorio: Comprar leche a las 9:00am"

**Concepto:** Job Queue = tarea que corre automáticamente en el background

---

## 🤖 FASE 3: INTEGRACIÓN DE GEMINI IA

### 3.1 Obtener API Key

```
Ir a: https://aistudio.google.com/app/apikey
Clic en "+ Create API Key"
Copiar el valor que empieza con "AI..."
Agregar al .env: GEMINI_API_KEY=AIzaSy...
```

**Concepto:** API Key = credencial para acceder a servicios de Google

### 3.2 Tres funcionalidades de IA agregadas

#### 🤖 1. Asistente Inteligente (`/pregunta`)
```
Usuario: /pregunta ¿Qué tareas tengo?
Bot: Procesa con Gemini AI
Respuesta: "Tienes 3 tareas pendientes: comprar leche, llamar a mamá..."
```

**Cómo funciona:**
1. Usuario hace pregunta
2. Bot recopila contexto (tareas, notas, cumpleaños)
3. Envía a Gemini con el contexto
4. Gemini genera respuesta inteligente
5. Bot devuelve respuesta al usuario

#### 📊 2. Análisis de Productividad (`/analizar`)
```
Usuario: /analizar
Bot: Analiza todas tus tareas y notas
Respuesta: "Insights: Tienes muchas tareas de salud pendientes..."
```

#### 🧠 3. Procesamiento de Lenguaje Natural (mejora futura)
```
Permite órdenes complejas: "Recordarme comprar leche mañana a las 9"
Sin necesidad de formato específico
```

### 3.3 Modelo Gemini elegido

```
Intentamos:
❌ gemini-pro (NO existe)
❌ gemini-2.0-flash (Cuota gratuita se agotó rápido)
✅ gemini-1.5-flash (Mejor para plan gratuito)
```

**Concepto:** Diferentes modelos tienen diferentes capacidades y costos

---

## 📤 FASE 4: GITHUB

### 4.1 Crear repositorio

**Comando:**
```bash
git init
```

**Qué hace:** Inicializa Git en la carpeta (crea carpeta `.git`)

**Concepto:** Git = sistema de control de versiones. Guarda historial de cambios.

### 4.2 Configurar Git

```bash
git config --global user.name "Tu Nombre"
git config --global user.email "tu@email.com"
```

**Para qué:** Git necesita saber quién hace cambios

### 4.3 Agregar archivos

```bash
git add .
```

**Qué hace:** Marca todos los archivos para guardar (staging)

**Concepto:** Staging = "preárea" antes de guardar

### 4.4 Hacer commit (guardar cambio)

```bash
git commit -m "Descripción del cambio"
```

**Qué hace:** Guarda snapshot de cambios con mensaje descriptivo

**Ejemplo:**
```bash
git commit -m "Add Gemini AI integration: intelligent assistant, NLP, and analytics"
```

**Concepto:** Commit = snapshot del proyecto en un momento. Puedes volver a versiones anteriores.

### 4.5 Conectar con GitHub

```bash
gh repo create bot-recordatorios --public --source=. --remote=origin --push
```

**Qué hace:**
1. `gh repo create` - Crea repositorio en GitHub
2. `--public` - Visible para todos
3. `--source=.` - Usa archivos actuales
4. `--remote=origin --push` - Conecta y sube código

**Concepto:** GitHub = servidor que guarda tu código en la nube

### 4.6 Subir cambios futuros

```bash
git add .
git commit -m "Descripción"
git push
```

**Qué hace:** Sube cambios locales a GitHub

---

## ☁️ FASE 5: RAILWAY (DESPLIEGUE EN NUBE)

### 5.1 Concepto de Cloud Hosting

**Local (tu computadora):**
- ✅ Bot corre mientras ejecutas `python bot.py`
- ❌ Bot se detiene cuando cierras terminal
- ❌ Bot se detiene cuando apaga computadora
- ❌ No puedes tener comandos 24/7

**Railway (servidor en la nube):**
- ✅ Bot corre 24/7 automáticamente
- ✅ No necesitas tu computadora encendida
- ✅ Acceso desde cualquier lugar
- ✅ Gratis o muy barato

### 5.2 Despliegue en Railway

**Pasos:**
1. Ve a https://railway.app
2. Login con GitHub
3. "Create new project" → "Deploy from GitHub"
4. Selecciona repositorio `bot-recordatorios`
5. Railway clona el código
6. Instala dependencias (del `requirements.txt`)
7. Ejecuta comando del `Procfile`: `python bot.py`
8. ¡Bot corre en Railway! 🎉

**Archivo: `Procfile`**
```
worker: python bot.py
```

**Qué dice:** "Ejecuta este comando en el servidor"

### 5.3 Variables de entorno en Railway

**Por qué necesita variables:**
- Railway no tiene archivo `.env` local
- Las variables se pasan como configuración del proyecto

**Variables agregadas:**
```
TELEGRAM_TOKEN=...
AUTHORIZED_USER_ID=...
TIMEZONE=America/Bogota
GOOGLE_CREDENTIALS_BASE64=...  (credentials.json en base64)
GOOGLE_TOKEN_BASE64=...  (token.json en base64)
GEMINI_API_KEY=...
```

**Por qué Base64:**
- Google requiere archivos JSON
- Variables son texto
- Base64 = convertir binario a texto

**Convertir a Base64:**
```bash
python -c "import base64; print(base64.b64encode(open('credentials.json','rb').read()).decode())"
```

### 5.4 Redeploy

```bash
# Local: cambio código
git add .
git commit -m "Fix: ..."
git push

# En Railway: automáticamente
# Detecta cambios en GitHub
# Redeploy automático
# Bot actualizado en segundos
```

---

## 📊 ESTRUCTURA DE CÓDIGO

### bot.py (Main)
```
Funciones principales:
- cmd_start()          → /start menu
- cmd_tarea()          → /tarea crear tarea
- cmd_nota()           → /nota guardar nota
- cmd_cumple()         → /cumple registro cumpleaños
- cmd_completar()      → /completar marcar tarea hecha
- cmd_limpiar()        → /limpiar eliminar notas
- cmd_analizar()       → /analizar análisis con IA
- cmd_pregunta()       → /pregunta asistente IA
- check_reminders()    → Verifica cada 60s si enviar recordatorio
```

### db.py (Base de datos)
```
Tablas:
- reminders    → tareas con fecha/hora
- notes        → notas personales
- birthdays    → cumpleaños con edades

Métodos principales:
- add_reminder()       → Agregar tarea
- get_pending_reminders() → Tareas próximas
- add_note()           → Guardar nota
- delete_note()        → Eliminar nota
- add_birthday()       → Guardar cumpleaños
```

### google_services.py (APIs de Google)
```
Métodos:
- create_task()        → Crear en Google Tasks
- create_calendar_event() → Crear en Google Calendar
- create_birthday_event() → Crear evento de cumpleaños
```

### google_docs.py (Google Docs)
```
Métodos:
- add_note()           → Agregar nota a Google Doc
- get_or_create_notes_doc() → Obtener/crear doc de notas
```

### gemini_helper.py (IA Gemini)
```
Funciones:
- ask_assistant()      → Responder preguntas
- summarize_tasks()    → Resumir tareas
- analyze_notes()      → Analizar notas
- parse_natural_language() → Procesar órdenes complejas
```

---

## 🖥️ COMANDOS DE TERMINAL - GUÍA COMPLETA

### 📁 NAVEGACIÓN

```bash
pwd
Qué hace: Print Working Directory
Muestra: Carpeta actual donde estás
Ejemplo: /Users/michelleborges/Desktop/bot-recordatorios

cd [ruta]
Qué hace: Change Directory
Cambia a otra carpeta
Ejemplo: cd ~/Desktop/bot-recordatorios

ls
Qué hace: List
Muestra archivos y carpetas
Opciones:
  ls -la      Ver todo (incluyendo ocultos)
  ls -lah     Ver todo con tamaño legible

mkdir [nombre]
Qué hace: Make Directory
Crea carpeta nueva
Ejemplo: mkdir proyecto_nuevo
```

### 📝 ARCHIVOS

```bash
cat [archivo]
Qué hace: Concatenate / Mostrar contenido
Lee archivo completo
Ejemplo: cat bot.py

echo "texto" > archivo.txt
Qué hace: Escribir en archivo
Crea/sobrescribe archivo con texto
Ejemplo: echo "API_KEY=123" > .env

echo "texto" >> archivo.txt
Qué hace: Agregar al archivo (append)
Agrega línea sin borrar contenido
Ejemplo: echo "OTRO_VAR=456" >> .env

cp [origen] [destino]
Qué hace: Copy
Copia archivo
Ejemplo: cp bot.py bot.py.backup

mv [origen] [destino]
Qué hace: Move
Mueve/renombra archivo
Ejemplo: mv bot_viejo.py bot.py

rm [archivo]
Qué hace: Remove
Elimina archivo (⚠️ CUIDADO - es permanente)
Ejemplo: rm archivo_temporal.txt
```

### 🐍 PYTHON

```bash
python --version
Qué hace: Muestra versión de Python instalada

python [archivo.py]
Qué hace: Ejecuta archivo Python
Ejemplo: python bot.py

python -m venv [nombre]
Qué hace: Create Virtual Environment
Crea "ambiente aislado" para proyecto
Ejemplo: python -m venv env

pip install [paquete]
Qué hace: Install Package
Instala librería Python
Ejemplo: pip install python-telegram-bot

pip install -r requirements.txt
Qué hace: Instala todos los paquetes del archivo
Usado para despliegue
```

### 🔧 GIT - LOS MÁS IMPORTANTES

```bash
git init
Qué hace: Initialize repository
Crea carpeta .git (proyecto Git)
Se hace UNA sola vez por proyecto

git status
Qué hace: Ver estado actual
Muestra: archivos nuevos, modificados, borrados
Úsalo ANTES de cada commit para verificar

git add [archivo]
Qué hace: Agregar archivo al staging
Marca archivo para guardar
Ejemplo: git add bot.py

git add .
Qué hace: Agregar TODOS los archivos
Marca todos los cambios para guardar
⚠️ Verifica con `git status` primero

git commit -m "mensaje"
Qué hace: Guardar snapshot
Crea versión del proyecto con mensaje
Ejemplo: git commit -m "Add authentication"
Importante: Mensaje debe ser descriptivo

git log
Qué hace: Ver historial de commits
Muestra todos los cambios hechos
Formato: autor, fecha, mensaje

git push
Qué hace: Subir a GitHub
Envía commits locales a servidor
Necesita: estar conectado con GitHub

git pull
Qué hace: Descargar de GitHub
Obtiene cambios del servidor
Útil si trabajas en equipo

git remote -v
Qué hace: Ver URL del servidor
Muestra dónde va el `git push`

git branch
Qué hace: Ver ramas (branches)
Por defecto: main (rama principal)
```

### 📦 GIT + GITHUB

```bash
gh auth login
Qué hace: Conectar con GitHub
Abre navegador para autorizar
Se hace UNA sola vez

gh repo create [nombre] --public --source=. --push
Qué hace: Crear repo en GitHub y subir código
Todo en un comando
Más fácil que `git remote add` + `git push`

git remote remove origin
Qué hace: Quitar conexión a servidor
Se usa cuando hay error de conexión
Luego: `gh repo create` de nuevo
```

### 🚀 RAILWAY

```bash
# Para loguearse desde terminal
heroku login
# o
railway login

# Después, el redeploy es automático
# Solo: git push
# Railway ve los cambios en GitHub
# Y redeploy automáticamente
```

### 🔌 UTILIDADES

```bash
clear
Qué hace: Limpiar pantalla
Borra toda la salida anterior
Mejora legibilidad

which [programa]
Qué hace: ¿Dónde está?
Encuentra ubicación de programa
Ejemplo: which python

grep [texto] [archivo]
Qué hace: Buscar texto en archivo
Muestra líneas que coinciden
Ejemplo: grep "TELEGRAM_TOKEN" bot.py

find [carpeta] -name "[patrón]"
Qué hace: Buscar archivos
Por nombre en toda carpeta
Ejemplo: find . -name "*.py"
```

---

## 🎯 FLUJO TÍPICO DE TRABAJO

### Después de escribir código:

```bash
# 1. Ver qué cambió
git status

# 2. Revisar cambios específicos
git diff bot.py

# 3. Agregar todos los cambios
git add .

# 4. Guardar con descripción
git commit -m "Add feature X"

# 5. Subir a GitHub
git push

# 6. Railway automáticamente redeploya
# (puedes ver logs en https://railway.app)
```

---

## 💡 CONCEPTOS CLAVE

### Variables de Entorno
**Qué son:** Configuración que el programa lee
**Por qué:** No guardar secretos en código

```bash
# Crear
export TELEGRAM_TOKEN="12345"

# Leer desde Python
import os
token = os.getenv('TELEGRAM_TOKEN')
```

### Base de Datos (SQLite)
**Qué es:** Archivo `.db` que guarda datos
**Por qué:** Persistencia local (no se pierde al cerrar bot)

**Tablas:**
- `reminders` → tareas con fecha
- `notes` → notas personales
- `birthdays` → cumpleaños

### OAuth 2.0
**Qué es:** Autorización segura sin contraseñas
**Flujo:**
1. App pide permiso a Google
2. Tú aceptas en navegador
3. Google da token de acceso
4. App usa token (no necesita contraseña)

### Job Queue (APScheduler)
**Qué es:** Tareas que corren automáticamente
**Por qué:** Verificar recordatorios cada 60 segundos sin que usuario lo pida

```python
app.job_queue.run_repeating(
    check_reminders,  # función a ejecutar
    interval=60,      # cada 60 segundos
    first=10          # primera ejecución en 10 segundos
)
```

---

## 📚 RESUMEN FINAL

### Lo que construimos:
✅ Bot inteligente con IA
✅ Sincronización con Google
✅ Recordatorios automáticos
✅ Despliegue en nube (24/7)
✅ Código versionado (GitHub)

### Tecnologías usadas:
- **Python** - Lenguaje de programación
- **Telegram Bot API** - Comunicación con Telegram
- **Google APIs** - Calendar, Tasks, Docs, Drive
- **Google Gemini** - IA generativa
- **SQLite** - Base de datos
- **Git/GitHub** - Control de versiones
- **Railway** - Cloud hosting

### Próximas mejoras (opcionales):
- Procesamiento de lenguaje natural mejorado
- Interfaz web (dashboard)
- Notificaciones vía email
- Integración con Slack
- Más modelos de IA

---

## 🆘 TROUBLESHOOTING COMÚN

| Problema | Solución |
|----------|----------|
| `ModuleNotFoundError` | `pip install -r requirements.txt` |
| Bot no responde en Telegram | Verificar `TELEGRAM_TOKEN` en `.env` |
| Google no se conecta | Ejecutar `python setup_google.py` |
| Railway muestra error | Ver logs: `railway logs` o panel web |
| `git push` falla | `git pull` primero, resolver conflictos |
| Gemini no genera respuesta | Esperar 10-15 min para reinicio de cuota |

---

**¡Felicidades! 🎉 Construiste un bot profesional con IA.**

