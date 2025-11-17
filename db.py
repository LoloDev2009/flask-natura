import sqlite3
from flask import g
import os

DB_PATH = os.path.join("instance", "natura.db")

def get_db():
    db = getattr(g, "_database", None)
    if db is None:
        db = g._database = sqlite3.connect(DB_PATH)
        db.row_factory = sqlite3.Row
    return db

def query(sql, params=(), one=False):
    cur = get_db().execute(sql, params)
    rv = cur.fetchall()
    cur.close()
    return (rv[0] if rv else None) if one else rv

def execute(sql, params=()):
    db = get_db()
    cur = db.execute(sql, params)
    db.commit()
    cur.close()
