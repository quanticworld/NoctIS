# NoctIS - Quick Start Guide

## Premier lancement (installation complète)

```bash
# Lancer le script d'installation et tests
./run.sh
```

Ce script va :
- Installer toutes les dépendances (Python + Node.js)
- Lancer les tests unitaires
- Démarrer les deux serveurs

## Démarrage rapide (après installation)

```bash
./start.sh
```

Puis ouvrez votre navigateur sur **http://localhost:5173**

## Utilisation

### 1. Configuration (Settings)

- Définissez le chemin de recherche (par défaut `/mnt/osint`)
- Ajustez le nombre de threads (1-16)
- Configurez la taille max des fichiers
- Cliquez sur **SCAN** pour obtenir les statistiques du dataset

### 2. Recherche (Search)

#### Templates disponibles :

1. **Name Search** : Recherche nom/prénom dans n'importe quel ordre
   - Remplissez "First Name" et "Last Name"
   - Exemple : `Alen` et `Gasparic` → trouve "Alen Gasparic" OU "Gasparic Alen"

2. **Email** : Détecte toutes les adresses email

3. **Phone (FR)** : Numéros de téléphone français (0X XX XX XX XX)

4. **IP Address** : Adresses IPv4

5. **Custom** : Votre propre regex

#### Lancement d'une recherche :

1. Sélectionnez un template
2. Remplissez les champs requis
3. Cliquez sur **START SEARCH**
4. Suivez la progression en temps réel
5. Les résultats s'affichent au fur et à mesure

#### Fonctionnalités :

- **Progress bar** avec vitesse de scan et ETA
- **Résultats en temps réel** via WebSocket
- **Highlight des matches** dans les lignes
- **CANCEL** pour arrêter une recherche en cours
- **CLEAR** pour vider les résultats

## Architecture

```
Backend:  http://localhost:8000
Frontend: http://localhost:5173
WebSocket: ws://localhost:8000/ws/search
```

## Exemples de recherche

### Recherche nom/prénom
```
Template: Name Search
First Name: Thomas
Last Name: Pingle
→ Trouve: "Thomas Pingle" ou "Pingle Thomas"
```

### Recherche emails dans des logs
```
Template: Email
→ Trouve tous les emails dans vos fichiers
```

### Regex personnalisée (ex: numéro IBAN)
```
Template: Custom
Pattern: [A-Z]{2}\d{2}[A-Z0-9]{1,30}
→ Trouve les formats IBAN
```

## Performances

Sur un dataset de **150 Go** :
- Scan multi-threadé (8 threads par défaut)
- Filtrage par type de fichier
- Limitation de taille de fichier
- Streaming temps réel des résultats

## Troubleshooting

### Erreur "ripgrep not found"
```bash
sudo apt install ripgrep
```

### Port déjà utilisé
Modifiez les ports dans :
- Backend : `backend/app/main.py` (ligne `uvicorn.run`)
- Frontend : `frontend/vite.config.ts` (server.port)

### Stats trop lent
Ajustez `max_files` dans `backend/app/services/stats.py` (ligne 17)

## Docker (optionnel)

```bash
docker-compose up --build
```

Les services seront disponibles sur les mêmes ports.
