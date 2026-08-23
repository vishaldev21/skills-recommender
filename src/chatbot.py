import json
import os
import re

import chainlit as cl
from dotenv import load_dotenv
from openai import AsyncOpenAI
from openai.types.chat import ChatCompletionMessageParam
from pydantic import BaseModel, Field

from db.db_connect import connect_with_db, get_skills_info
from scrappers import scrapper

load_dotenv()

MODEL = os.getenv("OPENAI_CHAT_MODEL", "gpt-4.1-mini")
JOB_SEARCH_PATTERN = re.compile(
    r"\b(job|jobs|employment|career|vacanc(?:y|ies)|opening|openings|roles?)\b",
    re.IGNORECASE,
)

client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))


class JobSearchFilters(BaseModel):
    location: str = Field(description="City, region, or country for the job search")
    keyword: str = Field(description="Job title or search keyword")
    experience_level: str = Field(
        description="Requested experience level, or empty string"
    )
    job_type: str = Field(description="Requested job type, or empty string")
    skills: list[str] = Field(
        description="Skills requested by the user, or an empty list"
    )


SYSTEM_PROMPT = """
You are an expert technical career coach and senior backend engineer.

When job skill data is provided, use it as the source of truth. The data can
contain duplicates caused by case sensitivity and naming variations. Mentally
group equivalent technologies (for example, Python/python, PostgreSQL/Postgres,
and React.js/React) before reasoning about demand. Treat priority 0.2500 as
Tier 1 (highest demand) and priority 0.0625 as Tier 2 (standard demand).

Create a practical, prerequisite-ordered learning roadmap rather than sorting
skills only by priority. Organize it into phases, explain why each phase is
useful based on the supplied data, and include a short practice project or tip
for each phase. Do not claim that a skill is present in the data when it is not.

For ordinary questions without job data, answer helpfully as a technical career
coach. Be concise and use Markdown.
"""


def is_job_search(prompt: str) -> bool:
    return bool(JOB_SEARCH_PATTERN.search(prompt))


def extract_role(prompt: str) -> str:
    """Extract a useful role phrase while keeping the original prompt intact."""
    patterns = (
        r"\b(?:jobs?|openings?|vacancies|roles?)\s+(?:for|in)\s+(.+?)(?:\?|$)",
        r"\b(?:search|find|show|get)\s+(?:me\s+)?(?:jobs?|roles?|openings?)\s+(.+?)(?:\?|$)",
    )
    for pattern in patterns:
        match = re.search(pattern, prompt, re.IGNORECASE)
        if match:
            role = match.group(1).strip(" .,!:")
            if role:
                return role
    return "backend developer"


async def call_model(messages: list[ChatCompletionMessageParam]) -> str:
    response = await client.chat.completions.create(
        model=MODEL,
        messages=messages,
        temperature=0.2,
    )
    content = response.choices[0].message.content
    if not content:
        raise RuntimeError("The model returned an empty response")
    return content


async def extract_search_filters(prompt: str) -> JobSearchFilters:
    response = await client.chat.completions.parse(
        model=MODEL,
        messages=[
            {
                "role": "system",
                "content": (
                    "Extract job-search filters from the user's request. "
                    "Return empty strings for unspecified location, experience "
                    "level, or job type, and an empty list for unspecified skills."
                ),
            },
            {"role": "user", "content": prompt},
        ],
        response_format=JobSearchFilters,
        temperature=0.0,
    )
    filters = response.choices[0].message.parsed
    if filters is None:
        raise RuntimeError("Could not extract job-search filters")
    return filters


async def collect_job_skill_data(search_filters: JobSearchFilters) -> str | None:
    pool = await connect_with_db()
    if pool is None:
        raise RuntimeError("Could not connect to the jobs database")

    try:
        async with cl.Step(name="Search job postings", type="tool") as step:
            step.input = search_filters.model_dump()
            await scrapper(pool, search_filters.model_dump())
            step.output = "Job postings collected and skills extracted."

        async with cl.Step(name="Calculate in-demand skills", type="tool") as step:
            step.input = search_filters.keyword
            skills_data = await get_skills_info(pool, search_filters.keyword)
            step.output = (
                "No matching jobs were found."
                if not skills_data
                else "Skill frequencies calculated."
            )
        return skills_data
    finally:
        await pool.close()


async def answer_prompt(prompt: str) -> str:
    if not is_job_search(prompt):
        return await call_model(
            [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ]
        )

    role = extract_role(prompt)
    async with cl.Step(name="Prepare job-market analysis", type="llm") as step:
        search_filters = await extract_search_filters(prompt)
        step.input = search_filters.model_dump()
        role = search_filters.keyword or role
        skills_data = await collect_job_skill_data(search_filters)
        if not skills_data:
            step.output = "There is no skill data for this role yet."
            return f"I could not find skill data for **{role}**."

        try:
            parsed_data = json.loads(skills_data)
        except json.JSONDecodeError:
            parsed_data = skills_data

        response = await call_model(
            [
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": (
                        f"User request:\n{prompt}\n\n"
                        f"Target role: {role}\n\n"
                        "Skill data from the database:\n"
                        f"{json.dumps(parsed_data, indent=2, default=str)}"
                    ),
                },
            ]
        )
        step.output = "Learning roadmap generated."
        return response


@cl.on_message
async def handle_message(message: cl.Message):
    if not os.getenv("OPENAI_API_KEY"):
        await cl.Message(content="OPENAI_API_KEY is not configured.").send()
        return

    try:
        response = await answer_prompt(message.content)
        await cl.Message(content=response).send()
    except Exception as error:
        await cl.Message(content=f"I could not complete that request: {error}").send()
