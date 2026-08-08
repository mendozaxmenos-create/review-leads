function readDashboardToken() {
  const params = new URLSearchParams(window.location.search);
  const fromUrl = (params.get("k") || "").trim();
  if (fromUrl) {
    sessionStorage.setItem("sofia_dash_k", fromUrl);
    return fromUrl;
  }
  return (sessionStorage.getItem("sofia_dash_k") || "").trim();
}

const dashboardToken = readDashboardToken();

function withDashAuth(path) {
  if (!dashboardToken) return path;
  const sep = path.includes("?") ? "&" : "?";
  return `${path}${sep}k=${encodeURIComponent(dashboardToken)}`;
}

async function api(path, opts = {}) {
  const headers = {};
  if (!(opts.body instanceof FormData)) headers["Content-Type"] = "application/json";
  if (dashboardToken) headers["X-Dashboard-Token"] = dashboardToken;
  const res = await fetch(withDashAuth(path), {
    ...opts,
    headers: { ...headers, ...(opts.headers || {}) },
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const detail = data.detail;
    const msg = typeof detail === "string" ? detail : detail?.[0]?.msg || data.message || res.statusText;
    throw new Error(msg);
  }
  return data;
}

const QUICK_REPLIES = [
  {
    id: "pitch",
    title: "Pitch único — convertir (con demo)",
    body: `Hola, soy Gustavo de SofIA.

Te armo un bot de WhatsApp para {{nombre}}: el huésped escribe a tu número y el bot atiende solo — disponibilidad, precios, dudas y pre-reserva con seña (transferencia o Mercado Pago). Vos recibís el aviso ordenado, sin estar pegado al celular de noche ni el finde.

Probá cómo se siente (demo interactiva, 2 minutos):
{{demo_url}}

Escribí como si fueras un huésped: pedí fechas, elegí cabaña y simulá la seña.

Valor: $19.000/mes. Lo dejamos funcionando con tus precios, reglas y check-in.

Si te cierra, respondeme y lo armamos para {{nombre}}.`,
  },
  {
    id: "no",
    title: "No les interesa (cortesía)",
    body: `Ningún drama, gracias por responder.
Si más adelante se complica contestar el WhatsApp, acá estoy. Éxitos con {{nombre}}.`,
  },
];

const els = {
  stats: document.getElementById("stats-row"),
  blockers: document.getElementById("blockers"),
  webhookHint: document.getElementById("webhook-hint"),
  handoffHint: document.getElementById("handoff-hint"),
  error: document.getElementById("error"),
  summary: document.getElementById("summary"),
  kpiViewPanel: document.getElementById("kpi-view-panel"),
  kpiViewTitle: document.getElementById("kpi-view-title"),
  kpiViewHint: document.getElementById("kpi-view-hint"),
  kpiViewBody: document.getElementById("kpi-view-tbody"),
  kpiClearBtn: document.getElementById("kpi-clear-btn"),
  workflowPanels: document.getElementById("workflow-panels"),
  fabHome: document.getElementById("fab-home"),
  baseName: document.getElementById("base-name"),
  basesSelect: document.getElementById("bases-select"),
  sentZonesSelect: document.getElementById("sent-zones-select"),
  sentZonesWrap: document.getElementById("sent-zones-wrap"),
  basesHint: document.getElementById("bases-hint"),
  priorityBody: document.getElementById("priority-tbody"),
  respondedBody: document.getElementById("responded-tbody"),
  followupBody: document.getElementById("followup-tbody"),
  prioritySection: document.getElementById("priority-section"),
  sendsBody: document.getElementById("sends-tbody"),
  loading: document.getElementById("loading"),
  loadingText: document.getElementById("loading-text"),
  liveBtn: document.getElementById("live-btn"),
  batchSize: document.getElementById("batch-size"),
  csvFile: document.getElementById("csv-file"),
  quickReplies: document.getElementById("quick-replies"),
  replyPlaceName: document.getElementById("reply-place-name"),
  replyDemoUrl: document.getElementById("reply-demo-url"),
};

/** @type {string|null} */
let activeKpi = null;
/** @type {Array|null} */
let allPipelineLeads = null;

const KPI_CARDS = [
  {
    key: "base",
    label: "En base",
    tip: "Leads del CSV limpio",
    value: (d) => d.universe,
  },
  {
    key: "pending",
    label: "Pendientes de envío",
    tip: "Aún no recibieron el WhatsApp de Twilio",
    value: (d) => d.pending_to_send,
  },
  {
    key: "sent",
    label: "Enviados",
    tip: "Mensajes live únicos vía Twilio",
    value: (d) => d.sent_live_unique || 0,
  },
  {
    key: "responded_human",
    label: "Por contestar (humano)",
    tip: "Personas que escribieron — sección Prioridad",
    value: (d) => d.responded_human ?? "—",
  },
  {
    key: "responded_auto",
    label: "Solo auto-reply",
    tip: "Bot contestó; si retoma un humano, sube a Prioridad",
    value: (d) => d.responded_auto ?? "—",
  },
  {
    key: "follow_up",
    label: "En seguimiento",
    tip: "Ya les contestaste desde tu WhatsApp",
    value: (d) => d.follow_up || (d.by_status || {}).follow_up || 0,
  },
  {
    key: "contacted",
    label: "Sin reply",
    tip: "Twilio OK, todavía no contestaron",
    value: (d) => (d.by_status || {}).contacted || 0,
  },
];

function showError(msg) {
  els.error.textContent = msg;
  els.error.hidden = false;
}
function hideError() {
  els.error.textContent = "";
  els.error.hidden = true;
}
function setLoading(on, text) {
  els.loading.hidden = !on;
  if (text) els.loadingText.textContent = text;
}
function escapeHtml(s) {
  return String(s ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function waLink(phone) {
  const d = String(phone || "").replace(/\D/g, "");
  return d ? `https://wa.me/${d}` : null;
}

function placeToken() {
  const name = (els.replyPlaceName?.value || "").trim();
  return name || "tu complejo";
}

function demoLink() {
  const custom = (els.replyDemoUrl?.value || "").trim();
  if (custom) return custom.replace(/\/$/, "");
  return `${window.location.origin}/demo`;
}

async function loadShareLink() {
  try {
    const data = await api("/api/demo/share-link");
    if (data?.url && els.replyDemoUrl) {
      els.replyDemoUrl.value = data.url;
      renderQuickReplies();
    } else if (els.replyDemoUrl && !els.replyDemoUrl.value) {
      els.replyDemoUrl.value = "";
      els.replyDemoUrl.placeholder = "Configurá DEMO_PUBLIC_URL en el server";
    }
  } catch {
    /* local sin endpoint ok */
  }
}

function fillReply(template) {
  return template.replaceAll("{{nombre}}", placeToken()).replaceAll("{{demo_url}}", demoLink());
}

async function copyText(text, btn) {
  try {
    await navigator.clipboard.writeText(text);
    const prev = btn.textContent;
    btn.textContent = "Copiado";
    setTimeout(() => {
      btn.textContent = prev;
    }, 1400);
  } catch {
    showError("No se pudo copiar al portapapeles");
  }
}

function renderQuickReplies() {
  if (!els.quickReplies) return;
  els.quickReplies.innerHTML = QUICK_REPLIES.map((r) => {
    const filled = fillReply(r.body);
    return `<article class="quick-reply-card" data-reply-id="${escapeHtml(r.id)}">
      <div class="quick-reply-head">
        <h3>${escapeHtml(r.title)}</h3>
        <button type="button" class="btn btn-sm btn-primary" data-copy-reply="${escapeHtml(r.id)}">Copiar</button>
      </div>
      <pre>${escapeHtml(filled)}</pre>
    </article>`;
  }).join("");

  els.quickReplies.querySelectorAll("[data-copy-reply]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const item = QUICK_REPLIES.find((x) => x.id === btn.dataset.copyReply);
      if (!item) return;
      copyText(fillReply(item.body), btn);
    });
  });
}

function renderStats(d) {
  els.stats.innerHTML = KPI_CARDS.map((card) => {
    const val = card.value(d);
    const active = activeKpi === card.key ? " is-active" : "";
    return `<button type="button" class="admin-stat-card${active}" data-kpi="${escapeHtml(card.key)}" title="${escapeHtml(card.tip)}">
      <div class="admin-stat-label">${escapeHtml(card.label)}</div>
      <div class="admin-stat-value">${val}</div>
    </button>`;
  }).join("");

  els.stats.querySelectorAll("[data-kpi]").forEach((btn) => {
    btn.addEventListener("click", () => selectKpi(btn.dataset.kpi));
  });

  const blockers = d.blockers || [];
  els.blockers.textContent = blockers.length
    ? "Para live: " + blockers.join(" · ")
    : "Credenciales OK — podés enviar lotes live.";
  els.liveBtn.disabled = blockers.length > 0;
  els.webhookHint.textContent = d.webhook_inbound
    ? `Webhook respuestas (Twilio → acá): ${window.location.origin}${d.webhook_inbound} (ngrok/Fly en local)`
    : "";
  if (els.handoffHint) {
    els.handoffHint.textContent =
      d.handoff_hint ||
      "El bot del alojamiento respondió solo. Si un humano escribe después, el lead salta a «Prioridad» arriba.";
  }
  renderBaseDropdowns(d);
}

function renderBaseDropdowns(d) {
  const bases = Array.isArray(d.bases) ? d.bases : [];

  if (els.basesSelect) {
    if (!bases.length) {
      els.basesSelect.innerHTML = `<option value="">Ninguna base en CRM todavía</option>`;
    } else {
      els.basesSelect.innerHTML =
        `<option value="">— Elegí una base (${bases.length}) —</option>` +
        bases
          .map(
            (b) =>
              `<option value="${escapeHtml(b.base)}">${escapeHtml(b.base)} · ${b.leads} leads · ${b.sent} enviados · ${b.pending} pend.</option>`
          )
          .join("");
    }
  }

  // Zonas solo después de elegir base
  if (els.sentZonesWrap) els.sentZonesWrap.hidden = true;
  if (els.sentZonesSelect) {
    els.sentZonesSelect.innerHTML = `<option value="">Elegí una base primero</option>`;
  }
  if (els.basesHint) {
    els.basesHint.textContent =
      "Primero elegí una base; después vas a ver solo las zonas contactadas de esa base.";
  }
}

async function onBaseSelectChange() {
  const val = els.basesSelect?.value;
  if (!val) {
    if (els.sentZonesWrap) els.sentZonesWrap.hidden = true;
    if (els.sentZonesSelect) {
      els.sentZonesSelect.innerHTML = `<option value="">Elegí una base primero</option>`;
    }
    if (els.basesHint) {
      els.basesHint.textContent =
        "Primero elegí una base; después vas a ver solo las zonas contactadas de esa base.";
    }
    return;
  }
  if (els.baseName) els.baseName.value = val;
  if (els.sentZonesWrap) els.sentZonesWrap.hidden = false;
  if (els.sentZonesSelect) {
    els.sentZonesSelect.innerHTML = `<option value="">Cargando zonas…</option>`;
  }
  try {
    const data = await api(
      `/api/campaigns/mendoza-cabanas/bases/${encodeURIComponent(val)}/sent-zones`
    );
    const zones = data.zones || [];
    if (!els.sentZonesSelect) return;
    if (!zones.length) {
      els.sentZonesSelect.innerHTML = `<option value="">Sin envíos live en «${escapeHtml(val)}»</option>`;
      if (els.basesHint) {
        els.basesHint.textContent = `Base «${val}» sin zonas contactadas todavía.`;
      }
      return;
    }
    const total = zones.reduce((acc, z) => acc + (z.places || 0), 0);
    els.sentZonesSelect.innerHTML =
      `<option value="">— Zonas de «${escapeHtml(val)}» (${zones.length}) —</option>` +
      zones
        .map(
          (z) =>
            `<option value="${escapeHtml(z.zone)}">${escapeHtml(z.zone)} · ${z.places} lugares</option>`
        )
        .join("");
    if (els.basesHint) {
      els.basesHint.textContent = `Base «${val}»: ${total} lugares enviados en ${zones.length} zonas. Elegí una zona para verlos.`;
    }
  } catch (err) {
    showError(err.message);
    if (els.sentZonesSelect) {
      els.sentZonesSelect.innerHTML = `<option value="">Error al cargar zonas</option>`;
    }
  }
}

async function onSentZoneSelectChange() {
  const zone = els.sentZonesSelect?.value;
  const base = els.basesSelect?.value;
  if (!zone || !base) return;
  activeKpi = "sent";
  els.stats?.querySelectorAll("[data-kpi]").forEach((btn) => {
    btn.classList.toggle("is-active", btn.dataset.kpi === "sent");
  });
  setLoading(true, `Cargando enviados en ${zone}…`);
  try {
    const q = new URLSearchParams({ limit: "500", zone });
    const data = await api(`/api/campaigns/mendoza-cabanas/kpi/sent?${q}`);
    // Etiqueta más clara con la base
    if (data && !String(data.label || "").includes(base)) {
      data.label = `${data.label || "Enviados"} · base ${base}`;
    }
    renderKpiView(data);
  } catch (err) {
    showError(err.message);
  } finally {
    setLoading(false);
  }
}

async function selectKpi(kpi) {
  if (!kpi) return;
  if (activeKpi === kpi) {
    clearKpiFilter();
    return;
  }
  activeKpi = kpi;
  els.stats.querySelectorAll("[data-kpi]").forEach((btn) => {
    btn.classList.toggle("is-active", btn.dataset.kpi === kpi);
  });
  setLoading(true, "Cargando contactos…");
  try {
    const data = await api(`/api/campaigns/mendoza-cabanas/kpi/${encodeURIComponent(kpi)}?limit=500`);
    renderKpiView(data);
  } catch (err) {
    showError(err.message);
  } finally {
    setLoading(false);
  }
}

function clearKpiFilter() {
  activeKpi = null;
  els.stats.querySelectorAll("[data-kpi]").forEach((btn) => btn.classList.remove("is-active"));
  if (els.kpiViewPanel) els.kpiViewPanel.hidden = true;
  if (els.workflowPanels) els.workflowPanels.hidden = false;
  updateFab();
  window.scrollTo({ top: 0, behavior: "smooth" });
}

function renderKpiView(data) {
  const rows = data?.leads || [];
  const label = data?.label || activeKpi || "KPI";
  if (els.kpiViewPanel) els.kpiViewPanel.hidden = false;
  if (els.workflowPanels) els.workflowPanels.hidden = true;
  if (els.kpiViewTitle) els.kpiViewTitle.textContent = `${label} (${data?.count ?? rows.length})`;
  if (els.kpiViewHint) {
    els.kpiViewHint.textContent =
      "Misma vista que Prioridad. Tocá «Cerrar · volver a KPIs» o el botón flotante ↑.";
  }
  const showHandoff = activeKpi === "responded_human" || activeKpi === "responded_auto";
  renderLeadActionRows(rows, els.kpiViewBody, {
    emptyText: "Sin contactos en este KPI",
    showHandoff,
  });
  updateFab();
  els.kpiViewPanel?.scrollIntoView({ behavior: "smooth", block: "start" });
}

function updateFab() {
  if (!els.fabHome) return;
  const show = Boolean(activeKpi) || window.scrollY > 280;
  els.fabHome.hidden = !show;
}

function goHome() {
  if (activeKpi) clearKpiFilter();
  else window.scrollTo({ top: 0, behavior: "smooth" });
}

function bindLeadRowActions(tbody) {
  if (!tbody) return;
  tbody.querySelectorAll("[data-handoff]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      try {
        await api("/api/campaigns/mendoza-cabanas/handoff", {
          method: "POST",
          body: JSON.stringify({ place_id: btn.dataset.handoff, channel: "whatsapp_personal" }),
        });
        await refresh();
      } catch (err) {
        showError(err.message);
      }
    });
  });
  tbody.querySelectorAll("[data-discard]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const ok = window.confirm("¿Descartar este lead? (STOP / no interesado)\nSale de Contestaron y Seguimiento.");
      if (!ok) return;
      try {
        await api("/api/campaigns/mendoza-cabanas/discard", {
          method: "POST",
          body: JSON.stringify({
            place_id: btn.dataset.discard,
            reason: btn.dataset.discardReason || "STOP / no interesado",
          }),
        });
        await refresh();
      } catch (err) {
        showError(err.message);
      }
    });
  });
  tbody.querySelectorAll("[data-use-name]").forEach((btn) => {
    btn.addEventListener("click", () => {
      if (els.replyPlaceName) {
        els.replyPlaceName.value = btn.dataset.useName || "";
        renderQuickReplies();
        els.replyPlaceName.scrollIntoView({ behavior: "smooth", block: "center" });
      }
    });
  });
}

function replyBadgeClass(threadKind) {
  if (threadKind === "human_only" || threadKind === "human_after_auto") return "reply-human";
  if (threadKind === "auto_only") return "reply-auto";
  if (threadKind === "stop") return "reply-stop";
  return "reply-other";
}

function formatReplyCell(r) {
  const replies = Array.isArray(r.inbound_replies) ? r.inbound_replies : [];
  const count = r.reply_inbound_count ? `${r.reply_inbound_count} msg` : "";
  const hint =
    r.reply_thread_kind === "auto_only"
      ? "Solo el bot. Si escribe un humano, pasa a Prioridad."
      : r.reply_thread_kind === "human_after_auto"
        ? "Primero contestó el bot; después escribió una persona — darle seguimiento."
        : r.reply_thread_kind === "human_only"
          ? "Escribió una persona — darle seguimiento."
          : r.reply_thread_kind === "pending"
            ? "Todavía no le mandamos el WhatsApp de Twilio."
            : r.reply_thread_kind === "sent" || r.reply_thread_kind === "contacted"
              ? "Ya se envió el primer mensaje; aún no hay respuesta humana."
              : "";

  let threadHtml = "";
  if (replies.length > 1) {
    threadHtml = `<ol class="reply-thread">${replies
      .map((m, i) => {
        const body = String(m.body || "").trim();
        const short = body.length > 160 ? `${body.slice(0, 160)}…` : body;
        const label = m.kind_label || m.kind || "";
        return `<li>
            <span class="reply-thread-idx">Msg ${i + 1} · ${escapeHtml(label)}</span>
            <div class="reply-snippet">${escapeHtml(short || "—")}</div>
          </li>`;
      })
      .join("")}</ol>`;
  } else if (replies.length === 1 || r.last_reply) {
    const snippet = String((replies[0] && replies[0].body) || r.last_reply || "").trim();
    const short = snippet.length > 160 ? `${snippet.slice(0, 160)}…` : snippet;
    threadHtml = `<div class="reply-snippet">${escapeHtml(short || "—")}</div>`;
  } else {
    threadHtml = `<div class="reply-snippet">${escapeHtml(r.notes || "—")}</div>`;
  }

  return `<div class="reply-cell">
      ${threadHtml}
      ${hint ? `<div class="reply-hint">${escapeHtml(hint)}</div>` : ""}
      <div class="reply-meta">${escapeHtml((r.reply_thread_label || r.reply_last_kind_label || "") + (count ? ` · ${count}` : ""))}</div>
    </div>`;
}

function isPriorityReply(r) {
  const kind = r.reply_thread_kind || "";
  return kind === "human_only" || kind === "human_after_auto" || kind === "empty_only";
}

function renderLeadActionRows(rows, tbody, { emptyText, showHandoff }) {
  if (!tbody) return;
  if (!rows.length) {
    tbody.innerHTML = `<tr><td colspan="5" class="admin-empty">${escapeHtml(emptyText)}</td></tr>`;
    return;
  }
  tbody.innerHTML = rows
    .map((r) => {
      const wa = r.wa_me || waLink(r.phone);
      const mail = r.mailto;
      const reply = String(r.last_reply || "");
      const looksOptOut = /^\s*(stop|baja|cancelar|no(,?\s*gracias)?)\s*\.?\s*$/i.test(reply);
      const kind = r.reply_thread_kind || "";
      let label = r.reply_thread_label || "Respuesta";
      if (r._priorityFromFollowUp) {
        label = `Seguimiento · ${label}`;
      }
      const rowClass =
        kind === "auto_only"
          ? "row-auto-reply"
          : kind === "human_after_auto" || kind === "human_only"
            ? "row-priority-human"
            : "";
      const handoffBtn =
        showHandoff && !r._priorityFromFollowUp
          ? `<button type="button" class="btn btn-sm btn-primary" data-handoff="${escapeHtml(r.place_id)}">Ya contesté</button>`
          : r._priorityFromFollowUp
            ? `<span class="reply-meta">Ya en seguimiento</span>`
            : "";
      return `<tr class="${rowClass}">
        <td>${escapeHtml(r.place_name)}</td>
        <td>${escapeHtml(r.zone || "")}</td>
        <td><span class="badge ${replyBadgeClass(kind)}" title="${escapeHtml(label)}">${escapeHtml(label)}</span></td>
        <td>${formatReplyCell(r)}</td>
        <td class="actions-row">
          ${wa ? `<a class="btn btn-sm btn-whatsapp-primary" href="${wa}" target="_blank" rel="noopener">Abrir en mi WhatsApp</a>` : ""}
          ${mail ? `<a class="btn btn-sm btn-secondary" href="${mail}">Email</a>` : ""}
          <button type="button" class="btn btn-sm btn-secondary" data-use-name="${escapeHtml(r.place_name || "")}">Usar nombre</button>
          ${handoffBtn}
          <button type="button" class="btn btn-sm btn-secondary" data-discard="${escapeHtml(r.place_id)}" data-discard-reason="${looksOptOut ? "STOP" : "no interesado"}">${looksOptOut ? "Descartar STOP" : "No interesado"}</button>
        </td>
      </tr>`;
    })
    .join("");
  bindLeadRowActions(tbody);
}

function renderResponded(respondedRows, followUpRows = []) {
  const list = Array.isArray(respondedRows) ? respondedRows : [];
  const follow = Array.isArray(followUpRows) ? followUpRows : [];

  const fromResponded = list.filter(isPriorityReply);
  const otherResponded = list.filter((r) => !isPriorityReply(r) && r.reply_thread_kind !== "auto_only");
  // Humanos / retomaron que ya marcaste «Ya contesté» siguen en Prioridad para no perderlos
  const fromFollowUp = follow
    .filter((r) => r.reply_thread_kind === "human_only" || r.reply_thread_kind === "human_after_auto")
    .map((r) => ({ ...r, _priorityFromFollowUp: true }));

  const seen = new Set();
  const priorityRows = [];
  for (const r of [...fromResponded, ...fromFollowUp, ...otherResponded]) {
    if (!r.place_id || seen.has(r.place_id)) continue;
    seen.add(r.place_id);
    priorityRows.push(r);
  }

  const autoOnly = list.filter((r) => r.reply_thread_kind === "auto_only");

  renderLeadActionRows(priorityRows, els.priorityBody, {
    emptyText: "Nadie humano pendiente — cuando alguien retome después del bot, aparece acá",
    showHandoff: true,
  });
  renderLeadActionRows(autoOnly, els.respondedBody, {
    emptyText: "Ningún auto-reply pendiente",
    showHandoff: true,
  });
  if (els.prioritySection) {
    els.prioritySection.classList.toggle("has-items", priorityRows.length > 0);
    const title = els.prioritySection.querySelector("h2");
    if (title) {
      title.textContent =
        priorityRows.length > 0
          ? `Prioridad — escribió un humano (${priorityRows.length})`
          : "Prioridad — escribió un humano";
    }
  }
}

function renderFollowUp(rows) {
  renderLeadActionRows(rows, els.followupBody, {
    emptyText: "Todavía no marcaste ninguno",
    showHandoff: false,
  });
}

function renderLeads(_rows) {
  // Pipeline completo se ve vía KPIs (evita página enorme)
}

function renderSends(rows) {
  if (!els.sendsBody) return;
  if (!rows.length) {
    els.sendsBody.innerHTML = `<tr><td colspan="5" class="admin-empty">Sin envíos</td></tr>`;
    return;
  }
  els.sendsBody.innerHTML = rows
    .map((r) => {
      const mode = r.dry_run ? "dry" : "live";
      const detail = r.ok ? r.twilio_sid || r.twilio_status || "ok" : r.error || "fail";
      return `<tr>
        <td>${escapeHtml((r.created_at || "").slice(0, 19).replace("T", " "))}</td>
        <td>${escapeHtml(r.place_name || "")}</td>
        <td>${mode}</td>
        <td>${r.ok ? "✓" : "✗"}</td>
        <td>${escapeHtml(detail)}</td>
      </tr>`;
    })
    .join("");
}

async function refresh() {
  hideError();
  setLoading(true, "Actualizando…");
  try {
    const settled = await Promise.allSettled([
      api("/api/campaigns/mendoza-cabanas/dashboard"),
      api("/api/campaigns/mendoza-cabanas/sends?limit=100"),
      api("/api/campaigns/mendoza-cabanas/responded?limit=100"),
      api("/api/campaigns/mendoza-cabanas/follow-up?limit=100"),
    ]);
    const [dash, sends, responded, followUp] = settled.map((r) =>
      r.status === "fulfilled" ? r.value : null
    );
    const errors = settled
      .filter((r) => r.status === "rejected")
      .map((r) => r.reason?.message || String(r.reason));
    if (dash) renderStats(dash);
    if (sends) renderSends(sends);
    if (responded || followUp) renderResponded(responded || [], followUp || []);
    if (followUp) renderFollowUp(followUp);
    else if (els.followupBody) {
      els.followupBody.innerHTML = `<tr><td colspan="5" class="admin-empty">Seguimiento no disponible (reiniciá el server)</td></tr>`;
    }
    if (activeKpi) {
      try {
        const data = await api(`/api/campaigns/mendoza-cabanas/kpi/${encodeURIComponent(activeKpi)}?limit=500`);
        renderKpiView(data);
      } catch (err) {
        /* keep previous */
      }
    }
    updateFab();
    if (!dash) {
      throw new Error(errors[0] || "No se pudo cargar el dashboard");
    }
    if (errors.length) {
      els.summary.hidden = false;
      els.summary.textContent = "Parcial: " + errors.join(" · ");
    }
  } catch (err) {
    showError(err.message);
  } finally {
    setLoading(false);
  }
}

async function syncCrm() {
  hideError();
  setLoading(true, "Sync CSV → CRM…");
  try {
    const data = await api("/api/campaigns/mendoza-cabanas/sync", { method: "POST", body: "{}" });
    els.summary.hidden = false;
    els.summary.textContent = `Sync: ${data.rows} filas (+${data.inserted} / ~${data.updated} upd).`;
    await refresh();
  } catch (err) {
    showError(err.message);
  } finally {
    setLoading(false);
  }
}

async function uploadCsv() {
  hideError();
  const file = els.csvFile.files?.[0];
  if (!file) {
    showError("Elegí un archivo CSV");
    return;
  }
  setLoading(true, "Subiendo CSV…");
  try {
    const fd = new FormData();
    fd.append("file", file);
    fd.append("base_name", (els.baseName?.value || "Mendoza").trim() || "Mendoza");
    const data = await api("/api/campaigns/mendoza-cabanas/upload", { method: "POST", body: fd });
    els.summary.hidden = false;
    const dup = data.already_messaged_in_other_send
      ? ` · ${data.already_messaged_in_other_send} ya contactados en otra base`
      : "";
    els.summary.textContent = `Upload «${data.base || "base"}»: ${data.rows} filas (+${data.inserted} / ~${data.updated} upd)${dup}.`;
    await refresh();
  } catch (err) {
    showError(err.message);
  } finally {
    setLoading(false);
  }
}

async function sendWa({ dryRun }) {
  hideError();
  const limit = Number(els.batchSize.value) || 10;
  if (!dryRun) {
    const ok = window.confirm(
      `¿Enviar LIVE hasta ${limit} WhatsApp por Twilio?\n\n` +
        `• Solo a pendientes (no reenvía si ya salió en Mendoza u otra base)\n` +
        `• Es el primer mensaje (plantilla)\n` +
        `• Dry-run no manda nada — este sí cobra/envía`
    );
    if (!ok) return;
  }
  setLoading(true, dryRun ? "Dry-run…" : `Enviando ${limit}…`);
  try {
    const data = await api("/api/campaigns/mendoza-cabanas/send-wa", {
      method: "POST",
      body: JSON.stringify({
        dry_run: dryRun,
        limit,
        skip_already_sent: true,
        mark_contacted: true,
      }),
    });
    els.summary.hidden = false;
    els.summary.textContent = data.summary;
    await refresh();
  } catch (err) {
    showError(err.message);
  } finally {
    setLoading(false);
  }
}

document.getElementById("refresh-btn").addEventListener("click", refresh);
document.getElementById("sync-btn").addEventListener("click", syncCrm);
document.getElementById("upload-btn").addEventListener("click", uploadCsv);
document.getElementById("dry-btn").addEventListener("click", () => sendWa({ dryRun: true }));
document.getElementById("live-btn").addEventListener("click", () => sendWa({ dryRun: false }));
els.replyPlaceName?.addEventListener("input", renderQuickReplies);
els.replyDemoUrl?.addEventListener("input", renderQuickReplies);
els.kpiClearBtn?.addEventListener("click", clearKpiFilter);
els.fabHome?.addEventListener("click", goHome);
els.basesSelect?.addEventListener("change", onBaseSelectChange);
els.sentZonesSelect?.addEventListener("change", onSentZoneSelectChange);
window.addEventListener("scroll", () => updateFab(), { passive: true });

if (els.replyDemoUrl && !els.replyDemoUrl.value) {
  els.replyDemoUrl.placeholder = "https://tu-app.onrender.com/demo";
}
renderQuickReplies();
loadShareLink();
refresh();
setInterval(refresh, 30000);
