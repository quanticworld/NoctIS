# CTI Google Dorks - Breach Intelligence

**NOTE**: Google a désactivé l'opérateur `OR` - Lancez chaque dork séparément ou utilisez des outils comme `googler`

---

## 1. TORRENTS & MAGNET LINKS ⭐

### Magnet links - Recherches séparées
```
intext:"magnet:?xt=urn:btih:" intext:"breach"
intext:"magnet:?xt=urn:btih:" intext:"leak"
intext:"magnet:?xt=urn:btih:" intext:"database"
intext:"magnet:?xt=urn:btih:" intext:"combo"
intext:"magnet:?xt=urn:btih:" intext:"collection"
intext:"magnet:?xt=urn:btih:" 2025
intext:"magnet:?xt=urn:btih:" 2026
```

### Torrents files
```
intext:"breach" filetype:torrent
intext:"leak" filetype:torrent
intext:"database" filetype:torrent
intext:"combo" filetype:torrent
intext:"compilation" filetype:torrent
```

### Torrents sur paste sites (TRÈS EFFICACE)
```
site:rentry.co intext:"magnet:"
site:rentry.co intext:".torrent"
site:telegra.ph intext:"magnet:"
site:telegra.ph intext:"torrent"
site:paste.ee "magnet:?xt"
site:ghostbin.co intext:"magnet"
```

### Index torrents
```
filetype:txt "magnet:?xt=urn:btih:"
filetype:txt ".torrent" intext:"http"
"torrent hash" intext:"database"
"torrent hash" intext:"breach"
```

---

## 2. PASTE SITES - Leaks récents ⭐⭐⭐

### Sites prioritaires 2025-2026
```
site:rentry.co intext:"leak"
site:rentry.co intext:"breach"
site:rentry.co intext:"dump"
site:telegra.ph intext:"database"
site:telegra.ph intext:"dump"
site:telegra.ph intext:"leak"
site:ghostbin.co intext:"combo"
site:ghostbin.co intext:"breach"
site:paste.ee intext:".csv"
site:paste.ee intext:".sql"
site:justpaste.it intext:"leak"
```

### Pastebin classique
```
site:pastebin.com "breach" "password"
site:pastebin.com "database leak"
site:pastebin.com "data breach"
site:pastebin.com "combo" "@"
site:pastebin.com "email:pass"
site:pastebin.com "email:password"
```

### Liens vers file hosts (TRÈS EFFICACE)
```
site:rentry.co "mega.nz"
site:rentry.co "gofile"
site:rentry.co "anonfiles"
site:telegra.ph "mega.nz"
site:telegra.ph "pixeldrain"
site:telegra.ph "gofile.io"
site:paste.ee "mega.nz/file"
site:paste.ee "gofile.io/d/"
```

### Autres paste actifs
```
site:controlc.com intext:"breach"
site:dpaste.com intext:"credentials"
site:textbin.net intext:"leak"
site:textbin.net intext:"dump"
```

---

## 3. FILE HOSTING - Direct downloads

### Mega.nz
```
site:mega.nz intext:"breach"
site:mega.nz intext:"leak"
site:mega.nz intext:"database"
"mega.nz/file/" intext:"combo"
"mega.nz/folder/" intext:"breach"
```

### File hosts actifs
```
site:gofile.io intext:"leak"
site:gofile.io intext:"breach"
site:pixeldrain.com intext:"database"
site:anonfiles.com intext:"breach"
site:file.io intext:"dump"
```

---

## 4. FRANCE SPECIFIC ⭐

### Données françaises
```
intext:"france" intext:"breach"
intext:"french" intext:"leak"
intext:".fr" intext:"dump"
site:pastebin.com "france" "téléphone"
site:pastebin.com "france" "phone"
site:pastebin.com ".fr" "adresse"
site:pastebin.com ".fr" "email"
```

### Opérateurs télécom FR (SÉPARÉS)
```
site:pastebin.com "@orange.fr"
site:pastebin.com "@wanadoo.fr"
site:pastebin.com "@free.fr"
site:pastebin.com "@sfr.fr"
site:pastebin.com "@bbox.fr"
site:pastebin.com "@laposte.net"
"@orange.fr" intext:"breach"
"@free.fr" intext:":"
```

### Numéros français
```
site:pastebin.com "06" "@"
site:pastebin.com "07" "@"
intext:"0033" intext:"breach"
"code postal" intext:"breach"
```

### Torrents FR
```
"magnet" "france"
"magnet" "french"
".torrent" ".fr" "database"
```

---

## 5. METADATA ENRICHMENT

### Dates récentes
```
intext:"breach" 2025
intext:"leak" 2026
intext:"dump" "january 2025"
intext:"dump" "february 2025"
intext:"dump" "march 2025"
```

### Taille des dumps
```
intext:"breach" "GB"
intext:"leak" "TB"
intext:"database" "100GB"
intext:"database" "1TB"
```

### Formats fichiers
```
intext:"breach" filetype:csv
intext:"leak" filetype:sql
intext:"dump" filetype:txt
intext:".csv" "breach"
intext:".sql" "dump"
```

---

## 6. FORUMS & COMMUNITIES

### Reddit
```
site:reddit.com "magnet" "leak"
site:reddit.com "magnet" "breach"
site:reddit.com "database dump"
site:reddit.com "combo list"
```

### Forums publics
```
inurl:forum "torrent" "breach"
inurl:forum "magnet" "leak"
inurl:forum "download" "database"
```

---

## 7. COLLECTIONS CONNUES

### CompilationOfManyBreaches
```
"CompilationOfManyBreaches"
"COMB"
"compilation" "breach" "torrent"
"compilation" "breach" "magnet"
"collection" "leak" "magnet"
```

### Autres collections
```
"Anti Public"
"RaidForums"
"BreachCompilation"
"Collection #1"
```

---

## 8. TELEGRAM & DISCORD

### Liens publics Telegram
```
"t.me/" "breach"
"t.me/" "leak"
"t.me/" "dump"
"telegram.me/" "database"
```

### Discord invites
```
"discord.gg/" "leak"
"discord.gg/" "breach"
"discord.gg/" "dump"
```

---

## 9. DORKS COMBINÉS SPÉCIAUX ⭐⭐⭐

### Combo paste + magnet (LANCE SÉPARÉMENT)
```
site:rentry.co "magnet" 2025
site:telegra.ph "magnet" 2026
site:paste.ee "mega.nz" "breach"
```

### Email:Password format
```
site:pastebin.com ":" "@" "breach"
site:pastebin.com ":" "@" "combo"
"email:password"
"email:pass"
```

### France + liens directs
```
site:rentry.co "france" "mega.nz"
site:telegra.ph "french" "magnet"
"france" "breach" ".torrent"
```

---

## TIPS D'UTILISATION

1. **PAS de OR** : Lance chaque dork séparément (Google bloque OR)
2. **Date range** : Utilise `after:2025-01-01` pour filtrer par date
3. **Exclude** : Ajoute `-site:exemple.com` pour exclure des sites
4. **Quotes** : Utilise `"exact phrase"` pour des matchs exacts
5. **Wildcards** : `*` ne fonctionne plus sur Google

## DORKS À LANCER EN PRIORITÉ

**TOP 5 - Résultats garantis** :
```
site:rentry.co "magnet"
site:telegra.ph "mega.nz"
site:pastebin.com "@orange.fr"
site:paste.ee "mega.nz/file"
"magnet:?xt=urn:btih:" intext:"breach"
```

## AUTOMATION

### Avec googler (recommandé)
```bash
# Installation
pip install googler

# Single dork
googler --np -n 50 'site:rentry.co "magnet"'

# Multiple dorks
cat << 'EOF' > dorks.txt
site:rentry.co "magnet"
site:telegra.ph "mega.nz"
site:paste.ee "gofile"
EOF

while IFS= read -r dork; do
  echo "[+] Searching: $dork"
  googler --np -n 20 "$dork" >> results_$(date +%Y%m%d).txt
  sleep 5
done < dorks.txt
```

### Avec Python
```python
from googlesearch import search
import time

dorks = [
    'site:rentry.co "magnet"',
    'site:telegra.ph "mega.nz"',
    'site:pastebin.com "@orange.fr"'
]

for dork in dorks:
    print(f"[+] {dork}")
    for url in search(dork, num_results=20):
        print(url)
    time.sleep(5)
```

### Monitoring continu
```bash
#!/bin/bash
# monitor_breaches.sh
while true; do
  googler --np -n 10 'site:rentry.co "magnet"' | grep -E 'http|https' >> new_leaks.txt
  sleep 3600  # Check every hour
done
```

---

**DISCLAIMER** : Ces dorks sont pour la CTI (Cyber Threat Intelligence) et la recherche en sécurité défensive uniquement.
