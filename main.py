from __future__ import annotations

import sqlite3
import hashlib
import re
from datetime import date
from pathlib import Path
import tkinter as tk
from tkinter import messagebox, ttk


APP_DIR = Path(__file__).resolve().parent
DB_PATH = APP_DIR / "gestcom.db"


class Database:
    def __init__(self, path: Path = DB_PATH) -> None:
        self.conn = sqlite3.connect(path)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")
        self.setup()

    def setup(self) -> None:
        self.conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS clients (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL, phone TEXT DEFAULT '', email TEXT DEFAULT '',
                address TEXT DEFAULT '', created_at TEXT DEFAULT CURRENT_DATE
            );
            CREATE TABLE IF NOT EXISTS products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL, category TEXT DEFAULT '', price REAL NOT NULL DEFAULT 0,
                stock INTEGER NOT NULL DEFAULT 0, min_stock INTEGER NOT NULL DEFAULT 5
            );
            CREATE TABLE IF NOT EXISTS sales (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                client_id INTEGER, product_id INTEGER NOT NULL, quantity INTEGER NOT NULL,
                total REAL NOT NULL, sold_at TEXT DEFAULT CURRENT_DATE,
                FOREIGN KEY(client_id) REFERENCES clients(id) ON DELETE SET NULL,
                FOREIGN KEY(product_id) REFERENCES products(id)
            );
            CREATE TABLE IF NOT EXISTS suppliers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL, phone TEXT DEFAULT '', email TEXT DEFAULT '', address TEXT DEFAULT '', created_at TEXT DEFAULT CURRENT_DATE
            );
            CREATE TABLE IF NOT EXISTS purchases (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                supplier_id INTEGER, product_id INTEGER NOT NULL, quantity INTEGER NOT NULL,
                unit_cost REAL NOT NULL, total REAL NOT NULL, purchased_at TEXT DEFAULT CURRENT_DATE,
                FOREIGN KEY(supplier_id) REFERENCES suppliers(id) ON DELETE SET NULL,
                FOREIGN KEY(product_id) REFERENCES products(id)
            );
            CREATE TABLE IF NOT EXISTS cash_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT, opened_at TEXT NOT NULL, opening_balance REAL NOT NULL DEFAULT 0,
                closed_at TEXT, closing_balance REAL, status TEXT NOT NULL DEFAULT 'open'
            );
            CREATE TABLE IF NOT EXISTS cash_transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT, session_id INTEGER NOT NULL, kind TEXT NOT NULL,
                label TEXT NOT NULL, amount REAL NOT NULL, payment_method TEXT DEFAULT 'Espèces',
                reference TEXT DEFAULT '', created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(session_id) REFERENCES cash_sessions(id) ON DELETE CASCADE
            );
            CREATE TABLE IF NOT EXISTS expenses (
                id INTEGER PRIMARY KEY AUTOINCREMENT, label TEXT NOT NULL, category TEXT DEFAULT '',
                amount REAL NOT NULL, expense_date TEXT DEFAULT CURRENT_DATE, payment_method TEXT DEFAULT 'Espèces'
            );
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT NOT NULL UNIQUE, password_hash TEXT NOT NULL,
                full_name TEXT NOT NULL, role TEXT NOT NULL DEFAULT 'cashier', active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT DEFAULT CURRENT_DATE
            );
            """
        )
        self.conn.execute("INSERT OR IGNORE INTO suppliers(id, name, phone, email) VALUES (1, 'Fournisseur principal', '', '')")
        # Keep existing databases compatible with the extended sales workflow.
        columns = {row[1] for row in self.conn.execute("PRAGMA table_info(sales)")}
        if "payment_method" not in columns:
            self.conn.execute("ALTER TABLE sales ADD COLUMN payment_method TEXT DEFAULT 'Espèces'")
        if "status" not in columns:
            self.conn.execute("ALTER TABLE sales ADD COLUMN status TEXT DEFAULT 'Payée'")
        if self.conn.execute("SELECT COUNT(*) FROM clients").fetchone()[0] == 0:
            self.conn.executemany("INSERT INTO clients(name, phone, email) VALUES (?, ?, ?)", [
                ("Binta Distribution", "+225 07 07 07 07 07", "contact@binta.ci"),
                ("Kouassi & Fils", "+225 05 05 05 05 05", "achats@kouassi.ci"),
                ("Client comptoir", "", ""),
            ])
        if self.conn.execute("SELECT COUNT(*) FROM products").fetchone()[0] == 0:
            self.conn.executemany("INSERT INTO products(name, category, price, stock, min_stock) VALUES (?, ?, ?, ?, ?)", [
                ("Carton de ramettes A4", "Fournitures", 18500, 24, 5),
                ("Encre imprimante HP 305", "Informatique", 23500, 8, 5),
                ("Pack stylos bleus", "Fournitures", 3500, 42, 10),
                ("Clavier sans fil", "Informatique", 12000, 3, 5),
            ])
        if self.conn.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 0:
            self.conn.execute("INSERT INTO users(username, password_hash, full_name, role) VALUES (?, ?, ?, ?)", ("admin", self.hash_password("admin123"), "Administrateur", "admin"))
        self.conn.commit()

    @staticmethod
    def hash_password(password: str) -> str:
        return hashlib.sha256(password.encode("utf-8")).hexdigest()

    def authenticate(self, username: str, password: str) -> sqlite3.Row | None:
        return self.conn.execute("SELECT * FROM users WHERE username=? AND password_hash=? AND active=1", (username.strip(), self.hash_password(password))).fetchone()

    def active_cash(self) -> sqlite3.Row | None:
        return self.conn.execute("SELECT * FROM cash_sessions WHERE status='open' ORDER BY id DESC LIMIT 1").fetchone()

    def scalar(self, sql: str, args: tuple = ()) -> object:
        return self.conn.execute(sql, args).fetchone()[0]

    def close(self) -> None:
        self.conn.close()


class GestComApp(tk.Tk):
    NAVY = "#10233F"
    BLUE = "#2563EB"
    BG = "#F6F8FC"
    TEXT = "#172033"
    MUTED = "#718096"
    GREEN = "#159570"
    ORANGE = "#D97706"
    BORDER = "#E3EAF4"
    PALE_BLUE = "#EAF1FF"

    def __init__(self) -> None:
        super().__init__()
        self.db = Database()
        self.title("GestCom — Gestion commerciale")
        self.geometry("1180x760")
        self.minsize(980, 650)
        self.configure(bg=self.BG)
        self.protocol("WM_DELETE_WINDOW", self.on_close)
        self.setup_styles()
        self.current_user: sqlite3.Row | None = None
        self.show_login()

    def show_login(self) -> None:
        for child in self.winfo_children(): child.destroy()
        self.geometry("980x620"); self.resizable(False, False); self.configure(bg="#EEF3FA")
        shell = tk.Frame(self, bg="white", highlightthickness=1, highlightbackground=self.BORDER)
        shell.pack(fill="both", expand=True, padx=30, pady=30)
        brand = tk.Frame(shell, bg=self.NAVY, width=365); brand.pack(side="left", fill="both"); brand.pack_propagate(False)
        tk.Frame(brand, bg="#2D6BFF", height=6).pack(fill="x")
        tk.Label(brand, text="◈", bg="#2D6BFF", fg="white", font=("Segoe UI", 24, "bold"), width=2, pady=5).pack(anchor="w", padx=42, pady=(55, 15))
        tk.Label(brand, text="GestCom", bg=self.NAVY, fg="white", font=("Segoe UI", 30, "bold")).pack(anchor="w", padx=42)
        tk.Label(brand, text="Votre activité, simplement\ngérée.", justify="left", bg=self.NAVY, fg="#B8C7DF", font=("Segoe UI", 16)).pack(anchor="w", padx=44, pady=(12, 38))
        tk.Frame(brand, bg="#263C60", height=1).pack(fill="x", padx=44)
        tk.Label(brand, text="Ventes  •  Stock  •  Caisse  •  Rapports", bg=self.NAVY, fg="#91A5C5", font=("Segoe UI", 9, "bold")).pack(anchor="w", padx=44, pady=18)
        panel = tk.Frame(shell, bg="white"); panel.pack(side="left", fill="both", expand=True)
        tk.Label(panel, text="Bienvenue 👋", bg="white", fg=self.NAVY, font=("Segoe UI", 25, "bold")).pack(anchor="w", padx=56, pady=(70, 5))
        tk.Label(panel, text="Connectez-vous à votre espace de travail", bg="white", fg=self.MUTED, font=("Segoe UI", 10)).pack(anchor="w", padx=58, pady=(0, 30))
        username = tk.StringVar(value="admin"); password = tk.StringVar()
        for label, var, show in [("Nom d'utilisateur", username, ""), ("Mot de passe", password, "•")]:
            tk.Label(panel, text=label, bg="white", fg=self.TEXT, font=("Segoe UI", 10, "bold")).pack(anchor="w", padx=58, pady=(8, 6))
            ttk.Entry(panel, textvariable=var, show=show, width=34, style="Login.TEntry").pack(padx=58, fill="x")
        message = tk.Label(panel, text="Identifiez-vous pour continuer", bg="white", fg=self.MUTED, font=("Segoe UI", 9)); message.pack(anchor="w", padx=58, pady=(16, 8))
        def submit(event: object | None = None) -> None:
            if not username.get().strip() or not password.get():
                message.configure(text="Saisissez l'identifiant et le mot de passe", fg="#C2410C"); return
            user = self.db.authenticate(username.get(), password.get())
            if not user: message.configure(text="Identifiants invalides ou compte désactivé", fg="#C2410C"); return
            self.current_user = user; self.geometry("1180x760"); self.resizable(True, True); self.build_layout(); self.show_dashboard()
        ttk.Button(panel, text="Se connecter  →", style="Primary.TButton", command=submit).pack(anchor="w", padx=58, pady=(8, 24))
        tk.Label(panel, text="GestCom Desktop  •  Gestion commerciale", bg="white", fg="#A0AEC0", font=("Segoe UI", 8)).pack(side="bottom", pady=24)
        self.bind("<Return>", submit)

    def setup_styles(self) -> None:
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("TFrame", background=self.BG)
        style.configure("TLabel", background=self.BG, foreground=self.TEXT, font=("Segoe UI", 10))
        style.configure("Title.TLabel", font=("Segoe UI", 25, "bold"), foreground=self.NAVY)
        style.configure("Subtitle.TLabel", font=("Segoe UI", 10), foreground=self.MUTED)
        style.configure("Card.TFrame", background="white")
        style.configure("Treeview", background="white", fieldbackground="white", foreground=self.TEXT, rowheight=38, font=("Segoe UI", 10))
        style.configure("Treeview.Heading", background="#EEF3FA", foreground=self.NAVY, font=("Segoe UI", 10, "bold"), padding=10)
        style.map("Treeview", background=[("selected", self.PALE_BLUE)], foreground=[("selected", self.NAVY)])
        style.configure("Primary.TButton", background=self.BLUE, foreground="white", padding=(16, 10), font=("Segoe UI", 10, "bold"), borderwidth=0)
        style.map("Primary.TButton", background=[("active", "#1D4ED8"), ("pressed", "#1E40AF")])
        style.configure("Secondary.TButton", background="#EAF0F8", foreground=self.NAVY, padding=(13, 9), borderwidth=0)
        style.map("Secondary.TButton", background=[("active", "#DCE7F7")])
        style.configure("TEntry", padding=8, fieldbackground="white", bordercolor=self.BORDER, lightcolor=self.BLUE, darkcolor=self.BORDER)
        style.configure("TCombobox", padding=7, fieldbackground="white", bordercolor=self.BORDER, lightcolor=self.BLUE, darkcolor=self.BORDER)
        style.configure("Login.TEntry", padding=10, font=("Segoe UI", 11))
        style.configure("TNotebook", background=self.BG, borderwidth=0)
        style.configure("TNotebook.Tab", padding=(18, 10), font=("Segoe UI", 10, "bold"))

    @staticmethod
    def validate_fields(labels: list[str], values: list[str]) -> None:
        """Validate common form rules before a callback writes to SQLite."""
        for label, value in zip(labels, values):
            value = value.strip()
            if not value and (label.startswith(("Nom", "Identifiant", "Libellé", "Produit")) or "Montant" in label or "Prix" in label or "Mot de passe" in label):
                raise ValueError(f"Le champ « {label} » est obligatoire.")
            if "Email" in label and value and not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", value):
                raise ValueError(f"L'adresse email « {value} » est invalide.")
            if "Téléphone" in label and value and not re.fullmatch(r"[+\d][\d ()-]{6,20}", value):
                raise ValueError("Le numéro de téléphone est invalide.")
            if "Mot de passe" in label and value and len(value) < 6:
                raise ValueError("Le mot de passe doit contenir au moins 6 caractères.")
        for label, value in zip(labels, values):
            if any(word in label for word in ("Montant", "Prix", "Coût")) and value:
                try:
                    if float(value.replace(" ", "").replace(",", ".")) < 0: raise ValueError
                except ValueError:
                    raise ValueError(f"Le champ « {label} » doit être un nombre positif.")
            if any(word in label for word in ("Quantité", "Stock", "Seuil")) and value:
                try:
                    if int(value) < 0: raise ValueError
                except ValueError:
                    raise ValueError(f"Le champ « {label} » doit être un entier positif.")

    def build_layout(self) -> None:
        # Defensive reset: only one shell (sidebar + page host) may exist.
        for child in self.winfo_children():
            child.destroy()
        self.sidebar = tk.Frame(self, bg=self.NAVY, width=252)
        self.sidebar.pack(side="left", fill="y")
        self.sidebar.pack_propagate(False)
        logo = tk.Frame(self.sidebar, bg=self.NAVY); logo.pack(fill="x", padx=25, pady=(26, 25))
        tk.Label(logo, text="◈", bg="#2D6BFF", fg="white", font=("Segoe UI", 18, "bold"), width=2, pady=4).pack(side="left")
        tk.Label(logo, text="GestCom", bg=self.NAVY, fg="white", font=("Segoe UI", 20, "bold")).pack(side="left", padx=10)
        tk.Label(self.sidebar, text="ESPACE DE TRAVAIL", bg=self.NAVY, fg="#8499BA", font=("Segoe UI", 8, "bold")).pack(anchor="w", padx=25, pady=(0, 12))
        self.nav_buttons: dict[str, tk.Button] = {}
        menu = [("dashboard", "⌂   Tableau de bord"), ("sales", "↗   Nouvelle vente"), ("cash", "▣   Caisse"), ("purchases", "⇩   Achats"), ("clients", "♙   Clients"), ("suppliers", "♧   Fournisseurs"), ("products", "▦   Produits & stock"), ("expenses", "−   Dépenses")]
        if self.current_user and self.current_user["role"] == "admin": menu.append(("admin", "⚙   Administration"))
        for key, label in menu:
            btn = tk.Button(self.sidebar, text=label, anchor="w", relief="flat", bd=0, bg=self.NAVY, fg="#CBD5E8", activebackground="#21385F", activeforeground="white", font=("Segoe UI", 11), padx=25, pady=13, command=lambda k=key: self.navigate(k))
            btn.pack(fill="x")
            btn.bind("<Enter>", lambda event, b=btn: b.configure(bg="#1B355B") if b.cget("bg") == self.NAVY else None)
            btn.bind("<Leave>", lambda event, b=btn: b.configure(bg=self.NAVY) if b.cget("bg") == "#1B355B" else None)
            self.nav_buttons[key] = btn
        footer = tk.Frame(self.sidebar, bg="#0C1C34"); footer.pack(fill="x", side="bottom", padx=14, pady=16)
        user_name = self.current_user["full_name"] if self.current_user else "Utilisateur"
        user_role = self.current_user["role"] if self.current_user else ""
        tk.Label(footer, text="●  " + user_name, bg="#0C1C34", fg="white", anchor="w", font=("Segoe UI", 10, "bold")).pack(fill="x", padx=12, pady=(12, 2))
        tk.Label(footer, text=user_role.upper(), bg="#0C1C34", fg="#91A5C5", anchor="w", font=("Segoe UI", 8, "bold")).pack(fill="x", padx=28, pady=(0, 9))
        tk.Button(footer, text="Se déconnecter", command=self.logout, relief="flat", bd=0, bg="#0C1C34", fg="#B9C6DB", activebackground="#1B355B", activeforeground="white", font=("Segoe UI", 9), anchor="w").pack(fill="x", padx=12, pady=(0, 10))
        self.content = tk.Frame(self, bg=self.BG)
        self.content.pack(side="left", fill="both", expand=True)

    def clear_content(self) -> None:
        # Recreate the page host entirely. This prevents a stale view from
        # remaining in the geometry manager when switching between sections.
        if hasattr(self, "content") and self.content.winfo_exists():
            self.content.pack_forget()
            self.content.destroy()
            self.update_idletasks()
        self.content = tk.Frame(self, bg=self.BG)
        self.content.pack(side="left", fill="both", expand=True)
        self.update_idletasks()

    def navigate(self, page: str) -> None:
        self.nav_buttons[page].configure(bg="#21385F", fg="white")
        for key, btn in self.nav_buttons.items():
            if key != page:
                btn.configure(bg=self.NAVY, fg="#CBD5E8")
        {"dashboard": self.show_dashboard, "sales": self.show_sales, "cash": self.show_cash, "purchases": self.show_purchases, "clients": self.show_clients, "suppliers": self.show_suppliers, "products": self.show_products, "expenses": self.show_expenses, "admin": self.show_admin}[page]()

    def logout(self) -> None:
        if messagebox.askyesno("Déconnexion", "Voulez-vous fermer la session ?"):
            self.current_user = None
            self.unbind("<Return>")
            self.show_login()

    def page_header(self, title: str, subtitle: str, action: tuple[str, object] | None = None) -> tk.Frame:
        head = tk.Frame(self.content, bg=self.BG)
        head.pack(fill="x", padx=38, pady=(32, 22))
        left = tk.Frame(head, bg=self.BG); left.pack(side="left")
        ttk.Label(left, text=title, style="Title.TLabel").pack(anchor="w")
        ttk.Label(left, text=subtitle, style="Subtitle.TLabel").pack(anchor="w", pady=(5, 0))
        right = tk.Frame(head, bg=self.BG); right.pack(side="right", anchor="n")
        if action:
            ttk.Button(right, text=action[0], style="Primary.TButton", command=action[1]).pack(pady=5)
        if self.current_user:
            tk.Label(right, text=f"{date.today().strftime('%d/%m/%Y')}  •  {self.current_user['full_name']}", bg=self.BG, fg=self.MUTED, font=("Segoe UI", 9)).pack(pady=(8, 0))
        return head

    def show_dashboard(self) -> None:
        self.clear_content(); self.page_header("Bonjour, bienvenue 👋", "Voici l'activité de votre entreprise aujourd'hui.")
        cards = tk.Frame(self.content, bg=self.BG); cards.pack(fill="x", padx=34)
        revenue = float(self.db.scalar("SELECT COALESCE(SUM(total), 0) FROM sales WHERE sold_at = CURRENT_DATE"))
        sales_count = int(self.db.scalar("SELECT COUNT(*) FROM sales WHERE sold_at = CURRENT_DATE"))
        clients = int(self.db.scalar("SELECT COUNT(*) FROM clients")); low = int(self.db.scalar("SELECT COUNT(*) FROM products WHERE stock <= min_stock"))
        for label, value, hint, color in [("Chiffre d'affaires", f"{revenue:,.0f} FCFA", "Aujourd'hui", self.BLUE), ("Ventes du jour", str(sales_count), "Transactions", self.GREEN), ("Clients", str(clients), "Clients enregistrés", "#7C3AED"), ("Alertes stock", str(low), "À réapprovisionner", self.ORANGE)]:
            card = tk.Frame(cards, bg="white", highlightthickness=1, highlightbackground=self.BORDER); card.pack(side="left", fill="x", expand=True, padx=(0, 14), ipady=18)
            tk.Frame(card, bg=color, width=5).pack(side="left", fill="y")
            inner = tk.Frame(card, bg="white"); inner.pack(anchor="w", padx=18)
            tk.Label(inner, text=label, bg="white", fg=self.MUTED, font=("Segoe UI", 10)).pack(anchor="w")
            tk.Label(inner, text=value, bg="white", fg=self.NAVY, font=("Segoe UI", 20, "bold")).pack(anchor="w", pady=3)
            tk.Label(inner, text=hint, bg="white", fg=color, font=("Segoe UI", 9, "bold")).pack(anchor="w")
        lower = tk.Frame(self.content, bg=self.BG); lower.pack(fill="both", expand=True, padx=34, pady=25)
        recent = self.card_frame(lower, "Dernières ventes"); recent.pack(side="left", fill="both", expand=True, padx=(0, 12))
        tree = self.make_tree(recent, [("date", "Date", 100), ("client", "Client", 190), ("product", "Produit", 230), ("total", "Montant", 120)])
        for row in self.db.conn.execute("SELECT s.sold_at, COALESCE(c.name, 'Client comptoir') client, p.name product, s.total FROM sales s JOIN products p ON p.id=s.product_id LEFT JOIN clients c ON c.id=s.client_id ORDER BY s.id DESC LIMIT 7"):
            tree.insert("", "end", values=(row["sold_at"], row["client"], row["product"], f"{row['total']:,.0f} FCFA"))
        alerts = self.card_frame(lower, "Stock à surveiller"); alerts.pack(side="left", fill="both", expand=True, padx=(12, 0))
        for row in self.db.conn.execute("SELECT name, stock, min_stock FROM products WHERE stock <= min_stock ORDER BY stock"):
            line = tk.Frame(alerts, bg="white"); line.pack(fill="x", padx=18, pady=10)
            tk.Label(line, text=row["name"], bg="white", fg=self.TEXT, font=("Segoe UI", 10, "bold")).pack(side="left")
            tk.Label(line, text=f"{row['stock']} en stock", bg="white", fg=self.ORANGE, font=("Segoe UI", 10, "bold")).pack(side="right")

    def card_frame(self, parent: tk.Widget, title: str) -> tk.Frame:
        outer = tk.Frame(parent, bg="white", highlightthickness=1, highlightbackground=self.BORDER)
        tk.Label(outer, text=title, bg="white", fg=self.NAVY, font=("Segoe UI", 13, "bold"), anchor="w").pack(fill="x", padx=22, pady=(19, 12))
        return outer

    def make_tree(self, parent: tk.Widget, columns: list[tuple[str, str, int]]) -> ttk.Treeview:
        frame = tk.Frame(parent, bg="white"); frame.pack(fill="both", expand=True, padx=18, pady=(0, 18))
        tree = ttk.Treeview(frame, columns=[c[0] for c in columns], show="headings", selectmode="browse")
        tree.tag_configure("even", background="#FBFCFE")
        tree.tag_configure("odd", background="white")
        for key, heading, width in columns:
            tree.heading(key, text=heading, command=lambda column=key: self.sort_tree(tree, column, False)); tree.column(key, width=width, anchor="w", minwidth=55)
        scroll_y = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
        scroll_x = ttk.Scrollbar(frame, orient="horizontal", command=tree.xview)
        tree.configure(yscrollcommand=scroll_y.set, xscrollcommand=scroll_x.set)
        scroll_x.pack(side="bottom", fill="x")
        scroll_y.pack(side="right", fill="y")
        tree.pack(side="left", fill="both", expand=True)
        tree.bind("<Configure>", lambda _event: self.stripe_tree(tree))
        tree.after_idle(lambda: self.stripe_tree(tree))
        return tree

    def stripe_tree(self, tree: ttk.Treeview) -> None:
        """Apply the alternating-row treatment shared by all data tables."""
        for index, item in enumerate(tree.get_children()):
            tree.item(item, tags=("even" if index % 2 == 0 else "odd",))

    def sort_tree(self, tree: ttk.Treeview, column: str, reverse: bool) -> None:
        values = [(tree.set(item, column), item) for item in tree.get_children("")]
        def sort_key(pair: tuple[str, str]) -> tuple[int, object]:
            value = pair[0].replace(" FCFA", "").replace(" ", "").replace(",", ".")
            try: return (0, float(value))
            except ValueError: return (1, value.casefold())
        for index, (_, item) in enumerate(sorted(values, key=sort_key, reverse=reverse)):
            tree.move(item, "", index)
        tree.heading(column, command=lambda: self.sort_tree(tree, column, not reverse))
        self.stripe_tree(tree)

    def selected_id(self, tree: ttk.Treeview, title: str) -> int | None:
        selected = tree.selection()
        if not selected: messagebox.showwarning(title, "Sélectionnez une ligne."); return None
        return int(tree.item(selected[0], "values")[0])

    def edit_selected_client(self, tree: ttk.Treeview) -> None:
        record_id = self.selected_id(tree, "Client")
        if record_id is None: return
        row = self.db.conn.execute("SELECT name, phone, email FROM clients WHERE id=?", (record_id,)).fetchone()
        self.record_dialog("Modifier le client", ["Nom / entreprise", "Téléphone", "Email"], list(row), lambda v: self.db.conn.execute("UPDATE clients SET name=?, phone=?, email=? WHERE id=?", (*v, record_id)), self.show_clients)

    def delete_selected_client(self, tree: ttk.Treeview) -> None:
        record_id = self.selected_id(tree, "Client")
        if record_id is None or not messagebox.askyesno("Supprimer le client", "Supprimer ce client ? Ses ventes seront conservées."): return
        self.db.conn.execute("DELETE FROM clients WHERE id=?", (record_id,)); self.db.conn.commit(); self.show_clients()

    def edit_selected_product(self, tree: ttk.Treeview) -> None:
        record_id = self.selected_id(tree, "Produit")
        if record_id is None: return
        row = self.db.conn.execute("SELECT name, category, price, stock, min_stock FROM products WHERE id=?", (record_id,)).fetchone()
        self.record_dialog("Modifier le produit", ["Nom", "Catégorie", "Prix unitaire", "Stock", "Seuil d'alerte"], [str(x) for x in row], lambda v: self.update_product(record_id, v), self.show_products)

    def update_product(self, record_id: int, values: list[str]) -> None:
        try: price, stock, minimum = float(values[2]), int(values[3]), int(values[4])
        except ValueError: raise ValueError("Prix, stock et seuil doivent être numériques.")
        if price < 0 or stock < 0 or minimum < 0: raise ValueError("Les valeurs numériques doivent être positives.")
        self.db.conn.execute("UPDATE products SET name=?, category=?, price=?, stock=?, min_stock=? WHERE id=?", (*values[:2], price, stock, minimum, record_id))

    def delete_selected_product(self, tree: ttk.Treeview) -> None:
        record_id = self.selected_id(tree, "Produit")
        if record_id is None: return
        used = int(self.db.scalar("SELECT COUNT(*) FROM sales WHERE product_id=?", (record_id,))) + int(self.db.scalar("SELECT COUNT(*) FROM purchases WHERE product_id=?", (record_id,)))
        if used: messagebox.showwarning("Suppression impossible", "Ce produit est utilisé dans l'historique des ventes ou achats."); return
        if messagebox.askyesno("Supprimer le produit", "Supprimer ce produit ?"): self.db.conn.execute("DELETE FROM products WHERE id=?", (record_id,)); self.db.conn.commit(); self.show_products()

    def edit_selected_supplier(self, tree: ttk.Treeview) -> None:
        record_id = self.selected_id(tree, "Fournisseur")
        if record_id is None: return
        row = self.db.conn.execute("SELECT name, phone, email FROM suppliers WHERE id=?", (record_id,)).fetchone()
        self.record_dialog("Modifier le fournisseur", ["Nom / entreprise", "Téléphone", "Email"], list(row), lambda v: self.db.conn.execute("UPDATE suppliers SET name=?, phone=?, email=? WHERE id=?", (*v, record_id)), self.show_suppliers)

    def delete_selected_supplier(self, tree: ttk.Treeview) -> None:
        record_id = self.selected_id(tree, "Fournisseur")
        if record_id is None: return
        if record_id == 1: messagebox.showwarning("Suppression impossible", "Le fournisseur principal ne peut pas être supprimé."); return
        if messagebox.askyesno("Supprimer le fournisseur", "Supprimer ce fournisseur ? Les achats seront conservés."): self.db.conn.execute("DELETE FROM suppliers WHERE id=?", (record_id,)); self.db.conn.commit(); self.show_suppliers()

    def show_clients(self) -> None:
        self.clear_content(); self.page_header("Clients", "Gérez votre portefeuille et vos contacts.", ("+ Nouveau client", self.add_client))
        box = self.card_frame(self.content, "Liste des clients"); box.pack(fill="both", expand=True, padx=34, pady=(0, 30))
        toolbar = tk.Frame(box, bg="white"); toolbar.pack(fill="x", padx=18, pady=(0, 8))
        tree = self.make_tree(box, [("id", "#", 50), ("name", "Nom / entreprise", 250), ("phone", "Téléphone", 180), ("email", "Email", 260), ("created", "Depuis", 120)])
        ttk.Button(toolbar, text="Modifier", style="Secondary.TButton", command=lambda: self.edit_selected_client(tree)).pack(side="right", padx=4)
        ttk.Button(toolbar, text="Supprimer", style="Secondary.TButton", command=lambda: self.delete_selected_client(tree)).pack(side="right", padx=4)
        for row in self.db.conn.execute("SELECT id, name, phone, email, created_at FROM clients ORDER BY name"):
            tree.insert("", "end", values=tuple(row))

    def show_products(self) -> None:
        self.clear_content(); self.page_header("Produits & stock", "Suivez vos références et vos niveaux de stock.", ("+ Nouveau produit", self.add_product))
        box = self.card_frame(self.content, "Catalogue produits"); box.pack(fill="both", expand=True, padx=34, pady=(0, 30))
        toolbar = tk.Frame(box, bg="white"); toolbar.pack(fill="x", padx=18, pady=(0, 8))
        tree = self.make_tree(box, [("id", "#", 50), ("name", "Produit", 270), ("category", "Catégorie", 160), ("price", "Prix unitaire", 150), ("stock", "Stock", 100), ("status", "État", 150)])
        ttk.Button(toolbar, text="Modifier", style="Secondary.TButton", command=lambda: self.edit_selected_product(tree)).pack(side="right", padx=4)
        ttk.Button(toolbar, text="Supprimer", style="Secondary.TButton", command=lambda: self.delete_selected_product(tree)).pack(side="right", padx=4)
        for row in self.db.conn.execute("SELECT id, name, category, price, stock, min_stock FROM products ORDER BY name"):
            status = "⚠ À réapprovisionner" if row["stock"] <= row["min_stock"] else "✓ Disponible"
            tree.insert("", "end", values=(row["id"], row["name"], row["category"], f"{row['price']:,.0f} FCFA", row["stock"], status))

    def show_sales(self) -> None:
        self.clear_content(); self.page_header("Nouvelle vente", "Enregistrez une transaction et mettez le stock à jour.")
        form = self.card_frame(self.content, "Détails de la vente"); form.pack(fill="x", padx=34, pady=(0, 18))
        fields = tk.Frame(form, bg="white"); fields.pack(fill="x", padx=22, pady=18)
        clients = [("Client comptoir", None)] + [(r["name"], r["id"]) for r in self.db.conn.execute("SELECT id, name FROM clients ORDER BY name")]
        products = [(f"{r['name']} — {r['price']:,.0f} FCFA (stock: {r['stock']})", r["id"], r["price"], r["stock"]) for r in self.db.conn.execute("SELECT id, name, price, stock FROM products ORDER BY name")]
        client_var = tk.StringVar(value=clients[0][0]); product_var = tk.StringVar(); qty_var = tk.StringVar(value="1"); payment_var = tk.StringVar(value="Espèces"); total_var = tk.StringVar(value="0 FCFA")
        self.form_label(fields, "Client", 0, 0); client_cb = ttk.Combobox(fields, textvariable=client_var, values=[x[0] for x in clients], state="readonly", width=30); client_cb.grid(row=1, column=0, padx=(0, 18), sticky="ew")
        self.form_label(fields, "Produit", 0, 1); product_cb = ttk.Combobox(fields, textvariable=product_var, values=[x[0] for x in products], state="readonly", width=42); product_cb.grid(row=1, column=1, padx=(0, 18), sticky="ew")
        self.form_label(fields, "Quantité", 0, 2); ttk.Entry(fields, textvariable=qty_var, width=10).grid(row=1, column=2, padx=(0, 18), sticky="w")
        self.form_label(fields, "Total", 0, 3); tk.Label(fields, textvariable=total_var, bg="white", fg=self.BLUE, font=("Segoe UI", 14, "bold")).grid(row=1, column=3, sticky="w")
        self.form_label(fields, "Paiement", 2, 0); ttk.Combobox(fields, textvariable=payment_var, values=["Espèces", "Mobile Money", "Carte bancaire", "Virement"], state="readonly", width=27).grid(row=3, column=0, sticky="w")
        for col in range(4): fields.columnconfigure(col, weight=1)
        def update_total(*_: object) -> None:
            try:
                idx = product_cb.current(); qty = max(0, int(qty_var.get() or 0)); total_var.set(f"{products[idx][2] * qty:,.0f} FCFA" if idx >= 0 else "0 FCFA")
            except (ValueError, IndexError): total_var.set("0 FCFA")
        product_var.trace_add("write", update_total); qty_var.trace_add("write", update_total)
        ttk.Button(form, text="Enregistrer la vente", style="Primary.TButton", command=lambda: self.save_sale(client_cb, clients, product_cb, products, qty_var, payment_var.get())).pack(anchor="e", padx=22, pady=(0, 20))
        history = self.card_frame(self.content, "Historique récent"); history.pack(fill="both", expand=True, padx=34, pady=(0, 30))
        toolbar = tk.Frame(history, bg="white"); toolbar.pack(fill="x", padx=18, pady=(0, 8))
        tree = self.make_tree(history, [("id", "#", 50), ("date", "Date", 100), ("client", "Client", 220), ("product", "Produit", 300), ("qty", "Qté", 70), ("total", "Total", 150)])
        ttk.Button(toolbar, text="Annuler la vente", style="Secondary.TButton", command=lambda: self.cancel_selected_sale(tree)).pack(side="right")
        for row in self.db.conn.execute("SELECT s.id, s.sold_at, COALESCE(c.name, 'Client comptoir') client, p.name, s.quantity, s.total FROM sales s JOIN products p ON p.id=s.product_id LEFT JOIN clients c ON c.id=s.client_id ORDER BY s.id DESC LIMIT 20"):
            tree.insert("", "end", values=(row["id"], row["sold_at"], row["client"], row["name"], row["quantity"], f"{row['total']:,.0f} FCFA"))

    def cancel_selected_sale(self, tree: ttk.Treeview) -> None:
        sale_id = self.selected_id(tree, "Vente")
        if sale_id is None or not messagebox.askyesno("Annuler la vente", "Annuler cette vente et remettre la quantité en stock ?"): return
        row = self.db.conn.execute("SELECT product_id, quantity FROM sales WHERE id=?", (sale_id,)).fetchone()
        if row:
            self.db.conn.execute("UPDATE products SET stock=stock+? WHERE id=?", (row["quantity"], row["product_id"]))
            self.db.conn.execute("DELETE FROM sales WHERE id=?", (sale_id,)); self.db.conn.execute("DELETE FROM cash_transactions WHERE reference=?", (f"Vente #{sale_id}",)); self.db.conn.commit(); self.show_sales()

    def show_cash(self) -> None:
        self.clear_content()
        session = self.db.active_cash()
        action = ("Fermer la caisse", self.close_cash) if session else ("Ouvrir la caisse", self.open_cash)
        self.page_header("Caisse", "Suivez les encaissements, décaissements et le solde de la journée.", action)
        balance = float(session["opening_balance"] if session else 0)
        if session:
            balance += float(self.db.scalar("SELECT COALESCE(SUM(CASE WHEN kind='IN' THEN amount ELSE -amount END),0) FROM cash_transactions WHERE session_id=?", (session["id"],)))
        today_in = float(self.db.scalar("SELECT COALESCE(SUM(amount),0) FROM cash_transactions WHERE kind='IN' AND date(created_at)=CURRENT_DATE"))
        today_out = float(self.db.scalar("SELECT COALESCE(SUM(amount),0) FROM cash_transactions WHERE kind='OUT' AND date(created_at)=CURRENT_DATE"))
        cards = tk.Frame(self.content, bg=self.BG); cards.pack(fill="x", padx=34, pady=(0, 20))
        for label, value, color in [("Solde actuel", f"{balance:,.0f} FCFA", self.GREEN), ("Encaissements", f"{today_in:,.0f} FCFA", self.BLUE), ("Décaissements", f"{today_out:,.0f} FCFA", self.ORANGE)]:
            card = tk.Frame(cards, bg="white", highlightthickness=1, highlightbackground="#E4EAF2"); card.pack(side="left", fill="x", expand=True, padx=(0, 14), ipady=14)
            tk.Label(card, text=label, bg="white", fg=self.MUTED, font=("Segoe UI", 10)).pack(anchor="w", padx=18)
            tk.Label(card, text=value, bg="white", fg=color, font=("Segoe UI", 19, "bold")).pack(anchor="w", padx=18, pady=4)
        box = self.card_frame(self.content, "Mouvements de caisse"); box.pack(fill="both", expand=True, padx=34, pady=(0, 30))
        toolbar = tk.Frame(box, bg="white"); toolbar.pack(fill="x", padx=18, pady=(0, 8))
        ttk.Button(toolbar, text="+ Entrée / sortie manuelle", style="Secondary.TButton", command=self.add_cash_movement).pack(side="right")
        tree = self.make_tree(box, [("date", "Date", 160), ("kind", "Type", 110), ("label", "Libellé", 300), ("method", "Paiement", 150), ("amount", "Montant", 160)])
        query = "SELECT created_at, kind, label, payment_method, amount FROM cash_transactions ORDER BY id DESC LIMIT 50"
        for row in self.db.conn.execute(query):
            tree.insert("", "end", values=(row["created_at"], "Encaissement" if row["kind"] == "IN" else "Décaissement", row["label"], row["payment_method"], f"{row['amount']:,.0f} FCFA"))

    def open_cash(self) -> None:
        self.simple_dialog("Ouverture de caisse", ["Fond de caisse (FCFA)"], self.insert_cash_opening, self.show_cash)

    def insert_cash_opening(self, values: list[str]) -> None:
        if self.db.active_cash(): raise ValueError("Une caisse est déjà ouverte.")
        try: amount = float(values[0])
        except ValueError: raise ValueError("Le fond de caisse doit être numérique.")
        if amount < 0: raise ValueError("Le fond de caisse ne peut pas être négatif.")
        self.db.conn.execute("INSERT INTO cash_sessions(opened_at, opening_balance) VALUES (?, ?)", (date.today().isoformat(), amount))
        self.db.conn.commit()

    def close_cash(self) -> None:
        session = self.db.active_cash()
        if not session: return
        balance = float(session["opening_balance"]) + float(self.db.scalar("SELECT COALESCE(SUM(CASE WHEN kind='IN' THEN amount ELSE -amount END),0) FROM cash_transactions WHERE session_id=?", (session["id"],)))
        if not messagebox.askyesno("Fermer la caisse", f"Solde théorique : {balance:,.0f} FCFA\nConfirmer la fermeture ?"): return
        self.db.conn.execute("UPDATE cash_sessions SET status='closed', closed_at=?, closing_balance=? WHERE id=?", (date.today().isoformat(), balance, session["id"])); self.db.conn.commit(); self.show_cash()

    def add_cash_movement(self) -> None:
        if not self.db.active_cash(): messagebox.showwarning("Caisse fermée", "Ouvrez d'abord la caisse."); return
        win = tk.Toplevel(self); win.title("Mouvement de caisse"); win.configure(bg="white"); win.resizable(False, False); win.transient(self); win.grab_set()
        kind = tk.StringVar(value="OUT"); label = tk.StringVar(); amount = tk.StringVar(); method = tk.StringVar(value="Espèces")
        for i, (text, var) in enumerate([("Libellé", label), ("Montant FCFA", amount)]):
            tk.Label(win, text=text, bg="white", fg=self.TEXT, font=("Segoe UI", 10, "bold")).grid(row=i, column=0, padx=22, pady=8, sticky="w"); ttk.Entry(win, textvariable=var, width=32).grid(row=i, column=1, padx=22, pady=8)
        tk.Label(win, text="Type", bg="white", fg=self.TEXT, font=("Segoe UI", 10, "bold")).grid(row=2, column=0, padx=22, pady=8, sticky="w"); ttk.Combobox(win, textvariable=kind, values=["IN", "OUT"], state="readonly", width=29).grid(row=2, column=1, padx=22, pady=8)
        tk.Label(win, text="Moyen", bg="white", fg=self.TEXT, font=("Segoe UI", 10, "bold")).grid(row=3, column=0, padx=22, pady=8, sticky="w"); ttk.Combobox(win, textvariable=method, values=["Espèces", "Mobile Money", "Carte bancaire", "Virement"], state="readonly", width=29).grid(row=3, column=1, padx=22, pady=8)
        def submit() -> None:
            try: self.validate_fields(["Libellé", "Montant FCFA"], [label.get(), amount.get()])
            except ValueError as exc: messagebox.showerror("Caisse", str(exc), parent=win); return
            try: value = float(amount.get())
            except ValueError: messagebox.showerror("Caisse", "Montant invalide.", parent=win); return
            if not label.get().strip() or value <= 0: messagebox.showwarning("Caisse", "Libellé et montant sont obligatoires.", parent=win); return
            session = self.db.active_cash(); self.db.conn.execute("INSERT INTO cash_transactions(session_id, kind, label, amount, payment_method) VALUES (?, ?, ?, ?, ?)", (session["id"], kind.get(), label.get().strip(), value, method.get())); self.db.conn.commit(); win.destroy(); self.show_cash()
        ttk.Button(win, text="Enregistrer", style="Primary.TButton", command=submit).grid(row=4, column=1, padx=22, pady=18, sticky="e")

    def show_purchases(self) -> None:
        self.clear_content(); self.page_header("Achats & approvisionnement", "Réceptionnez les produits et augmentez automatiquement le stock.", ("+ Nouvel achat", self.add_purchase))
        box = self.card_frame(self.content, "Historique des achats"); box.pack(fill="both", expand=True, padx=34, pady=(0, 30))
        toolbar = tk.Frame(box, bg="white"); toolbar.pack(fill="x", padx=18, pady=(0, 8))
        tree = self.make_tree(box, [("id", "#", 50), ("date", "Date", 110), ("supplier", "Fournisseur", 230), ("product", "Produit", 260), ("qty", "Qté", 70), ("cost", "Coût unitaire", 140), ("total", "Total", 140)])
        ttk.Button(toolbar, text="Supprimer", style="Secondary.TButton", command=lambda: self.delete_selected_purchase(tree)).pack(side="right")
        for row in self.db.conn.execute("SELECT p.id, p.purchased_at, COALESCE(s.name,'—') supplier, pr.name product, p.quantity, p.unit_cost, p.total FROM purchases p JOIN products pr ON pr.id=p.product_id LEFT JOIN suppliers s ON s.id=p.supplier_id ORDER BY p.id DESC"):
            tree.insert("", "end", values=(row["id"], row["purchased_at"], row["supplier"], row["product"], row["quantity"], f"{row['unit_cost']:,.0f} FCFA", f"{row['total']:,.0f} FCFA"))

    def delete_selected_purchase(self, tree: ttk.Treeview) -> None:
        purchase_id = self.selected_id(tree, "Achat")
        if purchase_id is None or not messagebox.askyesno("Supprimer l'achat", "Supprimer cet achat et annuler son entrée en stock ?"): return
        row = self.db.conn.execute("SELECT product_id, quantity FROM purchases WHERE id=?", (purchase_id,)).fetchone()
        if row:
            self.db.conn.execute("UPDATE products SET stock=stock-? WHERE id=?", (row["quantity"], row["product_id"]))
            self.db.conn.execute("DELETE FROM purchases WHERE id=?", (purchase_id,)); self.db.conn.commit(); self.show_purchases()

    def add_purchase(self) -> None:
        suppliers = [(r["name"], r["id"]) for r in self.db.conn.execute("SELECT id, name FROM suppliers ORDER BY name")]
        products = [(r["name"], r["id"]) for r in self.db.conn.execute("SELECT id, name FROM products ORDER BY name")]
        if not products: messagebox.showwarning("Achat", "Ajoutez d'abord un produit."); return
        win = tk.Toplevel(self); win.title("Nouvel achat"); win.configure(bg="white"); win.resizable(False, False); win.transient(self); win.grab_set()
        supplier = tk.StringVar(value=suppliers[0][0] if suppliers else "Fournisseur principal"); product = tk.StringVar(value=products[0][0]); qty = tk.StringVar(value="1"); cost = tk.StringVar(value="0")
        entries = [("Fournisseur", supplier, [x[0] for x in suppliers]), ("Produit", product, [x[0] for x in products]), ("Quantité", qty, None), ("Coût unitaire FCFA", cost, None)]
        for i, (label, var, values) in enumerate(entries):
            tk.Label(win, text=label, bg="white", fg=self.TEXT, font=("Segoe UI", 10, "bold")).grid(row=i, column=0, padx=22, pady=9, sticky="w")
            if values is not None: ttk.Combobox(win, textvariable=var, values=values, state="readonly", width=32).grid(row=i, column=1, padx=22, pady=9)
            else: ttk.Entry(win, textvariable=var, width=35).grid(row=i, column=1, padx=22, pady=9)
        def submit() -> None:
            try: self.validate_fields(["Quantité", "Coût unitaire"], [qty.get(), cost.get()])
            except ValueError as exc: messagebox.showerror("Achat", str(exc), parent=win); return
            try: quantity, unit_cost = int(qty.get()), float(cost.get())
            except ValueError: messagebox.showerror("Achat", "Quantité et coût doivent être numériques.", parent=win); return
            if quantity <= 0 or unit_cost < 0: messagebox.showwarning("Achat", "Valeurs invalides.", parent=win); return
            product_id = next(x[1] for x in products if x[0] == product.get()); supplier_id = next((x[1] for x in suppliers if x[0] == supplier.get()), None); total = quantity * unit_cost
            self.db.conn.execute("INSERT INTO purchases(supplier_id, product_id, quantity, unit_cost, total) VALUES (?, ?, ?, ?, ?)", (supplier_id, product_id, quantity, unit_cost, total)); self.db.conn.execute("UPDATE products SET stock=stock+? WHERE id=?", (quantity, product_id)); self.db.conn.commit(); win.destroy(); self.show_purchases()
        ttk.Button(win, text="Réceptionner l'achat", style="Primary.TButton", command=submit).grid(row=4, column=1, padx=22, pady=18, sticky="e")

    def show_suppliers(self) -> None:
        self.clear_content(); self.page_header("Fournisseurs", "Gérez vos partenaires d'approvisionnement.", ("+ Nouveau fournisseur", self.add_supplier))
        box = self.card_frame(self.content, "Liste des fournisseurs"); box.pack(fill="both", expand=True, padx=34, pady=(0, 30))
        toolbar = tk.Frame(box, bg="white"); toolbar.pack(fill="x", padx=18, pady=(0, 8))
        tree = self.make_tree(box, [("id", "#", 60), ("name", "Nom / entreprise", 300), ("phone", "Téléphone", 190), ("email", "Email", 280)])
        ttk.Button(toolbar, text="Modifier", style="Secondary.TButton", command=lambda: self.edit_selected_supplier(tree)).pack(side="right", padx=4)
        ttk.Button(toolbar, text="Supprimer", style="Secondary.TButton", command=lambda: self.delete_selected_supplier(tree)).pack(side="right", padx=4)
        for row in self.db.conn.execute("SELECT id, name, phone, email FROM suppliers ORDER BY name"): tree.insert("", "end", values=tuple(row))

    def add_supplier(self) -> None:
        self.simple_dialog("Nouveau fournisseur", ["Nom / entreprise", "Téléphone", "Email"], lambda v: self.db.conn.execute("INSERT INTO suppliers(name, phone, email) VALUES (?, ?, ?)", v), self.show_suppliers)

    def show_expenses(self) -> None:
        self.clear_content(); self.page_header("Dépenses", "Suivez les charges et sorties de trésorerie.", ("+ Nouvelle dépense", self.add_expense))
        box = self.card_frame(self.content, "Journal des dépenses"); box.pack(fill="both", expand=True, padx=34, pady=(0, 30))
        toolbar = tk.Frame(box, bg="white"); toolbar.pack(fill="x", padx=18, pady=(0, 8))
        tree = self.make_tree(box, [("id", "#", 50), ("date", "Date", 130), ("label", "Libellé", 300), ("category", "Catégorie", 180), ("method", "Paiement", 160), ("amount", "Montant", 160)])
        ttk.Button(toolbar, text="Modifier", style="Secondary.TButton", command=lambda: self.edit_selected_expense(tree)).pack(side="right", padx=4)
        ttk.Button(toolbar, text="Supprimer", style="Secondary.TButton", command=lambda: self.delete_selected_expense(tree)).pack(side="right", padx=4)
        for row in self.db.conn.execute("SELECT id, expense_date, label, category, payment_method, amount FROM expenses ORDER BY id DESC"): tree.insert("", "end", values=(row["id"], row["expense_date"], row["label"], row["category"], row["payment_method"], f"{row['amount']:,.0f} FCFA"))

    def edit_selected_expense(self, tree: ttk.Treeview) -> None:
        expense_id = self.selected_id(tree, "Dépense")
        if expense_id is None: return
        row = self.db.conn.execute("SELECT label, category, amount FROM expenses WHERE id=?", (expense_id,)).fetchone()
        self.record_dialog("Modifier la dépense", ["Libellé", "Catégorie", "Montant FCFA"], [str(x) for x in row], lambda v: self.update_expense(expense_id, v), self.show_expenses)

    def update_expense(self, expense_id: int, values: list[str]) -> None:
        try: amount = float(values[2])
        except ValueError: raise ValueError("Le montant doit être numérique.")
        if amount <= 0: raise ValueError("Le montant doit être positif.")
        self.db.conn.execute("UPDATE expenses SET label=?, category=?, amount=? WHERE id=?", (*values[:2], amount, expense_id))
        self.db.conn.execute("UPDATE cash_transactions SET label=?, amount=? WHERE reference=?", (values[0], amount, f"Dépense:{expense_id}"))

    def delete_selected_expense(self, tree: ttk.Treeview) -> None:
        expense_id = self.selected_id(tree, "Dépense")
        if expense_id is None or not messagebox.askyesno("Supprimer la dépense", "Supprimer cette dépense ?"): return
        self.db.conn.execute("DELETE FROM expenses WHERE id=?", (expense_id,)); self.db.conn.execute("DELETE FROM cash_transactions WHERE reference=?", (f"Dépense:{expense_id}",)); self.db.conn.commit(); self.show_expenses()

    def add_expense(self) -> None:
        self.simple_dialog("Nouvelle dépense", ["Libellé", "Catégorie", "Montant FCFA"], self.insert_expense, self.show_expenses)

    def insert_expense(self, values: list[str]) -> None:
        self.validate_fields(["Libellé", "Catégorie", "Montant FCFA"], values)
        try: amount = float(values[2])
        except ValueError: raise ValueError("Le montant doit être numérique.")
        if amount <= 0: raise ValueError("Le montant doit être positif.")
        self.db.conn.execute("INSERT INTO expenses(label, category, amount) VALUES (?, ?, ?)", (values[0], values[1], amount))
        if self.db.active_cash():
            expense_id = self.db.conn.execute("SELECT last_insert_rowid()").fetchone()[0]
            session = self.db.active_cash(); self.db.conn.execute("INSERT INTO cash_transactions(session_id, kind, label, amount, payment_method, reference) VALUES (?, 'OUT', ?, ?, 'Espèces', ?)", (session["id"], values[0], amount, f"Dépense:{expense_id}"))

    def form_label(self, parent: tk.Widget, text: str, row: int, col: int) -> None:
        tk.Label(parent, text=text, bg="white", fg=self.MUTED, font=("Segoe UI", 9, "bold")).grid(row=row, column=col, sticky="w", pady=(0, 6))

    def save_sale(self, client_cb: ttk.Combobox, clients: list[tuple[str, int | None]], product_cb: ttk.Combobox, products: list[tuple[str, int, float, int]], qty_var: tk.StringVar, payment_method: str) -> None:
        try: self.validate_fields(["Quantité"], [qty_var.get()]); qty = int(qty_var.get())
        except ValueError: messagebox.showerror("Vente", "La quantité doit être un nombre entier."); return
        idx = product_cb.current()
        if idx < 0: messagebox.showwarning("Vente", "Sélectionnez un produit."); return
        if qty <= 0 or qty > products[idx][3]: messagebox.showwarning("Stock insuffisant", f"Stock disponible : {products[idx][3]}."); return
        client_id = clients[client_cb.current()][1]
        product_id, price, stock = products[idx][1], products[idx][2], products[idx][3]
        total = qty * price
        if payment_method == "Espèces" and not self.db.active_cash():
            messagebox.showwarning("Caisse fermée", "Ouvrez une session de caisse avant d'enregistrer une vente en espèces."); return
        self.db.conn.execute("INSERT INTO sales(client_id, product_id, quantity, total, sold_at, payment_method) VALUES (?, ?, ?, ?, ?, ?)", (client_id, product_id, qty, total, date.today().isoformat(), payment_method))
        sale_id = self.db.conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        self.db.conn.execute("UPDATE products SET stock = stock - ? WHERE id = ?", (qty, product_id)); self.db.conn.commit()
        if payment_method == "Espèces":
            session = self.db.active_cash()
            self.db.conn.execute("INSERT INTO cash_transactions(session_id, kind, label, amount, payment_method, reference) VALUES (?, 'IN', ?, ?, ?, ?)", (session["id"], "Vente commerciale", total, payment_method, f"Vente #{sale_id}"))
            self.db.conn.commit()
        messagebox.showinfo("Vente enregistrée", "La vente a été enregistrée et le stock mis à jour."); self.show_sales()

    def add_client(self) -> None:
        self.simple_dialog("Nouveau client", ["Nom / entreprise", "Téléphone", "Email"], lambda v: self.db.conn.execute("INSERT INTO clients(name, phone, email) VALUES (?, ?, ?)", v), self.show_clients)

    def add_product(self) -> None:
        self.simple_dialog("Nouveau produit", ["Nom du produit", "Catégorie", "Prix unitaire", "Stock initial"], self.insert_product, self.show_products)

    def insert_product(self, values: list[str]) -> None:
        self.validate_fields(["Nom du produit", "Catégorie", "Prix unitaire", "Stock initial"], values)
        try: price, stock = float(values[2]), int(values[3])
        except ValueError: raise ValueError("Prix et stock doivent être numériques")
        self.db.conn.execute("INSERT INTO products(name, category, price, stock) VALUES (?, ?, ?, ?)", (values[0], values[1], price, stock)); self.db.conn.commit()

    def show_admin(self) -> None:
        if not self.current_user or self.current_user["role"] != "admin": self.show_dashboard(); return
        self.clear_content(); self.page_header("Administration", "Utilisateurs, rôles et sécurité de l'application.", ("+ Nouvel utilisateur", self.add_user))
        box = self.card_frame(self.content, "Comptes utilisateurs"); box.pack(fill="both", expand=True, padx=34, pady=(0, 30))
        toolbar = tk.Frame(box, bg="white"); toolbar.pack(fill="x", padx=18, pady=(0, 8))
        tree = self.make_tree(box, [("id", "#", 55), ("username", "Identifiant", 180), ("full_name", "Nom complet", 250), ("role", "Rôle", 150), ("active", "Statut", 130), ("created", "Créé le", 130)])
        ttk.Button(toolbar, text="Modifier", style="Secondary.TButton", command=lambda: self.edit_user(tree)).pack(side="right", padx=4)
        ttk.Button(toolbar, text="Activer / désactiver", style="Secondary.TButton", command=lambda: self.toggle_user(tree)).pack(side="right", padx=4)
        for row in self.db.conn.execute("SELECT id, username, full_name, role, active, created_at FROM users ORDER BY username"):
            tree.insert("", "end", values=(row["id"], row["username"], row["full_name"], row["role"], "Actif" if row["active"] else "Désactivé", row["created_at"]))
        info = tk.Frame(self.content, bg="#EAF0F8"); info.pack(fill="x", padx=34, pady=(0, 28))
        tk.Label(info, text="Rôles disponibles : admin (accès complet), manager (activité commerciale), cashier (ventes/caisse), stock (produits/achats).", bg="#EAF0F8", fg=self.NAVY, font=("Segoe UI", 10)).pack(anchor="w", padx=18, pady=12)

    def add_user(self) -> None:
        self.simple_dialog("Nouvel utilisateur", ["Identifiant", "Nom complet", "Rôle (admin/manager/cashier/stock)", "Mot de passe"], self.insert_user, self.show_admin)

    def insert_user(self, values: list[str]) -> None:
        self.validate_fields(["Identifiant", "Nom complet", "Rôle", "Mot de passe"], values)
        if values[2] not in {"admin", "manager", "cashier", "stock"}: raise ValueError("Rôle invalide.")
        try: self.db.conn.execute("INSERT INTO users(username, password_hash, full_name, role) VALUES (?, ?, ?, ?)", (values[0], self.db.hash_password(values[3]), values[1], values[2]))
        except sqlite3.IntegrityError: raise ValueError("Cet identifiant existe déjà.")

    def edit_user(self, tree: ttk.Treeview) -> None:
        record_id = self.selected_id(tree, "Utilisateur")
        if record_id is None: return
        row = self.db.conn.execute("SELECT username, full_name, role FROM users WHERE id=?", (record_id,)).fetchone()
        self.record_dialog("Modifier l'utilisateur", ["Identifiant", "Nom complet", "Rôle"], list(row), lambda v: self.update_user(record_id, v), self.show_admin)

    def update_user(self, record_id: int, values: list[str]) -> None:
        self.validate_fields(["Identifiant", "Nom complet", "Rôle"], values)
        if values[2] not in {"admin", "manager", "cashier", "stock"}: raise ValueError("Rôle invalide.")
        try: self.db.conn.execute("UPDATE users SET username=?, full_name=?, role=? WHERE id=?", (*values, record_id))
        except sqlite3.IntegrityError: raise ValueError("Cet identifiant existe déjà.")

    def toggle_user(self, tree: ttk.Treeview) -> None:
        record_id = self.selected_id(tree, "Utilisateur")
        if record_id is None: return
        if self.current_user and record_id == self.current_user["id"]: messagebox.showwarning("Administration", "Vous ne pouvez pas désactiver votre propre compte."); return
        row = self.db.conn.execute("SELECT active FROM users WHERE id=?", (record_id,)).fetchone()
        self.db.conn.execute("UPDATE users SET active=? WHERE id=?", (0 if row["active"] else 1, record_id)); self.db.conn.commit(); self.show_admin()

    def record_dialog(self, title: str, labels: list[str], values: list[str], action: object, refresh: object) -> None:
        win = tk.Toplevel(self); win.title(title); win.resizable(False, False); win.configure(bg="white"); win.transient(self); win.grab_set()
        vars_ = [tk.StringVar(value=str(value)) for value in values]
        for i, label in enumerate(labels):
            tk.Label(win, text=label, bg="white", fg=self.TEXT, font=("Segoe UI", 10, "bold")).grid(row=i, column=0, padx=22, pady=(16 if i == 0 else 5, 4), sticky="w")
            ttk.Entry(win, textvariable=vars_[i], width=38).grid(row=i, column=1, padx=(0, 22), pady=(16 if i == 0 else 5, 4))
        def submit() -> None:
            data = [v.get().strip() for v in vars_]
            try: self.validate_fields(labels, data); action(data); self.db.conn.commit(); win.destroy(); refresh()
            except ValueError as exc: messagebox.showerror(title, str(exc), parent=win)
        ttk.Button(win, text="Enregistrer", style="Primary.TButton", command=submit).grid(row=len(labels), column=1, padx=22, pady=20, sticky="e")

    def simple_dialog(self, title: str, labels: list[str], action: object, refresh: object) -> None:
        win = tk.Toplevel(self); win.title(title); win.resizable(False, False); win.configure(bg="white"); win.transient(self); win.grab_set()
        vars_ = [tk.StringVar() for _ in labels]
        for i, label in enumerate(labels):
            tk.Label(win, text=label, bg="white", fg=self.TEXT, font=("Segoe UI", 10, "bold")).grid(row=i, column=0, padx=22, pady=(16 if i == 0 else 5, 4), sticky="w")
            ttk.Entry(win, textvariable=vars_[i], width=38).grid(row=i, column=1, padx=(0, 22), pady=(16 if i == 0 else 5, 4))
        def submit() -> None:
            values = [v.get().strip() for v in vars_]
            try: self.validate_fields(labels, values); action(values); self.db.conn.commit(); win.destroy(); refresh()
            except ValueError as exc: messagebox.showerror(title, str(exc), parent=win)
        ttk.Button(win, text="Enregistrer", style="Primary.TButton", command=submit).grid(row=len(labels), column=1, padx=22, pady=20, sticky="e")

    def on_close(self) -> None:
        self.db.close(); self.destroy()


if __name__ == "__main__":
    GestComApp().mainloop()
