# Production-Ready Improvements TODO

## Approved Plan Breakdown (SQLite + SQLAlchemy + Secure Auth)

### Step 1: ✅ Create supporting files
- [x] TODO.md (this file)
- [x] models.py (SQLAlchemy models: User, Document)
- [x] config.py (Flask config classes)
- [x] init_db.py (DB creation + users.json migration)
- [x] Procfile (for deployment)
- [x] Update requirements.txt (add deps)

### Step 2: Core app updates (app_fixed.py)
- [x] Integrate SQLAlchemy/Flask-Login
- [x] Migrate user auth to DB (hashed PW)
- [ ] Secure uploads (validation, user-owned)
- [ ] Persistent per-user data storage
- [x] CSRF protection
- [x] Rate limiting setup
- [x] Production config (no debug)

### Step 3: Templates/UI updates
- [x] Add CSRF tokens to forms (login/signup/upload)

### Step 4: Deployment & Testing
- [ ] Install deps
- [ ] Run init_db.py
- [ ] Test auth/uploads/persistence
- [ ] Gunicorn/Procfile test
- [ ] Cleanup instructions

Progress will be updated after each major step.

