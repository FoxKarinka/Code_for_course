import os
import sqlite3
import uuid
from collections import Counter
from contextlib import contextmanager
from itertools import combinations
from math import ceil
from pathlib import Path

from flask import Flask, abort, redirect, render_template_string, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "demo-only-change-me")
app.config["MAX_CONTENT_LENGTH"] = 8 * 1024 * 1024
BASE = Path(__file__).parent
DB = BASE / "shop.db"
UPLOADS = BASE / "static" / "uploads"

PAGE = """
<!doctype html><html lang="uk"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Метал у роботі</title><style>
body{margin:0;background:#f6f5f0;color:#282d28;font:15px Arial,sans-serif}
header,main{max-width:1120px;margin:auto;padding:22px}
header{display:flex;justify-content:space-between;border-bottom:1px solid #ddd}
a{color:#315a46;text-decoration:none}h1{font-size:48px;margin:32px 0 8px}h2{margin-top:42px}
.grid{display:grid;grid-template-columns:repeat(4,1fr);gap:18px}.card{background:white;padding:10px}
.card img{width:100%;height:250px;object-fit:cover;background:#e8e7df}.price{font-weight:bold}
button{background:#315a46;color:white;border:0;padding:10px 14px;cursor:pointer}
input,textarea{padding:10px;border:1px solid #ccc;max-width:100%}form{margin:8px 0}
.form{margin:32px 0;background:#eeeee7;padding:18px}.form input{margin:5px}
.note{color:#777;font-size:13px}.recommend{background:#fffefa;padding:16px;margin:22px 0}
.recommend-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:12px}
.recommend-item{display:flex;gap:12px;align-items:flex-start;padding:12px;background:#f6f5f0}
.recommend-item img{width:76px;height:76px;object-fit:cover;background:#e8e7df}
.recommend-item p{margin:5px 0}.product-detail{max-width:760px;margin:30px auto;background:#fffefa;padding:24px}
.product-detail img{width:min(100%,520px);max-height:420px;object-fit:contain;background:#f6f5f0}
.cart-item{display:flex;justify-content:space-between;border-bottom:1px solid #ddd;padding:12px}
.overlay{position:fixed;inset:0;display:grid;place-items:center;background:#0008;z-index:5}
.popup{max-width:420px;margin:20px;padding:28px;background:#fffefa;text-align:center;box-shadow:0 12px 50px #0003}
.popup a{display:inline-block;margin:8px;padding:12px 16px;background:#315a46;color:white}
.auth{max-width:480px;margin:45px auto;background:#fffefa;padding:25px}.auth input{display:block;width:100%;margin:10px 0}
.user{display:flex;gap:12px;align-items:center}.user button{padding:7px}
@media(max-width:750px){.grid{grid-template-columns:repeat(2,1fr)}.card img{height:210px}h1{font-size:38px}}
</style><header><a href="/"><b>Кошик з брухтом</b></a><nav><a href="/cart">Кошик · {{ count }}</a>
{% if current_user %}<span class="user">{{ current_user.username }} · {{ "продавець" if current_user.role=="seller" else "покупець" }}
<form action="/logout" method="post"><button>Вийти</button></form></span>
{% else %}<a href="/login">Увійти</a> · <a href="/register">Реєстрація</a>{% endif %}</nav></header><main>
{% if auth_page %}<section class="auth"><h2>{{ "Увійти" if auth_page=="login" else "Реєстрація" }}</h2>
{% if error %}<p style="color:#a33">{{ error }}</p>{% endif %}
<form method="post" action="/{{ auth_page }}"><input name="username" placeholder="Ім’я користувача" required minlength="3" maxlength="40" autocomplete="username">
<input name="password" type="password" placeholder="Пароль (від 8 символів)" required minlength="8" autocomplete="{{ 'current-password' if auth_page=='login' else 'new-password' }}">
<button>{{ "Увійти" if auth_page=="login" else "Створити акаунт покупця" }}</button></form>
<p class="note">{% if auth_page=="login" %}Ще немає акаунта? <a href="/register">Зареєструйтесь</a>{% else %}Вже є акаунт? <a href="/login">Увійдіть</a>{% endif %}</p></section>
{% elif cart_page %}
<h1>Ваш кошик</h1>
{% for p,n in items %}<div class="cart-item"><span>{{ p.name }} × {{ n }}</span><b>{{ p.price*n }} ₿</b></div>{% endfor %}
<h3>Разом: {{ total }} ₿</h3>
{% if items %}<form action="/checkout" method="post"><label>Спосіб оплати
<select name="payment"><option value="тілом">Оплатити частиною тіла</option><option value="спогадом">Оплатити спогадом</option><option value="грошима">Оплатити грошима</option></select></label>
<p class="note">Дякую, що обрали нас!</p><button>Підтвердити замовлення</button></form>{% else %}<p>Кошик поки порожній.</p>{% endif %}
{% elif product_page %}
<section class="product-detail">
<p><a href="/">← До каталогу</a></p>
{% if product.image %}<img src="{{ url_for('static',filename='uploads/'+product.image) }}" alt="{{ product.name }}">{% endif %}
<p class="note">{{ product.category }}</p><h1>{{ product.name }}</h1><p class="price">{{ product.price }} ₿</p>
<h2>Опис</h2><p>{{ product.description or "Опис товару поки не додано." }}</p>
{% if product.tags %}<p class="note">Теги: {{ product.tags }}</p>{% endif %}
<form action="/add/{{ product.id }}" method="post"><button>＋ До кошика</button></form>
</section>
{% else %}
<p class="note">МАЛЕНЬКИЙ МАГАЗИН З МАЛЕНЬКИМИ ЦІНАМИ</p><h1>Послуги, які знаходять своїх.</h1>
<p>{% if current_user and current_user.role=="seller" %}Додавайте власні товари й обирайте для них фото.{% else %}Знаходьте послуги до душі та отримуйте рекомендації.{% endif %}</p>
{% if recs %}<section class="recommend"><h2>Рекомендації для вас</h2>
<p class="note">Підбір поєднує історію покупок, перегляди та схожість товарів.</p>
<div class="recommend-grid">{% for rec in recs %}<article class="recommend-item">
{% if rec.product.image %}<a href="/view/{{ rec.product.id }}"><img src="{{ url_for('static',filename='uploads/'+rec.product.image) }}" alt="{{ rec.product.name }}"></a>{% endif %}
<div><small>{{ rec.reason }}</small><br><a href="/view/{{ rec.product.id }}"><b>{{ rec.product.name }}</b></a>
<p>{{ rec.product.price }} ₿</p><form action="/add/{{ rec.product.id }}" method="post"><button>＋ До кошика</button></form></div>
</article>{% endfor %}</div></section>{% endif %}
<h2>Усі товари</h2><section class="grid">{% for p in products %}<article class="card">
<a href="/view/{{ p.id }}">{% if p.image %}<img src="{{ url_for('static',filename='uploads/'+p.image) }}" alt="{{ p.name }}">{% else %}<div style="height:230px;background:#e8e7df"></div>{% endif %}</a>
<p class="note">{{ p.category }}</p><a href="/view/{{ p.id }}"><b>{{ p.name }}</b></a><p class="price">{{ p.price }} ₿</p>
<form action="/add/{{ p.id }}" method="post"><button>＋ До кошика</button></form>
{% if current_user and current_user.role=="seller" %}<form action="/delete/{{ p.id }}" method="post"><button>Видалити</button></form>{% endif %}</article>{% else %}<p>Поки що товарів немає.</p>{% endfor %}</section>
{% if auth_prompt %}<div class="overlay"><section class="popup" role="dialog" aria-modal="true" aria-labelledby="guest-title">
<h2 id="guest-title">Потрібен акаунт</h2><p>Гості не можуть додавати товари в кошик. Увійдіть або зареєструйтесь, щоб продовжити.</p>
<a href="/register">Зареєструватися</a><a href="/login">Увійти</a><p><a href="/" style="background:none;color:#315a46">Продовжити як гість</a></p></section></div>{% endif %}
{% if current_user and current_user.role=="seller" %}
<details class="form"><summary><b>＋ Додати товар</b></summary><form action="/add-product" method="post" enctype="multipart/form-data">
<p><input name="name" placeholder="Назва" required><input name="price" type="number" min="0" step=".01" placeholder="Ціна, ₿" required></p>
<p><input name="category" placeholder="Категорія" required><input name="tags" placeholder="Теги через кому"></p>
<p><textarea name="description" placeholder="Опис"></textarea></p><p><input name="image" type="file" accept="image/*"></p>
<button>Зберегти товар</button></form></details>
{% endif %}
{% endif %}</main></html>
"""

@contextmanager
def connect():
    db = sqlite3.connect(DB)
    db.row_factory = sqlite3.Row
    db.execute("""CREATE TABLE IF NOT EXISTS products
        (id INTEGER PRIMARY KEY, name TEXT, price REAL, category TEXT,
         tags TEXT, description TEXT, image TEXT)""")
    db.execute("""CREATE TABLE IF NOT EXISTS purchases
        (order_id TEXT, product_id INTEGER)""")
    db.execute("CREATE TABLE IF NOT EXISTS orders (order_id TEXT PRIMARY KEY, payment TEXT)")
    db.execute("""CREATE TABLE IF NOT EXISTS users
        (id INTEGER PRIMARY KEY, username TEXT UNIQUE COLLATE NOCASE,
         password_hash TEXT NOT NULL, role TEXT NOT NULL DEFAULT 'customer')""")
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def page(cart_page=False, items=(), total=0, products=(), recs=(),
         product_page=False, product=None):
    return render_template_string(
        PAGE, cart_page=cart_page, items=items, total=total, products=products,
        recs=recs, count=sum(session.get("cart", {}).values()),
        current_user=current_user(), auth_prompt=session.pop("auth_prompt", False),
        auth_page=None, error=None, product_page=product_page, product=product
    )


def render_auth(mode, error=None):
    return render_template_string(
        PAGE, cart_page=False, items=(), total=0, products=(), recs=(),
        count=sum(session.get("cart", {}).values()), current_user=current_user(),
        auth_prompt=False, auth_page=mode, error=error, product_page=False, product=None
    )


def current_user():
    user_id = session.get("user_id")
    if not user_id:
        return None
    with connect() as db:
        return db.execute("SELECT id,username,role FROM users WHERE id=?", (user_id,)).fetchone()


def seller_required():
    user = current_user()
    if not user or user["role"] != "seller":
        abort(403, "Додавати товари може лише продавець.")


def ensure_seller():
    username = os.environ.get("SELLER_USERNAME", "").strip()
    password = os.environ.get("SELLER_PASSWORD", "")
    if not username or not password:
        return
    with connect() as db:
        exists = db.execute("SELECT id FROM users WHERE username=?", (username,)).fetchone()
        if not exists:
            db.execute(
                "INSERT INTO users(username,password_hash,role) VALUES(?,?,?)",
                (username, generate_password_hash(password), "seller"),
            )


@app.before_request
def initialize_seller():
    ensure_seller()


def apriori_pair_rules(transactions, min_support=0.06, min_confidence=0.1):
    baskets = [set(transaction) for transaction in transactions if transaction]
    if not baskets:
        return []

    transaction_count = len(baskets)
    item_counts = Counter(item for basket in baskets for item in basket)
    min_count = max(1, ceil(min_support * transaction_count))
    frequent_items = sorted(item for item, count in item_counts.items() if count >= min_count)
    rules = []

    for item_a, item_b in combinations(frequent_items, 2):
        pair_count = sum(item_a in basket and item_b in basket for basket in baskets)
        if pair_count < min_count:
            continue

        support = pair_count / transaction_count
        for antecedent, consequent in ((item_a, item_b), (item_b, item_a)):
            confidence = pair_count / item_counts[antecedent]
            consequent_support = item_counts[consequent] / transaction_count
            lift = confidence / consequent_support
            if confidence >= min_confidence and lift > 1:
                rules.append({
                    "antecedent": antecedent,
                    "consequent": consequent,
                    "support": support,
                    "confidence": confidence,
                    "lift": lift,
                })

    return rules


def build_recommendations(products, transactions, viewed=(), limit=8):
    catalog = {product["id"]: product for product in products}
    baskets = [set(transaction) for transaction in transactions if transaction]
    if not catalog or limit <= 0:
        return []

    viewed_ids = set(viewed)
    history = [catalog[item_id] for item_id in viewed if item_id in catalog]
    anchor = history[-1] if history else None
    item_orders = Counter(item for basket in baskets for item in basket)
    rule_by_product = {}
    if anchor:
        for rule in apriori_pair_rules(baskets):
            if rule["antecedent"] != anchor["id"]:
                continue
            previous = rule_by_product.get(rule["consequent"])
            if previous is None or (
                rule["support"], rule["confidence"], rule["lift"]
            ) > (previous["support"], previous["confidence"], previous["lift"]):
                rule_by_product[rule["consequent"]] = rule

    history_categories = Counter(item["category"] for item in history)
    history_tags = Counter(
        tag.strip().casefold()
        for item in history
        for tag in (item["tags"] or "").split(",")
        if tag.strip()
    )
    scored = []
    transaction_count = len(baskets)
    for product in catalog.values():
        product_id = product["id"]
        if product_id in viewed_ids:
            continue

        score = 0.0
        reasons = []
        rule = rule_by_product.get(product_id)
        if rule:
            score += (
                2 * rule["confidence"]
                + rule["support"]
                + 0.1 * min(rule["lift"], 4)
            )
            reasons.append("Купують разом")

        category_matches = history_categories[product["category"]]
        tags = {
            tag.strip().casefold()
            for tag in (product["tags"] or "").split(",")
            if tag.strip()
        }
        tag_matches = sum(history_tags[tag] for tag in tags)
        if category_matches or tag_matches:
            score += 0.35 * category_matches + 0.05 * tag_matches
            reasons.append("Схожий товар")

        popularity = item_orders[product_id] / transaction_count if transaction_count else 0
        score += 0.2 * popularity
        if popularity and not reasons:
            reasons.append("Популярне")
        if not reasons:
            reasons.append("Може зацікавити")

        scored.append({
            "product": product,
            "reason": " · ".join(reasons),
            "score": score,
            "orders": item_orders[product_id],
        })

    return sorted(
        scored,
        key=lambda rec: (rec["score"], rec["orders"], rec["product"]["id"]),
        reverse=True,
    )[:limit]


@app.get("/")
def home():
    with connect() as db:
        products = db.execute("SELECT * FROM products ORDER BY id DESC").fetchall()
        transactions = {}
        for order_id, product_id in db.execute(
            "SELECT order_id,product_id FROM purchases"
        ):
            transactions.setdefault(order_id, set()).add(product_id)
        recs = build_recommendations(
            products, transactions.values(), session.get("viewed", ())
        )
    return page(products=products, recs=recs)


@app.post("/add-product")
def add_product():
    seller_required()
    name = request.form.get("name", "").strip()
    category = request.form.get("category", "").strip()
    try:
        price = float(request.form["price"])
        if not name or not category or price < 0:
            raise ValueError
    except (ValueError, KeyError):
        abort(400, "Перевірте назву, категорію та ціну.")
    image = request.files.get("image")
    filename = ""
    if image and image.filename:
        extension = Path(image.filename).suffix.lower()
        if extension not in {".jpg", ".jpeg", ".png", ".webp", ".gif"}:
            abort(400, "Оберіть файл зображення.")
        filename = f"{uuid.uuid4().hex}{extension}"
        UPLOADS.mkdir(parents=True, exist_ok=True)
        image.save(UPLOADS / filename)
    with connect() as db:
        db.execute("INSERT INTO products(name,price,category,tags,description,image) VALUES(?,?,?,?,?,?)",
                   (name, price, category, request.form.get("tags", ""), request.form.get("description", ""), filename))
    return redirect(url_for("home"))


@app.post("/add/<int:product_id>")
def add_to_cart(product_id):
    with connect() as db:
        if not db.execute("SELECT id FROM products WHERE id=?", (product_id,)).fetchone():
            abort(404)
    if not current_user():
        session["pending_product"] = product_id
        session["auth_prompt"] = True
        return redirect(url_for("home"))
    cart = session.get("cart", {})
    key = str(product_id)
    cart[key] = cart.get(key, 0) + 1
    session["cart"] = cart
    return redirect(url_for("home"))


@app.get("/cart")
def show_cart():
    cart = session.get("cart", {})
    with connect() as db:
        items = [(p, cart[str(p["id"])]) for p in db.execute(
            f"SELECT * FROM products WHERE id IN ({','.join('?' for _ in cart) or 'NULL'})",
            list(map(int, cart)))]
    return page(cart_page=True, items=items, total=sum(p["price"] * n for p, n in items))


@app.post("/checkout")
def checkout():
    if not current_user():
        session["auth_prompt"] = True
        return redirect(url_for("home"))
    cart = session.get("cart", {})
    payment = request.form.get("payment")
    if payment not in {"тілом", "спогадом", "грошима"}:
        abort(400, "Оберіть один із доступних способів оплати.")
    if not cart:
        return redirect(url_for("show_cart"))
    order_id = uuid.uuid4().hex
    with connect() as db:
        db.execute("INSERT INTO orders VALUES(?,?)", (order_id, payment))
        existing = {str(row["id"]) for row in db.execute(
            f"SELECT id FROM products WHERE id IN ({','.join('?' for _ in cart)})",
            list(map(int, cart)),
        )}
        for product_id, quantity in cart.items():
            if product_id not in existing:
                continue
            for _ in range(quantity):
                db.execute("INSERT INTO purchases VALUES(?,?)", (order_id, int(product_id)))
    session["cart"] = {}
    return f"<h1>Замовлення оформлено!</h1><p>Спосіб: {payment}.</p><a href='/'>Повернутися до магазину</a>"


@app.get("/view/<int:product_id>")
def view_product(product_id):
    with connect() as db:
        product = db.execute(
            "SELECT * FROM products WHERE id=?", (product_id,)
        ).fetchone()
    if not product:
        abort(404)
    viewed = session.get("viewed", [])
    session["viewed"] = (viewed + [product_id])[-20:]
    return page(product_page=True, product=product)


@app.post("/delete/<int:product_id>")
def delete_product(product_id):
    seller_required()
    with connect() as db:
        db.execute("DELETE FROM products WHERE id=?", (product_id,))
        db.execute("DELETE FROM purchases WHERE product_id=?", (product_id,))
    return redirect(url_for("home"))


def finish_login(user):
    pending = session.get("pending_product")
    session.clear()
    session["user_id"] = user["id"]
    if pending:
        with connect() as db:
            exists = db.execute("SELECT id FROM products WHERE id=?", (pending,)).fetchone()
        if exists:
            session["cart"] = {str(pending): 1}
    return redirect(url_for("show_cart" if pending else "home"))


@app.route("/register", methods=["GET", "POST"])
def register():
    if current_user():
        return redirect(url_for("home"))
    if request.method == "GET":
        return render_auth("register")
    username = request.form.get("username", "").strip()
    password = request.form.get("password", "")
    if len(username) < 3 or len(username) > 40 or len(password) < 8:
        return render_auth("register", "Ім’я має містити 3–40 символів, пароль — щонайменше 8.")
    try:
        with connect() as db:
            cursor = db.execute(
                "INSERT INTO users(username,password_hash,role) VALUES(?,?,?)",
                (username, generate_password_hash(password), "customer"),
            )
            user = db.execute(
                "SELECT id,username,role FROM users WHERE id=?", (cursor.lastrowid,)
            ).fetchone()
    except sqlite3.IntegrityError:
        return render_auth("register", "Таке ім’я вже зайняте.")
    return finish_login(user)


@app.route("/login", methods=["GET", "POST"])
def login():
    if current_user():
        return redirect(url_for("home"))
    if request.method == "GET":
        return render_auth("login")
    username = request.form.get("username", "").strip()
    with connect() as db:
        user = db.execute("SELECT * FROM users WHERE username=?", (username,)).fetchone()
    if not user or not check_password_hash(user["password_hash"], request.form.get("password", "")):
        return render_auth("login", "Неправильне ім’я користувача або пароль.")
    return finish_login(user)


@app.post("/logout")
def logout():
    session.clear()
    return redirect(url_for("home"))


if __name__ == "__main__":
    app.run()
