const els = {
  messages: document.getElementById("messages"),
  form: document.getElementById("chat-form"),
  input: document.getElementById("chat-input"),
  sendBtn: document.getElementById("send-btn"),
  restart: document.getElementById("restart-btn"),
  loading: document.getElementById("loading"),
  turns: document.getElementById("turns-left"),
  propName: document.getElementById("demo-property-name"),
  propZone: document.getElementById("demo-property-zone"),
  chips: document.getElementById("chips"),
  chipsLabel: document.querySelector(".demo-guides-label"),
  datesPanel: document.querySelector(".demo-dates-panel"),
  dateIn: document.getElementById("date-in"),
  dateOut: document.getElementById("date-out"),
  guests: document.getElementById("guests"),
  sendDates: document.getElementById("send-dates-btn"),
  ownerFeed: document.getElementById("owner-feed"),
  ownerActions: document.getElementById("owner-actions"),
  approveXfer: document.getElementById("approve-xfer-btn"),
  rejectXfer: document.getElementById("reject-xfer-btn"),
};

let sessionId = null;
let sending = false;
let currentGuide = "dates";
let currentChips = [];
let lastReservation = null;
let demoToken = "";

function readDemoToken() {
  const params = new URLSearchParams(window.location.search);
  const fromUrl = (params.get("k") || "").trim();
  if (fromUrl) {
    sessionStorage.setItem("sofia_demo_k", fromUrl);
    return fromUrl;
  }
  return (sessionStorage.getItem("sofia_demo_k") || "").trim();
}

demoToken = readDemoToken();

function showAccessDenied(msg) {
  if (els.messages) {
    els.messages.innerHTML = "";
    appendBubble(
      "bot",
      msg ||
        "Esta demo es privada. Pedile a Gustavo de SofIA el link completo (con acceso)."
    );
  }
  if (els.chips) els.chips.innerHTML = "";
  if (els.datesPanel) els.datesPanel.hidden = true;
  if (els.form) els.form.hidden = true;
}

const GUIDE_META = {
  dates: {
    label: "Elegí fechas",
    placeholder: "O escribí fechas… ej: viernes a domingo",
    showCalendar: true,
  },
  guests: {
    label: "¿Cuántas personas?",
    placeholder: "Ej: somos 4",
    showCalendar: true,
  },
  quote: {
    label: "Siguiente paso",
    placeholder: "Ej: quiero reservar / ¿incluye desayuno?",
    showCalendar: false,
  },
  units: {
    label: "Elegí cabaña",
    placeholder: "Tocá una cabaña o escribí el nombre…",
    showCalendar: false,
  },
  book: {
    label: "Confirmar reserva",
    placeholder: "Ej: sí, quiero la pre-reserva",
    showCalendar: false,
  },
  pay: {
    label: "Cómo pagar la seña",
    placeholder: "Elegí transferencia o Mercado Pago…",
    showCalendar: false,
  },
  pay_mp: {
    label: "Mercado Pago (webhook)",
    placeholder: "Simulá el pago recibido…",
    showCalendar: false,
  },
  pay_xfer: {
    label: "Transferencia",
    placeholder: "Cuando transferís, tocá Ya transferí…",
    showCalendar: false,
  },
  pay_owner: {
    label: "Esperando dueño",
    placeholder: "El dueño aprueba en el panel CRM…",
    showCalendar: false,
  },
  name: {
    label: "Tu nombre",
    placeholder: "Escribí tu nombre… ej: Me llamo Ana",
    showCalendar: false,
  },
  done: {
    label: "Reserva confirmada",
    placeholder: "Reiniciá el chat para probar de nuevo",
    showCalendar: false,
  },
  general: {
    label: "Atajos",
    placeholder: "Escribí tu respuesta…",
    showCalendar: false,
  },
};

const CHIP_SETS = {
  dates: [
    { label: "Este finde", text: "Hola, ¿hay lugar este viernes a domingo?" },
    { label: "Próximo finde", text: "Busco el próximo viernes a domingo." },
    { label: "Usar calendario", text: "__focus_calendar__" },
  ],
  guests: [
    { label: "2 personas", text: "Somos 2 personas." },
    { label: "3 personas", text: "Somos 3 personas." },
    { label: "4 personas", text: "Somos 4 personas." },
    { label: "6 personas", text: "Somos 6 personas." },
  ],
  quote: [
    { label: "Quiero reservar", text: "Me interesa, quiero reservar. ¿Cómo seguimos?" },
    { label: "¿Precio total?", text: "¿Cuánto sería el total de la estadía?" },
    { label: "¿Seña?", text: "¿Cuánto es la seña y cómo la pago?" },
    { label: "Check-in", text: "¿A qué hora es el check-in y el check-out?" },
  ],
  units: [],
  book: [
    { label: "Sí, reservo", text: "Sí, quiero la pre-reserva." },
    { label: "¿Cómo pago la seña?", text: "Dale, ¿cómo pago la seña del 30%?" },
    { label: "Otra fecha", text: "¿Tenés otra fecha disponible?" },
  ],
  pay: [
    { label: "Transferencia", text: "Prefiero pagar la seña por transferencia al alias del complejo." },
    { label: "Mercado Pago", text: "Prefiero pagar la seña con Mercado Pago." },
    { label: "¿Alias de nuevo?", text: "Pasame otra vez el alias y el link de Mercado Pago." },
  ],
  pay_mp: [
    { label: "Simular pago MP recibido", text: "__simulate_mp__" },
    { label: "Prefiero transferencia", text: "Prefiero pagar la seña por transferencia al alias del complejo." },
  ],
  pay_xfer: [
    { label: "Ya transferí", text: "Listo, ya hice la seña (demo). Te mando el comprobante." },
    { label: "Prefiero Mercado Pago", text: "Prefiero pagar la seña con Mercado Pago." },
  ],
  pay_owner: [
    { label: "Esperando aprobación…", text: "__noop__" },
  ],
  name: [
    { label: "Me llamo Ana", text: "Me llamo Ana" },
    { label: "Me llamo Martín", text: "Me llamo Martín" },
    { label: "Me llamo Lucía", text: "Me llamo Lucía" },
    { label: "Me llamo Gustavo", text: "Me llamo Gustavo" },
  ],
  done: [
    { label: "Reiniciar demo", text: "__restart__" },
  ],
  general: [
    { label: "¿Precio?", text: "¿Cuánto sale por noche?" },
    { label: "Quiero reservar", text: "Me interesa, quiero reservar." },
    { label: "Check-in", text: "¿A qué hora es el check-in?" },
    { label: "Otras fechas", text: "Quiero consultar otras fechas." },
  ],
};

function escapeHtml(s) {
  return String(s ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function setLoading(on) {
  sending = on;
  els.loading.hidden = !on;
  els.sendBtn.disabled = on;
  els.input.disabled = on;
  els.sendDates.disabled = on;
  els.chips?.querySelectorAll("button").forEach((b) => {
    b.disabled = on;
  });
  if (els.approveXfer) els.approveXfer.disabled = on;
  if (els.rejectXfer) els.rejectXfer.disabled = on;
}

function appendBubble(role, text) {
  const div = document.createElement("div");
  div.className = `demo-bubble demo-bubble-${role}`;
  div.innerHTML = `<div class="demo-bubble-label">${role === "user" ? "Vos" : "Bot"}</div><div class="demo-bubble-text">${escapeHtml(text).replace(/\n/g, "<br>")}</div>`;
  els.messages.appendChild(div);
  els.messages.scrollTop = els.messages.scrollHeight;
}

async function api(path, body) {
  const headers = { "Content-Type": "application/json" };
  if (demoToken) headers["X-Demo-Token"] = demoToken;
  const url = demoToken ? `${path}${path.includes("?") ? "&" : "?"}k=${encodeURIComponent(demoToken)}` : path;
  const res = await fetch(url, {
    method: "POST",
    headers,
    body: JSON.stringify(body || {}),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const detail = data.detail || data.message || res.statusText;
    const err = new Error(typeof detail === "string" ? detail : "Error");
    err.status = res.status;
    err.detail = detail;
    throw err;
  }
  return data;
}

function isoLocal(d) {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

function initDateDefaults() {
  const today = new Date();
  const inDate = new Date(today);
  const day = inDate.getDay();
  const add = day <= 5 ? 5 - day : 6;
  inDate.setDate(inDate.getDate() + (add === 0 ? 7 : add));
  const outDate = new Date(inDate);
  outDate.setDate(outDate.getDate() + 2);
  els.dateIn.min = isoLocal(today);
  els.dateOut.min = isoLocal(today);
  els.dateIn.value = isoLocal(inDate);
  els.dateOut.value = isoLocal(outDate);
}

function money(n) {
  if (n == null) return "—";
  return `$${Number(n).toLocaleString("es-AR")}`;
}

function renderOwnerFeed(events, reservation) {
  lastReservation = reservation || lastReservation;
  const list = Array.isArray(events) ? events : [];
  if (!els.ownerFeed) return;

  if (!list.length) {
    els.ownerFeed.innerHTML = `<p class="map-hint">Todavía no hay eventos de pago.</p>`;
  } else {
    els.ownerFeed.innerHTML = list
      .slice()
      .reverse()
      .map((ev) => {
        const st = escapeHtml(ev.status || "");
        return `<article class="demo-owner-card demo-owner-${escapeHtml(ev.kind || "")}">
          <p class="demo-owner-card-title">${escapeHtml(ev.title || "Evento")}</p>
          <p class="demo-owner-card-detail">${escapeHtml(ev.detail || "")}</p>
          <p class="map-hint">${escapeHtml(ev.reservation_id || "")} · ${st}</p>
        </article>`;
      })
      .join("");
  }

  const st = reservation?.status;
  const showApprove = st === "reported";
  if (els.ownerActions) els.ownerActions.hidden = !showApprove;
}

function resolveGuide(data) {
  const apiGuide = data.guide || "general";
  const res = data.reservation || {};
  const reply = String(data.reply || "").toLowerCase();

  if (res.status === "awaiting_mp") return "pay_mp";
  if (res.status === "awaiting_transfer") return "pay_xfer";
  if (res.status === "reported") return "pay_owner";
  if (res.status === "confirmed") return "done";
  if (res.unit_id && !res.guest_name) return "name";
  if (res.unit_id && res.guest_name && res.status === "draft") return "pay";
  if (res.offered_units && !res.unit_id) return "units";
  if (!res.check_in) return "dates";
  if (res.check_in && (res.guests == null || res.guests === undefined)) return "guests";
  if (/fecha|check-in|check-out|calendario|entrada y salida/.test(reply) && !res.check_in) {
    return "dates";
  }
  return apiGuide;
}

function applyGuide(guide, unitOptions) {
  currentGuide = guide && (CHIP_SETS[guide] || guide === "units") ? guide : "general";
  const meta = GUIDE_META[currentGuide] || GUIDE_META.general;

  if (currentGuide === "units" && Array.isArray(unitOptions) && unitOptions.length) {
    currentChips = unitOptions.map((u) => ({
      label: `${u.label} · $${Number(u.price_night).toLocaleString("es-AR")}`,
      text: u.text || `Me interesa la ${u.label}`,
    }));
  } else {
    currentChips = CHIP_SETS[currentGuide] || CHIP_SETS.general;
  }

  if (els.chipsLabel) els.chipsLabel.textContent = meta.label;
  if (els.input) els.input.placeholder = meta.placeholder;

  const showCal = Boolean(meta.showCalendar) || currentGuide === "dates";
  if (els.datesPanel) {
    els.datesPanel.hidden = !showCal;
    if (showCal) els.datesPanel.open = true;
  }

  renderChips();
}

function renderChips() {
  if (!els.chips) return;
  els.chips.innerHTML = currentChips
    .map(
      (c, i) =>
        `<button type="button" class="demo-chip" data-chip="${i}">${escapeHtml(c.label)}</button>`
    )
    .join("");
  els.chips.querySelectorAll("[data-chip]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const item = currentChips[Number(btn.dataset.chip)];
      if (!item) return;
      if (item.text === "__noop__") return;
      if (item.text === "__restart__") {
        startSession();
        return;
      }
      if (item.text === "__simulate_mp__") {
        simulateMp();
        return;
      }
      if (item.text === "__focus_calendar__") {
        if (els.datesPanel) {
          els.datesPanel.hidden = false;
          els.datesPanel.open = true;
        }
        els.dateIn?.focus();
        return;
      }
      sendMessage(item.text);
    });
  });
}

function formatDateLabel(iso) {
  if (!iso) return "";
  const [y, m, d] = iso.split("-").map(Number);
  const dt = new Date(y, m - 1, d);
  return dt.toLocaleDateString("es-AR", { weekday: "short", day: "numeric", month: "short" });
}

function onBotReply(data, { skipBubble } = {}) {
  if (!skipBubble && data.reply) appendBubble("bot", data.reply);
  applyGuide(resolveGuide(data), data.unit_options);
  renderOwnerFeed(data.owner_events, data.reservation);
  if (typeof data.turns_left === "number") {
    els.turns.textContent = data.capped
      ? "Demo finalizada — reiniciá o contactá a SofIA"
      : `Mensajes restantes en esta demo: ${data.turns_left}`;
  }
  if (data.reservation?.id && data.reservation?.deposit_amount) {
    // hint in turns line when in pay flow
    if (["pay_mp", "pay_xfer", "pay_owner", "pay"].includes(data.guide)) {
      els.turns.textContent =
        `${els.turns.textContent || ""} · ${data.reservation.id} seña ${money(data.reservation.deposit_amount)}`.trim();
    }
  }
}

async function startSession() {
  setLoading(true);
  els.messages.innerHTML = "";
  try {
    const data = await api("/api/demo/session", {});
    sessionId = data.session_id;
    if (data.property) {
      els.propName.textContent = data.property.name || "Demo";
      els.propZone.textContent = data.property.zone || "";
    }
    onBotReply(data);
  } catch (err) {
    if (err.status === 401) {
      showAccessDenied(err.message);
    } else {
      appendBubble("bot", `No pude iniciar la demo: ${err.message}`);
      applyGuide("general");
    }
  } finally {
    setLoading(false);
    if (els.input && !els.form?.hidden) els.input.focus();
  }
}

async function sendMessage(text) {
  const msg = (text || "").trim();
  if (!msg || sending) return;
  if (!sessionId) {
    await startSession();
  }
  appendBubble("user", msg);
  els.input.value = "";
  setLoading(true);
  try {
    const data = await api("/api/demo/chat", { session_id: sessionId, message: msg });
    onBotReply(data);
  } catch (err) {
    const expired =
      String(err.detail || err.message || "").toLowerCase().includes("sesión") ||
      String(err.message || "").toLowerCase().includes("expir");
    if (expired) {
      appendBubble("bot", "Se reinició la demo (el server se recargó). Arrancamos de nuevo…");
      await startSession();
      try {
        setLoading(true);
        appendBubble("user", msg);
        const data = await api("/api/demo/chat", { session_id: sessionId, message: msg });
        onBotReply(data);
      } catch (err2) {
        appendBubble("bot", err2.message || "Error al responder");
      }
    } else {
      appendBubble("bot", err.message || "Error al responder");
    }
  } finally {
    setLoading(false);
    els.input.focus();
  }
}

async function simulateMp() {
  if (!sessionId || sending) return;
  setLoading(true);
  try {
    const data = await api("/api/demo/simulate-mp-payment", { session_id: sessionId });
    onBotReply(data);
  } catch (err) {
    appendBubble("bot", err.message || "No se pudo simular el pago");
  } finally {
    setLoading(false);
  }
}

async function ownerAction(path) {
  if (!sessionId || sending) return;
  setLoading(true);
  try {
    const data = await api(path, { session_id: sessionId });
    onBotReply(data);
  } catch (err) {
    appendBubble("bot", err.message || "Error en CRM dueño");
  } finally {
    setLoading(false);
  }
}

els.form.addEventListener("submit", (e) => {
  e.preventDefault();
  sendMessage(els.input.value);
});

els.input.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    sendMessage(els.input.value);
  }
});

els.sendDates.addEventListener("click", () => {
  const din = els.dateIn.value;
  const dout = els.dateOut.value;
  const guests = els.guests.value || "4";
  if (!din || !dout) {
    appendBubble("bot", "Elegí fecha de entrada y salida en el calendario.");
    applyGuide("dates");
    return;
  }
  if (dout <= din) {
    appendBubble("bot", "La salida tiene que ser después de la entrada.");
    applyGuide("dates");
    return;
  }
  const text =
    `Hola, quiero consultar disponibilidad del ${formatDateLabel(din)} (${din}) ` +
    `al ${formatDateLabel(dout)} (${dout}) para ${guests} personas. ¿Hay lugar y cuánto sale?`;
  sendMessage(text);
});

els.dateIn.addEventListener("change", () => {
  if (els.dateOut.value && els.dateOut.value <= els.dateIn.value) {
    const d = new Date(els.dateIn.value + "T12:00:00");
    d.setDate(d.getDate() + 2);
    els.dateOut.value = isoLocal(d);
  }
  els.dateOut.min = els.dateIn.value;
});

els.restart.addEventListener("click", () => startSession());
els.approveXfer?.addEventListener("click", () => ownerAction("/api/demo/approve-transfer"));
els.rejectXfer?.addEventListener("click", () => ownerAction("/api/demo/reject-transfer"));

initDateDefaults();
applyGuide("dates");
startSession();
