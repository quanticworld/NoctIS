#!/usr/bin/env python3
"""
Test script to demonstrate conflict detection in MDM
"""
import requests
import csv
import time

API_BASE = "http://localhost:8000/api/v1"

def import_csv(file_path, breach_name):
    """Import a CSV file to silver records"""

    documents = []

    # CSV format: phone,fb_id,first_name,last_name,gender,city1,city2,status,job,date
    with open(file_path, 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        for row in reader:
            if len(row) < 10:
                continue

            phone, fb_id, first_name, last_name, gender, city1, city2, status, job, date = row[:10]

            # Skip empty rows
            if not phone and not fb_id:
                continue

            doc = {
                'phone': phone.strip() if phone else None,
                'username': fb_id.strip() if fb_id else None,
                'first_name': first_name.strip() if first_name else None,
                'last_name': last_name.strip() if last_name else None,
                'gender': gender.strip() if gender else None,
                'city': city1.strip() if city1 else (city2.strip() if city2 else None),
                'company': job.strip() if job else None,
            }

            # Remove None values
            doc = {k: v for k, v in doc.items() if v}

            if doc:
                documents.append(doc)

    print(f"\n📤 Importing {len(documents)} documents from {breach_name}...")

    # Import via API
    response = requests.post(
        f"{API_BASE}/import/silver",
        json={
            'documents': documents,
            'breach_name': breach_name,
            'source_file': file_path
        }
    )

    if response.status_code == 200:
        result = response.json()
        print(f"✅ Imported: {result.get('imported', 0)} | Failed: {result.get('failed', 0)}")
        return result
    else:
        print(f"❌ Import failed: {response.status_code}")
        print(response.text)
        return None

def run_deduplication():
    """Run deduplication to detect conflicts"""
    print("\n🔄 Running deduplication...")

    response = requests.post(
        f"{API_BASE}/mdm/deduplicate",
        params={'batch_size': 100}
    )

    if response.status_code == 200:
        result = response.json()
        print(f"✅ Deduplication complete:")
        print(f"   - Processed: {result.get('processed', 0)}")
        print(f"   - New masters: {result.get('new_masters', 0)}")
        print(f"   - Merged: {result.get('merged', 0)}")
        print(f"   - Errors: {result.get('errors', 0)}")
        return result
    else:
        print(f"❌ Deduplication failed: {response.status_code}")
        return None

def get_conflicts():
    """Get pending conflicts"""
    print("\n⚠️  Checking for conflicts...")

    response = requests.get(
        f"{API_BASE}/mdm/conflicts",
        params={'status': 'pending'}
    )

    if response.status_code == 200:
        conflicts = response.json()
        print(f"✅ Found {len(conflicts)} conflicts")

        for conflict in conflicts:
            print(f"\n📋 Conflict ID: {conflict['id']}")
            print(f"   Field: {conflict['field_name']}")
            print(f"   Source 1 ({conflict['existing_source']}): {conflict['existing_value']}")
            print(f"   Source 2 ({conflict['new_source']}): {conflict['new_value']}")

        return conflicts
    else:
        print(f"❌ Failed to get conflicts: {response.status_code}")
        return []

def main():
    print("=" * 60)
    print("🧪 NoctIS MDM Conflict Detection Test")
    print("=" * 60)

    # Import first source
    result1 = import_csv('/home/quantic/tmp/mdtest/src1.csv', 'Source1')
    if not result1:
        return

    # Import second source
    result2 = import_csv('/home/quantic/tmp/mdtest/src2.csv', 'Source2')
    if not result2:
        return

    # Wait a bit for indexing
    print("\n⏳ Waiting for indexing...")
    time.sleep(2)

    # Run deduplication
    dedup_result = run_deduplication()
    if not dedup_result:
        return

    # Check for conflicts
    conflicts = get_conflicts()

    print("\n" + "=" * 60)
    print(f"✨ Test complete! Found {len(conflicts)} conflict(s)")
    print("=" * 60)

if __name__ == "__main__":
    main()
