# Job Skills Recommender

Job Skills Recommender is an AI-assisted career coach that turns current job postings into a practical learning roadmap. Ask the chat interface about a role, and the application can collect matching postings from LinkedIn and Naukri, extract their technical skills, calculate skill demand, and explain what to learn first.

## How it works

1. A Chainlit chat message is received through the FastAPI application.
2. Job-search messages are parsed into a keyword, location, experience level, job type, and optional skills using OpenAI structured output.
3. Bright Data collectors retrieves job postings from LinkedIn  and Naukri custom scrapper.
4. OpenAI extracts and normalizes hard technical skills from the job descriptions.
5. Postings and skills are inserted into PostgreSQL.
6. Skill frequencies and role relevance are queried from PostgreSQL, then OpenAI generates a prerequisite-ordered roadmap with practice projects.

Non-job questions are sent directly to the AI career coach without scraping or database access.

## Requirements

- Python 3.13 or newer
- PostgreSQL database
- An OpenAI API key with access to the configured chat models
- Bright Data access and collectors for LinkedIn and Naukri
- [`uv`](https://docs.astral.sh/uv/) (recommended) or another Python environment manager

## Setup

Clone the repository and install its dependencies:

```bash
uv sync
```

Create a `.env` file in the repository root:

```dotenv
OPENAI_API_KEY=your-openai-api-key
OPENAI_CHAT_MODEL=gpt-4.1-mini
DB_CONN_STR=postgresql://username:password@localhost:5432/job_skills
BRIGHTDATA_API_TOKEN=your-bright-data-token
DATASET_LINKEDIN=your-linkedin-dataset-id
NAUKRI_COLLECTOR_ID=your-naukri-collector-id
```


## Database

Create a PostgreSQL database and a `jobs` table before making a job-search request. The application writes the following fields:

```sql
CREATE TABLE jobs (
	id BIGSERIAL PRIMARY KEY,
	job_id TEXT NOT NULL,
	title TEXT NOT NULL,
	company TEXT,
	description TEXT,
	skills TEXT[]
);
```

`DB_CONN_STR` must be a PostgreSQL connection string accepted by `asyncpg`.

## Run the application

Start the FastAPI server with:

```bash
uv run fastapi dev src/app/main.py
```

Open the URL printed by FastAPI, usually `http://127.0.0.1:8000`, in a browser. The Chainlit interface is mounted at the root path.

Example prompts:

```text
What skills are most in demand for backend developer jobs in Bengaluru?
Find Python developer roles in India for someone with 2 years of experience.
How should I learn PostgreSQL and Docker?
```

The first two prompts trigger job collection and analysis. The last prompt is handled as a regular career-coaching question.

## Project structure

```text
src/
|-- app/main.py                  FastAPI entry point and Chainlit mounting
|-- ui.py                        Chainlit export surface
|-- chatbot.py                   Prompt routing, filtering, and roadmap generation
|-- db/db_connect.py             PostgreSQL pool, inserts, and skill statistics
`-- scrappers/
	|-- scrapper.py              Runs both job sources and coordinates enrichment
	|-- linkedin_scrapper.py     Bright Data LinkedIn collection and formatting
	|-- naukri_scrapper.py       Bright Data Naukri collection and formatting
	`-- skill_extactor.py        Batched OpenAI skill extraction
```

