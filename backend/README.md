# Backend Module

## Run

Install backend-only dependencies first:

```bash
pip install -r backend/requirements.txt
```

Then start the service from the project root:

```bash
python -m uvicorn backend.main:app --reload
```

If you need user login, forum, or history storage, also set:

```env
SUPABASE_URL=...
SUPABASE_KEY=...
```
