async function api(path, opts = {}) {
  const res = await fetch(path, {
    headers: opts.body instanceof FormData ? undefined : { "Content-Type": "application/json" },
    ...opts,
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
    id: "si",
    title: "Dijeron que sí / contame",
    body: `Perfecto. Te resumo rápido:

Es un bot de WhatsApp para tu cabaña: responde consultas 24/7, informa disponibilidad y toma la pre-reserva sin que tengas que estar pegado al celular.

Cuesta $19.000/mes. Lo dejamos funcionando con tu info (precios, reglas, check-in, etc.).

¿Querés que te muestre con un ejemplo cómo quedaría para {{nombre}}?`,
  },
  {
    id: "como",
    title: "¿Cómo funciona?",
    body: `Así de simple:

1) El huésped te escribe por WhatsApp
2) El bot responde al toque (precios, disponibilidad, dudas frecuentes)
3) Si quiere reservar, lo guía a confirmar / dejar seña
4) A vos te llega el aviso ordenado

Todo por $19.000/mes. ¿Te armo una demo corta con el nombre de tu complejo?`,
  },
  {
    id: "precio",
    title: "Precio / está caro",
    body: `Es $19.000/mes, sin setup raro de entrada.

La idea es que no se te escapen consultas de noche/finde: con 1–2 reservas extra al mes ya se paga solo.

Si querés, lo vemos 5 minutos con tu caso y después decidís.`,
  },
  {
    id: "pienso",
    title: "Lo pienso / después",
    body: `Dale, sin problema.
Si te sirve, mañana te mando 3 capturas de cómo responde el bot a: “¿hay lugar el finde?”, “¿precio?” y “quiero reservar”.
¿Te las paso?`,
  },
  {
    id: "no",
    title: "No les interesa",
    body: `Ningún drama, gracias por responder.
Si más adelante se complica contestar WhatsApp, acá estoy. Éxitos con {{nombre}}.`,
  },
];

const els = {
  stats: document.getElementById("stats-row"),
  blockers: document.getElementById("blockers"),
  webhookHint: document.getElementById("webhook-hint"),
  handoffHint: document.getElementById("handoff-hint"),
  error: document.getElementById("error"),
  summary: document.getElementById("summary"),
  leadsBody: document.getElementById("leads-tbody"),
  respondedBody: document.getElementById("responded-tbody"),
  sendsBody: document.getElementById("sends-tbody"),
  loading: document.getElementById("loading"),
  loadingText: document.getElementById("loading-text"),
  liveBtn: document.getElementById("live-btn"),
  batchSize: document.getElementById("batch-size"),
  csvFile: document.getElementById("csv-file"),
  quickReplies: document.getElementById("quick-replies"),
  replyPlaceName: document.getElementById("reply-place-name"),
};

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

function fillReply(template) {
  return template.replaceAll("{{nombre}}", placeToken());
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
  const by = d.by_status || {};
  els.stats.innerHTML = [
    ["En base", d.universe, "Leads del CSV limpio"],
    ["Pendientes de envío", d.pending_to_send, "Aún no recibieron el WhatsApp de Twilio"],
    ["Enviados", d.sent_live_unique || 0, "Mensajes live únicos vía Twilio"],
    ["Contestaron", d.responded || by.responded || 0, "Respondieron al primer mensaje"],
    ["Contactados sin reply", by.contacted || 0, "Twilio OK, todavía no contestaron"],
  ]
    .map(
      ([label, val, tip]) =>
        `<div class="admin-stat-card" title="${escapeHtml(tip)}"><div class="admin-stat-label">${escapeHtml(label)}</div><div class="admin-stat-value">${val}</div></div>`
    )
    .join("");

  const blockers = d.blockers || [];
  els.blockers.textContent = blockers.length
    ? "Para live: " + blockers.join(" · ")
    : "Credenciales OK — podés enviar lotes live.";
  els.liveBtn.disabled = blockers.length > 0;
  els.webhookHint.textContent = d.webhook_inbound
    ? `Webhook respuestas (Twilio → acá): ${window.location.origin}${d.webhook_inbound} (ngrok/Fly en local)`
    : "";
  els.handoffHint.textContent = d.handoff_hint || "";
}

function renderResponded(rows) {
  if (!rows.length) {
    els.respondedBody.innerHTML = `<tr><td colspan="4" class="admin-empty">Nadie respondió todavía</td></tr>`;
    return;
  }
  els.respondedBody.innerHTML = rows
    .map((r) => {
      const wa = r.wa_me || waLink(r.phone);
      const mail = r.mailto;
      return `<tr>
        <td>${escapeHtml(r.place_name)}</td>
        <td>${escapeHtml(r.zone || "")}</td>
        <td>${escapeHtml(r.last_reply || r.notes || "—")}</td>
        <td class="actions-row">
          ${wa ? `<a class="btn btn-sm btn-whatsapp-primary" href="${wa}" target="_blank" rel="noopener">Abrir en mi WhatsApp</a>` : ""}
          ${mail ? `<a class="btn btn-sm btn-secondary" href="${mail}">Email</a>` : ""}
          <button type="button" class="btn btn-sm btn-secondary" data-use-name="${escapeHtml(r.place_name || "")}">Usar nombre</button>
          <button type="button" class="btn btn-sm btn-secondary" data-handoff="${escapeHtml(r.place_id)}">Marcar handoff</button>
        </td>
      </tr>`;
    })
    .join("");

  els.respondedBody.querySelectorAll("[data-handoff]").forEach((btn) => {
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

  els.respondedBody.querySelectorAll("[data-use-name]").forEach((btn) => {
    btn.addEventListener("click", () => {
      if (els.replyPlaceName) {
        els.replyPlaceName.value = btn.dataset.useName || "";
        renderQuickReplies();
        els.replyPlaceName.scrollIntoView({ behavior: "smooth", block: "center" });
      }
    });
  });
}

function renderLeads(rows) {
  if (!rows.length) {
    els.leadsBody.innerHTML = `<tr><td colspan="5" class="admin-empty">Sin leads. Subí o sync CSV.</td></tr>`;
    return;
  }
  els.leadsBody.innerHTML = rows
    .slice(0, 200)
    .map((r) => {
      const lead = r.lead || {};
      const wa = waLink(lead.phone);
      return `<tr>
        <td>${escapeHtml(lead.place_name || "")}</td>
        <td>${escapeHtml(lead.zone || "")}</td>
        <td>${escapeHtml(lead.phone || "")}</td>
        <td><span class="badge ${escapeHtml(r.status)}">${escapeHtml(r.status)}</span></td>
        <td>${wa ? `<a class="btn btn-sm btn-secondary" href="${wa}" target="_blank" rel="noopener">wa.me</a>` : "—"}</td>
      </tr>`;
    })
    .join("");
}

function renderSends(rows) {
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
    const [dash, leads, sends, responded] = await Promise.all([
      api("/api/campaigns/mendoza-cabanas/dashboard"),
      api("/api/campaigns/mendoza-cabanas/leads?limit=500"),
      api("/api/campaigns/mendoza-cabanas/sends?limit=100"),
      api("/api/campaigns/mendoza-cabanas/responded?limit=100"),
    ]);
    renderStats(dash);
    renderLeads(leads);
    renderSends(sends);
    renderResponded(responded);
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
    const data = await api("/api/campaigns/mendoza-cabanas/upload", { method: "POST", body: fd });
    els.summary.hidden = false;
    els.summary.textContent = `Upload OK: ${data.rows} leads en CRM.`;
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
    const ok = window.confirm(`¿Enviar LIVE ${limit} mensajes por Twilio?\nSolo el primer contacto.`);
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

renderQuickReplies();
refresh();
setInterval(refresh, 30000);
