#!/bin/bash
set -e

echo "Building frontend..."
cd frontend
npm install
npm run build
cd ..

echo "Installing Python dependencies..."
pip install -r requirements.txt

echo "Starting backend..."
python3 -m backend.main
