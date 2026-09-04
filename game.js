const marketList = document.getElementById("market-list");
const inventoryList = document.getElementById("inventory-list");
const cashLabel = document.getElementById("cash-label");
const dayLabel = document.getElementById("day-label");
const rentLabel = document.getElementById("rent-label");
const newsBox = document.getElementById("news-box");
const nextDayBtn = document.getElementById("next-day-btn");
const toast = document.getElementById("toast");

let currentState = null;

function showToast(msg, type) {
  toast.textContent = msg;
  toast.className = `toast ${type}`;
  toast.classList.remove("hidden");
  setTimeout(() => toast.classList.add("hidden"), 2500);
}

function render(state) {
  currentState = state;
  cashLabel.textContent = `الفلوس: ${Math.round(state.cash)} جنيه`;
  dayLabel.textContent = `اليوم: ${state.day}`;
  rentLabel.textContent = `الإيجار (${state.rent_amount}ج) خلال: ${state.days_to_rent} أيام`;
  newsBox.textContent = state.news || "السوق هادئ اليوم...";

  if (state.game_over) {
    nextDayBtn.disabled = true;
    nextDayBtn.textContent = "❌ تم إغلاق المحل (خسرت اللعبة)";
    nextDayBtn.style.background = "#c0392b";
  }

  marketList.innerHTML = "";
  Object.entries(state.market).forEach(([key, good]) => {
    const owned = state.inventory[key] || 0;
    const isSpecialized = (state.specializations || []).includes(key);
    const tradeVol = (state.trade_volume || {})[key] || 0;
    
    const card = document.createElement("div");
    card.className = `good-card ${owned >= 30 ? 'monopolized' : ''}`;
    
    let specBadge = isSpecialized ? `<span class="specialized-badge">★ متخصص (خصم/بونص 10%)</span>` : '';
    let monopolyBtn = owned >= 30 ? `<button class="mini-btn monopoly" data-good="${key}">😈 احتكار السوق (رفع السعر +25%)</button>` : '';

    card.innerHTML = `
      <div class="good-top">
        <span class="good-name">${good.name} ${specBadge}</span>
        <span class="good-price">${good.current_price} ج / وحدة</span>
      </div>
      <div class="good-owned">
        عندك منها: ${owned} وحدة
        ${!isSpecialized ? `<div class="trade-progress">التداول للتخصص: ${tradeVol}/50</div>` : ''}
      </div>
      <div class="good-controls">
        <input type="number" min="1" value="1" id="qty-${key}">
        <button class="mini-btn buy" data-good="${key}" data-action="buy">شراء</button>
        <button class="mini-btn sell" data-good="${key}" data-action="sell">بيع</button>
      </div>
      ${monopolyBtn}
    `;
    marketList.appendChild(card);
  });

  const invEntries = Object.entries(state.inventory).filter(([, qty]) => qty > 0);
  if (invEntries.length === 0) {
    inventoryList.innerHTML = `<p class="empty">المخزن فاضي لسه</p>`;
  } else {
    inventoryList.innerHTML = invEntries
      .map(([key, qty]) => {
        const isMono = qty >= 30 ? ' (🔥 مخزون احتكاري)' : '';
        return `<div class="inv-row"><span>${state.market[key].name}${isMono}</span><span>${qty} وحدة</span></div>`;
      })
      .join("");
  }
}

async function loadState() {
  const res = await fetch("/api/state");
  const data = await res.json();
  render(data);
}

marketList.addEventListener("click", async (e) => {
  const buySellBtn = e.target.closest(".mini-btn.buy, .mini-btn.sell");
  const monopolyBtn = e.target.closest(".mini-btn.monopoly");

  if (monopolyBtn) {
    const good = monopolyBtn.dataset.good;
    const res = await fetch("/api/monopolize", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ good }),
    });
    const data = await res.json();
    if (!res.ok) {
      showToast(data.error || "حصل خطأ", "error");
      return;
    }
    showToast("نجحت في احتكار السلعة ورفع سعرها!", "success");
    loadState();
    return;
  }

  if (!buySellBtn) return;

  const good = buySellBtn.dataset.good;
  const action = buySellBtn.dataset.action;
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

  loadState();
});

nextDayBtn.addEventListener("click", async () => {
  const res = await fetch("/api/next_day", { method: "POST" });
  const data = await res.json();

  if (data.game_over) {
    showToast("تم طردك من المحل لعدم دفع الإيجار!", "error");
  } else {
    showToast("يوم جديد بدأ، الأسعار اتحركت شوية", "success");
  }

  loadState();
});

loadState();
