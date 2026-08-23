import sys

import chainlit as cl
from dotenv import load_dotenv

from db.db_connect import connect_with_db
from scrappers import scrapper


@cl.on_message
async def main():
    load_dotenv()
    pool = await connect_with_db()
    if pool is None:
        print("entered")
        sys.exit(1)
        await cl.Message(content="Internal server error").send()
    #     # naukri_jobs = naukri_main()
    #     # if naukri_jobs is not None:
    #     #     await insert_many(pool, naukri_jobs)

    # jobs = await linkedin_main()
    # if jobs is not None:
    #     formatted_jobs = linkedin_formatter(jobs)
    #     for el in formatted_jobs:
    #         print(el["id"])
    #     skills = await skills_extractor(formatted_jobs)
    #     print(skills)
    #     linkedin_jobs = skills_setter(formatted_jobs, skills)
    #     formatted_linked_jobs = linkedin_jobs_list_converter(linkedin_jobs)
    #     await insert_many(pool, formatted_linked_jobs)

    await scrapper(pool)
    await cl.Message(content="done").send()
    await pool.close()
