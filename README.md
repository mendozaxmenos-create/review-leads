# Review Leads

App para buscar reseñas de Google en una zona geográfica, clasificarlas con IA y detectar leads potenciales para tus proyectos.

## Qué hace

1. Define un punto central (lat/lng) y un radio en km
2. Busca negocios cercanos vía **Google Places API**
3. Obtiene sus reseñas
4. Clasifica cada reseña con **OpenAI** según tu proyecto/servicio
5. Devuelve leads ordenados por relevancia (`high`, `medium`, `low`)

## Requisitos

- Python 3.11+
- [Google Places API (New)](https://developers.google.com/maps/documentation/places/web-service/overview) habilitada
- API key de OpenAI

## Setup

```bash
cd C:\Users\gusta\Projects\review-leads
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```

Edita `.env` con tus claves:

```
GOOGLE_PLACES_API_KEY=tu_clave
OPENAI_API_KEY=tu_clave
```

## Ejecutar

```bash
uvicorn app.main:app --reload
```

## Usar la interfaz (sin código)

1. Configurá `.env` con tus API keys (ver Setup)
2. Ejecutá el servidor:

```bash
uvicorn app.main:app --reload
```

3. Abrí **http://localhost:8000** en el navegador

Desde la UI podés:
- Buscar una dirección o elegir el punto en el mapa
- Ajustar el radio en km
- Elegir el servicio que ofrecés
- Buscar leads y seleccionarlos con checkbox
- Exportar los seleccionados a CSV

### Contactos y mensajes

- Cada lead muestra **teléfono, web y Google Maps** (si Google los tiene)
- **Escribir mensaje**: genera un mensaje listo para WhatsApp/email
- **Bot de ventas**: simula conversación para ofrecer y cerrar el lead
- **Mensajes seleccionados**: genera mensajes para todos los leads marcados
- Si la categoría no encaja o hay pocos leads, la app **sugiere otras categorías** para buscar

La documentación de la API sigue en http://localhost:8000/docs

## Servicios disponibles

`GET /api/projects` lista los servicios que podés ofrecer:

| ID | Servicio |
|---|---|
| `ai` | Soluciones con IA |
| `booking-bot` | Bot de reservas |
| `crm` | CRM a medida |
| `it-solutions` | Soluciones informáticas |
| `apps` | Apps y desarrollo web |
| `cursor-dev` | Desarrollo ágil con Cursor |

Podés buscar leads pasando `project_id` en lugar de escribir la descripción manualmente.

## Ejemplo de búsqueda

Con un servicio predefinido:

```bash
curl -X POST http://localhost:8000/api/search ^
  -H "Content-Type: application/json" ^
  -d "{\"center\":{\"lat\":-34.6037,\"lng\":-58.3816},\"radius_km\":2,\"business_type\":\"restaurant\",\"project_id\":\"booking-bot\",\"max_places\":10}"
```

O con descripción custom:

```bash
curl -X POST http://localhost:8000/api/search ^
  -H "Content-Type: application/json" ^
  -d "{\"center\":{\"lat\":-34.6037,\"lng\":-58.3816},\"radius_km\":2,\"business_type\":\"restaurant\",\"max_places\":10,\"project_description\":\"Desarrollo apps de delivery y pedidos online para restaurantes\",\"lead_criteria\":\"Quejas sobre demoras, falta de app propia o mal servicio de delivery\"}"
```

## Tipos de negocio (Google Places)

Algunos valores válidos para `business_type`: `restaurant`, `cafe`, `gym`, `store`, `hair_salon`, `dentist`, `real_estate_agency`.

[Lista completa de tipos](https://developers.google.com/maps/documentation/places/web-service/place-types)

## Próximos pasos sugeridos

- UI web (mapa + filtros + exportar CSV)
- Cache de resultados para reducir costos de API
- Perfiles de proyecto guardados (varios servicios a vender)
- Filtro por rating mínimo del negocio o de la reseña
