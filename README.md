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
- **Mensajes masivos** para leads seleccionados
- **Sugerencias de categoría** cuando hay pocos leads o la categoría no encaja

## Modelo de lead (por negocio)

Cada lead representa **un negocio**, no una reseña suelta:

| Campo | Descripción |
|-------|-------------|
| `themes` | Etiquetas de dolor ordenadas por frecuencia |
| `theme_counts` | Conteo por tema, ej. `{"Tiempos de espera": 2}` |
| `reviews_count` | Cantidad de reseñas relevantes del negocio |
| `review_samples` | Hasta 3 reseñas con su tema |
| `phone` / `website` / `google_maps_url` | Contactos desde Google Places |

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

Definidos en `app/data/services.py`. Cada uno incluye `suggested_business_types` para las sugerencias de categoría.

## Estructura del proyecto

```
app/
├── main.py                 # FastAPI + UI estática
├── config.py               # Settings desde .env
├── models/schemas.py       # Pydantic (Search, Lead, Outreach)
├── routers/
│   ├── search.py           # POST /api/search — búsqueda y agrupación
│   ├── projects.py         # GET /api/projects
│   └── outreach.py         # Mensajes y bot
├── services/
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

## Costos y rendimiento

- Cada búsqueda llama a Google Places por cada lugar + detalle con reseñas.
- Cada reseña genera **una llamada a OpenAI** para clasificar.
- Búsquedas con 15–20 lugares y ~5 reseñas/lugar pueden tardar 1–3 minutos.
- Las sugerencias de categoría hacen búsquedas adicionales en Google si hay pocos leads.

## Próximos pasos sugeridos

Prioridad alta (impacto inmediato):

1. **Filtro por rating** — solo reseñas ≤ 3 estrellas o negocios con rating bajo (`SearchRequest` + UI)
2. **Reducir costo OpenAI** — pre-filtrar reseñas negativas antes de clasificar; limitar reseñas por lugar
3. **Cache** — SQLite/JSON con TTL para no repetir misma zona + categoría + servicio

Producto:

4. **Perfiles de proyecto propios** — CRUD de servicios (hoy hardcodeados en `services.py`)
5. **Persistencia de leads** — historial de búsquedas, estado (contactado, respondió)
6. **Email alternativo** — extraer contacto desde web del negocio (scraping o servicio externo), ya que Google no da email

UX:

7. **Progreso de búsqueda** — “Buscando lugares…”, “Analizando reseña 3/10…”
8. **Pins en mapa** — marcar leads en el mapa Leaflet
9. **Selector de canal en bulk** — WhatsApp vs email al generar mensajes masivos

## Historial reciente

- MVP: búsqueda + clasificación API
- UI web, outreach, bot de ventas, sugerencias de categoría
- Fix parseo de reseñas Google (texto localizado como objeto)
- Leads agrupados por negocio con temas de queja
- Links WhatsApp/email desde contactos reales de Google
