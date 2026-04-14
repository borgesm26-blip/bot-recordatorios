"""
db.py — Módulo de base de datos SQLite para el bot de recordatorios.
Gestiona: notas, recordatorios/tareas, citas, cumpleaños y configuración.
"""

import sqlite3
import json
import os
import logging
from datetime import datetime, timedelta
from typing import Optional, List, Dict

logger = logging.getLogger(__name__)

DB_PATH = os.getenv('DB_PATH', 'reminders.db')


class Database:
    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        self._init_db()
        logger.info("Base de datos lista en: %s", self.db_path)

    # ─── Conexión ─────────────────────────────────────────────────────────────

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")  # Mejor concurrencia
        return conn

    # ─── Inicialización de tablas ─────────────────────────────────────────────

    def _init_db(self):
        with self._conn() as c:
            c.executescript('''
                -- Notas personales
                CREATE TABLE IF NOT EXISTS notes (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    title       TEXT    NOT NULL,
                    content     TEXT    DEFAULT '',
                    tags        TEXT    DEFAULT '',
                    created_at  TEXT    DEFAULT (datetime('now')),
                    is_read     INTEGER DEFAULT 0
                );

                -- Tareas y citas con múltiples recordatorios
                CREATE TABLE IF NOT EXISTS reminders (
                    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
                    title               TEXT    NOT NULL,
                    description         TEXT    DEFAULT '',
                    type                TEXT    DEFAULT 'task',   -- 'task' | 'appointment'
                    due_datetime        TEXT,                      -- ISO 8601 UTC
                    reminder_1_dt       TEXT,                      -- recordatorio anticipado
                    reminder_2_dt       TEXT,                      -- recordatorio 1h antes (citas)
                    reminder_due_dt     TEXT,                      -- al momento del evento
                    sent_1              INTEGER DEFAULT 0,
                    sent_2              INTEGER DEFAULT 0,
                    sent_due            INTEGER DEFAULT 0,
                    is_completed        INTEGER DEFAULT 0,
                    google_id           TEXT,
                    created_at          TEXT    DEFAULT (datetime('now'))
                );

                -- Cumpleaños con recordatorio anual
                CREATE TABLE IF NOT EXISTS birthdays (
                    id              INTEGER PRIMARY KEY AUTOINCREMENT,
                    name            TEXT NOT NULL,
                    birth_date      TEXT NOT NULL,   -- YYYY-MM-DD
                    notes           TEXT DEFAULT '',
                    google_event_id TEXT,
                    created_at      TEXT DEFAULT (datetime('now'))
                );

                -- Configuración general del bot (clave-valor)
                CREATE TABLE IF NOT EXISTS settings (
                    key   TEXT PRIMARY KEY,
                    value TEXT
                );
            ''')
            c.commit()

    # ═══════════════════════════════════════════════════════════════════════════
    # NOTAS
    # ═══════════════════════════════════════════════════════════════════════════

    def add_note(self, title: str, content: str = '', tags: str = '') -> int:
        """Guarda una nota. Devuelve el ID creado."""
        with self._conn() as c:
            cur = c.execute(
                'INSERT INTO notes (title, content, tags) VALUES (?, ?, ?)',
                (title.strip(), content.strip(), tags.strip())
            )
            c.commit()
            return cur.lastrowid

    def get_notes(self, limit: int = 10, offset: int = 0, search: str = None) -> List[Dict]:
        """Lista notas. Opcional: búsqueda por texto."""
        with self._conn() as c:
            if search:
                q = f'%{search}%'
                rows = c.execute(
                    '''SELECT * FROM notes
                       WHERE title LIKE ? OR content LIKE ? OR tags LIKE ?
                       ORDER BY created_at DESC LIMIT ? OFFSET ?''',
                    (q, q, q, limit, offset)
                ).fetchall()
            else:
                rows = c.execute(
                    'SELECT * FROM notes ORDER BY created_at DESC LIMIT ? OFFSET ?',
                    (limit, offset)
                ).fetchall()
        return [dict(r) for r in rows]

    def count_notes(self) -> int:
        with self._conn() as c:
            return c.execute('SELECT COUNT(*) FROM notes').fetchone()[0]

    def mark_note_read(self, note_id: int):
        with self._conn() as c:
            c.execute('UPDATE notes SET is_read = 1 WHERE id = ?', (note_id,))
            c.commit()

    def delete_note(self, note_id: int):
        with self._conn() as c:
            c.execute('DELETE FROM notes WHERE id = ?', (note_id,))
            c.commit()

    # ═══════════════════════════════════════════════════════════════════════════
    # RECORDATORIOS (TAREAS Y CITAS)
    # ═══════════════════════════════════════════════════════════════════════════

    def add_reminder(
        self,
        title: str,
        description: str,
        due_dt: datetime,
        reminder_type: str = 'task',
        advance_minutes: int = 60,
        google_id: str = None
    ) -> int:
        """
        Agrega un recordatorio calculando automáticamente los tiempos de aviso.

        Para tareas:
          - Aviso 1: advance_minutes antes
          - Aviso al momento de la tarea

        Para citas:
          - Aviso 1: 1 día antes
          - Aviso 2: 1 hora antes
          - Aviso al momento de la cita
        """
        if due_dt.tzinfo is not None:
            # Convertir a UTC naive para almacenar
            import pytz
            due_utc = due_dt.astimezone(pytz.utc).replace(tzinfo=None)
        else:
            due_utc = due_dt

        if reminder_type == 'appointment':
            r1 = (due_utc - timedelta(days=1)).isoformat()
            r2 = (due_utc - timedelta(hours=1)).isoformat()
        else:  # task
            r1 = (due_utc - timedelta(minutes=advance_minutes)).isoformat()
            r2 = None

        r_due = due_utc.isoformat()

        with self._conn() as c:
            cur = c.execute(
                '''INSERT INTO reminders
                   (title, description, type, due_datetime,
                    reminder_1_dt, reminder_2_dt, reminder_due_dt, google_id)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
                (title.strip(), description.strip(), reminder_type,
                 due_utc.isoformat(), r1, r2, r_due, google_id)
            )
            c.commit()
            return cur.lastrowid

    def get_due_reminders(self) -> List[Dict]:
        """
        Devuelve recordatorios que tienen algún aviso pendiente de enviar y cuya
        hora ya llegó. El scheduler llama esto cada minuto.
        """
        now = datetime.utcnow().isoformat()
        with self._conn() as c:
            rows = c.execute(
                '''SELECT * FROM reminders
                   WHERE is_completed = 0
                     AND (
                       (sent_1   = 0 AND reminder_1_dt   IS NOT NULL AND reminder_1_dt   <= ?)
                    OR (sent_2   = 0 AND reminder_2_dt   IS NOT NULL AND reminder_2_dt   <= ?)
                    OR (sent_due = 0 AND reminder_due_dt IS NOT NULL AND reminder_due_dt <= ?)
                     )
                   ORDER BY due_datetime ASC''',
                (now, now, now)
            ).fetchall()
        return [dict(r) for r in rows]

    def mark_sent(self, rid: int, field: str):
        """Marca uno de los campos sent_1, sent_2, sent_due."""
        if field not in ('sent_1', 'sent_2', 'sent_due'):
            return
        with self._conn() as c:
            c.execute(f'UPDATE reminders SET {field} = 1 WHERE id = ?', (rid,))
            c.commit()

    def complete_reminder(self, rid: int):
        with self._conn() as c:
            c.execute('UPDATE reminders SET is_completed = 1 WHERE id = ?', (rid,))
            c.commit()

    def get_pending_reminders(self) -> List[Dict]:
        """Lista todos los recordatorios futuros no completados."""
        now = datetime.utcnow().isoformat()
        with self._conn() as c:
            rows = c.execute(
                '''SELECT * FROM reminders
                   WHERE is_completed = 0 AND due_datetime >= ?
                   ORDER BY due_datetime ASC LIMIT 20''',
                (now,)
            ).fetchall()
        return [dict(r) for r in rows]

    def get_reminders_today(self) -> List[Dict]:
        """Lista recordatorios de hoy."""
        today_start = datetime.utcnow().replace(hour=0, minute=0, second=0).isoformat()
        today_end   = datetime.utcnow().replace(hour=23, minute=59, second=59).isoformat()
        with self._conn() as c:
            rows = c.execute(
                '''SELECT * FROM reminders
                   WHERE is_completed = 0
                     AND due_datetime BETWEEN ? AND ?
                   ORDER BY due_datetime ASC''',
                (today_start, today_end)
            ).fetchall()
        return [dict(r) for r in rows]

    def delete_reminder(self, rid: int):
        with self._conn() as c:
            c.execute('DELETE FROM reminders WHERE id = ?', (rid,))
            c.commit()

    # ═══════════════════════════════════════════════════════════════════════════
    # CUMPLEAÑOS
    # ═══════════════════════════════════════════════════════════════════════════

    def add_birthday(self, name: str, birth_date: str,
                     notes: str = '', google_event_id: str = None) -> int:
        """Agrega un cumpleaños. birth_date debe ser 'YYYY-MM-DD'."""
        with self._conn() as c:
            cur = c.execute(
                'INSERT INTO birthdays (name, birth_date, notes, google_event_id) VALUES (?, ?, ?, ?)',
                (name.strip(), birth_date, notes.strip(), google_event_id)
            )
            c.commit()
            return cur.lastrowid

    def get_all_birthdays(self) -> List[Dict]:
        with self._conn() as c:
            rows = c.execute(
                'SELECT * FROM birthdays ORDER BY substr(birth_date, 6)'
            ).fetchall()
        return [dict(r) for r in rows]

    def get_upcoming_birthdays(self, days: int = 30) -> List[Dict]:
        """Devuelve cumpleaños en los próximos N días, con días restantes."""
        all_bds = self.get_all_birthdays()
        today = datetime.utcnow().date()
        upcoming = []

        for bd in all_bds:
            try:
                raw = datetime.strptime(bd['birth_date'], '%Y-%m-%d').date()
                this_year = raw.replace(year=today.year)
                if this_year < today:
                    this_year = this_year.replace(year=today.year + 1)
                delta = (this_year - today).days
                if 0 <= delta <= days:
                    bd['days_until'] = delta
                    bd['next_date']  = this_year.isoformat()
                    upcoming.append(bd)
            except (ValueError, TypeError):
                pass

        return sorted(upcoming, key=lambda x: x['days_until'])

    def delete_birthday(self, bid: int):
        with self._conn() as c:
            c.execute('DELETE FROM birthdays WHERE id = ?', (bid,))
            c.commit()

    # ═══════════════════════════════════════════════════════════════════════════
    # CONFIGURACIÓN
    # ═══════════════════════════════════════════════════════════════════════════

    def set_setting(self, key: str, value: str):
        with self._conn() as c:
            c.execute(
                'INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)',
                (key, str(value))
            )
            c.commit()

    def get_setting(self, key: str, default: str = None) -> Optional[str]:
        with self._conn() as c:
            row = c.execute(
                'SELECT value FROM settings WHERE key = ?', (key,)
            ).fetchone()
        return row['value'] if row else default
