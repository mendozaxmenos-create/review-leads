# Review Leads

App para buscar reseñas de Google en una zona geográfica, clasificarlas con IA y detectar leads potenciales para tus proyectos.

## Qué hace

1. Define un punto central (lat/lng) y un radio en km
2. Busca negocios cercanos vía **Google Places API (New)**
3. Obtiene reseñas y contactos (teléfono, web, Maps)
4. Clasifica cada reseña con **OpenAI** según tu servicio
5. **Agrupa por negocio** y extrae temas de queja (ej. *Tiempos de espera*, *Mala atención*)
6. Devuelve leads ordenados por relevancia (`high`, `medium`, `low`)
7. Genera mensajes de outreach y enlaces directos a WhatsApp con el teléfono de Google

## Requisitos

- Python 3.11+
- [Google Places API (New)](https://developers.google.com/maps/documentation/places/web-service/overview) habilitada
- API key de OpenAI

## Setup

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

# Opcional — persistencia local
DATABASE_PATH=data/review-leads.db
CACHE_TTL_HOURS=24
```

## Ejecutar

```bash
.venv\Scripts\uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

Abrí **http://127.0.0.1:8000** en el navegador. Documentación interactiva: http://127.0.0.1:8000/docs

## Usar la interfaz

Desde la UI podés:

- Buscar una dirección o elegir el punto en el mapa (Leaflet)
- Ajustar radio y cantidad máxima de lugares (1–60)
- Elegir servicio y tipo de negocio
- Ver leads con **temas de queja agrupados** y muestras de reseñas
- Filtrar por relevancia (high / medium / low)
- Seleccionar leads y exportar a CSV
- **WhatsApp**: genera mensaje y abre `wa.me` con el teléfono de Google
- **Email**: genera mensaje y abre `mailto:` si hay email (ver limitación abajo)
- **Bot de ventas**: simula conversación para cerrar el lead
- **Mensajes masivos** para leads seleccionados (WhatsApp o email)
- **Sugerencias de categoría** cuando hay pocos leads o la categoría no encaja
- **Filtros de calidad**: reseñas ≤ 3★, límite por negocio, rating máximo del local
- **Caché** de búsquedas (24 h) para repetir la misma zona sin gastar APIs
- **Servicio propio**: crear/editar/eliminar perfiles de venta custom
- **Historial** de búsquedas anteriores (botón en el header)
- **Estado del lead** en cada tarjeta (Nuevo → Contactado → Cerrado…)
- **Pins en el mapa** con la ubicación de cada lead

## Modelo de lead (por negocio)

Cada lead representa **un negocio**, no una reseña suelta:

| Campo | Descripción |
|-------|-------------|
| `themes` | Etiquetas de dolor ordenadas por frecuencia |
| `theme_counts` | Conteo por tema, ej. `{"Tiempos de espera": 2}` |
| `reviews_count` | Cantidad de reseñas relevantes del negocio |
| `review_samples` | Hasta 3 reseñas con su tema |
| `phone` / `website` / `google_maps_url` | Contactos desde Google Places |
| `lat` / `lng` | Ubicación del negocio (para pins en mapa) |
| `status` / `saved_lead_id` | Estado CRM persistido en SQLite |

La clasificación IA devuelve por reseña: `lead_fit`, `theme`, `reason`, `suggested_pitch`. El backend agrupa por `place_id` en `app/routers/search.py`.

## Contactos y outreach

- **WhatsApp**: el link `wa.me/{teléfono}` se construye en código con el teléfono de Google, no lo inventa la IA.
- **Email**: el link `mailto:` usa el email de Google si existe en el lead.
- **Limitación**: la [Places API (New)](https://developers.google.com/maps/documentation/places/web-service/data-fields) **no expone email** de negocios. Solo teléfono y web. Por eso el botón Email suele estar deshabilitado. El campo `email` está preparado por si Google lo agrega o se integra otra fuente.

Endpoints de outreach (`app/routers/outreach.py`):

| Método | Ruta | Función |
|--------|------|---------|
| `POST` | `/api/outreach/message` | Mensaje para un lead (`channel`: `whatsapp`, `email`, `linkedin`) |
| `POST` | `/api/outreach/messages/bulk` | Mensajes masivos |
| `POST` | `/api/outreach/chat` | Bot de ventas |

## Servicios predefinidos

`GET /api/projects` lista los servicios:

| ID | Servicio |
|---|---|
| `ai` | Soluciones con IA |
| `booking-bot` | Bot de reservas |
| `crm` | CRM a medida |
| `it-solutions` | Soluciones informáticas |
| `apps` | Apps y desarrollo web |
| `cursor-dev` | Desarrollo ágil con Cursor |

Definidos en `app/data/services.py`. Podés agregar servicios propios vía UI o API (ver abajo).

### Servicios custom

| Método | Ruta | Función |
|--------|------|---------|
| `POST` | `/api/projects/custom` | Crear servicio propio |
| `PUT` | `/api/projects/custom/{id}` | Editar servicio propio |
| `DELETE` | `/api/projects/custom/{id}` | Eliminar servicio propio |

Los IDs custom tienen prefijo `custom-`.

## Estructura del proyecto

```
app/
├── main.py                 # FastAPI + UI estática
├── config.py               # Settings desde .env
├── models/schemas.py       # Pydantic (Search, Lead, Outreach)
├── routers/
│   ├── search.py           # POST /api/search — búsqueda, caché y agrupación
│   ├── projects.py         # GET /api/projects + CRUD servicios custom
│   ├── history.py          # Historial de búsquedas y estado de leads
│   └── outreach.py         # Mensajes y bot
├── db/
│   └── store.py            # SQLite: caché, proyectos, historial, leads
├── services/
│   ├── cache.py            # Claves de caché de búsqueda
│   ├── places.py           # Google Places API
│   ├── classifier.py       # Clasificación OpenAI + themes
│   ├── category_suggester.py
│   └── outreach.py         # Mensajes + links de contacto
├── data/
│   ├── services.py         # Perfiles de servicio
│   └── business_types.py
└── static/                 # UI (HTML, CSS, JS, mapa)
```

## Ejemplo de búsqueda (API)

```bash
curl -X POST http://127.0.0.1:8000/api/search ^
  -H "Content-Type: application/json" ^
  -d "{\"center\":{\"lat\":-34.6037,\"lng\":-58.3816},\"radius_km\":2,\"business_type\":\"restaurant\",\"project_id\":\"booking-bot\",\"max_places\":10}"
```

Respuesta incluye `leads[]` con `themes`, `theme_counts`, `review_samples`, etc.

## Tipos de negocio (Google Places)

Valores válidos para `business_type`: `restaurant`, `cafe`, `gym`, `store`, `hair_salon`, `dentist`, `real_estate_agency`, etc.

[Lista completa de tipos](https://developers.google.com/maps/documentation/places/web-service/place-types)

## Filtros de calidad (UI y API)

Parámetros opcionales en `POST /api/search`:

| Parámetro | Default | Descripción |
|-----------|---------|-------------|
| `max_review_rating` | `3` | Solo clasifica reseñas con rating ≤ este valor. `null` = todas |
| `max_reviews_per_place` | `5` | Máximo de reseñas enviadas a OpenAI por negocio (prioriza las peores) |
| `max_place_rating` | `null` | Solo negocios con rating ≤ este valor |
| `use_cache` | `true` | Reutilizar resultado cacheado (misma zona + filtros + servicio) |

La respuesta incluye `reviews_fetched`, `reviews_classified`, `reviews_skipped`, `from_cache` y `search_history_id`.

## Caché, historial y CRM liviano

Persistencia local en SQLite (`data/review-leads.db`, configurable en `.env`):

| Función | API / UI |
|---------|----------|
| Caché de búsquedas (24 h) | `use_cache: true` · checkbox en UI |
| Historial de búsquedas | `GET /api/history/searches` · botón **Historial** |
| Recuperar búsqueda | `GET /api/history/searches/{id}` |
| Estado del lead | `PATCH /api/history/leads/{id}` · selector en cada tarjeta |
| Servicios propios | `POST/PUT/DELETE /api/projects/custom` · panel **Servicio propio** |

Estados de lead: `new`, `contacted`, `responded`, `closed`, `discarded`.

| Método | Ruta | Función |
|--------|------|---------|
| `GET` | `/api/history/searches` | Listar búsquedas guardadas |
| `GET` | `/api/history/searches/{id}` | Recuperar resultado completo |
| `GET` | `/api/history/leads` | Listar leads guardados (`?status=contacted`) |
| `PATCH` | `/api/history/leads/{id}` | Actualizar estado o notas |

## Producción (Render)

El repo incluye `Dockerfile` y `render.yaml` para desplegar en [Render](https://render.com):

1. Conectá el repo `schejtergustavo/review-leads` en Render → **New Blueprint**
2. Agregá las variables secretas:
   - `GOOGLE_PLACES_API_KEY`
   - `OPENAI_API_KEY`
3. Render monta un disco en `/app/data` para SQLite (caché, historial, servicios custom)

Health check: `GET /health`

Alternativa manual con Docker:

```bash
docker build -t review-leads .
docker run -p 8000:8000 --env-file .env -v review-leads-data:/app/data review-leads
```

## Retomar el proyecto

```bash
cd review-leads
.venv\Scripts\activate
.venv\Scripts\uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

1. Configurá `.env` (Google + OpenAI)
2. Abrí http://127.0.0.1:8000
3. Elegí zona, servicio y filtros → **Buscar leads**
4. Revisá **Historial** para búsquedas anteriores
5. Cambiá **Estado** en leads que ya contactaste

La base SQLite (`data/review-leads.db`) guarda caché, servicios custom, historial y estados. Se crea sola al arrancar.

## Costos y rendimiento

- Cada búsqueda llama a Google Places por cada lugar + detalle con reseñas.
- Cada reseña genera **una llamada a OpenAI** para clasificar.
- Búsquedas con 15–20 lugares y ~5 reseñas/lugar pueden tardar 1–3 minutos.
- Las sugerencias de categoría hacen búsquedas adicionales en Google si hay pocos leads.

## Próximos pasos sugeridos

Hecho recientemente:

- Filtros de rating y límite de reseñas por negocio
- Caché SQLite con TTL
- Servicios custom (CRUD)
- Historial de búsquedas + estado de leads
- Pins de leads en mapa, progreso de búsqueda, canal bulk WhatsApp/email

Pendiente:

1. **Email alternativo** — extraer contacto desde web del negocio (Google no publica email)
2. **Dashboard CRM** — vista filtrada de todos los leads guardados por estado
3. **Invalidar caché** — botón para forzar búsqueda fresca sin desactivar caché global
4. **Batch IA** — clasificar varias reseñas en una sola llamada OpenAI

## Historial reciente

- MVP: búsqueda + clasificación API
- UI web, outreach, bot de ventas, sugerencias de categoría
- Fix parseo de reseñas Google (texto localizado como objeto)
- Leads agrupados por negocio con temas de queja
- Links WhatsApp/email desde contactos reales de Google
- Filtros de rating y límite de reseñas por negocio
- SQLite: caché, historial, servicios custom, estado de leads
- Pins en mapa, progreso de búsqueda, bulk por canal
