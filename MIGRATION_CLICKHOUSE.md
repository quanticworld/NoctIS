# Migration ClickHouse - État des lieux

**Date**: 2026-04-02
**Objectif**: Migrer de Meilisearch vers ClickHouse pour améliorer les performances d'import (10k → 500k+ lignes/sec)

---

## 📊 Architecture Actuelle

### Stack Technique
- **Backend**: Python 3.11+ / FastAPI / WebSocket
- **Search Engine**: Meilisearch v1.7
- **Frontend**: Vue 3 / TypeScript / Vite / Tailwind CSS
- **Data Processing**: Pandas / asyncio

### Services Docker
```yaml
backend:     Port 8000, uvicorn --reload
frontend:    Port 5173, npm run dev
meilisearch: Port 7700, 4GB max indexing memory
```

### Configuration Meilisearch (à remplacer)
- **Batch size**: 100k documents
- **Mode async**: Activé (pas d'attente après indexing)
- **Timeout**: 600s (10 min)
- **Storage**: Volume externe `/media/.../meilisearch:/meili_data`

---

## 🔑 Features Critiques à Préserver

### 1. **MDM (Master Data Management)** ⚠️ CRITIQUE
Service de déduplication et résolution d'entités.

**Fichier**: `backend/app/services/mdm_service.py`

#### Concepts MDM
- **Silver Records**: Données brutes importées (collection `silver_records`)
- **Master Records**: Entités dédupliquées (collection `master_records`)
- **Conflicts**: Conflits de fusion à résoudre manuellement (collection `conflicts`)

#### Stratégies de matching (avec scores de confiance)
```python
MATCH_STRATEGIES = {
    'email_exact': {'confidence': 95, 'keys': ['email']},
    'phone_firstname': {'confidence': 85, 'keys': ['phone', 'first_name']},
    'phone_lastname': {'confidence': 85, 'keys': ['phone', 'last_name']},
    'email_username': {'confidence': 80, 'keys': ['email', 'username']},
    'fullname_birthdate': {'confidence': 75, 'keys': ['full_name', 'birth_date']},
    'username_breach': {'confidence': 50, 'keys': ['username', 'breach_name']},
}
```

#### Workflow MDM
1. **Import to Silver** (`import_to_silver()`)
   - Génère `source_id` déterministe (hash du contenu + breach)
   - Upsert automatique (même contenu = même ID)
   - Bulk import vers `silver_records`

2. **Deduplication** (`process_silver_deduplication()`)
   - Parcourt silver records non linkés
   - Pour chaque record:
     - Cherche master matching via stratégies
     - Si match → merge vers master existant
     - Sinon → créé nouveau master
   - Gère conflits de données (valeurs différentes pour même champ)

3. **Master Status**
   - `golden`: Confiance ≥ 90% (multi-sources validées)
   - `silver`: Confiance < 90% (source unique ou données partielles)

#### API MDM Endpoints
- `GET /mdm/stats` - Statistiques silver/master
- `POST /mdm/import` - Import direct vers silver
- `POST /mdm/deduplicate` - Lance déduplication
- `GET /mdm/breaches` - Liste breaches avec counts
- `DELETE /mdm/breaches/{name}` - Supprime breach
- `GET /mdm/masters` - Liste masters avec filtres
- `DELETE /mdm/clear-all` - Purge toutes les données

#### Champs Master Record
```python
{
    'id': UUID,
    'status': 'golden|silver',
    'confidence_score': 0-100,
    'created_at': timestamp,
    'updated_at': timestamp,
    'validated_by': 'auto|manual',
    'matching_keys': ['email:...', 'phone+fn:...'],
    'silver_ids': [source_id, ...],
    'source_count': int,
    'breach_names': ['LinkedIn', 'Adobe'],
    'first_seen': timestamp,
    'last_seen': timestamp,

    # Data fields
    'email', 'username', 'phone', 'ip_address',
    'full_name', 'first_name', 'last_name', 'gender', 'birth_date',
    'address', 'city', 'country', 'zip_code',
    'company', 'job_title', 'social_media', 'website',
    'passwords': [],        # Array de passwords
    'password_hashes': [],  # Array de hashes
}
```

---

### 2. **Import Service avec WebSocket Streaming** ⚠️ CRITIQUE

**Fichier**: `backend/app/services/import_service.py`

#### Features
- **Parsing CSV robuste**: Détection auto encoding/delimiter
- **Auto-fix malformé**: Répare dates avec commas, addresses mal échappées
- **Progress streaming**: Updates temps réel via WebSocket
- **Resumable imports**: Support skip_lines pour reprendre
- **Cancellation**: Support interruption utilisateur
- **Column mapping**: Mapping flexible `col_0 → email`, etc.

#### Workflow Import
1. **Analyze CSV** (`file_service.analyze_csv()`)
   - Détecte encoding (chardet)
   - Détecte delimiter (`,`, `;`, `\t`)
   - Compte total lignes
   - Sample preview

2. **Line-by-line parsing**
   - Fix malformed lines avec heuristiques
   - Skip lignes invalides (log errors)
   - Batch accumulation

3. **Transform & Import**
   - Transform row → document via `column_mapping`
   - Batch import vers MDM (`import_to_silver()`)
   - Progress updates every 1000 rows

4. **WebSocket Protocol**
```json
{"status": "analyzing", "message": "...", "progress": 0}
{"status": "importing", "imported": 50000, "failed": 12, "progress": 45, "total_rows": 1000000}
{"status": "completed", "imported": 999988, "failed": 12, "fixed": 234, "progress": 100}
```

#### API Import Endpoints
- `WS /import/stream` - WebSocket streaming import
- `POST /import/preview` - Preview mapping (10 rows)
- `POST /import/cancel` - Cancel active import

---

### 3. **Search API** ⚠️ CRITIQUE

**Fichier**: `backend/app/routers/search.py`

#### Features
- **Multi-field search**: Recherche sur tous les champs
- **Typo tolerance**: Correction fautes frappe
- **Prefix matching**: Recherche préfixe
- **Filtering**: Filtres par champ (Typesense format)
- **Pagination**: Page/per_page
- **Facets**: Agrégations (breach_name, domain, etc.)

#### Search Fields
```python
['email', 'username', 'phone', 'first_name', 'last_name', 'full_name',
 'gender', 'address', 'city', 'country', 'zip_code', 'company',
 'job_title', 'social_media', 'website', 'domain', 'notes']
```

#### API Search Endpoints
- `POST /search/query` - Recherche principale
- `POST /search/multi-query` - Multi-search
- `GET /search/stats` - Stats collection
- `GET /search/facets` - Facet counts
- `GET /search/health` - Health check
- `GET /search/initialization-status` - Init status

---

### 4. **Frontend Integration**

**Store**: `frontend/src/stores/typesense.ts`

#### State Management
```typescript
{
  searchResults: SearchResponse | null,
  collectionStats: CollectionStats | null,
  loading: boolean,
  error: string | null
}
```

#### Actions
- `search(params)` - Execute search
- `fetchCollectionStats()` - Get doc count
- `initialize()` - Initialize collections
- `clearResults()` - Reset state

**View**: `frontend/src/views/TypesenseSearchView.vue`

#### UI Features
- **Global search bar** (fuzzy across all fields)
- **Advanced filters** (first_name, last_name, email, phone, city, country, company, breach_name, domain)
- **Results table** avec highlights
- **Pagination**
- **Stats display** (total docs, search time)

---

### 5. **Background Import Service**

**Fichier**: `backend/app/services/background_import_service.py`

#### Features
- **Job persistence**: Sauvegarde état import (JSON)
- **Resume capability**: Reprend imports interrompus
- **Status tracking**: pending/running/completed/failed/cancelled
- **Progress tracking**: Lines processed, errors

#### Job Structure
```python
{
    'id': UUID,
    'status': 'pending|running|completed|failed|cancelled',
    'file_path': str,
    'breach_name': str,
    'column_mapping': dict,
    'total_lines': int,
    'processed_lines': int,
    'created_at': timestamp,
    'started_at': timestamp,
    'completed_at': timestamp,
    'error': str | None,
}
```

---

### 6. **File Service**

**Fichier**: `backend/app/services/file_service.py`

#### Features
- **CSV Analysis** (`analyze_csv()`)
  - Encoding detection (chardet)
  - Delimiter detection
  - Line counting (wc -l)
  - Sample preview (normalisé à `col_0`, `col_1`, ...)

- **File Listing** (`list_files()`)
  - Récursif avec filtres
  - Tri par date/nom/taille

---

## 🎯 Requirements pour ClickHouse

### Schema ClickHouse à créer

#### Table: silver_records
```sql
CREATE TABLE silver_records (
    id String,
    source_id String,
    breach_name String,
    source_file String,
    imported_at DateTime,
    master_id Nullable(String),

    -- Data fields
    email Nullable(String),
    username Nullable(String),
    phone Nullable(String),
    password Nullable(String),
    password_hash Nullable(String),
    ip_address Nullable(String),
    full_name Nullable(String),
    first_name Nullable(String),
    last_name Nullable(String),
    gender Nullable(String),
    birth_date Nullable(Date),
    address Nullable(String),
    city Nullable(String),
    country Nullable(String),
    zip_code Nullable(String),
    company Nullable(String),
    job_title Nullable(String),
    social_media Nullable(String),
    website Nullable(String),
    domain Nullable(String),
    notes Nullable(String),

    -- Normalized fields for fuzzy matching
    email_normalized Nullable(String),
    name_soundex Nullable(String),
    phone_normalized Nullable(String),

    -- Indexes
    INDEX idx_email email TYPE bloom_filter(0.01) GRANULARITY 1,
    INDEX idx_phone phone TYPE bloom_filter(0.01) GRANULARITY 1,
    INDEX idx_breach breach_name TYPE bloom_filter(0.01) GRANULARITY 1

) ENGINE = MergeTree()
ORDER BY (breach_name, imported_at)
PARTITION BY toYYYYMM(imported_at);
```

#### Table: master_records
```sql
CREATE TABLE master_records (
    id String,
    status Enum8('silver' = 0, 'golden' = 1),
    confidence_score Float32,
    created_at DateTime,
    updated_at DateTime,
    validated_by String,
    matching_keys Array(String),
    silver_ids Array(String),
    source_count UInt32,
    breach_names Array(String),
    first_seen DateTime,
    last_seen DateTime,

    -- Data fields (same as silver)
    email Nullable(String),
    username Nullable(String),
    phone Nullable(String),
    passwords Array(String),
    password_hashes Array(String),
    ip_address Nullable(String),
    full_name Nullable(String),
    first_name Nullable(String),
    last_name Nullable(String),
    gender Nullable(String),
    birth_date Nullable(Date),
    address Nullable(String),
    city Nullable(String),
    country Nullable(String),
    zip_code Nullable(String),
    company Nullable(String),
    job_title Nullable(String),
    social_media Nullable(String),
    website Nullable(String),

    -- Indexes
    INDEX idx_email email TYPE bloom_filter(0.01) GRANULARITY 1,
    INDEX idx_status status TYPE set(0) GRANULARITY 1

) ENGINE = MergeTree()
ORDER BY (status, updated_at);
```

#### Table: conflicts
```sql
CREATE TABLE conflicts (
    id String,
    master_id String,
    silver_id String,
    field_name String,
    status Enum8('pending' = 0, 'resolved' = 1, 'ignored' = 2),
    existing_value String,
    new_value String,
    existing_source String,
    new_source String,
    created_at DateTime,
    resolved_at Nullable(DateTime),
    resolved_value Nullable(String),
    resolved_by Nullable(String)

) ENGINE = MergeTree()
ORDER BY (status, created_at);
```

### Fonctions de normalisation ClickHouse

```sql
-- Email normalization
CREATE FUNCTION email_normalize AS (email) -> lowerUTF8(trim(email));

-- Name soundex (phonetic matching)
CREATE FUNCTION name_soundex AS (name) -> soundex(lowerUTF8(trim(name)));

-- Phone normalization (remove spaces, dashes, +)
CREATE FUNCTION phone_normalize AS (phone) -> replaceRegexpAll(phone, '[^0-9]', '');

-- Remove accents (UTF-8 normalization)
CREATE FUNCTION remove_accents AS (text) ->
    replaceRegexpAll(
        replaceRegexpAll(text, '[àáâãäå]', 'a'),
        '[èéêë]', 'e'
    ); -- etc.
```

### Search avec fuzzy matching

```sql
-- Example: Search avec ngramDistance
SELECT *
FROM silver_records
WHERE
    ngramDistance(lowerUTF8(email), 'john@exanple.com') < 0.3  -- typo tolerance
    OR soundex(first_name) = soundex('Jon')  -- phonetic
    OR phone_normalize(phone) LIKE phone_normalize('+33 6 12 34 56 78') || '%'
LIMIT 20;
```

---

## 🚧 Points d'attention Migration

### ⚠️ Limitations ClickHouse
1. **Pas de full-text ranking** comme Meilisearch
   - Solution: ngramDistance + seuils de similarité

2. **Updates lents** (ClickHouse = append-only)
   - Solution: Materialized views pour agrégations
   - Batch updates via mutations (async)

3. **Pas de typo tolerance native**
   - Solution: ngramDistance, soundex, levenshteinDistance

### ✅ Avantages ClickHouse
1. **Import ultra-rapide**: 500k-1M lignes/sec (vs 10k Meilisearch)
2. **Compression native**: LZ4/ZSTD (économie stockage)
3. **Analytics puissants**: Agrégations, stats, facets
4. **Materialized views**: Pre-calc pour déduplication
5. **Partitioning**: Par mois/breach pour performance

---

## 📝 Plan de Migration

### Phase 1: Setup ClickHouse
- [ ] Ajouter service ClickHouse au docker-compose
- [ ] Créer schemas (silver_records, master_records, conflicts)
- [ ] Créer fonctions de normalisation
- [ ] Tests de performance import

### Phase 2: Backend Service
- [ ] Créer `clickhouse_service.py` (remplace meilisearch_service)
- [ ] Adapter API wrapper (ES-compatible)
- [ ] Implémenter fuzzy search (ngramDistance)
- [ ] Adapter MDM service pour ClickHouse

### Phase 3: Migration Progressive
- [ ] Mode dual (ClickHouse + Meilisearch en parallèle)
- [ ] Tests A/B performance
- [ ] Migration données existantes
- [ ] Switch complet vers ClickHouse

### Phase 4: Optimisations
- [ ] Materialized views pour stats
- [ ] Tuning indexes (bloom, ngram)
- [ ] Compression optimization
- [ ] Monitoring performance

---

## 📊 Performance Targets

| Metric | Meilisearch (actuel) | ClickHouse (cible) | Gain |
|--------|---------------------|-------------------|------|
| Import speed | 10k lignes/sec | 500k-1M lignes/sec | **50-100x** |
| Import 3B lignes | 83 heures | 1-2 heures | **~40-80x** |
| Storage (compressed) | N/A | 30-50% compression | TBD |
| Search latency | 50-200ms | 100-300ms | -1.5-2x* |
| Fuzzy accuracy | Native (excellent) | ngramDistance (bon) | Similar |

*Latence search légèrement supérieure mais acceptable pour le gain en import

---

## 🔍 Compatibilité API

L'objectif est de garder l'API backend **identique** pour éviter de toucher le frontend.

### Wrapper ClickHouse → API ES-like

```python
class ClickHouseClientWrapper:
    """Wrapper pour compatibilité ES/Meilisearch API"""

    def search(self, index, query, from_, size, sort, aggs):
        # Translate to ClickHouse SQL
        # Return ES-format results

    def count(self, index, query):
        # SELECT count(*) FROM ...

    def bulk(self, index, documents):
        # INSERT INTO ... VALUES

    def delete_by_query(self, index, query):
        # ALTER TABLE ... DELETE WHERE
```

---

**Prêt pour migration** ✅
Tous les composants critiques sont documentés.
