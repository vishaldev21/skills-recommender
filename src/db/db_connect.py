import asyncio
import os

import asyncpg

# load_dotenv()


async def insert_many(pool, data):
    async with pool.acquire() as conn:
        await conn.executemany(
            "INSERT INTO jobs(job_id,title,company, description, skills) VALUES($1, $2, $3, $4, $5)",
            data,
        )
        print("inserted provided data")


async def connect_with_db():
    conn_url = os.getenv("DB_CONN_STR")
    pool = await asyncpg.create_pool(
        conn_url, min_size=2, max_size=10, command_timeout=10
    )
    try:
        async with pool.acquire() as conn:
            await conn.fetchval("SELECT version();")
            print("connection created successfully")
            return pool
    except Exception as e:
        print(e)
        return None


async def main(data):
    pool = await connect_with_db()
    if pool is not None:
        await insert_many(pool, data)
        await pool.close()


# if __name__ == "__main__":
#     my_list = [
#         {
#             "id": "job_001",
#             "title": "Backend Engineer",
#             "company": "Example Corp",
#             "description": """
#                     We are looking for a Backend Engineer with experience
#                     building APIs using Python and FastAPI.

#                     Requirements:
#                     Python, FastAPI, PostgreSQL, Redis, Docker,
#                     AWS and REST APIs.
#                     """,
#             "skills": [
#                 "AWS",
#                 "Docker",
#                 "FastAPI",
#                 "PostgreSQL",
#                 "Python",
#                 "REST APIs",
#                 "Redis",
#             ],
#         },
#         {
#             "id": "job_002",
#             "title": "Frontend Developer",
#             "company": "Tech Inc",
#             "description": """
#                     Looking for a frontend engineer experienced with
#                     React, TypeScript, Next.js, GraphQL and Tailwind CSS.
#                     """,
#             "skills": ["GraphQL", "Next.js", "React", "Tailwind CSS", "TypeScript"],
#         },
#     ]
#     data = [list(el.values()) for el in my_list]
#     asyncio.run(main(data))
