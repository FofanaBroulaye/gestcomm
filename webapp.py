from __future__ import annotations

import hashlib
import os
import re
import sqlite3
from datetime import date
from functools import wraps
from pathlib import Path
from typing import Any, Callable

from flask import Flask, flash, g, redirect, render_template, request, session, url_for


APP_DIR = Path(__file__).resolve().parent
DB_PATH = Path(os.getenv("GESTCOM_DB", APP_DIR / "gestcom.db"))
app = Flask(__name__)
app.config["SECRET_KEY"] = os.getenv("GESTCOM_SECRET", "change-this-secret-in-production")


def hash_password(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def get_db() -> sqlite3.Connection:
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


@app.teardown_appcontext
def close_db(_error: BaseException | None = None) -> None:
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db() -> None:
    db = get_db()
    db.executescript(
        """
        CREATE TABLE IF NOT EXISTS clients (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, phone TEXT DEFAULT '', email TEXT DEFAULT '', address TEXT DEFAULT '', created_at TEXT DEFAULT CURRENT_DATE);
        CREATE TABLE IF NOT EXISTS suppliers (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, phone TEXT DEFAULT '', email TEXT DEFAULT '', address TEXT DEFAULT '', created_at TEXT DEFAULT CURRENT_DATE);
        CREATE TABLE IF NOT EXISTS products (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, category TEXT DEFAULT '', price REAL NOT NULL DEFAULT 0, stock INTEGER NOT NULL DEFAULT 0, min_stock INTEGER NOT NULL DEFAULT 5);
        CREATE TABLE IF NOT EXISTS sales (id INTEGER PRIMARY KEY AUTOINCREMENT, client_id INTEGER, product_id INTEGER NOT NULL, quantity INTEGER NOT NULL, total REAL NOT NULL, sold_at TEXT DEFAULT CURRENT_DATE, payment_method TEXT DEFAULT 'Espèces', status TEXT DEFAULT 'Payée', FOREIGN KEY(client_id) REFERENCES clients(id) ON DELETE SET NULL, FOREIGN KEY(product_id) REFERENCES products(id));
        CREATE TABLE IF NOT EXISTS purchases (id INTEGER PRIMARY KEY AUTOINCREMENT, supplier_id INTEGER, product_id INTEGER NOT NULL, quantity INTEGER NOT NULL, unit_cost REAL NOT NULL, total REAL NOT NULL, purchased_at TEXT DEFAULT CURRENT_DATE, FOREIGN KEY(supplier_id) REFERENCES suppliers(id) ON DELETE SET NULL, FOREIGN KEY(product_id) REFERENCES products(id));
        CREATE TABLE IF NOT EXISTS cash_sessions (id INTEGER PRIMARY KEY AUTOINCREMENT, opened_at TEXT NOT NULL, opening_balance REAL NOT NULL DEFAULT 0, closed_at TEXT, closing_balance REAL, status TEXT NOT NULL DEFAULT 'open');
        CREATE TABLE IF NOT EXISTS cash_transactions (id INTEGER PRIMARY KEY AUTOINCREMENT, session_id INTEGER NOT NULL, kind TEXT NOT NULL, label TEXT NOT NULL, amount REAL NOT NULL, payment_method TEXT DEFAULT 'Espèces', reference TEXT DEFAULT '', created_at TEXT DEFAULT CURRENT_TIMESTAMP, FOREIGN KEY(session_id) REFERENCES cash_sessions(id) ON DELETE CASCADE);
        CREATE TABLE IF NOT EXISTS expenses (id INTEGER PRIMARY KEY AUTOINCREMENT, label TEXT NOT NULL, category TEXT DEFAULT '', amount REAL NOT NULL, expense_date TEXT DEFAULT CURRENT_DATE, payment_method TEXT DEFAULT 'Espèces');
        CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT NOT NULL UNIQUE, password_hash TEXT NOT NULL, full_name TEXT NOT NULL, role TEXT NOT NULL DEFAULT 'cashier', active INTEGER NOT NULL DEFAULT 1, created_at TEXT DEFAULT CURRENT_DATE);
        """
    )
    db.execute("INSERT OR IGNORE INTO suppliers(id, name) VALUES (1, 'Fournisseur principal')")
    if db.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 0:
        db.execute("INSERT INTO users(username,password_hash,full_name,role) VALUES (?,?,?,?)", ("admin", hash_password("admin123"), "Administrateur", "admin"))
    db.commit()


@app.before_request
def prepare() -> None:
    init_db()
    g.user = None
    if session.get("user_id"):
        g.user = get_db().execute("SELECT * FROM users WHERE id=? AND active=1", (session["user_id"],)).fetchone()


def login_required(view: Callable[..., Any]) -> Callable[..., Any]:
    @wraps(view)
    def wrapped(*args: Any, **kwargs: Any) -> Any:
        if g.user is None:
            return redirect(url_for("login", next=request.path))
        return view(*args, **kwargs)
    return wrapped


def admin_required(view: Callable[..., Any]) -> Callable[..., Any]:
    @wraps(view)
    def wrapped(*args: Any, **kwargs: Any) -> Any:
        if g.user is None: return redirect(url_for("login"))
        if g.user["role"] != "admin":
            flash("Accès réservé à l'administrateur.", "error")
            return redirect(url_for("dashboard"))
        return view(*args, **kwargs)
    return wrapped


def validate_common(name: str, email: str = "", phone: str = "") -> list[str]:
    errors: list[str] = []
    if not name.strip(): errors.append("Le nom est obligatoire.")
    if email and not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email): errors.append("L'adresse email est invalide.")
    if phone and not re.fullmatch(r"[+\d][\d ()-]{6,20}", phone): errors.append("Le téléphone est invalide.")
    return errors


def number_field(value: str, label: str, integer: bool = False, minimum: float = 0) -> tuple[float | int | None, str | None]:
    try: parsed: float | int = int(value) if integer else float(value.replace(" ", "").replace(",", "."))
    except (TypeError, ValueError): return None, f"{label} doit être numérique."
    if parsed < minimum: return None, f"{label} doit être supérieur ou égal à {minimum}."
    return parsed, None


@app.context_processor
def inject_helpers() -> dict[str, Any]:
    return {"today": date.today().isoformat(), "money": lambda value: f"{float(value or 0):,.0f} FCFA"}


@app.route("/login", methods=["GET", "POST"])
def login() -> str | Any:
    if request.method == "POST":
        user = get_db().execute("SELECT * FROM users WHERE username=? AND password_hash=? AND active=1", (request.form.get("username", "").strip(), hash_password(request.form.get("password", "")))).fetchone()
        if user:
            session.clear(); session["user_id"] = user["id"]
            return redirect(request.args.get("next") or url_for("dashboard"))
        flash("Identifiants invalides ou compte désactivé.", "error")
    return render_template("login.html")


@app.get("/logout")
def logout() -> Any:
    session.clear(); return redirect(url_for("login"))


@app.get("/")
@login_required
def dashboard() -> str:
    db = get_db()
    stats = {"revenue": db.execute("SELECT COALESCE(SUM(total),0) FROM sales WHERE sold_at=CURRENT_DATE").fetchone()[0], "sales": db.execute("SELECT COUNT(*) FROM sales WHERE sold_at=CURRENT_DATE").fetchone()[0], "clients": db.execute("SELECT COUNT(*) FROM clients").fetchone()[0], "alerts": db.execute("SELECT COUNT(*) FROM products WHERE stock<=min_stock").fetchone()[0]}
    recent = db.execute("SELECT s.sold_at, COALESCE(c.name,'Client comptoir') client, p.name product, s.total FROM sales s JOIN products p ON p.id=s.product_id LEFT JOIN clients c ON c.id=s.client_id ORDER BY s.id DESC LIMIT 8").fetchall()
    alerts = db.execute("SELECT * FROM products WHERE stock<=min_stock ORDER BY stock LIMIT 8").fetchall()
    return render_template("dashboard.html", stats=stats, recent=recent, alerts=alerts)


@app.route("/clients", methods=["GET", "POST"])
@login_required
def clients() -> str | Any:
    db = get_db(); edit_id = request.args.get("edit", type=int); row = db.execute("SELECT * FROM clients WHERE id=?", (edit_id,)).fetchone() if edit_id else None
    if request.method == "POST":
        data = [request.form.get(k, "").strip() for k in ("name", "phone", "email", "address")]; errors = validate_common(data[0], data[2], data[1])
        if errors: [flash(error, "error") for error in errors]
        elif edit_id: db.execute("UPDATE clients SET name=?,phone=?,email=?,address=? WHERE id=?", (*data, edit_id)); db.commit(); flash("Client modifié.", "success"); return redirect(url_for("clients"))
        else: db.execute("INSERT INTO clients(name,phone,email,address) VALUES (?,?,?,?)", data); db.commit(); flash("Client ajouté.", "success"); return redirect(url_for("clients"))
    rows = db.execute("SELECT * FROM clients ORDER BY name").fetchall(); return render_template("clients.html", rows=rows, row=row)


@app.post("/clients/<int:item_id>/delete")
@login_required
def delete_client(item_id: int) -> Any:
    get_db().execute("DELETE FROM clients WHERE id=?", (item_id,)); get_db().commit(); flash("Client supprimé.", "success"); return redirect(url_for("clients"))


@app.route("/suppliers", methods=["GET", "POST"])
@login_required
def suppliers() -> str | Any:
    db = get_db(); edit_id = request.args.get("edit", type=int); row = db.execute("SELECT * FROM suppliers WHERE id=?", (edit_id,)).fetchone() if edit_id else None
    if request.method == "POST":
        data = [request.form.get(k, "").strip() for k in ("name", "phone", "email", "address")]; errors = validate_common(data[0], data[2], data[1])
        if errors: [flash(error, "error") for error in errors]
        elif edit_id: db.execute("UPDATE suppliers SET name=?,phone=?,email=?,address=? WHERE id=?", (*data, edit_id)); db.commit(); flash("Fournisseur modifié.", "success"); return redirect(url_for("suppliers"))
        else: db.execute("INSERT INTO suppliers(name,phone,email,address) VALUES (?,?,?,?)", data); db.commit(); flash("Fournisseur ajouté.", "success"); return redirect(url_for("suppliers"))
    rows = db.execute("SELECT * FROM suppliers ORDER BY name").fetchall(); return render_template("suppliers.html", rows=rows, row=row)


@app.post("/suppliers/<int:item_id>/delete")
@login_required
def delete_supplier(item_id: int) -> Any:
    if item_id == 1: flash("Le fournisseur principal ne peut pas être supprimé.", "error")
    else: get_db().execute("DELETE FROM suppliers WHERE id=?", (item_id,)); get_db().commit(); flash("Fournisseur supprimé.", "success")
    return redirect(url_for("suppliers"))


@app.route("/products", methods=["GET", "POST"])
@login_required
def products() -> str | Any:
    db = get_db(); edit_id = request.args.get("edit", type=int); row = db.execute("SELECT * FROM products WHERE id=?", (edit_id,)).fetchone() if edit_id else None
    if request.method == "POST":
        data = [request.form.get(k, "").strip() for k in ("name", "category")]; price, e1 = number_field(request.form.get("price", ""), "Le prix"); stock, e2 = number_field(request.form.get("stock", ""), "Le stock", True); minimum, e3 = number_field(request.form.get("min_stock", ""), "Le seuil", True)
        errors = validate_common(data[0]) + [x for x in (e1, e2, e3) if x]
        if errors: [flash(error, "error") for error in errors]
        elif edit_id: db.execute("UPDATE products SET name=?,category=?,price=?,stock=?,min_stock=? WHERE id=?", (*data, price, stock, minimum, edit_id)); db.commit(); flash("Produit modifié.", "success"); return redirect(url_for("products"))
        else: db.execute("INSERT INTO products(name,category,price,stock,min_stock) VALUES (?,?,?,?,?)", (*data, price, stock, minimum)); db.commit(); flash("Produit ajouté.", "success"); return redirect(url_for("products"))
    rows = db.execute("SELECT * FROM products ORDER BY name").fetchall(); return render_template("products.html", rows=rows, row=row)


@app.post("/products/<int:item_id>/delete")
@login_required
def delete_product(item_id: int) -> Any:
    db = get_db(); used = db.execute("SELECT COUNT(*) FROM sales WHERE product_id=?", (item_id,)).fetchone()[0] + db.execute("SELECT COUNT(*) FROM purchases WHERE product_id=?", (item_id,)).fetchone()[0]
    if used: flash("Ce produit est utilisé dans l'historique et ne peut pas être supprimé.", "error")
    else: db.execute("DELETE FROM products WHERE id=?", (item_id,)); db.commit(); flash("Produit supprimé.", "success")
    return redirect(url_for("products"))


@app.route("/sales/new", methods=["GET", "POST"])
@login_required
def new_sale() -> str | Any:
    db = get_db(); clients_rows = db.execute("SELECT id,name FROM clients ORDER BY name").fetchall(); products_rows = db.execute("SELECT * FROM products WHERE stock>0 ORDER BY name").fetchall()
    if request.method == "POST":
        product_id = request.form.get("product_id", type=int); client_id = request.form.get("client_id", type=int); qty, error = number_field(request.form.get("quantity", ""), "La quantité", True, 1); payment = request.form.get("payment_method", "Espèces"); product = db.execute("SELECT * FROM products WHERE id=?", (product_id,)).fetchone() if product_id else None
        if error: flash(error, "error")
        elif not product: flash("Produit invalide.", "error")
        elif qty > product["stock"]: flash(f"Stock disponible : {product['stock']}.", "error")
        elif payment == "Espèces" and not db.execute("SELECT 1 FROM cash_sessions WHERE status='open'").fetchone(): flash("Ouvrez la caisse avant une vente en espèces.", "error")
        else:
            total = qty * product["price"]; db.execute("INSERT INTO sales(client_id,product_id,quantity,total,payment_method) VALUES (?,?,?,?,?)", (client_id or None, product_id, qty, total, payment)); sale_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]; db.execute("UPDATE products SET stock=stock-? WHERE id=?", (qty, product_id))
            if payment == "Espèces": session_row = db.execute("SELECT id FROM cash_sessions WHERE status='open' ORDER BY id DESC LIMIT 1").fetchone(); db.execute("INSERT INTO cash_transactions(session_id,kind,label,amount,payment_method,reference) VALUES (?,'IN',?,?,?,?)", (session_row["id"], "Vente commerciale", total, payment, f"Vente #{sale_id}"))
            db.commit(); flash("Vente enregistrée.", "success"); return redirect(url_for("sales"))
    return render_template("sale_form.html", clients=clients_rows, products=products_rows)


@app.get("/sales")
@login_required
def sales() -> str:
    rows = get_db().execute("SELECT s.*,COALESCE(c.name,'Client comptoir') client,p.name product FROM sales s JOIN products p ON p.id=s.product_id LEFT JOIN clients c ON c.id=s.client_id ORDER BY s.id DESC").fetchall(); return render_template("sales.html", rows=rows)


@app.post("/sales/<int:item_id>/cancel")
@login_required
def cancel_sale(item_id: int) -> Any:
    db = get_db(); row = db.execute("SELECT product_id,quantity FROM sales WHERE id=?", (item_id,)).fetchone()
    if row: db.execute("UPDATE products SET stock=stock+? WHERE id=?", (row["quantity"], row["product_id"])); db.execute("DELETE FROM cash_transactions WHERE reference=?", (f"Vente #{item_id}",)); db.execute("DELETE FROM sales WHERE id=?", (item_id,)); db.commit(); flash("Vente annulée et stock restauré.", "success")
    return redirect(url_for("sales"))


@app.route("/purchases/new", methods=["GET", "POST"])
@login_required
def new_purchase() -> str | Any:
    db = get_db(); suppliers_rows = db.execute("SELECT id,name FROM suppliers ORDER BY name").fetchall(); products_rows = db.execute("SELECT id,name FROM products ORDER BY name").fetchall()
    if request.method == "POST":
        product_id = request.form.get("product_id", type=int); supplier_id = request.form.get("supplier_id", type=int); qty, e1 = number_field(request.form.get("quantity", ""), "La quantité", True, 1); cost, e2 = number_field(request.form.get("unit_cost", ""), "Le coût", False, 0); errors = [x for x in (e1, e2) if x]
        if errors: [flash(error, "error") for error in errors]
        elif not product_id: flash("Sélectionnez un produit.", "error")
        else: db.execute("INSERT INTO purchases(supplier_id,product_id,quantity,unit_cost,total) VALUES (?,?,?,?,?)", (supplier_id, product_id, qty, cost, qty * cost)); db.execute("UPDATE products SET stock=stock+? WHERE id=?", (qty, product_id)); db.commit(); flash("Achat réceptionné et stock mis à jour.", "success"); return redirect(url_for("purchases"))
    return render_template("purchase_form.html", suppliers=suppliers_rows, products=products_rows)


@app.get("/purchases")
@login_required
def purchases() -> str:
    rows = get_db().execute("SELECT p.*,COALESCE(s.name,'—') supplier,pr.name product FROM purchases p JOIN products pr ON pr.id=p.product_id LEFT JOIN suppliers s ON s.id=p.supplier_id ORDER BY p.id DESC").fetchall(); return render_template("purchases.html", rows=rows)


@app.post("/purchases/<int:item_id>/delete")
@login_required
def delete_purchase(item_id: int) -> Any:
    db = get_db(); row = db.execute("SELECT product_id,quantity FROM purchases WHERE id=?", (item_id,)).fetchone()
    if row: db.execute("UPDATE products SET stock=stock-? WHERE id=?", (row["quantity"], row["product_id"])); db.execute("DELETE FROM purchases WHERE id=?", (item_id,)); db.commit(); flash("Achat supprimé et stock corrigé.", "success")
    return redirect(url_for("purchases"))


@app.route("/cash", methods=["GET", "POST"])
@login_required
def cash() -> str | Any:
    db = get_db(); active = db.execute("SELECT * FROM cash_sessions WHERE status='open' ORDER BY id DESC LIMIT 1").fetchone()
    if request.method == "POST":
        kind = request.form.get("kind", "OUT"); amount, error = number_field(request.form.get("amount", ""), "Le montant", False, 0.01); label = request.form.get("label", "").strip()
        if not active: flash("Ouvrez d'abord la caisse.", "error")
        elif error or not label: flash(error or "Le libellé est obligatoire.", "error")
        else: db.execute("INSERT INTO cash_transactions(session_id,kind,label,amount,payment_method) VALUES (?,?,?,?,?)", (active["id"], kind, label, amount, request.form.get("payment_method", "Espèces"))); db.commit(); flash("Mouvement enregistré.", "success"); return redirect(url_for("cash"))
    balance = float(active["opening_balance"]) if active else 0; transactions = db.execute("SELECT * FROM cash_transactions ORDER BY id DESC LIMIT 50").fetchall(); balance += sum((1 if row["kind"] == "IN" else -1) * row["amount"] for row in transactions if active and row["session_id"] == active["id"])
    return render_template("cash.html", active=active, balance=balance, transactions=transactions)


@app.post("/cash/open")
@login_required
def open_cash() -> Any:
    db = get_db(); amount, error = number_field(request.form.get("opening_balance", ""), "Le fond de caisse", False, 0)
    if db.execute("SELECT 1 FROM cash_sessions WHERE status='open'").fetchone(): flash("Une caisse est déjà ouverte.", "error")
    elif error: flash(error, "error")
    else: db.execute("INSERT INTO cash_sessions(opened_at,opening_balance) VALUES (?,?)", (date.today().isoformat(), amount)); db.commit(); flash("Caisse ouverte.", "success")
    return redirect(url_for("cash"))


@app.post("/cash/close")
@login_required
def close_cash() -> Any:
    db = get_db(); active = db.execute("SELECT * FROM cash_sessions WHERE status='open' LIMIT 1").fetchone()
    if active:
        balance = active["opening_balance"] + db.execute("SELECT COALESCE(SUM(CASE WHEN kind='IN' THEN amount ELSE -amount END),0) FROM cash_transactions WHERE session_id=?", (active["id"],)).fetchone()[0]; db.execute("UPDATE cash_sessions SET status='closed',closed_at=?,closing_balance=? WHERE id=?", (date.today().isoformat(), balance, active["id"])); db.commit(); flash("Caisse clôturée.", "success")
    return redirect(url_for("cash"))


@app.route("/expenses", methods=["GET", "POST"])
@login_required
def expenses() -> str | Any:
    db = get_db(); edit_id = request.args.get("edit", type=int); row = db.execute("SELECT * FROM expenses WHERE id=?", (edit_id,)).fetchone() if edit_id else None
    if request.method == "POST":
        label = request.form.get("label", "").strip(); category = request.form.get("category", "").strip(); amount, error = number_field(request.form.get("amount", ""), "Le montant", False, 0.01)
        if error or not label: flash(error or "Le libellé est obligatoire.", "error")
        elif edit_id: db.execute("UPDATE expenses SET label=?,category=?,amount=? WHERE id=?", (label, category, amount, edit_id)); db.execute("UPDATE cash_transactions SET label=?,amount=? WHERE reference=?", (label, amount, f"Dépense:{edit_id}")); db.commit(); flash("Dépense modifiée.", "success"); return redirect(url_for("expenses"))
        else: db.execute("INSERT INTO expenses(label,category,amount) VALUES (?,?,?)", (label, category, amount)); expense_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]; active = db.execute("SELECT id FROM cash_sessions WHERE status='open' LIMIT 1").fetchone();
        if not edit_id and active: db.execute("INSERT INTO cash_transactions(session_id,kind,label,amount,reference) VALUES (?,'OUT',?,?,?)", (active["id"], label, amount, f"Dépense:{expense_id}")); db.commit(); flash("Dépense ajoutée.", "success"); return redirect(url_for("expenses"))
    rows = db.execute("SELECT * FROM expenses ORDER BY id DESC").fetchall(); return render_template("expenses.html", rows=rows, row=row)


@app.post("/expenses/<int:item_id>/delete")
@login_required
def delete_expense(item_id: int) -> Any:
    db = get_db(); db.execute("DELETE FROM expenses WHERE id=?", (item_id,)); db.execute("DELETE FROM cash_transactions WHERE reference=?", (f"Dépense:{item_id}",)); db.commit(); flash("Dépense supprimée.", "success"); return redirect(url_for("expenses"))


@app.route("/admin/users", methods=["GET", "POST"])
@admin_required
def users() -> str | Any:
    db = get_db(); edit_id = request.args.get("edit", type=int); row = db.execute("SELECT * FROM users WHERE id=?", (edit_id,)).fetchone() if edit_id else None
    if request.method == "POST":
        username = request.form.get("username", "").strip(); full_name = request.form.get("full_name", "").strip(); role = request.form.get("role", "cashier"); password = request.form.get("password", "")
        if not username or not full_name or role not in {"admin", "manager", "cashier", "stock"}: flash("Identifiant, nom et rôle sont obligatoires.", "error")
        elif edit_id: db.execute("UPDATE users SET username=?,full_name=?,role=? WHERE id=?", (username, full_name, role, edit_id)); db.commit(); flash("Utilisateur modifié.", "success"); return redirect(url_for("users"))
        elif len(password) < 6: flash("Le mot de passe doit contenir au moins 6 caractères.", "error")
        else:
            try: db.execute("INSERT INTO users(username,password_hash,full_name,role) VALUES (?,?,?,?)", (username, hash_password(password), full_name, role)); db.commit(); flash("Utilisateur créé.", "success"); return redirect(url_for("users"))
            except sqlite3.IntegrityError: flash("Cet identifiant existe déjà.", "error")
    rows = db.execute("SELECT * FROM users ORDER BY username").fetchall(); return render_template("users.html", rows=rows, row=row)


@app.post("/admin/users/<int:item_id>/toggle")
@admin_required
def toggle_user(item_id: int) -> Any:
    if g.user["id"] == item_id: flash("Vous ne pouvez pas désactiver votre propre compte.", "error")
    else:
        db = get_db(); active = db.execute("SELECT active FROM users WHERE id=?", (item_id,)).fetchone(); db.execute("UPDATE users SET active=? WHERE id=?", (0 if active["active"] else 1, item_id)); db.commit(); flash("Statut utilisateur mis à jour.", "success")
    return redirect(url_for("users"))


if __name__ == "__main__":
    with app.app_context(): init_db()
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "5000")), debug=os.getenv("FLASK_DEBUG") == "1")
