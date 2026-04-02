#!/usr/bin/env python3
"""
Generate synthetic breach data for testing NoctIS performance
Creates realistic CSV files with millions of rows
"""
import csv
import random
from faker import Faker
from pathlib import Path

# Initialize Faker with French locale
fake = Faker('fr_FR')

# Configuration
OUTPUT_DIR = Path('/home/quantic/NoctIS/breaches/raw')
OUTPUT_FILE = OUTPUT_DIR / 'synthetic_20M.csv'
NUM_ROWS = 20_000_000  # 20 million rows
BATCH_SIZE = 100_000

# Sample data
COMPANIES = ['Google', 'Microsoft', 'Apple', 'Amazon', 'Meta', 'Tesla', 'Airbus', 'Total', 'LVMH', 'Carrefour']
CITIES = ['Paris', 'Lyon', 'Marseille', 'Toulouse', 'Nice', 'Nantes', 'Bordeaux', 'Lille', 'Strasbourg', 'Rennes']

def generate_row(index):
    """Generate a single row of synthetic data"""
    return {
        'phone': fake.phone_number(),
        'facebook_id': f'1000{random.randint(10000000, 99999999)}',
        'first_name': fake.first_name(),
        'last_name': fake.last_name(),
        'gender': random.choice(['male', 'female', 'other']),
        'city': random.choice(CITIES),
        'address': fake.street_address().replace('\n', ' '),
        'relationship': random.choice(['Single', 'Married', 'Divorced', 'In a relationship', '']),
        'company': random.choice(COMPANIES) if random.random() > 0.3 else '',
        'birth_date': fake.date_of_birth(minimum_age=18, maximum_age=80).strftime('%m/%d/%Y'),
        'email': fake.email() if random.random() > 0.2 else '',
        'username': fake.user_name() if random.random() > 0.5 else '',
    }

def main():
    """Generate the CSV file"""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    print(f"Generating {NUM_ROWS:,} rows of synthetic data...")
    print(f"Output: {OUTPUT_FILE}")

    with open(OUTPUT_FILE, 'w', newline='', encoding='utf-8') as f:
        # No header - simulating real breach files
        writer = csv.DictWriter(f, fieldnames=[
            'phone', 'facebook_id', 'first_name', 'last_name', 'gender',
            'city', 'address', 'relationship', 'company', 'birth_date', 'email', 'username'
        ])

        for i in range(NUM_ROWS):
            writer.writerow(generate_row(i))

            if (i + 1) % BATCH_SIZE == 0:
                progress = ((i + 1) / NUM_ROWS) * 100
                print(f"Progress: {i+1:,}/{NUM_ROWS:,} ({progress:.1f}%)")

    file_size_mb = OUTPUT_FILE.stat().st_size / (1024 * 1024)
    print(f"\n✅ Done! Generated {NUM_ROWS:,} rows ({file_size_mb:.1f} MB)")
    print(f"   File: {OUTPUT_FILE}")

if __name__ == '__main__':
    main()
