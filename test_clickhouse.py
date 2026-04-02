#!/usr/bin/env python3
"""
ClickHouse Integration Test

This script tests the ClickHouse service integration:
1. Connection test
2. Table verification
3. Bulk insert performance test
4. Search/query test
5. Fuzzy matching test

Usage:
    python3 test_clickhouse.py
"""
import asyncio
import sys
import time
from datetime import datetime

# Add backend to path
sys.path.insert(0, 'backend')

from app.services.clickhouse_service import clickhouse_service
from app.config import settings


async def test_connection():
    """Test ClickHouse connection"""
    print("=" * 60)
    print("TEST 1: Connection Health Check")
    print("=" * 60)

    health = await clickhouse_service.health_check()
    print(f"Status: {health['status']}")
    print(f"Server: {health.get('server_status', 'unknown')}")

    if health['status'] != 'healthy':
        print("❌ Connection failed!")
        return False

    print("✅ Connection successful!")
    return True


async def test_table_initialization():
    """Test table creation/verification"""
    print("\n" + "=" * 60)
    print("TEST 2: Table Initialization")
    print("=" * 60)

    results = await clickhouse_service.initialize_collections()

    for table, exists in results.items():
        status = "✅" if exists else "❌"
        print(f"{status} Table '{table}': {'EXISTS' if exists else 'NOT FOUND'}")

    all_exist = all(results.values())
    if not all_exist:
        print("\n⚠️  Some tables missing. Run docker-compose up to initialize.")
        return False

    print("\n✅ All tables verified!")
    return True


async def test_bulk_insert():
    """Test bulk insert performance"""
    print("\n" + "=" * 60)
    print("TEST 3: Bulk Insert Performance")
    print("=" * 60)

    # Generate test data
    num_docs = 10000
    print(f"Generating {num_docs:,} test documents...")

    documents = []
    for i in range(num_docs):
        doc = {
            'id': f'test_{i}',
            'source_id': f'test_source_{i}',
            'breach_name': 'test_breach',
            'source_file': 'test_clickhouse.py',
            'imported_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),  # String format for ClickHouse
            'email': f'user{i}@example.com',
            'username': f'user{i}',
            'first_name': f'John{i}',
            'last_name': f'Doe{i}',
            'phone': f'+336{i:08d}',
            'city': 'Paris',
            'country': 'France',
        }
        documents.append(doc)

    print(f"Inserting {num_docs:,} documents...")
    start_time = time.time()

    result = await clickhouse_service.import_documents(
        documents=documents,
        collection_name='silver_records'
    )

    elapsed = time.time() - start_time
    docs_per_sec = num_docs / elapsed if elapsed > 0 else 0

    print(f"✅ Inserted: {result['success']:,} documents")
    print(f"❌ Failed: {result['failed']:,} documents")
    print(f"⏱️  Time: {elapsed:.2f}s")
    print(f"🚀 Speed: {docs_per_sec:,.0f} docs/sec")

    if result['failed'] > 0:
        print(f"Errors: {result.get('error', 'Unknown')}")

    return result['success'] > 0


async def test_search():
    """Test search functionality"""
    print("\n" + "=" * 60)
    print("TEST 4: Search & Query")
    print("=" * 60)

    # Test 1: Count all test records
    print("\n→ Counting test records...")
    count_result = clickhouse_service.client.count(
        index='silver_records',
        query={"term": {"breach_name": "test_breach"}}
    )
    print(f"  Found {count_result['count']:,} test records")

    # Test 2: Exact search
    print("\n→ Exact email search...")
    search_result = await clickhouse_service.search(
        query='user0@example.com',
        search_fields=['email'],
        collection_name='silver_records',
        typo_tolerance=False,
        per_page=5
    )
    print(f"  Found {search_result['found']} results")
    print(f"  Search time: {search_result['search_time_ms']}ms")

    if search_result['hits']:
        print(f"  First result: {search_result['hits'][0]['document']['email']}")

    # Test 3: Fuzzy search (with typo)
    print("\n→ Fuzzy search (typo: 'user0@exanple.com' → 'user0@example.com')...")
    fuzzy_result = await clickhouse_service.search(
        query='user0@exanple.com',  # Intentional typo: exanple
        search_fields=['email'],
        collection_name='silver_records',
        typo_tolerance=True,
        per_page=5
    )
    print(f"  Found {fuzzy_result['found']} results")
    print(f"  Search time: {fuzzy_result['search_time_ms']}ms")

    if fuzzy_result['hits']:
        print(f"  First result: {fuzzy_result['hits'][0]['document']['email']}")
        print("  ✅ Fuzzy matching works!")

    return True


async def test_stats():
    """Test collection statistics"""
    print("\n" + "=" * 60)
    print("TEST 5: Collection Statistics")
    print("=" * 60)

    stats = await clickhouse_service.get_collection_stats('silver_records')

    if stats:
        print(f"Collection: {stats['name']}")
        print(f"Documents: {stats['num_documents']:,}")
        print(f"Disk size: {stats.get('size', 'N/A')}")
        print(f"Rows: {stats.get('rows', 'N/A'):,}")
        print("✅ Stats retrieved!")
        return True
    else:
        print("❌ Failed to get stats")
        return False


async def cleanup():
    """Clean up test data"""
    print("\n" + "=" * 60)
    print("CLEANUP: Removing Test Data")
    print("=" * 60)

    print("Deleting test records...")
    result = clickhouse_service.client.delete_by_query(
        index='silver_records',
        query={"term": {"breach_name": "test_breach"}}
    )

    print(f"✅ Cleanup initiated (mutation: {result.get('mutation', 'pending')})")
    print("   Note: ClickHouse mutations are async, data will be deleted shortly.")


async def main():
    """Run all tests"""
    print("\n" + "#" * 60)
    print("# ClickHouse Integration Test Suite")
    print("#" * 60)
    print(f"Host: {settings.clickhouse_host}:{settings.clickhouse_port}")
    print(f"Database: {settings.clickhouse_database}")
    print("#" * 60)

    try:
        # Run tests
        tests = [
            ("Connection", test_connection),
            ("Table Initialization", test_table_initialization),
            ("Bulk Insert", test_bulk_insert),
            ("Search & Query", test_search),
            ("Statistics", test_stats),
        ]

        results = []
        for name, test_func in tests:
            try:
                result = await test_func()
                results.append((name, result))
            except Exception as e:
                print(f"\n❌ Test '{name}' failed with error: {e}")
                import traceback
                traceback.print_exc()
                results.append((name, False))

                # Stop on critical failures
                if name in ["Connection", "Table Initialization"]:
                    print("\n⚠️  Critical test failed, stopping.")
                    break

        # Cleanup
        await cleanup()

        # Summary
        print("\n" + "=" * 60)
        print("TEST SUMMARY")
        print("=" * 60)

        passed = sum(1 for _, result in results if result)
        total = len(results)

        for name, result in results:
            status = "✅ PASS" if result else "❌ FAIL"
            print(f"{status} - {name}")

        print("=" * 60)
        print(f"Results: {passed}/{total} tests passed")

        if passed == total:
            print("🎉 All tests passed!")
            return 0
        else:
            print("⚠️  Some tests failed")
            return 1

    except KeyboardInterrupt:
        print("\n\n⚠️  Tests interrupted by user")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
