# Guide : Chasse aux Torrents de Breaches

## 1. MÉTHODE PASTE SITES → MAGNET LINKS ⭐⭐⭐ (MEILLEURE)

Les liens magnet sont **postés sur paste sites**, pas sur les indexeurs torrents classiques.

### Dorks Google optimisés
```bash
# Top 3 - Résultats garantis
site:rentry.co "magnet"
site:telegra.ph "magnet"
site:paste.ee "magnet:?xt"

# Avec mots-clés
site:rentry.co "magnet" "breach"
site:rentry.co "magnet" "2025"
site:rentry.co "magnet" "collection"
site:telegra.ph "magnet" "COMB"
site:telegra.ph "magnet" "database"

# Autres paste sites
site:ghostbin.co "magnet"
site:pastebin.com "magnet:?xt=urn:btih:"
site:justpaste.it "magnet"
```

### Workflow efficace
```bash
# 1. Lance le dork
googler --np -n 50 'site:rentry.co "magnet"'

# 2. Extrait les URLs
googler --np -n 50 'site:rentry.co "magnet"' | grep -oP 'https://rentry\.co/\w+' > urls.txt

# 3. Crawl les pages pour extraire magnet links
while read url; do
  curl -s "$url" | grep -oP 'magnet:\?xt=urn:btih:[a-zA-Z0-9]+' >> magnets.txt
done < urls.txt

# 4. Déduplique
sort -u magnets.txt > magnets_clean.txt
```

---

## 2. DHT CRAWLERS / TORRENT SEARCH ENGINES

### Moteurs actifs (2025-2026)

**Clearnet** :
```
btdig.com - DHT crawler, pas de tracking
solidtorrents.to - Meta-search
torrentseeker.com - Multi-sources
snowfl.com - DHT search
```

**Recherches** :
```
"CompilationOfManyBreaches"
"COMB"
"breach 2025"
"database leak"
"combo list"
"collection"
```

### API DHT directe (avancé)
```python
# Avec libtorrent
import libtorrent as lt

session = lt.session()
params = {
    'save_path': '/tmp/',
    'storage_mode': lt.storage_mode_t.storage_mode_sparse,
}

# Ajoute magnet
magnet = "magnet:?xt=urn:btih:XXXXXX"
handle = lt.add_magnet_uri(session, magnet, params)
```

---

## 3. TELEGRAM CHANNELS (Source primaire)

Les magnet links sont **souvent postés en premier sur Telegram** avant paste sites.

### Channels publics à monitorer
```
# Recherche Telegram via Google
site:t.me "breach"
site:t.me "leak"
site:t.me "database"
site:t.me "magnet"
```

### Channels typiques (noms génériques)
```
@leaks
@breaches
@database_leaks
@combolists
@freeleaks
```

### Monitoring automatisé
```python
# Avec telethon
from telethon import TelegramClient

api_id = YOUR_API_ID
api_hash = 'YOUR_API_HASH'
client = TelegramClient('session', api_id, api_hash)

@client.on(events.NewMessage(pattern='magnet:'))
async def handler(event):
    print(f"New magnet: {event.message.text}")
```

---

## 4. REDDIT & FORUMS

### Subreddits (attention aux bans)
```
site:reddit.com "magnet" "breach"
site:reddit.com "torrent" "database"
site:reddit.com "COMB"
```

### Forums underground
```
# Recherche via Google (forums publics)
inurl:forum "magnet" "breach"
inurl:forum "torrent" "leak"
```

---

## 5. FICHIERS .TORRENT DIRECTS

Moins courant que magnet, mais existe encore.

### Recherche de fichiers
```
# Google dorks
filetype:torrent "breach"
filetype:torrent "leak"
filetype:torrent "database"

# Sur file hosts
site:mega.nz ".torrent" "breach"
site:gofile.io ".torrent"
```

### Index de .torrent
```
filetype:txt ".torrent" "http"
filetype:txt "torrent" "breach"
```

---

## 6. METADATA TRACKING

### Noms de collections connues (recherche directe)
```
"CompilationOfManyBreaches"
"COMB"
"Anti Public"
"Collection #1"
"Collection #2"
"BreachCompilation"
"RaidForums"
"Exploit.in"
"Weleakinfo"
```

### Hash tracking
Si tu connais le **info_hash** d'un torrent connu :
```python
# Recherche DHT par hash
import libtorrent as lt
import hashlib

info_hash = "XXXXXXXXXXXXXX"  # Hash SHA1 du torrent
# Recherche peers via DHT
```

---

## 7. OUTILS D'AUTOMATISATION

### A. Script de monitoring paste sites

```bash
#!/bin/bash
# monitor_magnets.sh

SITES=(
  "site:rentry.co"
  "site:telegra.ph"
  "site:paste.ee"
)

KEYWORDS=("magnet" "breach" "leak" "COMB" "database")

for site in "${SITES[@]}"; do
  for keyword in "${KEYWORDS[@]}"; do
    echo "[+] Searching: $site \"$keyword\""
    googler --np -n 20 "$site \"$keyword\"" | \
      grep -oP 'https?://[^\s]+' >> found_urls.txt
    sleep 5
  done
done

# Extrait magnet links
sort -u found_urls.txt | while read url; do
  curl -s "$url" | grep -oP 'magnet:\?xt=urn:btih:[a-zA-Z0-9]+' >> magnets.txt
done

sort -u magnets.txt > magnets_final.txt
echo "[✓] Found $(wc -l < magnets_final.txt) unique magnet links"
```

### B. Python scraper complet

```python
import requests
import re
from bs4 import BeautifulSoup
from googlesearch import search
import time

def extract_magnets(url):
    """Extrait magnet links d'une page"""
    try:
        r = requests.get(url, timeout=10)
        magnets = re.findall(r'magnet:\?xt=urn:btih:[a-zA-Z0-9]+', r.text)
        return magnets
    except:
        return []

def search_paste_sites():
    """Cherche sur paste sites"""
    dorks = [
        'site:rentry.co "magnet"',
        'site:telegra.ph "magnet"',
        'site:paste.ee "magnet"'
    ]

    all_magnets = set()

    for dork in dorks:
        print(f"[+] Searching: {dork}")
        try:
            for url in search(dork, num_results=20):
                print(f"  - Checking: {url}")
                magnets = extract_magnets(url)
                all_magnets.update(magnets)
                time.sleep(2)
        except Exception as e:
            print(f"  [!] Error: {e}")

        time.sleep(5)

    return all_magnets

if __name__ == "__main__":
    magnets = search_paste_sites()

    with open('magnets.txt', 'w') as f:
        for magnet in magnets:
            f.write(f"{magnet}\n")

    print(f"\n[✓] Found {len(magnets)} unique magnet links")
    print(f"[✓] Saved to magnets.txt")
```

### C. Telegram monitor

```python
from telethon import TelegramClient, events
import re

api_id = YOUR_API_ID
api_hash = 'YOUR_API_HASH'

client = TelegramClient('breach_monitor', api_id, api_hash)

# Liste de channels à monitorer
CHANNELS = [
    '@leaks',
    '@breaches',
    '@database_leaks'
]

@client.on(events.NewMessage(chats=CHANNELS))
async def magnet_handler(event):
    """Détecte et log les magnet links"""
    text = event.message.text

    # Cherche magnet links
    magnets = re.findall(r'magnet:\?xt=urn:btih:[a-zA-Z0-9]+', text)

    if magnets:
        print(f"\n[+] New magnet found in {event.chat.username}:")
        for magnet in magnets:
            print(f"  {magnet}")
            with open('telegram_magnets.txt', 'a') as f:
                f.write(f"{magnet}\n")

print("[*] Starting Telegram monitor...")
client.start()
client.run_until_disconnected()
```

---

## 8. DOWNLOAD & VERIFICATION

### A. Avec transmission-cli
```bash
# Ajoute magnet
transmission-remote -a "magnet:?xt=urn:btih:XXXX"

# Liste torrents
transmission-remote -l

# Monitoring
watch -n 5 transmission-remote -l
```

### B. Avec qBittorrent
```bash
# CLI
qbittorrent-nox

# Ajoute via API
curl -X POST http://localhost:8080/api/v2/torrents/add \
  -d "urls=magnet:?xt=urn:btih:XXXX"
```

### C. Vérification avant download
```python
import libtorrent as lt

# Récupère metadata sans télécharger
params = {
    'save_path': '/tmp/',
    'flags': lt.torrent_flags.upload_mode  # Pas de download
}

handle = lt.add_magnet_uri(session, magnet, params)

# Attend metadata
while not handle.has_metadata():
    time.sleep(1)

# Affiche infos
info = handle.get_torrent_info()
print(f"Name: {info.name()}")
print(f"Size: {info.total_size() / (1024**3):.2f} GB")
print(f"Files: {info.num_files()}")
```

---

## 9. FRANCE SPECIFIC

### Dorks ciblés
```bash
# Paste sites
site:rentry.co "magnet" "france"
site:rentry.co "magnet" "french"
site:telegra.ph "magnet" ".fr"

# Collections françaises
"france breach" "magnet"
"french database" "torrent"
"orange.fr" "magnet"
```

### Keywords spécifiques
```
"france"
"french"
"fr database"
"orange.fr"
"free.fr"
"sfr.fr"
"numéro france"
"téléphone france"
```

---

## 10. SÉCURITÉ & ANONYMAT

### VPN/Proxy obligatoire
```bash
# Avec transmission via SOCKS5
transmission-daemon --config-dir ~/.config/transmission \
  --proxy socks5://127.0.0.1:9050
```

### Tor pour recherche
```bash
# Googler via Tor
torsocks googler 'site:rentry.co "magnet"'

# Curl via Tor
torsocks curl -s https://rentry.co/xxxxx
```

### Vérification des fichiers
```bash
# Check avant d'ouvrir
file suspicious.txt
head -100 suspicious.txt
grep -a "email" suspicious.txt | head
```

---

## WORKFLOW COMPLET RECOMMANDÉ

```bash
# 1. Recherche paste sites
googler --np -n 50 'site:rentry.co "magnet"' > results.txt

# 2. Extrait URLs
grep -oP 'https://rentry\.co/\w+' results.txt | sort -u > urls.txt

# 3. Download pages et extrait magnets
cat urls.txt | while read url; do
  echo "[+] Fetching: $url"
  curl -s "$url" | grep -oP 'magnet:\?xt=urn:btih:[a-zA-Z0-9]+' >> magnets_raw.txt
  sleep 2
done

# 4. Clean & dedupe
sort -u magnets_raw.txt > magnets.txt

# 5. Preview metadata (optionnel)
# (utilise script Python ci-dessus)

# 6. Download sélectif
cat magnets.txt | while read magnet; do
  transmission-remote -a "$magnet"
done
```

---

## TIPS AVANCÉS

1. **Monitoring continu** : Cron job qui lance le script toutes les 6h
2. **Notification** : Envoie alerte Discord/Telegram quand nouveau magnet trouvé
3. **Base de données** : Stocke hash + metadata pour éviter doublons
4. **RSS feeds** : Certains paste sites ont des feeds (rare)
5. **Archive.org** : Parfois des vieux torrents archivés
6. **DHT bootstrap** : Ajoute plusieurs DHT nodes pour meilleure découverte

---

**DISCLAIMER** : Pour CTI et recherche défensive uniquement.
