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
];

let map;
let marker;
let circle;
let center = { ...DEFAULT_CENTER };
let projects = [];
let leads = [];
let categorySuggestions = [];
let selectedIds = new Set();
let activeFilter = "all";
let activeLeadForBot = null;
let botMessages = [];
let currentMessageBody = "";

const els = {
  projectSelect: document.getElementById("project-select"),
  serviceDesc: document.getElementById("service-desc"),
  businessType: document.getElementById("business-type"),
  radius: document.getElementById("radius"),
  radiusValue: document.getElementById("radius-value"),
  maxPlaces: document.getElementById("max-places"),
  addressSearch: document.getElementById("address-search"),
  searchBtn: document.getElementById("search-btn"),
  results: document.getElementById("results"),
  summary: document.getElementById("summary"),
  suggestions: document.getElementById("suggestions"),
  error: document.getElementById("error"),
  loading: document.getElementById("loading"),
  loadingText: document.getElementById("loading-text"),
  statPlaces: document.getElementById("stat-places"),
  statReviews: document.getElementById("stat-reviews"),
  statSelected: document.getElementById("stat-selected"),
  selectAll: document.getElementById("select-all"),
  exportBtn: document.getElementById("export-btn"),
  messagesBtn: document.getElementById("messages-btn"),
  clearSelection: document.getElementById("clear-selection"),
  messageModal: document.getElementById("message-modal"),
  messageModalBody: document.getElementById("message-modal-body"),
  copyMessageBtn: document.getElementById("copy-message-btn"),
  whatsappOpenBtn: document.getElementById("whatsapp-open-btn"),
  botDrawer: document.getElementById("bot-drawer"),
  botTitle: document.getElementById("bot-title"),
  botSubtitle: document.getElementById("bot-subtitle"),
  botStage: document.getElementById("bot-stage"),
  chatLog: document.getElementById("chat-log"),
  chatInput: document.getElementById("chat-input"),
  chatSendBtn: document.getElementById("chat-send-btn"),
  chatStartBtn: document.getElementById("chat-start-btn"),
  botNextAction: document.getElementById("bot-next-action"),
};

function leadId(lead, index) {
  return `${lead.place_id}-${index}`;
}

function leadInputFrom(lead) {
  return {
    place_name: lead.place_name,
    place_id: lead.place_id,
    address: lead.address,
    phone: lead.phone,
    website: lead.website,
    review_text: lead.review_text,
    lead_fit: lead.lead_fit,
    reason: lead.reason,
    suggested_pitch: lead.suggested_pitch,
  };
}

function projectPayload() {
  return { project_id: els.projectSelect.value };
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

async function apiPost(url, body) {
  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const data = await res.json();
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
  const radiusM = Number(els.radius.value) * 1000;
  els.radiusValue.textContent = `${els.radius.value} km`;
  if (circle) {
    circle.setLatLng([center.lat, center.lng]);
    circle.setRadius(radiusM);
  } else {
    circle = L.circle([center.lat, center.lng], {
      radius: radiusM,
      color: "#3b82f6",
      fillColor: "#3b82f6",
      fillOpacity: 0.12,
      weight: 2,
    }).addTo(map);
  }
}

async function geocodeAddress(query) {
  const url = `https://nominatim.openstreetmap.org/search?format=json&q=${encodeURIComponent(query)}&limit=1`;
  const res = await fetch(url, { headers: { Accept: "application/json" } });
  const data = await res.json();
  if (!data.length) throw new Error("No encontramos esa dirección. Probá con ciudad + barrio.");
  return { lat: parseFloat(data[0].lat), lng: parseFloat(data[0].lon) };
}

async function loadProjects() {
  const res = await fetch("/api/projects");
  projects = await res.json();
  els.projectSelect.innerHTML = projects.map((p) => `<option value="${p.id}">${p.name}</option>`).join("");
  els.businessType.innerHTML = BUSINESS_TYPES.map((t) => `<option value="${t.value}">${t.label}</option>`).join("");
  onProjectChange();
}

function onProjectChange() {
  const project = projects.find((p) => p.id === els.projectSelect.value);
  if (!project) return;
  els.serviceDesc.textContent = project.description;
  if (project.suggested_business_types?.length) {
    const suggested = project.suggested_business_types[0];
    if ([...els.businessType.options].some((o) => o.value === suggested)) {
      els.businessType.value = suggested;
    }
  }
}

function applySuggestion(suggestion) {
  els.businessType.value = suggestion.business_type;
  if (suggestion.project_id && [...els.projectSelect.options].some((o) => o.value === suggestion.project_id)) {
    els.projectSelect.value = suggestion.project_id;
    onProjectChange();
  }
  runSearch();
}

function renderSuggestions() {
  if (!categorySuggestions.length) {
    els.suggestions.hidden = true;
    els.suggestions.innerHTML = "";
    return;
  }

  els.suggestions.hidden = false;
  els.suggestions.innerHTML = `
    <h3>💡 Categorías sugeridas para tu zona</h3>
    ${categorySuggestions
      .map(
        (s) => `
      <div class="suggestion-item">
        <div>
          <strong>${escapeHtml(s.business_type_label)}</strong>
          <span class="suggestion-meta"> · ${escapeHtml(s.project_name)} · ${s.places_in_area} negocios · score ${Math.round(s.score * 100)}%</span>
          <p>${escapeHtml(s.reason)}</p>
        </div>
        <button type="button" class="btn btn-secondary btn-sm" data-suggest-type="${escapeHtml(s.business_type)}" data-suggest-project="${escapeHtml(s.project_id)}">
          Buscar
        </button>
      </div>`
      )
      .join("")}`;

  els.suggestions.querySelectorAll("[data-suggest-type]").forEach((btn) => {
    btn.addEventListener("click", () => {
      applySuggestion({
        business_type: btn.dataset.suggestType,
        project_id: btn.dataset.suggestProject,
      });
    });
  });
}

function filteredLeads() {
  if (activeFilter === "all") return leads;
  return leads.filter((l) => l.lead_fit === activeFilter);
}

function contactsHtml(lead) {
  const parts = [];
  if (lead.phone) {
    parts.push(`<a class="contact-link" href="tel:${escapeHtml(lead.phone)}">📞 ${escapeHtml(lead.phone)}</a>`);
  }
  if (lead.website) {
    parts.push(`<a class="contact-link" href="${escapeHtml(lead.website)}" target="_blank" rel="noopener">🌐 Web</a>`);
  }
  if (lead.google_maps_url) {
    parts.push(`<a class="contact-link" href="${escapeHtml(lead.google_maps_url)}" target="_blank" rel="noopener">📍 Maps</a>`);
  }
  return parts.length ? `<div class="contacts">${parts.join("")}</div>` : `<div class="contacts"><span class="suggestion-meta">Sin teléfono/web en Google</span></div>`;
}

function renderResults() {
  const visible = filteredLeads();

  if (!leads.length) {
    els.results.innerHTML = `
      <div class="empty">
        <div class="empty-icon">🔍</div>
        <p>Configurá la zona en el mapa, elegí un servicio y tocá <strong>Buscar leads</strong>.</p>
      </div>`;
    els.summary.hidden = true;
    updateStats(0, 0);
    return;
  }

  els.summary.hidden = false;

  if (!visible.length) {
    els.results.innerHTML = `<div class="empty"><p>No hay leads con el filtro seleccionado.</p></div>`;
    return;
  }

  els.results.innerHTML = visible
    .map((lead) => {
      const idx = leads.indexOf(lead);
      const id = leadId(lead, idx);
      const checked = selectedIds.has(id) ? "checked" : "";
      const selectedClass = selectedIds.has(id) ? "selected" : "";
      const stars = lead.review_rating ? `${"★".repeat(lead.review_rating)}${"☆".repeat(5 - lead.review_rating)}` : "";

      return `
        <article class="lead-card ${selectedClass}" data-id="${id}">
          <input type="checkbox" ${checked} aria-label="Seleccionar lead" />
          <div>
            <div class="lead-header">
              <h3>${escapeHtml(lead.place_name)}</h3>
              <span class="badge ${lead.lead_fit}">${lead.lead_fit}</span>
            </div>
            <p class="meta">
              ${escapeHtml(lead.address || "Sin dirección")}
              ${lead.rating ? ` · ⭐ ${lead.rating}` : ""}
              ${lead.author ? ` · ${escapeHtml(lead.author)}` : ""}
              ${stars ? ` · ${stars}` : ""}
            </p>
            ${contactsHtml(lead)}
            <p class="review-text">"${escapeHtml(lead.review_text)}"</p>
            <p class="reason"><strong>Por qué es lead:</strong> ${escapeHtml(lead.reason)}</p>
            ${lead.suggested_pitch ? `<p class="pitch"><strong>Pitch sugerido:</strong> ${escapeHtml(lead.suggested_pitch)}</p>` : ""}
            <div class="lead-actions">
              <button type="button" class="btn btn-secondary btn-sm" data-action="message" data-id="${id}">Escribir mensaje</button>
              <button type="button" class="btn btn-secondary btn-sm" data-action="bot" data-id="${id}">Bot de ventas</button>
            </div>
          </div>
        </article>`;
    })
    .join("");

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
      if (e.target.closest("button, a, input")) return;
      toggle();
    });

    card.querySelector('[data-action="message"]')?.addEventListener("click", (e) => {
      e.stopPropagation();
      openMessageForLead(id);
    });

    card.querySelector('[data-action="bot"]')?.addEventListener("click", (e) => {
      e.stopPropagation();
      openBotForLead(id);
    });
  });
}

function escapeHtml(text) {
  const div = document.createElement("div");
  div.textContent = text ?? "";
  return div.innerHTML;
}

function getLeadById(id) {
  const idx = leads.findIndex((lead, i) => leadId(lead, i) === id);
  return idx >= 0 ? { lead: leads[idx], idx } : null;
}

function showMessageModal(title, html, message) {
  document.getElementById("modal-title").textContent = title;
  els.messageModalBody.innerHTML = html;
  currentMessageBody = message.body || message;
  els.whatsappOpenBtn.hidden = !message.whatsapp_link;
  if (message.whatsapp_link) els.whatsappOpenBtn.href = message.whatsapp_link;
  els.messageModal.hidden = false;
}

function closeMessageModal() {
  els.messageModal.hidden = true;
}

async function openMessageForLead(id) {
  const found = getLeadById(id);
  if (!found) return;

  setLoading(true, "Generando mensaje personalizado…");
  try {
    const data = await apiPost("/api/outreach/message", {
      lead: leadInputFrom(found.lead),
      ...projectPayload(),
      channel: "whatsapp",
    });

    const html = `
      <p>${escapeHtml(data.body)}</p>
      ${data.tips ? `<div class="message-tips"><strong>Tip:</strong> ${escapeHtml(data.tips)}</div>` : ""}`;
    showMessageModal(`Mensaje para ${found.lead.place_name}`, html, data);
  } catch (err) {
    showError(err.message);
  } finally {
    setLoading(false);
  }
}

async function openBulkMessages() {
  const selected = leads
    .map((lead, idx) => ({ lead, id: leadId(lead, idx) }))
    .filter(({ id }) => selectedIds.has(id));

  if (!selected.length) return;

  setLoading(true, `Generando ${selected.length} mensajes…`);
  try {
    const data = await apiPost("/api/outreach/messages/bulk", {
      leads: selected.map(({ lead }) => leadInputFrom(lead)),
      ...projectPayload(),
      channel: "whatsapp",
    });

    const html = data.messages
      .map(
        (item) => `
        <div class="bulk-message-item">
          <h4>${escapeHtml(item.place_name)}</h4>
          <p>${escapeHtml(item.message.body)}</p>
          ${item.message.whatsapp_link ? `<a class="contact-link" href="${escapeHtml(item.message.whatsapp_link)}" target="_blank" rel="noopener">Abrir WhatsApp</a>` : ""}
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
      ...projectPayload(),
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
      ...projectPayload(),
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

function updateStats(places, reviews) {
  els.statPlaces.textContent = places;
  els.statReviews.textContent = reviews;
  updateSelectedCount();
}

function updateSelectedCount() {
  els.statSelected.textContent = selectedIds.size;
  const disabled = selectedIds.size === 0;
  els.exportBtn.disabled = disabled;
  els.messagesBtn.disabled = disabled;
}

async function runSearch() {
  hideError();
  setLoading(true, "Buscando y clasificando reseñas… puede tardar un minuto.");

  try {
    const data = await apiPost("/api/search", {
      center,
      radius_km: Number(els.radius.value),
      business_type: els.businessType.value,
      max_places: Number(els.maxPlaces.value),
      project_id: els.projectSelect.value,
    });

    leads = data.leads || [];
    categorySuggestions = data.category_suggestions || [];
    selectedIds.clear();
    els.summary.textContent = data.summary || "";
    updateStats(data.places_scanned || 0, data.reviews_analyzed || 0);
    renderSuggestions();
    renderResults();
  } catch (err) {
    showError(err.message || "Ocurrió un error inesperado");
  } finally {
    setLoading(false);
  }
}

function exportSelected() {
  const rows = leads
    .map((lead, idx) => ({ lead, id: leadId(lead, idx) }))
    .filter(({ id }) => selectedIds.has(id))
    .map(({ lead }) => lead);

  if (!rows.length) return;

  const headers = [
    "negocio", "telefono", "web", "direccion", "rating_negocio", "autor_resena",
    "rating_resena", "relevancia", "resena", "razon", "pitch", "place_id", "google_maps",
  ];

  const csvLines = [
    headers.join(","),
    ...rows.map((r) =>
      [
        r.place_name, r.phone || "", r.website || "", r.address || "", r.rating ?? "",
        r.author || "", r.review_rating ?? "", r.lead_fit, r.review_text, r.reason,
        r.suggested_pitch || "", r.place_id, r.google_maps_url || "",
      ].map((v) => `"${String(v).replace(/"/g, '""')}"`).join(",")
    ),
  ];

  const blob = new Blob(["\uFEFF" + csvLines.join("\n")], { type: "text/csv;charset=utf-8;" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `leads-${els.projectSelect.value}-${new Date().toISOString().slice(0, 10)}.csv`;
  a.click();
  URL.revokeObjectURL(url);
}

function bindEvents() {
  els.radius.addEventListener("input", updateCircle);
  els.projectSelect.addEventListener("change", onProjectChange);
  els.searchBtn.addEventListener("click", runSearch);

  document.getElementById("geocode-btn").addEventListener("click", async () => {
    const q = els.addressSearch.value.trim();
    if (!q) return;
    hideError();
    setLoading(true);
    try {
      const pos = await geocodeAddress(q);
      center = pos;
      marker.setLatLng([pos.lat, pos.lng]);
      map.setView([pos.lat, pos.lng], 14);
      updateCircle();
    } catch (err) {
      showError(err.message);
    } finally {
      setLoading(false);
    }
  });

  els.addressSearch.addEventListener("keydown", (e) => {
    if (e.key === "Enter") {
      e.preventDefault();
      document.getElementById("geocode-btn").click();
    }
  });

  document.querySelectorAll(".chip").forEach((chip) => {
    chip.addEventListener("click", () => {
      document.querySelectorAll(".chip").forEach((c) => c.classList.remove("active"));
      chip.classList.add("active");
      activeFilter = chip.dataset.filter;
      renderResults();
    });
  });

  els.selectAll.addEventListener("click", () => {
    filteredLeads().forEach((lead) => selectedIds.add(leadId(lead, leads.indexOf(lead))));
    renderResults();
  });

  els.clearSelection.addEventListener("click", () => {
    selectedIds.clear();
    renderResults();
  });

  els.exportBtn.addEventListener("click", exportSelected);
  els.messagesBtn.addEventListener("click", openBulkMessages);

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
  await loadProjects();
  renderResults();
}

init();
