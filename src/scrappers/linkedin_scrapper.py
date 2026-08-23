import asyncio
import os
from typing import Any

import httpx


async def trigger_snapshot(
    base_url: str,
    dataset_id: str,
    client: httpx.AsyncClient,
    headers: dict[str, str],
    payload: list[dict[str, str]],
) -> str:

    params = {
        "dataset_id": dataset_id,
        "type": "discover_new",
        "discover_by": "keyword",
        "limit_per_input": 2,
        "format": "json",
    }

    print("Triggering snapshot...")

    response = await client.post(
        f"{base_url}/trigger",
        headers=headers,
        params=params,
        json=payload,
    )

    response.raise_for_status()

    snapshot = response.json()
    snapshot_id = snapshot.get("snapshot_id")

    if not snapshot_id:
        raise RuntimeError("Response did not contain snapshot_id.")

    print(f"✅ Snapshot triggered. ID: {snapshot_id}")

    return snapshot_id


async def wait_for_snapshot(
    base_url: str,
    client: httpx.AsyncClient,
    headers: dict[str, str],
    snapshot_id: str,
    poll_interval: int = 10,
    timeout: int = 300,
) -> list[dict[str, Any]]:
    """
    Poll the snapshot until it is ready.

    200 -> snapshot ready
    409 -> still processing
    """
    snapshot_url = f"{base_url}/snapshot/{snapshot_id}?format=json"

    print("Monitoring progress...")

    elapsed = 0

    while elapsed < timeout:
        response = await client.get(
            snapshot_url,
            headers=headers,
        )

        if response.status_code == 200:
            print("✅ Snapshot is ready!")
            return response.json()

        if response.status_code == 409:
            print(
                f"⏳ Snapshot still processing. "
                f"Polling again in {poll_interval} seconds..."
            )

            await asyncio.sleep(poll_interval)
            elapsed += poll_interval
            continue

        response.raise_for_status()

    raise TimeoutError(
        f"Snapshot {snapshot_id} was not ready within {timeout} seconds."
    )


def print_jobs(data: list[dict[str, Any]]) -> None:
    """Print relevant fields from each job record."""
    print(f"\n🎉 Successfully collected {len(data)} job records.")

    for record in data:
        job_title = record.get("job_title", "Unknown Title")
        company = record.get("company_name", "Unknown Company")
        location = record.get("location", "Unknown Location")

        print(f"- {job_title} at {company} ({location})")


async def fetch_jobs(
    base_url: str,
    dataset_id: str,
    api_key: str,
    payload: list[dict[str, str]],
) -> list[dict[str, Any]]:
    """Run the complete Bright Data job collection workflow."""
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        snapshot_id = await trigger_snapshot(
            base_url,
            dataset_id,
            client,
            headers,
            payload,
        )

        return await wait_for_snapshot(
            base_url,
            client,
            headers,
            snapshot_id,
        )


async def linkedin_main():
    base_url = "https://api.brightdata.com/datasets/v3"
    payload = [
        {
            "location": "bangalore",
            "keyword": "Full stack developer",
            "experience_level": "",
            "job_type": "",
        }
    ]
    dataset_id = os.getenv("DATASET_LINKEDIN") or ""
    try:
        api_key = os.getenv("BRIGHTDATA_API_TOKEN")
        if not api_key:
            raise ValueError("BRIGHTDATA_API_TOKEN environment variable is not set.")
        jobs = await fetch_jobs(base_url, dataset_id, api_key, payload)
        return jobs

    except httpx.HTTPError as exc:
        print(f"❌ HTTP error: {exc}")
        return None

    except TimeoutError as exc:
        print(f"❌ Timeout: {exc}")
        return None

    except Exception as exc:
        print(f"❌ Error: {exc}")
        return None


def linkedin_formatter(jobs: list):
    final_list = []
    for job in jobs:
        final_list.append(
            {
                "id": job.get("job_posting_id") or "",
                "title": job.get("job_title") or "",
                "company": job.get("company_name") or "",
                "description": job.get("job_summary"),
            }
        )
    return final_list


def linkedin_jobs_list_converter(jobs):
    final_jobs = []
    for job in jobs:
        final_jobs.append(
            [
                job.get("id") or "",
                job.get("title") or "",
                job.get("company") or "",
                job.get("description") or "",
                job.get("skills") or [],
            ]
        )
    return final_jobs
