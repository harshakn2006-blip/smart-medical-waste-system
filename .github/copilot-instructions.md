# Copilot instructions for the Smart Medical Waste System

## Project overview

- This repository is a Flask application for a local medical-waste management prototype used in a hospital or clinic workflow.
- The main app logic lives in `app.py`: authentication, role checks, SQLite access, waste classification rules, collection workflow, and admin user/report features.
- `ai_classifier.py` contains a small scikit-learn demo classifier used as a secondary suggestion only; it is not a regulatory decision engine.
- UI templates live under `templates/` and static assets under `static/`; most page behavior is server-rendered with Jinja templates rather than a separate frontend framework.
- The app stores its data in `medical_waste.db`, which is created automatically on first run through `init_db()` when the database file is missing.

## Run, validate, and smoke-test

### Local development

```bash
py -m venv .venv
.venv\Scripts\activate
python -m pip install -r requirements.txt
python app.py
```

Then open the local URL shown in the terminal, typically `http://127.0.0.1:5000`.

### Manual validation

This repository does not currently define a formal build, lint, or automated test runner (`package.json`, `pyproject.toml`, `Makefile`, or pytest config are not present). The project’s expected checks are documented in `TESTING.md` and should be used as the primary smoke test workflow.

Use the checklist in `TESTING.md` for the main validation flow:

- login success/failure
- role-based access enforcement
- segregation suggestions for known and unknown items
- waste record creation and invalid-quantity rejection
- collection request creation and assignment lifecycle
- admin user creation

If the repo later adopts pytest, prefer single-test invocations such as:

```bash
python -m pytest path/to/test_file.py::test_name
```

or:

```bash
python -m pytest path/to/test_file.py -k "test_name"
```

Do not treat the AI classifier as production safety logic; it is educational and deliberately conservative.

## High-level architecture

### Flask app lifecycle

- `app.py` creates the Flask app with `template_folder` and `static_folder` pointed at the local project directories.
- `@app.before_request` ensures the SQLite database exists and runs `init_db()` if necessary.
- `get_db()` and teardown logic manage a request-scoped SQLite connection with `PRAGMA foreign_keys = ON`.
- `init_db()` creates the `users`, `waste_records`, and `collection_requests` tables and seeds demo accounts when the database is empty.

### Authentication and authorization

- Session-based auth is the primary security mechanism.
- `login_required` redirects unauthenticated users to `/login`.
- `roles_required(*roles)` wraps routes and enforces role checks (`staff`, `collector`, `admin`).
- Access is intentionally split by role:
  - staff: create waste records and manage their own collection requests
  - collector: update assigned/in-progress requests
  - admin: full dashboard access, user management, and report exports

### Waste workflow

- `classify_waste()` in `app.py` prefers conservative rule-based logic from `WASTE_GUIDE` and only uses the ML suggestion as an extra hint when rule matching is uncertain or absent.
- Waste entries are saved to `waste_records` with category, container, guidance, and `review_required` flags.
- Collection requests are created from waste records or standalone pickup requests, then advanced through `Pending -> Assigned -> Collected -> Completed`.
- Reports are generated under `/reports/pdf` and `/reports/excel` and are restricted to admin access.

### Frontend structure

- Templates in `templates/` are server-rendered pages for dashboard, login, segregation, waste tracking, collections, and user administration.
- Static assets under `static/` contain supporting CSS/JS for the browser UI.
- Keep route logic in `app.py` and use template variables for display; avoid duplicating business rules in the frontend.

## Key conventions specific to this repo

- Favor the existing demo safety policy: if an item is ambiguous or unknown, require staff review rather than making a definitive classification.
- Preserve the role model and the `STATUSES`/`ROLES` constants when modifying route behavior; do not widen privileges without updating both the guards and the UI expectations.
- Treat `medical_waste.db` as local app state. Changes to the schema should be reflected in `init_db()` and should not silently break existing demo accounts or seeded data.
- Keep validation consistent with `app.py`: numeric waste quantities must be positive and bounded, and collection request statuses must remain within the canonical `STATUSES` list.
- When adding new workflows, follow the existing pattern of:
  1. validate input in the route,
  2. write to SQLite via `get_db()`,
  3. commit the transaction,
  4. flash a success/error message,
  5. redirect back to the relevant page.
- Do not replace the educational classifier with a production compliance system without also updating the operating guidance in the README and any related safety messaging.

## Relevant docs to consult

- `README.md` for setup, demo accounts, and deployment warnings
- `TESTING.md` for the expected manual smoke tests
- `requirements.txt` for the installed Python dependencies

## MCP server configuration

This project is a local Flask web app, so browser automation is the most likely project-relevant MCP addition if you want deeper UI validation. If you do add MCP tooling, prefer focused workflow coverage for login, role enforcement, and collection status updates rather than broad automation.
