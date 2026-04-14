# Guía de Instalación — Bot de Recordatorios Personales

Tiempo estimado de configuración: **20–30 minutos** (una sola vez).

---

## Requisitos previos

Necesitas tener instalado en tu computadora:

- **Python 3.10 o superior** — [descargar aquí](https://www.python.org/downloads/)
- **Git** — [descargar aquí](https://git-scm.com/downloads/)
- Una cuenta de **Google** (Gmail)
- Una cuenta en **Railway** (gratuita) — [railway.app](https://railway.app)

---

## PASO 1 — Crear el bot en Telegram

1. Abre Telegram y busca **@BotFather**.
2. Envíale el mensaje: `/newbot`
3. Sigue las instrucciones: elige un nombre y un nombre de usuario (ej: `MisRecordatorios_bot`).
4. BotFather te dará un **token** como este:
   ```
   123456789:ABCdefGHIjklMNOpqrSTUvwxYZ
   ```
   Guárdalo, lo necesitarás más adelante.

5. Para obtener tu **ID de usuario de Telegram**:
   - Busca **@userinfobot** en Telegram
   - Envíale `/start`
   - Te responderá con tu ID (un número como `987654321`)

---

## PASO 2 — Configurar Google Cloud Console

### 2.1 Crear un proyecto

1. Ve a [console.cloud.google.com](https://console.cloud.google.com/)
2. Haz clic en el selector de proyectos (arriba a la izquierda) → **"Nuevo proyecto"**
3. Nombre: `bot-recordatorios` → **Crear**
4. Selecciona el proyecto recién creado.

### 2.2 Activar APIs

1. Menú de la izquierda → **"APIs y servicios"** → **"Biblioteca"**
2. Busca **"Google Calendar API"** → haz clic → **Habilitar**
3. Vuelve a la biblioteca → busca **"Google Tasks API"** → **Habilitar**

### 2.3 Crear credenciales OAuth

1. Menú → **"APIs y servicios"** → **"Credenciales"**
2. Clic en **"+ Crear credenciales"** → **"ID de cliente de OAuth"**
3. Si te pide configurar la pantalla de consentimiento:
   - Tipo de usuario: **"Externo"** → Crear
   - Nombre de la app: `Bot Recordatorios`
   - Correo de soporte: tu correo de Gmail
   - Desplázate abajo → **Guardar y continuar** (en los pasos 2, 3 y 4 solo haz clic en "Continuar")
   - Vuelve a Credenciales → **+ Crear credenciales** → **"ID de cliente de OAuth"**
4. **Tipo de aplicación:** `Aplicación de escritorio`
5. **Nombre:** `Bot Recordatorios`
6. Clic en **Crear**
7. Haz clic en **"Descargar JSON"** → renombra el archivo como `credentials.json`

---

## PASO 3 — Instalar y configurar localmente

### 3.1 Clonar / descargar el proyecto

Si tienes Git:
```bash
git clone https://github.com/TU_USUARIO/bot-recordatorios.git
cd bot-recordatorios
```

O simplemente copia los archivos de este proyecto en una carpeta nueva.

### 3.2 Crear el entorno virtual e instalar dependencias

```bash
# Crear entorno virtual
python -m venv venv

# Activarlo (Windows)
venv\Scripts\activate

# Activarlo (Mac / Linux)
source venv/bin/activate

# Instalar dependencias
pip install -r requirements.txt
```

### 3.3 Configurar variables de entorno

1. Copia el archivo de ejemplo:
   ```bash
   cp .env.example .env
   ```
2. Abre `.env` con cualquier editor de texto y rellena:
   ```
   TELEGRAM_TOKEN=123456789:ABCdefGHI...  ← tu token de BotFather
   AUTHORIZED_USER_ID=987654321            ← tu ID de Telegram
   TIMEZONE=America/Bogota                 ← o tu zona horaria
   ```

Zonas horarias frecuentes:
| País | Zona |
|------|------|
| Colombia | America/Bogota |
| México (Centro) | America/Mexico_City |
| Argentina | America/Argentina/Buenos_Aires |
| España | Europe/Madrid |
| Venezuela | America/Caracas |
| Perú | America/Lima |

### 3.4 Colocar credentials.json

Copia el archivo `credentials.json` que descargaste de Google Cloud a la carpeta del proyecto.

### 3.5 Autenticarte con Google

```bash
python setup_google.py
```

- Se abrirá tu navegador.
- Inicia sesión con tu cuenta de Google.
- Acepta los permisos que solicita (Calendario y Tareas).
- El script generará `token.json` y mostrará los valores base64 para Railway.

> **IMPORTANTE:** Guarda el archivo `railway_env_vars.txt` que se genera. Lo necesitarás en el Paso 4.

### 3.6 Probar el bot localmente

```bash
python bot.py
```

Abre Telegram, busca tu bot y envíale `/start`. ¡Debería responder!

---

## PASO 4 — Desplegar en Railway (gratuito, siempre activo)

Railway es un servicio de hosting en la nube. El plan gratuito da **$5 de crédito/mes**, que es más que suficiente para un bot personal ligero.

### 4.1 Subir el código a GitHub

> Si no tienes cuenta de GitHub, créala gratis en [github.com](https://github.com).

```bash
# Inicializar repositorio (si no lo tienes)
git init
git add .
git commit -m "Bot de recordatorios inicial"

# Crear un repositorio PRIVADO en github.com y luego:
git remote add origin https://github.com/TU_USUARIO/bot-recordatorios.git
git push -u origin main
```

> **IMPORTANTE:** El repositorio debe ser **PRIVADO** para que tus credenciales no queden expuestas.
> El `.gitignore` ya excluye `credentials.json`, `token.json` y `.env`.

### 4.2 Crear el servicio en Railway

1. Ve a [railway.app](https://railway.app) y regístrate con tu cuenta de GitHub.
2. Clic en **"New Project"** → **"Deploy from GitHub repo"**
3. Selecciona tu repositorio `bot-recordatorios`.
4. Railway detectará automáticamente que es un proyecto Python.

### 4.3 Agregar variables de entorno en Railway

1. En el dashboard de Railway, haz clic en tu servicio.
2. Ve a la pestaña **"Variables"**.
3. Agrega estas variables una por una:

| Variable | Valor |
|----------|-------|
| `TELEGRAM_TOKEN` | Tu token de BotFather |
| `AUTHORIZED_USER_ID` | Tu ID de Telegram |
| `TIMEZONE` | Tu zona horaria (ej: `America/Bogota`) |
| `REMINDER_MINUTES_BEFORE` | `60` (o los minutos que prefieras) |
| `GOOGLE_TOKEN_BASE64` | El valor del archivo `railway_env_vars.txt` |
| `GOOGLE_CREDENTIALS_BASE64` | El valor del archivo `railway_env_vars.txt` |

4. Clic en **"Deploy"** (o Railway lo hace automáticamente al guardar variables).

### 4.4 Verificar que funciona

- En la pestaña **"Deployments"** de Railway verás los logs en tiempo real.
- Busca el mensaje: `Bot iniciado. Esperando mensajes...`
- Abre Telegram y envíale `/start` a tu bot.

---

## Uso del bot

### Comandos principales

| Comando | Acción |
|---------|--------|
| `/nueva` | Menú principal para crear cualquier cosa |
| `/tarea` | Nueva tarea con recordatorio |
| `/cita` | Nueva cita → Google Calendar |
| `/nota` | Guardar una nota (para tus 1000 notas) |
| `/cumple` | Registrar un cumpleaños |
| `/hoy` | Ver agenda del día |
| `/ver` | Ver todos los pendientes |
| `/notas` | Listar tus notas guardadas |
| `/buscar` | Buscar entre tus notas |
| `/cumples` | Ver próximos cumpleaños |

### Flujo de preguntas de control

Cuando creas una tarea o cita, el bot te pregunta:

```
Tú:  /tarea

Bot: 📋 Nueva tarea
     ¿Qué quieres recordar?

Tú:  Llamar al seguro médico

Bot: 📆 ¿Cuándo?
     [Hoy] [Mañana] [Lunes] [Otra fecha]

Tú:  mañana (o haz clic en el botón)

Bot: ⏰ ¿A qué hora? (ej: 9am, 14:30, sin hora)

Tú:  10am

Bot: ✅ Guardado.
     📋 Llamar al seguro médico
     📆 Mañana, martes 15 de abril a las 10:00
     📌 Añadido a Google Tasks
```

### Escribir libremente

También puedes escribir directamente sin comandos:

```
Tú:  Cita con el dentista el viernes a las 3pm

Bot: 📅 Cita detectada: "Cita con el dentista el viernes a las 3pm"
     📆 ¿Cuándo?
     [Hoy] [Mañana] [Otra]
```

### Guardar tus notas del móvil

Para importar tus ~1000 notas, tienes dos opciones:

**Opción A — Una por una (para notas importantes):**
```
/nota
→ Escribe el título o contenido
```

**Opción B — Importación masiva (próximamente):**
Puedes enviar un archivo `.txt` con tus notas, una por línea, y el bot las importará todas. (Puedes solicitar esta funcionalidad para una futura versión.)

### Recordatorios automáticos

El bot te enviará mensajes automáticos:

- **Tareas:** aviso X minutos antes (configurable con `REMINDER_MINUTES_BEFORE`) + aviso al momento
- **Citas:** aviso 1 día antes + aviso 1 hora antes + aviso al momento
- **Cumpleaños:** aviso 7 días antes + aviso 1 día antes + aviso el mismo día

---

## Solución de problemas frecuentes

**El bot no responde:**
- Verifica que `TELEGRAM_TOKEN` esté correcto en Railway.
- Revisa los logs en Railway → pestaña Deployments.

**Google no funciona:**
- Verifica que `GOOGLE_TOKEN_BASE64` y `GOOGLE_CREDENTIALS_BASE64` estén correctos.
- Vuelve a ejecutar `python setup_google.py` localmente y actualiza las variables en Railway.

**Error "Token expirado":**
- El bot refresca el token automáticamente. Si persiste, vuelve a ejecutar `setup_google.py`.

**"No tienes acceso":**
- Verifica que `AUTHORIZED_USER_ID` sea tu ID de Telegram correcto.
- Consúltalo enviando `/start` a @userinfobot.

---

## Estructura del proyecto

```
bot-recordatorios/
├── bot.py              ← Bot principal (manejadores, conversaciones, scheduler)
├── db.py               ← Base de datos SQLite (notas, recordatorios, cumpleaños)
├── google_services.py  ← Integración con Google Calendar y Tasks
├── setup_google.py     ← Ejecutar UNA VEZ para autenticarse con Google
├── requirements.txt    ← Dependencias de Python
├── .env.example        ← Plantilla de variables de entorno
├── .gitignore          ← Archivos a excluir de Git (¡importante!)
├── Procfile            ← Configuración para Railway/Heroku
└── railway.toml        ← Configuración adicional para Railway
```

---

## Costos

| Servicio | Plan | Costo |
|----------|------|-------|
| Telegram Bot API | Gratuito | $0 |
| Google Calendar API | Gratuito (uso personal) | $0 |
| Google Tasks API | Gratuito | $0 |
| Railway hosting | Starter (crédito $5/mes incluido) | $0* |

*Railway incluye $5 de crédito mensual gratuito. Un bot ligero consume aprox. $0.50–$1.00/mes, por lo que debería ser gratuito o de muy bajo costo.

---

*Guía generada con Claude — Bot de Recordatorios Personales*
