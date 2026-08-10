# SofIA Ops — visión de producto

Empaquetado de lo que ya corre en **review-leads** (campaña cabañas Argentina) como dashboard multi-cliente: cada usuario define *qué* prospectar, envía con freno de gasto, y cierra Priority con demo white-label.

## Lo que ya existe (MVP real)

| Módulo | Hoy en el repo |
|--------|----------------|
| Generación de leads | Places + ETL por zonas / bases (`CABANAS_BASES`, Ola 1/2) |
| CRM campaña | `/campaign` + SQLite (`saved_leads`, `campaign_*`) |
| Envío WhatsApp | Twilio templates, lotes, `CAMPAIGN_SEND_PAUSED` |
| Inbox Priority | Clasificación humano/auto, playbook 3 msgs, `ops_stage` |
| Pitch | Pitch + WhatsApp → demo `?nombre=` en Render |
| Demo oferta | `/demo` bot reservas + vista dueño + `AvailabilitySource` |
| Disponibilidad | CSV (`data/demo_availability/`) + Sheets genérico (env) |

## Flujo del dashboard (5 pantallas conceptuales)

1. **Audiencias** — el usuario define universo (rubro, zonas, exclusiones, nombre de base).
2. **Leads / CRM** — pipeline: pendiente → contactado → respondió → seguimiento → cerrado / perdido.
3. **Campañas WA** — plantillas Meta, dry-run, pause global, saldo Twilio, lotes ≤20.
4. **Inbox Priority** — solo humanos; pitch + demo; etapas ops (`pending|contacted|demo|closed|lost`).
5. **Demo / oferta** — link white-label; bot y conectores según vertical.

## Compradores

- Agencias / growth que arman bases y cobran setup + cierre.
- Dueño de un vertical (como SofIA hoy: bot + prospección a pares).
- Equipos de ventas internas (lista propia; usan inbox + demo).

## De repo único → multi-tenant

| Capa | Hoy | Producto |
|------|-----|----------|
| Tenant | Un ops | Workspace + Twilio por cliente |
| Audiencia | Cabañas AR hardcodeadas | Builder query + zonas + filtros |
| CRM | SQLite local | Cloud + mismos `ops_stage` |
| Envío | Pause + v6 | Caps / créditos |
| Cierre | Pitch + `/demo` | Plantillas de oferta por rubro |
| Disponibilidad | CSV + Sheets adapter | IDs por workspace |

## Orden de construcción (después de validar cierre)

1. Validar conversión Priority (primer cliente cabañas) — **en curso / esperando replies**.
2. Builder de audiencia (sin hardcode de zonas).
3. Multi-workspace + credenciales Twilio aisladas.
4. Plantillas de demo por vertical (no solo reservas).

Sin el cierre, el dashboard multi-tenant no se vende.

## Referencias en código

- Campaña: `app/routers/campaigns.py`, `app/static/js/campaign.js`
- Ops stages: `app/services/campaign_ops.py`
- Inventario: `python -m scripts.list_priority_leads`
- Demo: `app/static/demo.html`, `app/services/demo_booking_bot.py`
- Disponibilidad: `app/services/availability/`
