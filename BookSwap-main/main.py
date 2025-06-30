from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from dotenv import load_dotenv
import hashlib
import os
from datetime import datetime
import re

from supabase import create_client, Client

app = Flask(__name__)
load_dotenv()
app.secret_key = os.getenv("SECRET_KEY")
supabase_url = os.getenv("SUPABASE_URL")
supabase_key = os.getenv("SUPABASE_KEY")
supabase: Client = create_client(supabase_url, supabase_key)
# OAuth setup using OpenID Connect metadata (Fixes jwks_uri error)
from authlib.integrations.flask_client import OAuth

oauth = OAuth(app)

google = oauth.register(
    name='google',
    client_id=os.getenv("GOOGLE_CLIENT_ID"),
    client_secret=os.getenv("GOOGLE_CLIENT_SECRET"),
    server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
    client_kwargs={
        'scope': 'openid email profile'
    }
)

# Database setup
"""def init_db():
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
        gender TEXT,
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
        chat_accepted BOOLEAN DEFAULT 0,
        FOREIGN KEY (requester_id) REFERENCES users (id),
        FOREIGN KEY (book_id) REFERENCES books (id),
        FOREIGN KEY (owner_id) REFERENCES users (id)
    )''')
    
    # Chat messages table
    c.execute('''CREATE TABLE IF NOT EXISTS chat_messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        request_id INTEGER,
        sender_id INTEGER,
        message TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (request_id) REFERENCES book_requests (id),
        FOREIGN KEY (sender_id) REFERENCES users (id)
    )''')
    
    # Add gender column if it doesn't exist
    try:
        c.execute('ALTER TABLE users ADD COLUMN gender TEXT')
    except sqlite3.OperationalError:
        pass
    
    # Add chat_accepted column if it doesn't exist
    try:
        c.execute('ALTER TABLE book_requests ADD COLUMN chat_accepted BOOLEAN DEFAULT 0')
    except sqlite3.OperationalError:
        pass
    
    conn.commit()
    conn.close()

def get_db_connection():
    conn = sqlite3.connect('bookswap.db')
    conn.row_factory = sqlite3.Row
    return conn
"""
def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def validate_vit_email(email):
    pattern = r'^[a-zA-Z0-9._%+-]+@vitstudent\.ac\.in$'
    return re.match(pattern, email) is not None

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/loading')
def loading():
    return render_template('loading.html')


# --- Signin ---
@app.route('/signin', methods=['GET', 'POST'])
def signin():
    if request.method == 'POST':
        email = request.form['email'].lower().strip()
        password = request.form['password']

        if not validate_vit_email(email):
            flash('Please use a valid @vitstudent.ac.in email address', 'error')
            return render_template('signin.html')

        # Query Supabase
        result = supabase.table("users").select("*").eq("email", email).execute()

        if result.data and result.data[0]['password_hash'] == hash_password(password):
            user = result.data[0]
            session['user_id'] = user['id']
            session['user_name'] = user['name']
            session['user_email'] = user['email']
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid email or password', 'error')

    return render_template('signin.html')
@app.route('/login/callback')
def auth_callback():
    try:
        # Step 1: Complete OAuth flow
        token = google.authorize_access_token()
        resp = google.get('https://openidconnect.googleapis.com/v1/userinfo')
        user_info = resp.json()

        email = user_info['email']
        name = user_info.get('name', '')

        # Step 2: Ensure it's a VIT email
        if not email.endswith("@vitstudent.ac.in"):
            flash("Only @vitstudent.ac.in emails are allowed", "error")
            return redirect(url_for('signup'))

        # Step 3: Check if user already exists
        existing_user = supabase.table("users").select("*").eq("email", email).execute().data

        # Step 4: If not, create the user
        if not existing_user:
            supabase.table("users").insert({
                "name": name,
                "email": email,
                "student_id": "",
                "branch": "",
                "semester": "",
                "gender": "",
                "password_hash": ""  # no password needed for Google sign-in
            }).execute()
            # Re-fetch user to get ID
            existing_user = supabase.table("users").select("*").eq("email", email).execute().data

        # Step 5: Store user ID in session
        user_data = existing_user[0]
        session['user_id'] = user_data['id']
        session['user'] = {"email": email, "name": name}

        print("✅ Google sign-in successful:", session['user'])

        return redirect(url_for('dashboard'))

    except Exception as e:
        import traceback
        traceback.print_exc()
        flash("Google sign-up failed. Please try again.", "error")
        return redirect(url_for('signup'))
# --- Signup ---
@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        name = request.form['name'].strip()
        email = request.form['email'].lower().strip()
        password = request.form['password']
        student_id = request.form['student_id'].strip()
        branch = request.form['branch']
        semester = request.form['semester']
        gender = request.form.get('gender', '')

        if not validate_vit_email(email):
            flash('Please use a valid @vitstudent.ac.in email address', 'error')
            return render_template('signup.html')

        if len(password) < 6:
            flash('Password must be at least 6 characters long', 'error')
            return render_template('signup.html')

        try:
            existing_user = supabase.table("users").select("id").eq("email", email).execute().data
            if existing_user:
                flash('An account with this email already exists', 'error')
                return render_template('signup.html')

            supabase.table("users").insert({
                "name": name,
                "email": email,
                "password_hash": hash_password(password),
                "student_id": student_id,
                "branch": branch,
                "semester": semester,
                "gender": gender
            }).execute()

            flash('Account created successfully! Please sign in.', 'success')
            return redirect(url_for('signin'))

        except Exception as e:
            print("Signup error:", e)
            flash("Error creating account. Please try again.", "error")

    return render_template('signup.html')

# --- Dashboard ---
@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('signin'))

    user_id = session['user_id']
    user = session.get('user', {})

    # Fetch user's books
    user_books_res = supabase.table("books").select("*").eq("user_id", user_id).order("created_at", desc=True).execute()
    user_books = user_books_res.data if user_books_res.data else []

    # Fetch requests made by the user
    my_requests_res = supabase.rpc("get_user_requests", {"uid": user_id}).execute()
    requests = my_requests_res.data if my_requests_res.data else []

    # Fetch incoming requests for the user's books
    incoming_res = supabase.rpc("get_incoming_requests", {"uid": user_id}).execute()
    incoming_requests = incoming_res.data if incoming_res.data else []

    return render_template("dashboard.html",
                           user_books=user_books,
                           requests=requests,
                           incoming_requests=incoming_requests,
                           user=user)  # 👈 added thisrequests=incoming_requests)
@app.route('/signup/google')
def signup_google():
    redirect_uri = url_for('auth_callback', _external=True)
    return google.authorize_redirect(redirect_uri)
"""
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
        gender = request.form.get('gender', '')
        
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
                'INSERT INTO users (name, email, password_hash, student_id, branch, semester, gender) VALUES (?, ?, ?, ?, ?, ?, ?)',
                (name, email, hash_password(password), student_id, branch, semester, gender)
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
"""

@app.route('/browse')
def browse_books():
    if 'user_id' not in session:
        return redirect(url_for('signin'))

    user_id = session['user_id']

    # Get filters
    search_query = request.args.get('search', '').strip()
    semester_filter = request.args.get('semester', '')
    branch_filter = request.args.get('branch', '')
    book_type_filter = request.args.get('book_type', '')

    # Get user's own available books
    user_books_res = supabase.table('books') \
        .select('*, users(name)') \
        .eq('user_id', user_id) \
        .eq('is_available', True) \
        .order('created_at', desc=True) \
        .execute()
    user_books = user_books_res.data if user_books_res.data else []

    # Start query for other users' books
    query = supabase.table('books').select('*, users(name)') \
        .neq('user_id', user_id) \
        .eq('is_available', True)

    if search_query:
        query = query.ilike('title', f'%{search_query}%')  # Supabase supports ilike

    if semester_filter:
        query = query.eq('semester', semester_filter)
    if branch_filter:
        query = query.eq('branch', branch_filter)
    if book_type_filter:
        query = query.eq('book_type', book_type_filter)

    books_res = query.order('created_at', desc=True).execute()
    books = books_res.data if books_res.data else []

    return render_template('browse.html', books=books, user_books=user_books)


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
        user_id = session['user_id']

        try:
            result = supabase.table('books').insert({
                "user_id": user_id,
                "title": title,
                "author": author,
                "semester": semester,
                "branch": branch,
                "condition": condition,
                "subjects": subjects,
                "book_type": book_type,
                "is_available": True
            }).execute()

            if result.data:
                flash("Book added successfully!", "success")
            else:
                flash("Failed to add book.", "error")

        except Exception as e:
            print("Add book error:", e)
            flash("An error occurred while adding the book.", "error")

        return redirect(url_for('dashboard'))

    return render_template('add_book.html')

@app.route('/request_book/<int:book_id>', methods=['POST'])
def request_book(book_id):
    if 'user_id' not in session:
        return redirect(url_for('signin'))

    user_id = session['user_id']
    message = request.form.get('message', '').strip()

    try:
        book_res = supabase.table('books').select('*').eq('id', book_id).single().execute().data

        if not book_res:
            flash("Book not found.", "error")
            return redirect(url_for('browse_books'))

        if book_res['user_id'] == user_id:
            flash("You cannot request your own book.", "error")
            return redirect(url_for('browse_books'))

        existing_req = supabase.table('book_requests') \
            .select('id') \
            .eq('requester_id', user_id) \
            .eq('book_id', book_id) \
            .execute().data

        if existing_req:
            flash("You have already requested this book.", "error")
            return redirect(url_for('browse_books'))

        supabase.table('book_requests').insert({
            "requester_id": user_id,
            "book_id": book_id,
            "owner_id": book_res['user_id'],
            "message": message,
            "status": "pending",
            "chat_accepted": False
        }).execute()

        flash("Book request sent successfully!", "success")

    except Exception as e:
        print("Request book error:", e)
        flash("Could not send request.", "error")

    return redirect(url_for('browse_books'))

"""
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
    
    # Get user's own books separately
    user_books = conn.execute('''
        SELECT b.*, u.name as owner_name 
        FROM books b 
        JOIN users u ON b.user_id = u.id 
        WHERE b.user_id = ? AND b.is_available = 1
        ORDER BY b.created_at DESC
    ''', (session['user_id'],)).fetchall()
    
    # Build query for other users' books
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
    
    return render_template('browse.html', books=books, user_books=user_books)

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
"""

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('home'))


@app.route('/accept_request/<int:request_id>', methods=['POST'])
def accept_request(request_id):
    if 'user_id' not in session:
        return redirect(url_for('signin'))

    try:
        # Query book request
        res = supabase.table('book_requests').select('*').eq('id', request_id).execute()

        # Check for response error or empty result
        if not res.data or not isinstance(res.data, list):
            flash("Request not found or invalid data.", "error")
            return redirect(url_for('dashboard'))

        request_data = res.data[0]  # Get the actual request dict

        # Ensure only the book owner can accept
        if request_data.get('owner_id') != session['user_id']:
            flash("Unauthorized action.", "error")
            return redirect(url_for('dashboard'))

        # Mark the request as accepted
        update_req = supabase.table('book_requests') \
            .update({'status': 'accepted'}) \
            .eq('id', request_id) \
            .execute()

        # Mark the book as unavailable
        update_book = supabase.table('books') \
            .update({'is_available': False}) \
            .eq('id', request_data['book_id']) \
            .execute()

        # Flash result
        if update_req.data and update_book.data:
            flash("Book request accepted and marked as unavailable.", "success")
        else:
            flash("Request updated, but book status may not be correct.", "warning")

    except Exception as e:
        flash(f"An unexpected error occurred: {str(e)}", "error")

    return redirect(url_for('dashboard'))



@app.route('/decline_request/<int:request_id>', methods=['POST'])
def decline_request(request_id):
    if 'user_id' not in session:
        return redirect(url_for('signin'))

    user_id = session['user_id']

    try:
        # First, fetch the request to validate ownership
        res = supabase.table('book_requests').select('*').eq('id', request_id).execute()

        if not res.data or not isinstance(res.data, list):
            flash("Request not found.", "error")
            return redirect(url_for('dashboard'))

        request_data = res.data[0]

        if request_data.get('owner_id') != user_id:
            flash("Unauthorized action.", "error")
            return redirect(url_for('dashboard'))

        # Proceed to update the status to declined
        update_res = supabase.table('book_requests') \
            .update({'status': 'declined'}) \
            .eq('id', request_id) \
            .execute()

        if update_res.data:
            flash('Book request declined.', 'info')
        else:
            flash('Failed to decline the request.', 'error')

    except Exception as e:
        flash(f"Unexpected error: {str(e)}", 'error')

    return redirect(url_for('dashboard'))


@app.route('/edit_profile', methods=['GET', 'POST'])
def edit_profile():
    if 'user_id' not in session:
        return redirect(url_for('signin'))

    user_id = session['user_id']

    if request.method == 'POST':
        name = request.form['name'].strip()
        student_id = request.form['student_id'].strip()
        branch = request.form['branch']
        semester = request.form['semester']
        gender = request.form['gender']

        supabase.table('users').update({
            'name': name,
            'student_id': student_id,
            'branch': branch,
            'semester': semester,
            'gender': gender
        }).eq('id', user_id).execute()

        session['user_name'] = name
        flash('Profile updated successfully!', 'success')
        return redirect(url_for('dashboard'))

    # Fetch current user info
    user_res = supabase.table('users').select('*').eq('id', user_id).single().execute()
    user = user_res.data if user_res.data else {}

    return render_template('edit_profile.html', user=user)


@app.route('/exchange_history')
def exchange_history():
    if 'user_id' not in session:
        return redirect(url_for('signin'))

    user_id = session['user_id']

    # Get all requests the user sent
    sent_res = supabase.rpc("get_user_requests", {"uid": user_id}).execute()
    sent_requests = sent_res.data if sent_res.data else []

    # Get all requests the user received
    received_res = supabase.rpc("get_incoming_requests", {"uid": user_id}).execute()
    received_requests = received_res.data if received_res.data else []

    accepted_sent = len([r for r in sent_requests if r['status'] == 'accepted'])
    accepted_received = len([r for r in received_requests if r['status'] == 'accepted'])
    total_swapped = accepted_sent + accepted_received

    return render_template('exchange_history.html',
                           sent_requests=sent_requests,
                           received_requests=received_requests,
                           total_swapped=total_swapped)

"""
@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('home'))

@app.route('/accept_request/<int:request_id>')
def accept_request(request_id):
    if 'user_id' not in session:
        return redirect(url_for('signin'))
    
    conn = get_db_connection()
    
    # Update request status
    conn.execute(
        'UPDATE book_requests SET status = ? WHERE id = ? AND owner_id = ?',
        ('accepted', request_id, session['user_id'])
    )
    conn.commit()
    conn.close()
    
    flash('Book request accepted!', 'success')
    return redirect(url_for('dashboard'))

@app.route('/decline_request/<int:request_id>')
def decline_request(request_id):
    if 'user_id' not in session:
        return redirect(url_for('signin'))
    
    conn = get_db_connection()
    
    # Update request status
    conn.execute(
        'UPDATE book_requests SET status = ? WHERE id = ? AND owner_id = ?',
        ('declined', request_id, session['user_id'])
    )
    conn.commit()
    conn.close()
    
    flash('Book request declined.', 'info')
    return redirect(url_for('dashboard'))

@app.route('/edit_profile', methods=['GET', 'POST'])
def edit_profile():
    if 'user_id' not in session:
        return redirect(url_for('signin'))
    
    if request.method == 'POST':
        name = request.form['name'].strip()
        student_id = request.form['student_id'].strip()
        branch = request.form['branch']
        semester = request.form['semester']
        gender = request.form['gender']
        
        conn = get_db_connection()
        conn.execute('''
            UPDATE users SET name = ?, student_id = ?, branch = ?, semester = ?, gender = ?
            WHERE id = ?
        ''', (name, student_id, branch, semester, gender, session['user_id']))
        conn.commit()
        conn.close()
        
        session['user_name'] = name
        flash('Profile updated successfully!', 'success')
        return redirect(url_for('dashboard'))
    
    # Get current user data
    conn = get_db_connection()
    user = conn.execute('SELECT * FROM users WHERE id = ?', (session['user_id'],)).fetchone()
    conn.close()
    
    return render_template('edit_profile.html', user=user)

@app.route('/exchange_history')
def exchange_history():
    if 'user_id' not in session:
        return redirect(url_for('signin'))
    
    conn = get_db_connection()
    
    # Get all user's request history
    sent_requests = conn.execute('''
        SELECT br.*, b.title, b.author, u.name as owner_name 
        FROM book_requests br 
        JOIN books b ON br.book_id = b.id 
        JOIN users u ON br.owner_id = u.id 
        WHERE br.requester_id = ? 
        ORDER BY br.created_at DESC
    ''', (session['user_id'],)).fetchall()
    
    # Get requests for user's books
    received_requests = conn.execute('''
        SELECT br.*, b.title, b.author, u.name as requester_name 
        FROM book_requests br 
        JOIN books b ON br.book_id = b.id 
        JOIN users u ON br.requester_id = u.id 
        WHERE br.owner_id = ? 
        ORDER BY br.created_at DESC
    ''', (session['user_id'],)).fetchall()
    
    # Calculate stats
    accepted_sent = len([r for r in sent_requests if r['status'] == 'accepted'])
    accepted_received = len([r for r in received_requests if r['status'] == 'accepted'])
    total_swapped = accepted_sent + accepted_received
    
    conn.close()
    
    return render_template('exchange_history.html', 
                         sent_requests=sent_requests,
                         received_requests=received_requests,
                         total_swapped=total_swapped)
"""
@app.route('/contact')
def contact():
    return render_template('contact.html')

@app.route('/swapmates')
def swapmates():
    if 'user_id' not in session:
        return redirect(url_for('signin'))

    user_id = session['user_id']

    response = supabase.rpc("get_chat_requests", {"uid": user_id}).execute()
    chat_requests = response.data if response.data else []

    return render_template('swapmates.html', chat_requests=chat_requests)

@app.route('/accept_chat/<int:request_id>')
def accept_chat(request_id):
    if 'user_id' not in session:
        return redirect(url_for('signin'))

    supabase.table('book_requests') \
        .update({'chat_accepted': True}) \
        .eq('id', request_id) \
        .or_(f'owner_id.eq.{session["user_id"]},requester_id.eq.{session["user_id"]}') \
        .execute()

    flash('Chat accepted! You can now message each other in SwapMates.', 'success')
    return redirect(url_for('chat', request_id=request_id))


@app.route('/chat/<int:request_id>')
def chat(request_id):
    if 'user_id' not in session:
        return redirect(url_for('signin'))

    uid = session['user_id']

    request_res = supabase.rpc("get_chat_details", {"rid": request_id, "uid": uid}).execute()
    request_data = request_res.data[0] if request_res.data else None

    if not request_data:
        flash('Chat not found or access denied.', 'error')
        return redirect(url_for('swapmates'))

    messages = supabase.table('chat_messages') \
        .select('*, users(name)') \
        .eq('request_id', request_id) \
        .order('created_at', desc=False) \
        .execute().data

    partner_name = request_data['owner_name'] if uid == request_data['requester_id'] else request_data['requester_name']

    return render_template('chat.html', request_data=request_data, messages=messages, chat_partner_name=partner_name)


"""
@app.route('/swapmates')
def swapmates():
    if 'user_id' not in session:
        return redirect(url_for('signin'))
    
    conn = get_db_connection()
    
    # Get all accepted requests (both where chat is enabled and where it needs to be enabled)
    chat_requests = conn.execute('''
        SELECT br.*, b.title, b.author, 
               CASE 
                   WHEN br.requester_id = ? THEN u_owner.name 
                   ELSE u_requester.name 
               END as chat_partner_name,
               CASE 
                   WHEN br.requester_id = ? THEN br.owner_id 
                   ELSE br.requester_id 
               END as chat_partner_id
        FROM book_requests br 
        JOIN books b ON br.book_id = b.id 
        JOIN users u_owner ON br.owner_id = u_owner.id
        JOIN users u_requester ON br.requester_id = u_requester.id
        WHERE (br.requester_id = ? OR br.owner_id = ?) 
        AND br.status = 'accepted'
        ORDER BY br.created_at DESC
    ''', (session['user_id'], session['user_id'], session['user_id'], session['user_id'])).fetchall()
    
    conn.close()
    
    return render_template('swapmates.html', chat_requests=chat_requests)

@app.route('/accept_chat/<int:request_id>')
def accept_chat(request_id):
    if 'user_id' not in session:
        return redirect(url_for('signin'))
    
    conn = get_db_connection()
    
    # Update chat acceptance
    conn.execute(
        'UPDATE book_requests SET chat_accepted = 1 WHERE id = ? AND (owner_id = ? OR requester_id = ?)',
        (request_id, session['user_id'], session['user_id'])
    )
    conn.commit()
    conn.close()
    
    flash('Chat accepted! You can now message each other in SwapMates.', 'success')
    return redirect(url_for('dashboard'))

@app.route('/chat/<int:request_id>')
def chat(request_id):
    if 'user_id' not in session:
        return redirect(url_for('signin'))
    
    conn = get_db_connection()
    
    # Verify user is part of this chat
    request_data = conn.execute('''
        SELECT br.*, b.title, b.author, u_owner.name as owner_name, u_requester.name as requester_name
        FROM book_requests br 
        JOIN books b ON br.book_id = b.id 
        JOIN users u_owner ON br.owner_id = u_owner.id
        JOIN users u_requester ON br.requester_id = u_requester.id
        WHERE br.id = ? AND (br.owner_id = ? OR br.requester_id = ?) AND br.chat_accepted = 1
    ''', (request_id, session['user_id'], session['user_id'])).fetchone()
    
    if not request_data:
        flash('Chat not found or access denied.', 'error')
        return redirect(url_for('swapmates'))
    
    # Get chat messages
    messages = conn.execute('''
        SELECT cm.*, u.name as sender_name
        FROM chat_messages cm
        JOIN users u ON cm.sender_id = u.id
        WHERE cm.request_id = ?
        ORDER BY cm.created_at ASC
    ''', (request_id,)).fetchall()
    
    conn.close()
    
    chat_partner_name = request_data['owner_name'] if session['user_id'] == request_data['requester_id'] else request_data['requester_name']
    
    return render_template('chat.html', request_data=request_data, messages=messages, chat_partner_name=chat_partner_name)

"""
@app.route('/send_message', methods=['POST'])
def send_message():
    if 'user_id' not in session:
        return jsonify({'error': 'Not authenticated'}), 401

    uid = session['user_id']
    request_id = int(request.form['request_id'])
    message = request.form['message'].strip()

    if not message:
        return jsonify({'error': 'Message cannot be empty'}), 400

    # Check chat permission
    valid = supabase.table('book_requests') \
        .select('id') \
        .eq('id', request_id) \
        .eq('chat_accepted', True) \
        .or_(f'owner_id.eq.{uid},requester_id.eq.{uid}') \
        .execute().data

    if not valid:
        return jsonify({'error': 'Access denied'}), 403

    supabase.table('chat_messages').insert({
        'request_id': request_id,
        'sender_id': uid,
        'message': message
    }).execute()

    return jsonify({'success': True})

@app.route('/api/check_updates')
def check_updates():
    if 'user_id' not in session:
        return jsonify({'error': 'Not authenticated'}), 401

    user_id = session['user_id']
    last_update_str = request.args.get('last_update')

    if not last_update_str:
        return jsonify({'error': 'Missing last_update'}), 400

    try:
        # Convert ISO 8601 timestamp string to datetime format
        last_update = datetime.fromisoformat(last_update_str.replace("Z", "+00:00"))
    except ValueError:
        return jsonify({'error': 'Invalid timestamp format'}), 400

    last_update_iso = last_update.isoformat()

    # Check for new requests to user (as owner)
    new_requests = supabase.table("book_requests") \
        .select("id") \
        .eq("owner_id", user_id) \
        .gt("created_at", last_update_iso) \
        .execute().data

    # Check for status updates (as requester)
    status_updates = supabase.table("book_requests") \
        .select("id") \
        .eq("requester_id", user_id) \
        .gt("created_at", last_update_iso) \
        .execute().data

    # Get all chat_messages since last update
    new_messages = supabase.table("chat_messages") \
        .select("id, request_id, sender_id, created_at") \
        .gt("created_at", last_update_iso) \
        .neq("sender_id", user_id) \
        .execute().data

    # Get related request_ids where user is either requester or owner
    request_ids = supabase.table("book_requests") \
        .select("id") \
        .or_(f"owner_id.eq.{user_id},requester_id.eq.{user_id}") \
        .execute().data

    valid_request_ids = {r["id"] for r in request_ids}
    relevant_messages = [msg for msg in new_messages if msg["request_id"] in valid_request_ids]

    total_notifications = len(new_requests) + len(status_updates) + len(relevant_messages)

    return jsonify({
        'has_updates': total_notifications > 0,
        'notification_count': total_notifications,
        'refresh_needed': total_notifications > 0
    })

@app.route('/api/notifications')
def api_notifications():
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({"notifications": []})

    try:
        status_updates = supabase.table("book_requests") \
            .select("id, status, message, created_at") \
            .or_(f"owner_id.eq.{user_id},requester_id.eq.{user_id}") \
            .order("created_at", desc=True) \
            .limit(5) \
            .execute().data

        notifications = []
        for update in status_updates:
            status = update["status"].capitalize()
            time_str = update["created_at"][:19].replace("T", " ")
            notifications.append({
                "title": f"Request {status}",
                "message": update.get("message", ""),
                "time": time_str,
                "read": False  # Add logic if you track read status
            })

        return jsonify({"notifications": notifications})
    except Exception as e:
        print("Notification error:", e)
        return jsonify({"notifications": []})

@app.route('/api/get_new_messages')
def get_new_messages():
    user_id = session.get('user_id')
    request_id = request.args.get('request_id')
    last_update = request.args.get('last_update')

    if not user_id or not request_id or not last_update:
        return jsonify({'messages': []})

    new_messages = (
        supabase.table('chat_messages')
        .select('id, message, sender_id, request_id, created_at, users(name)')
        .eq('request_id', request_id)
        .gt('created_at', last_update)
        .neq('sender_id', user_id)  # This is now safe!
        .order("created_at")
        .execute()
        .data
    )

    return jsonify({'messages': new_messages})

"""
@app.route('/send_message', methods=['POST'])
def send_message():
    if 'user_id' not in session:
        return jsonify({'error': 'Not authenticated'}), 401
    
    request_id = request.form['request_id']
    message = request.form['message'].strip()
    
    if not message:
        return jsonify({'error': 'Message cannot be empty'}), 400
    
    conn = get_db_connection()
    
    # Verify user is part of this chat
    request_data = conn.execute(
        'SELECT * FROM book_requests WHERE id = ? AND (owner_id = ? OR requester_id = ?) AND chat_accepted = 1',
        (request_id, session['user_id'], session['user_id'])
    ).fetchone()
    
    if not request_data:
        conn.close()
        return jsonify({'error': 'Access denied'}), 403
    
    # Insert message
    conn.execute('''
        INSERT INTO chat_messages (request_id, sender_id, message)
        VALUES (?, ?, ?)
    ''', (request_id, session['user_id'], message))
    conn.commit()
    conn.close()
    
    return jsonify({'success': True})

@app.route('/api/check_updates')
def check_updates():
    if 'user_id' not in session:
        return jsonify({'error': 'Not authenticated'}), 401
    
    last_update = request.args.get('last_update', 0, type=int)
    
    conn = get_db_connection()
    
    # Check for new requests since last update
    new_requests = conn.execute('''
        SELECT COUNT(*) as count FROM book_requests 
        WHERE owner_id = ? AND created_at > datetime(?, 'unixepoch', 'localtime')
    ''', (session['user_id'], last_update / 1000)).fetchone()
    
    # Check for request status updates
    status_updates = conn.execute('''
        SELECT COUNT(*) as count FROM book_requests 
        WHERE requester_id = ? AND created_at > datetime(?, 'unixepoch', 'localtime')
    ''', (session['user_id'], last_update / 1000)).fetchone()
    
    # Check for new chat messages
    new_messages = conn.execute('''
        SELECT COUNT(*) as count FROM chat_messages cm
        JOIN book_requests br ON cm.request_id = br.id
        WHERE (br.requester_id = ? OR br.owner_id = ?) AND cm.sender_id != ?
        AND cm.created_at > datetime(?, 'unixepoch', 'localtime')
    ''', (session['user_id'], session['user_id'], session['user_id'], last_update / 1000)).fetchone()
    
    conn.close()
    
    total_notifications = (new_requests['count'] if new_requests else 0) + \
                         (status_updates['count'] if status_updates else 0) + \
                         (new_messages['count'] if new_messages else 0)
    
    return jsonify({
        'has_updates': total_notifications > 0,
        'notification_count': total_notifications,
        'refresh_needed': total_notifications > 0
    })
"""
@app.route('/api/notifications')
def get_notifications():
    if 'user_id' not in session:
        return jsonify({'error': 'Not authenticated'}), 401

    user_id = session['user_id']
    notifications = []

    # 1. Incoming book requests (status = 'pending' where user is owner)
    incoming_requests = supabase.table('book_requests') \
        .select('id, message, created_at, book_id, requester_id, books(title), users!requester_id(name)') \
        .eq('owner_id', user_id) \
        .eq('status', 'pending') \
        .order('created_at', desc=True) \
        .limit(5) \
        .execute().data

    for req in incoming_requests:
        title = req['books']['title']
        requester_name = req['users']['name']
        notifications.append({
            'title': 'New Book Request',
            'message': f'{requester_name} wants to exchange "{title}"',
            'time': req['created_at'],
            'read': False
        })

    # 2. Status updates on user's own requests (not pending)
    status_updates = supabase.table('book_requests') \
        .select('id, status, created_at, book_id, owner_id, books(title), users!owner_id(name)') \
        .eq('requester_id', user_id) \
        .not_('status', 'eq', 'pending') \
        .order('created_at', desc=True) \
        .limit(5) \
        .execute().data

    for update in status_updates:
        status_text = '✅ Accepted' if update['status'] == 'accepted' else '❌ Declined'
        title = update['books']['title']
        notifications.append({
            'title': f'Request {status_text}',
            'message': f'Your request for "{title}" was {update["status"]}',
            'time': update['created_at'],
            'read': False
        })

    # 3. New chat messages from others in accepted requests
    new_messages = supabase.table('chat_messages') \
        .select('id, created_at, message, sender_id, request_id, users(name), book_requests!inner(book_id, owner_id, requester_id, books(title))') \
        .neq('sender_id', user_id) \
        .order('created_at', desc=True) \
        .limit(10) \
        .execute().data

    for msg in new_messages:
        req = msg['book_requests']
        if req['owner_id'] == user_id or req['requester_id'] == user_id:
            sender_name = msg['users']['name']
            title = req['books']['title']
            notifications.append({
                'title': 'New Message',
                'message': f'{sender_name} sent you a message about "{title}"',
                'time': msg['created_at'],
                'read': False
            })

    # Sort all notifications by time
    notifications.sort(key=lambda x: x['time'], reverse=True)

    return jsonify({'notifications': notifications[:10]})

"""
@app.route('/api/notifications')
def get_notifications():
    if 'user_id' not in session:
        return jsonify({'error': 'Not authenticated'}), 401
    
    conn = get_db_connection()
    
    notifications = []
    
    # Get incoming book requests
    incoming_requests = conn.execute('''
        SELECT br.*, b.title, u.name as requester_name
        FROM book_requests br
        JOIN books b ON br.book_id = b.id
        JOIN users u ON br.requester_id = u.id
        WHERE br.owner_id = ? AND br.status = 'pending'
        ORDER BY br.created_at DESC LIMIT 5
    ''', (session['user_id'],)).fetchall()
    
    for req in incoming_requests:
        notifications.append({
            'title': 'New Book Request',
            'message': f'{req["requester_name"]} wants to exchange "{req["title"]}"',
            'time': req['created_at'],
            'read': False
        })
    
    # Get request status updates
    status_updates = conn.execute('''
        SELECT br.*, b.title, u.name as owner_name
        FROM book_requests br
        JOIN books b ON br.book_id = b.id
        JOIN users u ON br.owner_id = u.id
        WHERE br.requester_id = ? AND br.status != 'pending'
        ORDER BY br.created_at DESC LIMIT 5
    ''', (session['user_id'],)).fetchall()
    
    for update in status_updates:
        status_text = '✅ Accepted' if update['status'] == 'accepted' else '❌ Declined'
        notifications.append({
            'title': f'Request {status_text}',
            'message': f'Your request for "{update["title"]}" was {update["status"]}',
            'time': update['created_at'],
            'read': False
        })
    
    # Get new chat messages
    new_messages = conn.execute('''
        SELECT cm.*, br.id as request_id, b.title, u.name as sender_name
        FROM chat_messages cm
        JOIN book_requests br ON cm.request_id = br.id
        JOIN books b ON br.book_id = b.id
        JOIN users u ON cm.sender_id = u.id
        WHERE (br.requester_id = ? OR br.owner_id = ?) AND cm.sender_id != ?
        ORDER BY cm.created_at DESC LIMIT 5
    ''', (session['user_id'], session['user_id'], session['user_id'])).fetchall()
    
    for msg in new_messages:
        notifications.append({
            'title': 'New Message',
            'message': f'{msg["sender_name"]} sent you a message about "{msg["title"]}"',
            'time': msg['created_at'],
            'read': False
        })
    
    conn.close()
    
    # Sort by time
    notifications.sort(key=lambda x: x['time'], reverse=True)
    
    return jsonify({'notifications': notifications[:10]})
"""

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
