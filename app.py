from fastapi import FastAPI, Depends, Form, Request, Query, File, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime, or_
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from datetime import datetime
from typing import Optional
import os
import uuid
import urllib.parse

# 1. إعداد قاعدة البيانات والملفات المرفوعة لتتوافق مع بيئة Vercel Serverless
# في Vercel، المجلد الوحيد المسموح بالكتابة فيه هو /tmp
IS_VERCEL = os.environ.get("VERCEL", False)
DB_FILE = "/tmp/amana.db" if IS_VERCEL else "amana.db"
UPLOAD_DIR = "/tmp/uploads" if IS_VERCEL else "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

engine = create_engine(f"sqlite:///{DB_FILE}", connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# (بقيّة الكود تبقى كما هي بدون أي تغيير...)