# AUTO-ZOHO - Smart Zoho Expense Automation

AUTO-ZOHO is a production-hardened automated expense ingestion and validation tool that parses Excel spreadsheets, validates business rules, matches entries with Zoho Expense master data, and creates entries inside target GST / NON-GST reports.

---

## 📌 PROJECT OVERVIEW & FEATURES

AUTO-ZOHO is designed to automate the ingestion of monthly business expense files (averaging ~200 rows per month) into Zoho Expense. 

### Key Features
1. **Spreadsheet Ingestion:** Drag-and-drop or select Excel files.
2. **Business Rules Validation:** Pre-validates date formats, tax structures, matching vendor records, and amount ranges.
3. **GST / NON-GST Separation:** Automatically splits expenses into separate Zoho Expense folders depending on their tax status.
4. **Master-Data Mapping:** Custom dropdown selectors to map categories, paid through accounts, project targets, and expense kinds.
5. **Idempotency & Resumable Sessions:** If a network failure occurs, the uploader can safely resume execution and skip already created entries to avoid duplicate postings.
6. **Local Passcode Security:** Automatic application lock overlay after 10 minutes of user inactivity.
7. **Excel Error Reports:** Exports failed spreadsheet rows indicating Zoho error codes and exact cell failure explanations.
8. **Dark Mode Support:** Class-based theme toggling with complete interface compatibility.

---

## 🏛️ SYSTEM ARCHITECTURE & STRUCTURE

AUTO-ZOHO separates data parsing logic and database persistence layers from downstream Zoho APIs:

```text
auto-zoho/
│
├── backend/                       # Python FastAPI Backend
│   ├── app/
│   │   ├── api/
│   │   │   ├── endpoints.py       # API endpoints (auth, validation, history, delete)
│   │   │   └── zoho_api.py        # Zoho Expense creation, reports, dry-runs
│   │   ├── config/
│   │   │   └── config.py          # Environment settings loader
│   │   ├── database/
│   │   │   ├── models.py          # SQLite Entities (UploadSession, ExpenseRecord)
│   │   │   └── session.py         # SQLAlchemy engine connection managers
│   │   ├── security/
│   │   │   └── encryption.py      # PBKDF2 passcode hashing and Fernet token encryption
│   │   ├── services/
│   │   │   ├── excel/
│   │   │   │   └── parser.py      # Pandas workbook parser
│   │   │   ├── upload/
│   │   │   │   └── history_service.py # Database CRUD controllers
│   │   │   └── zoho/
│   │   │       └── master_data.py # Zoho master-data mappings caches
│   │   └── main.py                # Uvicorn FastAPI startup
│   └── requirements.txt           # Backend python dependencies
│
├── frontend/                      # React TypeScript + Vite Client
│   ├── src/
│   │   ├── components/            # UI components (AppLock screen, overlays)
│   │   ├── layouts/
│   │   │   └── DashboardLayout.tsx# Sidebar, connection states, and theme switcher
│   │   ├── pages/
│   │   │   ├── DashboardPage.tsx  # Upload statistics and metrics graphs
│   │   │   ├── HistoryPage.tsx    # Upload archive list and details drawers
│   │   │   ├── SettingsPage.tsx   # Zoho connection settings and passcode lock configurations
│   │   │   └── UploadPage.tsx     # 8-step uploader wizard with SVG loader consoles
│   │   ├── services/
│   │   │   └── api.ts             # REST client API services
│   │   ├── App.tsx                # App state manager
│   │   └── main.tsx               # Entrypoint
│   ├── index.html                 # Main template
│   ├── tailwind.config.js         # Styling configurations
│   └── package.json               # Node packages
│
├── tests/                         # Backend Pytest suite
│   ├── test_api.py                # API router endpoint tests
│   └── test_excel.py              # Parsing and validation rules tests
└── README.md                      # Documentation
```

---

## 🛠️ INSTALLATION & RUNNING THE APPLICATION

### Step 1: Environment Setup
Create a `.env` file at the root folder of the project. Fill in the parameters as shown in `.env.example`:
```env
HOST=127.0.0.1
PORT=8000
ENV=development

DATABASE_URL=sqlite:///./data/zoho_uploader.db
UPLOAD_DIR=./data/uploads
LOGS_DIR=./logs

ALLOWED_ORIGINS=http://localhost:5173

ZOHO_CLIENT_ID=your_zoho_client_id
ZOHO_CLIENT_SECRET=your_zoho_client_secret
ZOHO_ACCOUNTS_URL=https://accounts.zoho.in
ZOHO_API_URL=https://www.zohoapis.in/expense/v1
ZOHO_TOKEN_ENCRYPTION_KEY=generate_a_new_key_locally
```

### Step 2: Backend Setup
1. Open a terminal and navigate to the backend:
   ```bash
   cd backend
   ```
2. Install python dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Start the server:
   ```bash
   python -m app.main
   ```
   *The backend starts on `http://127.0.0.1:8000`.*

### Step 3: Frontend Setup
1. Open a terminal and navigate to the frontend:
   ```bash
   cd frontend
   ```
2. Install node packages:
   ```bash
   npm install
   ```
3. Launch development server:
   ```bash
   npm run dev
   ```
   *The client runs on `http://localhost:5173`.*

---

## 🔑 ZOHO DEVELOPER CONSOLE & SCOPES SETUP

To authorize communication, configure a client on the **Zoho Developer Console**:
1. Choose **Server-based Applications**.
2. Define the Redirect URI:
   ```text
   http://localhost:8000/api/zoho/callback
   ```
3. Ensure the client is configured with the following OAuth scopes:
   * `ZohoExpense.settings.READ` (to resolve organizations and base currencies)
   * `ZohoExpense.expense.CREATE` (to create expenses inside reports)
   * `ZohoExpense.reports.READ` (to retrieve folders list)

---

## 📊 EXCEL SPREADSHEET RULES & MAPPINGS

The uploader parses worksheets and verifies that these columns are present:
1. **Expense Date**
2. **Amount**
3. **Description**
4. **GST/Non GST** (Values must normalize to `"GST"` or `"NON-GST"`)
5. **Category**
6. **Tax Type** (For GST items, e.g. `"Standard Rate [18%]"` or `"Zero Rate [0%]"`)
7. **Paid Through** (e.g. `"Petty Cash"`, `"Employee Reimbursements"`)
8. **Project** (e.g. `"Internal Project"`)
9. **Expense Kind** (e.g. `"Standard"`, `"Item"`)
10. **Vendor Name** (e.g. `"Vendor Ltd"`)

---

## 🔒 SECURITY DESIGN

This application implements the following security protocols:
* **Excluded Secrets:** `.env` config settings are stored locally and are excluded from the repository.
* **Token Encryption:** Refresh tokens and OAuth tokens are stored in the database encrypted with **Fernet (AES-128 in CBC mode)**. The key (`ZOHO_TOKEN_ENCRYPTION_KEY`) remains only on the local machine.
* **Passcode Hashing:** Numeric passcodes are hashed using **PBKDF2-HMAC-SHA256** with 100,000 iterations before logging configuration.
* **No Automatic Submissions:** The application **strictly creates** expense entries in the selected reports. It **never** submits, approves, or reimburses reports automatically. The final submission workflow remains a manual action inside the Zoho Expense web console.
* **Runtime Isolation:** Active SQLite database files (`*.db`), temporary spreadsheet copies, logs (`logs/`), and exports are ignored by `.gitignore`.
