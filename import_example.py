#!/usr/bin/env python3
"""
Example script showing how to use the MDM import API endpoint
"""
import requests
import csv
import json

API_BASE = "http://localhost:8000/api/v1/mdm"

def import_csv_to_mdm(csv_file_path, breach_name, field_mapping=None):
    """
    Import a CSV file to MDM via API

    Args:
        csv_file_path: Path to CSV file
        breach_name: Name to identify this data source
        field_mapping: Optional dict to map CSV columns to field names
                      Example: {'col1': 'email', 'col2': 'first_name'}
    """
    documents = []

    # Default field mapping (adjust based on your CSV structure)
    if field_mapping is None:
        # Example for Facebook-style CSV
        field_mapping = {
            0: 'phone',
            1: 'username',  # Facebook ID
            2: 'first_name',
            3: 'last_name',
            4: 'gender',
            5: 'city',
            6: 'country',
            7: 'relationship_status',
            8: 'company',
            9: 'date'
        }

    with open(csv_file_path, 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        for row in reader:
            if not row:  # Skip empty rows
                continue

            doc = {}

            # Map columns to fields
            if isinstance(field_mapping, dict):
                if all(isinstance(k, int) for k in field_mapping.keys()):
                    # Column index mapping
                    for col_idx, field_name in field_mapping.items():
                        if col_idx < len(row) and row[col_idx].strip():
                            doc[field_name] = row[col_idx].strip()
                else:
                    # Column name mapping (if CSV has headers)
                    for col_name, field_name in field_mapping.items():
                        if col_name in row and row[col_name].strip():
                            doc[field_name] = row[col_name].strip()

            if doc:  # Only add non-empty documents
                documents.append(doc)

    # Send to API
    print(f"📤 Importing {len(documents)} documents from {csv_file_path}...")

    response = requests.post(
        f"{API_BASE}/import",
        json={
            'documents': documents,
            'breach_name': breach_name,
            'source_file': csv_file_path
        }
    )

    if response.status_code == 200:
        result = response.json()
        print(f"✅ Success!")
        print(f"   - Imported: {result['imported']}")
        print(f"   - Failed: {result['failed']}")
        print(f"   - Breach: {result['breach_name']}")
        return result
    else:
        print(f"❌ Failed: {response.status_code}")
        print(f"   {response.text}")
        return None

def import_json_to_mdm(json_file_path, breach_name):
    """Import a JSON file containing a list of documents"""
    with open(json_file_path, 'r', encoding='utf-8') as f:
        documents = json.load(f)

    if not isinstance(documents, list):
        documents = [documents]

    print(f"📤 Importing {len(documents)} documents from {json_file_path}...")

    response = requests.post(
        f"{API_BASE}/import",
        json={
            'documents': documents,
            'breach_name': breach_name,
            'source_file': json_file_path
        }
    )

    if response.status_code == 200:
        result = response.json()
        print(f"✅ Success!")
        print(f"   - Imported: {result['imported']}")
        print(f"   - Failed: {result['failed']}")
        return result
    else:
        print(f"❌ Failed: {response.status_code}")
        print(f"   {response.text}")
        return None

def run_deduplication():
    """Trigger deduplication process"""
    print("\n🔄 Running deduplication...")

    response = requests.post(
        f"{API_BASE}/deduplicate",
        params={'batch_size': 250}
    )

    if response.status_code == 200:
        result = response.json()
        print(f"✅ Deduplication complete!")
        print(f"   - Processed: {result['processed']}")
        print(f"   - New masters: {result['new_masters']}")
        print(f"   - Merged: {result['merged']}")
        print(f"   - Errors: {result['errors']}")
        return result
    else:
        print(f"❌ Failed: {response.status_code}")
        return None

def get_conflicts():
    """Get pending conflicts"""
    response = requests.get(f"{API_BASE}/conflicts")

    if response.status_code == 200:
        conflicts = response.json()
        print(f"\n⚠️  Found {len(conflicts)} conflict(s)")
        for c in conflicts:
            print(f"   - {c['field_name']}: '{c['existing_value']}' ({c['existing_source']}) vs '{c['new_value']}' ({c['new_source']})")
        return conflicts
    else:
        print(f"❌ Failed to get conflicts: {response.status_code}")
        return []

# Example usage
if __name__ == "__main__":
    print("=" * 60)
    print("NoctIS MDM Import Example")
    print("=" * 60)

    # Example 1: Import from CSV files
    # import_csv_to_mdm('/tmp/mdtest/src1.csv', 'Source1')
    # import_csv_to_mdm('/tmp/mdtest/src2.csv', 'Source2')

    # Example 2: Import from /mnt/osint (accessible via /host/mnt/osint in container)
    # Note: When running this script ON THE HOST, use the normal path
    # When running INSIDE THE CONTAINER, use /host/mnt/osint

    # import_csv_to_mdm('/mnt/osint/breaches/linkedin.csv', 'LinkedIn')

    # Example 3: Import JSON data
    # data = [
    #     {"email": "test1@example.com", "first_name": "John", "last_name": "Doe"},
    #     {"email": "test2@example.com", "first_name": "Jane", "last_name": "Smith"}
    # ]
    # response = requests.post(
    #     f"{API_BASE}/import",
    #     json={
    #         'documents': data,
    #         'breach_name': 'ManualTest',
    #         'source_file': 'manual_entry'
    #     }
    # )
    # print(response.json())

    # Example 4: Run full workflow
    # import_csv_to_mdm('/tmp/mdtest/src1.csv', 'Source1')
    # import_csv_to_mdm('/tmp/mdtest/src2.csv', 'Source2')
    # run_deduplication()
    # get_conflicts()

    print("\n💡 Edit this script to uncomment the examples you want to run")
