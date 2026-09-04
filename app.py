from flask import Flask, render_template, request, jsonify, session
import os
import random

app = Flask(__name__)
app.secret_key = "souq-el-horra-secret"

if os.environ.get("REPL_ID"):
    app.config.update(
        SESSION_COOKIE_SAMESITE="None",
        SESSION_COOKIE_SECURE=True,
    )

STARTING_CASH = 2000
RENT_AMOUNT = 300
RENT_CYCLE_DAYS = 7
SPECIALIZATION_THRESHOLD = 50  # إجمالي المعاملات لفتح التخصص
MONOPOLY_THRESHOLD = 30        # عدد الوحدات بالمخزن لتفعيل الاحتكار

def fresh_market():
    return {
        "قماش": {"name": "قماش", "base_price": 50, "current_price": 50, "min": 15, "max": 150},
        "نحاسيات": {"name": "أواني نحاسية", "base_price": 120, "current_price": 120, "min": 40, "max": 350},
        "سجاد": {"name": "سجاد قديم", "base_price": 300, "current_price": 300, "min": 100, "max": 900},
        "كتب": {"name": "كتب ومخطوطات", "base_price": 80, "current_price": 80, "min": 20, "max": 250},
        "تحف": {"name": "تحف وأنتيكات", "base_price": 500, "current_price": 500, "min": 150, "max": 1500},
    }

def fresh_daily_net(market):
    return {key: 0 for key in market}

DEMAND_IMPACT_PER_UNIT = 0.03
DEMAND_IMPACT_CAP = 0.35
DAILY_REVERSION = 0.05
DAILY_NOISE = 0.14

def clamp(value, lo, hi):
    return max(lo, min(hi, value))

def get_state():
    if "cash" not in session:
        session["cash"] = STARTING_CASH
        session["day"] = 1
        session["inventory"] = {}
        session["market"] = fresh_market()
        session["daily_net"] = fresh_daily_net(session["market"])
        session["trade_volume"] = {k: 0 for k in session["market"]} # إجمالي التداول للتخصص
        session["specializations"] = []                           # التخصصات المفتوحة
        session["news"] = "أهلاً بك في دكانك الجديد! استعد لجمع المال ودفع الإيجار."
        session["game_over"] = False
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
        "trade_volume": s.get("trade_volume", {}),
        "specializations": s.get("specializations", []),
        "news": s.get("news", ""),
        "game_over": s.get("game_over", False),
        "rent_amount": RENT_AMOUNT,
        "rent_cycle": RENT_CYCLE_DAYS,
        "days_to_rent": RENT_CYCLE_DAYS - ((s["day"] - 1) % RENT_CYCLE_DAYS)
    })

@app.route("/api/buy", methods=["POST"])
def buy():
    s = get_state()
    if s.get("game_over"):
        return jsonify({"error": "اللعبة انتهت!"}), 400

    data = request.get_json()
    good_key = data.get("good")
    qty = int(data.get("qty", 0))

    if good_key not in s["market"] or qty <= 0:
        return jsonify({"error": "طلب غير صالح"}), 400

    good = s["market"][good_key]
    unit_price = good["current_price"]
    
    # خصم التخصص 10% عند الشراء
    if good_key in s.get("specializations", []):
        unit_price *= 0.90

    total_cost = round(unit_price * qty, 2)

    if total_cost > s["cash"]:
        return jsonify({"error": "معاك فلوس مش كفاية"}), 400

    s["cash"] -= total_cost
    s["inventory"][good_key] = s["inventory"].get(good_key, 0) + qty
    s["daily_net"][good_key] = s["daily_net"].get(good_key, 0) + qty
    
    # تحديث إجمالي التداول للتخصص
    s["trade_volume"][good_key] = s["trade_volume"].get(good_key, 0) + qty
    if s["trade_volume"][good_key] >= SPECIALIZATION_THRESHOLD and good_key not in s["specializations"]:
        s["specializations"].append(good_key)
        s["news"] = f"مبروك! أصبحت متخصصاً في تجارة ({good['name']}) وصار لك خصم 10%!"

    session["cash"] = s["cash"]
    session["inventory"] = s["inventory"]
    session["daily_net"] = s["daily_net"]
    session["trade_volume"] = s["trade_volume"]
    session["specializations"] = s["specializations"]

    return jsonify({
        "cash": s["cash"], 
        "market": s["market"], 
        "inventory": s["inventory"], 
        "spent": total_cost,
        "specializations": s["specializations"],
        "trade_volume": s["trade_volume"]
    })

@app.route("/api/sell", methods=["POST"])
def sell():
    s = get_state()
    if s.get("game_over"):
        return jsonify({"error": "اللعبة انتهت!"}), 400

    data = request.get_json()
    good_key = data.get("good")
    qty = int(data.get("qty", 0))

    owned = s["inventory"].get(good_key, 0)
    if good_key not in s["market"] or qty <= 0 or qty > owned:
        return jsonify({"error": "طلب غير صالح"}), 400

    good = s["market"][good_key]
    unit_price = good["current_price"]
    
    # بونص التخصص 10% زيادة عند البيع
    if good_key in s.get("specializations", []):
        unit_price *= 1.10

    total_revenue = round(unit_price * qty, 2)

    s["cash"] += total_revenue
    s["inventory"][good_key] = owned - qty
    if s["inventory"][good_key] == 0:
        del s["inventory"][good_key]
    s["daily_net"][good_key] = s["daily_net"].get(good_key, 0) - qty

    s["trade_volume"][good_key] = s["trade_volume"].get(good_key, 0) + qty
    if s["trade_volume"][good_key] >= SPECIALIZATION_THRESHOLD and good_key not in s["specializations"]:
        s["specializations"].append(good_key)
        s["news"] = f"مبروك! أصبحت متخصصاً في تجارة ({good['name']}) وصار لك زيادة 10% في أرباح بيعها!"

    session["cash"] = s["cash"]
    session["inventory"] = s["inventory"]
    session["daily_net"] = s["daily_net"]
    session["trade_volume"] = s["trade_volume"]
    session["specializations"] = s["specializations"]

    return jsonify({
        "cash": s["cash"], 
        "market": s["market"], 
        "inventory": s["inventory"], 
        "earned": total_revenue,
        "specializations": s["specializations"],
        "trade_volume": s["trade_volume"]
    })

@app.route("/api/monopolize", methods=["POST"])
def monopolize():
    """رفع سعر سلعة محتكرة بنسبة 25%"""
    s = get_state()
    data = request.get_json()
    good_key = data.get("good")

    owned = s["inventory"].get(good_key, 0)
    if owned < MONOPOLY_THRESHOLD:
        return jsonify({"error": f"تحتاج لتخزين {MONOPOLY_THRESHOLD} وحدة على الأقل للاحتكار!"}), 400

    good = s["market"][good_key]
    good["current_price"] = round(clamp(good["current_price"] * 1.25, good["min"], good["max"]), 2)
    s["news"] = f"قم بقوة نفوذك الاحتكاري برفع سعر ({good['name']}) في السوق بنسبة 25%!"

    session["market"] = s["market"]
    session["news"] = s["news"]

    return jsonify({"market": s["market"], "news": s["news"]})

@app.route("/api/next_day", methods=["POST"])
def next_day():
    s = get_state()
    if s.get("game_over"):
        return jsonify({"error": "اللعبة انتهت!"}), 400

    s["day"] += 1

    # 1. التحقق من الإيجار كل 7 أيام
    if (s["day"] - 1) % RENT_CYCLE_DAYS == 0 and s["day"] > 1:
        if s["cash"] >= RENT_AMOUNT:
            s["cash"] -= RENT_AMOUNT
            s["news"] = f"تم دفع إيجار المحل ({RENT_AMOUNT} جنيه) بنجاح."
        else:
            s["game_over"] = True
            s["news"] = f"لم تستطع دفع الإيجار ({RENT_AMOUNT} جنيه)! صاحبة المكان طردتك وأغلقت المحل."
            session["game_over"] = True
            session["news"] = s["news"]
            return jsonify({
                "day": s["day"], 
                "market": s["market"], 
                "cash": s["cash"], 
                "game_over": True, 
                "news": s["news"]
            })

    # 2. تحديث أسعار السوق
    event_text = ""
    # حدوث خبر عشوائي ينط السعر بنسبة كبيرة (احتمالية 30%)
    event_good = None
    if random.random() < 0.30:
        event_good = random.choice(list(s["market"].keys()))
        multiplier = random.choice([1.35, 0.65])
        s["market"][event_good]["current_price"] = round(
            clamp(s["market"][event_good]["current_price"] * multiplier, s["market"][event_good]["min"], s["market"][event_good]["max"]), 2
        )
        if multiplier > 1:
            event_text = f" 📰 خبر عاجل: أزمة شحن ترفّع سعر ({s['market'][event_good]['name']})!"
        else:
            event_text = f" 📰 خبر عاجل: إغراق السوق ببضائع تجعل سعر ({s['market'][event_good]['name']}) ينهار!"

    for key, good in s["market"].items():
        if key == event_good:
            continue
        base = good["base_price"]
        current = good["current_price"]
        net = s["daily_net"].get(key, 0)

        demand_pct = clamp(net * DEMAND_IMPACT_PER_UNIT, -DEMAND_IMPACT_CAP, DEMAND_IMPACT_CAP)
        reversion_pct = (base - current) / base * DAILY_REVERSION
        noise_pct = random.uniform(-DAILY_NOISE, DAILY_NOISE)

        new_price = current * (1 + demand_pct + reversion_pct + noise_pct)
        good["current_price"] = round(clamp(new_price, good["min"], good["max"]), 2)

    s["daily_net"] = fresh_daily_net(s["market"])
    if not event_text and not s["news"].startswith("تم دفع"):
        s["news"] = "يوم جديد في السوق.. الأسعار تغيرت بناءً على العرض والطلب."
    elif event_text:
        s["news"] = event_text

    session["day"] = s["day"]
    session["market"] = s["market"]
    session["daily_net"] = s["daily_net"]
    session["cash"] = s["cash"]
    session["news"] = s["news"]

    days_to_rent = RENT_CYCLE_DAYS - ((s["day"] - 1) % RENT_CYCLE_DAYS)

    return jsonify({
        "day": s["day"], 
        "market": s["market"], 
        "cash": s["cash"], 
        "news": s["news"],
        "game_over": False,
        "days_to_rent": days_to_rent
    })

@app.route("/api/reset", methods=["POST"])
def reset():
    session.clear()
    get_state()
    return jsonify({"ok": True})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080 if os.environ.get("REPL_ID") else 5000))
    app.run(host="0.0.0.0", port=port, debug=not os.environ.get("REPL_ID"))
