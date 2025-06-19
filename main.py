
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
import sqlite3
import hashlib
import os
from datetime import datetime
import re

app = Flask(__name__)
app.secret_key = 'your-secret-key-change-this-in-production'

# Database setup
def init_db():
    conn = sqlite3.connect('bookswap.db')
    c = conn.cursor()
    
    # Users table
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        email TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        name TEXT NOT NULL,
        student_id TEXT,
        branch TEXT,
        semester TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    
    # Books table
    c.execute('''CREATE TABLE IF NOT EXISTS books (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        title TEXT NOT NULL,
        author TEXT NOT NULL,
        semester TEXT,
        branch TEXT,
        condition TEXT,
        subjects TEXT,
        book_type TEXT,
        image_path TEXT,
        is_available BOOLEAN DEFAULT 1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users (id)
    )''')
    
    # Book requests table
    c.execute('''CREATE TABLE IF NOT EXISTS book_requests (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        requester_id INTEGER,
        book_id INTEGER,
        owner_id INTEGER,
        status TEXT DEFAULT 'pending',
        message TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (requester_id) REFERENCES users (id),
        FOREIGN KEY (book_id) REFERENCES books (id),
        FOREIGN KEY (owner_id) REFERENCES users (id)
    )''')
    
    conn.commit()
    conn.close()

def get_db_connection():
    conn = sqlite3.connect('bookswap.db')
    conn.row_factory = sqlite3.Row
    return conn

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def validate_vit_email(email):
    pattern = r'^[a-zA-Z0-9._%+-]+@vitstudent\.ac\.in$'
    return re.match(pattern, email) is not None

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/signin', methods=['GET', 'POST'])
def signin():
    if request.method == 'POST':
        email = request.form['email'].lower().strip()
        password = request.form['password']
        
        if not validate_vit_email(email):
            flash('Please use a valid @vitstudent.ac.in email address', 'error')
            return render_template('signin.html')
        
        conn = get_db_connection()
        user = conn.execute(
            'SELECT * FROM users WHERE email = ?', (email,)
        ).fetchone()
        conn.close()
        
        if user and user['password_hash'] == hash_password(password):
            session['user_id'] = user['id']
            session['user_name'] = user['name']
            session['user_email'] = user['email']
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid email or password', 'error')
    
    return render_template('signin.html')

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        name = request.form['name'].strip()
        email = request.form['email'].lower().strip()
        password = request.form['password']
        student_id = request.form['student_id'].strip()
        branch = request.form['branch']
        semester = request.form['semester']
        
        if not validate_vit_email(email):
            flash('Please use a valid @vitstudent.ac.in email address', 'error')
            return render_template('signup.html')
        
        if len(password) < 6:
            flash('Password must be at least 6 characters long', 'error')
            return render_template('signup.html')
        
        conn = get_db_connection()
        
        # Check if user already exists
        existing_user = conn.execute(
            'SELECT id FROM users WHERE email = ?', (email,)
        ).fetchone()
        
        if existing_user:
            flash('An account with this email already exists', 'error')
            conn.close()
            return render_template('signup.html')
        
        # Create new user
        try:
            conn.execute(
                'INSERT INTO users (name, email, password_hash, student_id, branch, semester) VALUES (?, ?, ?, ?, ?, ?)',
                (name, email, hash_password(password), student_id, branch, semester)
            )
            conn.commit()
            flash('Account created successfully! Please sign in.', 'success')
            conn.close()
            return redirect(url_for('signin'))
        except Exception as e:
            flash('Error creating account. Please try again.', 'error')
            conn.close()
    
    return render_template('signup.html')

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('signin'))
    
    conn = get_db_connection()
    
    # Get user's books
    user_books = conn.execute(
        'SELECT * FROM books WHERE user_id = ? ORDER BY created_at DESC',
        (session['user_id'],)
    ).fetchall()
    
    # Get user's requests
    requests = conn.execute('''
        SELECT br.*, b.title, b.author, u.name as owner_name 
        FROM book_requests br 
        JOIN books b ON br.book_id = b.id 
        JOIN users u ON br.owner_id = u.id 
        WHERE br.requester_id = ? 
        ORDER BY br.created_at DESC
    ''', (session['user_id'],)).fetchall()
    
    # Get requests for user's books
    incoming_requests = conn.execute('''
        SELECT br.*, b.title, b.author, u.name as requester_name 
        FROM book_requests br 
        JOIN books b ON br.book_id = b.id 
        JOIN users u ON br.requester_id = u.id 
        WHERE br.owner_id = ? 
        ORDER BY br.created_at DESC
    ''', (session['user_id'],)).fetchall()
    
    conn.close()
    
    return render_template('dashboard.html', 
                         user_books=user_books, 
                         requests=requests, 
                         incoming_requests=incoming_requests)

@app.route('/browse')
def browse_books():
    if 'user_id' not in session:
        return redirect(url_for('signin'))
    
    conn = get_db_connection()
    
    # Get search filters
    search_query = request.args.get('search', '').strip()
    semester_filter = request.args.get('semester', '')
    branch_filter = request.args.get('branch', '')
    book_type_filter = request.args.get('book_type', '')
    
    # Build query
    query = '''
        SELECT b.*, u.name as owner_name 
        FROM books b 
        JOIN users u ON b.user_id = u.id 
        WHERE b.is_available = 1 AND b.user_id != ?
    '''
    params = [session['user_id']]
    
    if search_query:
        query += ' AND (b.title LIKE ? OR b.author LIKE ? OR b.subjects LIKE ?)'
        search_param = f'%{search_query}%'
        params.extend([search_param, search_param, search_param])
    
    if semester_filter:
        query += ' AND b.semester = ?'
        params.append(semester_filter)
    
    if branch_filter:
        query += ' AND b.branch = ?'
        params.append(branch_filter)
    
    if book_type_filter:
        query += ' AND b.book_type = ?'
        params.append(book_type_filter)
    
    query += ' ORDER BY b.created_at DESC'
    
    books = conn.execute(query, params).fetchall()
    conn.close()
    
    return render_template('browse.html', books=books)

@app.route('/add_book', methods=['GET', 'POST'])
def add_book():
    if 'user_id' not in session:
        return redirect(url_for('signin'))
    
    if request.method == 'POST':
        title = request.form['title'].strip()
        author = request.form['author'].strip()
        semester = request.form['semester']
        branch = request.form['branch']
        condition = request.form['condition']
        subjects = request.form['subjects'].strip()
        book_type = request.form['book_type']
        
        conn = get_db_connection()
        conn.execute('''
            INSERT INTO books (user_id, title, author, semester, branch, condition, subjects, book_type)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (session['user_id'], title, author, semester, branch, condition, subjects, book_type))
        conn.commit()
        conn.close()
        
        flash('Book added successfully!', 'success')
        return redirect(url_for('dashboard'))
    
    return render_template('add_book.html')

@app.route('/request_book/<int:book_id>', methods=['POST'])
def request_book(book_id):
    if 'user_id' not in session:
        return redirect(url_for('signin'))
    
    message = request.form.get('message', '').strip()
    
    conn = get_db_connection()
    
    # Get book details
    book = conn.execute('SELECT * FROM books WHERE id = ?', (book_id,)).fetchone()
    
    if not book:
        flash('Book not found', 'error')
        return redirect(url_for('browse_books'))
    
    if book['user_id'] == session['user_id']:
        flash('You cannot request your own book', 'error')
        return redirect(url_for('browse_books'))
    
    # Check if request already exists
    existing_request = conn.execute(
        'SELECT id FROM book_requests WHERE requester_id = ? AND book_id = ?',
        (session['user_id'], book_id)
    ).fetchone()
    
    if existing_request:
        flash('You have already requested this book', 'error')
        return redirect(url_for('browse_books'))
    
    # Create request
    conn.execute('''
        INSERT INTO book_requests (requester_id, book_id, owner_id, message)
        VALUES (?, ?, ?, ?)
    ''', (session['user_id'], book_id, book['user_id'], message))
    conn.commit()
    conn.close()
    
    flash('Book request sent successfully!', 'success')
    return redirect(url_for('browse_books'))

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('home'))

@app.route('/contact')
def contact():
    return render_template('contact.html')

if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', port=5000, debug=True)
