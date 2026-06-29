const BUSINESS_TYPE_LABELS = {
  restaurant: "Restaurantes",
  cafe: "Cafés",
  hair_salon: "Peluquerías",
  spa: "Spas",
  dentist: "Dentistas",
  gym: "Gimnasios",
  store: "Tiendas",
  real_estate_agency: "Inmobiliarias",
  lawyer: "Abogados",
  accounting: "Contadores",
  bakery: "Panaderías",
  car_dealer: "Concesionarios",
  doctor: "Médicos",
  insurance_agency: "Seguros",
};

let statuses = [];
let allLeads = [];
let projects = [];
let currentMessageBody = "";

const els = {
  statsRow: document.getElementById("stats-row"),
  filterStatus: document.getElementById("filter-status"),
  filterProject: document.getElementById("filter-project"),
  filterFit: document.getElementById("filter-fit"),
  filterSearch: document.getElementById("filter-search"),
  visibleCount: document.getElementById("visible-count"),
  leadsTbody: document.getElementById("leads-tbody"),
  error: document.getElementById("error"),
  loading: document.getElementById("loading"),
  loadingText: document.getElementById("loading-text"),
  refreshBtn: document.getElementById("refresh-btn"),
  exportBtn: document.getElementById("export-btn"),
  messageModal: document.getElementById("message-modal"),
  messageModalBody: document.getElementById("message-modal-body"),
  copyMessageBtn: document.getElementById("copy-message-btn"),
  whatsappOpenBtn: document.getElementById("whatsapp-open-btn"),
};

async function apiGet(url) {
  const res = await fetch(url);
  const data = await res.json();
  if (!res.ok) throw new Error(data.detail || "Error en la solicitud");
  return data;
}

async function apiPatch(url, body) {
  const res = await fetch(url, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const data = await res.json();
  if (!res.ok) throw new Error(data.detail || "Error en la solicitud");
  return data;
}

async function apiPost(url, body) {
  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const data = await res.json();
  if (!res.ok) throw new Error(data.detail || "Error en la solicitud");
  return data;
}

function setLoading(on, text = "Cargando…") {
  els.loading.hidden = !on;
  els.loadingText.textContent = text;
}

function showError(msg) {
  els.error.textContent = msg;
  els.error.classList.add("visible");
}

function hideError() {
  els.error.textContent = "";
  els.error.classList.remove("visible");
}

function escapeHtml(text) {
  const div = document.createElement("div");
  div.textContent = text ?? "";
  return div.innerHTML;
}

function businessTypeLabel(value) {
  return BUSINESS_TYPE_LABELS[value] || value || "—";
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
  };
}

function filteredLeads() {
  const q = els.filterSearch.value.trim().toLowerCase();
  return allLeads.filter((item) => {
    const lead = item.lead;
    if (!q) return true;
    const haystack = [
      lead.place_name,
      lead.address,
      item.project_name,
      item.business_type,
      ...(lead.themes || []),
      lead.reason,
    ]
      .filter(Boolean)
      .join(" ")
      .toLowerCase();
    return haystack.includes(q);
  });
}

function statCount(stats, code) {
  const by = stats?.by_status_code || {};
  return by[code] ?? by[String(code)] ?? 0;
}

function renderStats(stats) {
  const cards = [
    { code: null, label: "Total", count: stats.total, className: "stat-total" },
    ...statuses.map((s) => ({
      code: s.code,
      label: `${s.code} · ${s.label}`,
      count: statCount(stats, s.code),
      className: `stat-step stat-step-${s.code}`,
      filter: s.value,
    })),
  ];

  els.statsRow.innerHTML = cards
    .map(
      (card) => `
    <button type="button" class="admin-stat-card ${card.className}" data-status="${card.filter || ""}">
      <span class="admin-stat-value">${card.count}</span>
      <span class="admin-stat-label">${escapeHtml(card.label)}</span>
    </button>`
    )
    .join("");

  els.statsRow.querySelectorAll("[data-status]").forEach((btn) => {
    btn.addEventListener("click", () => {
      els.filterStatus.value = btn.dataset.status;
      loadLeads();
    });
  });
}

function statusSelectHtml(item) {
  const current = item.status || "new";
  return `
    <select class="admin-status-select" data-id="${item.id}" title="Estado del pipeline">
      ${statuses
        .map(
          (s) =>
            `<option value="${s.value}" ${current === s.value ? "selected" : ""}>${s.code} — ${escapeHtml(s.label)}</option>`
        )
        .join("")}
    </select>`;
}

function themesCell(lead) {
  const themes = lead.themes || [];
  if (!themes.length) return '<span class="muted">—</span>';
  return themes
    .slice(0, 3)
    .map((t) => `<span class="theme-tag theme-tag-sm">${escapeHtml(t)}</span>`)
    .join(" ");
}

const leadMessages = new Map();

function whatsappHref(phone, message = "") {
  if (!phone) return null;
  const digits = phone.replace(/\D/g, "");
  if (digits.length < 8) return null;
  const text = message ? `?text=${encodeURIComponent(message.slice(0, 500))}` : "";
  return `https://wa.me/${digits}${text}`;
}

function cacheLeadMessage(placeId, data) {
  if (!data?.body || !placeId) return;
  leadMessages.set(placeId, { body: data.body, whatsapp_link: data.whatsapp_link || null });
}

function getLeadMessageBody(item) {
  const cached = leadMessages.get(item.lead.place_id);
  if (cached?.body) return cached.body;
  return item.lead.suggested_pitch || "";
}

async function openWhatsAppForPhone(item) {
  if (!item?.lead?.phone) return;
  hideError();
  let body = getLeadMessageBody(item);
  if (!body) {
    setLoading(true, "Generando mensaje…");
    try {
      const message = await apiPost("/api/outreach/message", {
        lead: leadInputFrom(item.lead),
        project_id: item.project_id || item.lead.recommended_project_id,
        channel: "whatsapp",
      });
      cacheLeadMessage(item.lead.place_id, message);
      body = message.body;
    } catch (err) {
      showError(err.message);
      return;
    } finally {
      setLoading(false);
    }
  }
  const cached = leadMessages.get(item.lead.place_id);
  const url = cached?.whatsapp_link && cached.body === body ? cached.whatsapp_link : whatsappHref(item.lead.phone, body);
  if (url) window.open(url, "_blank", "noopener");
}

function contactCell(lead, placeId) {
  const parts = [];
  if (lead.phone) {
    parts.push(
      `<a href="#" class="contact-phone" data-place-id="${escapeHtml(placeId)}">${escapeHtml(lead.phone)}</a>`
    );
  }
  if (lead.website) parts.push(`<a href="${escapeHtml(lead.website)}" target="_blank" rel="noopener">Web</a>`);
  return parts.length ? parts.join("<br>") : '<span class="muted">Sin teléfono</span>';
}

function formatDate(iso) {
  if (!iso) return "—";
  return new Date(iso).toLocaleString("es-AR", {
    day: "2-digit",
    month: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function renderTable() {
  const visible = filteredLeads();
  els.visibleCount.textContent = `${visible.length} lead${visible.length === 1 ? "" : "s"}`;

  if (!visible.length) {
    els.leadsTbody.innerHTML = `
      <tr>
        <td colspan="11" class="admin-empty">
          ${allLeads.length ? "Ningún lead coincide con los filtros." : "Todavía no hay leads guardados. Hacé una búsqueda primero."}
        </td>
      </tr>`;
    return;
  }

  els.leadsTbody.innerHTML = visible
    .map((item) => {
      const lead = item.lead;
      const waDisabled = lead.phone ? "" : " disabled";
      return `
      <tr data-id="${item.id}">
        <td class="admin-code">${item.status_code}</td>
        <td>
          <strong>${escapeHtml(lead.place_name)}</strong>
          <div class="admin-sub">${escapeHtml(lead.address || "")}</div>
        </td>
        <td>${escapeHtml(item.project_name || lead.recommended_project_name || item.project_id || "—")}</td>
        <td>${escapeHtml(lead.business_type_label || item.business_type || businessTypeLabel(item.business_type))}</td>
        <td><span class="badge ${lead.lead_fit}">${lead.lead_fit}</span></td>
        <td class="admin-themes">${themesCell(lead)}</td>
        <td class="admin-contact">${contactCell(lead, lead.place_id)}</td>
        <td>${statusSelectHtml(item)}</td>
        <td>
          <textarea class="admin-notes" data-id="${item.id}" rows="2" placeholder="Notas…">${escapeHtml(item.notes || "")}</textarea>
        </td>
        <td class="admin-date">${formatDate(item.updated_at)}</td>
        <td class="admin-actions">
          <button type="button" class="btn btn-secondary btn-xs" data-action="whatsapp" data-id="${item.id}"${waDisabled}>WA</button>
        </td>
      </tr>`;
    })
    .join("");

  els.leadsTbody.querySelectorAll(".admin-status-select").forEach((select) => {
    select.addEventListener("change", async (e) => {
      const id = Number(e.target.dataset.id);
      const newStatus = e.target.value;
      try {
        const updated = await apiPatch(`/api/history/leads/${id}`, { status: newStatus });
        const idx = allLeads.findIndex((l) => l.id === id);
        if (idx >= 0) {
          allLeads[idx] = {
            ...allLeads[idx],
            status: updated.status,
            status_code: updated.status_code,
            status_label: updated.status_label,
            notes: updated.notes,
            updated_at: updated.updated_at,
            lead: updated.lead || allLeads[idx].lead,
          };
        }
        const row = e.target.closest("tr");
        row.querySelector(".admin-code").textContent = updated.status_code;
        const stats = await apiGet("/api/admin/stats");
        renderStats(stats);
        const filter = els.filterStatus.value;
        if (filter && filter !== newStatus) {
          await loadLeads();
        } else {
          renderTable();
        }
      } catch (err) {
        showError(err.message);
      }
    });
  });

  els.leadsTbody.querySelectorAll(".admin-notes").forEach((textarea) => {
    textarea.addEventListener("blur", async (e) => {
      const id = Number(e.target.dataset.id);
      const item = allLeads.find((l) => l.id === id);
      if (!item || (item.notes || "") === e.target.value) return;
      try {
        const updated = await apiPatch(`/api/history/leads/${id}`, { notes: e.target.value });
        item.notes = updated.notes;
        item.updated_at = updated.updated_at;
      } catch (err) {
        showError(err.message);
      }
    });
  });

  els.leadsTbody.querySelectorAll(".contact-phone").forEach((link) => {
    link.addEventListener("click", (e) => {
      e.preventDefault();
      const item = allLeads.find((l) => l.lead.place_id === link.dataset.placeId);
      if (item) openWhatsAppForPhone(item);
    });
  });

  els.leadsTbody.querySelectorAll('[data-action="whatsapp"]').forEach((btn) => {
    btn.addEventListener("click", () => openWhatsApp(Number(btn.dataset.id)));
  });
}

async function refreshStats() {
  const stats = await apiGet("/api/admin/stats");
  renderStats(stats);
}

async function loadProjects() {
  projects = await apiGet("/api/admin/projects");
  const current = els.filterProject.value;
  els.filterProject.innerHTML =
    '<option value="">Todos</option>' +
    projects
      .map(
        (p) =>
          `<option value="${escapeHtml(p.project_id || "")}">${escapeHtml(p.project_name || p.project_id || "Servicio")}</option>`
      )
      .join("");
  if (current) els.filterProject.value = current;
}

async function loadStatuses() {
  statuses = await apiGet("/api/admin/statuses");
  const current = els.filterStatus.value;
  els.filterStatus.innerHTML =
    '<option value="">Todos</option>' +
    statuses
      .map((s) => `<option value="${s.value}">${s.code} — ${escapeHtml(s.label)}</option>`)
      .join("");
  if (current) els.filterStatus.value = current;
}

async function loadLeads() {
  hideError();
  setLoading(true, "Cargando leads…");
  try {
    const params = new URLSearchParams();
    if (els.filterStatus.value) params.set("status", els.filterStatus.value);
    if (els.filterProject.value) params.set("project_id", els.filterProject.value);
    if (els.filterFit.value) params.set("lead_fit", els.filterFit.value);
    params.set("limit", "1000");

    const [leads, stats] = await Promise.all([
      apiGet(`/api/admin/leads?${params}`),
      apiGet("/api/admin/stats"),
    ]);
    allLeads = leads;
    renderStats(stats);
    renderTable();
  } catch (err) {
    showError(err.message);
    els.leadsTbody.innerHTML = `<tr><td colspan="11" class="admin-empty">Error al cargar.</td></tr>`;
  } finally {
    setLoading(false);
  }
}

async function openWhatsApp(id) {
  const item = allLeads.find((l) => l.id === id);
  if (!item?.lead?.phone) return;

  setLoading(true, "Generando mensaje…");
  try {
    const message = await apiPost("/api/outreach/message", {
      lead: leadInputFrom(item.lead),
      project_id: item.project_id,
      channel: "whatsapp",
    });
    showMessageModal(item.lead.place_name, message);
    cacheLeadMessage(item.lead.place_id, message);
    if (item.status === "new") {
      const updated = await apiPatch(`/api/history/leads/${id}`, { status: "contacted" });
      const idx = allLeads.findIndex((l) => l.id === id);
      if (idx >= 0) {
        allLeads[idx] = {
          ...allLeads[idx],
          status: updated.status,
          status_code: updated.status_code,
          status_label: updated.status_label,
          notes: updated.notes,
          updated_at: updated.updated_at,
        };
      }
      const stats = await apiGet("/api/admin/stats");
      renderStats(stats);
      renderTable();
    }
  } catch (err) {
    showError(err.message);
  } finally {
    setLoading(false);
  }
}

function showMessageModal(title, message) {
  document.getElementById("modal-title").textContent = `WhatsApp — ${title}`;
  els.messageModalBody.innerHTML = `<pre class="message-pre">${escapeHtml(message.body)}</pre>`;
  currentMessageBody = message.body || "";
  els.whatsappOpenBtn.hidden = !message.whatsapp_link;
  if (message.whatsapp_link) els.whatsappOpenBtn.href = message.whatsapp_link;
  els.messageModal.hidden = false;
}

function closeMessageModal() {
  els.messageModal.hidden = true;
}

function exportCsv() {
  const visible = filteredLeads();
  if (!visible.length) return;

  const headers = [
    "estado_codigo",
    "estado",
    "negocio",
    "direccion",
    "servicio",
    "tipo_negocio",
    "fit",
    "temas",
    "telefono",
    "notas",
    "actualizado",
  ];
  const rows = visible.map((item) => {
    const lead = item.lead;
    return [
      item.status_code,
      item.status_label,
      lead.place_name,
      lead.address || "",
      item.project_name || item.project_id || "",
      item.business_type || "",
      lead.lead_fit,
      (lead.themes || []).join("; "),
      lead.phone || "",
      item.notes || "",
      item.updated_at,
    ];
  });

  const csv = [headers, ...rows]
    .map((row) => row.map((cell) => `"${String(cell).replace(/"/g, '""')}"`).join(","))
    .join("\n");

  const blob = new Blob(["\ufeff" + csv], { type: "text/csv;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `leads-crm-${new Date().toISOString().slice(0, 10)}.csv`;
  a.click();
  URL.revokeObjectURL(url);
}

els.refreshBtn.addEventListener("click", () => loadLeads());
els.exportBtn.addEventListener("click", exportCsv);
els.filterStatus.addEventListener("change", loadLeads);
els.filterProject.addEventListener("change", loadLeads);
els.filterFit.addEventListener("change", loadLeads);
els.filterSearch.addEventListener("input", renderTable);

els.copyMessageBtn.addEventListener("click", async () => {
  try {
    await navigator.clipboard.writeText(currentMessageBody);
  } catch {
  }
});

document.querySelectorAll("[data-close-modal]").forEach((el) => {
  el.addEventListener("click", closeMessageModal);
});

async function init() {
  await loadStatuses();
  await loadProjects();
  await loadLeads();
}

init();
