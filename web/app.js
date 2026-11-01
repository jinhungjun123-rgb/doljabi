// 돌잡이 화면: 질문 5단계 → 결과 → 상세, 센터 찾기. 채팅은 chat.js가 Dol.screens.chat 으로 붙는다.
(() => {
  const PROFILE_KEY = "doljabi.profile.v1";
  const REGIONS = ["서울", "부산", "대구", "인천", "광주", "대전", "울산", "세종", "경기", "강원", "충북", "충남", "전북", "전남", "경북", "경남", "제주"];
  const LINKS = { youthOn: "https://www.mohw2030.co.kr", bokjiro: "https://www.bokjiro.go.kr", youthCenter: "https://www.youthcenter.go.kr" };

  // 브라우저 저장소는 막혀 있을 수 있다 (사생활 보호 모드 등): 실패해도 앱은 동작한다
  const store = {
    get: (k) => { try { return localStorage.getItem(k); } catch { return null; } },
    set: (k, v) => { try { localStorage.setItem(k, v); } catch { /* 저장 안 됨 */ } },
    del: (k) => { try { localStorage.removeItem(k); } catch { /* 없음 */ } },
  };
  function loadProfile() {
    const raw = store.get(PROFILE_KEY);
    if (!raw) return {};
    try {
      const p = JSON.parse(raw);
      if (p && typeof p === "object" && !Array.isArray(p)) return p;
    } catch { /* 깨진 값 */ }
    store.del(PROFILE_KEY);
    return {};
  }

  const state = { profile: loadProfile(), screen: null, params: {}, data: null, match: null };
  const t = () => window.I18N.ko;
  const app = document.getElementById("app");
  const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const linkify = (s) => esc(s).replace(/https?:\/\/[^\s;,)]+/g, (u) => `<a href="${u}" target="_blank" rel="noopener">${u}</a>`);
  const save = () => store.set(PROFILE_KEY, JSON.stringify(state.profile));
  const programById = (id) => state.data?.programs.find((p) => p.id === id);

  async function api(path, body) {
    const r = await fetch(path, body ? { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(body) } : {});
    if (!r.ok) throw new Error(`${path} ${r.status}`);
    return r.json();
  }

  // ---------------------------------------------------------------- 공통 조각
  function chips(field, options, { multi = false, idk = true, grid = false } = {}) {
    const cur = state.profile[field];
    const on = (v) => (multi ? (cur || []).includes(v) : cur === v);
    const items = Object.entries(options).map(([v, label]) =>
      `<button type="button" class="chip${on(v) ? " on" : ""}" data-field="${field}" data-value="${esc(v)}" data-multi="${multi}">${esc(label)}</button>`);
    if (idk) items.push(`<button type="button" class="chip idk${on("unknown") ? " on" : ""}" data-field="${field}" data-value="unknown" data-multi="${multi}">${esc(t().idk)}</button>`);
    return `<div class="chips${grid ? " grid" : ""}">${items.join("")}</div>`;
  }
  const statusPill = (s) => `<span class="st ${s}">${esc(t().results.status[s])}</span>`;
  function tagFor(p) {
    if (p.group === "local") return `<span class="tag local">${esc(p.region)}</span>`;
    return `<span class="tag${p.group === "linked" ? " linked" : ""}">${esc(t().results.tags[p.group])}</span>`;
  }
  function centerBlock(center) {
    const r = t().results;
    if (!center) return `<div class="center"><p>${esc(r.noRegion)}</p></div>`;
    if (center.status !== "open") {
      return `<div class="center"><span class="label">${esc(r.myCenter)}</span><p>${esc(r.preparing(center.region))}</p>
        <div class="actions"><a href="${LINKS.youthOn}" target="_blank" rel="noopener">${esc(r.apply)}</a><a href="tel:129">📞 129</a></div></div>`;
    }
    const phone = center.phone
      ? `<a href="tel:${esc(center.phone)}">${r.call} ${esc(center.phone)}</a>`
      : `<a href="tel:129">📞 129</a>`;
    return `<div class="center"><span class="label">${esc(r.myCenter)}</span><b>${esc(center.name)}</b>
      ${center.phone ? "" : `<p>${esc(r.noCenterPhone)}</p>`}
      <div class="actions">${phone}<a href="${LINKS.youthOn}" target="_blank" rel="noopener">${esc(r.apply)}</a></div></div>`;
  }

  // ---------------------------------------------------------------- 질문 5단계
  function questionBody(step) {
    const q = t().q, o = t().opt, p = state.profile;
    if (step === 1) {
      const military = p.age >= 35 && p.age <= 40
        ? `<div class="sub-q"><div class="q">${esc(q.military)}</div><div class="row">
             <input class="field" id="military" inputmode="numeric" placeholder="${esc(q.militaryPh)}" value="${p.military_months > 0 ? p.military_months : ""}">
             <button type="button" class="chip${p.military_months === 0 ? " on" : ""}" id="noMilitary">${esc(q.noMilitary)}</button></div></div>` : "";
      return `<div class="privacy">${esc(t().privacy)}</div>
        <div class="q">${esc(q.age)}</div>
        <div class="row"><input class="field" id="age" inputmode="numeric" placeholder="${esc(q.agePh)}" value="${p.age ?? ""}">
          <button type="button" class="chip idk${p.age_unknown ? " on" : ""}" id="ageIdk">${esc(t().idk)}</button></div>
        ${military}
        <div class="q">${esc(q.region)}</div>
        ${chips("region", Object.fromEntries(REGIONS.map((r) => [r, r])), { grid: true })}
        <div class="q">${esc(q.sigungu)}</div>
        <input class="field" id="sigungu" placeholder="${esc(q.sigunguPh)}" value="${esc(p.sigungu || "")}">`;
    }
    if (step === 2) {
      return `<div class="q">${esc(q.relations)}<small>${esc(q.many)}</small></div>${chips("relations", o.relations, { multi: true })}
        <div class="q">${esc(q.conditions)}<small>${esc(q.many)}</small></div>${chips("conditions", o.conditions, { multi: true })}`;
    }
    if (step === 3) {
      const exc = p.adult_other === "yes"
        ? `<div class="sub-q"><div class="q">${esc(q.adultException)}</div>${chips("adult_other_exception", o.adult_other_exception)}</div>` : "";
      return `<div class="q">${esc(q.living)}</div>${chips("living", o.living)}
        <div class="q">${esc(q.adultOther)}</div>${chips("adult_other", o.adult_other)}${exc}`;
    }
    if (step === 4) {
      return `<div class="q">${esc(q.activity)}</div>${chips("activity", o.activity)}
        <div class="q">${esc(q.burden)}</div>${chips("burden", o.burden)}`;
    }
    return `<div class="q">${esc(q.livelihood)}</div>${chips("basic_livelihood", o.basic_livelihood)}
      <div class="q">${esc(q.income)}</div>${chips("income_band", o.income_band)}
      <p class="note">${esc(q.incomeNote)}</p>`;
  }

  function screenQuestion() {
    const step = state.params.step || 1;
    app.innerHTML = `<div class="stepname">${esc(t().step(step))} · ${esc(t().steps[step - 1])}</div>
      <div class="progress"><i style="width:${step * 20}%"></i></div>
      ${questionBody(step)}
      <div class="nav">${step > 1 ? `<button type="button" class="btn ghost" data-go="prev">${esc(t().prev)}</button>` : ""}
        <button type="button" class="btn" data-go="next">${esc(step === 5 ? t().seeResults : t().next)}</button></div>`;
  }

  function readNumber(id) {
    const el = document.getElementById(id);
    if (!el) return undefined;
    const n = parseInt(el.value.replace(/[^0-9]/g, ""), 10);
    return Number.isFinite(n) ? n : null;
  }
  function readStepInputs() {
    if ((state.params.step || 1) !== 1) return;
    const age = readNumber("age");
    if (age !== undefined) { state.profile.age = age; if (age !== null) delete state.profile.age_unknown; }
    const military = readNumber("military");
    if (military !== undefined && military !== null) state.profile.military_months = military;
    const sgg = document.getElementById("sigungu");
    if (sgg) state.profile.sigungu = sgg.value.trim() || null;
    if (!(state.profile.age >= 35 && state.profile.age <= 40)) delete state.profile.military_months;
    save();
  }

  // ---------------------------------------------------------------- 결과
  async function screenResults() {
    const r = t().results;
    if (!state.profile.done) {
      app.innerHTML = `<h1>${esc(r.title)}</h1><p class="sub">${esc(r.empty)}</p><button type="button" class="btn" data-go="start">${esc(r.start)}</button>`;
      return;
    }
    state.match = await api("/api/match", { profile: state.profile });
    const p = state.profile, o = t().opt;
    const tags = [[p.region, p.sigungu].filter(Boolean).join(" "), p.age != null ? `${p.age}세` : "",
      ...(p.relations || []).map((v) => o.relations[v]).filter(Boolean)].filter(Boolean);
    const groups = { national: [], linked: [], local: [] };
    for (const c of state.match.cards) groups[c.group].push(c);
    const section = (g) => {
      if (!groups[g].length) return "";
      const title = g === "local" ? r.groups.local(p.region) : r.groups[g];
      return `<h2>${esc(title)}</h2>` + groups[g].map((c) => {
        const prog = programById(c.id);
        return `<button type="button" class="card" data-detail="${c.id}">
          <span class="meta">${tagFor(prog)}${statusPill(c.status)}${prog.closed ? `<span class="tag closed">${esc(r.closed)}</span>` : ""}</span>
          <span class="name">${esc(prog.name)}</span><span class="desc">${esc(prog.summary)}</span></button>`;
      }).join("");
    };
    app.innerHTML = `<h1>${esc(r.title)}</h1>
      <div class="summary">${tags.map((x) => `<span>${esc(x)}</span>`).join("")}
        <button type="button" class="linkbtn" data-go="start">${esc(r.edit)}</button>
        <button type="button" class="linkbtn" data-go="clear">${esc(r.clear)}</button></div>
      ${centerBlock(state.match.center)}
      ${section("national")}${section("linked")}${section("local")}
      <h2></h2>
      <div class="card more">${esc(r.more)}<br><span class="note">${esc(r.moreSub)}</span></div>
      <div class="card guide">${esc(r.others)}<div class="links"><a href="${LINKS.bokjiro}" target="_blank" rel="noopener">복지로</a>
        <a href="${LINKS.youthCenter}" target="_blank" rel="noopener">온통청년</a><a href="tel:129">📞 129</a></div></div>
      <p class="foot">${esc(r.foot)}</p>`;
  }

  // ---------------------------------------------------------------- 상세
  async function screenDetail() {
    const d = t().detail, prog = programById(state.params.id);
    if (!state.match) state.match = await api("/api/match", { profile: state.profile });
    const card = state.match.cards.find((c) => c.id === prog.id);
    const icon = { ok: "✅", unknown: "❔", no: "❌" };
    const conds = card && card.conditions.length
      ? `<div class="conds">${card.conditions.map((c) => `<div class="cond"><span>${icon[c.result]}</span>
          <span>${esc(c.label)}<span class="law">${esc(c.law)}</span></span></div>`).join("")}</div>` : "";
    const center = state.match.center;
    const call = center && center.status === "open" && center.phone
      ? `<a class="btn" href="tel:${esc(center.phone)}">📞 ${esc(center.name)} ${esc(center.phone)}</a>`
      : `<a class="btn" href="tel:129">${esc(d.call129)}</a>`;
    const field = (label, value) => (value ? `<dt>${esc(label)}</dt><dd>${linkify(value)}</dd>` : "");
    app.innerHTML = `<button type="button" class="back" data-go="results">${esc(d.back)}</button>
      <div class="meta">${tagFor(prog)} ${card ? statusPill(card.status) : ""} ${prog.closed ? `<span class="tag closed">${esc(t().results.closed)}</span>` : ""}</div>
      <h1>${esc(prog.name)}</h1><p class="sub">${esc(prog.summary)}</p>
      ${conds}
      ${prog.notice ? `<div class="warn">⚠ ${esc(prog.notice)}</div>` : ""}
      <dl>${field(d.target, prog.target)}${field(d.income, prog.income)}${field(d.benefit, prog.benefit)}${field(d.how, prog.how)}
        ${field(d.period, prog.period)}${field(d.contact, prog.contact)}${field(d.source, prog.source)}${field(d.checked, prog.checked)}</dl>
      <div class="stack">${call}<button type="button" class="btn ghost" data-ask="${prog.id}">${esc(d.ask)}</button></div>
      <p class="foot">${esc(t().results.foot)}</p>`;
  }

  // ---------------------------------------------------------------- 센터 찾기
  function screenCenters() {
    const c = t().centers, mine = state.profile.region;
    const open = state.data.centers.filter((x) => x.status === "open").sort((a, b) => (b.region === mine) - (a.region === mine));
    const prep = state.data.centers.filter((x) => x.status !== "open");
    const row = (x) => `<div class="crow${x.region === mine ? " mine" : ""}"><div><b>${esc(x.region)}</b> ${esc(x.name)}
        ${x.region === mine ? `<small>${esc(c.mine)}</small>` : ""}</div>
        ${x.phone ? `<a href="tel:${esc(x.phone)}">📞 ${esc(x.phone)}</a>` : `<a href="${LINKS.youthOn}" target="_blank" rel="noopener">청년ON</a>`}</div>`;
    app.innerHTML = `<h1>${esc(c.title)}</h1><p class="sub">${esc(c.sub)} (${esc(state.data.updated)})</p>
      <h2>${esc(c.open(open.length))}</h2>${open.map(row).join("")}
      <h2>${esc(c.preparing(prep.length))}</h2>
      <div class="crow${prep.some((x) => x.region === mine) ? " mine" : ""}"><div><b>${esc(prep.map((x) => x.region).join(" · "))}</b>
        <small>${esc(c.preparingNote)}</small></div><a href="${LINKS.youthOn}" target="_blank" rel="noopener">청년ON</a></div>
      <h2></h2><div class="crow"><div>${esc(c.unsure)}<br><b>${esc(c.hotline)}</b></div><a href="tel:129">📞 129</a></div>`;
  }

  function screenChatPlaceholder() {
    app.innerHTML = `<p class="sub">${esc(t().chatSoon)}</p>`;
  }

  // ---------------------------------------------------------------- 이동, 그리기
  const screens = { q: screenQuestion, results: screenResults, detail: screenDetail, centers: screenCenters, chat: screenChatPlaceholder };
  const TAB_OF = { q: "results", results: "results", detail: "results", chat: "chat", centers: "centers" };

  function renderChrome() {
    document.getElementById("brandSub").textContent = t().appSub;
    const ico = { results: "🧭", chat: "💬", centers: "📍" };
    document.getElementById("tabs").innerHTML = ["results", "chat", "centers"].map((k) =>
      `<button type="button" data-tab="${k}" class="${TAB_OF[state.screen] === k ? "on" : ""}"><span class="ico">${ico[k]}</span>${esc(t().tabs[k])}</button>`).join("");
  }

  async function render() {
    renderChrome();
    try {
      await screens[state.screen]();
    } catch (e) {
      console.error(e);
      app.innerHTML = `<p class="sub">⚠ 화면을 불러오지 못했어요. 잠시 뒤 다시 시도해 주세요.</p>
        <a class="btn" href="tel:129">📞 129</a>`;
    }
  }
  function go(screen, params = {}) {
    state.screen = screen;
    state.params = params;
    render();
    window.scrollTo(0, 0);
  }

  app.addEventListener("click", (e) => {
    const chip = e.target.closest("[data-field]");
    if (chip) {
      const { field, value } = chip.dataset;
      readStepInputs();
      if (chip.dataset.multi === "true") {
        let cur = (state.profile[field] || []).filter((v) => v !== "unknown");
        if (value === "unknown") cur = (state.profile[field] || []).includes("unknown") ? [] : ["unknown"];
        else cur = cur.includes(value) ? cur.filter((v) => v !== value) : [...cur, value];
        state.profile[field] = cur;
      } else {
        state.profile[field] = state.profile[field] === value ? undefined : value;
        if (field === "adult_other" && state.profile.adult_other !== "yes") delete state.profile.adult_other_exception;
      }
      save();
      return screenQuestion();
    }
    if (e.target.id === "ageIdk") { state.profile.age = null; state.profile.age_unknown = true; delete state.profile.military_months; save(); return screenQuestion(); }
    if (e.target.id === "noMilitary") { readStepInputs(); state.profile.military_months = 0; save(); return screenQuestion(); }
    const nav = e.target.closest("[data-go]");
    if (nav) {
      const step = state.params.step || 1;
      readStepInputs();
      if (nav.dataset.go === "next") {
        if (step < 5) return go("q", { step: step + 1 });
        state.profile.done = true; save(); return go("results");
      }
      if (nav.dataset.go === "prev") return go("q", { step: step - 1 });
      if (nav.dataset.go === "start") return go("q", { step: 1 });
      if (nav.dataset.go === "results") return go("results");
      if (nav.dataset.go === "clear" && window.confirm(t().results.clearConfirm)) {
        state.profile = {}; state.match = null; store.del(PROFILE_KEY); return go("q", { step: 1 });
      }
      return undefined;
    }
    const detail = e.target.closest("[data-detail]");
    if (detail) return go("detail", { id: detail.dataset.detail });
    const ask = e.target.closest("[data-ask]");
    if (ask) return go("chat", { programId: ask.dataset.ask });
    return undefined;
  });
  app.addEventListener("change", (e) => {   // 나이를 바꾸면 군 복무 질문이 나타나거나 사라진다
    if (e.target.id === "age") { readStepInputs(); screenQuestion(); document.getElementById("age")?.blur(); }
  });
  document.getElementById("tabs").addEventListener("click", (e) => {
    const b = e.target.closest("[data-tab]");
    if (!b) return;
    if (state.screen === "q") readStepInputs();
    if (b.dataset.tab === "results") return go(state.profile.done ? "results" : "q", { step: 1 });
    return go(b.dataset.tab);
  });
  document.getElementById("brand").addEventListener("click", () => go(state.profile.done ? "results" : "q", { step: 1 }));

  window.Dol = { state, go, api, t, esc, linkify, screens, programById, render };

  (async () => {
    try {
      state.data = await api("/api/programs");
    } catch (e) {
      console.error(e);
      app.innerHTML = `<p class="sub">⚠ 서버에 연결하지 못했어요. 잠시 뒤 다시 열어 주세요.</p><a class="btn" href="tel:129">📞 129</a>`;
      return;
    }
    go(state.profile.done ? "results" : "q", { step: 1 });
  })();
})();
