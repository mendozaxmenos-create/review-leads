from dataclasses import dataclass


@dataclass(frozen=True)
class ServiceProfile:
    id: str
    name: str
    description: str
    lead_criteria: str
    suggested_business_types: list[str]


SERVICE_PROFILES: list[ServiceProfile] = [
    ServiceProfile(
        id="ai",
        name="Soluciones con IA",
        description=(
            "Automatización e inteligencia artificial a medida: asistentes virtuales, "
            "análisis de datos, generación de contenido, chatbots inteligentes y "
            "optimización de procesos con IA."
        ),
        lead_criteria=(
            "Quejas sobre procesos manuales lentos, falta de atención al cliente, "
            "pérdida de tiempo en tareas repetitivas, necesidad de responder más rápido, "
            "o menciones de que el negocio está desactualizado tecnológicamente."
        ),
        suggested_business_types=["restaurant", "store", "real_estate_agency", "lawyer", "accounting"],
    ),
    ServiceProfile(
        id="booking-bot",
        name="Bot de reservas",
        description=(
            "Bot automatizado para gestionar reservas, turnos y citas por WhatsApp, web o redes. "
            "Reduce llamadas perdidas, confirmaciones manuales y no-shows."
        ),
        lead_criteria=(
            "Quejas sobre no poder reservar, teléfono siempre ocupado, demoras para conseguir turno, "
            "mala organización de citas, doble reserva, o dificultad para contactar al negocio."
        ),
        suggested_business_types=["restaurant", "hair_salon", "spa", "dentist", "gym", "doctor"],
    ),
    ServiceProfile(
        id="crm",
        name="CRM a medida",
        description=(
            "Sistemas CRM personalizados para seguimiento de clientes, pipeline de ventas, "
            "historial de contactos, recordatorios y reportes para equipos comerciales."
        ),
        lead_criteria=(
            "Quejas sobre seguimiento deficiente, clientes olvidados, falta de comunicación post-venta, "
            "desorganización del equipo, pérdida de leads o menciones de que no devuelven llamadas."
        ),
        suggested_business_types=["real_estate_agency", "car_dealer", "insurance_agency", "lawyer", "store"],
    ),
    ServiceProfile(
        id="it-solutions",
        name="Soluciones informáticas",
        description=(
            "Consultoría y desarrollo IT: infraestructura, integraciones, migraciones, "
            "soporte técnico, automatización de workflows y modernización de sistemas legacy."
        ),
        lead_criteria=(
            "Problemas con sistemas que fallan, software lento o viejo, falta de integración entre herramientas, "
            "pérdida de datos, errores técnicos recurrentes o necesidad de digitalizar procesos en papel."
        ),
        suggested_business_types=["store", "accounting", "lawyer", "real_estate_agency", "hospital"],
    ),
    ServiceProfile(
        id="apps",
        name="Apps y desarrollo web",
        description=(
            "Desarrollo de aplicaciones móviles, plataformas web, e-commerce, paneles de administración "
            "y productos digitales a medida."
        ),
        lead_criteria=(
            "Quejas sobre no tener app propia, web desactualizada o inexistente, mala experiencia online, "
            "no poder pedir por internet, checkout complicado o dependencia excesiva de terceros (Rappi, etc.)."
        ),
        suggested_business_types=["restaurant", "store", "gym", "cafe", "bakery"],
    ),
    ServiceProfile(
        id="cursor-dev",
        name="Desarrollo ágil con Cursor",
        description=(
            "Desarrollo de software rápido y económico usando IA asistida (Cursor): MVPs, prototipos, "
            "features nuevas, integraciones y productos digitales en tiempo récord."
        ),
        lead_criteria=(
            "Menciones de presupuestos altos de desarrollo, proyectos que nunca arrancan, "
            "necesidad urgente de una solución digital, o frustración con proveedores de software lentos."
        ),
        suggested_business_types=["store", "restaurant", "startup", "real_estate_agency", "gym"],
    ),
]

_PROFILES_BY_ID = {profile.id: profile for profile in SERVICE_PROFILES}

DISCOVERY_INTRO = (
    "Estudio de desarrollo con Cursor (IA asistida): software a medida, automatizaciones, "
    "bots de WhatsApp, CRMs, apps web/móvil, integraciones e IA aplicada a cualquier proceso digital."
)


def get_profile(profile_id: str) -> ServiceProfile | None:
    profile = _PROFILES_BY_ID.get(profile_id)
    if profile:
        return profile
    from app.db.store import get_store

    return get_store().get_custom_profile(profile_id)


def list_profiles() -> list[ServiceProfile]:
    return list(SERVICE_PROFILES)


def list_all_profiles() -> list[ServiceProfile]:
    from app.db.store import get_store

    return list(SERVICE_PROFILES) + get_store().list_custom_projects()


def catalog_for_discovery() -> list[dict[str, str]]:
    return [
        {
            "id": profile.id,
            "name": profile.name,
            "description": profile.description,
            "lead_criteria": profile.lead_criteria,
        }
        for profile in list_all_profiles()
    ]
