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
10. **Campaña Mendoza** (`/campaign`): Twilio primer contacto, inbox clasificado, handoff a WhatsApp personal
11. **Demo del bot de reservas** (`/demo`) para mostrar el producto a leads

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
| `TWILIO_ACCOUNT_SID` / `TWILIO_AUTH_TOKEN` | Credenciales Twilio |
| `TWILIO_WHATSAPP_FROM` | Sender prod ej. `whatsapp:+549…` (Sandbox: `whatsapp:+14155238886`) |
| `TWILIO_TEMPLATE_SID` | Content SID plantilla marketing aprobada (`HX…`) |
| `TWILIO_SEND_ENABLED` | `true` = envío live; `false` = dry-run |
| `TWILIO_SEND_DELAY_SECONDS` | Pausa entre mensajes (default `3`) |

## Ejecutar

```bash
.venv\Scripts\uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

| Ruta | Descripción |
|------|-------------|
| http://127.0.0.1:8000 | UI principal — generar leads |
| http://127.0.0.1:8000/campaign | **Dashboard campaña Mendoza · cabañas** (Twilio + handoff) |
| http://127.0.0.1:8000/demo | **Demo interactiva del bot de reservas** (sin Twilio; para mostrar a leads) |
| http://127.0.0.1:8000/admin | Panel CRM |
| http://127.0.0.1:8000/docs | API interactiva (Swagger) |
| http://127.0.0.1:8000/health | Health check |

## Usar la interfaz

### Motor de prospección (modo descubrimiento)

- **Geocodificación**: buscá una dirección, usá presets de Argentina o arrastrá el marcador
- **Foco de prospección**: `Todos los rubros` o **Alojamiento turístico** (cabañas, complejos de departamentos, hoteles — ideal para bot de reservas)
- **IA multi-servicio**: cada lead trae servicio sugerido (bot de reservas, CRM, etc.)
- **Filtros de calidad**: reseñas ≤ 3★, límite por negocio, rating máximo, caché 24 h
- **Resultados agrupados por rubro** con chips para filtrar

**Más leads:** subí `max_places` a 40–60, desactivá caché, ampliá radio, o desmarcá “solo reseñas ≤ 3★”. En modo alojamiento el default sugerido es 40.

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
| **Twilio (campaña)** | Envía plantilla WhatsApp Business a leads depurados (ver abajo) |

**Reglas del primer contacto** (`app/data/outreach_guidelines.py`):

- Remitente: **Gustavo de SofIA** (`OUTREACH_SENDER_*`), nunca el nombre del negocio contactado
- Dolores atribuidos a **reseñas de clientes en Google**
- **2–3 opciones** de solución + pregunta de interés
- **Sin reunión** en el primer mensaje (reunión solo en etapas avanzadas del bot)

Al enviar WhatsApp o email desde la UI, el lead pasa a **1 — Contacto realizado** automáticamente.

### Campaña Mendoza · cabañas + Twilio

Flujo de producto: **Twilio = solo el primer mensaje** → cuando contestan, seguís en **tu WhatsApp personal** (respuestas rápidas en el dashboard). Oferta actual: **bot de reservas ~$19.000/mes**.

#### Dashboard (`/campaign`)

| KPI | Significado |
|-----|-------------|
| En base | Leads del CSV limpio |
| Pendientes de envío | Aún no recibieron el WA de Twilio |
| Enviados | Mensajes live únicos vía Twilio |
| Contestaron | Respondieron al primer mensaje |
| Contactados sin reply | Enviados, todavía no contestaron |

Los KPIs son **clickeables**: abren la misma tabla de leads (con mensajes inbound) filtrada por ese KPI. Botón flotante **↑ KPIs** / cerrar para volver.

**Bases y zonas**

- Upload CSV con nombre de **base** (`base_name`); cada lead guarda `lead_json.base`
- Dropdown **Bases en CRM** (conteos: leads / enviados / pendientes)
- Tras elegir una base: **Zonas ya contactadas** → click abre KPI `sent` filtrado por zona
- **No reenvía** a un `place_id` o teléfono ya contactado en *cualquier* envío live (aunque esté en otra base)

**Inbox de respuestas (clasificación automática)**

Inbound WhatsApp se clasifica en `app/services/reply_classify.py`:

| Señal | Significado |
|-------|-------------|
| Prioridad | Humano o humano después de auto-reply (hay que contestar) |
| Solo auto-reply | Mensajes de ausencia / bots; un humano puede retomar después |
| En seguimiento | Marcaste “Ya contesté” |

- Hilos con humano (o retomó después del auto) **siguen en Prioridad** aunque estén en follow-up, para no perderlos
- Auto-replies tipo hotel (“en un momento respondemos…”) se marcan como auto, no como humano

**Acciones del dashboard**

- Upload/sync CSV, lotes dry-run/live (**Enviar lote** = hasta N pendientes; saltea ya enviados)
- Tabla Contestaron + **Abrir en mi WhatsApp**
- **Respuestas rápidas** de venta (demo, “pásame info”, objeciones, etc.) con `{{nombre}}` / `{{demo_url}}` + Copiar
- Link a **Demo bot** (`/demo`)
- Log técnico de Twilio en un `<details>` colapsado

#### Demo del bot de reservas (`/demo`)

Página para **mostrar el producto** a un dueño de complejo (sin costo Twilio):

| Pieza | Detalle |
|-------|---------|
| UI | Chat + chips (finde, personas, nombre, precio…) + calendario entrada/salida |
| API | `POST /api/demo/session`, `POST /api/demo/chat` |
| Bot | `app/services/demo_booking_bot.py` — OpenAI (`gpt-4o-mini`) + fallback por reglas |
| Sesión | En memoria (~24 turnos); si el server recarga, la UI reinicia sola |
| Complejo | Nombre inventado al azar (no usa lodges reales de la base) |

Compartir con un lead: URL pública (`/demo` detrás de ngrok/Fly). Local solo sirve en tu PC.

#### Pipeline de datos

1. **Barrido:** `python -m scripts.mendoza_cabanas_sweep --mode directory`
2. **ETL limpio** (excluye hoteles/camping/Villa Oliva/Las Leñas/tels malos):  
   `python -m scripts.etl_mendoza_cabanas`  
   → `data/exports/mendoza-cabanas-etl-clean.csv` (~250 leads)
3. Sync al CRM desde el dashboard o `POST /api/campaigns/mendoza-cabanas/sync`

#### Twilio (producción)

1. Sender WhatsApp **+54** ONLINE (no Sandbox US para blast)
2. Plantilla **MARKETING** aprobada: `{{1}}`=nombre, `{{2}}`=zona, precio fijo en el texto  
   Crear/enviar a Meta: `python scripts/create_wa_template.py`
3. `.env`: `TWILIO_WHATSAPP_FROM`, `TWILIO_TEMPLATE_SID`, `TWILIO_SEND_ENABLED=true`
4. Webhook inbound (URL pública): `POST /api/twilio/whatsapp/inbound`  
   Local: túnel (`cloudflared` / ngrok) apuntando al sender en Twilio

#### Envío por lotes

```bash
# Dry-run
python -m scripts.send_mendoza_whatsapp --limit 5

# Live (CLI)
python -m scripts.send_mendoza_whatsapp --live --limit 10

# Lotes hasta N enviados / resto
python scripts/send_mendoza_batches.py --target-sent 100 --batch-size 10
python scripts/send_mendoza_batches.py --remaining-all --batch-size 10
```

Dashboard: botón **Enviar lote vía Twilio**.  
API: `POST /api/campaigns/mendoza-cabanas/send-wa`

#### Programar el resto (Windows)

Tarea: `SofIA-Mendoza-WA-Rest` → `scripts/run_mendoza_remaining.bat`  
Log: `data/exports/mendoza-wa-scheduled.log`  
La PC debe estar encendida y con sesión iniciada a la hora programada.

#### Handoff (después de que contestan)

1. Dashboard → **Prioridad / Contestaron** → Abrir en mi WhatsApp / Usar nombre  
2. Sección **Respuestas rápidas** → Copiar pitch de seguimiento (incluye link a `/demo`)  
3. No responder por Twilio (ahorra costo por mensaje)

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
| 1 | `contacted` | Contacto realizado (Twilio enviado) |
| 2 | `responded` | Respondió (por contestar vos) |
| 3 | `follow_up` | En seguimiento (ya contestaste) |
| 4 | `closed` | Cerrado |
| 5 | `discarded` | Descartado |

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
| `POST` | `/api/outreach/send-campaign` |

### Campaña Mendoza + Twilio

| Método | Ruta |
|--------|------|
| `GET` | `/api/campaigns/mendoza-cabanas/dashboard` |
| `POST` | `/api/campaigns/mendoza-cabanas/sync` |
| `POST` | `/api/campaigns/mendoza-cabanas/upload` |
| `POST` | `/api/campaigns/mendoza-cabanas/send-wa` |
| `GET` | `/api/campaigns/mendoza-cabanas/responded` |
| `GET` | `/api/campaigns/mendoza-cabanas/kpi/{kpi}` |
| `GET` | `/api/campaigns/mendoza-cabanas/bases/{base_name}/sent-zones` |
| `POST` | `/api/campaigns/mendoza-cabanas/handoff` |
| `POST` | `/api/twilio/whatsapp/inbound` |
| `POST` | `/api/twilio/whatsapp/status` |

### Demo bot de reservas

| Método | Ruta |
|--------|------|
| `POST` | `/api/demo/session` |
| `POST` | `/api/demo/chat` |

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
├── routers/         search, geocode, admin, history, outreach, projects, campaigns, twilio_webhooks, demo
├── db/store.py      SQLite: caché, historial, CRM, campaign_sends/messages, bases/zonas
├── services/        places, classifier, geocode, outreach, twilio_whatsapp, mendoza_campaign,
│                    campaign_send, reply_classify, demo_booking_bot
├── data/            services, business_types, cabanas_filter, outreach_guidelines, ar_locations
└── static/          index.html, campaign.html, demo.html, admin.html, js/, css/, sofia-wa-avatar.png
scripts/             etl/sweep/send batches, create_wa_template, run_mendoza_remaining.bat
Dockerfile
fly.toml             Fly.io (región gru) — trial vencido hasta agregar billing
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
   - `NOMINATIM_CONTACT_EMAIL` (opcional)
4. **Apply** → esperar build Docker (3–8 min)

URL típica: `https://review-leads.onrender.com`

Variables ya definidas en `render.yaml`: `OUTREACH_SENDER_*`, `DATABASE_PATH=/tmp/review-leads.db`, health `/health`, `DEMO_PUBLIC_URL`, `DEMO_ACCESS_TOKEN` (auto-generado).

### Demo pública para leads (`/demo`)

1. En Render → Environment → copiá el valor de `DEMO_ACCESS_TOKEN`
2. Link del pitch (único que compartís):
   `https://review-leads.onrender.com/demo?k=<DEMO_ACCESS_TOKEN>`
3. En `/campaign` el campo **URL demo** se completa solo si el server tiene `DEMO_PUBLIC_URL` + token
4. Sin el `?k=` correcto la demo no arranca

### Keep-alive con UptimeRobot (gratis, para que no duerma)

El plan free de Render duerme ~15 min sin tráfico. Para dejarlo “siempre listo”:

1. https://uptimerobot.com → cuenta free
2. **Add New Monitor**
   - Monitor Type: **HTTP(s)**
   - URL: `https://review-leads.onrender.com/health`
   - Interval: **5 minutes**
3. Guardar

UptimeRobot pega cada 5 min → Render no duerme. Costo: $0.

| Qué | Render free |
|-----|-------------|
| Costo | $0 |
| Sleep | Tras ~15 min sin tráfico (~1 min despertar) — mitigar con UptimeRobot |
| SQLite | Efímero en `/tmp` |
| Demo | `/demo?k=…` con token |

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

## Modo directorio (hoteles / rubro)

Además del modo **leads por reseñas**, existe el modo **Listar negocios (directorio)**:

1. Elegí localidad (dropdown o mapa)
2. Rubro específico (ej. **Hoteles**) o foco **Alojamiento turístico**
3. **Listar / generar** → resultados con teléfono, WhatsApp y estado CRM

**Límite:** Google Places no devuelve el 100% de una ciudad (máx. ~20 por consulta/tipo; la app combina tipos y búsquedas de texto hasta `max_places`).

### WhatsApp

- Abrir chat: link `wa.me` con mensaje generado (si Google tiene teléfono)
- Al enviar/abrir WhatsApp, el lead pasa a **Contacto realizado**
- **No** hay auto-respuesta en WhatsApp Web (viola términos de Meta; usar Cloud API oficial si se necesita bot real)

## Retomar el proyecto

```bash
cd review-leads
git pull origin main
.venv\Scripts\activate
pip install -r requirements.txt   # si hubo cambios
.venv\Scripts\uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

1. `.env` con Google + OpenAI + `OUTREACH_SENDER_*`
2. http://127.0.0.1:8000 → modo **Listar negocios** → localidad → rubro **Hoteles** → **Listar / generar**
3. WhatsApp / CRM en http://127.0.0.1:8000/admin
4. Redeploy Fly o Render cuando quieras producción pública

## Pendiente / roadmap

- [x] Deploy en Render free + keep-alive UptimeRobot (`/health` cada 5 min)
- [ ] Volumen persistente o DB externa para CRM permanente
- [ ] Sesiones demo en Redis/SQLite (hoy en memoria; se pierden al reload)
- [ ] Proteger `/campaign` y `/admin` con `DASHBOARD_ACCESS_TOKEN` en producción
- [ ] Email desde web del negocio (Google no expone email)
- [ ] Batch IA — varias reseñas en una llamada OpenAI

## Changelog

| Fecha | Cambio |
|-------|--------|
| Ago 2026 | Clasificación inbound (prioridad / auto-reply), KPIs clickeables, multi-base + no reenvío, demo `/demo` con chips/calendario |
| Ago 2026 | Dashboard `/campaign`, Twilio WA prod, ETL Mendoza, handoff + respuestas rápidas, lotes programados |
| Ago 2026 | Modo directorio: listar hoteles/rubro por localidad + WA + contactado |
| Jun 2026 | Modo descubrimiento multi-rubro, geocodificación AR, filtros gobierno |
| Jun 2026 | Outreach SofIA, reseñas Google, CTA sin reunión, `solution_value` |
| Jun 2026 | Panel `/admin`, Fly.io, fix CRM y `.gitignore` (`app/data/`) |
| Jun 2026 | Auto-estado al contactar, fix contadores CRM, 1 máquina Fly |
