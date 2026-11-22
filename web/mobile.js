"use strict";

const app = document.querySelector("#inspection-app");
const sessionKey = "ceramika-inspector";
const state = {token: sessionStorage.getItem(sessionKey), user: null, run: null, point: null, draft: null, page: "routes", demo: false};
const esc = value => String(value ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const when = value => value ? new Date(value.replace(" ", "T") + "Z").toLocaleString("ru-RU", {day:"2-digit",month:"2-digit",hour:"2-digit",minute:"2-digit"}) : "—";
const number = value => Number(value).toLocaleString("ru-RU");
const pill = (label, tone="") => `<span class="pill ${tone}"><i class="dot"></i>${esc(label)}</span>`;
const action = (label, command, style="", attrs="") => `<button type="button" class="btn ${style}" data-action="${command}" ${attrs}>${label}</button>`;
const heading = (title, subtitle="") => `<header class="intro"><h1>${esc(title)}</h1>${subtitle ? `<p>${esc(subtitle)}</p>` : ""}</header>`;
const pointState = point => point.checked ? (point.severity ? pill(point.severity === "critical" ? "Критическое" : "Есть замечание", point.severity === "critical" ? "bad" : "warn") : pill("Осмотрено","good")) : pill("Ожидает");
const point = () => state.run.points.find(p => p.id === state.point);
let toastTimer;

async function api(path, data) {
  const headers = {};
  if (state.token) headers.Authorization = "Bearer " + state.token;
  if (data) headers["Content-Type"] = "application/json";
  let response;
  try {
    response = await fetch("/api/" + path, {method: data ? "POST" : "GET", headers, body: data ? JSON.stringify(data) : undefined});
  } catch {
    throw new Error("Нет соединения. Проверьте Wi‑Fi и окно Mobile.bat на компьютере.");
  }
  const result = await response.json();
  if (!response.ok) {
    if (response.status === 401 && path !== "login") clearSession();
    throw new Error(result.error || "Запрос не выполнен.");
  }
  return result.data;
}

function toast(message) {
  const element = document.querySelector("#inspection-toast");
  element.textContent = message;
  element.classList.add("visible");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => element.classList.remove("visible"), 3800);
}

function clearSession() {
  Object.assign(state, {token:null,user:null,run:null,point:null,draft:null});
  sessionStorage.removeItem(sessionKey);
  renderLogin();
}

function shell(page, content) {
  state.page = page;
  const nav = state.user && state.run ? `<nav class="inspection-nav" aria-label="Разделы обхода">${[
    ["routes","Маршруты"], ["points","Точки"], ["report","Отчёт"],
  ].map(([key,name])=>`<button type="button" class="${page === key || (key === "points" && ["point","readings","remark"].includes(page)) ? "selected" : ""}" data-action="${key}">${name}</button>`).join("")}</nav>` : "";
  app.innerHTML = `<header class="inspection-header"><div><div class="brand">
    <div class="logo" aria-hidden="true">C.</div><div><b>CERAMIKA</b><small>Обход линии</small></div></div>
    ${state.user ? action("Выйти","logout","signout") : ""}</div></header>
    <main class="inspection">${nav}${content}</main>`;
  scrollTo(0,0);
}

function renderLogin() {
  shell("login", `${heading("Вход в обходы", "Ежедневный осмотр оборудования линии.")}
    <form class="panel stack" data-form="login">
      <label>Логин<input name="login" required autocomplete="username" autocapitalize="none"></label>
      <label>Пароль<input name="password" required type="password" autocomplete="current-password"></label>
      <p role="alert" class="error" hidden></p>
      <button class="btn primary">Войти</button>
      ${state.demo ? '<p class="demo-entry"><button type="button" class="link" data-action="demo">Заполнить демо-доступ оператора</button></p>' : ""}
    </form>`);
}

async function showRoutes() {
  const routes = await api("inspections/routes");
  shell("routes", `${heading("Маршруты обхода", `${state.user.name} · ${state.user.shift || state.user.role_name}`)}
    ${routes.length ? routes.map(route => `<section class="panel route-card">
      <div class="row between"><h2>${esc(route.line)}</h2>${route.open_id ? pill("В работе","warn") : route.last_id ? pill("Есть отчёт","good") : pill("Назначен")}</div>
      <p class="muted">${esc(route.name)} · точек ${route.total}</p>
      ${route.last_finished ? `<small>Прошлый обход ${when(route.last_finished)}</small>` : ""}
      <div class="actions ${route.last_id ? "" : "single"}">
        ${action(route.open_id ? "Продолжить" : "Начать обход","start","primary",`data-id="${route.id}"`)}
        ${route.last_id ? action("Прошлый отчёт","load-report","",`data-id="${route.last_id}"`) : ""}
      </div></section>`).join("") : '<div class="panel">Маршруты пока не назначены.</div>'}`);
}

function progress() {
  const done = state.run.points.filter(p=>p.checked).length;
  const total = state.run.points.length;
  return `<div class="panel stack"><div class="row between"><b>Осмотрено ${done} из ${total}</b>
    ${state.run.status === "done" ? pill("Завершён","good") : pill("В работе","warn")}</div>
    <progress class="progress" value="${done}" max="${total || 1}" aria-label="Прогресс обхода"></progress></div>`;
}

function showPoints() {
  const run = state.run;
  shell("points", `${heading("Контрольные точки",run.line)}${progress()}<section class="stack" aria-label="Оборудование">
    ${run.points.map(p=>`<button type="button" class="btn point-button" data-action="point" data-id="${p.id}">
      <span class="row between"><span class="point-name">${p.position}. ${esc(p.equipment)}</span>${pointState(p)}</span>
      <small>${esc(p.location)}</small></button>`).join("")}</section>${action("Открыть итоговый отчёт","report","wide")}`);
}

function showPoint() {
  const p = point();
  shell("point", `${heading(p.equipment,p.location)}<section class="panel stack">
    <div class="row between"><h2>Точка ${p.position} из ${state.run.points.length}</h2>${pointState(p)}</div>
    <p class="instruction">${esc(p.instruction)}</p>
    ${p.checked ? `<div>${valuesList(p)}${p.note ? `<p class="note-text">${esc(p.note)}</p>` : ""}</div>` : ""}
    ${state.run.status === "open" ? action(p.checked ? "Изменить показания" : "Ввести показания","readings","primary wide") : ""}
    ${action("К контрольным точкам","points","wide")}</section>`);
}

function valuesList(p) {
  return `<ul class="value-list">${p.parameters.filter(v=>v.value != null).map(v=>`<li>${esc(v.name)} · ${number(v.value)} ${esc(v.unit)}</li>`).join("")}</ul>`;
}

function initDraft() {
  const p = point();
  state.draft = {values:Object.fromEntries(p.parameters.map(v=>[v.id,v.value ?? ""])),note:p.note || "", severity:p.severity || "warning"};
}

function showReadings() {
  const p = point();
  shell("readings", `${heading("Показания",p.equipment)}<form class="panel stack" data-form="readings">
    <div>${p.parameters.map(v=>`<label class="reading">${esc(v.name)}, ${esc(v.unit)}
      <small>Допуск ${number(v.minimum)}–${number(v.maximum)}</small>
      <input name="p-${v.id}" inputmode="decimal" required value="${esc(state.draft.values[v.id])}" data-min="${v.minimum}" data-max="${v.maximum}"></label>`).join("")}</div>
    <p role="alert" class="error" hidden></p>
    <div class="actions"><button class="btn" name="intent" value="remark">Замечание</button>
    <button class="btn primary" name="intent" value="save">Сохранить</button></div>
    ${action("Назад к точке","point","wide",`data-id="${p.id}"`)}</form>`);
  app.querySelector("form").addEventListener("input", event=>{
    const input = event.target;
    if (!input.dataset.min) return;
    const value = Number(input.value.replace(",","."));
    input.classList.toggle("over", Boolean(input.value) && (!Number.isFinite(value) || value < Number(input.dataset.min) || value > Number(input.dataset.max)));
  });
}

function showRemark(required=false) {
  const draft = state.draft;
  shell("remark", `${heading("Замечание",point().equipment)}<form class="panel stack" data-form="remark">
     ${required ? '<p class="instruction">Показание вне допуска. Укажите причину или наблюдение.</p>' : ""}
     <label>Уровень<select name="severity"><option value="warning">Предупреждение</option>
     <option value="critical" ${draft.severity === "critical" ? "selected" : ""}>Критическое</option></select></label>
     <label>Описание<textarea name="note" maxlength="1000" required>${esc(draft.note)}</textarea></label>
     <p role="alert" class="error" hidden></p>
     <button class="btn primary">Сохранить точку</button>${action("К показаниям","back-readings","wide")}</form>`);
}

async function savePoint(note="", severity=null) {
  state.run = await api(`inspections/${state.run.id}/points/${state.point}`,{values:state.draft.values,note,severity});
  state.draft = null;
  showPoints();
  toast("Точка осмотрена.");
}

function showReport() {
  const run = state.run;
  const remarks = run.points.filter(p=>p.note);
  const allDone = run.points.length && run.points.every(p=>p.checked);
  shell("report", `${heading("Итоговый отчёт",`${run.line} · ${run.inspector}`)}${progress()}
    <section class="panel stack"><div class="row between"><h2>Результаты осмотра</h2><small>${when(run.finished || run.started)}</small></div>
    <p>${remarks.length ? `Замечаний: ${remarks.length}` : "Замечаний нет."}</p>
    ${run.points.map(p=>`<article class="reading"><div class="row between"><b>${esc(p.equipment)}</b>${pointState(p)}</div>
      ${p.checked ? valuesList(p) : ""}${p.note ? `<p class="note-text">${esc(p.note)}</p>` : ""}</article>`).join("")}
    ${run.status === "open" ? action("Завершить обход","finish","primary wide",allDone ? "" : 'disabled title="Сначала осмотрите все точки"') : ""}
    ${action(run.status === "done" ? "К маршрутам" : "К контрольным точкам",run.status === "done" ? "routes" : "points","wide")}</section>`);
}

const commands = {
  demo() {
    const form = app.querySelector("form");
    form.elements.login.value = "operator";
    form.elements.password.value = "Ceramika2026";
    form.querySelector("button:not([type=button])").focus();
  },
  async logout() {
    try { await api("logout", {}); } catch {}
    clearSession();
  },
  routes: showRoutes,
  async start(id) {
    state.run = await api("inspections/start", {route_id:id});
    showPoints();
  },
  async "load-report"(id) {
    state.run = await api("inspections/" + id);
    showReport();
  },
  points: showPoints,
  report: showReport,
  point(id) {
    state.point = id;
    showPoint();
  },
  readings() {
    initDraft();
    showReadings();
  },
  "back-readings": showReadings,
  async finish() {
    state.run = await api(`inspections/${state.run.id}/finish`,{});
    showReport();
    toast("Обход завершён.");
  },
};

app.addEventListener("click", async event=>{
  const button = event.target.closest("[data-action]");
  if (!button) return;
  const command = commands[button.dataset.action];
  if (!command) return;
  button.disabled = true;
  try { await command(Number(button.dataset.id)); }
  catch (error) { toast(error.message); }
  finally { button.disabled = false; }
});

app.addEventListener("submit", async event=>{
  event.preventDefault();
  const form = event.target;
  const button = event.submitter;
  if (!button) return;
  button.disabled = true;
  const fields = Object.fromEntries(new FormData(form));
  try {
    if (form.dataset.form === "login") {
      const auth = await api("login", fields);
      if (!["operator","manager"].includes(auth.user.role)) {
        state.token = auth.token;
        try { await api("logout",{}); } finally { state.token = null; }
        throw new Error("Вход доступен оператору и мастеру смены.");
      }
      state.token = auth.token;
      state.user = auth.user;
      sessionStorage.setItem(sessionKey,auth.token);
      await showRoutes();
    } else if (form.dataset.form === "readings") {
      const params = point().parameters;
      state.draft.values = Object.fromEntries(params.map(p=>[p.id,fields[`p-${p.id}`].trim()]));
      let outside = false;
      for (const p of params) {
        const raw = state.draft.values[p.id];
        const value = Number(raw.replace(",","."));
        if (!raw || !Number.isFinite(value)) throw new Error(`Введите число для поля «${p.name}».`);
        if (value < p.minimum || value > p.maximum) outside = true;
      }
      if (button.value === "remark" || (outside && !state.draft.note)) showRemark(outside);
      else await savePoint(state.draft.note,state.draft.note ? state.draft.severity : null);
    } else {
      state.draft.note = fields.note.trim();
      state.draft.severity = fields.severity;
      if (!state.draft.note) throw new Error("Заполните описание замечания.");
      await savePoint(state.draft.note,state.draft.severity);
    }
  } catch(error) {
    const line = form.querySelector(".error");
    line.textContent = error.message;
    line.hidden = false;
  } finally { button.disabled = false; }
});

(async () => {
  try {
    state.demo = (await api("health")).mode === "demo";
    if (state.token) {
      state.user = await api("me");
      await showRoutes();
      return;
    }
  } catch(error) { toast(error.message); }
  clearSession();
})();
