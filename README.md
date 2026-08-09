# Review Leads / SofIA

App para buscar reseñas de Google, clasificar leads con IA y operar la campaña Mendoza (cabañas): Twilio → handoff WhatsApp personal → demo del bot de reservas.

| Entorno | URL / estado |
|---------|----------------|
| **Producción (Render free)** | https://review-leads.onrender.com — **activo** |
| **Demo para leads** | https://review-leads.onrender.com/demo — **pública** (sin token) |
| **Dashboard campaña** | https://review-leads.onrender.com/campaign?k=`DASHBOARD_ACCESS_TOKEN` |
| **CRM** | https://review-leads.onrender.com/admin?k=`DASHBOARD_ACCESS_TOKEN` |
| **Local** | http://127.0.0.1:8000 |
| **Repo deploy (público)** | https://github.com/mendozaxmenos-create/review-leads (`main`) |
| **Repo original** | https://github.com/schejtergustavo/review-leads — puede no ser clonable por terceros (cuenta GitHub restringida); Render usa el **mirror** |
| **Fly.io** | Suspendido (trial vencido) |

Keep-alive: UptimeRobot → `GET https://review-leads.onrender.com/health` cada 5 min.

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
| `DEMO_PUBLIC_URL` | Origen del pitch/demo. Default/recomendado: `https://review-leads.onrender.com` (sin `/demo`). **No** uses túnel trycloudflare/ngrok acá |
| `ALERT_WHATSAPP_TO` | Tu celular para avisos de Prioridad |
| `ALERT_WHATSAPP_TEMPLATE_SID` | Content SID plantilla Utility de avisos (`HX…`) |
| `ALERT_ON_HUMAN_REPLY` | `true`/`false` — avisos al entrar a Prioridad |
| `ALERT_DASHBOARD_URL` | Link en el aviso (local: `http://127.0.0.1:8000/campaign`) |
| `DASHBOARD_ACCESS_TOKEN` | Si está seteado, protege `/campaign` y `/admin` (`?k=` o header `X-Dashboard-Token`) |
| `DEMO_ACCESS_TOKEN` | Legacy / ignorado — la demo es pública |

## Ejecutar

```bash
.venv\Scripts\uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

| Ruta | Descripción |
|------|-------------|
| http://127.0.0.1:8000 | UI principal — generar leads |
| http://127.0.0.1:8000/campaign | Dashboard campaña Mendoza (local sin token; en prod `?k=`) |
| http://127.0.0.1:8000/demo | Demo interactiva del bot (pública; misma UX que en Render) |
| http://127.0.0.1:8000/admin | Panel CRM |
| http://127.0.0.1:8000/docs | API interactiva (Swagger) |
| http://127.0.0.1:8000/health | Health check |

Túnel local (`scripts\run_demo_tunnel.bat` / cloudflared): **solo** para que Twilio pegue el webhook inbound a tu PC. **No** lo pongas en `DEMO_PUBLIC_URL` ni en el pitch — los leads deben abrir siempre https://review-leads.onrender.com/demo.

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
| En base | Todos los leads del **CRM** (todas las bases: Mendoza + Córdoba + …) |
| Pendientes de envío | En CRM y aún sin envío live Twilio |
| Enviados | Mensajes live únicos vía Twilio |
| Por contestar (humano) | Prioridad: escribió una persona |
| Solo auto-reply | Bot/ausencia; un humano puede retomar después |
| En seguimiento | Marcaste “Ya contesté” |
| Sin reply | Contactados, todavía no contestaron |

Los KPIs son **clickeables**: abren la tabla de leads (con mensajes inbound) filtrada por ese KPI.

**Bases y zonas**

- Upload CSV con nombre de **base** (`base_name`); cada lead guarda `lead_json.base`
- Dropdown **Bases en CRM** (conteos: leads / enviados / pendientes)
- El **inbox** (Prioridad / auto-reply) se filtra por la base elegida; sin base, elegí una antes de operar
- Tras elegir una base: **Zonas ya contactadas** → click abre KPI `sent` filtrado por zona
- **No reenvía** a un `place_id` o teléfono ya contactado en *cualquier* envío live (aunque esté en otra base)

**Inbox de respuestas (clasificación automática)**

Inbound WhatsApp se clasifica en `app/services/reply_classify.py`:

| Señal | Significado |
|-------|-------------|
| Prioridad | Humano o humano después de auto-reply (hay que contestar) |
| Solo auto-reply | Mensajes de ausencia / bots; un humano puede retomar después |
| En seguimiento | Marcaste “Ya contesté” |
| Descartado | STOP / opt-out — **no** aparece en Prioridad |

- Hilos con humano (o retomó después del auto) **siguen en Prioridad** aunque estén en follow-up, para no perderlos
- Auto-replies tipo hotel (“en un momento respondemos…”) se marcan como auto, no como humano
- Tras un **STOP**, mensajes tipo «gracias» no reabren Prioridad ni disparan aviso

**Match de teléfono inbound (importante)**

`find_lead_by_phone_digits` (`app/db/store.py`) asocia el WhatsApp entrante al lead:

1. Primero busca en `campaign_sends` (envíos live ok) — fuente más fiable
2. Luego CRM, **solo** si el lead tiene teléfono real (≥8 dígitos)
3. Nunca matchea `phone` vacío (bug post-Ola 1: `endswith("")` pegaba inbounds a leads sin teléfono recién importados)

El **nombre en el aviso WhatsApp** sale del lead matcheado. Si no lo encontrás en Prioridad: mirá la **base correcta** del complejo real (el inbox filtra por base). Scripts ops locales:

```bash
python -m scripts.scan_recent_inbounds          # últimos inbounds + flags NO_PHONE
python -m scripts.repair_la_ruka_misattribute   # one-shot ejemplo de reatribuir hilo
```

**Avisos al dueño (KPI Prioridad / humano)**

Cuando un inbound **entra** a «Por contestar (humano)» (primera vez del hilo, no cada mensaje), SofIA te avisa por WhatsApp (plantilla Utility). Servicio: `app/services/owner_alerts.py`.

| Variable | Uso |
|----------|-----|
| `ALERT_WHATSAPP_TO` | Tu celular |
| `ALERT_WHATSAPP_TEMPLATE_SID` | Plantilla Utility `sofia_owner_prioridad_v1` (sin esto Meta rechaza fuera de 24h, **63016**). Crear: `python scripts/create_wa_alert_template.py` |
| `ALERT_EMAIL_TO` + `SMTP_*` | Email opcional |
| `ALERT_DASHBOARD_URL` | Link en el mensaje |
| `ALERT_ON_HUMAN_REPLY` | `false` para apagar |

- No avisa si hubo **STOP** / lead descartado
- Solo dispara en la instancia que recibe el webhook Twilio (local + túnel)
- Probar (PowerShell):

```powershell
Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:8000/api/campaigns/mendoza-cabanas/alerts/test" | ConvertTo-Json -Depth 5
```

**Acciones del dashboard**

- Upload/sync CSV, lotes dry-run/live (**Enviar lote** = hasta N pendientes; saltea ya enviados)
- Tabla Contestaron + **Abrir en mi WhatsApp** / **Usar nombre**
- **Respuestas rápidas**: pitch “más info” con `{{nombre}}` / `{{demo_url}}` + Copiar (exige nombre del complejo)
- Cierre del pitch: invitación calmada (“lo vemos con calma”), no cierre de venta duro
- Link a **Demo bot** (`https://review-leads.onrender.com/demo`)
- Log técnico de Twilio en un `<details>` colapsado

#### Demo del bot de reservas (`/demo`)

Página **pública** para que el prospecto pruebe el producto (sin Twilio, sin token):

| Pieza | Detalle |
|-------|---------|
| URL prod | https://review-leads.onrender.com/demo |
| UI | Chat huésped + chips/calendario + panel CRM dueño (simulado) |
| Flujo | Fechas → personas → cabañas → nombre → seña (transferencia / Mercado Pago simulado) |
| API | `POST /api/demo/session`, `/chat`, `/simulate-mp-payment`, `/approve-transfer`, `/reject-transfer` |
| Share | `GET /api/demo/share-link` → siempre URL estable de Render (ignora túneles/localhost en `DEMO_PUBLIC_URL`) |
| Bot | `app/services/demo_booking_bot.py` (máquina de estados + OpenAI opcional; **rechaza off-topic / jailbreak**) |
| Sesión | En memoria; si el server recarga, reiniciá el chat |
| Rate limit | ~20 sesiones nuevas / IP / hora |

**Pitch WhatsApp** (cuando el lead pide más info): plantilla en `/campaign` → “Más info — pitch con demo”.

- Link demo: **https://review-leads.onrender.com/demo** (fijo/estable; no trycloudflare)
- Precio: **$19.000/mes**
- Nombre del complejo: **Usar nombre** / Abrir WhatsApp (obligatorio antes de Copiar)
- Cierre: “si te gustó la demo… lo vemos con calma”

Nunca pegues `http://127.0.0.1` ni un túnel en el pitch: el lead no puede abrirlo (o el link muere al apagar la PC).

#### Pipeline de datos

1. **Barrido:** `python -m scripts.mendoza_cabanas_sweep --mode directory`
2. **ETL limpio** (excluye hoteles/camping/Villa Oliva/Las Leñas/tels malos):  
   `python -m scripts.etl_mendoza_cabanas`  
   → `data/exports/mendoza-cabanas-etl-clean.csv` (~250 leads)
3. Sync al CRM desde el dashboard o `POST /api/campaigns/mendoza-cabanas/sync`

#### Twilio (producción)

1. Sender WhatsApp **+54** ONLINE (no Sandbox US para blast)
2. Plantilla **MARKETING** de primer contacto: `{{1}}`=nombre, `{{2}}`=zona  
   Crear/enviar a Meta: `python scripts/create_wa_template.py`
3. Plantilla **UTILITY** de aviso al dueño (Prioridad): `python scripts/create_wa_alert_template.py` → `ALERT_WHATSAPP_TEMPLATE_SID`
4. `.env`: `TWILIO_WHATSAPP_FROM`, `TWILIO_TEMPLATE_SID`, `TWILIO_SEND_ENABLED=true`, `ALERT_WHATSAPP_TO`, `ALERT_WHATSAPP_TEMPLATE_SID`
5. Webhook inbound (URL pública): `POST /api/twilio/whatsapp/inbound`  
   Local: túnel (`cloudflared` / ngrok) → misma PC donde corre el CRM/SQLite

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
2. Sección **Respuestas rápidas** → Copiar pitch “Más info” (incluye `https://review-leads.onrender.com/demo`)  
3. No responder por Twilio (ahorra costo por mensaje)

### Base Córdoba · cabañas (misma campaña)

Misma campaña / dashboard (`/campaign`), **`base=Córdoba`**. Cobertura v1: **Punilla + Calamuchita** (11 zonas).

Preferí el pipeline genérico (abajo). Legacy: `cordoba_cabanas_sweep` / `etl_cordoba_cabanas`.

### Expansión Argentina · Ola 1 + filtro reservas online

Objetivo: más bases de cabañas **sin quemar Twilio** en alojamientos que ya tienen Booking/Airbnb/motor propio.

**Bases Ola 1** (registro `CABANAS_BASES` en [`app/data/ar_locations.py`](app/data/ar_locations.py)):

| Base CRM | Zonas |
|----------|-------|
| Buenos Aires (interior) | Tandil, Sierra de la Ventana, Villa Ventana |
| San Luis | El Trapiche, Merlo, Potrero de los Funes |
| Salta | Cafayate, Cachi, San Lorenzo |
| Jujuy | Purmamarca, Tilcara, Humahuaca |
| Neuquén | San Martín de los Andes, Villa La Angostura, Villa Traful |
| Río Negro | Bariloche, Circuito Chico, El Bolsón, Las Grutas |

(+ Mendoza y Córdoba en el mismo registro para CLI unificado.)

**Filtro booking** ([`app/services/booking_signals.py`](app/services/booking_signals.py)): hard-exclude en ETL si el `website` es OTA/directorio o el HTML tiene motor (Cloudbeds, Little Hotelier, etc.). Instagram/WhatsApp **no** excluyen. Fallo de fetch ≠ exclude.

```bash
# Listar bases
.venv\Scripts\python -m scripts.cabanas_sweep --list-bases

# Una base: sweep → ETL → CRM
.venv\Scripts\python -m scripts.cabanas_sweep --base "San Luis" --mode directory --max-places 35
.venv\Scripts\python -m scripts.etl_cabanas_base --base "San Luis" --fetch-booking --sync-crm

# Ola 1 completa (orden costo Places)
.venv\Scripts\python -m scripts.run_cabanas_ola1 --max-places 35

# Re-ETL bases viejas (Mendoza/Córdoba) con filtro booking
.venv\Scripts\python -m scripts.etl_cabanas_base --base Mendoza --in data/exports/mendoza-cabanas-ready.csv --fetch-booking --sync-crm
.venv\Scripts\python -m scripts.etl_cabanas_base --base Córdoba --in data/exports/cordoba-cabanas-ready.csv --fetch-booking --sync-crm
```

Salidas: `data/exports/campaign-{Base}.csv`, `*-etl-clean.csv`, `*-etl-quarantine.csv`.  
El envío Twilio **omite** filas con `has_online_booking=yes` y leads `discarded`.

### Base Córdoba · cabañas (legacy CLI)

Salidas: `data/exports/cordoba-cabanas-*.csv`, `cordoba-cabanas-etl-clean.csv`, `campaign-Córdoba.csv`.  
API: `GET /api/campaigns/cordoba-cabanas/zones`, `POST /api/campaigns/cordoba-cabanas`.  
Upload UI: base **Córdoba** → escribe `campaign-Córdoba.csv` **sin** sobrescribir `mendoza-cabanas-etl-clean.csv`.

Zonas: Villa Carlos Paz, Cosquín, La Falda, La Cumbre, Capilla del Monte, Valle Hermoso/Huerta Grande, Villa General Belgrano, Santa Rosa de Calamuchita, Embalse/Rumipal, Los Reartes/Villa Berna, La Cumbrecita.

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
| `GET` | `/api/demo/share-link` |
| `POST` | `/api/demo/session` |
| `POST` | `/api/demo/chat` |
| `POST` | `/api/demo/simulate-mp-payment` |
| `POST` | `/api/demo/approve-transfer` |
| `POST` | `/api/demo/reject-transfer` |

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
├── main.py              rutas HTML + middleware DASHBOARD_ACCESS_TOKEN
├── auth_gate.py         gate /campaign /admin (demo abierta)
├── config.py
├── models/              schemas.py, lead_status.py
├── routers/             search, geocode, admin, history, outreach, projects, campaigns, twilio_webhooks, demo
├── db/store.py          SQLite: caché, historial, CRM, campaign_sends/messages, bases/zonas
├── services/            places, classifier, geocode, outreach, twilio_whatsapp, mendoza_campaign,
│                        campaign_send, reply_classify, owner_alerts, booking_signals, demo_booking_bot
├── data/                services, business_types, cabanas_filter, outreach_guidelines, ar_locations
└── static/              index.html, campaign.html, demo.html, admin.html, js/, css/
scripts/                 cabanas_sweep, etl_cabanas_base, run_cabanas_ola1, mark_booking_discards,
│                        create_wa_template, create_wa_alert_template, sweep/ETL Mendoza+Córdoba legacy
tools/                   cloudflared.exe (túnel local opcional)
Dockerfile
fly.toml                 Fly.io — trial vencido
render.yaml              Blueprint / env de referencia (deploy real suele ser Web Service desde el mirror)
```

## Filtros de calidad (API)

| Parámetro | Default | Descripción |
|-----------|---------|-------------|
| `max_review_rating` | `3` | Solo reseñas ≤ este valor. `null` = todas |
| `max_reviews_per_place` | `5` | Máx. reseñas IA por negocio |
| `max_place_rating` | `null` | Solo negocios con rating ≤ valor |
| `max_places` | `24` | Lugares a escanear (8–60) |
| `use_cache` | `true` | Caché 24 h |

## Producción — Render (activo)

**URL:** https://review-leads.onrender.com  
**Código que despliega Render:** repo público  
https://github.com/mendozaxmenos-create/review-leads · branch `main`

> El repo `schejtergustavo/review-leads` puede devolver 404 a clones anónimos (cuenta GitHub restringida). Por eso el deploy usa el **mirror** `mendozaxmenos-create`.

### Alta / redeploy

1. https://render.com → cuenta con **email** (no hace falta GitHub OAuth)
2. **New → Web Service → Public Git Repository**  
   `https://github.com/mendozaxmenos-create/review-leads`
3. Branch `main` · Runtime **Docker** · Plan **Free** · Health `/health`
4. Env vars mínimas:
   - `OPENAI_API_KEY` (y `GOOGLE_PLACES_API_KEY` si usás búsqueda)
   - `DEMO_PUBLIC_URL=https://review-leads.onrender.com`
   - `DASHBOARD_ACCESS_TOKEN=<secreto largo>` (solo vos)
   - `DATABASE_PATH=/tmp/review-leads.db`
   - `DEBUG=false`
5. Deploy. Tras cambios locales: push al mirror y **Manual Deploy** en Render si no hay auto-deploy.

```powershell
# Push al mirror (cuenta mendozaxmenos-create)
gh auth switch -u mendozaxmenos-create
git push mirror HEAD:main
gh auth switch -u schejtergustavo
```

Remote local típico: `mirror` → `https://github.com/mendozaxmenos-create/review-leads.git`

### URLs de uso diario

| Quién | Link |
|-------|------|
| Lead (pitch) | https://review-leads.onrender.com/demo |
| Vos — campaña | `https://review-leads.onrender.com/campaign?k=<DASHBOARD_ACCESS_TOKEN>` |
| Vos — CRM | `https://review-leads.onrender.com/admin?k=<DASHBOARD_ACCESS_TOKEN>` |
| Health / UptimeRobot | https://review-leads.onrender.com/health |

### Keep-alive UptimeRobot (gratis)

El plan free duerme ~15 min sin tráfico. Monitor HTTP(s) cada **5 minutes** a `/health` → Render no duerme. Costo: $0.

| Qué | Render free |
|-----|-------------|
| Costo | $0 |
| Sleep | Mitigar con UptimeRobot |
| SQLite | Efímero en `/tmp` |
| Demo | `/demo` público |
| Dashboard | Protegido con `DASHBOARD_ACCESS_TOKEN` |

## Producción — Fly.io (legacy)

App `review-leads` · https://review-leads.fly.dev/ — **suspendida** (trial terminado). Preferí Render. Redeploy solo si agregás billing en Fly y `fly scale count 1` (una máquina por SQLite).

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
git pull mirror main          # código de producción / deploy
.venv\Scripts\activate
pip install -r requirements.txt   # si hubo cambios
.venv\Scripts\uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

1. `.env` con Google + OpenAI + `OUTREACH_SENDER_*` + Twilio + `ALERT_WHATSAPP_*` (avisos)
2. Campaña local (CRM en disco): http://127.0.0.1:8000/campaign  
3. Túnel + webhook Twilio apuntando a esa misma instancia  
4. Demo leads (prod): https://review-leads.onrender.com/demo  
5. Tras cambios: `git push mirror HEAD:main` → redeploy Render (demo; el CRM operativo sigue en local)

## Pendiente / roadmap

- [x] Deploy Render free + UptimeRobot keep-alive
- [x] Demo `/demo` pública; dashboards con `DASHBOARD_ACCESS_TOKEN`
- [x] Mirror público `mendozaxmenos-create/review-leads` para deploy (GitHub flaggeado)
- [x] Pitch “más info” con link **Render** estable + nombre obligatorio al copiar
- [x] Base Córdoba Punilla+Calamuchita (misma campaña, `base=Córdoba`)
- [x] Avisos WhatsApp al dueño (plantilla Utility) al entrar a Prioridad
- [x] KPI «En base» = todo el CRM multi-base
- [x] `share-link` / pitch rechazan túneles (trycloudflare, ngrok, localhost) → Render
- [x] Ola 1 multi-provincia (BA interior, San Luis, Salta, Jujuy, Neuquén, Río Negro) + ETL/sync
- [x] Filtro hard `booking_signals` (OTA/motor) + re-ETL Mendoza/Córdoba
- [x] Fix match inbound: no atribuir a leads sin teléfono; priorizar `campaign_sends`
- [ ] **Ola 2:** Chubut, Calafate, TdF, Catamarca, La Rioja, Entre Ríos, Misiones interior
- [ ] Barrido nacional único (solo si Ola 1 valida unit economics)
- [ ] Places `reservable` / Google Reserve en `booking_signals`
- [ ] A/B plantilla WhatsApp y precio post-filtro
- [ ] Cola de envío priorizada en dashboard (sin website / solo WA primero)
- [ ] Volumen persistente o DB externa para CRM permanente
- [ ] Sesiones demo en Redis/SQLite (hoy en memoria; se pierden al reload)
- [ ] Email desde web del negocio (Google no expone email)
- [ ] Batch IA — varias reseñas en una llamada OpenAI

## Changelog

| Fecha | Cambio |
|-------|--------|
| Ago 2026 | Fix match inbound (`find_lead_by_phone_digits`): prioriza envíos live, ignora phone vacío; scripts scan/repair; doc inbox por base |
| Ago 2026 | Ola 1 AR (6 bases), pipeline `cabanas_sweep`/`etl_cabanas_base`, filtro reservas online, re-ETL Mza/Cba |
| Ago 2026 | Demo bot: anti prompt-injection / off-topic (no responde mates, historia, jailbreaks; redirige a la reserva) |
| Ago 2026 | Pitch/demo: `DEMO_PUBLIC_URL` default Render; share-link ignora túneles; docs ops locales vs demo prod |
| Ago 2026 | Avisos WSP Prioridad (`owner_alerts` + plantilla Utility); no alertar post-STOP; KPI En base = CRM multi-base; pitch cierre empático |
| Ago 2026 | Base Córdoba (Punilla+Calamuchita): zonas, sweep/ETL, sync multi-base sin pisar Mendoza |
| Ago 2026 | Render live, demo pública, dashboards con token, mirror deploy, UptimeRobot, pitch más-info |
| Ago 2026 | Demo interactiva (cabañas, seña MP/transferencia simulada), share-link, rate limit |
| Ago 2026 | Clasificación inbound, KPIs clickeables, multi-base + no reenvío |
| Ago 2026 | Dashboard `/campaign`, Twilio WA, ETL Mendoza, handoff + respuestas rápidas |
| Ago 2026 | Modo directorio: listar hoteles/rubro por localidad + WA + contactado |
| Jun 2026 | Modo descubrimiento multi-rubro, geocodificación AR, filtros gobierno |
| Jun 2026 | Outreach SofIA, reseñas Google, CTA sin reunión, `solution_value` |
| Jun 2026 | Panel `/admin`, Fly.io, fix CRM y `.gitignore` |
