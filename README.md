# Smart Web-Based Medical Waste Segregation and Collection System

A beginner-friendly Flask + SQLite student project. It includes:
- Login with three roles: admin, staff, collector
- Rule-based segregation guide
- Waste record entry and review flags
- Collection request creation, assignment, and status tracking
- Admin user management and dashboard summaries
- Responsive HTML/CSS interface

## Important safety and compliance note

This is an educational prototype, not a certified compliance system. It is not an exhaustive classification engine and must not be used as the sole authority for handling, treating, or disposing of biomedical waste. The lookup intentionally sends unknown or ambiguous items to trained staff review. Before real use, have the facility's biomedical-waste officer validate every rule against the current Biomedical Waste Management Rules, amendments, CPCB/SPCB guidance, and approved facility SOPs. Do not enter patient-identifying information.

## Requirements

- Python 3.10 or newer recommended
- Visual Studio Code
- Internet connection only for optional Google Fonts in the stylesheet; the app itself runs locally

## Run in VS Code

### 1. Extract the ZIP
Extract `smart_medical_waste_system.zip` to a folder and open that folder in VS Code.

### 2. Open the terminal
In VS Code choose **Terminal → New Terminal**.

### 3. Create a virtual environment

Windows:
```bash
py -m venv .venv
.venv\Scripts\activate
```

macOS/Linux:
```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 4. Install Flask
```bash
python -m pip install -r requirements.txt
```

### 5. Start the website
```bash
python app.py
```

Open the local URL shown in the terminal, normally `http://127.0.0.1:5000`.

The SQLite database file `medical_waste.db` is created automatically on first run.

## Demo login accounts

These accounts are created automatically only when the database has no users.

| Role | Username | Password |
|---|---|---|
| Administrator | `admin` | `Admin123!` |
| Hospital staff | `staff` | `Staff123!` |
| Collection staff | `collector` | `Collector123!` |

Use **Users** as admin to create other accounts. Passwords are stored as hashes, not plain text.

## Suggested demo workflow

1. Sign in as `staff`.
2. Open **Segregation guide** and test `contaminated IV tubing`, `needle`, and `unknown laboratory item`.
3. Open **Waste records** and add an item, department, and quantity.
4. Open **Collections** and create a pickup request.
5. Sign out and sign in as `admin`; assign the request to `collector` and set status to `Assigned`.
6. Sign in as `collector`; update the request to `Collected`, then `Completed`.
7. Return to the dashboard to see the totals and status changes.

## Roles

- **Staff:** dashboard, segregation guide, add/view waste records, create/view their own collection requests.
- **Collector:** dashboard, segregation guide, view relevant assigned/in-progress requests, update permitted statuses.
- **Admin:** all dashboard data, waste records, all collection requests, assignment/status updates, and user creation.

## Rule-based classification examples

The prototype has a small allow-list of example phrases. Exact category assignment depends on the actual item and contamination. For example, "needle" suggests White (translucent), while "contaminated IV tubing" suggests Red for a specified recyclable plastic item. These suggestions are deliberately conservative and still require local SOP verification. Ambiguous/unknown items are flagged.

## Troubleshooting

- **`python` not found:** try `py app.py` on Windows or install Python and enable PATH.
- **Flask not found:** activate `.venv` and run `python -m pip install -r requirements.txt`.
- **Forgot demo password / want a clean database:** stop the server, delete `medical_waste.db`, then run `python app.py` again. This deletes all locally stored demo data.
- **Port 5000 busy:** edit the final line of `app.py` to `app.run(debug=True, port=5001)` and visit `http://127.0.0.1:5001`.

## Before any real deployment

- Replace the development `SECRET_KEY` with a long random secret stored in an environment variable.
- Disable debug mode; use a production WSGI server and HTTPS.
- Add CSRF protection, login rate limiting, audit logs, backups, and secure password reset.
- Review permissions, retention, privacy, data security, accessibility, and local regulatory requirements with qualified staff.
- Replace the example classifier with a version-controlled, reviewed rule set signed off by the facility's authorized biomedical-waste officer.
- Never use this student prototype to override trained staff or emergency/safety procedures.

## Reference links

- Central Pollution Control Board (CPCB), Annual Report on Biomedical Waste Management: https://cpcb.nic.in/uploads/Projects/Bio-Medical-Waste/AR_BMWM_2023.pdf
- CPCB, Guidelines for implementation of Biomedical Waste Management Rules by Healthcare Facilities: https://cpcb.nic.in/uploads/projects/bio-medical-waste/guidelines_healthcare_june_2018.pdf
- Biomedical Waste Management Rules, 2016 (hosted by Haryana State Pollution Control Board): https://hppcb.nic.in/BMW2016.pdf

Rules and guidance can be amended. Check the latest official central and state guidance before relying on the classification list.
