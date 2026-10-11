# Repository structure
Below is a map for target repository structure. This is a work in progress, the main goal is to present separation between web and scraping parts of the application colocated in one repository.

## Repsitory file tree
lidl-engine/
│
├── README.md
├── pyproject.toml
├── uv.lock
├── .env.example
├── .gitignore
├── .dockerignore
│
├── Dockerfile
├── compose.yaml
│
├── src/
│   └── myapp/
│       ├── __init__.py
│       │
│       ├── config.py
│       ├── db.py
│       │
│       ├── web/
│       │   ├── __init__.py
│       │   ├── app.py
│       │   ├── routes.py
│       │   │
│       │   ├── templates/
│       │   │   ├── base.html
│       │   │   ├── index.html
│       │   │   └── partials/
│       │   │       └── data_table.html
│       │   │
│       │   └── static/
│       │       └── style.css
│       │
│       ├── scraper/
│       │   ├── __init__.py
│       │   ├── __main__.py
│       │   ├── fetch.py
│       │   ├── parse.py
│       │   └── pipeline.py
│       │
│       ├── models/
│       │   ├── __init__.py
│       │   └── item.py
│       │
│       └── repositories/
│           ├── __init__.py
│           └── items.py
│
├── migrations/
│   └── 001_initial.sql
│
└── tests/
    ├── conftest.py
    ├── fixtures/
    │   └── sample_page.html
    │
    ├── scraper/
    │   ├── test_parse.py
    │   └── test_pipeline.py
    │
    ├── web/
    │   └── test_routes.py
    │
    └── repositories/
        └── test_items.py
