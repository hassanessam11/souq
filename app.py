from flask import Flask, render_template, request, jsonify, session
import random

app = Flask(__name__)
app.secret_key = "souq-el-horra-secret"  # غيّرها لو هتنشر اللعبة فعلياً

STARTING_CASH = 2000

# ==========================================
# تعريف بضايع السوق
# base_price = السعر "الطبيعي" اللي السعر بيميل يرجعله بمرور الوقت
# current_price = السعر الحالي (بيتغير حسب البيع والشراء)
# min_price/max_price = حدود عشان السعر ميجيش سالب أو يجنن
# ==========================================
def fresh_market():
    return {
        "قماش": {"name": "قماش", "base_price": 50, "current_price": 50, "min": 15, "max": 150},
        "نحاسيات": {"name": "أواني نحاسية", "base_price": 120, "current_price": 120, "min": 40, "max": 350},
        "سجاد": {"name": "سجاد قديم", "base_price": 300, "current_price": 300, "min": 100, "max": 900},
        "كتب": {"name": "كتب ومخطوطات", "base_price": 80, "current_price": 80, "min": 20, "max": 250},
        "تحف": {"name": "تحف وأنتيكات", "base_price": 500, "current_price": 500, "min": 150, "max": 1500},
    }


# نسبة تغيّر السعر لكل وحدة بتتباع أو بتتشترى (2%)
PRICE_IMPACT_PER_UNIT = 0.02
# نسبة رجوع السعر ناحية الطبيعي كل يوم (10%)
DAILY_REVERSION = 0.10
# نسبة العشوائية اليومية (+-5%)
DAILY_NOISE = 0.05


def clamp(value, lo, hi):
    return max(lo, min(hi, value))


def get_state():
    if "cash" not in session:
        session["cash"] = STARTING_CASH
        session["day"] = 1
        session["inventory"] = {}
        session["market"] = fresh_market()
    return session


@app.route("/")
def index():
    get_state()
    return render_template("index.html")


@app.route("/api/state")
def state():
    s = get_state()
    return jsonify({
        "cash": s["cash"],
        "day": s["day"],
        "inventory": s["inventory"],
        "market": s["market"],
    })


@app.route("/api/buy", methods=["POST"])
def buy():
    s = get_state()
    data = request.get_json()
    good_key = data.get("good")
    qty = int(data.get("qty", 0))

    if good_key not in s["market"] or qty <= 0:
        return jsonify({"error": "طلب غير صالح"}), 400

    good = s["market"][good_key]
    price = good["current_price"]
    total_cost = 0
    # كل وحدة بتتشترى بتغلّي اللي بعدها شوية (تأثير فوري داخل نفس عملية الشراء)
    for _ in range(qty):
        total_cost += price
        price = clamp(price * (1 + PRICE_IMPACT_PER_UNIT), good["min"], good["max"])

    if total_cost > s["cash"]:
        return jsonify({"error": "معاك فلوس مش كفاية"}), 400

    s["cash"] -= total_cost
    good["current_price"] = round(price, 2)
    s["inventory"][good_key] = s["inventory"].get(good_key, 0) + qty

    session["cash"] = s["cash"]
    session["market"] = s["market"]
    session["inventory"] = s["inventory"]

    return jsonify({"cash": s["cash"], "market": s["market"], "inventory": s["inventory"], "spent": round(total_cost, 2)})


@app.route("/api/sell", methods=["POST"])
def sell():
    s = get_state()
    data = request.get_json()
    good_key = data.get("good")
    qty = int(data.get("qty", 0))

    owned = s["inventory"].get(good_key, 0)
    if good_key not in s["market"] or qty <= 0 or qty > owned:
        return jsonify({"error": "طلب غير صالح"}), 400

    good = s["market"][good_key]
    price = good["current_price"]
    total_revenue = 0
    for _ in range(qty):
        total_revenue += price
        price = clamp(price * (1 - PRICE_IMPACT_PER_UNIT), good["min"], good["max"])

    s["cash"] += total_revenue
    good["current_price"] = round(price, 2)
    s["inventory"][good_key] = owned - qty
    if s["inventory"][good_key] == 0:
        del s["inventory"][good_key]

    session["cash"] = s["cash"]
    session["market"] = s["market"]
    session["inventory"] = s["inventory"]

    return jsonify({"cash": s["cash"], "market": s["market"], "inventory": s["inventory"], "earned": round(total_revenue, 2)})


@app.route("/api/next_day", methods=["POST"])
def next_day():
    s = get_state()
    s["day"] += 1

    for good in s["market"].values():
        base = good["base_price"]
        current = good["current_price"]
        # رجوع تدريجي ناحية السعر الطبيعي
        reverted = current + (base - current) * DAILY_REVERSION
        # عشوائية بسيطة تحاكي نشاط تجار تانيين
        noise = reverted * random.uniform(-DAILY_NOISE, DAILY_NOISE)
        good["current_price"] = round(clamp(reverted + noise, good["min"], good["max"]), 2)

    session["day"] = s["day"]
    session["market"] = s["market"]

    return jsonify({"day": s["day"], "market": s["market"]})


@app.route("/api/reset", methods=["POST"])
def reset():
    session.clear()
    get_state()
    return jsonify({"ok": True})


if __name__ == "__main__":
    app.run(debug=True)
