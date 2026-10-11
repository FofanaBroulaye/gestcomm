# GestCom Web

Application web de gestion commerciale avec Flask, SQLite et une interface responsive.

## Fonctionnalités

- Tableau de bord commercial
- Connexion sécurisée et rôles (`admin`, `manager`, `cashier`, `stock`)
- Administration des utilisateurs
- Clients et fournisseurs
- Produits et suivi du stock
- Ventes et annulation avec restauration du stock
- Achats et réception fournisseur
- Caisse : ouverture, encaissements, décaissements et clôture
- Dépenses
- Modification, suppression et validation des données

## Installation locale

```powershell
cd D:\gestCom
py -3.13 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements-web.txt
python webapp.py
```

Ouvrir ensuite `http://127.0.0.1:5000`.

La base SQLite est créée automatiquement dans `gestcom.db`. Pour isoler la base web :

```powershell
$env:GESTCOM_DB = "D:\gestCom\gestcom-web.db"
$env:GESTCOM_SECRET = "une-cle-secrete-longue-et-aleatoire"
python webapp.py
```

## Déploiement VPS

En production, utiliser un serveur WSGI comme Gunicorn derrière Nginx avec HTTPS. Pour plusieurs utilisateurs simultanés, remplacer SQLite par PostgreSQL et définir `GESTCOM_DB` selon la configuration du backend.

## Premier accès

- Identifiant : `admin`
- Mot de passe : `admin123`

Modifiez ou désactivez ce compte depuis **Administration** après la première connexion.
