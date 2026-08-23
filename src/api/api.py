import json
import os

import requests
from dotenv import load_dotenv

load_dotenv()

api_token = os.getenv("BRIGHT_DATA_API_KEY")
if not api_token:
    raise RuntimeError(
        "Set the BRIGHTDATA_API_TOKEN environment variable before running this script."
    )

headers = {
    "Authorization": f"Bearer {api_token}",
    "Content-Type": "application/json",
}

payload = {
    "input": [
        {
            "location": "bangalore",
            "keyword": '"python developer"',
            "experience_level": "Executive",
            "job_type": "",
        },
    ],
    "limit_per_input": 1,
}

response = requests.post(
    "https://api.brightdata.com/datasets/v3/scrape?dataset_id=gd_lpfll7v5hcqtkxl6l&notify=false&include_errors=true&type=discover_new&discover_by=keyword&limit_per_input=1",
    headers=headers,
    json=payload,
)

print(f"HTTP {response.status_code}")
response.raise_for_status()

try:
    result = response.json()
except requests.exceptions.JSONDecodeError:
    # Bright Data can return one JSON object per line for multiple results.
    # result = [json.loads(line) for line in response.text.splitlines() if line.strip()]
    with open("data.json", "w") as f:
        f.write(response.text)
    print(response.text)

# print(json.dumps(result, indent=2))
