# Storybard - Backend

## How to build Storybard

1. Create virtual Python environment 

`python3 -m venv .venv`

2. Activate environment

`source .venv/bin/activate`

3. Install requirements 

`pip install --upgrade pip`

`pip install -r requirements.txt`

4. Run Postgres

`docker run -d \
  --name storybard-postgres \
  -e POSTGRES_USER=postgres \
  -e POSTGRES_PASSWORD=postgres \
  -e POSTGRES_DB=storybard \
  -p 5432:5432 \
  postgres:16
`