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

Aucune dépendance externe n'est nécessaire.

## Premier accès

- Identifiant : `admin`
- Mot de passe : `admin123`

Modifiez ou désactivez ce compte depuis le menu **Administration** après la première connexion.
