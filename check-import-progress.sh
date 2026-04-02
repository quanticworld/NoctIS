#!/bin/bash
# Monitor Elasticsearch import progress

echo "=== Elasticsearch Import Progress ==="
echo ""

# Get document count
COUNT=$(curl -s http://localhost:9200/silver_records/_count | jq -r '.count')
echo "Documents indexed: $(printf "%'d" $COUNT)"

# Get index size
SIZE=$(curl -s http://localhost:9200/_cat/indices/silver_records?h=store.size)
echo "Index size: $SIZE"

# Get indexing rate (docs/sec)
STATS=$(curl -s http://localhost:9200/_nodes/stats/indices/indexing)
TOTAL=$(echo $STATS | jq -r '.nodes | to_entries[0].value.indices.indexing.index_total')
TIME=$(echo $STATS | jq -r '.nodes | to_entries[0].value.indices.indexing.index_time_in_millis')

if [ "$TIME" != "0" ] && [ "$TIME" != "null" ]; then
    RATE=$(echo "scale=2; $TOTAL / ($TIME / 1000)" | bc)
    echo "Average indexing rate: $RATE docs/sec"
fi

echo ""
echo "=== Elasticsearch Stats ==="
docker stats noctis-elasticsearch-1 --no-stream | tail -1

echo ""
echo "Target: 19,000,000 documents"
if [ "$COUNT" != "null" ]; then
    PERCENT=$(echo "scale=2; ($COUNT / 19000000) * 100" | bc)
    echo "Progress: ${PERCENT}%"
fi
