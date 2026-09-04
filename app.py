from flask import Flask, render_template, request, jsonify, session
import os
import random

app = Flask(__name__)
app.secret_key = "souq-el-horra-secret"  # غيّرها لو هتنشر اللعبة فعلياً

# إعدادات دي بتخلي الكوكيز (اللي بتفتكر فلوسك ومخزنك) تشتغل حتى لو اللعبة
# اتفتحت جوه إطار تاني (iframe) زي الـ Webview بتاع Replit.
# بنفعّلها بس لو شغالين فعلاً على Replit (اللي بيوفر https)، عشان
# متبوظش التجربة المحلية عندك على جهازك (اللي بتشتغل بـ http عادي).
if os.environ.get("REPL_ID"):
    app.config.update(
        SESSION_COOKIE_SAMESITE="None",
        SESSION_COOKIE_SECURE=True,
    )

STARTING_CASH = 2000

# ==========================================
# تعريف بضايع السوق
# base_price = السعر "الطبيعي" اللي السعر بيميل يرجعله بمرور الوقت
# current_price = السعر الحالي (ثابت طول اليوم، بيتغير بس عند نهاية اليوم)
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


def fresh_daily_net(market):
    # بيسجل صافي الكمية اللي اتشترت أو اتباعت في اليوم الحالي لكل سلعة
    # (موجب = اتشترى أكتر مما اتباع، سالب = العكس). بيتصفر كل يوم جديد.
    return {key: 0 for key in market}


# كل وحدة "صافية" اتشترت أو اتباعت في اليوم بتأثر في سعر الغد بنسبة 3%
DEMAND_IMPACT_PER_UNIT = 0.03
# أقصى تأثير للطلب في يوم واحد (عشان يوم شراء ضخم ميجيبش السعر لأقصى حد فوراً)
DEMAND_IMPACT_CAP = 0.35
# نسبة رجوع السعر ناحية الطبيعي كل يوم (أضعف من الأول عشان يسيب مجال للعشوائية)
DAILY_REVERSION = 0.05
# نسبة العشوائية اليومية (بقت أوسع بكتير عشان تحس إن السوق حي وغير متوقع)
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
    price = good["current_price"]  # ثابت طول اليوم، مفيش تغيير لحظي
    total_cost = round(price * qty, 2)

    if total_cost > s["cash"]:
        return jsonify({"error": "معاك فلوس مش كفاية"}), 400

    s["cash"] -= total_cost
    s["inventory"][good_key] = s["inventory"].get(good_key, 0) + qty
    s["daily_net"][good_key] = s["daily_net"].get(good_key, 0) + qty  # هيأثر في سعر الغد

    session["cash"] = s["cash"]
    session["inventory"] = s["inventory"]
    session["daily_net"] = s["daily_net"]

    return jsonify({"cash": s["cash"], "market": s["market"], "inventory": s["inventory"], "spent": total_cost})


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
    price = good["current_price"]  # ثابت طول اليوم
    total_revenue = round(price * qty, 2)

    s["cash"] += total_revenue
    s["inventory"][good_key] = owned - qty
    if s["inventory"][good_key] == 0:
        del s["inventory"][good_key]
    s["daily_net"][good_key] = s["daily_net"].get(good_key, 0) - qty  # هيأثر في سعر الغد

    session["cash"] = s["cash"]
    session["inventory"] = s["inventory"]
    session["daily_net"] = s["daily_net"]

    return jsonify({"cash": s["cash"], "market": s["market"], "inventory": s["inventory"], "earned": total_revenue})


@app.route("/api/next_day", methods=["POST"])
def next_day():
    s = get_state()
    s["day"] += 1

    for key, good in s["market"].items():
        base = good["base_price"]
        current = good["current_price"]
        net = s["daily_net"].get(key, 0)

        # 1) تأثير الطلب: لو الناس اشترت كتير السعر بيميل يعلى، ولو باعت كتير بيميل ينزل
        demand_pct = clamp(net * DEMAND_IMPACT_PER_UNIT, -DEMAND_IMPACT_CAP, DEMAND_IMPACT_CAP)

        # 2) رجوع خفيف ناحية السعر الطبيعي (عشان السعر مايهربش للأبد من قيمته الحقيقية)
        reversion_pct = (base - current) / base * DAILY_REVERSION

        # 3) عشوائية واسعة تحاكي نشاط تجار تانيين وتقلبات السوق
        noise_pct = random.uniform(-DAILY_NOISE, DAILY_NOISE)

        new_price = current * (1 + demand_pct + reversion_pct + noise_pct)
        good["current_price"] = round(clamp(new_price, good["min"], good["max"]), 2)

    s["daily_net"] = fresh_daily_net(s["market"])

    session["day"] = s["day"]
    session["market"] = s["market"]
    session["daily_net"] = s["daily_net"]

    return jsonify({"day": s["day"], "market": s["market"]})


@app.route("/api/reset", methods=["POST"])
def reset():
    session.clear()
    get_state()
    return jsonify({"ok": True})


if __name__ == "__main__":
    # على Replit لازم نسمع على 0.0.0.0 وبورت 8080 عشان يقدر يوصلّك
    port = int(os.environ.get("PORT", 8080 if os.environ.get("REPL_ID") else 5000))
    app.run(host="0.0.0.0", port=port, debug=not os.environ.get("REPL_ID"))
