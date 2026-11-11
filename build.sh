#!/usr/bin/env bash
# Exit immediately on non-zero exit code
set -o errexit

echo "==> 1. Upgrading Pip and Installing Python Dependencies..."
python -m pip install --upgrade pip
pip install -r backend/requirements.txt

echo "==> 2. Installing Frontend Node Dependencies and Building React Static Bundle..."
cd frontend
npm install
npm run build
cd ..

echo "==> 3. Running Database Migrations via Alembic..."
cd backend
alembic upgrade head
cd ..

echo "==> Build Process Completed Successfully!"
