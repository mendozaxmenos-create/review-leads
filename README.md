# Review Leads

App para buscar reseñas de Google en una zona geográfica, clasificarlas con IA y detectar leads potenciales para tus proyectos.

**Producción:** https://review-leads.fly.dev/

## Qué hace

1. Define un punto central (mapa, geocodificación o presets de Argentina)
2. Busca negocios cercanos en **todos los rubros** vía **Google Places API (New)**
3. Obtiene reseñas y contactos (teléfono, web, Maps)
4. Clasifica cada reseña con **OpenAI** y detecta automáticamente qué servicio encaja
5. **Excluye** entidades no prospectables (comisarías, municipalidades, etc.)
6. **Agrupa por negocio** y por **rubro** en la UI; extrae temas de queja
7. Devuelve leads con pitch, valor de la solución y reseñas en español
8. Genera mensajes de outreach (WhatsApp / email) y simula conversación con bot de ventas

## Requisitos

- Python 3.11+
- [Google Places API (New)](https://developers.google.com/maps/documentation/places/web-service/overview) habilitada
- API key de OpenAI

## Setup local

```bash
cd review-leads
python -m venv .venv
.venv\Scripts\activate          # Windows
pip install -r requirements.txt
copy .env.example .env          # Windows
```

Edita `.env` con tus claves:

```
GOOGLE_PLACES_API_KEY=tu_clave
OPENAI_API_KEY=tu_clave
OPENAI_MODEL=gpt-4o-mini

# Opcional
DATABASE_PATH=data/review-leads.db
CACHE_TTL_HOURS=24
NOMINATIM_CONTACT_EMAIL=tu@email.com

# Remitente de mensajes (WhatsApp, email, bot)
OUTREACH_SENDER_NAME=Gustavo
OUTREACH_SENDER_COMPANY=SofIA
```

## Ejecutar

```bash
.venv\Scripts\uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

- UI principal: http://127.0.0.1:8000
- Panel CRM: http://127.0.0.1:8000/admin
- API docs: http://127.0.0.1:8000/docs

## Usar la interfaz

### Motor de prospección (modo descubrimiento)

- **Geocodificación**: buscá una dirección, usá presets de Argentina o arrastrá el marcador
- **Todos los rubros**: la búsqueda recorre restaurantes, abogados, hoteles, etc. sin elegir manualmente
- **IA multi-servicio**: cada lead trae `recommended_project_id` (bot de reservas, CRM, etc.)
- **Filtros de calidad**: reseñas ≤ 3★, límite por negocio, rating máximo del local, caché 24 h
- **Resultados agrupados por rubro** con chips para filtrar

### Cada lead incluye

- Temas de queja detectados en reseñas de Google
- Reseñas traducidas al español cuando vienen en otro idioma
- **Pitch sugerido** y **Cómo mejora la solución**
- Contactos de Google (teléfono, web, Maps)
- Estado CRM (pendiente → contacto → respondió → cerrado / descartado)

### Outreach

| Acción | Descripción |
|--------|-------------|
| **WhatsApp** | Genera mensaje y abre `wa.me` con el teléfono de Google |
| **Email** | Genera mensaje y abre `mailto:` si hay email (raro en Google Places) |
| **Bot de ventas** | Simula conversación para practicar el cierre (no envía WhatsApp real) |

**Reglas del primer contacto** (configuradas en `app/data/outreach_guidelines.py`):

- El remitente es **Gustavo de SofIA** (configurable con `OUTREACH_SENDER_*`), no el negocio contactado
- Los dolores se atribuyen explícitamente a **reseñas de clientes en Google**
- Se presentan **2–3 opciones** de solución y se pregunta si hay interés
- **No** se propone reunión en el primer mensaje (solo en etapas avanzadas del bot)

### Panel admin (`/admin`)

Pipeline de estados, notas, mensajes WhatsApp y seguimiento de leads guardados.

## Modelo de lead (por negocio)

| Campo | Descripción |
|-------|-------------|
| `business_type_label` | Rubro comercial (Restaurante, Abogados, etc.) |
| `recommended_project_id` / `recommended_project_name` | Servicio sugerido por la IA |
| `themes` / `theme_counts` | Dolores detectados en reseñas |
| `solution_value` | Cómo la solución mejora esos dolores |
| `suggested_pitch` | Primer contacto sugerido |
| `review_samples` | Reseñas en español con tema |
| `phone` / `website` / `google_maps_url` | Contactos desde Google |
| `status` / `saved_lead_id` | Estado CRM en SQLite |

## API principal

### Búsqueda

```bash
curl -X POST http://127.0.0.1:8000/api/search \
  -H "Content-Type: application/json" \
  -d "{\"center\":{\"lat\":-32.8895,\"lng\":-68.8458},\"radius_km\":10,\"max_places\":30,\"max_review_rating\":3,\"use_cache\":false}"
```

`business_type` y `project_id` son opcionales (modo descubrimiento = todos los rubros).

### Geocodificación

| Método | Ruta | Función |
|--------|------|---------|
| `GET` | `/api/geocode/search?q=mendoza` | Sugerencias de ubicación |
| `GET` | `/api/geocode/presets` | Provincias y zonas de Argentina |

### Outreach

| Método | Ruta | Función |
|--------|------|---------|
| `POST` | `/api/outreach/message` | Mensaje para un lead (`channel`: `whatsapp`, `email`) |
| `POST` | `/api/outreach/messages/bulk` | Mensajes masivos |
| `POST` | `/api/outreach/chat` | Bot de ventas (simulación) |

### Historial y CRM

| Método | Ruta | Función |
|--------|------|---------|
| `GET` | `/api/history/searches` | Listar búsquedas guardadas |
| `GET` | `/api/history/searches/{id}` | Recuperar resultado |
| `PATCH` | `/api/history/leads/{id}` | Actualizar estado o notas |
| `GET` | `/api/admin/leads` | Panel admin — listar leads |

Estados: `0` Pendiente → `1` Contacto → `2` Respondió → `3` Cerrado → `4` Descartado

Al enviar WhatsApp o email desde la UI principal, el lead pasa automáticamente a **Contacto realizado** (`contacted`).

**Importante (Fly.io):** el CRM usa SQLite. Con más de una máquina, cada una tiene su propia base en `/tmp` y los datos no se comparten. Mantené **1 sola máquina** (`fly scale count 1`) o usá un volumen persistente en `/data`.

## Servicios predefinidos

`GET /api/projects` — IDs: `ai`, `booking-bot`, `crm`, `it-solutions`, `apps`, `cursor-dev`

Definidos en `app/data/services.py`. Servicios custom vía UI o `POST /api/projects/custom`.

## Estructura del proyecto

```
app/
├── main.py
├── config.py                    # Settings + outreach_sender_signature()
├── models/
│   ├── schemas.py
│   └── lead_status.py
├── routers/
│   ├── search.py                # Descubrimiento multi-rubro
│   ├── geocode.py
│   ├── admin.py
│   ├── history.py
│   ├── outreach.py
│   └── projects.py
├── db/store.py                  # SQLite: caché, historial, CRM
├── services/
│   ├── places.py                # Google Places + prioriza reseñas en español
│   ├── classifier.py            # Clasificación + detección de servicio
│   ├── geocode.py               # Nominatim + fallback Google
│   └── outreach.py              # Mensajes + bot
├── data/
│   ├── services.py
│   ├── business_types.py
│   ├── lead_filters.py          # Excluye gobierno; permite abogados
│   ├── outreach_guidelines.py   # Tono, Google reviews, CTA
│   └── ar_locations.py          # Presets Argentina
└── static/                      # UI + admin
fly.toml                         # Deploy Fly.io
Dockerfile
```

## Filtros de calidad (API)

| Parámetro | Default | Descripción |
|-----------|---------|-------------|
| `max_review_rating` | `3` | Solo reseñas con rating ≤ este valor. `null` = todas |
| `max_reviews_per_place` | `5` | Máx. reseñas a clasificar por negocio |
| `max_place_rating` | `null` | Solo negocios con rating ≤ este valor |
| `max_places` | `24` | Lugares a escanear (8–60). Más = más leads, más costo |
| `use_cache` | `true` | Reutilizar búsqueda cacheada (24 h) |

## Producción — Fly.io (recomendado)

URL: **https://review-leads.fly.dev/** · Región: `gru` (São Paulo)

### Deploy

```bash
# Instalar CLI: https://fly.io/docs/hands-on/install-flyctl/
fly auth login
fly deploy --depot=false
```

Si el builder Depot falla por timeout, usá siempre `--depot=false`.

### Secrets

```bash
fly secrets set \
  GOOGLE_PLACES_API_KEY=tu_clave \
  OPENAI_API_KEY=tu_clave \
  OPENAI_MODEL=gpt-4o-mini \
  OUTREACH_SENDER_NAME=Gustavo \
  OUTREACH_SENDER_COMPANY=SofIA \
  DATABASE_PATH=/tmp/review-leads.db \
  DEBUG=false
```

### Plan free — limitaciones

| Qué | En free |
|-----|---------|
| Cold start | ~30–60 s tras inactividad |
| SQLite | Efímero en `/tmp` (historial/CRM se pierde al reiniciar máquina) |
| Health check | `/health` — grace period 20 s |

Para persistencia real: volumen Fly o PostgreSQL externo.

### Verificar

```bash
fly status -a review-leads
curl https://review-leads.fly.dev/health
```

## Producción alternativa — Render (free)

Ver sección histórica en commits anteriores. Render apaga el servicio tras 15 min sin tráfico; Fly.io con `auto_start_machines` es la opción actual en prod.

Deploy manual Docker:

```bash
docker build -t review-leads .
docker run -p 8000:8000 --env-file .env -v review-leads-data:/app/data review-leads
```

## Costos y rendimiento

- Modo descubrimiento: ~15 tipos de negocio × lugares por rubro + detalle con reseñas
- Cada reseña clasificada = **1 llamada OpenAI**
- Búsqueda de 24–30 lugares puede tardar 1–3 minutos
- Subí `max_places` a 40–60 y desactivá caché para más resultados

## Retomar el proyecto

```bash
cd review-leads
.venv\Scripts\activate
.venv\Scripts\uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

1. Configurá `.env` (Google + OpenAI + remitente outreach)
2. Abrí http://127.0.0.1:8000 → elegí zona → **Generar leads**
3. Contactá por WhatsApp o usá el bot de ventas para practicar
4. Seguí leads en http://127.0.0.1:8000/admin

## Changelog reciente

- Modo descubrimiento multi-rubro con detección automática de servicio
- Geocodificación Argentina (Nominatim + presets + fallback Google)
- Filtros de entidades no prospectables (gobierno); estudios de abogados sí incluidos
- Agrupación por rubro, `solution_value`, reseñas en español
- Outreach: remitente configurable, dolores atribuidos a Google, CTA por interés (sin reunión inicial)
- Panel admin CRM, deploy Fly.io, fix `.gitignore` para `app/data/`
