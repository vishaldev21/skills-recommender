import asyncio
import os
import re

from dotenv import load_dotenv
from openai import AsyncOpenAI
from pydantic import BaseModel, Field

load_dotenv()

MODEL = "gpt-4.1-nano"
BATCH_SIZE = 20
MAX_CONCURRENT_REQUESTS = 10
MAX_DESCRIPTION_CHARS = 2000
MAX_RETRIES = 3

openai_api_key = os.getenv("OPENAI_API_KEY")
if not openai_api_key:
    raise RuntimeError(
        "OPENAI_API_KEY is not set. Add it to your .env file or environment."
    )

client = AsyncOpenAI(
    api_key=openai_api_key,
    timeout=120.0,
)


class JobSkills(BaseModel):
    job_id: str = Field(description="Unique ID of the job")

    skills: list[str] = Field(
        description=(
            "Technical skills, programming languages, "
            "frameworks, libraries, databases, cloud platforms, "
            "DevOps tools, and other hard technical skills "
            "explicitly mentioned or clearly required."
        )
    )


class SkillsResponse(BaseModel):
    jobs: list[JobSkills]


SYSTEM_PROMPT = """
You are an expert technical recruiter.

Your task is to extract technical skills from job descriptions.

Extract ONLY hard technical skills, including:

- Programming languages
- Frameworks
- Libraries
- Databases
- Cloud platforms
- DevOps tools
- Development tools
- Infrastructure technologies
- Data technologies
- Machine learning technologies
- APIs
- Technical platforms

DO NOT extract soft skills such as:

- Communication
- Leadership
- Teamwork
- Problem solving
- Time management
- Collaboration
- Adaptability

IMPORTANT RULES:

1. Only extract skills that are explicitly mentioned
   or clearly required by the job description.

2. Do NOT invent or infer technologies that are not supported
   by the text.

3. Normalize common variations:
   - JS -> JavaScript
   - TS -> TypeScript
   - Node -> Node.js
   - Postgres -> PostgreSQL
   - AWS -> AWS
   - GCP -> Google Cloud
   - React.js -> React

4. Return concise skill names.

5. Remove duplicate skills within each job.

6. Do not include explanations.

7. Return results for every job provided.
"""


def truncate_description(description: str) -> str:
    """
    Normalize whitespace and truncate long descriptions.
    """
    if not description:
        return ""

    description = re.sub(r"\s+", " ", description).strip()

    return description[:MAX_DESCRIPTION_CHARS]


def prepare_batches(jobs: list[dict], batch_size: int = BATCH_SIZE) -> list[list[dict]]:
    prepared_jobs = []

    for job in jobs:
        prepared_jobs.append(
            {
                "id": str(job["id"]),
                "title": job.get("title", ""),
                "company": job.get("company", ""),
                "description": truncate_description(job.get("description", "")),
            }
        )

    return [
        prepared_jobs[i : i + batch_size]
        for i in range(0, len(prepared_jobs), batch_size)
    ]


def format_batch(batch: list[dict]) -> str:
    parts = []
    for job in batch:
        parts.append(
            f"""
                --- JOB START ---
                JOB ID: {job["id"]}
                TITLE: {job["title"]}
                COMPANY: {job["company"]}

                DESCRIPTION:
                {job["description"]}

                --- JOB END ---
                """
        )
    return "\n".join(parts)


async def extract_skills_for_batch(
    batch: list[dict], batch_number: int
) -> list[JobSkills]:

    jobs_text = format_batch(batch)

    user_prompt = f"""
Extract technical skills from the following {len(batch)} jobs.

Return one result for EVERY job.

Jobs:

{jobs_text}
"""

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = await client.chat.completions.parse(
                model=MODEL,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                response_format=SkillsResponse,
                temperature=0.0,
            )

            parsed = response.choices[0].message.parsed
            if parsed is None:
                raise ValueError("OpenAI returned an empty structured response")

            print(f"✅ Batch {batch_number}: {len(parsed.jobs)} jobs processed")

            return parsed.jobs

        except Exception as e:
            print(
                f"⚠️ Batch {batch_number} failed (attempt {attempt}/{MAX_RETRIES}): {e}"
            )

            if attempt < MAX_RETRIES:
                # Exponential backoff
                await asyncio.sleep(2**attempt)

            else:
                print(f"❌ Batch {batch_number} permanently failed")

    return []


async def process_all_jobs(jobs: list[dict]) -> dict:
    batches = prepare_batches(jobs, BATCH_SIZE)
    print(f"\n🚀 Processing {len(jobs)} jobs in {len(batches)} batches")

    semaphore = asyncio.Semaphore(MAX_CONCURRENT_REQUESTS)

    async def process_with_limit(batch: list[dict], batch_number: int):
        async with semaphore:
            return await extract_skills_for_batch(batch, batch_number)

    tasks = [process_with_limit(batch, i + 1) for i, batch in enumerate(batches)]

    results = await asyncio.gather(*tasks, return_exceptions=True)

    final_result = {}

    for result in results:
        if isinstance(result, BaseException):
            print(f"⚠️ Unexpected batch error: {result}")
            continue
        for job in result:
            skills = sorted(
                {skill.strip() for skill in job.skills if skill and skill.strip()}
            )
            final_result[job.job_id] = skills
    print(f"\n🎉 Finished: {len(final_result)} jobs have extracted skills")

    return final_result


async def skills_extractor(jobs: list):
    skills_map = await process_all_jobs(jobs)

    print("\n============================")
    print("EXTRACTED SKILLS")
    print("============================")

    print(skills_map)
    return skills_map


def skills_setter(jobs: list, skills: dict):
    for index, skill in enumerate(skills):
        jobs[index]["skills"] = skills[skill]
    return jobs
