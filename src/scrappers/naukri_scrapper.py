import asyncio
import json
import os
from typing import Any

import httpx
from dotenv import load_dotenv


def parse_dataset_response(response: httpx.Response) -> Any:
    """Parse regular JSON and newline/concatenated JSON dataset responses."""
    try:
        return response.json()
    except json.JSONDecodeError:
        decoder = json.JSONDecoder()
        values = []
        position = 0
        text = response.text

        while position < len(text):
            while position < len(text) and text[position].isspace():
                position += 1
            if position >= len(text):
                break

            value, position = decoder.raw_decode(text, position)
            values.append(value)

        if not values:
            raise ValueError("Dataset response did not contain valid JSON.")
        return values[0] if len(values) == 1 else values


async def trigger_collection(
    base_url: str,
    collector_id: str,
    client: httpx.AsyncClient,
    headers: dict[str, str],
    payload: dict[str, Any],
) -> str:
    """Trigger a Bright Data Naukri collection and return its collection ID."""
    response = await client.post(
        f"{base_url}/trigger",
        headers=headers,
        params={"collector": collector_id, "queue_next": 1},
        json=payload,
    )
    response.raise_for_status()

    collection_id = response.json().get("collection_id")
    if not collection_id:
        raise RuntimeError("Trigger response did not contain collection_id.")

    return collection_id


async def wait_for_collection(
    base_url: str,
    collection_id: str,
    client: httpx.AsyncClient,
    headers: dict[str, str],
    poll_interval: int = 10,
    timeout: int = 300,
) -> Any:
    """Poll the collection until Bright Data returns 200 instead of 202."""
    elapsed = 0

    while elapsed < timeout:
        response = await client.get(
            f"{base_url}/dataset",
            headers=headers,
            params={"id": collection_id},
        )

        if response.status_code == 200:
            return parse_dataset_response(response)

        if response.status_code == 202:
            await asyncio.sleep(poll_interval)
            elapsed += poll_interval
            continue

        response.raise_for_status()

    raise TimeoutError(
        f"Collection {collection_id} was not ready within {timeout} seconds."
    )


async def fetch_jobs(
    collector_id: str,
    api_key: str,
    payload: dict[str, Any],
    poll_interval: int = 10,
    timeout: int = 300,
) -> Any:
    """Trigger a Naukri collection and wait for its dataset results."""
    base_url = "https://api.brightdata.com/dca"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        collection_id = await trigger_collection(
            base_url,
            collector_id,
            client,
            headers,
            payload,
        )
        print(f"Collection triggered: {collection_id}")

        return await wait_for_collection(
            base_url,
            collection_id,
            client,
            headers,
            poll_interval,
            timeout,
        )


async def naukri_job_scrapper(search_filters: dict) -> None:
    load_dotenv()
    try:
        api_key = os.getenv("BRIGHTDATA_API_TOKEN")
        collector_id = os.getenv("NAUKRI_COLLECTOR_ID")
        if not api_key:
            raise ValueError("BRIGHTDATA_API_TOKEN environment variable is not set.")
        if not collector_id:
            raise ValueError("NAUKRI_COLLECTOR_ID environment variable is not set.")

        payload = {
            "location": search_filters["location"],
            "keyword": search_filters["keyword"],
            "experience_level": search_filters["experience_level"],
            "job_type": search_filters["job_type"],
            "max_results": 2,
        }

        jobs = await fetch_jobs(collector_id, api_key, payload)
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


def naukri_formatter(jobs):
    final_jobs = []
    for job in jobs:
        final_jobs.append(
            [
                job.get("naukri_job_id") or "",
                job.get("job_title") or "",
                job.get("company") or "",
                job.get("description") or "",
                job.get("skills") or [],
            ]
        )
    return final_jobs


async def naukri_main(search_filters: dict):
    jobs = await naukri_job_scrapper(search_filters)
    if jobs is not None:
        print(jobs)
        formatted_jobs = naukri_formatter(jobs)
        return formatted_jobs
    return None
