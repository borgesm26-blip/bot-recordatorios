"""
gemini_helper.py — Integración de Google Gemini para el bot

Funcionalidades:
  - Asistente inteligente: responder preguntas sobre tareas y notas
  - Procesamiento de lenguaje natural: entender órdenes complejas
  - Análisis y resumen: analizar tareas y notas automáticamente
"""

import os
import logging
from typing import Optional
import google.generativeai as genai

logger = logging.getLogger(__name__)

# Configurar Gemini
API_KEY = os.getenv('GEMINI_API_KEY', '')
if API_KEY:
    genai.configure(api_key=API_KEY)
    MODEL = genai.GenerativeModel('gemini-pro')
else:
    MODEL = None
    logger.warning("GEMINI_API_KEY no configurada")


def is_gemini_available() -> bool:
    """Verifica si Gemini está disponible."""
    return MODEL is not None and API_KEY != ''


def ask_assistant(question: str, context: Optional[dict] = None) -> Optional[str]:
    """
    Asistente inteligente: responde preguntas sobre tareas, notas, etc.

    Args:
        question: La pregunta del usuario
        context: Contexto opcional (tareas, notas, cumpleaños)

    Returns:
        Respuesta de Gemini o None si hay error
    """
    if not is_gemini_available():
        return None

    try:
        # Construir prompt con contexto si está disponible
        prompt = question

        if context:
            prompt = f"""Eres un asistente personal amigable.
Tienes acceso a la siguiente información del usuario:

TAREAS PENDIENTES:
{context.get('reminders', 'Ninguna')}

NOTAS GUARDADAS:
{context.get('notes', 'Ninguna')}

CUMPLEAÑOS PRÓXIMOS:
{context.get('birthdays', 'Ninguno')}

PREGUNTA DEL USUARIO: {question}

Responde de forma breve, amigable y útil. Si la pregunta está relacionada con sus tareas/notas, usa la información anterior."""

        try:
            response = MODEL.generate_content(
                prompt,
                generation_config=genai.types.GenerationConfig(
                    max_output_tokens=500,
                    temperature=0.7,
                )
            )

            if response and hasattr(response, 'text') and response.text:
                return response.text.strip()
            else:
                logger.warning(f"Respuesta vacía de Gemini: {response}")
                return None

        except Exception as inner_e:
            logger.error(f"Error llamando a Gemini API: {inner_e}")
            return None

    except Exception as e:
        logger.error(f"Error en ask_assistant: {e}")
        return None


def parse_natural_language(user_input: str) -> Optional[dict]:
    """
    Procesa lenguaje natural para extraer información de tareas.

    Intenta entender: "Recordarme comprar leche mañana a las 9am"
    Y devuelve: {'title': 'comprar leche', 'date': 'mañana', 'time': '9am'}

    Args:
        user_input: Lo que escribió el usuario

    Returns:
        Dict con {title, date, time} o None si no puede procesar
    """
    if not is_gemini_available():
        return None

    try:
        prompt = f"""Extrae información de esta orden en lenguaje natural para crear una tarea:

ORDEN: "{user_input}"

Devuelve un JSON con estos campos (usa "null" si no está claro):
{{
  "title": "descripción breve de la tarea",
  "date": "fecha en texto (hoy, mañana, 15 de mayo, etc.) o null",
  "time": "hora en texto (9am, 14:30, etc.) o null",
  "confidence": 0.0 a 1.0 (qué tan seguro estás de la interpretación)
}}

SOLO devuelve el JSON, sin explicaciones."""

        response = MODEL.generate_content(prompt)

        if response and response.text:
            import json
            # Limpiar el texto (a veces Gemini agrega markdown)
            text = response.text.strip()
            if text.startswith('```'):
                text = text.split('```')[1]
                if text.startswith('json'):
                    text = text[4:]
                text = text.strip()

            data = json.loads(text)

            # Solo devolver si la confianza es alta
            if data.get('confidence', 0) >= 0.7:
                return {
                    'title': data.get('title'),
                    'date': data.get('date'),
                    'time': data.get('time')
                }

        return None

    except Exception as e:
        logger.error(f"Error en parse_natural_language: {e}")
        return None


def summarize_tasks(reminders: list) -> Optional[str]:
    """
    Resumen inteligente de tareas pendientes.

    Args:
        reminders: Lista de recordatorios de la BD

    Returns:
        Resumen legible o None si hay error
    """
    if not is_gemini_available() or not reminders:
        return None

    try:
        # Formatear tareas
        task_text = "\n".join([
            f"- {r['title']} (vencimiento: {r.get('due_datetime', 'N/A')})"
            for r in reminders
        ])

        prompt = f"""Haz un resumen BREVE y motivador de estas tareas pendientes:

{task_text}

Resumen (máximo 3 líneas):"""

        response = MODEL.generate_content(prompt)
        return response.text if response else None

    except Exception as e:
        logger.error(f"Error en summarize_tasks: {e}")
        return None


def analyze_notes(notes: list) -> Optional[str]:
    """
    Análisis inteligente de notas guardadas.

    Args:
        notes: Lista de notas de la BD

    Returns:
        Análisis o None si hay error
    """
    if not is_gemini_available() or not notes:
        return None

    try:
        # Formatear notas
        notes_text = "\n".join([
            f"- {n['title']}: {n.get('content', '')[:100]}..."
            for n in notes[:10]  # Máximo 10 notas
        ])

        prompt = f"""Analiza estas notas personales y dame insights:

{notes_text}

Análisis breve (máximo 3 líneas):"""

        response = MODEL.generate_content(prompt)
        return response.text if response else None

    except Exception as e:
        logger.error(f"Error en analyze_notes: {e}")
        return None


def categorize_task(title: str) -> Optional[str]:
    """
    Sugerir categoría/prioridad para una tarea.

    Args:
        title: Título de la tarea

    Returns:
        Categoría sugerida (ALTA, NORMAL, BAJA) o None
    """
    if not is_gemini_available():
        return None

    try:
        prompt = f"""Basándote en este título de tarea, sugiere una prioridad:
"{title}"

Responde SOLO con una palabra: ALTA, NORMAL o BAJA"""

        response = MODEL.generate_content(prompt)
        text = response.text.strip().upper() if response else None

        if text in ['ALTA', 'NORMAL', 'BAJA']:
            return text

        return None

    except Exception as e:
        logger.error(f"Error en categorize_task: {e}")
        return None
