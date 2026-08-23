import asyncio

from asyncpg import Pool

from db.db_connect import insert_many

from .linkedin_scrapper import (
    linkedin_formatter,
    linkedin_jobs_list_converter,
    linkedin_main,
)
from .naukri_scrapper import naukri_main
from .skill_extactor import skills_extractor, skills_setter


async def scrapper(pool: Pool):
    naukri_jobs, jobs = await asyncio.gather(
        naukri_main(),
        linkedin_main(),
    )

    if naukri_jobs is not None:
        await insert_many(pool, naukri_jobs)

    if jobs is not None:
        formatted_jobs = linkedin_formatter(jobs)
        for el in formatted_jobs:
            print(el["id"])
        skills = await skills_extractor(formatted_jobs)
        print(skills)
        linkedin_jobs = skills_setter(formatted_jobs, skills)
        formatted_linked_jobs = linkedin_jobs_list_converter(linkedin_jobs)
        await insert_many(pool, formatted_linked_jobs)
