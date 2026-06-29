# Review Leads

App para buscar reseñas de Google en una zona geográfica, clasificarlas con IA y detectar leads potenciales para tus proyectos (SofIA / desarrollo con Cursor).

| Entorno | URL / estado |
|---------|----------------|
| **Local** | http://127.0.0.1:8000 — funcional |
| **Fly.io** | https://review-leads.fly.dev/ — **suspendido** (trial terminado; requiere tarjeta o redeploy) |
| **Render** | Alternativa free documentada abajo |
| **Repo** | https://github.com/schejtergustavo/review-leads |

## Qué hace

1. Define un punto central (mapa, geocodificación o presets de Argentina)
2. Busca negocios cercanos en **todos los rubros** vía **Google Places API (New)**
3. Obtiene reseñas y contactos (teléfono, web, Maps)
4. Clasifica cada reseña con **OpenAI** y detecta automáticamente qué servicio encaja
5. **Excluye** entidades no prospectables (comisarías, municipalidades, etc.); **incluye** estudios de abogados y negocios privados
6. **Agrupa por negocio** y por **rubro** en la UI; extrae temas de queja
7. Devuelve leads con pitch, valor de la solución y reseñas en español
8. Genera mensajes de outreach (WhatsApp / email) y simula conversación con bot de ventas
9. **CRM** en `/admin` con pipeline de estados

## Requisitos

- Python 3.11+
- [Google Places API (New)](https://developers.google.com/maps/documentation/places/web-service/overview) habilitada
- API key de OpenAI

## Setup local

```bash
cd review-leads
python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # Linux/macOS
pip install -r requirements.txt
copy .env.example .env          # Windows
# cp .env.example .env          # Linux/macOS
```

Editá `.env` (ver `.env.example`):

| Variable | Descripción |
|----------|-------------|
| `GOOGLE_PLACES_API_KEY` | Google Places API (New) |
| `OPENAI_API_KEY` | Clasificación y mensajes |
| `OPENAI_MODEL` | Default: `gpt-4o-mini` |
| `DATABASE_PATH` | Default local: `data/review-leads.db` |
| `NOMINATIM_CONTACT_EMAIL` | Email para geocodificación OSM (recomendado) |
| `OUTREACH_SENDER_NAME` | Remitente outreach (default: `Gustavo`) |
| `OUTREACH_SENDER_COMPANY` | Empresa remitente (default: `SofIA`) |

## Ejecutar

```bash
.venv\Scripts\uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

| Ruta | Descripción |
|------|-------------|
| http://127.0.0.1:8000 | UI principal — generar leads |
| http://127.0.0.1:8000/admin | Panel CRM |
| http://127.0.0.1:8000/docs | API interactiva (Swagger) |
| http://127.0.0.1:8000/health | Health check |

## Usar la interfaz

### Motor de prospección (modo descubrimiento)

- **Geocodificación**: buscá una dirección, usá presets de Argentina o arrastrá el marcador
- **Todos los rubros**: restaurantes, abogados, hoteles, etc. sin elegir manualmente
- **IA multi-servicio**: cada lead trae servicio sugerido (bot de reservas, CRM, etc.)
- **Filtros de calidad**: reseñas ≤ 3★, límite por negocio, rating máximo, caché 24 h
- **Resultados agrupados por rubro** con chips para filtrar

**Más leads:** subí `max_places` a 40–60, desactivá caché, ampliá radio, o desmarcá “solo reseñas ≤ 3★”.

### Cada lead incluye

- Temas de queja en **reseñas de clientes en Google**
- Reseñas en español (traduce si venían en otro idioma)
- **Pitch sugerido** y **Cómo mejora la solución**
- Contactos de Google (teléfono, web, Maps)
- Selector de **estado CRM**

### Outreach

| Acción | Descripción |
|--------|-------------|
| **WhatsApp** | Genera mensaje y abre `wa.me` con el teléfono de Google |
| **Email** | Genera mensaje y abre `mailto:` si hay email (Google casi nunca lo expone) |
| **Bot de ventas** | Simula chat para practicar cierre (**no envía** WhatsApp real) |

**Reglas del primer contacto** (`app/data/outreach_guidelines.py`):

- Remitente: **Gustavo de SofIA** (`OUTREACH_SENDER_*`), nunca el nombre del negocio contactado
- Dolores atribuidos a **reseñas de clientes en Google**
- **2–3 opciones** de solución + pregunta de interés
- **Sin reunión** en el primer mensaje (reunión solo en etapas avanzadas del bot)

Al enviar WhatsApp o email desde la UI, el lead pasa a **1 — Contacto realizado** automáticamente.

### Bot de ventas

1. Clic en **Bot de ventas** en una tarjeta → panel lateral
2. **Iniciar conversación** → la IA escribe el primer mensaje como vendedor
3. Escribís como si fueras el dueño del negocio → **Enviar**
4. El bot avanza: intro → interés → opciones → objeciones → cierre

### Panel CRM (`/admin`)

- Contadores por estado (0–4)
- Filtros por estado, servicio y relevancia
- Cambio de estado, notas, WhatsApp, export CSV

**Pipeline de estados:**

| Código | Valor | Etiqueta |
|--------|-------|----------|
| 0 | `new` | Pendiente de contacto |
| 1 | `contacted` | Contacto realizado |
| 2 | `responded` | Respondió |
| 3 | `closed` | Cerrado |
| 4 | `discarded` | Descartado |

## Modelo de lead (por negocio)

| Campo | Descripción |
|-------|-------------|
| `business_type_label` | Rubro (Restaurante, Abogados, etc.) |
| `recommended_project_id` / `recommended_project_name` | Servicio sugerido por IA |
| `themes` / `theme_counts` | Dolores en reseñas |
| `solution_value` | Cómo la solución mejora esos dolores |
| `suggested_pitch` | Primer contacto sugerido |
| `review_samples` | Reseñas en español con tema |
| `phone` / `website` / `google_maps_url` | Contactos Google |
| `saved_lead_id` / `status` / `notes` | CRM en SQLite |

## API

### Búsqueda

```bash
curl -X POST http://127.0.0.1:8000/api/search \
  -H "Content-Type: application/json" \
  -d "{\"center\":{\"lat\":-32.8895,\"lng\":-68.8458},\"radius_km\":10,\"max_places\":30,\"max_review_rating\":3,\"use_cache\":false}"
```

`business_type` y `project_id` son opcionales (descubrimiento = todos los rubros).

### Geocodificación

| Método | Ruta |
|--------|------|
| `GET` | `/api/geocode/search?q=mendoza` |
| `GET` | `/api/geocode/presets` |

### Outreach

| Método | Ruta |
|--------|------|
| `POST` | `/api/outreach/message` |
| `POST` | `/api/outreach/messages/bulk` |
| `POST` | `/api/outreach/chat` |

### Historial y CRM

| Método | Ruta |
|--------|------|
| `GET` | `/api/history/searches` |
| `GET` | `/api/history/searches/{id}` |
| `PATCH` | `/api/history/leads/{id}` |
| `GET` | `/api/admin/leads` |
| `GET` | `/api/admin/stats` |
| `GET` | `/api/admin/statuses` |

## Servicios predefinidos

`GET /api/projects` — IDs: `ai`, `booking-bot`, `crm`, `it-solutions`, `apps`, `cursor-dev`

Servicios custom: `POST /api/projects/custom` o panel “Servicio propio”.

## Estructura del proyecto

```
app/
├── main.py
├── config.py
├── models/          schemas.py, lead_status.py
├── routers/         search, geocode, admin, history, outreach, projects
├── db/store.py      SQLite: caché, historial, CRM
├── services/        places, classifier, geocode, outreach, category_suggester
├── data/            services, business_types, lead_filters, outreach_guidelines, ar_locations
└── static/          index.html, admin.html, js/, css/
Dockerfile
fly.toml             Fly.io (región gru)
render.yaml          Render Blueprint
```

## Filtros de calidad (API)

| Parámetro | Default | Descripción |
|-----------|---------|-------------|
| `max_review_rating` | `3` | Solo reseñas ≤ este valor. `null` = todas |
| `max_reviews_per_place` | `5` | Máx. reseñas IA por negocio |
| `max_place_rating` | `null` | Solo negocios con rating ≤ valor |
| `max_places` | `24` | Lugares a escanear (8–60) |
| `use_cache` | `true` | Caché 24 h |

## Producción — Fly.io

App: `review-leads` · Región: `gru` · URL: https://review-leads.fly.dev/

### Estado actual (jun 2026)

El **trial de Fly.io terminó**. La app queda suspendida hasta:

1. Agregar tarjeta en https://fly.io/dashboard/billing (pay-as-you-go, ~USD 0–5/mes para esta app), **o**
2. Migrar a Render (abajo)

### Redeploy en Fly (cuando tengas billing)

```bash
fly auth login
fly scale count 1 -a review-leads    # CRÍTICO: 1 sola máquina para SQLite
fly secrets set \
  GOOGLE_PLACES_API_KEY=tu_clave \
  OPENAI_API_KEY=tu_clave \
  OPENAI_MODEL=gpt-4o-mini \
  OUTREACH_SENDER_NAME=Gustavo \
  OUTREACH_SENDER_COMPANY=SofIA \
  DATABASE_PATH=/tmp/review-leads.db \
  DEBUG=false \
  -a review-leads
fly deploy --depot=false -a review-leads
```

Si el builder Depot falla, usá siempre `--depot=false`.

### Limitaciones Fly

| Qué | Detalle |
|-----|---------|
| SQLite | Efímero en `/tmp` — CRM/historial se pierde al reiniciar |
| Multi-máquina | **No usar** — cada máquina tiene su propia DB |
| Cold start | ~30–60 s tras inactividad (con `min_machines_running = 1` reduce) |

Persistencia real: volumen Fly en `/data` o PostgreSQL externo.

## Producción — Render (free, sin tarjeta)

1. https://render.com → login con GitHub
2. **New → Blueprint** → repo `schejtergustavo/review-leads`
3. Completar secrets que pide `render.yaml`:
   - `GOOGLE_PLACES_API_KEY`
   - `OPENAI_API_KEY`
4. **Apply** → esperar build Docker (3–8 min)

Variables ya definidas en `render.yaml`: `OUTREACH_SENDER_*`, `DATABASE_PATH=/tmp/review-leads.db`, health `/health`.

| Qué | Render free |
|-----|-------------|
| Costo | $0 |
| Sleep | Tras ~15 min sin tráfico (~1 min despertar) |
| SQLite | Efímero en `/tmp` |

## Docker local

```bash
docker build -t review-leads .
docker run -p 8000:8000 --env-file .env -v review-leads-data:/app/data review-leads
```

## Costos y rendimiento

- Descubrimiento: ~15 rubros × lugares por rubro + detalle con reseñas
- 1 reseña clasificada = 1 llamada OpenAI
- 24–30 lugares ≈ 1–3 minutos
- WhatsApp: link `wa.me` con teléfono real de Google (no inventado por IA)

## Retomar el proyecto

```bash
cd review-leads
git pull origin main
.venv\Scripts\activate
pip install -r requirements.txt   # si hubo cambios
.venv\Scripts\uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

1. `.env` con Google + OpenAI + `OUTREACH_SENDER_*`
2. http://127.0.0.1:8000 → zona → **Generar leads** (desactivar caché para probar cambios)
3. WhatsApp / CRM en http://127.0.0.1:8000/admin
4. Redeploy Fly o Render cuando quieras producción pública

## Pendiente / roadmap

- [ ] Reactivar Fly.io (tarjeta) **o** deploy en Render
- [ ] Volumen persistente o DB externa para CRM permanente
- [ ] Email desde web del negocio (Google no expone email)
- [ ] Batch IA — varias reseñas en una llamada OpenAI

## Changelog

| Fecha | Cambio |
|-------|--------|
| Jun 2026 | Modo descubrimiento multi-rubro, geocodificación AR, filtros gobierno |
| Jun 2026 | Outreach SofIA, reseñas Google, CTA sin reunión, `solution_value` |
| Jun 2026 | Panel `/admin`, Fly.io, fix CRM y `.gitignore` (`app/data/`) |
| Jun 2026 | Auto-estado al contactar, fix contadores CRM, 1 máquina Fly |
