# WorkHub — Multi-Tenant RBAC Workspace Platform

A full-stack **Django REST Framework + React** application for managing multi-tenant company workspaces, RBAC-controlled workers, and invitation-based onboarding.

---

## 📁 Project Structure

```
WorkHub/
├── backend/                  ← Django DRF backend
│   ├── config/               ← Project config (settings, urls, wsgi, asgi)
│   ├── accounts/             ← Custom User model, auth endpoints, JWT
│   ├── companies/            ← Company model, dashboard stats, worker management
│   ├── invitations/          ← Invitation model, send/accept/revoke flow
│   └── manage.py
│
├── frontend/                 ← React + Vite frontend
│   ├── src/
│   │   ├── api/              ← Axios API modules (auth, companies, invitations)
│   │   ├── components/       ← Sidebar, Topbar, Layout, Modal, ProtectedRoute
│   │   ├── context/          ← AuthContext (JWT + session management)
│   │   └── pages/            ← Login, Register, Dashboard, Workers, Invitations,
│   │                            Settings, AcceptInvite
│   ├── index.html
│   └── package.json
│
└── .gitignore
```

---

## 🚀 Getting Started

### Backend

```bash
cd backend
py -3.14 manage.py migrate
py -3.14 manage.py runserver
```

API runs on → **http://127.0.0.1:8000/api/**

### Frontend

```bash
cd frontend
npm install
npm run dev
```

UI runs on → **http://localhost:5173**

---

## 🔑 Key API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/accounts/register/` | Register company + owner |
| `POST` | `/api/accounts/login/` | JWT login |
| `POST` | `/api/accounts/token/refresh/` | Refresh access token |
| `POST` | `/api/accounts/logout/` | Logout |
| `GET/PATCH` | `/api/accounts/me/` | Profile |
| `POST` | `/api/accounts/change-password/` | Change password |
| `GET/PATCH` | `/api/companies/me/` | Company details |
| `GET` | `/api/companies/dashboard-stats/` | Admin dashboard metrics |
| `GET` | `/api/companies/workers/` | List team workers |
| `DELETE` | `/api/companies/workers/<id>/` | Remove worker |
| `POST` | `/api/invitations/send/` | Dispatch invitation email |
| `GET` | `/api/invitations/validate/<token>/` | Validate invite token |
| `POST` | `/api/invitations/accept/` | Accept invite & set password |
| `DELETE` | `/api/invitations/revoke/<token>/` | Revoke pending invite |

### Admin list pagination

Team workers, audience submissions, integrations, pending invitations, and integration logs use page-number pagination. List responses contain `count`, `next`, `previous`, and `results`. Use `page` to select a page and `page_size` to choose the number of records (default: 10; maximum: 1,000). The audience and worker lists also accept a `search` query parameter, which is applied before pagination.

For example: `/api/companies/workers/?page=2&page_size=25`

---

## ⚙️ JWT Token Lifetimes (configurable via `.env`)

| Token | Default TTL |
|-------|-------------|
| Access | 60 minutes |
| Refresh | 7 days |
| Rotation | Enabled (session rolling) |

Set `JWT_ACCESS_TOKEN_LIFETIME_MINUTES` and `JWT_REFRESH_TOKEN_LIFETIME_DAYS` in `backend/.env`.

---

## 📧 Email

Set `EMAIL_HOST_USER` and `EMAIL_HOST_PASSWORD` in `backend/.env`. Falls back to console backend when no credentials are configured.
