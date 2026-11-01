// 물어보기: POST /api/chat 의 진행 단계(SSE)를 보여 주고, 답과 출처 칩을 그린다. 내 정보가 있으면 함께 보낸다.
(() => {
  const D = window.Dol;
  const app = document.getElementById("app");
  // 메모리에만 (새로고침하면 사라짐). ctxFor/ctxStart: 어느 카드에서 왔고, 그때 대화가 몇 개였는지
  const chat = { messages: [], pending: null, lastQuestion: null, ctxFor: null, ctxStart: 0 };
  D.state.chat = chat;
  const c = () => D.t().chat;
  const esc = D.esc;
  // 답은 마크다운 굵게(**…**)를 쓴다: 이스케이프한 뒤 <b>로 바꾸고, 짝 없는 ** 는 지운다
  const rich = (s) => esc(s).replace(/\*\*(.+?)\*\*/gs, "<b>$1</b>").replace(/\*\*/g, "").replace(/\n/g, "<br>");
  const ctxProgram = () => (D.state.params.programId ? D.programById(D.state.params.programId) : null);

  function bubble(m, i) {
    if (m.role === "user") return `<div class="bub me">${esc(m.content)}</div>`;
    if (m.error) {
      const center = D.state.match?.center;
      const call = center && center.phone ? `<a class="btn small" href="tel:${esc(center.phone)}">📞 ${esc(center.phone)}</a>` : "";
      return `<div class="bub bot err">${esc(c().error)}<div class="row wrap">${call}<a class="btn small" href="tel:129">📞 129</a>
        <button type="button" class="btn small ghost" data-retry>${esc(c().retry)}</button></div></div>`;
    }
    const chips = (m.chips || []).map((ch, j) => `<button type="button" class="src" data-src="${i}-${j}">📘 ${esc(ch.label)}</button>
      ${ch.open && ch.text ? `<div class="srctext">${esc(ch.text)}</div>` : ""}`).join("");
    const web = (m.web || []).map((u) => `<a class="src web" href="${esc(u)}" target="_blank" rel="noopener">${esc(c().web)}</a>`).join("");
    return `<div class="bub bot">${rich(m.content)}
      ${chips || web ? `<div class="srcs">${chips}${web}</div>` : ""}<div class="disc">${esc(c().disclaimer)}</div></div>`;
  }

  function progress() {
    if (!chat.pending) return "";
    const labels = c().steps;
    return `<div class="prog">${chat.pending.steps.map((s, i) => {
      const done = i < chat.pending.steps.length - 1;
      return `<div>${esc(labels[s] || labels.tool)} ${done ? "✓" : "…"}</div>`;
    }).join("") || `<div>${esc(labels.route)} …</div>`}</div>`;
  }

  const freshFromCard = () => ctxProgram() && chat.messages.length === chat.ctxStart;

  function render() {
    const prog = ctxProgram();
    if (prog && chat.ctxFor !== D.state.params) {   // 카드에서 새로 들어옴: 그 시점부터 추천 질문과 사업명 붙이기
      chat.ctxFor = D.state.params;
      chat.ctxStart = chat.messages.length;
    }
    const suggestions = freshFromCard() ? c().suggest(prog.name) : chat.messages.length || prog ? [] : c().starters;
    app.innerHTML = `<h1>${esc(c().title)}</h1>
      ${prog ? `<div class="ctx">${esc(c().fromCard(prog.name))}</div>` : ""}
      <div class="msgs">${chat.messages.length ? "" : `<div class="bub bot">${esc(c().hello)}</div>`}
        ${chat.messages.map(bubble).join("")}${progress()}</div>
      ${suggestions.length ? `<div class="chips sugg">${suggestions.map((s) => `<button type="button" class="chip" data-suggest="${esc(s)}">${esc(s)}</button>`).join("")}</div>` : ""}
      <form class="ask" id="askForm"><input class="field" id="askInput" autocomplete="off" placeholder="${esc(c().placeholder)}" ${chat.pending ? "disabled" : ""}>
        <button class="btn small" ${chat.pending ? "disabled" : ""}>${esc(c().send)}</button></form>`;
    const last = app.querySelector(".msgs > :last-child");
    if (last && chat.messages.length) last.scrollIntoView({ block: "end" });
  }

  async function send(question) {
    question = question.trim();
    if (!question || chat.pending) return;
    const prog = ctxProgram();
    const asked = freshFromCard() && !question.includes(prog.name) ? c().about(prog.name) + question : question;
    const history = chat.messages.filter((m) => !m.error).slice(-6).map((m) => ({ role: m.role, content: m.content }));
    chat.messages.push({ role: "user", content: question });
    chat.lastQuestion = question;
    chat.pending = { steps: [] };
    render();
    const profile = D.state.profile && Object.keys(D.state.profile).length ? D.state.profile : null;
    let answered = false;
    try {
      const r = await fetch("/api/chat", { method: "POST", headers: { "content-type": "application/json" },
        body: JSON.stringify({ question: asked, history, profile, lang: D.state.lang }) });
      if (!r.ok || !r.body) throw new Error(`chat ${r.status}`);
      const reader = r.body.getReader();
      const dec = new TextDecoder();
      let buf = "";
      for (;;) {
        const { value, done } = await reader.read();
        if (done) break;
        buf += dec.decode(value, { stream: true });
        let cut;
        while ((cut = buf.indexOf("\n\n")) >= 0) {
          const block = buf.slice(0, cut);
          buf = buf.slice(cut + 2);
          const event = /^event: (.*)$/m.exec(block)?.[1];
          const data = JSON.parse(/^data: (.*)$/m.exec(block)?.[1] || "{}");
          if (event === "progress") {
            chat.pending.steps.push(data.step === "tool" ? data.name : data.step);
            if (D.state.screen === "chat") render();
          } else if (event === "answer") {
            chat.messages.push({ role: "assistant", content: data.answer, chips: data.chips, web: data.web });
            answered = true;
          } else if (event === "error") {
            break;
          }
        }
      }
    } catch (e) {
      console.warn(e);
    }
    if (!answered) chat.messages.push({ role: "assistant", content: "", error: true });
    chat.pending = null;
    if (D.state.screen === "chat") render();
  }

  app.addEventListener("submit", (e) => {
    if (e.target.id !== "askForm") return;
    e.preventDefault();
    const input = document.getElementById("askInput");
    const q = input.value;
    input.value = "";
    send(q);
  });
  app.addEventListener("click", (e) => {
    if (D.state.screen !== "chat") return;
    const sug = e.target.closest("[data-suggest]");
    if (sug) return send(sug.dataset.suggest);
    const src = e.target.closest("[data-src]");
    if (src) {
      const [i, j] = src.dataset.src.split("-").map(Number);
      const chip = chat.messages[i].chips[j];
      chip.open = !chip.open;
      return render();
    }
    if (e.target.closest("[data-retry]") && chat.lastQuestion) {
      chat.messages = chat.messages.slice(0, -2);   // 실패한 질문과 오류 말풍선을 지우고 다시 보낸다
      return send(chat.lastQuestion);
    }
    return undefined;
  });

  D.screens.chat = render;
})();
