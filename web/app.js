"use strict";

const app = document.querySelector("#app");
const modal = document.querySelector("#modal");
const sections = {
  batches: ["Активные партии", "M3 7h18v13H3zM6 7V4h12v3M3 12h18M10 12v3h4v-3"],
  program: ["Программа партии", "M7 3h10v3H7zM7 5H4v16h16V5h-3M8 11h8m-8 4h8"],
  live: ["Печь LIVE", "M2 12h4l3-6 4 13 3-7h6"],
  journal: ["Журнал партии", "M4 3h16v18H4zM8 8h8m-8 4h8m-8 4h5"],
  issue: ["Сообщить о проблеме", "M12 3 2 20h20L12 3zm0 6v4m0 3v1"],
};
const labels = {
  planned: "Запланирована", in_progress: "В работе", quality: "Контроль качества",
  completed: "Выпущена", blocked: "Заблокирована", pending: "Ожидает", ready: "Готов к запуску",
  running: "Выполняется", done: "Выполнен", skipped: "Пропущен", ready_equipment: "Исправно",
  warning: "Предупреждение", critical: "Критический", open: "Открыт", resolved: "Устранён",
  released: "Допущено", maintenance: "Обслуживание",
};
const state = {
  user: null, token: sessionStorage.getItem("ceramika-token"), page: "batches",
  batchId: null, batch: null, stepId: null, list: [], alerts: [], connected: true, demo: false,
};
const esc = value => String(value ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const icon = path => `<svg viewBox="0 0 24 24" aria-hidden="true"><path d="${path}"/></svg>`;
const brand = '<div class="brand"><div class="logo" aria-hidden="true">C.</div><div><b>CERAMIKA</b><small>Оператор линии</small></div></div>';
const status = key => labels[key] || key || "—";
const time = value => value ? new Date(value.replace(" ", "T") + "Z").toLocaleString("ru-RU", {
  day:"2-digit",month:"2-digit",hour:"2-digit",minute:"2-digit"
}) : "—";
const count = value => Number(value).toLocaleString("ru-RU");
const tone = key => ["in_progress","running","done","completed","released","ready_equipment","resolved"].includes(key) ? "good" :
  ["quality","ready","warning"].includes(key) ? "warn" : ["blocked","critical"].includes(key) ? "bad" : "";
const pill = (key, name=status(key)) => `<span class="pill ${tone(key)}"><i class="dot"></i>${esc(name)}</span>`;
const empty = msg => `<p class="empty">${esc(msg)}</p>`;
const option = (value, label, selected=false) => `<option value="${esc(value)}" ${selected ? "selected" : ""}>${esc(label)}</option>`;
const intro = (title, description="") => `<header class="intro"><h1>${esc(title)}</h1>${description ? `<p>${esc(description)}</p>` : ""}</header>`;
const selection = () => `<label>Производственная партия<select id="batch-select">${option("", "Выберите партию", !state.batchId)}${state.list.map(b => option(b.id,`${b.code} · ${b.product}`,b.id === state.batchId)).join("")}</select></label>`;
let toastTimer;

async function api(path, data) {
  let res;
  try {
    const headers = {};
    if (state.token) headers.Authorization = "Bearer " + state.token;
    if (data) headers["Content-Type"] = "application/json";
    res = await fetch("/api/" + path, { method: data ? "POST" : "GET", headers, body: data ? JSON.stringify(data) : undefined });
    connection(true);
  } catch {
    connection(false);
    throw new Error("Нет соединения с локальным сервером.");
  }
  const body = await res.json();
  if (!res.ok) {
    if (res.status === 401 && path !== "login") logout();
    throw new Error(body.error || "Запрос завершился с ошибкой.");
  }
  return body.data;
}

function connection(online) {
  state.connected = online;
  const place = document.querySelector("#connection");
  if (place) place.innerHTML = pill(online ? "done" : "critical", online ? "На связи" : "Нет связи");
}

function notify(message) {
  const node = document.querySelector("#toast");
  node.textContent = message;
  node.classList.add("visible");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => node.classList.remove("visible"), 4400);
}

function logout() {
  state.user = null;
  state.token = null;
  state.batchId = null;
  state.page = "batches";
  sessionStorage.removeItem("ceramika-token");
  if (modal.open) modal.close();
  login();
}

function login() {
  const diagram = `<svg class="kiln" viewBox="0 0 560 280" aria-label="Схема трёх зон обжига">
    <defs><linearGradient id="heat"><stop stop-color="#4b5d59"/><stop offset=".52" stop-color="#754629"/><stop offset="1" stop-color="#aa6733"/></linearGradient></defs>
    <rect x="25" y="52" width="510" height="156" rx="18" fill="url(#heat)" stroke="#789192" stroke-width="2"/>
    <path d="M195 54v152m171-152v152M52 162h456" stroke="#e3ab70" stroke-opacity=".7"/>
    <g fill="none" stroke="#fac369" stroke-width="3" opacity=".85"><path d="M75 131c14 0 24-22 44-22s27 19 44 19M224 132c16 0 24-42 54-42s33 24 56 24M394 124c17 0 25-42 54-42s35 38 56 38"/></g>
    <g fill="#e6efee" font-size="14" font-family="Segoe UI, sans-serif" text-anchor="middle"><text x="110" y="188">Нагрев</text><text x="280" y="188">Обжиг</text><text x="450" y="188">Выдержка</text></g>
    <path d="M49 235h462" stroke="#65848a" stroke-width="3" stroke-dasharray="4 6"/>
    <g fill="#fac369"><rect x="80" y="227" width="46" height="8" rx="3"/><rect x="228" y="227" width="46" height="8" rx="3"/><rect x="379" y="227" width="46" height="8" rx="3"/></g>
  </svg>`;
  app.innerHTML = `<main class="login"><section class="stack">${brand}${intro("Вход в цех", "Рабочее место оператора производства керамической плитки.")}
    <form id="login-form" class="stack"><label>Логин<input name="login" autocomplete="username" required></label>
    <label>Пароль<input name="password" type="password" autocomplete="current-password" required></label>
    <p class="error" id="login-error" role="alert" hidden></p><button class="btn primary">Войти</button>
    ${state.demo ? '<p class="muted demo">Демо-доступ · <button type="button" class="link" id="demo-login">Заполнить данные оператора</button></p>' : ""}
    </form></section><aside class="login-art"><figure>${diagram}<figcaption>Зоны печи обжига</figcaption></figure></aside></main>`;
  const form = document.querySelector("#login-form");
  document.querySelector("#demo-login")?.addEventListener("click", () => {
    form.elements.login.value = "operator";
    form.elements.password.value = "Ceramika2026";
    form.querySelector("[type=submit], button").focus();
  });
  form.addEventListener("submit", async event => {
    event.preventDefault();
    const error = document.querySelector("#login-error");
    const button = form.querySelector("button");
    button.disabled = true;
    try {
      const data = await api("login", {...Object.fromEntries(new FormData(form)), role:"operator"});
      state.user = data.user;
      state.token = data.token;
      sessionStorage.setItem("ceramika-token", data.token);
      await show("batches");
    } catch (err) {
      error.hidden = false;
      error.textContent = err.message;
    } finally {
      button.disabled = false;
    }
  });
}

function shell() {
  const user = state.user;
  const initials = user.name.split(" ").map(x => x[0]).slice(0,2).join("");
  app.innerHTML = `<div class="shell"><aside class="side">${brand}
    <nav class="nav" aria-label="Разделы цеха">${Object.entries(sections).map(([key,[name,path]]) =>
      `<button type="button" data-page="${key}" class="${key === state.page ? "chosen" : ""}" ${key === state.page ? 'aria-current="page"' : ""}>${icon(path)}${name}</button>`).join("")}</nav>
    <div class="sidefoot">Производственный контур</div></aside>
    <div class="body"><header class="top"><span class="crumb">Цех / ${sections[state.page][0]}</span>
      <div class="row"><span id="connection"></span>
        <button class="icon" id="notifications" aria-label="Уведомления">${icon("M4 17h16l-2-3V9a6 6 0 0 0-12 0v5l-2 3zm5 3h6")}<span id="alert-count"></span></button>
        <div class="avatar" aria-hidden="true">${esc(initials)}</div><div class="account"><b>${esc(user.name)}</b><small>${esc(user.shift || user.department)}</small></div>
        <button id="logout" class="text-button signout">Выйти</button>
      </div></header><main class="main" id="content"></main></div></div>`;
  connection(state.connected);
  renderAlertCount();
}

function renderAlertCount() {
  const amount = state.alerts.filter(a => !a.read_at).length;
  const node = document.querySelector("#alert-count");
  if (node) {
    node.className = amount ? "counter" : "";
    node.textContent = amount || "";
  }
}

async function alerts() {
  if (!state.user) return;
  state.alerts = await api("notifications");
  renderAlertCount();
}

function showAlerts() {
  modal.innerHTML = `<div class="row between"><h2>Уведомления</h2><button class="btn" data-close>Закрыть</button></div>
    ${state.alerts.length ? state.alerts.map(a => `<article class="event"><div class="row between"><b>${esc(a.action)}</b><small>${time(a.created)}</small></div>
    ${a.detail ? `<p>${esc(a.detail)}</p>` : ""}<div class="row">
      ${a.batch_id ? `<button class="link" data-alert-batch="${a.batch_id}">Открыть партию</button>` : ""}
      ${!a.read_at ? `<button class="text-button" data-read="${a.id}">Отметить прочитанным</button>` : ""}</div></article>`).join("")
      : empty("Уведомлений пока нет.")}`;
  if (!modal.open) modal.showModal();
}

function metric(title, value, kind="") {
  return `<div class="metric ${kind}"><small>${esc(title)}</small><strong>${esc(value)}</strong></div>`;
}

function batches(main) {
  const list = state.list;
  const lines = [...new Set(list.map(b => b.line))];
  const products = [...new Set(list.map(b => b.product))];
  main.innerHTML = `${intro("Активные партии", "Выполнение производственных заданий по линиям.")}
    <section class="metrics" aria-label="Сводка партий">
      ${metric("В работе",list.filter(b => b.status === "in_progress").length)}
      ${metric("Контроль качества",list.filter(b => b.status === "quality").length)}
      ${metric("С предупреждениями",list.filter(b => b.warning > 0).length,"warn")}
      ${metric("Критические",list.filter(b => b.critical > 0).length,"bad")}
    </section>
    <section class="panel"><div class="panel-title stack"><div class="row between"><h2>Партии цеха</h2><button id="refresh" class="btn">Обновить</button></div>
      <div class="filters"><label>Поиск<input id="search" type="search" placeholder="Номер или продукт"></label>
      <label>Линия<select id="by-line">${option("","Все линии")}${lines.map(x => option(x,x)).join("")}</select></label>
      <label>Статус<select id="by-status">${option("","Все статусы")}${[...new Set(list.map(b => b.status))].map(x => option(x,status(x))).join("")}</select></label>
      <label>Продукт<select id="by-product">${option("","Все продукты")}${products.map(x => option(x,x)).join("")}</select></label></div></div>
      <div class="scroll" id="batch-table"></div><footer class="footer" id="table-foot"></footer></section>`;
  const render = () => {
    const value = id => document.querySelector("#" + id).value;
    const term = value("search").trim().toLocaleLowerCase("ru");
    const filtered = list.filter(b => (!value("by-line") || b.line === value("by-line")) &&
      (!value("by-status") || b.status === value("by-status")) && (!value("by-product") || b.product === value("by-product")) &&
      (`${b.code} ${b.product} ${b.product_code}`).toLocaleLowerCase("ru").includes(term));
    document.querySelector("#batch-table").innerHTML = filtered.length ? `<table><thead><tr><th>Партия</th><th>Продукт</th><th>Линия</th><th>Текущий шаг</th>
      <th>Статус партии</th><th>Отклонения</th></tr></thead><tbody>${filtered.map(b => `<tr><td><button class="link" data-batch="${b.id}">${esc(b.code)}</button></td>
      <td>${esc(b.product)}</td><td>${esc(b.line)}</td><td>${esc(b.current_step || "—")}${b.step_status ? `<br><small>${esc(status(b.step_status))}</small>` : ""}</td>
      <td>${pill(b.status)}</td><td>${b.critical ? pill("critical",`Критические · ${b.critical}`) : b.warning ? pill("warning",`Предупреждения · ${b.warning}`) : '<span class="muted">—</span>'}</td></tr>`).join("")}</tbody></table>` : empty("По выбранным условиям партий нет.");
    document.querySelector("#table-foot").textContent = `Показано ${filtered.length} из ${list.length}`;
  };
  main.querySelector(".filters").addEventListener("input", render);
  render();
}

function stepForm(step, batch) {
  const current = state.list.find(b => b.id === batch.id);
  const busy = step.status === "running";
  const ready = step.status === "ready";
  return `<section class="panel pad stack"><div class="bheading"><div class="stack" style="gap:5px"><small>${esc(step.kind)} · шаг ${step.position}</small><h2>${esc(step.name)}</h2></div>${pill(step.status)}</div>
    <p class="instruction">${esc(step.instructions || "Следуйте технологической карте.")}</p>
    ${step.equipment ? `<div class="row"><b>${esc(step.equipment)}</b>${pill(step.equipment_status === "ready" ? "ready_equipment" : step.equipment_status)}</div>` : ""}
    ${step.kind === "Смешивание" && batch.raw.length ? `<details><summary>Партии сырья</summary><ul>${batch.raw.map(r => `<li>${esc(r.material)} · ${esc(r.code)} · ${count(r.quantity)} ${esc(r.unit)}</li>`).join("")}</ul></details>` : ""}
    ${step.kind === "Обжиг" ? '<div class="compact graph" id="telemetry"></div>' : ""}
    <form class="stack" id="step-form" data-step="${step.id}">${step.parameters.length ? `<div class="fieldgrid">${step.parameters.map(p => `<label>
      ${esc(p.name)}${p.required ? " *" : ""}<small class="fieldnote">План ${count(p.target)} · допуск ${count(p.minimum)} – ${count(p.maximum)} ${esc(p.unit)}</small>
      <input name="p-${p.id}" inputmode="decimal" value="${esc(p.value)}" data-min="${p.minimum}" data-max="${p.maximum}" ${busy ? "" : "disabled"} placeholder="Фактическое значение"></label>`).join("")}</div>` : ""}
      ${busy || step.comment ? `<label>Комментарий к шагу<textarea name="comment" ${busy ? "" : "disabled"}>${esc(step.comment)}</textarea></label>` : ""}
      <p class="error" id="step-error" role="alert" hidden></p>
      <div class="row">${ready ? '<button class="btn primary" name="action" value="start">Начать шаг</button>' : ""}
      ${ready && !step.required ? '<button class="btn" name="action" value="skip">Пропустить</button>' : ""}
      ${busy ? '<button class="btn" name="action" value="save">Сохранить факт</button><button class="btn primary" name="action" value="finish">Завершить шаг</button>' : ""}
      ${(busy || ready || current) ? '<button class="btn danger" data-page="issue" type="button">Сообщить о проблеме</button>' : ""}</div></form></section>`;
}

function program(main) {
  const batch = state.batch;
  if (!batch) {
    main.innerHTML = `${intro("Программа партии")}<div class="panel pad">${selection()}${empty("Выберите партию для просмотра маршрута.")}</div>`;
    return;
  }
  const step = batch.steps.find(s => s.id === state.stepId) || batch.steps.find(s => ["ready","running"].includes(s.status)) || batch.steps[0];
  state.stepId = step?.id;
  main.innerHTML = `<div class="row between">${intro(batch.code,batch.product + " · " + batch.line)}${selection()}</div>
    <div class="panel pad row between"><div class="row">${pill(batch.status)}
    <span class="muted">Начало ${time(batch.started)}</span><span class="muted">Шаги ${batch.done} / ${batch.total}</span>${batch.warning ? pill("warning",`Предупреждения · ${batch.warning}`) : ""}${batch.critical ? pill("critical",`Критические · ${batch.critical}`) : ""}</div>
    <button class="btn" data-page="journal">Журнал партии</button></div>
    <div class="route"><div class="panel"><div class="panel-title"><h2>Маршрут</h2></div><div class="step-list">
    ${batch.steps.map(s => `<button class="step ${s.id === step?.id ? "chosen" : ""}" data-select-step="${s.id}"><b>${String(s.position).padStart(2,"0")}</b>
      <span><b>${esc(s.name)}</b><small>${esc(s.kind)} · ${esc(status(s.status))}${batch.deviations.some(d => d.execution_id === s.id) || batch.incidents.some(i => i.execution_id === s.id) ? " · Есть отклонение" : ""}</small></span></button>`).join("")}</div></div>
      ${step ? stepForm(step,batch) : empty("В программе отсутствуют шаги.")}</div>`;
  const form = main.querySelector("#step-form");
  form?.addEventListener("input", event => {
    const field = event.target;
    if (!field.name?.startsWith("p-")) return;
    const value = Number(field.value.replace(",","."));
    field.classList.toggle("over", Boolean(field.value) && (!Number.isFinite(value) || value < Number(field.dataset.min) || value > Number(field.dataset.max)));
  });
  form?.addEventListener("submit", async event => {
    event.preventDefault();
    const action = event.submitter?.value;
    if (!action) return;
    event.submitter.disabled = true;
    const fields = new FormData(form);
    const values = Object.fromEntries([...fields].filter(([key])=>key.startsWith("p-")).map(([key, val])=>[key.slice(2),val]));
    try {
      state.batch = await api(`batches/${batch.id}/steps/${step.id}/${action}`, {values, comment:fields.get("comment") || ""});
      if (["finish","skip"].includes(action)) state.stepId = null;
      program(main);
      refreshTelemetry().catch(()=>{});
      alerts().catch(()=>{});
      notify(action === "save" ? "Фактические параметры сохранены." : action === "finish" ? "Шаг завершён." : action === "skip" ? "Шаг пропущен." : "Шаг начат.");
    } catch (err) {
      const error = form.querySelector("#step-error");
      error.hidden = false;
      error.textContent = err.message;
      event.submitter.disabled = false;
    }
  });
}

function charts(oven) {
  const samples = oven.samples.slice().reverse();
  const groups = Map.groupBy ? Map.groupBy(samples, s => s.zone) :
    new Map([...new Set(samples.map(s => s.zone))].map(zone => [zone,samples.filter(s => s.zone === zone)]));
  if (!samples.length) return empty("Пока нет показаний для выбранного оборудования.");
  const low = Math.floor((Math.min(...samples.map(s => s.temperature)) - 3) / 10) * 10;
  const high = Math.ceil((Math.max(...samples.map(s => s.temperature)) + 3) / 10) * 10;
  const palette = ["#176552","#ac6d1b","#4661a1"];
  const series = [...groups].map(([zone, records], index) => {
    const points = records.map((s, i) => `${52+i*680/Math.max(1,records.length-1)},${134-(s.temperature-low)*118/(high-low)}`).join(" ");
    return {zone, last:records.at(-1).temperature, points, color:palette[index % palette.length]};
  });
  return `<div class="row between"><h3>${esc(oven.equipment.name)}</h3><small>${oven.source === "simulation" ? "Имитация телеметрии" : "Телеметрия оборудования"} · ${time(samples.at(-1).recorded)}</small></div>
    <div class="zones">${series.map(s=>metric(s.zone,`${count(s.last)} °C`)).join("")}</div>
    <svg class="chart" viewBox="0 0 750 159" preserveAspectRatio="none" role="img" aria-label="График температуры по зонам печи">
    ${[0,1,2].map(i=>`<path d="M52 ${16+i*59}H732" stroke="#e2e9eb"/><text x="2" y="${21+i*59}" font-size="13" fill="#50656e">${high-i*(high-low)/2}°</text>`).join("")}
    ${series.map(s=>`<polyline fill="none" stroke="${s.color}" stroke-width="2.5" vector-effect="non-scaling-stroke" points="${s.points}"/>`).join("")}</svg>`;
}

async function refreshTelemetry() {
  const node = document.querySelector("#telemetry");
  if (!node) return;
  const results = await api("telemetry" + (state.batchId ? "?batch=" + state.batchId : ""));
  if (!node.isConnected) return;
  node.innerHTML = results.length ? results.map(oven => `<div class="graph">${charts(oven)}</div>`).join("") : empty("Печь для выбранной линии отсутствует.");
}

function live(main) {
  main.innerHTML = `<div class="row between">${intro("Печь LIVE","Текущие температуры по зонам обжига.")}${selection()}</div>
    <section class="panel pad stack"><div class="row between"><h2>Температура по зонам</h2><small>Обновление каждые 5 секунд</small></div>
    <div class="graph" id="telemetry">${empty("Получаем показания…")}</div></section>`;
}

function journal(main) {
  const batch = state.batch;
  main.innerHTML = `<div class="row between">${intro("Журнал партии", batch ? batch.code + " · " + batch.product : "")}${selection()}</div>
    ${batch ? `<section class="panel pad"><div class="row between"><h2>События производства</h2><button class="btn" id="refresh">Обновить</button></div>
    ${batch.events.length ? batch.events.map(e => `<article class="event"><div class="row between"><b>${esc(e.action)}</b><small>${time(e.created)}</small></div>
      <p>${esc(e.author)}${e.detail ? " · " + esc(e.detail) : ""}</p></article>`).join("") : empty("У партии пока нет событий.")}</section>`
      : `<div class="panel">${empty("Выберите партию для просмотра журнала.")}</div>`}`;
}

function issue(main) {
  main.innerHTML = `${intro("Сообщить о проблеме")}
    <section class="panel pad issue-form"><form class="stack" id="problem">${selection()}
    <label>Операция<select name="execution_id">${option("","Общий инцидент",!state.stepId)}
    ${(state.batch?.steps || []).map(s=>option(s.id,s.name,s.id === state.stepId)).join("")}</select></label>
    <label>Уровень<select name="severity">${option("warning","Предупреждение")}${option("critical","Критический")}</select></label>
    <label>Описание<textarea name="description" placeholder="Что произошло и на каком оборудовании?" required></textarea></label>
    <p class="error" role="alert" hidden></p><div><button class="btn primary" ${state.batchId ? "" : "disabled"}>Зарегистрировать</button></div></form></section>`;
  main.querySelector("form").addEventListener("submit", async event => {
    event.preventDefault();
    const button = event.submitter;
    button.disabled = true;
    try {
      await api(`batches/${state.batchId}/incident`, Object.fromEntries(new FormData(event.target)));
      await show("journal");
      notify("Инцидент добавлен в журнал партии.");
    } catch(err) {
      const error = event.target.querySelector(".error");
      error.hidden = false;
      error.textContent = err.message;
      button.disabled = false;
    }
  });
}

const pages = {batches,program,live,journal,issue};
let navigation = 0;
async function show(page, batchId=state.batchId) {
  const epoch = ++navigation;
  state.page = page;
  if (Number(batchId) !== state.batchId) state.stepId = null;
  state.batchId = Number(batchId) || null;
  if (!state.user) return;
  shell();
  const main = document.querySelector("#content");
  main.innerHTML = empty("Загрузка…");
  try {
    const [list,batch] = await Promise.all([
      api(page === "batches" ? "batches?active=1" : "batches"),
      state.batchId && page !== "batches" ? api("batches/" + state.batchId) : null
    ]);
    if (epoch !== navigation || !state.user) return;
    state.list = list;
    state.batch = batch;
    pages[page](main);
    refreshTelemetry().catch(err => notify(err.message));
    alerts().catch(()=>{});
  } catch(err) {
    main.innerHTML = `<div class="panel pad stack"><p class="error">${esc(err.message)}</p><div><button id="refresh" class="btn">Повторить</button></div></div>`;
  }
}

app.addEventListener("click", async event => {
  const button = event.target.closest("button");
  if (!button) return;
  if (button.dataset.page) await show(button.dataset.page);
  if (button.dataset.batch) await show("program", button.dataset.batch);
  if (button.dataset.selectStep) {
    state.stepId = Number(button.dataset.selectStep);
    program(document.querySelector("#content"));
    refreshTelemetry().catch(()=>{});
  }
  if (button.id === "refresh") await show(state.page);
  if (button.id === "notifications") {
    try { await alerts(); showAlerts(); } catch(err) { notify(err.message); }
  }
  if (button.id === "logout") {
    try { await api("logout", {}); } catch {}
    logout();
  }
});
app.addEventListener("change", event => {
  if (event.target.id === "batch-select") show(state.page,event.target.value);
});
modal.addEventListener("click", async event => {
  const button = event.target.closest("button");
  if (!button) return;
  if (button.hasAttribute("data-close")) modal.close();
  if (button.dataset.alertBatch) {
    modal.close();
    await show("program",button.dataset.alertBatch);
  }
  if (button.dataset.read) {
    button.disabled = true;
    try {
      await api("notifications/" + button.dataset.read, {});
      await alerts();
      if (modal.open) showAlerts();
    } catch(err) {
      button.disabled = false;
      notify(err.message);
    }
  }
});

async function boot() {
  try {
    state.demo = (await api("health")).mode === "demo";
    if (state.token) {
      state.user = await api("me");
      if (state.user.role === "operator") {
        await show("batches");
        return;
      }
    }
  } catch {}
  logout();
}
setInterval(() => { if (state.user) refreshTelemetry().catch(()=>{}); },5000);
setInterval(() => { if (state.user) alerts().catch(()=>{}); },15000);
boot();
