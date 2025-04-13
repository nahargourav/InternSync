from flask import Flask, render_template, request, redirect, url_for, session, flash,jsonify
import sqlite3
import hashlib
import os,subprocess,sys
import re
#import pyautogui
import WebScraper  # Import the WebScraper module to access the global variable
import requests
# Define the path to the Databases folder and database file
DATABASE_FOLDER = os.path.join(os.path.dirname(os.path.dirname(__file__)), "Databases")
DATABASE_PATH = os.path.join(DATABASE_FOLDER, "internsync.db")

def clear_database():
    """Flush old job listings before storing new ones."""
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM ratings")  # Clear old data
    conn.commit()
    conn.close()
clear_database()