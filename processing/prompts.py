SUMMARY_SYSTEM_PROMPT = """Eres un asistente especializado en generar actas de \
reuniones. Genera actas claras, concisas y bien estructuradas en espanol. \
No uses emojis. No inventes informacion que no este en la transcripcion."""

SUMMARY_USER_PROMPT = """A partir de la siguiente transcripcion de una llamada, \
genera un acta de reunion con el siguiente formato exacto en Markdown:

# Acta de Reunion - {fecha}

## Participantes
- Lista de participantes identificados (si no se pueden identificar, indicar \
"No identificados explicitamente")

## Resumen General
Parrafo breve (3-5 oraciones) describiendo el proposito y resultado general de \
la llamada.

## Temas Tratados
### 1. [Nombre del tema]
- Puntos clave discutidos
- Decisiones tomadas (si aplica)

### 2. [Nombre del tema]
- (repetir para cada tema)

## Decisiones Tomadas
- Lista numerada de decisiones concretas acordadas durante la llamada.
- Si no hubo decisiones explicitas, indicar "No se registraron decisiones \
explicitas."

## Tareas Pendientes (Action Items)
| # | Tarea | Responsable | Fecha limite |
|---|-------|-------------|-------------|
| 1 | Descripcion de la tarea | Persona (si se menciona) | Fecha (si se menciona) |

Si no se asignaron tareas, indicar "No se asignaron tareas explicitas."

## Notas Adicionales
- Cualquier otro punto relevante mencionado que no encaje en las secciones \
anteriores.
- Si no hay notas adicionales, omitir esta seccion.

---
Transcripcion:
{transcription}"""
