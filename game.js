const marketList = document.getElementById("market-list");
const inventoryList = document.getElementById("inventory-list");
const cashLabel = document.getElementById("cash-label");
const dayLabel = document.getElementById("day-label");
const nextDayBtn = document.getElementById("next-day-btn");
const toast = document.getElementById("toast");

let currentState = null;

function showToast(msg, type) {
  toast.textContent = msg;
  toast.className = `toast ${type}`;
  toast.classList.remove("hidden");
  setTimeout(() => toast.classList.add("hidden"), 2000);
}

function render(state) {
  currentState = state;
  cashLabel.textContent = `الفلوس: ${Math.round(state.cash)} جنيه`;
  dayLabel.textContent = `اليوم: ${state.day}`;

  marketList.innerHTML = "";
  Object.entries(state.market).forEach(([key, good]) => {
    const owned = state.inventory[key] || 0;
    const card = document.createElement("div");
    card.className = "good-card";
    card.innerHTML = `
      <div class="good-top">
        <span class="good-name">${good.name}</span>
        <span class="good-price">${good.current_price} ج / وحدة</span>
      </div>
      <div class="good-owned">عندك منها: ${owned}</div>
      <div class="good-controls">
        <input type="number" min="1" value="1" id="qty-${key}">
        <button class="mini-btn buy" data-good="${key}" data-action="buy">شراء</button>
        <button class="mini-btn sell" data-good="${key}" data-action="sell">بيع</button>
      </div>
    `;
    marketList.appendChild(card);
  });

  const invEntries = Object.entries(state.inventory).filter(([, qty]) => qty > 0);
  if (invEntries.length === 0) {
    inventoryList.innerHTML = `<p class="empty">المخزن فاضي لسه</p>`;
  } else {
    inventoryList.innerHTML = invEntries
      .map(([key, qty]) => `<div class="inv-row"><span>${state.market[key].name}</span><span>${qty} وحدة</span></div>`)
      .join("");
  }
}

async function loadState() {
  const res = await fetch("/api/state");
  const data = await res.json();
  render(data);
}

marketList.addEventListener("click", async (e) => {
  const btn = e.target.closest(".mini-btn");
  if (!btn) return;

  const good = btn.dataset.good;
  const action = btn.dataset.action;
  const qtyInput = document.getElementById(`qty-${good}`);
  const qty = parseInt(qtyInput.value, 10);

  if (!qty || qty <= 0) {
    showToast("اكتب كمية صحيحة", "error");
    return;
  }

  const res = await fetch(`/api/${action}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ good, qty }),
  });
  const data = await res.json();

  if (!res.ok) {
    showToast(data.error || "حصل خطأ", "error");
    return;
  }

  if (action === "buy") {
    showToast(`اشتريت بـ ${Math.round(data.spent)} جنيه`, "success");
  } else {
    showToast(`بعت بـ ${Math.round(data.earned)} جنيه`, "success");
  }

  render({ cash: data.cash, day: currentState.day, inventory: data.inventory, market: data.market });
});

nextDayBtn.addEventListener("click", async () => {
  const res = await fetch("/api/next_day", { method: "POST" });
  const data = await res.json();
  render({ cash: currentState.cash, day: data.day, inventory: currentState.inventory, market: data.market });
  showToast("يوم جديد بدأ، الأسعار اتحركت شوية", "success");
});

loadState();
