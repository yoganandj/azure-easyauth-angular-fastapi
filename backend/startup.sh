#!/bin/bash
# Azure App Service Linux Startup Script
echo "Starting FastAPI application for Azure App Service..."
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
