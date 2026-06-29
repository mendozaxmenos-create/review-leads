"""Guías de tono y CTA para mensajes de prospección."""

GOOGLE_REVIEWS_SOURCE_RULES = """
Fuente de los dolores (OBLIGATORIO aclararlo):
- Las quejas/dolores vienen de reseñas públicas de clientes en Google Maps / Google (no de suposiciones ni experiencia personal)
- Mencioná explícitamente la fuente, ej: "revisando reseñas de clientes en Google", "en Google algunos clientes comentan que…"
- Tono respetuoso: no acusar al negocio ni citar reseñas textualmente de forma agresiva
- No inventes quejas que no estén en los temas/reseñas provistas
""".strip()

FIRST_CONTACT_RULES = """
Estructura del primer mensaje (en este orden):
1. Saludo y presentación del vendedor
2. Mención breve y respetuosa de quejas de clientes en Google (sin citar reseñas de forma invasiva)
3. 2-3 opciones concretas de solución (qué pueden implementar y qué mejora aporta cada una)
4. Cierre con pregunta de interés abierta, ej: "¿Te interesa que te cuente más?" o "¿Alguna de estas opciones te sirve?"

PROHIBIDO en el primer contacto:
- Proponer reunión, videollamada, demo o llamada agendada
- Frases como "¿Le parece bien coordinar una reunión de 15 minutos?"
- CTA que presione a agendar antes de saber si hay interés
- Hablar de dolores sin aclarar que provienen de reseñas de clientes en Google

La reunión o demo es la ÚLTIMA opción: solo ofrecerla si el cliente ya mostró interés explícito
(en un segundo mensaje o más adelante en la conversación).
""".strip()

CONVERSATION_RULES = """
En conversaciones de seguimiento:
- Primero confirmá interés y respondé dudas
- Si retomás los dolores, recordá que salieron de reseñas de clientes en Google
- Ampliá las opciones con detalle según lo que pregunte el cliente
- Solo en etapa avanzada (cliente interesado) podés sugerir reunión breve como opción más, no como único cierre
- Nunca saltes directo a agendar si aún no hubo señales de interés
""".strip()
