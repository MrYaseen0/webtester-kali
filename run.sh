#!/bin/bash
# WebTester-Kali launcher — Kali Linux (or any Linux with python3)
cd "$(dirname "$0")"
echo "WebTester-Kali starting..."
echo "Browser mein kholo: http://127.0.0.1:8080"
python3 webtester.py
