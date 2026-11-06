import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from faker import Faker


parser = argparse.ArgumentParser(description="Générer des logs SecuriLog fictifs.")
parser.add_argument("--count", type=int, default=100)
args = parser.parse_args()

if args.count < 2:
    parser.error("--count doit être au moins égal à 2")

fake = Faker()
batch_id = f"faker-{uuid4().hex[:12]}"
output = Path("/tmp") / f"{batch_id}.jsonl"

with output.open("w", encoding="utf-8") as file:
    for number in range(1, args.count + 1):
        failure = number % 2 == 0
        event = {
            "@timestamp": datetime.now(timezone.utc).isoformat(),
            "event_id": f"{batch_id}-{number:04d}",
            "service": "portail-demo",
            "user": {"name": fake.user_name()},
            "event": {
                "category": "authentication",
                "outcome": "failure" if failure else "success",
            },
            "source": {"ip": f"192.0.2.{fake.random_int(min=1, max=254)}"},
            "message": "Connexion échouée" if failure else "Connexion réussie",
        }
        file.write(json.dumps(event, ensure_ascii=False) + "\n")

print(output)
