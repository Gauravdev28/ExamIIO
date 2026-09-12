# ExamIIo — Online Technical Assessment & Examination Platform

![Build Status](https://img.shields.io/badge/Build-Passing-brightgreen?style=for-the-badge)
![Backend Tests](https://img.shields.io/badge/Pytest-Verified%20PASS-success?style=for-the-badge&logo=python)
![Frontend Status](https://img.shields.io/badge/Frontend-TypeScript%20Verified-blue?style=for-the-badge&logo=react)
![Django 5](https://img.shields.io/badge/Backend-Django_5_|_DRF_|_Channels-092e20?style=for-the-badge&logo=django)
![React 18](https://img.shields.io/badge/Frontend-React_18_|_TypeScript_|_Tailwind-20232a?style=for-the-badge&logo=react)
![MySQL 8](https://img.shields.io/badge/Database-MySQL_8.0-4479A1?style=for-the-badge&logo=mysql)
![Redis 7](https://img.shields.io/badge/Cache_&_Broker-Redis_7-DC382D?style=for-the-badge&logo=redis)

---

## 1. Project Overview

**ExamIIo** is an enterprise-grade technical examination and assessment platform engineered for universities, academic institutions, and technical recruitment. It pairs sandboxed multi-language code execution (Python, C++, Java, C) with automated real-time AI invigilation, mathematical scoring and certificate generation, automated GDPR/FERPA-compliant data retention with legal hold management, a real-time human proctoring console with live interventions, and a robust Proctor Reattempt / Second-Chance workflow.

### Key Capabilities
- **Candidate Assessment Workflow**: Students register and receive institutional EUIDs, take scheduled examinations in a locked environment with server-authoritative countdown timers, and solve MCQ, SQL, and DSA coding challenges.
- **Sandboxed Code Execution**: Multi-language code (Python, C++, Java, C) executes in isolated Piston/Judge0 Linux sandboxes with strict CPU, memory, and disk quotas and zero network access.
- **Automated AI Proctoring & Human Invigilation**: Comprehensive browser telemetry, webcam proctoring, 120-second window termination policies, and live proctor consoles with four authoritative review verdicts.
- **Proctor Reattempt / Second-Chance Architecture**: Authoritative granting of Attempt #2 with a 60-second preparation delay, full attempt isolation, Django Admin second-chance workflows, Timeline evidence integration, and technical prevention of Attempt #3.
- **Authoritative Results & Analytics**: Computes weighted scores, grade bands, passing determinations, and exports cryptographically verifiable PDF scorecards and Excel reports sanitized against CSV formula injection.
- **Data Retention & Privacy Compliance**: Automated lifecycle engine purges detailed answers, code, and telemetry after retention deadlines, enforces scoped legal holds, assembly-encrypts AES-256-GCM DSAR self-service archives, and mints permanent HMAC-SHA256 audit tombstones.

---

## 2. Platform Phase Status

```text
Phase 1: Foundation, Authentication & Security      ──► FROZEN 🔒 (Verified)
Phase 2: User Profiles & Student Foundation         ──► FROZEN 🔒 (Verified)
Phase 3: Student Management & Batch Operations       ──► FROZEN 🔒 (Verified)
Phase 4: Question Bank & Versioning Engine          ──► FROZEN 🔒 (Verified)
Phase 5: Assessment Engine & Runtime Attempts       ──► FROZEN 🔒 (Verified)
Phase 6: Sandboxed Code Execution & Grading (Judge0)──► FROZEN 🔒 (Verified)
Phase 7: Real-Time AI Proctoring & Risk Scoring     ──► FROZEN 🔒 (Verified)
Phase 8: Results, Grade Ledger & Scorecards (PDF)   ──► FROZEN 🔒 (Verified)
Phase 9: Data Retention, DSAR & Legal Hold Engine   ──► FROZEN 🔒 (Verified)
Phase 10: Human Invigilation & Live Interventions   ──► IMPLEMENTED & VERIFIED 🔒
```

### Verified Quality Metrics:
- **Backend Test Suite**: **372 / 372 PASS** (257 Phase 1–9 regression tests + 101 Phase 10 invigilation tests + 14 Phase 10.1 hardening tests).
- **Frontend Typecheck**: **0 errors** (`tsc --noEmit` PASS).
- **Frontend Production Build**: **PASS** (`vite build` production bundle generated cleanly).
- **Database Schema**: `python manage.py makemigrations --check` $\longrightarrow$ **"No changes detected"**.

---

## 3. Technology Stack

### Frontend Client
- **Core**: React 18 + TypeScript + Vite 5 + Tailwind CSS
- **Code Editor**: Monaco Editor (`@monaco-editor/react`)
- **Visuals & Charts**: Recharts + Lucide React
- **Network**: Axios + Native WebSockets (`withCredentials: true`)

### Backend Core
- **Framework**: Python 3.14 + Django 5.1.15 + Django REST Framework 3.15.2
- **Real-Time Channels**: Django Channels 4.1.0 + Daphne 4.1.0 + Redis Channel Layer
- **Task Orchestration**: Celery 5.4.0 + Redis 7 message broker
- **Relational Storage**: MySQL 8.0 (InnoDB with row-level locks)
- **Code Execution**: Judge0 Community Edition (Dockerized isolate sandbox)
- **Vision AI**: OpenCV (headless) + MediaPipe + PyTorch / YOLO
- **Reporting Engines**: ReportLab (PDF scorecards) + pandas + openpyxl (Excel exports)

### Infrastructure & Deployment
- Docker & Docker Compose (development and production stacks)
- Nginx (reverse proxy, SSL termination, static asset offloading)
- Git & GitHub (`exam_code`)

---

## 4. Repository Structure

```text
codeguard/
├── .github/workflows/          # Automated GitHub Actions CI/CD pipelines
├── backend/
│   ├── manage.py               # Django CLI management entrypoint
│   ├── requirements.txt        # Python dependency manifest
│   ├── pytest.ini              # Pytest configuration
│   ├── codeguard/              # Core Django project configuration
│   │   ├── asgi.py             # Channels ASGI HTTP + WebSocket protocol router
│   │   ├── wsgi.py             # WSGI server entrypoint
│   │   ├── celery.py           # Celery application setup
│   │   ├── urls.py             # Central API router
│   │   ├── routing.py          # WebSocket route registry
│   │   └── settings/           # base.py, development.py, production.py, test.py
│   ├── apps/
│   │   ├── core/               # Base UUID/Timestamp models, standardized responses
│   │   ├── accounts/           # User authentication, RBAC, and student management
│   │   ├── questions/          # Question bank, versioning, and testcases
│   │   ├── assessments/        # Assessment scheduling, snapshots, attempts, timers
│   │   ├── evaluator/          # Judge0 integration and automated code grading
│   │   ├── proctoring/         # AI vision models, telemetry, and risk scoring
│   │   ├── results/            # Score finalization, gradebook, PDF scorecards
│   │   └── retention/          # Data retention, purges, legal holds, DSAR encryption
│   └── tests/                  # 372 automated backend tests
├── frontend/
│   ├── index.html              # Single-page app HTML host
│   ├── package.json            # Node.js dependency manifest
│   ├── vite.config.ts          # Vite build and proxy configuration
│   ├── tailwind.config.js      # Design system styling tokens
│   ├── tsconfig.json           # TypeScript configuration
│   └── src/
│       ├── api/                # Type-safe Axios REST clients
│       ├── components/         # Common UI tokens and domain-specific modals
│       ├── context/            # AuthContext and session state
│       ├── pages/              # Admin and student view routes
│       └── types/              # TypeScript interface definitions
├── docker/                     # Dockerfiles and container initialization scripts
├── docker-compose.yml          # Development container cluster
├── docker-compose.prod.yml     # Production deployment cluster
└── docs/                       # Comprehensive architecture and security specifications
```

---

## 5. Local College Demo (One-Click Docker Deployment)

For teachers, evaluators, or demo environments, the complete ExamIIO platform runs locally with a single Docker Compose command on any machine with Docker Desktop installed.

**No manual installations** of GCC, G++, Java, Python execution runtime, Piston, MySQL, or Redis are required on the host PC. All execution runtimes (Python 3.10, GCC 10.2 C/C++, OpenJDK 15 Java) and backend services are containerized.

### Prerequisites
- **Docker Desktop** (with Docker Compose v2)

### Starting the Environment
```bash
# 1. Clone repository and initialize environment configuration
git clone https://github.com/Gauravdev28/exam_code.git
cd exam_code
cp .env.example .env

# 2. Build and launch all services in the background
docker compose up -d
```

### Accessing the Platform
1. Wait for services to become healthy (`docker compose ps`).
2. Open your browser and navigate to:
   - **Frontend UI**: `http://localhost:5173`
   - **Backend API**: `http://localhost:8000/api/v1`
3. Log in as an Administrator or Student.
4. Run or submit coding questions in Python, C, C++, or Java. Execution is securely sandboxed inside the Piston container.

### Stopping the Environment
```bash
# Gracefully stop containers (preserves database data and volumes)
docker compose down
```

> [!WARNING]
> **Data Persistence**: Standard `docker compose down` retains all MySQL and student attempt data in Docker volumes. Only run `docker compose down -v` if you explicitly intend to perform a **DESTRUCTIVE full reset** of all database records.

---

## 6. Running Automated Tests

Execute the complete backend test suite:
```bash
cd backend
pytest -q
# Output: 372 passed
```

Run frontend typechecking and production build:
```bash
cd frontend
npm run typecheck
npm run build
```

---

## 7. Architecture Documentation Index

Detailed architectural specifications are maintained in the [`docs/`](docs/) directory:
- [`docs/system-architecture.md`](docs/system-architecture.md): Overall multi-tier system topology and phase boundaries.
- [`docs/security-architecture.md`](docs/security-architecture.md): Complete threat model, sandbox security, and encryption details.
- [`docs/data-flow.md`](docs/data-flow.md): Step-by-step lifecycle from candidate login to cryptographic data purge.
- [`docs/codebase-file-reference.md`](docs/codebase-file-reference.md): Comprehensive inventory of every source file across backend and frontend.
- [`docs/phase10-architecture.md`](docs/phase10-architecture.md): Phase 10 Human Invigilation architecture specification.
- [`docs/phase10-final-architecture-correction.md`](docs/phase10-final-architecture-correction.md): Phase 10 micro-hardening and invariant report.
- [`docs/PROCTOR_REATTEMPT_IMPLEMENTATION_PLAN.md`](docs/PROCTOR_REATTEMPT_IMPLEMENTATION_PLAN.md): Proctor Reattempt / Second-Chance authoritative implementation plan and architecture.
