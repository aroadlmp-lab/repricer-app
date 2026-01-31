#!/usr/bin/env bash
set -e

# Backend
cd backend
pip install -r requirements.txt

# Frontend
cd ../frontend
npm install
npm run build
