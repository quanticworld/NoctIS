# NoctIS Deployment Guide

## Problème résolu

Le backend ne pouvait pas démarrer sur l'OS du disque externe à cause de deux problèmes :

1. **Résolution DNS échouée** : Le backend tentait de se connecter à ClickHouse pendant l'import des modules, avant que le réseau Docker soit prêt
2. **Chemins de volumes incorrects** : Les volumes Docker pointaient vers des chemins valides depuis l'OS principal mais invalides depuis l'OS externe

## Solutions implémentées

### 1. Lazy Loading de MDMService

**Fichiers modifiés :**
- `backend/app/services/mdm_service.py:680-690`
- `backend/app/services/import_service.py:11`
- `backend/app/routers/mdm.py:5`
- `backend/app/websocket.py:176`

**Changement :** Le `mdm_service` n'est plus instancié au niveau module. Utilisation de `get_mdm_service()` pour lazy loading.

### 2. Retry Logic sur ClickHouse

**Fichier modifié :**
- `backend/app/services/clickhouse_service.py:13-24,430-456`

**Changement :** Ajout d'une fonction `_retry_connect()` avec exponential backoff (5 tentatives max, délai de 1s doublé à chaque fois).

### 3. Docker Compose pour OS Externe

**Fichier créé :**
- `docker-compose.external.yml`

**Différences principales :**
- Volume ClickHouse : `/home/quantic/NoctIS/data/clickhouse` au lieu de `/media/quantic/.../home/quantic/NoctIS/data/clickhouse`
- Healthcheck amélioré : 5s d'intervalle, 10 retries, 20s de start_period
- `depends_on` avec conditions : Le backend attend que ClickHouse soit healthy

### 4. Script de Déploiement

**Fichier créé :**
- `deploy-external.sh`

**Fonctionnalités :**
- Vérifie qu'on est sur l'OS externe
- Crée les répertoires nécessaires
- Build et démarre les services
- Attend que les services soient prêts
- Affiche les URLs et commandes utiles

## Déploiement

### Sur l'OS Principal (disque interne)

```bash
docker-compose up -d --build
```

### Sur l'OS Externe (disque USB)

```bash
# Booter sur l'OS du disque USB, puis :
cd /home/quantic/NoctIS
./deploy-external.sh
```

Ou manuellement :

```bash
docker-compose -f docker-compose.external.yml up -d --build
```

## Vérification

### Logs
```bash
# OS principal
docker-compose logs -f

# OS externe
docker-compose -f docker-compose.external.yml logs -f
```

### Statut des services
```bash
# OS principal
docker-compose ps

# OS externe
docker-compose -f docker-compose.external.yml ps
```

### Santé de ClickHouse
```bash
curl http://localhost:8123/ping
# Devrait retourner "Ok."
```

### Santé du Backend
```bash
curl http://localhost:8001/health
# Devrait retourner {"status":"ok"}
```

## Troubleshooting

### Backend ne démarre pas

1. Vérifier les logs ClickHouse :
   ```bash
   docker-compose -f docker-compose.external.yml logs clickhouse
   ```

2. Vérifier que ClickHouse est healthy :
   ```bash
   docker-compose -f docker-compose.external.yml ps
   ```

3. Tester la connexion manuellement :
   ```bash
   docker-compose -f docker-compose.external.yml exec backend python -c "
   from app.services.clickhouse_service import clickhouse_service
   print(clickhouse_service.client)
   "
   ```

### Volumes non accessibles

Sur l'OS externe, vérifier que le répertoire existe :
```bash
ls -la /home/quantic/NoctIS/data/clickhouse
```

Si le répertoire n'existe pas :
```bash
mkdir -p /home/quantic/NoctIS/data/clickhouse
chmod 755 /home/quantic/NoctIS/data/clickhouse
```

### Frontend ne peut pas se connecter au Backend

1. Vérifier que le backend répond :
   ```bash
   curl http://localhost:8001/health
   ```

2. Vérifier les logs du frontend :
   ```bash
   docker-compose -f docker-compose.external.yml logs frontend
   ```

3. Vérifier le réseau Docker :
   ```bash
   docker network inspect noctis_default
   ```

## Architecture des volumes

### OS Principal
```
/media/quantic/80c1859f-536b-459f-a547-d6ecf1dfceea/
└── home/
    └── quantic/
        └── NoctIS/
            └── data/
                └── clickhouse/  # Volume ClickHouse
```

### OS Externe
```
/home/
└── quantic/
    └── NoctIS/
        └── data/
            └── clickhouse/  # Volume ClickHouse (chemin direct)
```

## Performance

Avec les changements apportés :
- **Retry logic** : Le backend attend jusqu'à 31 secondes (1+2+4+8+16) pour que ClickHouse soit prêt
- **Lazy loading** : Le MDMService ne se connecte à ClickHouse que lors de la première requête
- **Healthcheck** : Docker Compose attend confirmation que ClickHouse est prêt avant de démarrer le backend

## Notes

- Le fichier `.env` doit être présent dans `/home/quantic/NoctIS/` sur l'OS externe
- Les ports utilisés : 8001 (backend), 5174 (frontend), 8123/9000 (ClickHouse)
- Le backend utilise `--reload` en mode dev, donc il redémarrera automatiquement lors des changements de code
