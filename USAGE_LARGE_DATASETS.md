# Using NoctIS with Large Datasets (30M+ documents)

This guide explains how to configure NoctIS for optimal performance with large datasets on systems with limited RAM (24GB).

## 🔧 Configuration for Large Datasets

### 1. Typesense Timeout

The default connection timeout (5s) is too short for large datasets. Update your configuration:

**Option A: Using .env file**
```bash
cp .env.example .env
# Edit .env and set:
TYPESENSE_CONNECTION_TIMEOUT=300
```

**Option B: Direct edit**
Edit `backend/app/config.py` line 30:
```python
typesense_connection_timeout: int = 300  # 5 minutes
```

### 2. Using Existing Data Volume

If you have pre-imported data on an external volume:

1. **Locate your data directory**
   - Example: `/home/quantic/NoctIS/data` (1TB USB drive)
   - This directory should contain Typesense's data files

2. **Edit docker-compose.yml**
   ```yaml
   typesense:
     volumes:
       # Comment out the default volume:
       # - typesense-data:/data
       # Add your external volume path:
       - /home/quantic/NoctIS/data:/data
   ```

### 3. Memory Optimization

For systems with 24GB RAM and 30M documents:

**Estimated memory usage:**
- Typesense: 18-22 GB (for 30M records with 6 fields)
- FastAPI/Python: ~2 GB
- OS: ~2 GB

**Optimization in docker-compose.yml:**
```yaml
typesense:
  command: >
    --data-dir /data
    --api-key=noctis_dev_key_change_in_prod
    --enable-cors
    --cache-size-mb=8000          # Limit cache to 8GB
    --healthy-read-lag=1000        # Increase tolerance for lag
    --healthy-write-lag=1000
```

### 4. Startup Behavior

With the new health check retry mechanism:

1. **Typesense starts** → begins loading 30M records into memory (2-3 minutes)
2. **FastAPI waits** → checks health every 5 seconds, up to 60 attempts (5 minutes)
3. **Collections initialized** → schemas verified/created
4. **Stats displayed** → shows document counts for each collection
5. **Ready to serve** ✅

**Example startup logs:**
```
============================================================
🚀 Starting NoctIS - OSINT Red Team Toolbox
============================================================
⏳ Waiting for Typesense to be ready...
⏳ Typesense not ready yet (attempt 1/60), retrying in 5s...
⏳ Typesense not ready yet (attempt 2/60), retrying in 5s...
✅ Typesense is healthy (attempt 3/60)
📦 Initializing Typesense collections...
✅ Collections initialized: {...}
   📊 silver_records: 30,000,000 documents
   📊 master_records: 15,000,000 documents
   📊 conflicts: 1,234 documents
============================================================
🎯 NoctIS is ready to serve requests!
============================================================
```

## 🚀 Starting NoctIS

### Development Mode (with existing data)

```bash
# Stop any running containers
docker-compose down

# Start services
docker-compose up

# Monitor logs in separate terminals:
# Terminal 1 - Typesense logs
docker-compose logs -f typesense

# Terminal 2 - Backend logs
docker-compose logs -f backend

# Terminal 3 - Memory usage
watch -n 2 'docker stats --no-stream'
```

### First-time Setup with Existing Data

```bash
# 1. Stop everything
docker-compose down -v

# 2. Edit docker-compose.yml to point to your data volume
nano docker-compose.yml
# Uncomment: - /home/quantic/NoctIS/data:/data

# 3. Start services
docker-compose up -d

# 4. Monitor startup
docker-compose logs -f
```

## 🐛 Troubleshooting

### Error 500 at Startup

**Symptom:** FastAPI fails with "Failed to initialize Typesense"

**Cause:** Typesense hasn't finished loading data yet

**Solution:** The new retry mechanism should handle this automatically. If it still fails:
1. Check timeout: should be 300+ seconds
2. Check memory: `docker stats` - Typesense should have <20GB
3. Check logs: `docker-compose logs typesense`

### Out of Memory (OOM)

**Symptom:** Typesense container crashes or system freezes

**Solutions:**
1. **Reduce cache size** in docker-compose.yml:
   ```yaml
   --cache-size-mb=6000  # Reduce from 8000 to 6000
   ```

2. **Add swap space** (temporary):
   ```bash
   sudo fallocate -l 8G /swapfile
   sudo chmod 600 /swapfile
   sudo mkswap /swapfile
   sudo swapon /swapfile
   ```

3. **Use external memory** (if available):
   - Upgrade RAM to 32GB+
   - Use a server with more memory

### Slow Queries

**Symptom:** Searches take 5+ seconds

**Causes:**
- Cache not warmed up yet
- Too many fields indexed
- Complex filters

**Solutions:**
1. **Warm up cache** by running common queries after startup
2. **Limit indexed fields** in schema (only index searchable fields)
3. **Use pagination** (don't fetch all results at once)

## 📊 Monitoring

### Check Current Stats

**Via API:**
```bash
curl http://localhost:8000/api/v1/mdm/stats
```

**Via Typesense directly:**
```bash
curl http://localhost:8108/collections/master_records
```

### Memory Usage

```bash
# Docker container memory
docker stats typesense --no-stream

# System memory
free -h

# Typesense process
docker exec typesense ps aux
```

## 🔒 Production Deployment

For production with large datasets:

1. **Use dedicated server** with 32GB+ RAM
2. **Update API key** in docker-compose.prod.yml
3. **Set up monitoring** (Prometheus + Grafana)
4. **Configure backups** for Typesense data directory
5. **Use SSD** for data volume (faster I/O)

## 📚 Resources

- [Typesense Performance Tuning](https://typesense.org/docs/latest/guide/system-requirements.html)
- [NoctIS Documentation](./IMPLEMENTATION_STATUS.md)
- [MDM Architecture](./backend/app/services/mdm_service.py)
