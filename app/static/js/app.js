const DEFAULT_CENTER = { lat: -34.6037, lng: -58.3816 };

const BUSINESS_TYPES = [
  { value: "restaurant", label: "Restaurantes" },
  { value: "cafe", label: "Cafés" },
  { value: "hair_salon", label: "Peluquerías" },
  { value: "spa", label: "Spas" },
  { value: "dentist", label: "Dentistas" },
  { value: "gym", label: "Gimnasios" },
  { value: "store", label: "Tiendas" },
  { value: "real_estate_agency", label: "Inmobiliarias" },
  { value: "lawyer", label: "Abogados" },
  { value: "accounting", label: "Contadores" },
  { value: "bakery", label: "Panaderías" },
  { value: "car_dealer", label: "Concesionarios" },
  { value: "doctor", label: "Médicos" },
  { value: "insurance_agency", label: "Seguros" },
  { value: "lodging", label: "Alojamiento" },
  { value: "hotel", label: "Hoteles" },
  { value: "cottage", label: "Cabañas" },
  { value: "guest_house", label: "Casas de huéspedes" },
];

const LEAD_STATUSES = [
  { code: 0, value: "new", label: "0 — Pendiente de contacto" },
  { code: 1, value: "contacted", label: "1 — Contacto realizado" },
  { code: 2, value: "responded", label: "2 — Respondió" },
  { code: 3, value: "follow_up", label: "3 — En seguimiento" },
  { code: 4, value: "closed", label: "4 — Cerrado" },
  { code: 5, value: "discarded", label: "5 — Descartado" },
];

let map;
let marker;
let circle;
let leadLayer;
let center = { ...DEFAULT_CENTER };
let projects = [];
let leads = [];
let rubroSummary = [];
let selectedIds = new Set();
let activeFilter = "all";
let activeServiceFilter = "all";
let activeRubroFilter = "all";
let hasSearched = false;
let activeLeadForBot = null;
let botMessages = [];
let currentMessageBody = "";
let activeModalLeadId = null;
const leadMessages = new Map();
let progressTimer = null;
let lastSearchHistoryId = null;
let locationPresets = [];
let geocodeDebounce = null;

const els = {
  serviceCatalog: document.getElementById("service-catalog"),
  serviceFilters: document.getElementById("service-filters"),
  rubroFilters: document.getElementById("rubro-filters"),
  fitFilters: document.getElementById("fit-filters"),
  radius: document.getElementById("radius"),
  radiusValue: document.getElementById("radius-value"),
  maxPlaces: document.getElementById("max-places"),
  searchMode: document.getElementById("search-mode"),
  searchFocus: document.getElementById("search-focus"),
  businessType: document.getElementById("business-type"),
  discoveryIntro: document.getElementById("discovery-intro"),
  filterNegativeReviews: document.getElementById("filter-negative-reviews"),
  maxReviewsPerPlace: document.getElementById("max-reviews-per-place"),
  maxPlaceRating: document.getElementById("max-place-rating"),
  useCache: document.getElementById("use-cache"),
  customName: document.getElementById("custom-name"),
  customDescription: document.getElementById("custom-description"),
  customCriteria: document.getElementById("custom-criteria"),
  customTypes: document.getElementById("custom-types"),
  saveCustomBtn: document.getElementById("save-custom-btn"),
  deleteCustomBtn: document.getElementById("delete-custom-btn"),
  historyBtn: document.getElementById("history-btn"),
  historyDrawer: document.getElementById("history-drawer"),
  historyList: document.getElementById("history-list"),
  bulkChannel: document.getElementById("bulk-channel"),
  addressSearch: document.getElementById("address-search"),
  geocodeSuggestions: document.getElementById("geocode-suggestions"),
  locationPreset: document.getElementById("location-preset"),
  searchBtn: document.getElementById("search-btn"),
  mendozaCabanasBtn: document.getElementById("mendoza-cabanas-btn"),
  results: document.getElementById("results"),
  summary: document.getElementById("summary"),
  suggestions: document.getElementById("suggestions"),
  error: document.getElementById("error"),
  loading: document.getElementById("loading"),
  loadingText: document.getElementById("loading-text"),
  statPlaces: document.getElementById("stat-places"),
  statReviews: document.getElementById("stat-reviews"),
  statLeads: document.getElementById("stat-leads"),
  statHigh: document.getElementById("stat-high"),
  statSelected: document.getElementById("stat-selected"),
  selectAll: document.getElementById("select-all"),
  exportBtn: document.getElementById("export-btn"),
  messagesBtn: document.getElementById("messages-btn"),
  clearSelection: document.getElementById("clear-selection"),
  messageModal: document.getElementById("message-modal"),
  messageModalBody: document.getElementById("message-modal-body"),
  copyMessageBtn: document.getElementById("copy-message-btn"),
  whatsappOpenBtn: document.getElementById("whatsapp-open-btn"),
  emailOpenBtn: document.getElementById("email-open-btn"),
  botDrawer: document.getElementById("bot-drawer"),
  botTitle: document.getElementById("bot-title"),
  botSubtitle: document.getElementById("bot-subtitle"),
  botStage: document.getElementById("bot-stage"),
  botNextAction: document.getElementById("bot-next-action"),
  chatLog: document.getElementById("chat-log"),
  chatInput: document.getElementById("chat-input"),
  chatSendBtn: document.getElementById("chat-send-btn"),
  chatStartBtn: document.getElementById("chat-start-btn"),
};

function leadId(lead) {
  return lead.place_id;
}

function leadInputFrom(lead) {
  return {
    place_name: lead.place_name,
    place_id: lead.place_id,
    address: lead.address,
    phone: lead.phone,
    email: lead.email,
    website: lead.website,
    themes: lead.themes || [],
    reviews_count: lead.reviews_count || 1,
    review_text: lead.review_text,
    lead_fit: lead.lead_fit,
    reason: lead.reason,
    suggested_pitch: lead.suggested_pitch,
    recommended_project_id: lead.recommended_project_id,
    business_type_label: lead.business_type_label,
  };
}

function projectPayload(lead) {
  return { project_id: lead?.recommended_project_id || "cursor-dev" };
}

function cacheLeadMessage(id, data) {
  if (!data?.body) return;
  leadMessages.set(id, {
    body: data.body,
    whatsapp_link: data.whatsapp_link || null,
  });
}

function getLeadMessageBody(id) {
  if (activeModalLeadId === id && currentMessageBody) return currentMessageBody;
  const cached = leadMessages.get(id);
  if (cached?.body) return cached.body;
  const lead = getLeadById(id)?.lead;
  return lead?.suggested_pitch || "";
}

function openWhatsAppWeb(id, messageBody) {
  const found = getLeadById(id);
  if (!found?.lead.phone) return false;
  const body = messageBody || getLeadMessageBody(id);
  const cached = leadMessages.get(id);
  const url =
    body && cached?.whatsapp_link && cached.body === body
      ? cached.whatsapp_link
      : whatsappHref(found.lead.phone, body);
  if (!url) return false;
  window.open(url, "_blank", "noopener");
  return true;
}

async function ensureLeadWhatsAppMessage(id) {
  const existing = getLeadMessageBody(id);
  if (existing) return existing;

  const found = getLeadById(id);
  if (!found?.lead.phone) throw new Error("Este negocio no tiene teléfono en Google.");

  const data = await apiPost("/api/outreach/message", {
    lead: leadInputFrom(found.lead),
    ...projectPayload(found.lead),
    channel: "whatsapp",
  });
  cacheLeadMessage(id, data);
  return data.body;
}

async function openWhatsAppForLead(id) {
  hideError();
  const found = getLeadById(id);
  if (!found?.lead.phone) {
    showError("Este negocio no tiene teléfono en Google.");
    return;
  }

  let body = getLeadMessageBody(id);
  if (!body) {
    setLoading(true, "Generando mensaje de WhatsApp…");
    try {
      body = await ensureLeadWhatsAppMessage(id);
    } catch (err) {
      showError(err.message);
      return;
    } finally {
      setLoading(false);
    }
  }

  openWhatsAppWeb(id, body);
  await markLeadContacted(id);
}

function whatsappHref(phone, message = "") {
  if (!phone) return null;
  const digits = phone.replace(/\D/g, "");
  if (digits.length < 8) return null;
  const text = message ? `?text=${encodeURIComponent(message.slice(0, 500))}` : "";
  return `https://wa.me/${digits}${text}`;
}

function showError(message) {
  els.error.textContent = message;
  els.error.classList.add("visible");
}

function hideError() {
  els.error.classList.remove("visible");
}

function setLoading(visible, text) {
  els.loading.classList.toggle("visible", visible);
  els.searchBtn.disabled = visible;
  if (text) els.loadingText.textContent = text;
}

async function parseApiResponse(res) {
  const text = await res.text();
  try {
    return text ? JSON.parse(text) : {};
  } catch {
    throw new Error(text.slice(0, 120) || `Error ${res.status}`);
  }
}

async function apiGet(url) {
  const res = await fetch(url);
  const data = await parseApiResponse(res);
  if (!res.ok) throw new Error(data.detail || "Error en la solicitud");
  return data;
}

async function apiPut(url, body) {
  const res = await fetch(url, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const data = await parseApiResponse(res);
  if (!res.ok) throw new Error(data.detail || "Error en la solicitud");
  return data;
}

async function apiPatch(url, body) {
  const res = await fetch(url, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const data = await parseApiResponse(res);
  if (!res.ok) throw new Error(data.detail || "Error en la solicitud");
  return data;
}

async function apiDelete(url) {
  const res = await fetch(url, { method: "DELETE" });
  if (!res.ok) {
    const data = await res.json();
    throw new Error(data.detail || "Error en la solicitud");
  }
}

async function apiPost(url, body) {
  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const data = await parseApiResponse(res);
  if (!res.ok) {
    const detail = Array.isArray(data.detail)
      ? data.detail.map((d) => d.msg || JSON.stringify(d)).join(", ")
      : data.detail;
    throw new Error(detail || "Error en la solicitud");
  }
  return data;
}

function initMap() {
  map = L.map("map", { zoomControl: true }).setView([center.lat, center.lng], 14);
  L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
    attribution: "&copy; OpenStreetMap",
    maxZoom: 19,
  }).addTo(map);

  marker = L.marker([center.lat, center.lng], { draggable: true }).addTo(map);
  leadLayer = L.layerGroup().addTo(map);
  updateCircle();

  marker.on("dragend", () => {
    const pos = marker.getLatLng();
    center = { lat: pos.lat, lng: pos.lng };
    updateCircle();
  });

  map.on("click", (e) => {
    center = { lat: e.latlng.lat, lng: e.latlng.lng };
    marker.setLatLng(e.latlng);
    updateCircle();
  });
}

function updateCircle() {
  const km = Number(els.radius?.value) || 8;
  const radiusM = km * 1000;
  if (els.radiusValue) els.radiusValue.textContent = `${km} km`;
  if (circle) {
    circle.setLatLng([center.lat, center.lng]);
    circle.setRadius(radiusM);
  } else {
    circle = L.circle([center.lat, center.lng], {
      radius: radiusM,
      color: "#2dd4a0",
      fillColor: "#2dd4a0",
      fillOpacity: 0.12,
      weight: 2,
    }).addTo(map);
  }
}

function applyMapLocation(pos, zoom = 13) {
  center = { lat: pos.lat, lng: pos.lng };
  marker.setLatLng([pos.lat, pos.lng]);
  map.setView([pos.lat, pos.lng], zoom);
  updateCircle();
}

function hideGeocodeSuggestions() {
  els.geocodeSuggestions.hidden = true;
  els.geocodeSuggestions.innerHTML = "";
}

function showGeocodeSuggestions(items) {
  if (!items.length) {
    hideGeocodeSuggestions();
    return;
  }
  els.geocodeSuggestions.innerHTML = items
    .map(
      (item, index) => `
    <li>
      <button type="button" class="geocode-suggestion" data-index="${index}">
        <strong>${escapeHtml(item.label.split(",")[0])}</strong>
        <span>${escapeHtml(item.label)}</span>
        <em>${escapeHtml(item.kind)} · ${item.source === "preset" ? "zona conocida" : "OpenStreetMap"}</em>
      </button>
    </li>`
    )
    .join("");

  els.geocodeSuggestions.hidden = false;
  els.geocodeSuggestions.querySelectorAll(".geocode-suggestion").forEach((btn) => {
    btn.addEventListener("click", () => {
      const item = items[Number(btn.dataset.index)];
      applyGeocodeResult(item);
      hideGeocodeSuggestions();
    });
  });
}

function applyGeocodeResult(item) {
  applyMapLocation(item, item.zoom || 13);
  els.addressSearch.value = item.label.split(",")[0];
  els.locationPreset.value = "";
}

async function geocodeAddress(query, { autoPickSingle = true } = {}) {
  const items = await apiGet(`/api/geocode/search?q=${encodeURIComponent(query)}&limit=8`);
  if (!items.length) throw new Error("No encontramos esa zona en Argentina.");
  if (items.length === 1 && autoPickSingle) {
    applyGeocodeResult(items[0]);
    hideGeocodeSuggestions();
    return items[0];
  }
  showGeocodeSuggestions(items);
  return items;
}

async function loadLocationPresets() {
  locationPresets = await apiGet("/api/geocode/presets");
  const groups = [
    { key: "argentina", label: "Provincias y ciudades" },
    { key: "mendoza", label: "Departamentos de Mendoza" },
  ];
  els.locationPreset.innerHTML =
    '<option value="">— Elegir provincia o zona —</option>' +
    groups
      .map((group) => {
        const options = locationPresets
          .filter((p) => p.group === group.key)
          .map((p) => `<option value="${p.id}">${escapeHtml(p.label)}</option>`)
          .join("");
        return options ? `<optgroup label="${group.label}">${options}</optgroup>` : "";
      })
      .join("");
}

async function loadServiceCatalog() {
  projects = await apiGet("/api/projects");
  els.serviceCatalog.innerHTML = projects
    .map(
      (p) =>
        `<li><strong>${escapeHtml(p.name)}</strong><span>${escapeHtml(p.description.slice(0, 90))}${p.description.length > 90 ? "…" : ""}</span></li>`
    )
    .join("");
  renderServiceFilters();
}

function renderServiceFilters() {
  if (!els.serviceFilters) return;
  const counts = {};
  for (const lead of leads) {
    const id = lead.recommended_project_id || "other";
    counts[id] = (counts[id] || 0) + 1;
  }
  const chips = [
    `<button type="button" class="chip ${activeServiceFilter === "all" ? "active" : ""}" data-service="all">Todos los servicios</button>`,
    ...projects.map((p) => {
      const n = counts[p.id] || 0;
      const label = n > 0 ? `${escapeHtml(p.name)} (${n})` : escapeHtml(p.name);
      return `<button type="button" class="chip ${activeServiceFilter === p.id ? "active" : ""}" data-service="${escapeHtml(p.id)}">${label}</button>`;
    }),
  ];
  els.serviceFilters.innerHTML = chips.join("");
  els.serviceFilters.querySelectorAll("[data-service]").forEach((chip) => {
    chip.addEventListener("click", () => {
      activeServiceFilter = chip.dataset.service;
      els.serviceFilters.querySelectorAll(".chip").forEach((c) => c.classList.remove("active"));
      chip.classList.add("active");
      renderResults();
    });
  });
}

function fillCustomForm(project) {
  if (!project) {
    els.customName.value = "";
    els.customDescription.value = "";
    els.customCriteria.value = "";
    els.customTypes.value = "";
    return;
  }
  els.customName.value = project.name;
  els.customDescription.value = project.description;
  els.customCriteria.value = project.lead_criteria;
  els.customTypes.value = (project.suggested_business_types || []).join(", ");
}

function renderRubroFilters(summary = []) {
  rubroSummary = summary;
  if (!summary.length) {
    els.rubroFilters.hidden = true;
    els.rubroFilters.innerHTML = "";
    return;
  }
  els.rubroFilters.hidden = false;
  els.rubroFilters.innerHTML = [
    `<button type="button" class="chip rubro-chip active" data-rubro="all">Todos los rubros</button>`,
    ...summary.map(
      (r) =>
        `<button type="button" class="chip rubro-chip" data-rubro="${escapeHtml(r.business_type)}">${escapeHtml(r.business_type_label)} (${r.leads_count})</button>`
    ),
    ].join("");

  els.rubroFilters.querySelectorAll(".rubro-chip").forEach((chip) => {
    chip.addEventListener("click", () => {
      activeRubroFilter = chip.dataset.rubro;
      els.rubroFilters.querySelectorAll(".rubro-chip").forEach((c) => c.classList.remove("active"));
      chip.classList.add("active");
      renderResults();
    });
  });
}

function renderRubroInsights() {
  if (!rubroSummary.length) {
    els.suggestions.hidden = true;
    return;
  }
  els.suggestions.hidden = false;
  els.suggestions.innerHTML = `
    <h3>Rubros con más oportunidades</h3>
    <div class="rubro-insights">
      ${rubroSummary
        .map(
          (r) => `
        <button type="button" class="insight-card" data-rubro="${escapeHtml(r.business_type)}">
          <strong>${escapeHtml(r.business_type_label)}</strong>
          <span>${r.leads_count} lead${r.leads_count === 1 ? "" : "s"}</span>
        </button>`
        )
        .join("")}
    </div>`;

  els.suggestions.querySelectorAll("[data-rubro]").forEach((btn) => {
    btn.addEventListener("click", () => {
      activeRubroFilter = btn.dataset.rubro;
      els.rubroFilters.querySelectorAll(".rubro-chip").forEach((chip) => {
        chip.classList.toggle("active", chip.dataset.rubro === activeRubroFilter);
      });
      renderResults();
    });
  });
}

async function saveCustomProject() {
  const body = {
    name: els.customName.value.trim(),
    description: els.customDescription.value.trim(),
    lead_criteria: els.customCriteria.value.trim(),
    suggested_business_types: els.customTypes.value
      .split(",")
      .map((t) => t.trim())
      .filter(Boolean),
  };
  if (body.name.length < 2 || body.description.length < 10 || body.lead_criteria.length < 10) {
    showError("Completá nombre, descripción y criterios (mín. 10 caracteres en descripción/criterios).");
    return;
  }
  hideError();
  try {
    await apiPost("/api/projects/custom", body);
    await loadServiceCatalog();
    fillCustomForm(null);
  } catch (err) {
    showError(err.message);
  }
}

function filteredLeads() {
  return leads.filter((lead) => {
    if (activeFilter !== "all" && lead.lead_fit !== activeFilter) return false;
    if (activeServiceFilter !== "all" && lead.recommended_project_id !== activeServiceFilter) return false;
    if (activeRubroFilter !== "all" && lead.business_type !== activeRubroFilter) return false;
    return true;
  });
}

function contactsHtml(lead, id) {
  const parts = [];
  if (lead.phone) {
    parts.push(
      `<a class="contact-link contact-phone" href="#" data-id="${escapeHtml(id)}" data-action="phone-whatsapp" title="Abrir WhatsApp Web con el mensaje">📞 ${escapeHtml(lead.phone)}</a>`
    );
  }
  if (lead.email) {
    parts.push(`<a class="contact-link" href="mailto:${escapeHtml(lead.email)}">✉️ ${escapeHtml(lead.email)}</a>`);
  }
  if (lead.website) {
    parts.push(`<a class="contact-link" href="${escapeHtml(lead.website)}" target="_blank" rel="noopener">🌐 Web</a>`);
  }
  if (lead.google_maps_url) {
    parts.push(`<a class="contact-link" href="${escapeHtml(lead.google_maps_url)}" target="_blank" rel="noopener">📍 Maps</a>`);
  }
  return parts.length ? `<div class="contacts">${parts.join("")}</div>` : `<div class="contacts"><span class="suggestion-meta">Sin teléfono/email en Google</span></div>`;
}

function themesHtml(lead) {
  const counts = lead.theme_counts || {};
  const themes = lead.themes || [];
  if (!themes.length) return "";
  return `
    <div class="themes">
      <span class="themes-label">Quejas detectadas:</span>
      ${themes
        .map((theme) => {
          const count = counts[theme];
          const label = count > 1 ? `${escapeHtml(theme)} (${count})` : escapeHtml(theme);
          return `<span class="theme-tag">${label}</span>`;
        })
        .join("")}
    </div>`;
}

function statusSelectHtml(lead, id) {
  const current = lead.status || "new";
  return `
    <label class="status-label">
      Estado
      <select class="lead-status" data-id="${id}">
        ${LEAD_STATUSES.map(
          (s) => `<option value="${s.value}" ${current === s.value ? "selected" : ""}>${s.label}</option>`
        ).join("")}
      </select>
    </label>`;
}

function renderLeadPins() {
  if (!leadLayer) return;
  leadLayer.clearLayers();
  const colors = { high: "#22c55e", medium: "#f59e0b", low: "#94a3b8" };
  leads.forEach((lead) => {
    if (lead.lat == null || lead.lng == null) return;
    L.circleMarker([lead.lat, lead.lng], {
      radius: 8,
      color: colors[lead.lead_fit] || "#3b82f6",
      fillColor: colors[lead.lead_fit] || "#3b82f6",
      fillOpacity: 0.85,
      weight: 2,
    })
      .bindPopup(`<strong>${escapeHtml(lead.place_name)}</strong><br>${escapeHtml(lead.lead_fit)}`)
      .addTo(leadLayer);
  });
}

async function updateLeadStatus(id, status) {
  const lead = leads.find((item) => leadId(item) === id);
  if (!lead?.saved_lead_id) {
    showError("Este lead no está guardado en el CRM. Generá una búsqueda primero.");
    return;
  }
  try {
    const updated = await apiPatch(`/api/history/leads/${lead.saved_lead_id}`, { status });
    lead.status = updated.status;
    lead.notes = updated.notes;
    renderLeads();
  } catch (err) {
    showError(err.message);
  }
}

async function markLeadContacted(id) {
  const lead = leads.find((item) => leadId(item) === id);
  if (!lead?.saved_lead_id || lead.status !== "new") return;
  try {
    const updated = await apiPatch(`/api/history/leads/${lead.saved_lead_id}`, { status: "contacted" });
    lead.status = updated.status;
    lead.notes = updated.notes;
    renderLeads();
  } catch {
    /* no bloquear el envío si falla el CRM */
  }
}

function startSearchProgress() {
  const steps = [
    "Escaneando comercios de la zona…",
    "Leyendo reseñas con dolor…",
    "Matcheando cada dolor con un servicio SofIA…",
    "Agrupando leads por servicio…",
  ];
  let step = 0;
  setLoading(true, steps[0]);
  progressTimer = setInterval(() => {
    step = (step + 1) % steps.length;
    els.loadingText.textContent = steps[step];
  }, 9000);
}

function stopSearchProgress() {
  if (progressTimer) {
    clearInterval(progressTimer);
    progressTimer = null;
  }
  setLoading(false);
}

function applySearchResponse(data) {
  hasSearched = true;
  leads = data.leads || [];
  leadMessages.clear();
  lastSearchHistoryId = data.search_history_id || null;
  selectedIds.clear();
  activeFilter = "all";
  activeServiceFilter = "all";
  activeRubroFilter = "all";
  els.fitFilters.querySelectorAll(".chip").forEach((chip) => {
    chip.classList.toggle("active", chip.dataset.filter === "all");
  });
  let summaryText = data.summary || "";
  if (data.from_cache) summaryText = `Desde caché. ${summaryText}`;
  els.summary.textContent = summaryText;
  els.summary.hidden = !summaryText;
  updateStats(
    data.places_scanned || 0,
    data.reviews_classified ?? data.reviews_analyzed ?? 0,
    data.reviews_skipped || 0
  );
  renderServiceFilters();
  renderRubroFilters(data.rubro_summary || []);
  renderRubroInsights();
  renderResults();
}

async function openHistoryDrawer() {
  els.historyDrawer.hidden = false;
  try {
    const items = await apiGet("/api/history/searches?limit=30");
    if (!items.length) {
      els.historyList.innerHTML = `<p class="empty-hint">Todavía no hay búsquedas guardadas.</p>`;
      return;
    }
    els.historyList.innerHTML = items
      .map(
        (item) => `
      <button type="button" class="history-item" data-history-id="${item.id}">
        <strong>${new Date(item.created_at).toLocaleString("es-AR")}</strong>
        <span>${escapeHtml(item.project_name || item.project_id || "Servicio")} · ${escapeHtml(item.business_type)} · ${item.leads_count} leads</span>
        ${item.from_cache ? '<span class="history-cache">caché</span>' : ""}
      </button>`
      )
      .join("");
    els.historyList.querySelectorAll("[data-history-id]").forEach((btn) => {
      btn.addEventListener("click", () => loadHistorySearch(Number(btn.dataset.historyId)));
    });
  } catch (err) {
    els.historyList.innerHTML = `<p class="empty-hint">${escapeHtml(err.message)}</p>`;
  }
}

function closeHistoryDrawer() {
  els.historyDrawer.hidden = true;
}

async function loadHistorySearch(historyId) {
  hideError();
  startSearchProgress();
  try {
    const data = await apiGet(`/api/history/searches/${historyId}`);
    if (data.center) {
      center = data.center;
      marker.setLatLng([center.lat, center.lng]);
      map.setView([center.lat, center.lng], 14);
      updateCircle();
    }
    applySearchResponse(data);
    closeHistoryDrawer();
  } catch (err) {
    showError(err.message);
  } finally {
    stopSearchProgress();
  }
}

function reviewSamplesHtml(lead) {
  const samples = lead.review_samples || [];
  if (!samples.length) {
    if (!lead.review_text) return "";
    return `<p class="review-text">"${escapeHtml(lead.review_text)}"</p>`;
  }
  return `
    <div class="review-samples">
      ${samples
        .slice(0, 3)
        .map(
          (sample) => `
        <blockquote class="review-sample">
          ${sample.theme ? `<span class="theme-tag theme-tag-sm">${escapeHtml(sample.theme)}</span>` : ""}
          "${escapeHtml(sample.text)}"
        </blockquote>`
        )
        .join("")}
    </div>`;
}

function groupVisibleLeadsByService(visible) {
  const order = [];
  const groups = new Map();
  for (const lead of visible) {
    const key = lead.recommended_project_id || "other";
    const label = lead.recommended_project_name || "Otro servicio SofIA";
    if (!groups.has(key)) {
      groups.set(key, { key, label, leads: [] });
      order.push(key);
    }
    groups.get(key).leads.push(lead);
  }
  // Prefer catalog order
  const catalogOrder = projects.map((p) => p.id);
  order.sort((a, b) => {
    const ia = catalogOrder.indexOf(a);
    const ib = catalogOrder.indexOf(b);
    if (ia === -1 && ib === -1) return 0;
    if (ia === -1) return 1;
    if (ib === -1) return -1;
    return ia - ib;
  });
  return order.map((k) => groups.get(k));
}

function groupVisibleLeadsByRubro(visible) {
  const order = [];
  const groups = new Map();
  for (const lead of visible) {
    const key = lead.business_type || lead.business_type_label || "other";
    const label = lead.business_type_label || "Otros";
    if (!groups.has(key)) {
      groups.set(key, { key, label, leads: [] });
      order.push(key);
    }
    groups.get(key).leads.push(lead);
  }
  return order.map((k) => groups.get(k));
}

function leadCardHtml(lead, { hideServiceBadge = false } = {}) {
  const id = leadId(lead);
  const checked = selectedIds.has(id) ? "checked" : "";
  const selectedClass = selectedIds.has(id) ? "selected" : "";
  const waDisabled = lead.phone ? "" : " disabled title=\"Sin teléfono en Google\"";
  const emailDisabled = lead.email ? "" : " disabled title=\"Google no publica email para este negocio\"";
  const themes = (lead.themes || []).slice(0, 4);
  const painText = themes.length
    ? themes.map((t) => escapeHtml(t)).join(" · ")
    : "Dolor detectado en reseñas de Google";

  return `
    <article class="lead-card ${selectedClass}" data-id="${id}">
      <input type="checkbox" ${checked} aria-label="Seleccionar lead" />
      <div>
        <div class="lead-header">
          <h3>${escapeHtml(lead.place_name)}</h3>
          <div class="lead-badges">
            ${lead.business_type_label ? `<span class="badge rubro">${escapeHtml(lead.business_type_label)}</span>` : ""}
            ${!hideServiceBadge && lead.recommended_project_name ? `<span class="badge service">${escapeHtml(lead.recommended_project_name)}</span>` : ""}
            <span class="badge ${lead.lead_fit}">${lead.lead_fit}</span>
          </div>
        </div>
        <p class="meta">
          ${escapeHtml(lead.address || "Sin dirección")}
          ${lead.rating ? ` · ⭐ ${lead.rating}` : ""}
        </p>
        ${contactsHtml(lead, id)}
        <p class="pain-line"><strong>Dolor:</strong> ${painText}</p>
        ${lead.solution_value ? `<p class="sofia-help"><strong>Cómo SofIA ayuda:</strong> ${escapeHtml(lead.solution_value)}</p>` : ""}
        ${lead.suggested_pitch ? `<p class="pitch"><strong>Pitch:</strong> ${escapeHtml(lead.suggested_pitch)}</p>` : ""}
        ${lead.reason ? `<p class="reason"><strong>Por qué es lead:</strong> ${escapeHtml(lead.reason)}</p>` : ""}
        ${reviewSamplesHtml(lead)}
        ${statusSelectHtml(lead, id)}
        <div class="lead-actions">
          <button type="button" class="btn btn-sm btn-whatsapp-primary" data-action="whatsapp" data-id="${id}"${waDisabled}>WhatsApp</button>
          <button type="button" class="btn btn-secondary btn-sm" data-action="email" data-id="${id}"${emailDisabled}>Email</button>
          <button type="button" class="btn btn-secondary btn-sm" data-action="bot" data-id="${id}">Practicar pitch</button>
        </div>
      </div>
    </article>`;
}

function bindLeadCardEvents() {
  els.results.querySelectorAll(".lead-card").forEach((card) => {
    const id = card.dataset.id;
    const checkbox = card.querySelector('input[type="checkbox"]');

    const toggle = () => {
      if (selectedIds.has(id)) {
        selectedIds.delete(id);
        card.classList.remove("selected");
        checkbox.checked = false;
      } else {
        selectedIds.add(id);
        card.classList.add("selected");
        checkbox.checked = true;
      }
      updateSelectedCount();
    };

    checkbox.addEventListener("change", (e) => {
      e.stopPropagation();
      toggle();
    });

    card.addEventListener("click", (e) => {
      if (e.target.closest("button, a, input, select, textarea")) return;
      toggle();
    });

    card.querySelector('[data-action="phone-whatsapp"]')?.addEventListener("click", (e) => {
      e.preventDefault();
      e.stopPropagation();
      openWhatsAppForLead(id);
    });

    card.querySelector('[data-action="whatsapp"]')?.addEventListener("click", (e) => {
      e.stopPropagation();
      openMessageForLead(id, "whatsapp");
    });

    card.querySelector('[data-action="email"]')?.addEventListener("click", (e) => {
      e.stopPropagation();
      openMessageForLead(id, "email");
    });

    card.querySelector('[data-action="bot"]')?.addEventListener("click", (e) => {
      e.stopPropagation();
      openBotForLead(id);
    });

    card.querySelector(".lead-status")?.addEventListener("change", (e) => {
      e.stopPropagation();
      updateLeadStatus(id, e.target.value);
    });
  });

  renderLeadPins();
}

function renderResults() {
  const visible = filteredLeads();

  if (!hasSearched) {
    els.results.innerHTML = `
      <div class="empty empty-hero">
        <h2>SofIA Leads</h2>
        <p>Elegí una zona y tocá <strong>Buscar leads</strong>. Vas a ver comercios con dolores en Google y el servicio SofIA que conviene ofrecerles.</p>
      </div>`;
    els.summary.hidden = true;
    return;
  }

  els.summary.hidden = !els.summary.textContent;

  if (!leads.length) {
    els.results.innerHTML = `
      <div class="empty">
        <p><strong>No hay leads en esta zona</strong></p>
        <p class="empty-hint">Abrí Ajustes y subí el radio o la cantidad de lugares.</p>
      </div>`;
    return;
  }

  if (!visible.length) {
    els.results.innerHTML = `
      <div class="empty">
        <p>No hay leads con el filtro actual.</p>
        <p class="empty-hint">Probá <strong>Todos los servicios</strong> u otra prioridad.</p>
      </div>`;
    return;
  }

  const groups = groupVisibleLeadsByService(visible);
  const multipleGroups = groups.length > 1;

  els.results.innerHTML = groups
    .map(
      (group) => `
    <section class="service-group">
      <header class="service-group-header">
        <h3>${escapeHtml(group.label)}</h3>
        <span class="service-group-count">${group.leads.length} lead${group.leads.length === 1 ? "" : "s"}</span>
      </header>
      <div class="service-group-leads">
        ${group.leads.map((lead) => leadCardHtml(lead, { hideServiceBadge: multipleGroups })).join("")}
      </div>
    </section>`
    )
    .join("");

  bindLeadCardEvents();
}

function escapeHtml(text) {
  const div = document.createElement("div");
  div.textContent = text ?? "";
  return div.innerHTML;
}

function getLeadById(id) {
  const lead = leads.find((item) => leadId(item) === id);
  return lead ? { lead } : null;
}

function showMessageModal(title, html, message, leadId = null) {
  document.getElementById("modal-title").textContent = title;
  activeModalLeadId = leadId;
  let bodyHtml = html;
  if (message.contact_phone) {
    bodyHtml += `<p class="contact-note">Teléfono Google: ${escapeHtml(message.contact_phone)}</p>`;
  }
  if (message.contact_email) {
    bodyHtml += `<p class="contact-note">Email Google: ${escapeHtml(message.contact_email)}</p>`;
  }
  els.messageModalBody.innerHTML = bodyHtml;
  currentMessageBody = message.body || message;
  if (leadId && message.body) cacheLeadMessage(leadId, message);
  els.whatsappOpenBtn.hidden = !message.whatsapp_link && !leadId;
  if (message.whatsapp_link) {
    els.whatsappOpenBtn.href = message.whatsapp_link;
  } else if (leadId) {
    const found = getLeadById(leadId);
    if (found?.lead.phone) els.whatsappOpenBtn.href = whatsappHref(found.lead.phone, currentMessageBody);
  }
  els.emailOpenBtn.hidden = !message.email_link;
  if (message.email_link) els.emailOpenBtn.href = message.email_link;
  els.messageModal.hidden = false;
}

function closeMessageModal() {
  els.messageModal.hidden = true;
  activeModalLeadId = null;
}

async function openMessageForLead(id, channel = "whatsapp") {
  const found = getLeadById(id);
  if (!found) return;

  if (channel === "whatsapp" && !found.lead.phone) {
    showError("Este negocio no tiene teléfono en Google.");
    return;
  }
  if (channel === "email" && !found.lead.email) {
    showError("Google no publica email para este negocio.");
    return;
  }

  setLoading(true, channel === "email" ? "Generando email…" : "Generando mensaje de WhatsApp…");
  try {
    const data = await apiPost("/api/outreach/message", {
      lead: leadInputFrom(found.lead),
      ...projectPayload(found.lead),
      channel,
    });

    const html = `
      ${data.subject ? `<p><strong>Asunto:</strong> ${escapeHtml(data.subject)}</p>` : ""}
      <p>${escapeHtml(data.body)}</p>
      ${data.tips ? `<div class="message-tips"><strong>Tip:</strong> ${escapeHtml(data.tips)}</div>` : ""}`;
    const title = channel === "email" ? `Email para ${found.lead.place_name}` : `WhatsApp para ${found.lead.place_name}`;
    showMessageModal(title, html, data, channel === "whatsapp" ? id : null);
    await markLeadContacted(id);
  } catch (err) {
    showError(err.message);
  } finally {
    setLoading(false);
  }
}

async function openBulkMessages() {
  const selected = leads
    .map((lead) => ({ lead, id: leadId(lead) }))
    .filter(({ id }) => selectedIds.has(id));

  if (!selected.length) return;

  setLoading(true, `Generando ${selected.length} mensajes…`);
  try {
    const data = await apiPost("/api/outreach/messages/bulk", {
      leads: selected.map(({ lead }) => leadInputFrom(lead)),
      channel: els.bulkChannel.value,
    });

    data.messages.forEach((item) => {
      cacheLeadMessage(item.place_id, item.message);
    });

    const html = data.messages
      .map(
        (item) => `
        <div class="bulk-message-item">
          <h4>${escapeHtml(item.place_name)}</h4>
          <p>${escapeHtml(item.message.body)}</p>
          ${item.message.whatsapp_link ? `<a class="contact-link" href="${escapeHtml(item.message.whatsapp_link)}" target="_blank" rel="noopener">Abrir WhatsApp (${escapeHtml(item.message.contact_phone || "")})</a>` : ""}
          ${item.message.email_link ? `<a class="contact-link" href="${escapeHtml(item.message.email_link)}">Abrir email (${escapeHtml(item.message.contact_email || "")})</a>` : ""}
        </div>`
      )
      .join("");

    currentMessageBody = data.messages.map((m) => `${m.place_name}:\n${m.message.body}`).join("\n\n---\n\n");
    showMessageModal("Mensajes para leads seleccionados", html, { body: currentMessageBody });
  } catch (err) {
    showError(err.message);
  } finally {
    setLoading(false);
  }
}

function openBotForLead(id) {
  const found = getLeadById(id);
  if (!found) return;

  activeLeadForBot = found.lead;
  botMessages = [];
  els.botTitle.textContent = `Bot de ventas — ${found.lead.place_name}`;
  els.botSubtitle.textContent = found.lead.phone || found.lead.address || "";
  els.botStage.textContent = "Etapa: listo para iniciar";
  els.botNextAction.textContent = "";
  els.chatLog.innerHTML = "";
  els.chatInput.value = "";
  els.botDrawer.hidden = false;
}

function closeBotDrawer() {
  els.botDrawer.hidden = true;
  activeLeadForBot = null;
  botMessages = [];
}

function appendChatBubble(role, content) {
  const div = document.createElement("div");
  div.className = `chat-bubble ${role}`;
  div.textContent = content;
  els.chatLog.appendChild(div);
  els.chatLog.scrollTop = els.chatLog.scrollHeight;
}

async function startBotConversation() {
  if (!activeLeadForBot) return;
  setLoading(true, "El bot está preparando el primer mensaje…");
  try {
    const data = await apiPost("/api/outreach/chat", {
      lead: leadInputFrom(activeLeadForBot),
      ...projectPayload(activeLeadForBot),
      messages: [],
    });
    botMessages = [{ role: "assistant", content: data.reply }];
    els.chatLog.innerHTML = "";
    appendChatBubble("assistant", data.reply);
    els.botStage.textContent = `Etapa: ${data.stage} · Cierre: ${data.close_probability}%`;
    els.botNextAction.textContent = data.next_action;
  } catch (err) {
    showError(err.message);
  } finally {
    setLoading(false);
  }
}

async function sendBotReply() {
  const text = els.chatInput.value.trim();
  if (!text || !activeLeadForBot) return;

  botMessages.push({ role: "user", content: text });
  appendChatBubble("user", text);
  els.chatInput.value = "";

  setLoading(true, "El bot está respondiendo…");
  try {
    const data = await apiPost("/api/outreach/chat", {
      lead: leadInputFrom(activeLeadForBot),
      ...projectPayload(activeLeadForBot),
      messages: botMessages,
    });
    botMessages.push({ role: "assistant", content: data.reply });
    appendChatBubble("assistant", data.reply);
    els.botStage.textContent = `Etapa: ${data.stage} · Cierre: ${data.close_probability}%`;
    els.botNextAction.textContent = data.next_action;
  } catch (err) {
    showError(err.message);
  } finally {
    setLoading(false);
  }
}

function updateStats(places, classified, skipped = 0) {
  els.statPlaces.textContent = places;
  els.statReviews.textContent = skipped > 0 ? `${classified} (${skipped} omit.)` : classified;
  els.statLeads.textContent = leads.length;
  if (els.statHigh) {
    els.statHigh.textContent = leads.filter((l) => l.lead_fit === "high").length;
  }
  updateSelectedCount();
}

function searchFiltersPayload() {
  const maxPlaceRating = els.maxPlaceRating.value.trim();
  return {
    max_review_rating: els.filterNegativeReviews.checked ? 3 : null,
    max_reviews_per_place: Number(els.maxReviewsPerPlace.value) || 5,
    max_place_rating: maxPlaceRating ? Number(maxPlaceRating) : null,
    use_cache: els.useCache.checked,
  };
}

function updateSelectedCount() {
  els.statSelected.textContent = selectedIds.size;
  const disabled = selectedIds.size === 0;
  els.exportBtn.disabled = disabled;
  els.messagesBtn.disabled = disabled;
}

async function runSearch() {
  hideError();
  startSearchProgress();

  try {
    const payload = {
      center,
      radius_km: Number(els.radius?.value) || 8,
      max_places: Number(els.maxPlaces.value) || 36,
      mode: "leads",
      search_focus: "all",
      ...searchFiltersPayload(),
    };

    const data = await apiPost("/api/search", payload);
    applySearchResponse(data);
  } catch (err) {
    showError(err.message || "Ocurrió un error inesperado");
  } finally {
    stopSearchProgress();
  }
}

async function runMendozaCabanasCampaign() {
  hideError();
  const confirmRun = window.confirm(
    "¿Barrer cabañas en todas las zonas turísticas de Mendoza?\n\nModo directorio (contactos + teléfono). Puede tardar varios minutos y consume cuota de Google Places."
  );
  if (!confirmRun) return;

  startSearchProgress();
  if (els.loadingText) {
    els.loadingText.textContent = "Campaña Mendoza · cabañas: recorriendo zonas turísticas…";
  }

  try {
    const data = await apiPost("/api/campaigns/mendoza-cabanas", {
      mode: "directory",
      max_places_per_zone: Math.max(Number(els.maxPlaces?.value) || 40, 40),
      use_cache: els.useCache?.checked ?? true,
    });
    applySearchResponse({
      ...data,
      places_scanned: data.places_scanned,
      reviews_classified: 0,
      reviews_analyzed: 0,
      reviews_skipped: 0,
      summary: data.summary,
      leads: data.leads || [],
      rubro_summary: [],
      search_history_id: data.search_history_id,
      from_cache: false,
    });
    if (els.statHigh) {
      els.statHigh.textContent = String(data.with_phone || 0);
    }
  } catch (err) {
    showError(err.message || "Error en la campaña Mendoza cabañas");
  } finally {
    stopSearchProgress();
  }
}

function exportSelected() {
  const rows = leads
    .map((lead) => ({ lead, id: leadId(lead) }))
    .filter(({ id }) => selectedIds.has(id))
    .map(({ lead }) => lead);

  if (!rows.length) return;

  const headers = [
    "negocio", "rubro", "servicio_recomendado", "telefono", "email", "web", "direccion", "rating_negocio",
    "relevancia", "temas", "cantidad_resenas", "resenas", "razon", "pitch", "como_ayuda_solucion", "place_id", "google_maps",
  ];

  const csvLines = [
    headers.join(","),
    ...rows.map((r) =>
      [
        r.place_name, r.business_type_label || "", r.recommended_project_name || "", r.phone || "", r.email || "",
        r.website || "", r.address || "", r.rating ?? "", r.lead_fit, (r.themes || []).join("; "),
        r.reviews_count || 1, r.review_text, r.reason, r.suggested_pitch || "", r.solution_value || "",
        r.place_id, r.google_maps_url || "",
      ].map((v) => `"${String(v).replace(/"/g, '""')}"`).join(",")
    ),
  ];

  const blob = new Blob(["\uFEFF" + csvLines.join("\n")], { type: "text/csv;charset=utf-8;" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `leads-discovery-${new Date().toISOString().slice(0, 10)}.csv`;
  a.click();
  URL.revokeObjectURL(url);
}

function bindDashboardNav() {
  const link = document.getElementById("nav-campaign");
  if (!link) return;
  const params = new URLSearchParams(window.location.search);
  const fromUrl = (params.get("k") || "").trim();
  if (fromUrl) sessionStorage.setItem("sofia_dash_k", fromUrl);
  const k = fromUrl || (sessionStorage.getItem("sofia_dash_k") || "").trim();
  if (!k) return;
  const sep = link.href.includes("?") ? "&" : "?";
  link.href = `${link.pathname}${sep}k=${encodeURIComponent(k)}`;
}

function bindEvents() {
  bindDashboardNav();
  els.radius?.addEventListener("input", updateCircle);
  els.searchBtn.addEventListener("click", runSearch);
  els.mendozaCabanasBtn?.addEventListener("click", runMendozaCabanasCampaign);

  document.getElementById("geocode-btn").addEventListener("click", async () => {
    const q = els.addressSearch.value.trim();
    if (!q) return;
    hideError();
    setLoading(true);
    try {
      await geocodeAddress(q, { autoPickSingle: false });
    } catch (err) {
      showError(err.message);
      hideGeocodeSuggestions();
    } finally {
      setLoading(false);
    }
  });

  els.addressSearch.addEventListener("input", () => {
    clearTimeout(geocodeDebounce);
    const q = els.addressSearch.value.trim();
    if (q.length < 2) {
      hideGeocodeSuggestions();
      return;
    }
    geocodeDebounce = setTimeout(async () => {
      try {
        await geocodeAddress(q, { autoPickSingle: false });
      } catch {
        hideGeocodeSuggestions();
      }
    }, 450);
  });

  els.addressSearch.addEventListener("keydown", (e) => {
    if (e.key === "Enter") {
      e.preventDefault();
      document.getElementById("geocode-btn").click();
    }
    if (e.key === "Escape") hideGeocodeSuggestions();
  });

  els.locationPreset.addEventListener("change", () => {
    const preset = locationPresets.find((p) => p.id === els.locationPreset.value);
    if (!preset) return;
    hideError();
    applyGeocodeResult(preset);
    hideGeocodeSuggestions();
  });

  document.addEventListener("click", (e) => {
    if (!e.target.closest(".geocode-wrap")) hideGeocodeSuggestions();
  });

  els.fitFilters.querySelectorAll(".chip").forEach((chip) => {
    chip.addEventListener("click", () => {
      els.fitFilters.querySelectorAll(".chip").forEach((c) => c.classList.remove("active"));
      chip.classList.add("active");
      activeFilter = chip.dataset.filter;
      renderResults();
    });
  });

  els.selectAll.addEventListener("click", () => {
    filteredLeads().forEach((lead) => selectedIds.add(leadId(lead)));
    renderResults();
  });

  els.clearSelection.addEventListener("click", () => {
    selectedIds.clear();
    renderResults();
  });

  els.exportBtn.addEventListener("click", exportSelected);
  els.messagesBtn.addEventListener("click", openBulkMessages);
  els.saveCustomBtn?.addEventListener("click", saveCustomProject);
  els.historyBtn.addEventListener("click", openHistoryDrawer);

  document.querySelectorAll("[data-close-history]").forEach((el) => {
    el.addEventListener("click", closeHistoryDrawer);
  });

  els.copyMessageBtn.addEventListener("click", async () => {
    await navigator.clipboard.writeText(currentMessageBody);
    els.copyMessageBtn.textContent = "¡Copiado!";
    setTimeout(() => { els.copyMessageBtn.textContent = "Copiar mensaje"; }, 1500);
  });

  document.querySelectorAll("[data-close-modal]").forEach((el) => {
    el.addEventListener("click", closeMessageModal);
  });

  document.querySelectorAll("[data-close-drawer]").forEach((el) => {
    el.addEventListener("click", closeBotDrawer);
  });

  els.chatStartBtn.addEventListener("click", startBotConversation);
  els.chatSendBtn.addEventListener("click", sendBotReply);
  els.chatInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter") sendBotReply();
  });
}

async function init() {
  initMap();
  bindEvents();
  await Promise.all([loadServiceCatalog(), loadLocationPresets()]);
  if (els.searchMode) els.searchMode.value = "leads";
  if (els.searchFocus) els.searchFocus.value = "all";
  if (els.radius && !els.radius.value) els.radius.value = "8";
  updateCircle();
  renderResults();
}

init();
