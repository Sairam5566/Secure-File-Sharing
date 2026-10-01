# Quick Setup Guide

## Prerequisites Check
- [ ] Python 3.10+ installed
- [ ] PostgreSQL 12+ installed and running
- [ ] pip package manager available

## Setup Steps

### 1. Create Virtual Environment
```bash
python -m venv venv
.\venv\Scripts\activate
```

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Configure Environment
```bash
# Copy template
cp .env.example .env

# Edit .env with your settings:
# - DATABASE_URL: Your PostgreSQL connection string
# - JWT_SECRET_KEY: Generate a secure random key
# - CORS_ORIGINS: Your frontend URLs
```

### 4. Setup PostgreSQL Database
```sql
-- Connect to PostgreSQL
psql -U postgres

-- Create database
CREATE DATABASE secure_file_sharing;

-- Exit
\q
```

### 5. Run Application
```bash
uvicorn app.main:app --reload
```

### 6. Access API Documentation
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc
- Health Check: http://localhost:8000/health

## Quick Test

1. Open http://localhost:8000/docs
2. Register a user via `POST /register`
3. Login via `POST /login` to get JWT token
4. Click "Authorize" and enter: `Bearer <your_token>`
5. Upload a file via `POST /files/upload`
6. Download the file via `GET /files/download/{file_id}`
7. View access logs via `GET /access-logs/`

## Troubleshooting

### Database Connection Error
- Verify PostgreSQL is running
- Check DATABASE_URL in .env
- Ensure database exists

### Import Errors
- Activate virtual environment
- Run `pip install -r requirements.txt`

### Port Already in Use
- Change port: `uvicorn app.main:app --reload --port 8001`

## Production Deployment

Before deploying to production:
1. Set `DEBUG=False` in .env
2. Generate strong `JWT_SECRET_KEY`
3. Use strong PostgreSQL password
4. Configure proper CORS origins
5. Enable HTTPS/TLS
6. Set up proper file storage (S3, Azure Blob)
7. Configure backup strategy

## Next Steps

- Review README.md for complete documentation
- Test all API endpoints
- Set up Alembic migrations: `alembic revision --autogenerate -m "Initial"`
- Configure production deployment
