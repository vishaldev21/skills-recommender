import os

import asyncpg
import json


async def insert_many(pool, data):
    try:
        async with pool.acquire() as conn:
            await conn.executemany(
                "INSERT INTO jobs(job_id,title,company, description, skills) VALUES($1, $2, $3, $4, $5)",
                data,
            )
            print("inserted provided data")
    except Exception as e:
        print(e)


async def get_skills_info(pool, role):
    try:
        # Connect to the database
        async with pool.acquire() as conn:
            # 2. Define the parameterized SQL query
            # Notice we replaced '%backend%' with $1
            query = """
            WITH 
            base AS (
                SELECT id, title, UNNEST(skills) AS skill
                FROM jobs
                WHERE skills IS NOT NULL
            ),
            global_stats AS (
                SELECT skill, COUNT(DISTINCT id) AS job_count
                FROM base
                GROUP BY skill
            ),
            target_stats AS (
                SELECT skill, COUNT(DISTINCT id) AS role_count
                FROM base
                WHERE title ILIKE $1
                GROUP BY skill
            ),
            totals AS (
                -- NULLIF prevents "division by zero" errors if the table is empty
                SELECT 
                    NULLIF((SELECT COUNT(*) FROM jobs), 0)::numeric AS total_jobs,
                    NULLIF((SELECT COUNT(*) FROM jobs WHERE title ILIKE $1), 0)::numeric AS total_target_jobs
            )
            SELECT 
                gs.skill,
                ROUND((gs.job_count / t.total_jobs), 4) AS job_frequency,
                ROUND((ts.role_count / t.total_target_jobs), 4) AS relevance_to_target_role,
                ROUND(
                    ((gs.job_count / t.total_jobs) * (ts.role_count / t.total_target_jobs)), 
                4) AS priority
            FROM global_stats gs
            JOIN target_stats ts ON gs.skill = ts.skill
            CROSS JOIN totals t
            ORDER BY priority DESC;
            """

            # 3. Define the target role (You can change this to anything!)
            target_role = f"%{role}%"
            # We pass `target_role` as the second argument to `fetch()` to replace $1
            rows = await conn.fetch(query, target_role)

            # 5. Print the results in a clean table format
            if not rows:
                print("⚠️ No data found for this target role.")
                return

            # Convert the raw asyncpg Records directly to a JSON string
            raw_json_data = json.dumps(
                [dict(row) for row in rows], indent=2, default=float
            )
            return raw_json_data

    except Exception as e:
        print(f"❌ Error executing query: {e}")
        return None


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
