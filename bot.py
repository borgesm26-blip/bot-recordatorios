"""
bot.py — Bot principal de recordatorios personales para Telegram.

Características:
  - Gestión de tareas con recordatorios → Google Tasks
  - Gestión de citas/reuniones → Google Calendar
  - Almacenamiento de notas personales (hasta 1000+)
  - Recordatorios de cumpleaños anuales
  - Preguntas de control guiadas: ¿Qué? ¿Cuándo? ¿A qué hora?
  - Scheduler interno: avisos automáticos via Telegram

Uso:
  python bot.py
"""

import asyncio
import logging
import os
from datetime import datetime, timedelta
from typing import Optional, Tuple

import dateparser
import pytz
from dotenv import load_dotenv

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    BotCommand,
)
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ConversationHandler,
    CallbackQueryHandler,
    filters,
    ContextTypes,
)

load_dotenv()

from db import Database
from google_services import GoogleServices
from google_docs import GoogleDocs
from gemini_helper import (
    is_gemini_available,
    ask_assistant,
    parse_natural_language,
    summarize_tasks,
    analyze_notes,
    categorize_task,
)

# ═══════════════════════════════════════════════════════════════════════════════
# CONFIGURACIÓN
# ═══════════════════════════════════════════════════════════════════════════════

TOKEN           = os.getenv('TELEGRAM_TOKEN', '')
AUTH_USER_ID    = int(os.getenv('AUTHORIZED_USER_ID', '0'))
TZ_NAME         = os.getenv('TIMEZONE', 'America/Bogota')
TZ              = pytz.timezone(TZ_NAME)
ADV_MINUTES     = int(os.getenv('REMINDER_MINUTES_BEFORE', '60'))

logging.basicConfig(
    format='%(asctime)s | %(levelname)s | %(name)s | %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════════════════════
# ESTADOS DE CONVERSACIÓN
# ═══════════════════════════════════════════════════════════════════════════════

(
    CHOOSING_TYPE,    # Elegir: tarea / cita / nota / cumpleaños
    ASK_TITLE,        # ¿Qué quieres recordar?
    ASK_DATE,         # ¿Cuándo?
    ASK_TIME,         # ¿A qué hora?
    ASK_EXTRA,        # Notas adicionales (opcional)
    CONFIRMING,       # Confirmar antes de guardar
    BDAY_NAME,        # Nombre de la persona (cumpleaños)
    BDAY_DATE,        # Fecha de cumpleaños
    NOTE_CONTENT,     # Contenido de la nota
    SEARCH_QUERY,     # Texto de búsqueda en notas
    CLEANUP_MENU,     # Menú para limpiar notas
    CLEANUP_COUNT,    # Elegir cuántas notas eliminar
    COMPLETE_MENU,    # Menú para completar tareas
) = range(13)

# ═══════════════════════════════════════════════════════════════════════════════
# INSTANCIAS GLOBALES
# ═══════════════════════════════════════════════════════════════════════════════

db     = Database()
google = GoogleServices()

google_docs = GoogleDocs()
# ═══════════════════════════════════════════════════════════════════════════════
# UTILIDADES
# ═══════════════════════════════════════════════════════════════════════════════

def authorized(update: Update) -> bool:
    """Verifica que el mensaje viene del usuario autorizado."""
    if AUTH_USER_ID == 0:
        return True
    return update.effective_user.id == AUTH_USER_ID


async def deny(update: Update):
    await update.effective_message.reply_text(
        "⛔ No tienes acceso a este bot."
    )


def parse_dt(date_str: str, time_str: str = '') -> Optional[datetime]:
    """
    Parsea fecha y hora en español.
    Acepta: 'mañana a las 10am', '1 de mayo a las 9am', 'el viernes', etc.
    """
    full = f"{date_str} {time_str}".strip()
    if not full:
        return None

    settings = {
        'PREFER_DATES_FROM': 'future',
        'DATE_ORDER':        'DMY',
        'TIMEZONE':          TZ_NAME,
        'RETURN_AS_TIMEZONE_AWARE': True,
    }

    try:
        # Parsear con idioma español
        return dateparser.parse(full, languages=['es'], settings=settings)
    except Exception as e:
        logger.error(f"Error parseando fecha/hora '{full}': {e}")
        return None


def fmt_dt(dt: datetime) -> str:
    """Formatea datetime en español para mostrar al usuario."""
    if dt.tzinfo is None:
        dt = pytz.utc.localize(dt)
    local = dt.astimezone(TZ)

    dias   = ['Lunes','Martes','Miércoles','Jueves','Viernes','Sábado','Domingo']
    meses  = ['', 'enero','febrero','marzo','abril','mayo','junio',
               'julio','agosto','septiembre','octubre','noviembre','diciembre']

    return (
        f"{dias[local.weekday()]} "
        f"{local.day} de {meses[local.month]} "
        f"a las {local.strftime('%H:%M')}"
    )


def fmt_date_only(dt: datetime) -> str:
    meses = ['', 'enero','febrero','marzo','abril','mayo','junio',
              'julio','agosto','septiembre','octubre','noviembre','diciembre']
    return f"{dt.day} de {meses[dt.month]} de {dt.year}"


def type_emoji(t: str) -> str:
    return {'task': '📋', 'appointment': '📅', 'note': '📝', 'birthday': '🎂'}.get(t, '📌')


def type_label(t: str) -> str:
    return {'task': 'Tarea', 'appointment': 'Cita', 'note': 'Nota', 'birthday': 'Cumpleaños'}.get(t, t)


def main_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📋 Tarea",      callback_data="new_task"),
            InlineKeyboardButton("📅 Cita",        callback_data="new_appointment"),
        ],
        [
            InlineKeyboardButton("📝 Nota",        callback_data="new_note"),
            InlineKeyboardButton("🎂 Cumpleaños",  callback_data="new_birthday"),
        ],
        [
            InlineKeyboardButton("📅 Hoy",         callback_data="today"),
            InlineKeyboardButton("📋 Pendientes",  callback_data="pending"),
        ],
        [
            InlineKeyboardButton("📒 Mis notas",   callback_data="notes"),
            InlineKeyboardButton("🎂 Cumples",     callback_data="birthdays"),
        ],
    ])


# ═══════════════════════════════════════════════════════════════════════════════
# SCHEDULER — ENVÍO AUTOMÁTICO DE RECORDATORIOS
# ═══════════════════════════════════════════════════════════════════════════════

async def check_reminders(context: ContextTypes.DEFAULT_TYPE):
    """
    Tarea periódica (cada 60 s). Revisa la BD y envía los recordatorios
    cuyos avisos hayan llegado.
    """
    chat_id = db.get_setting('chat_id')
    if not chat_id:
        return

    # Refrescar token de Google si es necesario
    google.refresh_if_needed()

    due = db.get_due_reminders()
    now = datetime.utcnow()

    for r in due:
        title       = r['title']
        rtype       = r['type']
        emoji       = type_emoji(rtype)
        r1_dt       = r.get('reminder_1_dt')
        r2_dt       = r.get('reminder_2_dt')
        due_dt_str  = r.get('reminder_due_dt')

        # ── Aviso 1: anticipado (1 día antes para citas, X min para tareas) ──
        if r['sent_1'] == 0 and r1_dt and _is_past(r1_dt, now):
            if rtype == 'appointment':
                msg = f"📣 *Recordatorio* — mañana tienes:\n{emoji} {title}"
            else:
                hours_before = ADV_MINUTES // 60
                mins_before  = ADV_MINUTES % 60
                time_label   = f"{hours_before}h {mins_before}min" if hours_before else f"{mins_before} min"
                msg = f"⏰ *Recordatorio* ({time_label} antes)\n{emoji} {title}"

            await _send(context, int(chat_id), msg, r['id'], 'sent_1')

        # ── Aviso 2: 1 hora antes (solo citas) ──
        if r['sent_2'] == 0 and r2_dt and _is_past(r2_dt, now):
            msg = f"⏰ *En 1 hora:*\n{emoji} {title}"
            await _send(context, int(chat_id), msg, r['id'], 'sent_2')

        # ── Aviso en el momento ──
        if r['sent_due'] == 0 and due_dt_str and _is_past(due_dt_str, now):
            msg = f"🔔 *¡Ahora!*\n{emoji} *{title}*"
            kb  = InlineKeyboardMarkup([[
                InlineKeyboardButton("✅ Completado", callback_data=f"done_{r['id']}")
            ]])
            await _send(context, int(chat_id), msg, r['id'], 'sent_due', kb)

    # ── Cumpleaños: avisar 7 días, 1 día y el mismo día ──
    await _check_birthdays(context, int(chat_id), now)


def _is_past(dt_str: str, now: datetime) -> bool:
    try:
        dt = datetime.fromisoformat(dt_str)
        return dt <= now
    except (ValueError, TypeError):
        return False


async def _send(context, chat_id: int, text: str, rid: int,
                field: str, reply_markup=None):
    try:
        await context.bot.send_message(
            chat_id=chat_id, text=text,
            parse_mode='Markdown',
            reply_markup=reply_markup
        )
        db.mark_sent(rid, field)
    except Exception as e:
        logger.error("Error enviando recordatorio: %s", e)


async def _check_birthdays(context, chat_id: int, now: datetime):
    """Envía avisos de cumpleaños (7 días, 1 día, el mismo día) con edad."""
    upcoming = db.get_upcoming_birthdays(days=7)
    for bd in upcoming:
        days = bd.get('days_until', -1)
        name = bd['name']

        # Calcular edad si el año está disponible (no es 1900)
        birth_date = bd['birth_date']  # Formato: YYYY-MM-DD
        birth_year = int(birth_date.split('-')[0]) if birth_date else 1900

        age_str = ""
        if birth_year != 1900:
            age = now.year - birth_year
            age_str = f" ¡Cumple {age} años!"

        setting_key = f"bday_sent_{bd['id']}_{bd['next_date']}"
        already_sent = db.get_setting(setting_key)
        if already_sent:
            continue

        if days == 7:
            msg = f"🎂 En 7 días es el cumpleaños de *{name}* ({bd['next_date']}){age_str}"
        elif days == 1:
            msg = f"🎂 ¡Mañana es el cumpleaños de *{name}*! 🎉{age_str}"
        elif days == 0:
            msg = f"🎂🎉 ¡Hoy es el cumpleaños de *{name}*!{age_str} ¡Felicítale!"
        else:
            continue
        try:
            await context.bot.send_message(
                chat_id=chat_id, text=msg, parse_mode='Markdown'
            )
            db.set_setting(setting_key, '1')
        except Exception as e:
            logger.error("Error enviando aviso de cumpleaños: %s", e)


# ═══════════════════════════════════════════════════════════════════════════════
# COMANDOS SIMPLES
# ═══════════════════════════════════════════════════════════════════════════════

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not authorized(update):
        return await deny(update)

    # Guardar chat_id para que el scheduler pueda enviar mensajes
    db.set_setting('chat_id', str(update.effective_chat.id))

    g_status    = "✅ Conectado" if google.is_authorized() else "❌ Desconectado (usa /auth)"
    notes_count = db.count_notes()

    text = (
        f"👋 ¡Hola, *{update.effective_user.first_name}*!\n\n"
        f"Soy tu asistente personal de recordatorios.\n\n"
        f"*Estado:*\n"
        f"• Google: {g_status}\n"
        f"• Notas guardadas: *{notes_count}*\n\n"
        f"Elige una opción o escríbeme directamente:"
    )
    await update.message.reply_text(
        text, parse_mode='Markdown', reply_markup=main_keyboard()
    )


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not authorized(update):
        return await deny(update)
    text = (
        "📖 *Comandos disponibles:*\n\n"
        "*/nueva* — Menú para crear tarea, cita, nota o cumpleaños\n"
        "*/tarea* — Crear tarea / recordatorio rápido\n"
        "*/cita* — Crear cita (va a Google Calendar)\n"
        "*/nota* — Guardar una nota\n"
        "*/cumple* — Registrar cumpleaños\n\n"
        "*/hoy* — Agenda del día de hoy\n"
        "*/ver* — Todos los pendientes\n"
        "*/completar* — Marcar tareas como hechas\n"
        "*/historial* — Log de tareas completadas\n"
        "*/notas* — Ver tus notas guardadas\n"
        "*/buscar* — Buscar en tus notas\n"
        "*/cumples* — Ver cumpleaños próximos\n"
        "*/limpiar* — Eliminar notas (una a una o últimas N)\n\n"
        "*/auth* — Conectar con Google Calendar/Tasks\n"
        "*/start* — Menú principal\n"
        "*/ayuda* — Este mensaje\n\n"
        "💡 *Truco:* Puedes escribirme cualquier cosa y te haré las preguntas necesarias."
    )
    await update.message.reply_text(text, parse_mode='Markdown')


async def cmd_hoy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not authorized(update):
        return await deny(update)

    items = db.get_reminders_today()
    bdays = db.get_upcoming_birthdays(days=0)  # solo hoy (days_until == 0)

    if not items and not bdays:
        await update.message.reply_text("🌅 Hoy no tienes nada agendado. ¡Disfruta!")
        return

    lines = ["📅 *Agenda de hoy:*\n"]
    for r in items:
        try:
            dt = datetime.fromisoformat(r['due_datetime']).astimezone(TZ)
            hora = dt.strftime('%H:%M')
        except Exception:
            hora = '??:??'
        emoji = type_emoji(r['type'])
        lines.append(f"• {hora} {emoji} {r['title']}")

    for b in bdays:
        if b.get('days_until') == 0:
            lines.append(f"• 🎂 Cumpleaños de *{b['name']}* ¡Hoy!")

    await update.message.reply_text('\n'.join(lines), parse_mode='Markdown')


async def cmd_ver(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not authorized(update):
        return await deny(update)

    items = db.get_pending_reminders()
    if not items:
        await update.message.reply_text("✅ No tienes pendientes. ¡Todo al día!")
        return

    lines = ["📋 *Pendientes próximos:*\n"]
    for r in items[:15]:
        try:
            dt   = datetime.fromisoformat(r['due_datetime'])
            label = fmt_dt(dt)
        except Exception:
            label = r['due_datetime'] or 'sin fecha'
        emoji = type_emoji(r['type'])
        lines.append(f"• {emoji} *{r['title']}*\n  📆 {label}")

    await update.message.reply_text('\n'.join(lines), parse_mode='Markdown')


async def cmd_notas(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not authorized(update):
        return await deny(update)

    notes = db.get_notes(limit=10)
    total = db.count_notes()

    if not notes:
        await update.message.reply_text(
            "📝 No tienes notas guardadas todavía.\nUsa /nota para agregar una."
        )
        return

    lines = [f"📒 *Tus notas* (mostrando {len(notes)} de {total}):\n"]
    for n in notes:
        lines.append(f"• `#{n['id']}` {n['title']}")

    lines.append(f"\nUsa /buscar para buscar entre tus {total} notas.")
    await update.message.reply_text('\n'.join(lines), parse_mode='Markdown')


async def cmd_cumples(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not authorized(update):
        return await deny(update)

    upcoming = db.get_upcoming_birthdays(days=60)
    all_bds  = db.get_all_birthdays()

    if not all_bds:
        await update.message.reply_text(
            "🎂 No tienes cumpleaños registrados.\nUsa /cumple para agregar uno."
        )
        return

    lines = [f"🎂 *Próximos cumpleaños* (siguientes 60 días):\n"]
    if upcoming:
        for b in upcoming:
            days = b.get('days_until', '?')
            if days == 0:
                when = "¡*HOY*! 🎉"
            elif days == 1:
                when = "Mañana"
            else:
                when = f"En {days} días"
            lines.append(f"• {b['name']} — {when} ({b['next_date']})")
    else:
        lines.append("_Ninguno en los próximos 60 días._")

    lines.append(f"\nTotal registrados: {len(all_bds)}")
    await update.message.reply_text('\n'.join(lines), parse_mode='Markdown')


# ═══════════════════════════════════════════════════════════════════════════════
# FLUJO DE CREACIÓN — ConversationHandler
# ═══════════════════════════════════════════════════════════════════════════════

async def cmd_nueva(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Muestra el menú de selección de tipo."""
    if not authorized(update):
        return await deny(update)
    context.user_data.clear()
    kb = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📋 Tarea",      callback_data="ct_task"),
            InlineKeyboardButton("📅 Cita",        callback_data="ct_appointment"),
        ],
        [
            InlineKeyboardButton("📝 Nota",        callback_data="ct_note"),
            InlineKeyboardButton("🎂 Cumpleaños",  callback_data="ct_birthday"),
        ],
        [InlineKeyboardButton("❌ Cancelar",        callback_data="ct_cancel")],
    ])
    await update.effective_message.reply_text(
        "¿Qué quieres agregar?", reply_markup=kb
    )
    return CHOOSING_TYPE


async def cmd_tarea(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not authorized(update):
        return await deny(update)
    context.user_data.clear()
    context.user_data['type'] = 'task'
    await update.message.reply_text(
        "📋 *Nueva tarea*\n\n¿Qué quieres recordar?",
        parse_mode='Markdown'
    )
    return ASK_TITLE


async def cmd_cita(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not authorized(update):
        return await deny(update)
    context.user_data.clear()
    context.user_data['type'] = 'appointment'
    await update.message.reply_text(
        "📅 *Nueva cita*\n\n¿Qué cita o reunión tienes?",
        parse_mode='Markdown'
    )
    return ASK_TITLE


async def cmd_nota(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not authorized(update):
        return await deny(update)
    context.user_data.clear()
    context.user_data['type'] = 'note'
    await update.message.reply_text(
        "📝 *Nueva nota*\n\n¿Cuál es el título o contenido de la nota?",
        parse_mode='Markdown'
    )
    return NOTE_CONTENT


async def cmd_cumple(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not authorized(update):
        return await deny(update)
    context.user_data.clear()
    context.user_data['type'] = 'birthday'
    await update.message.reply_text(
        "🎂 *Nuevo cumpleaños*\n\n¿Nombre de la persona?",
        parse_mode='Markdown'
    )
    return BDAY_NAME


async def cmd_buscar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not authorized(update):
        return await deny(update)
    await update.message.reply_text("🔍 ¿Qué quieres buscar en tus notas?")
    return SEARCH_QUERY


async def cmd_historial(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Muestra el historial de tareas completadas."""
    if not authorized(update):
        return await deny(update)

    # Obtener tareas completadas directamente de la BD
    try:
        with db._conn() as c:
            rows = c.execute(
                '''SELECT id, title, due_datetime, created_at FROM reminders
                   WHERE is_completed = 1
                   ORDER BY created_at DESC LIMIT 50'''
            ).fetchall()

        if not rows:
            await update.message.reply_text("📝 No hay tareas completadas aún.")
            return

        # Formatear el historial
        msg = "✅ *Tareas Completadas (últimas 50):*\n\n"
        for i, row in enumerate(rows, 1):
            title = row['title']
            msg += f"{i}. {title}\n"

        await update.message.reply_text(msg, parse_mode='Markdown')

    except Exception as e:
        logger.error(f"Error obteniendo historial: {e}")
        await update.message.reply_text("❌ Error al obtener el historial.")


# ─── Comando /limpiar: eliminar notas ────────────────────────────────────────

async def cmd_limpiar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Menú para limpiar notas."""
    if not authorized(update):
        return await deny(update)

    notes = db.get_notes(limit=99999)
    if not notes:
        await update.message.reply_text("📝 No hay notas para eliminar.")
        return ConversationHandler.END

    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("📋 Ver todas mis notas", callback_data="cleanup_view_all")],
        [InlineKeyboardButton("🗑️ Eliminar últimas N", callback_data="cleanup_delete_last")],
        [InlineKeyboardButton("❌ Cancelar", callback_data="cleanup_cancel")],
    ])
    await update.message.reply_text(
        f"🧹 *Limpiar notas*\n\nTienes *{len(notes)}* notas. ¿Qué quieres hacer?",
        reply_markup=kb,
        parse_mode='Markdown'
    )
    return CLEANUP_MENU


async def cleanup_menu_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Maneja la selección del menú de limpiar."""
    query = update.callback_query
    await query.answer()

    if query.data == "cleanup_cancel":
        await query.edit_message_text("❌ Cancelado.")
        return ConversationHandler.END

    if query.data == "cleanup_view_all":
        # Mostrar todas las notas con botones para eliminar
        notes = db.get_notes(limit=99999)
        if not notes:
            await query.edit_message_text("📝 No hay notas.")
            return ConversationHandler.END

        # Crear botones para cada nota
        kb_buttons = []
        for note in notes:
            btn_text = f"🗑️ {note['title'][:30]}"
            btn_data = f"cleanup_delete_{note['id']}"
            kb_buttons.append([InlineKeyboardButton(btn_text, callback_data=btn_data)])

        kb_buttons.append([InlineKeyboardButton("❌ Cancelar", callback_data="cleanup_cancel")])
        kb = InlineKeyboardMarkup(kb_buttons)

        msg = f"*Tus {len(notes)} notas:*\n\nSelecciona una para eliminar:"
        await query.edit_message_text(msg, reply_markup=kb, parse_mode='Markdown')
        return CLEANUP_MENU

    if query.data == "cleanup_delete_last":
        # Solicitar cantidad
        await query.edit_message_text("¿Cuántas notas quieres eliminar? (escribe un número)")
        return CLEANUP_COUNT


async def cleanup_delete_count(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Elimina las últimas N notas."""
    try:
        count = int(update.message.text.strip())
        notes = db.get_notes(limit=99999)

        if count > len(notes):
            count = len(notes)

        # Obtener las últimas N notas (del final hacia atrás)
        notes_to_delete = notes[-count:]

        for note in notes_to_delete:
            db.delete_note(note['id'])

        await update.message.reply_text(
            f"✅ Se eliminaron *{count}* notas correctamente.",
            parse_mode='Markdown'
        )
        return ConversationHandler.END

    except ValueError:
        await update.message.reply_text("❌ Por favor, escribe un número válido.")
        return CLEANUP_COUNT


async def cleanup_delete_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Elimina una nota seleccionada y vuelve a mostrar la lista."""
    query = update.callback_query
    await query.answer()

    data = query.data
    if data == "cleanup_cancel":
        await query.edit_message_text("❌ Cancelado.")
        return ConversationHandler.END

    if data.startswith("cleanup_delete_"):
        note_id = int(data.replace("cleanup_delete_", ""))
        db.delete_note(note_id)

        # Mostrar la lista de notas actualizada
        notes = db.get_notes(limit=99999)
        if not notes:
            await query.edit_message_text("✅ Nota eliminada.\n\n📝 ¡Ya no tienes más notas!")
            return ConversationHandler.END

        # Recrear la lista de botones con las notas restantes
        kb_buttons = []
        for note in notes:
            btn_text = f"🗑️ {note['title'][:30]}"
            btn_data = f"cleanup_delete_{note['id']}"
            kb_buttons.append([InlineKeyboardButton(btn_text, callback_data=btn_data)])

        kb_buttons.append([InlineKeyboardButton("❌ Salir", callback_data="cleanup_cancel")])
        kb = InlineKeyboardMarkup(kb_buttons)

        msg = f"✅ Nota eliminada.\n\n*Tus {len(notes)} notas restantes:*\n\nSelecciona una para eliminar:"
        await query.edit_message_text(msg, reply_markup=kb, parse_mode='Markdown')
        return CLEANUP_MENU

    return ConversationHandler.END


# ─── Comando /completar: marcar tareas como hechas ──────────────────────────

async def cmd_completar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Menú para marcar tareas como completadas."""
    if not authorized(update):
        return await deny(update)

    reminders = db.get_pending_reminders()
    if not reminders:
        await update.message.reply_text("✅ ¡No hay tareas pendientes!")
        return ConversationHandler.END

    # Crear botones para cada tarea
    kb_buttons = []
    for reminder in reminders:
        btn_text = f"✓ {reminder['title'][:30]}"
        btn_data = f"complete_{reminder['id']}"
        kb_buttons.append([InlineKeyboardButton(btn_text, callback_data=btn_data)])

    kb_buttons.append([InlineKeyboardButton("❌ Cancelar", callback_data="complete_cancel")])
    kb = InlineKeyboardMarkup(kb_buttons)

    msg = f"*Tus {len(reminders)} tareas pendientes:*\n\nSelecciona una para marcar como hecha:"
    await update.message.reply_text(msg, reply_markup=kb, parse_mode='Markdown')
    return COMPLETE_MENU


async def complete_task_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Marca una tarea como completada y pregunta si eliminarla."""
    query = update.callback_query
    await query.answer()

    data = query.data
    if data == "complete_cancel":
        await query.edit_message_text("❌ Cancelado.")
        return ConversationHandler.END

    # Opción: eliminar la tarea que se acaba de completar
    if data.startswith("complete_delete_"):
        reminder_id = int(data.replace("complete_delete_", ""))
        db.delete_reminder(reminder_id)

        # Volver a la lista de tareas pendientes
        reminders = db.get_pending_reminders()
        if not reminders:
            await query.edit_message_text("✅ Tarea eliminada.\n\n🎉 ¡Ya no tienes más tareas pendientes!")
            return ConversationHandler.END

        # Recrear la lista de botones
        kb_buttons = []
        for reminder in reminders:
            btn_text = f"✓ {reminder['title'][:30]}"
            btn_data = f"complete_{reminder['id']}"
            kb_buttons.append([InlineKeyboardButton(btn_text, callback_data=btn_data)])

        kb_buttons.append([InlineKeyboardButton("❌ Salir", callback_data="complete_cancel")])
        kb = InlineKeyboardMarkup(kb_buttons)

        msg = f"✅ Tarea eliminada.\n\n*Quedan {len(reminders)} tareas:*\n\nSelecciona otra:"
        await query.edit_message_text(msg, reply_markup=kb, parse_mode='Markdown')
        return COMPLETE_MENU

    # Opción: no eliminar, continuar con siguiente tarea
    if data == "complete_keep":
        reminders = db.get_pending_reminders()
        if not reminders:
            await query.edit_message_text("✅ ¡Ya no tienes más tareas pendientes!")
            return ConversationHandler.END

        kb_buttons = []
        for reminder in reminders:
            btn_text = f"✓ {reminder['title'][:30]}"
            btn_data = f"complete_{reminder['id']}"
            kb_buttons.append([InlineKeyboardButton(btn_text, callback_data=btn_data)])

        kb_buttons.append([InlineKeyboardButton("❌ Salir", callback_data="complete_cancel")])
        kb = InlineKeyboardMarkup(kb_buttons)

        msg = f"*Quedan {len(reminders)} tareas:*\n\nSelecciona otra para marcar como hecha:"
        await query.edit_message_text(msg, reply_markup=kb, parse_mode='Markdown')
        return COMPLETE_MENU

    if data.startswith("complete_"):
        reminder_id = int(data.replace("complete_", ""))
        db.complete_reminder(reminder_id)

        # Preguntar si eliminar o continuar
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("🗑️ Eliminar del registro", callback_data=f"complete_delete_{reminder_id}")],
            [InlineKeyboardButton("➡️ Continuar", callback_data="complete_keep")],
            [InlineKeyboardButton("❌ Salir", callback_data="complete_cancel")],
        ])

        await query.edit_message_text(
            "✅ Tarea marcada como completada.\n\n¿Quieres eliminarla del registro?",
            reply_markup=kb,
            parse_mode='Markdown'
        )
        return COMPLETE_MENU

    return ConversationHandler.END


# ─── Callback: selección de tipo desde menú ─────────────────────────────────

async def cb_choose_type(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    data = query.data
    if data == 'ct_cancel':
        await query.edit_message_text("❌ Cancelado.")
        return ConversationHandler.END

    type_map = {
        'ct_task':        ('task',        '📋 *Nueva tarea*\n\n¿Qué quieres recordar?',         ASK_TITLE),
        'ct_appointment': ('appointment', '📅 *Nueva cita*\n\n¿Qué cita o reunión tienes?',      ASK_TITLE),
        'ct_note':        ('note',        '📝 *Nueva nota*\n\n¿Cuál es el título de la nota?',   NOTE_CONTENT),
        'ct_birthday':    ('birthday',    '🎂 *Nuevo cumpleaños*\n\n¿Nombre de la persona?',     BDAY_NAME),
    }

    if data not in type_map:
        return ConversationHandler.END

    t, msg, next_state = type_map[data]
    context.user_data['type'] = t
    await query.edit_message_text(msg, parse_mode='Markdown')
    return next_state


# ─── Estado ASK_TITLE: recibe el título ──────────────────────────────────────

async def recv_title(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['title'] = update.message.text.strip()
    rtype = context.user_data.get('type', 'task')

    if rtype == 'note':
        # Las notas no necesitan fecha → ir a confirmación directa
        return await _confirm_note(update, context)

    kb = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("Hoy",     callback_data="date_hoy"),
            InlineKeyboardButton("Mañana",  callback_data="date_manana"),
            InlineKeyboardButton("Lunes",   callback_data="date_lunes"),
        ],
        [InlineKeyboardButton("Otra fecha (escríbela)", callback_data="date_custom")],
    ])
    await update.message.reply_text(
        "📆 ¿Cuándo?", reply_markup=kb
    )
    return ASK_DATE


# ─── Estado ASK_DATE: recibe la fecha ────────────────────────────────────────

async def cb_date_preset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    preset_map = {
        'date_hoy':    'hoy',
        'date_manana': 'mañana',
        'date_lunes':  'el próximo lunes',
    }

    data = query.data
    if data == 'date_custom':
        await query.edit_message_text(
            "✍️ Escribe la fecha (ej: *20 de abril*, *el viernes*, *próxima semana*)",
            parse_mode='Markdown'
        )
        return ASK_DATE

    date_str = preset_map.get(data, 'hoy')
    context.user_data['date_str'] = date_str
    await query.edit_message_text(f"📆 Fecha: _{date_str}_", parse_mode='Markdown')
    await query.message.reply_text("⏰ ¿A qué hora? (ej: *9am*, *14:30*, *sin hora*)",
                                   parse_mode='Markdown')
    return ASK_TIME


async def recv_date_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_input = update.message.text.strip()

    # Intentar parsear como si ya tuviera fecha Y hora
    dt = parse_dt(user_input, '')
    if dt:
        # Éxito: el usuario incluyó fecha y hora juntas
        context.user_data['datetime'] = dt
        await _show_confirm(update, context)
        return CONFIRMING

    # Si no funciona, guardar la fecha y pedir la hora
    context.user_data['date_str'] = user_input
    await update.message.reply_text(
        "⏰ ¿A qué hora? (ej: *9am*, *14:30*, *sin hora*)",
        parse_mode='Markdown'
    )
    return ASK_TIME


# ─── Estado ASK_TIME: recibe la hora ─────────────────────────────────────────

async def recv_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    time_raw = update.message.text.strip().lower()
    context.user_data['time_str'] = '' if time_raw in ('sin hora', 'no', 'n/a', '-') else time_raw

    date_str = context.user_data.get('date_str', 'hoy')
    time_str = context.user_data.get('time_str', '')

    dt = parse_dt(date_str, time_str)
    if not dt:
        await update.message.reply_text(
            "❌ No entendí la fecha/hora. Inténtalo de nuevo (ej: *mañana a las 10am*).",
            parse_mode='Markdown'
        )
        return ASK_TIME

    context.user_data['datetime'] = dt
    await _show_confirm(update, context)
    return CONFIRMING


# ─── Nota: recibe el contenido directamente ──────────────────────────────────

async def recv_note_content(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    # Si el título ya fue guardado (flujo nueva→nota), usar texto como contenido
    if 'title' not in context.user_data:
        context.user_data['title'] = text
    context.user_data['note_content'] = text
    return await _confirm_note(update, context)


async def _confirm_note(update: Update, context: ContextTypes.DEFAULT_TYPE):
    title = context.user_data.get('title', '(sin título)')
    kb = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Guardar", callback_data="confirm_yes"),
            InlineKeyboardButton("❌ Cancelar", callback_data="confirm_no"),
        ]
    ])
    # No usar parse_mode si el contenido tiene URLs u caracteres especiales
    # Telegram no puede parsear markdown con URLs correctamente
    await update.effective_message.reply_text(
        f"📝 Nota: {title}\n\n¿Guardamos?",
        reply_markup=kb
    )
    return CONFIRMING


# ─── Mostrar resumen para confirmar ──────────────────────────────────────────

async def _show_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ud    = context.user_data
    title = ud.get('title', '?')
    rtype = ud.get('type', 'task')
    dt    = ud.get('datetime')
    emoji = type_emoji(rtype)
    label = type_label(rtype)

    dt_label = fmt_dt(dt) if dt else '_(sin fecha)_'

    g_line = ""
    if rtype == 'task' and google.is_authorized():
        g_line = "\n📌 _Se agregará también a Google Tasks_"
    elif rtype == 'appointment' and google.is_authorized():
        g_line = "\n📌 _Se agregará también a Google Calendar_"

    text = (
        f"{emoji} *{label}:* {title}\n"
        f"📆 {dt_label}"
        f"{g_line}\n\n"
        f"¿Todo correcto?"
    )
    kb = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Confirmar", callback_data="confirm_yes"),
            InlineKeyboardButton("✏️ Cambiar hora", callback_data="confirm_edit_time"),
        ],
        [InlineKeyboardButton("❌ Cancelar", callback_data="confirm_no")],
    ])
    await update.effective_message.reply_text(
        text, parse_mode='Markdown', reply_markup=kb
    )


# ─── Estado CONFIRMING: guardar o cancelar ───────────────────────────────────

async def cb_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    data  = query.data
    ud    = context.user_data
    rtype = ud.get('type', 'task')

    if data == 'confirm_no':
        await query.edit_message_text("❌ Cancelado. Sin cambios.")
        context.user_data.clear()
        return ConversationHandler.END

    if data == 'confirm_edit_time':
        await query.edit_message_text(
            "⏰ ¿A qué hora? (ej: *9am*, *14:30*, *sin hora*)",
            parse_mode='Markdown'
        )
        return ASK_TIME

    # ── confirm_yes: guardar ──────────────────────────────────────────────────
    title = ud.get('title', '(sin título)')
    dt    = ud.get('datetime')

    if rtype == 'note':
        note_id = db.add_note(title=title, content=ud.get('note_content', ''))

        # Guardar también en Google Docs si está disponible
        if google_docs and google_docs.is_authorized():
            content = ud.get("note_content", "")
            google_docs.add_note(title=title, content=content)
            docs_status = " y en Google Docs"
        else:
            docs_status = ""
        await query.edit_message_text(
            f"✅ Nota guardada en BD{docs_status}.\n📒 *{title}* (#{note_id})",
            parse_mode='Markdown'
        )
        context.user_data.clear()
        return ConversationHandler.END

    # Guardar en Google si está disponible
    google_id = None
    if rtype == 'task' and dt:
        google_id = google.create_task(title=title, notes='', due_dt=dt)
    elif rtype == 'appointment' and dt:
        google_id = google.create_event(title=title, start_dt=dt, description='')

    # Guardar en BD local
    rid = db.add_reminder(
        title=title,
        description='',
        due_dt=dt or datetime.utcnow() + timedelta(hours=1),
        reminder_type=rtype,
        advance_minutes=ADV_MINUTES,
        google_id=google_id
    )

    g_msg = ''
    if google_id and rtype == 'task':
        g_msg = '\n📌 Añadido a Google Tasks'
    elif google_id and rtype == 'appointment':
        g_msg = '\n📌 Añadido a Google Calendar'
    elif not google.is_authorized():
        g_msg = '\n⚠️ _Google no conectado, guardado solo localmente_'

    emoji = type_emoji(rtype)
    dt_label = fmt_dt(dt) if dt else '_(sin fecha)_'

    await query.edit_message_text(
        f"✅ Guardado.\n{emoji} *{title}*\n📆 {dt_label}{g_msg}",
        parse_mode='Markdown'
    )
    context.user_data.clear()
    return ConversationHandler.END


# ─── Flujo de cumpleaños ─────────────────────────────────────────────────────

async def recv_bday_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['bday_name'] = update.message.text.strip()
    await update.message.reply_text(
        "📅 ¿Cuál es la fecha de su cumpleaños?\n"
        "Formato: *DD/MM/AAAA* o *15 de marzo de 1990*",
        parse_mode='Markdown'
    )
    return BDAY_DATE


async def recv_bday_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    raw  = update.message.text.strip()
    name = context.user_data.get('bday_name', '?')

    # Parsear fecha (cumpleaños pueden ser del pasado)
    settings = {
        'PREFER_DATES_FROM': 'past',
        'DATE_ORDER':        'DMY',
        'RETURN_AS_TIMEZONE_AWARE': False,
    }
    try:
        dt = dateparser.parse(raw, languages=['es'], settings=settings)
    except Exception as e:
        logger.error(f"Error parseando cumpleaños '{raw}': {e}")
        dt = None

    if not dt:
        await update.message.reply_text(
            "❌ No entendí la fecha. Intenta con formato *15/03* o *15 de marzo* (sin año) o *15 de marzo de 1990*.",
            parse_mode='Markdown'
        )
        return BDAY_DATE

    # Si el usuario no incluyó año (números de 4 dígitos), usar 1900 como marcador
    import re
    has_year = bool(re.search(r'\d{4}', raw))

    if not has_year:
        # Usuario no ingresó año, reemplazar con 1900 como marcador
        dt = dt.replace(year=1900)

    birth_str  = dt.strftime('%Y-%m-%d')
    display    = fmt_date_only(dt)

    # Guardar en BD
    google_id = google.create_birthday_event(name, birth_str) if google.is_authorized() else None
    bid       = db.add_birthday(name=name, birth_date=birth_str, google_event_id=google_id)

    g_msg = '\n📌 Agregado a Google Calendar (evento anual)' if google_id else ''

    await update.message.reply_text(
        f"🎂 ¡Cumpleaños guardado!\n"
        f"*{name}* — {display}"
        f"{g_msg}",
        parse_mode='Markdown'
    )
    context.user_data.clear()
    return ConversationHandler.END


# ─── Búsqueda de notas ───────────────────────────────────────────────────────

async def recv_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query_text = update.message.text.strip()
    results    = db.get_notes(limit=10, search=query_text)

    if not results:
        await update.message.reply_text(
            f"🔍 Sin resultados para: _{query_text}_",
            parse_mode='Markdown'
        )
    else:
        lines = [f"🔍 *{len(results)} resultado(s) para '{query_text}':*\n"]
        for n in results:
            lines.append(f"• `#{n['id']}` *{n['title']}*")
            if n.get('content') and n['content'] != n['title']:
                snippet = n['content'][:80] + ('…' if len(n['content']) > 80 else '')
                lines.append(f"  _{snippet}_")
        await update.message.reply_text('\n'.join(lines), parse_mode='Markdown')

    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.effective_message.reply_text("❌ Operación cancelada.")
    return ConversationHandler.END


# ─── Callbacks del menú principal ────────────────────────────────────────────

async def cb_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data  = query.data

    if data == 'today':
        items = db.get_reminders_today()
        bdays = [b for b in db.get_upcoming_birthdays(0) if b.get('days_until') == 0]
        if not items and not bdays:
            await query.edit_message_text("🌅 Hoy no tienes nada agendado.")
            return
        lines = ["📅 *Agenda de hoy:*\n"]
        for r in items:
            try:
                dt   = datetime.fromisoformat(r['due_datetime']).astimezone(TZ)
                hora = dt.strftime('%H:%M')
            except Exception:
                hora = '??:??'
            lines.append(f"• {hora} {type_emoji(r['type'])} {r['title']}")
        for b in bdays:
            lines.append(f"• 🎂 Cumpleaños de *{b['name']}* ¡Hoy!")
        await query.edit_message_text('\n'.join(lines), parse_mode='Markdown')

    elif data == 'pending':
        items = db.get_pending_reminders()
        if not items:
            await query.edit_message_text("✅ No tienes pendientes.")
            return
        lines = ["📋 *Pendientes:*\n"]
        for r in items[:10]:
            try:
                dt    = datetime.fromisoformat(r['due_datetime'])
                label = fmt_dt(dt)
            except Exception:
                label = r['due_datetime'] or '?'
            lines.append(f"• {type_emoji(r['type'])} *{r['title']}*\n  📆 {label}")
        await query.edit_message_text('\n'.join(lines), parse_mode='Markdown')

    elif data == 'notes':
        notes = db.get_notes(10)
        total = db.count_notes()
        if not notes:
            await query.edit_message_text("📝 No tienes notas aún. Usa /nota.")
            return
        lines = [f"📒 *Notas* ({total} total):\n"]
        for n in notes:
            lines.append(f"• `#{n['id']}` {n['title']}")
        await query.edit_message_text('\n'.join(lines), parse_mode='Markdown')

    elif data == 'birthdays':
        upcoming = db.get_upcoming_birthdays(60)
        all_bds  = db.get_all_birthdays()
        if not all_bds:
            await query.edit_message_text("🎂 No tienes cumpleaños. Usa /cumple.")
            return
        lines = ["🎂 *Próximos cumpleaños (60 días):*\n"]
        if upcoming:
            for b in upcoming:
                d = b.get('days_until', '?')
                when = "¡HOY! 🎉" if d == 0 else (f"mañana" if d == 1 else f"en {d} días")
                lines.append(f"• *{b['name']}* — {when}")
        else:
            lines.append("_Ninguno próximamente._")
        await query.edit_message_text('\n'.join(lines), parse_mode='Markdown')


# ─── Marcar tarea como completada ────────────────────────────────────────────

async def cb_done(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    rid_str = query.data.split('_', 1)[1]
    try:
        rid = int(rid_str)
    except ValueError:
        return

    db.complete_reminder(rid)
    await query.edit_message_text("✅ ¡Marcado como completado!")


# ─── Mensaje libre: clasificar y arrancar conversación ───────────────────────

TASK_WORDS  = {'recordar', 'comprar', 'llamar', 'enviar', 'pagar', 'renovar',
               'hacer', 'tramite', 'trámite', 'entregar', 'recoger', 'buscar'}
APPT_WORDS  = {'cita', 'reunion', 'reunión', 'doctor', 'dentista', 'médico',
               'medico', 'junta', 'entrevista', 'consulta', 'turno'}
BDAY_WORDS  = {'cumpleaños', 'cumpleanos', 'nació', 'aniversario', 'nacio'}


def _classify(text: str) -> str:
    lower = text.lower()
    if any(w in lower for w in BDAY_WORDS):
        return 'birthday'
    if any(w in lower for w in APPT_WORDS):
        return 'appointment'
    if any(w in lower for w in TASK_WORDS):
        return 'task'
    return 'unknown'


async def handle_free_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not authorized(update):
        return await deny(update)

    text  = update.message.text.strip()
    rtype = _classify(text)

    if rtype == 'unknown':
        await update.message.reply_text(
            "¿Qué quieres hacer?", reply_markup=main_keyboard()
        )
        return

    context.user_data.clear()
    context.user_data['type']  = rtype
    context.user_data['title'] = text

    if rtype == 'birthday':
        await update.message.reply_text(
            "🎂 Parece un cumpleaños. ¿Nombre de la persona?"
        )
        return BDAY_NAME

    emoji = type_emoji(rtype)
    label = type_label(rtype)
    await update.message.reply_text(
        f"{emoji} *{label}* detectada:\n_{text}_\n\n📆 ¿Cuándo?",
        parse_mode='Markdown',
        reply_markup=InlineKeyboardMarkup([
            [
                InlineKeyboardButton("Hoy",     callback_data="date_hoy"),
                InlineKeyboardButton("Mañana",  callback_data="date_manana"),
                InlineKeyboardButton("Otra",    callback_data="date_custom"),
            ]
        ])
    )
    return ASK_DATE


# ═══════════════════════════════════════════════════════════════════════════════
# COMANDO /auth — Conectar Google (se usa setup_google.py localmente)
# ═══════════════════════════════════════════════════════════════════════════════

async def cmd_auth(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not authorized(update):
        return await deny(update)

    if google.is_authorized():
        await update.message.reply_text(
            "✅ Ya estás conectado a Google Calendar, Tasks y Docs."
        )
        return

    await update.message.reply_text(
        "🔑 *Configuración de Google*\n\n"
        "Para conectar Google Calendar y Tasks:\n\n"
        "1. En tu computadora, ejecuta:\n"
        "   `python setup_google.py`\n\n"
        "2. Se abrirá el navegador → inicia sesión con tu cuenta de Google.\n\n"
        "3. Una vez autorizado, el archivo `token.json` se creará automáticamente.\n\n"
        "4. En Railway: convierte `token.json` a base64 y agrégalo como variable `GOOGLE_TOKEN_BASE64`.\n\n"
        "Consulta el archivo `SETUP.md` para instrucciones detalladas.",
        parse_mode='Markdown'
    )


# ═══════════════════════════════════════════════════════════════════════════════
# COMANDOS CON GEMINI (ASISTENTE INTELIGENTE)
# ═══════════════════════════════════════════════════════════════════════════════

async def cmd_pregunta(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Asistente inteligente: responde preguntas sobre tareas y notas."""
    if not authorized(update):
        return await deny(update)

    if not is_gemini_available():
        await update.message.reply_text(
            "❌ Gemini no está configurado. Verifica que GEMINI_API_KEY esté en el .env"
        )
        return

    if not context.args:
        await update.message.reply_text(
            "🤖 *Asistente Inteligente*\n\n"
            "Uso: `/pregunta ¿Qué tareas tengo pendientes?`\n\n"
            "Puedo responder preguntas sobre tus tareas, notas y cumpleaños.",
            parse_mode='Markdown'
        )
        return

    question = ' '.join(context.args)

    # Obtener contexto del usuario
    reminders = db.get_pending_reminders()
    notes = db.get_notes(limit=10)
    birthdays = db.get_upcoming_birthdays(days=90)

    context_data = {
        'reminders': '\n'.join([f"- {r['title']} ({r.get('due_datetime', 'N/A')})" for r in reminders[:5]]) or "Ninguna",
        'notes': '\n'.join([f"- {n['title']}" for n in notes[:5]]) or "Ninguna",
        'birthdays': '\n'.join([f"- {b['name']} ({b['birth_date']})" for b in birthdays[:5]]) or "Ninguno"
    }

    await update.message.reply_text("⏳ Procesando tu pregunta...", parse_mode='Markdown')

    answer = ask_assistant(question, context_data)

    if answer:
        await update.message.reply_text(f"🤖 *Respuesta:*\n\n{answer}", parse_mode='Markdown')
    else:
        await update.message.reply_text("❌ No pude procesar tu pregunta. Intenta de nuevo.")


async def cmd_analizar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Análisis inteligente de tareas y notas."""
    if not authorized(update):
        return await deny(update)

    if not is_gemini_available():
        await update.message.reply_text(
            "❌ Gemini no está configurado. Verifica que GEMINI_API_KEY esté en el .env"
        )
        return

    await update.message.reply_text("⏳ Analizando tus tareas y notas...", parse_mode='Markdown')

    reminders = db.get_pending_reminders()
    notes = db.get_notes(limit=15)

    tasks_summary = None
    notes_summary = None

    if reminders:
        tasks_summary = summarize_tasks(reminders)

    if notes:
        notes_summary = analyze_notes(notes)

    response = "📊 *Análisis Inteligente:*\n\n"

    if tasks_summary:
        response += f"📋 *Tareas:*\n{tasks_summary}\n\n"
    else:
        response += "📋 No tienes tareas pendientes.\n\n"

    if notes_summary:
        response += f"📝 *Notas:*\n{notes_summary}"
    else:
        response += "📝 No tienes notas guardadas."

    await update.message.reply_text(response, parse_mode='Markdown')


async def cmd_gemini_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Ayuda sobre funciones de Gemini."""
    if not authorized(update):
        return await deny(update)

    status = "✅ Disponible" if is_gemini_available() else "❌ No configurado"

    text = (
        f"🤖 *Comandos con Gemini AI:* {status}\n\n"
        "*/pregunta [tu pregunta]* — Asistente inteligente\n"
        "Ejemplo: `/pregunta ¿Qué tareas tengo pendientes?`\n\n"
        "*/analizar* — Análisis de tus tareas y notas\n"
        "Te da insights sobre tu productividad.\n\n"
        "*/gemini_help* — Este mensaje"
    )

    await update.message.reply_text(text, parse_mode='Markdown')


# ═══════════════════════════════════════════════════════════════════════════════
# CONFIGURACIÓN Y ARRANQUE DEL BOT
# ═══════════════════════════════════════════════════════════════════════════════

def build_app() -> Application:
    if not TOKEN:
        raise ValueError("No se encontró TELEGRAM_TOKEN en las variables de entorno.")

    app = Application.builder().token(TOKEN).build()

    # ── ConversationHandler unificado ────────────────────────────────────────
    conv = ConversationHandler(
        entry_points=[
            CommandHandler('nueva',     cmd_nueva),
            CommandHandler('tarea',     cmd_tarea),
            CommandHandler('cita',      cmd_cita),
            CommandHandler('nota',      cmd_nota),
            CommandHandler('cumple',    cmd_cumple),
            CommandHandler('buscar',    cmd_buscar),
            CommandHandler('limpiar',   cmd_limpiar),
            CommandHandler('completar', cmd_completar),
        ],
        states={
            CHOOSING_TYPE: [CallbackQueryHandler(cb_choose_type, pattern='^ct_')],

            ASK_TITLE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, recv_title)
            ],

            NOTE_CONTENT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, recv_note_content)
            ],

            ASK_DATE: [
                CallbackQueryHandler(cb_date_preset, pattern='^date_'),
                MessageHandler(filters.TEXT & ~filters.COMMAND, recv_date_text),
            ],

            ASK_TIME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, recv_time)
            ],

            CONFIRMING: [
                CallbackQueryHandler(cb_confirm, pattern='^confirm_'),
            ],

            BDAY_NAME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, recv_bday_name)
            ],
            BDAY_DATE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, recv_bday_date)
            ],

            SEARCH_QUERY: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, recv_search)
            ],

            CLEANUP_MENU: [
                CallbackQueryHandler(cleanup_delete_selected, pattern='^cleanup_delete_\\d+$'),
                CallbackQueryHandler(cleanup_menu_choice, pattern='^cleanup_'),
            ],

            CLEANUP_COUNT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, cleanup_delete_count)
            ],

            COMPLETE_MENU: [
                CallbackQueryHandler(complete_task_selected, pattern='^complete_'),
            ],
        },
        fallbacks=[
            CommandHandler('cancelar', cancel),
            CommandHandler('start',    cmd_start),
        ],
        allow_reentry=True,
    )

    # ── Handlers simples ──────────────────────────────────────────────────────
    app.add_handler(CommandHandler('start',     cmd_start))
    app.add_handler(CommandHandler('ayuda',     cmd_help))
    app.add_handler(CommandHandler('help',      cmd_help))
    app.add_handler(CommandHandler('hoy',       cmd_hoy))
    app.add_handler(CommandHandler('ver',       cmd_ver))
    app.add_handler(CommandHandler('historial', cmd_historial))
    app.add_handler(CommandHandler('notas',     cmd_notas))
    app.add_handler(CommandHandler('cumples',   cmd_cumples))
    app.add_handler(CommandHandler('auth',      cmd_auth))
    app.add_handler(CommandHandler('pregunta',  cmd_pregunta))
    app.add_handler(CommandHandler('analizar',  cmd_analizar))
    app.add_handler(CommandHandler('gemini_help', cmd_gemini_help))

    # Callbacks del menú principal y de "completado"
    app.add_handler(CallbackQueryHandler(cb_done,      pattern='^done_'))
    app.add_handler(CallbackQueryHandler(cb_main_menu, pattern='^(today|pending|notes|birthdays)$'))

    # Conversación (debe ir DESPUÉS de los handlers simples)
    app.add_handler(conv)

    # ── Manejo de texto libre (solo si no está en conversación) ─────────────────
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_free_text))

    # ── Scheduler de recordatorios (cada 60 segundos) ─────────────────────────
    app.job_queue.run_repeating(
        check_reminders,
        interval=60,
        first=10,
        name='reminder_check'
    )

    return app


async def set_commands(app: Application):
    await app.bot.set_my_commands([
        BotCommand('start',        'Menú principal'),
        BotCommand('nueva',        'Crear tarea, cita, nota o cumpleaños'),
        BotCommand('tarea',        'Nueva tarea rápida'),
        BotCommand('cita',         'Nueva cita (Google Calendar)'),
        BotCommand('nota',         'Guardar una nota'),
        BotCommand('cumple',       'Registrar cumpleaños'),
        BotCommand('hoy',          'Agenda de hoy'),
        BotCommand('ver',          'Todos los pendientes'),
        BotCommand('notas',        'Ver tus notas'),
        BotCommand('buscar',       'Buscar en notas'),
        BotCommand('cumples',      'Cumpleaños próximos'),
        BotCommand('pregunta',     '🤖 Asistente inteligente'),
        BotCommand('analizar',     '📊 Análisis de productividad'),
        BotCommand('gemini_help',  '🤖 Ayuda de Gemini'),
        BotCommand('auth',         'Conectar con Google'),
        BotCommand('ayuda',        'Ayuda'),
    ])


def main():
    app = build_app()

    async def post_init(application: Application):
        await set_commands(application)
        logger.info("Bot iniciado. Esperando mensajes...")

    app.post_init = post_init
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == '__main__':
    main()
