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
  dateIn: document.getElementById("date-in"),
  dateOut: document.getElementById("date-out"),
  guests: document.getElementById("guests"),
  sendDates: document.getElementById("send-dates-btn"),
};

let sessionId = null;
let sending = false;

const CHIPS = [
  { label: "Este finde", text: "Hola, ¿hay lugar este viernes a domingo para 4 personas?" },
  { label: "Próxima semana", text: "Hola, busco alojamiento de lunes a viernes de la próxima semana, somos 2." },
  { label: "2 personas", text: "Somos 2 personas. ¿Qué opciones tenés?" },
  { label: "4 personas", text: "Somos 4 personas. ¿Hay cabaña disponible?" },
  { label: "¿Precio?", text: "¿Cuánto sale por noche?" },
  { label: "Quiero reservar", text: "Me interesa, quiero reservar. ¿Cómo seguimos con la seña?" },
  { label: "Me llamo Ana", text: "Me llamo Ana" },
  { label: "Me llamo Martín", text: "Me llamo Martín" },
  { label: "Me llamo Lucía", text: "Me llamo Lucía" },
  { label: "Check-in", text: "¿A qué hora es el check-in y el check-out?" },
];

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
}

function appendBubble(role, text) {
  const div = document.createElement("div");
  div.className = `demo-bubble demo-bubble-${role}`;
  div.innerHTML = `<div class="demo-bubble-label">${role === "user" ? "Vos" : "Bot"}</div><div class="demo-bubble-text">${escapeHtml(text).replace(/\n/g, "<br>")}</div>`;
  els.messages.appendChild(div);
  els.messages.scrollTop = els.messages.scrollHeight;
}

async function api(path, body) {
  const res = await fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
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
  // próximo viernes
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

function renderChips() {
  if (!els.chips) return;
  els.chips.innerHTML = CHIPS.map(
    (c, i) =>
      `<button type="button" class="demo-chip" data-chip="${i}">${escapeHtml(c.label)}</button>`
  ).join("");
  els.chips.querySelectorAll("[data-chip]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const item = CHIPS[Number(btn.dataset.chip)];
      if (item) sendMessage(item.text);
    });
  });
}

function formatDateLabel(iso) {
  if (!iso) return "";
  const [y, m, d] = iso.split("-").map(Number);
  const dt = new Date(y, m - 1, d);
  return dt.toLocaleDateString("es-AR", { weekday: "short", day: "numeric", month: "short" });
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
    appendBubble("bot", data.reply);
    els.turns.textContent =
      typeof data.turns_left === "number" ? `Mensajes restantes en esta demo: ${data.turns_left}` : "";
  } catch (err) {
    appendBubble("bot", `No pude iniciar la demo: ${err.message}`);
  } finally {
    setLoading(false);
    els.input.focus();
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
    appendBubble("bot", data.reply);
    if (typeof data.turns_left === "number") {
      els.turns.textContent = data.capped
        ? "Demo finalizada — reiniciá o contactá a SofIA"
        : `Mensajes restantes en esta demo: ${data.turns_left}`;
    }
  } catch (err) {
    const expired =
      String(err.detail || err.message || "").toLowerCase().includes("sesión") ||
      String(err.message || "").toLowerCase().includes("expir");
    if (expired) {
      appendBubble("bot", "Se reinició la demo (el server se recargó). Arrancamos de nuevo…");
      await startSession();
      // reintentar una vez
      try {
        setLoading(true);
        appendBubble("user", msg);
        const data = await api("/api/demo/chat", { session_id: sessionId, message: msg });
        appendBubble("bot", data.reply);
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
    return;
  }
  if (dout <= din) {
    appendBubble("bot", "La salida tiene que ser después de la entrada.");
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

initDateDefaults();
renderChips();
startSession();
