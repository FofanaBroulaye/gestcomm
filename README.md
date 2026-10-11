# GestCom

Application desktop de gestion commerciale en Python, Tkinter et SQLite.

## Fonctionnalités

- Tableau de bord avec chiffre d'affaires, ventes, clients et alertes stock
- Gestion des clients
- Gestion des fournisseurs
- Catalogue produits et suivi des seuils de stock
- Enregistrement des ventes avec contrôle du stock et moyens de paiement
- Caisse : ouverture, fond de caisse, encaissements, décaissements et clôture
- Achats fournisseurs avec réception et mise à jour automatique du stock
- Journal des dépenses avec impact sur la caisse ouverte
- Historique des ventes, achats et mouvements financiers
- Connexion sécurisée par utilisateur et mot de passe
- Administration des utilisateurs et rôles : `admin`, `manager`, `cashier`, `stock`
- Modification et suppression contrôlées des clients, produits et fournisseurs
- Validation des champs : obligatoires, email, téléphone, montants, quantités, stocks, rôles et mots de passe
- Base SQLite locale créée automatiquement dans `gestcom.db`

## Lancer l'application

```powershell
C:/Users/fofan/AppData/Local/Programs/Python/Python313/python.exe main.py
```

L'application n'a aucune dépendance externe à l'exécution : Tkinter et SQLite sont inclus avec Python.

## Installation et setup développeur

Depuis PowerShell :

```powershell
cd D:\gestCom
py -3.13 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python main.py
```

La base locale `gestcom.db` est créée automatiquement au premier lancement.

## Version Windows compilée

PyInstaller est utilisé pour générer l'application autonome :

```powershell
.\.venv\Scripts\Activate.ps1
python -m pip install pyinstaller
python -m PyInstaller --noconfirm --clean --windowed --name GestCom main.py
```

L'exécutable produit se trouve dans :

```text
dist\GestCom\GestCom.exe
```

Copiez tout le dossier `dist\GestCom` sur le poste cible. La base SQLite sera créée à côté de l'exécutable au premier démarrage.

## Version web Flask

La version web se trouve dans [webapp.py](./webapp.py). Elle reprend la connexion, les rôles, le tableau de bord, les clients, fournisseurs, produits, ventes, achats, caisse, dépenses et l'administration.

Installation locale :

```powershell
cd D:\gestCom
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-web.txt
python webapp.py
```

Ouvrir ensuite `http://127.0.0.1:5000`.

Pour un serveur de production, définir une clé secrète et lancer Flask derrière Nginx ou un reverse proxy HTTPS :

```powershell
$env:GESTCOM_SECRET = "une-cle-secrete-longue-et-aleatoire"
$env:GESTCOM_DB = "D:\gestCom\gestcom-web.db"
python webapp.py
```

En production Linux, utiliser un serveur WSGI comme Gunicorn et PostgreSQL pour plusieurs utilisateurs simultanés. SQLite reste adapté au prototype ou à une petite installation mono-serveur.

## Premier accès

- Identifiant : `admin`
- Mot de passe : `admin123`

Modifiez ou désactivez ce compte depuis le menu **Administration** après la première connexion.
