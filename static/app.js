const $ = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => [...r.querySelectorAll(s)];
const money = (n) =>
  new Intl.NumberFormat("vi-VN", { maximumFractionDigits: 0 }).format(
    Number(n || 0),
  ) + " ₫";
const today = () => new Date().toISOString().slice(0, 10);
const thisMonth = () => today().slice(0, 7);
let csrf = "",
  authMode = "login",
  user = null,
  txCache = [];

async function api(path, options = {}) {
  const headers = {
    "Content-Type": "application/json",
    ...(options.headers || {}),
  };
  if (options.method && options.method !== "GET" && options.method !== "HEAD")
    headers["X-CSRF-Token"] = csrf;
  const res = await fetch(path, { ...options, headers });
  let data = {};
  try {
    data = await res.json();
  } catch {}
  if (
    res.status === 401 &&
    !path.includes("/login") &&
    !path.includes("/register")
  ) {
    showAuth();
    throw new Error(data.error || "Phiên đăng nhập đã hết hạn.");
  }
  if (!res.ok) throw new Error(data.error || "Có lỗi xảy ra.");
  return data;
}
function toast(msg) {
  const el = $("#toast");
  el.textContent = msg;
  el.classList.add("show");
  setTimeout(() => el.classList.remove("show"), 2600);
}
function esc(s = "") {
  return String(s).replace(
    /[&<>"']/g,
    (c) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[
        c
      ],
  );
}
function showAuth() {
  user = null;
  $("#app").classList.add("hidden");
  $("#auth").classList.remove("hidden");
}
function showApp() {
  $("#auth").classList.add("hidden");
  $("#app").classList.remove("hidden");
  $("#username-label").textContent = user.username;
  $("#avatar").textContent = (user.username[0] || "U").toUpperCase();
  route();
}
async function bootstrap() {
  try {
    const d = await api("/api/me");
    user = d.user;
    csrf = d.csrf || "";
    user ? showApp() : showAuth();
  } catch {
    showAuth();
  }
}

$("#auth-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  $("#auth-error").textContent = "";
  const d = Object.fromEntries(new FormData(e.currentTarget));
  try {
    await api(authMode === "login" ? "/api/login" : "/api/register", {
      method: "POST",
      body: JSON.stringify(d),
    });
    await bootstrap();
  } catch (err) {
    $("#auth-error").textContent = err.message;
  }
});
$$("[data-auth]").forEach((b) =>
  b.addEventListener("click", () => {
    authMode = b.dataset.auth;
    $$("[data-auth]").forEach((x) => x.classList.toggle("active", x === b));
    $("#auth-submit").textContent =
      authMode === "login" ? "Đăng nhập" : "Tạo tài khoản";
    $("#auth-error").textContent = "";
  }),
);
$("#logout").addEventListener("click", async () => {
  try {
    await api("/api/logout", { method: "POST", body: "{}" });
  } catch {}
  csrf = "";
  showAuth();
});
$("#mobile-menu").addEventListener("click", () =>
  $(".sidebar").classList.toggle("open"),
);
$("#nav").addEventListener("click", (e) => {
  if (e.target.closest("a")) $(".sidebar").classList.remove("open");
});
window.addEventListener("hashchange", route);

function route() {
  if (!user) return;
  const p = location.hash.slice(1) || "dashboard";
  const name = [
    "dashboard",
    "transactions",
    "categories",
    "budgets",
    "goals",
    "assistant",
  ].includes(p)
    ? p
    : "dashboard";
  $$(".page").forEach((x) =>
    x.classList.toggle("hidden", x.id !== "page-" + name),
  );
  $$(".nav-item").forEach((x) =>
    x.classList.toggle("active", x.dataset.page === name),
  );
  $("#page-label").textContent = {
    dashboard: "Tổng quan",
    transactions: "Giao dịch",
    categories: "Danh mục",
    budgets: "Ngân sách",
    goals: "Mục tiêu tiết kiệm",
    assistant: "Trợ lý AI",
  }[name];
  ({
    dashboard: renderDashboard,
    transactions: renderTransactions,
    categories: renderCategories,
    budgets: renderBudgets,
    goals: renderGoals,
    assistant: renderAssistant,
  })[name]();
}
const title = (h, sub, btn = "") =>
  `<div class="page-title"><div><h1>${h}</h1><p>${sub}</p></div>${btn}</div>`;

async function renderDashboard() {
  const root = $("#page-dashboard");
  root.innerHTML =
    title(
      "Chào " + esc(user.username) + " 👋",
      "Đây là bức tranh tài chính của bạn trong tháng này.",
      `<a class="btn primary" href="#transactions" onclick="setTimeout(openTransaction,0)">＋ Thêm giao dịch</a>`,
    ) +
    `<div id="budget-alerts"></div><div class="stats" id="stats"></div><div class="grid-2"><div class="card"><div class="card-head"><div><h2>Dòng tiền tháng</h2><p>So sánh tổng thu và chi hiện tại</p></div><span class="month-label">${thisMonth()}</span></div><div class="chart-wrap"><canvas id="cash-chart"></canvas></div><div class="legend"><span>Thu nhập</span><span class="expense">Chi tiêu</span></div></div><div class="card"><div class="card-head"><div><h2>Chi tiêu theo danh mục</h2><p>Phân bổ chi tiêu tháng này</p></div></div><div id="category-list" class="category-list"></div></div></div><div class="card" style="margin-bottom:16px"><div class="card-head"><div><h2>Xu hướng thu chi theo năm</h2><p>So sánh tổng thu và chi theo từng tháng</p></div><label class="month-label">Năm <input id="trend-year" type="number" min="2000" max="2100" value="${thisMonth().slice(0, 4)}" style="width:82px;padding:6px;border:1px solid var(--line);border-radius:6px"></label></div><div class="chart-wrap"><canvas id="trend-chart"></canvas></div><div class="legend"><span>Thu nhập</span><span class="expense">Chi tiêu</span></div></div><div class="card"><div class="card-head"><div><h2>Giao dịch gần đây</h2><p>Các cập nhật mới nhất</p></div><a class="text-btn" href="#transactions">Xem tất cả →</a></div><div id="recent-table"></div></div>`;
  try {
    const d = await api("/api/dashboard");
    $("#stats").innerHTML = [
      ["Tổng thu nhập", d.income, "↗", "green"],
      ["Tổng chi tiêu", d.expense, "↘", "red"],
      ["Số dư hiện tại", d.balance, "◈", "blue"],
      ["Ngân sách đã đặt", d.budgets.length, "◷", ""],
    ]
      .map(
        ([l, v, i, c], n) =>
          `<div class="stat"><div class="stat-top">${l}<span class="stat-icon ${c}">${i}</span></div><strong>${n === 3 ? Number(v) + " danh mục" : money(v)}</strong><small>${n === 2 ? "Thu nhập trừ chi tiêu" : n === 3 ? "Trong tháng này" : "Trong tháng này"}</small></div>`,
      )
      .join("");
    const cats = d.by_category;
    $("#category-list").innerHTML = cats.length
      ? cats
          .slice(0, 5)
          .map(
            (x, i) =>
              `<div class="cat-row"><span class="cat-name">${esc(x.category)}</span><span class="cat-amount">${money(x.amount)}</span><div class="progress"><i style="width:${Math.max(3, (x.amount / (cats[0].amount || 1)) * 100)}%;background:${["#7366e7", "#f5a26c", "#49b998", "#5a9be7", "#e17ca7"][i % 5]}"></i></div></div>`,
          )
          .join("")
      : '<div class="empty">Chưa có khoản chi trong tháng.</div>';
    const over = d.budgets.filter((b) => b.spent > b.limit_amount);
    $("#budget-alerts").innerHTML = over.length
      ? `<div class="notice alert-notice">⚠️ Vượt ngân sách: ${over.map((b) => `${esc(b.category)} (${money(b.spent)} / ${money(b.limit_amount)})`).join(" · ")}</div>`
      : "";
    drawChart(d.income, d.expense);
    $("#recent-table").innerHTML = table(d.recent);
    $("#trend-year").onchange = loadTrends;
    loadTrends();
  } catch (err) {
    toast(err.message);
  }
}
function drawChart(income, expense) {
  const c = $("#cash-chart");
  if (!c) return;
  const rect = c.getBoundingClientRect(),
    dpr = window.devicePixelRatio || 1;
  c.width = rect.width * dpr;
  c.height = rect.height * dpr;
  const ctx = c.getContext("2d");
  ctx.scale(dpr, dpr);
  const w = rect.width,
    h = rect.height,
    max = Math.max(income, expense, 1) * 1.15;
  ctx.strokeStyle = "#edf0f5";
  ctx.lineWidth = 1;
  ctx.fillStyle = "#95a0b2";
  ctx.font = "10px Arial";
  for (let i = 0; i < 4; i++) {
    const y = 14 + (i * (h - 42)) / 3;
    ctx.beginPath();
    ctx.moveTo(34, y);
    ctx.lineTo(w - 8, y);
    ctx.stroke();
    ctx.fillText(money((max * (3 - i)) / 3).replace(" ₫", ""), 0, y + 3);
  }
  const base = h - 22;
  for (const [x, val, color] of [
    [w * 0.37, income, "#7264e6"],
    [w * 0.68, expense, "#f6ad79"],
  ]) {
    const bh = ((base - 22) * val) / max;
    ctx.fillStyle = color;
    ctx.beginPath();
    ctx.roundRect(x - 22, base - bh, 44, bh, 6);
    ctx.fill();
    ctx.fillStyle = "#7b8597";
    ctx.textAlign = "center";
    ctx.fillText(x < w / 2 ? "Thu nhập" : "Chi tiêu", x, h - 3);
  }
}
async function loadTrends() {
  const c = $("#trend-chart"),
    year = Number($("#trend-year")?.value || thisMonth().slice(0, 4));
  if (!c) return;
  try {
    const d = await api("/api/trends?year=" + year);
    drawTrend(d.months);
  } catch (e) {
    toast(e.message);
  }
}
function drawTrend(rows) {
  const c = $("#trend-chart");
  if (!c) return;
  const rect = c.getBoundingClientRect(),
    dpr = window.devicePixelRatio || 1;
  c.width = rect.width * dpr;
  c.height = rect.height * dpr;
  const ctx = c.getContext("2d");
  ctx.scale(dpr, dpr);
  const w = rect.width,
    h = rect.height,
    vals = rows.flatMap((x) => [x.income, x.expense]),
    max = Math.max(...vals, 1) * 1.1,
    left = 36,
    right = 8,
    top = 16,
    bottom = 25,
    plotH = h - top - bottom,
    slot = (w - left - right) / 12;
  ctx.strokeStyle = "#edf0f5";
  ctx.fillStyle = "#95a0b2";
  ctx.font = "9px Arial";
  ctx.textAlign = "left";
  for (let i = 0; i < 4; i++) {
    let y = top + (i * plotH) / 3;
    ctx.beginPath();
    ctx.moveTo(left, y);
    ctx.lineTo(w - right, y);
    ctx.stroke();
    ctx.fillText(money((max * (3 - i)) / 3).replace(" ₫", ""), 0, y + 3);
  }
  rows.forEach((m, i) => {
    const x = left + i * slot + slot * 0.2,
      bw = slot * 0.24;
    [
      [m.income, "#7264e6"],
      [m.expense, "#f6ad79"],
    ].forEach(([v, col], j) => {
      const bh = (v / max) * plotH;
      ctx.fillStyle = col;
      ctx.beginPath();
      ctx.roundRect(x + j * (bw + 2), top + plotH - bh, bw, bh, 3);
      ctx.fill();
    });
    ctx.fillStyle = "#7b8597";
    ctx.textAlign = "center";
    ctx.fillText(String(i + 1), left + i * slot + slot / 2, h - 6);
  });
}
function table(rows) {
  if (!rows?.length)
    return '<div class="empty"><div class="empty-icon">☷</div>Chưa có giao dịch nào.</div>';
  return `<div class="table-wrap"><table class="data-table"><thead><tr><th>GIAO DỊCH</th><th>NGÀY</th><th>LOẠI</th><th>SỐ TIỀN</th><th></th></tr></thead><tbody>${rows.map((x) => `<tr><td><b>${esc(x.category)}</b><br><small class="muted">${esc(x.note || "—")}</small></td><td>${esc(x.txn_date)}</td><td><span class="type-pill ${x.kind}">${x.kind === "income" ? "Thu nhập" : "Chi tiêu"}</span></td><td class="amount ${x.kind}">${x.kind === "income" ? "+" : "−"}${money(x.amount)}</td><td><div class="actions"><button class="text-btn" onclick="editTransaction(${x.id})">Sửa</button><button class="text-btn" onclick="deleteTransaction(${x.id})">Xóa</button></div></td></tr>`).join("")}</tbody></table></div>`;
}

async function renderTransactions() {
  const r = $("#page-transactions");
  r.innerHTML =
    title(
      "Giao dịch",
      "Quản lý các khoản thu và chi của bạn.",
      `<button class="btn primary" onclick="openTransaction()">＋ Thêm giao dịch</button>`,
    ) +
    `<div class="card"><div class="filters"><input id="tx-search" placeholder="Tìm danh mục hoặc ghi chú"><input id="tx-month" type="month" value="${thisMonth()}"><select id="tx-kind"><option value="">Tất cả giao dịch</option><option value="income">Thu nhập</option><option value="expense">Chi tiêu</option></select><button class="btn soft" id="tx-filter">Lọc</button></div><div id="tx-table"></div></div>`;
  $("#tx-filter").onclick = loadTransactions;
  $("#tx-search").onkeydown = (e) => {
    if (e.key === "Enter") loadTransactions();
  };
  loadTransactions();
}
async function loadTransactions() {
  try {
    const q = new URLSearchParams({
      q: $("#tx-search").value,
      month: $("#tx-month").value,
      kind: $("#tx-kind").value,
    });
    const d = await api("/api/transactions?" + q);
    txCache = d.items;
    $("#tx-table").innerHTML = table(d.items);
  } catch (e) {
    toast(e.message);
  }
}
function openTransaction(item = null) {
  const root = $("#modal-root");
  root.innerHTML = `<div class="modal-backdrop" id="backdrop"><div class="modal"><h2>${item ? "Sửa giao dịch" : "Thêm giao dịch mới"}</h2><form id="tx-form"><label>Loại giao dịch<select name="kind"><option value="expense">Chi tiêu</option><option value="income">Thu nhập</option></select></label><label>Số tiền (₫)<input name="amount" type="number" min="1" step="1" required placeholder="0"></label><label>Danh mục<input name="category" required maxlength="50" placeholder="VD: Ăn uống"></label><label>Ngày giao dịch<input name="txn_date" type="date" required value="${today()}"></label><label class="full">Ghi chú<input name="note" maxlength="200" placeholder="Mô tả ngắn"></label><div class="modal-actions"><button type="button" class="btn" onclick="closeModal()">Hủy</button><button class="btn primary" type="submit">Lưu giao dịch</button></div></form></div></div>`;
  if (item)
    Object.entries(item).forEach(([k, v]) => {
      const el = $(`[name=${k}]`, root);
      if (el) el.value = v;
    });
  $("#tx-form").onsubmit = async (e) => {
    e.preventDefault();
    const d = Object.fromEntries(new FormData(e.currentTarget));
    try {
      await api(item ? "/api/transactions/" + item.id : "/api/transactions", {
        method: item ? "PUT" : "POST",
        body: JSON.stringify(d),
      });
      closeModal();
      toast("Đã lưu giao dịch.");
      route();
    } catch (err) {
      toast(err.message);
    }
  };
  $("#backdrop").onclick = (e) => {
    if (e.target.id === "backdrop") closeModal();
  };
}

async function renderCategories() {
  const r = $("#page-categories");
  r.innerHTML =
    title(
      "Danh mục thu chi",
      "Tạo và đổi tên danh mục để phân loại giao dịch.",
      `<button class="btn primary" onclick="openCategory()">＋ Thêm danh mục</button>`,
    ) +
    `<div class="card"><div class="card-head"><div><h2>Danh sách danh mục</h2><p>Danh mục đang dùng trong giao dịch sẽ được bảo vệ khi xóa.</p></div></div><div id="category-table"></div></div>`;
  loadCategories();
}
async function loadCategories() {
  try {
    const d = await api("/api/categories");
    const rows = d.items;
    $("#category-table").innerHTML = rows.length
      ? `<div class="table-wrap"><table class="data-table"><thead><tr><th>TÊN DANH MỤC</th><th>LOẠI</th><th></th></tr></thead><tbody>${rows.map((x) => `<tr><td><b>${esc(x.name)}</b></td><td><span class="type-pill ${x.kind}">${x.kind === "income" ? "Thu nhập" : "Chi tiêu"}</span></td><td><div class="actions"><button class="text-btn" onclick="editCategory(${x.id})">Đổi tên</button><button class="text-btn" onclick="deleteCategory(${x.id})">Xóa</button></div></td></tr>`).join("")}</tbody></table></div>`
      : '<div class="empty">Chưa có danh mục.</div>';
  } catch (e) {
    toast(e.message);
  }
}
window.openCategory = (item = null) => {
  const root = $("#modal-root");
  root.innerHTML = `<div class="modal-backdrop" id="backdrop"><div class="modal"><h2>${item ? "Đổi tên" : "Thêm"} danh mục</h2><form id="category-form"><label class="full">Tên danh mục<input name="name" maxlength="50" required value="${esc(item?.name || "")}" placeholder="VD: Ăn uống"></label><label class="full">Loại danh mục<select name="kind" ${item ? "disabled" : ""}><option value="expense">Chi tiêu</option><option value="income">Thu nhập</option></select></label><div class="modal-actions"><button type="button" class="btn" onclick="closeModal()">Hủy</button><button class="btn primary">Lưu danh mục</button></div></form></div></div>`;
  if (item) $("[name=kind]").value = item.kind;
  $("#category-form").onsubmit = async (e) => {
    e.preventDefault();
    const fd = new FormData(e.currentTarget),
      data = { name: fd.get("name"), kind: item?.kind || fd.get("kind") };
    try {
      await api(item ? "/api/categories/" + item.id : "/api/categories", {
        method: item ? "PUT" : "POST",
        body: JSON.stringify(data),
      });
      closeModal();
      toast("Đã lưu danh mục.");
      loadCategories();
    } catch (err) {
      toast(err.message);
    }
  };
};
window.editCategory = async (id) => {
  const d = await api("/api/categories");
  openCategory(d.items.find((x) => x.id === id));
};
window.deleteCategory = async (id) => {
  if (!confirm("Xóa danh mục này?")) return;
  try {
    await api("/api/categories/" + id, { method: "DELETE" });
    toast("Đã xóa danh mục.");
    loadCategories();
  } catch (e) {
    toast(e.message);
  }
};
window.openTransaction = openTransaction;
window.closeModal = () => ($("#modal-root").innerHTML = "");
window.editTransaction = (id) => {
  const item = txCache.find((x) => x.id === id);
  if (item) openTransaction(item);
  else
    api("/api/transactions").then((d) => {
      txCache = d.items;
      openTransaction(txCache.find((x) => x.id === id));
    });
};
window.deleteTransaction = async (id) => {
  if (!confirm("Xóa giao dịch này?")) return;
  try {
    await api("/api/transactions/" + id, { method: "DELETE" });
    toast("Đã xóa giao dịch.");
    route();
  } catch (e) {
    toast(e.message);
  }
};

async function renderBudgets() {
  const r = $("#page-budgets");
  r.innerHTML =
    title(
      "Ngân sách",
      "Đặt giới hạn chi tiêu và theo dõi tiến độ theo danh mục.",
      `<button class="btn primary" onclick="openBudget()">＋ Tạo ngân sách</button>`,
    ) +
    `<div class="filters"><input id="budget-month" type="month" value="${thisMonth()}"><button class="btn soft" id="budget-filter">Xem tháng</button></div><div class="budget-cards" id="budget-list"></div>`;
  $("#budget-filter").onclick = loadBudgets;
  loadBudgets();
}
async function loadBudgets() {
  try {
    const d = await api("/api/budgets?month=" + $("#budget-month").value);
    $("#budget-list").innerHTML = d.items.length
      ? d.items
          .map((b) => {
            const p = (b.spent / b.amount) * 100;
            return `<div class="budget-card"><div class="budget-top"><strong>${esc(b.category)}</strong><button class="text-btn" onclick="deleteBudget(${b.id})">Xóa</button></div><div class="big">${money(b.spent)}</div><small>đã dùng trên ${money(b.amount)}</small><div class="progress"><i class="${p > 100 ? "over" : ""}" style="width:${Math.min(p, 100)}%"></i></div><small>${p.toFixed(0)}% ngân sách · ${esc(b.month)}</small></div>`;
          })
          .join("")
      : '<div class="card empty">Chưa có ngân sách cho tháng này.</div>';
  } catch (e) {
    toast(e.message);
  }
}
window.openBudget = () => {
  const root = $("#modal-root");
  root.innerHTML = `<div class="modal-backdrop" id="backdrop"><div class="modal"><h2>Tạo hoặc cập nhật ngân sách</h2><form id="budget-form"><label>Danh mục<input name="category" required placeholder="VD: Ăn uống"></label><label>Hạn mức (₫)<input name="amount" type="number" min="1" required></label><label class="full">Tháng<input name="month" type="month" value="${thisMonth()}" required></label><div class="modal-actions"><button type="button" class="btn" onclick="closeModal()">Hủy</button><button class="btn primary">Lưu ngân sách</button></div></form></div></div>`;
  $("#budget-form").onsubmit = async (e) => {
    e.preventDefault();
    try {
      await api("/api/budgets", {
        method: "POST",
        body: JSON.stringify(Object.fromEntries(new FormData(e.currentTarget))),
      });
      closeModal();
      toast("Đã lưu ngân sách.");
      loadBudgets();
    } catch (err) {
      toast(err.message);
    }
  };
};
window.deleteBudget = async (id) => {
  if (!confirm("Xóa ngân sách này?")) return;
  try {
    await api("/api/budgets/" + id, { method: "DELETE" });
    loadBudgets();
  } catch (e) {
    toast(e.message);
  }
};

async function renderGoals() {
  const r = $("#page-goals");
  r.innerHTML =
    title(
      "Mục tiêu tiết kiệm",
      "Theo dõi tiến độ tích lũy cho những điều bạn hướng tới.",
      `<button class="btn primary" onclick="openGoal()">＋ Tạo mục tiêu</button>`,
    ) + `<div class="goal-grid" id="goal-list"></div>`;
  try {
    const d = await api("/api/goals");
    $("#goal-list").innerHTML = d.items.length
      ? d.items
          .map((g) => {
            const p = (g.saved / g.target) * 100;
            return `<div class="goal-card"><div class="goal-top"><strong>◎ &nbsp;${esc(g.title)}</strong><div><button class="text-btn" onclick="editGoal(${g.id})">Sửa</button><button class="text-btn" onclick="deleteGoal(${g.id})">Xóa</button></div></div><div class="big">${money(g.saved)}</div><small>mục tiêu ${money(g.target)}</small><div class="progress"><i style="width:${Math.min(p, 100)}%"></i></div><small>${p.toFixed(0)}% hoàn thành${g.due_date ? " · Hạn " + esc(g.due_date) : ""}</small></div>`;
          })
          .join("")
      : '<div class="card empty">Chưa có mục tiêu tiết kiệm.</div>';
  } catch (e) {
    toast(e.message);
  }
}
let goalCache = [];
window.openGoal = (g = null) => {
  const root = $("#modal-root");
  root.innerHTML = `<div class="modal-backdrop" id="backdrop"><div class="modal"><h2>${g ? "Cập nhật" : "Tạo"} mục tiêu tiết kiệm</h2><form id="goal-form"><label class="full">Tên mục tiêu<input name="title" required maxlength="80" value="${esc(g?.title || "")}" placeholder="VD: Mua laptop"></label><label>Số tiền mục tiêu<input name="target" type="number" min="1" required value="${g?.target || ""}"></label><label>Đã tiết kiệm<input name="saved" type="number" min="0" value="${g?.saved || 0}"></label><label class="full">Ngày dự kiến<input name="due_date" type="date" value="${g?.due_date || ""}"></label><div class="modal-actions"><button type="button" class="btn" onclick="closeModal()">Hủy</button><button class="btn primary">Lưu mục tiêu</button></div></form></div></div>`;
  $("#goal-form").onsubmit = async (e) => {
    e.preventDefault();
    try {
      await api(g ? "/api/goals/" + g.id : "/api/goals", {
        method: g ? "PUT" : "POST",
        body: JSON.stringify(Object.fromEntries(new FormData(e.currentTarget))),
      });
      closeModal();
      toast("Đã lưu mục tiêu.");
      renderGoals();
    } catch (err) {
      toast(err.message);
    }
  };
};
window.editGoal = async (id) => {
  const d = await api("/api/goals");
  openGoal(d.items.find((x) => x.id === id));
};
window.deleteGoal = async (id) => {
  if (!confirm("Xóa mục tiêu này?")) return;
  try {
    await api("/api/goals/" + id, { method: "DELETE" });
    renderGoals();
  } catch (e) {
    toast(e.message);
  }
};

function renderAssistantReport() {
  const r = $("#page-assistant");
  r.innerHTML =
    title(
      "Trợ lý tài chính AI",
      "Hỏi đáp và nhận gợi ý dựa trên dữ liệu thu chi của bạn.",
    ) +
    `<div class="assistant-intro"><div><h2>✦ &nbsp;Phân tích chi tiêu thông minh</h2><p>Trợ lý xem tổng thu, tổng chi, danh mục và ngân sách trong tháng.</p></div><div class="sparkle">✦</div></div><div class="card"><div class="card-head"><div><h2>Báo cáo tài chính tháng</h2><p>AI chỉ truy cập số liệu cần thiết của tài khoản đang đăng nhập</p></div><div class="filters"><input id="ai-month" type="month" value="${thisMonth()}"><button class="btn primary" id="ai-run">✦ Tạo phân tích</button></div></div><div id="ai-output" class="ai-result">Chọn tháng và bấm “Tạo phân tích” để bắt đầu.</div><div id="ai-disclaimer" class="disclaimer"></div></div><div class="notice">Thông tin là gợi ý tham khảo, không phải tư vấn tài chính chuyên nghiệp. Không nhập mật khẩu ngân hàng, số thẻ hoặc dữ liệu nhạy cảm vào ghi chú giao dịch.</div>`;
  $("#ai-run").onclick = async () => {
    const out = $("#ai-output");
    out.textContent = "Đang phân tích dữ liệu…";
    $("#ai-disclaimer").textContent = "";
    try {
      const d = await api("/api/ai/summary", {
        method: "POST",
        body: JSON.stringify({ month: $("#ai-month").value }),
      });
      out.textContent = d.answer;
      $("#ai-disclaimer").textContent =
        (d.provider === "demo-local"
          ? "Chế độ demo ngoại tuyến · "
          : "Mô hình: " + d.provider + " · ") + d.disclaimer;
    } catch (e) {
      out.textContent = e.message;
    }
  };
}
function renderAssistant() {
  renderAssistantReport();
  const r = $("#page-assistant");
  r.insertAdjacentHTML(
    "beforeend",
    `<div class="card" style="margin-top:16px"><div class="card-head"><div><h2>Hỏi trợ lý về chi tiêu</h2><p>Ví dụ: “Tháng này tôi chi nhiều nhất vào đâu?”</p></div></div><div id="chat-log" class="chat-log"><div class="chat-message assistant">Xin chào! Mình có thể xem tổng thu chi, danh mục chi nhiều nhất, ngân sách và gợi ý tiết kiệm.</div></div><form id="chat-form" class="chat-form"><input id="chat-question" maxlength="500" placeholder="Nhập câu hỏi về dữ liệu thu chi…" required><button class="btn primary">Gửi câu hỏi</button></form><div id="chat-status" class="disclaimer"></div></div>`,
  );
  $("#chat-form").onsubmit = async (e) => {
    e.preventDefault();
    const q = $("#chat-question").value.trim();
    if (!q) return;
    const log = $("#chat-log"),
      status = $("#chat-status");
    const userMsg = document.createElement("div");
    userMsg.className = "chat-message user";
    userMsg.textContent = q;
    log.append(userMsg);
    $("#chat-question").value = "";
    status.textContent = "Đang kiểm tra dữ liệu…";
    try {
      const d = await api("/api/ai/chat", {
        method: "POST",
        body: JSON.stringify({ question: q, month: $("#ai-month").value }),
      });
      const msg = document.createElement("div");
      msg.className = "chat-message assistant";
      msg.textContent = d.answer;
      log.append(msg);
      status.textContent =
        (d.provider === "demo-local"
          ? "Chế độ demo ngoại tuyến · "
          : "Mô hình: " + d.provider + " · ") + d.disclaimer;
      log.scrollTop = log.scrollHeight;
    } catch (err) {
      status.textContent = err.message;
    }
  };
}

bootstrap();
