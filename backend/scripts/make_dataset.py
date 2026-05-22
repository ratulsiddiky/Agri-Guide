import random
import sys
from pathlib import Path
from datetime import datetime, timedelta

import bcrypt

# Allow running as a script: `python scripts/make_dataset.py`
# by ensuring the repo root (where `config.py` lives) is on sys.path.
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from config import get_db


db = get_db()


def main():
    db.farms.drop()
    db.users.drop()
    db.blacklist.drop()

    print("Generating Smart Agriculture Dataset...")

    users_data = []
    usernames = ["admin_user", "farmer_john", "farmer_mary"]
    roles = ["admin", "user", "user"]

    for index, username in enumerate(usernames):
        hashed_password = bcrypt.hashpw(b"password123", bcrypt.gensalt()).decode("utf-8")
        users_data.append(
            {
                "username": username,
                "email": f"{username}@smartagri.com",
                "password": hashed_password,
                "role": roles[index],
                "contact_preference": "email",
                "is_verified": True,
                "created_at": datetime.utcnow(),
            }
        )

    inserted_users = db.users.insert_many(users_data)
    user_ids = inserted_users.inserted_ids
    print(f"  Created {len(user_ids)} users.")

    crop_types = ["Wheat", "Corn", "Vineyard", "Soybeans", "Potatoes"]
    areas = ["Belfast", "Derry", "Lisburn", "Newry", "Armagh"]
    postcodes = ["BT7 1NN", "BT48 7NL", "BT28 1AB", "BT35 6PB", "BT60 1NT"]
    base_lat = 54.5
    base_lng = -6.5
    farms_data = []

    for farm_index in range(50):
        owner_id = random.choice(user_ids[1:])
        area_index = random.randint(0, 4)
        base_date = datetime(2025, 1, 1) + timedelta(days=random.randint(0, 60))

        sensors = []
        for sensor_index in range(random.randint(2, 5)):
            sensor_type = random.choice(["Soil Moisture", "Temperature", "pH Level"])
            readings = []
            for reading_index in range(7):
                reading_time = base_date + timedelta(days=reading_index)
                readings.append(
                    {
                        "timestamp": reading_time,
                        "value": round(random.uniform(10.0, 60.0), 2),
                    }
                )

            sensors.append(
                {
                    "sensor_id": f"SEN-{farm_index}-{sensor_index}",
                    "type": sensor_type,
                    "status": random.choice([True, True, False]),
                    "readings": readings,
                }
            )

        weather_logs = []
        for weather_index in range(3):
            log_time = base_date + timedelta(days=weather_index)
            weather_logs.append(
                {
                    "timestamp": log_time,
                    "temperature_celsius": round(random.uniform(5.0, 25.0), 1),
                    "windspeed": round(random.uniform(5.0, 30.0), 1),
                    "humidity_percent": random.randint(40, 95),
                    "conditions": random.choice(["Clear", "Rain", "Cloudy", "Overcast"]),
                }
            )

        farms_data.append(
            {
                "farm_name": f"Farm Plot {farm_index + 1}",
                "owner_id": owner_id,
                "crop_type": random.choice(crop_types),
                "address": {
                    "area_name": areas[area_index],
                    "postcode": postcodes[area_index],
                },
                "location": {
                    "type": "Point",
                    "coordinates": [
                        round(base_lng + random.uniform(-1.0, 1.0), 4),
                        round(base_lat + random.uniform(-0.5, 0.5), 4),
                    ],
                },
                "sensors": sensors,
                "weather_logs": weather_logs,
                "alerts_history": [],
            }
        )

    db.farms.insert_many(farms_data)
    db.farms.create_index([("location", "2dsphere")])
    db.farms.create_index([("address.area_name", "text"), ("address.postcode", "text")])

    print("  Created 50 farms with sensors and weather logs.")
    print("  Indexes created (2dsphere + compound text).")
    print("\nDone! Login credentials for testing:")
    print("  Admin:   username=admin_user  / password=password123")
    print("  Farmer:  username=farmer_john / password=password123")
    print("  Farmer:  username=farmer_mary / password=password123")


if __name__ == "__main__":
    main()
