from flask import Flask, render_template, request, redirect, session, flash, url_for
import mysql.connector
from werkzeug.security import generate_password_hash, check_password_hash
from itsdangerous import URLSafeTimedSerializer
from datetime import timedelta

app = Flask(__name__)
app.secret_key = "myverysecretkey"


app.permanent_session_lifetime = timedelta(days=7)


s = URLSafeTimedSerializer(app.secret_key)




def get_db_connection():
    return mysql.connector.connect(
        host="localhost",
        user="root",
        password="root",
        database="flaskbdNotes"
    )




@app.route('/')
def index():
    if 'user_id' in session:
        return redirect('/dashboard')
    return render_template('home.html')


@app.route('/home')
def home():
    return render_template('home.html')


@app.route('/about')
def about():
    return render_template('about.html')


@app.route('/contact')
def contact():
    return render_template('contact.html')




@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username'].strip()
        email = request.form['email'].strip()
        password = request.form['password']

        if not username or not email or not password:
            flash("All fields are required.", "danger")
            return redirect('/register')

        hashed_pw = generate_password_hash(password)

        conn = get_db_connection()
        cur = conn.cursor()

        cur.execute("SELECT id FROM users WHERE username=%s", (username,))
        if cur.fetchone():
            flash("Username already exists.", "danger")
            conn.close()
            return redirect('/register')

        cur.execute("INSERT INTO users (username,email,password) VALUES (%s,%s,%s)",
                    (username, email, hashed_pw))
        conn.commit()
        conn.close()

        flash("Registration successful! Login now.", "success")
        return redirect('/login')

    return render_template("register.html")


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username'].strip()
        password = request.form['password']

        conn = get_db_connection()
        cur = conn.cursor(dictionary=True)

        cur.execute("SELECT * FROM users WHERE username=%s", (username,))
        user = cur.fetchone()
        conn.close()

        if user and check_password_hash(user['password'], password):
            session.permanent = True
            session['user_id'] = user['id']
            session['username'] = user['username']

            flash(f"Welcome, {user['username']}!", "success")
            return redirect('/dashboard')

        flash("Invalid username or password.", "danger")

    return render_template("login.html")


@app.route('/logout')
def logout():
    session.clear()
    flash("Logged out successfully.", "info")
    return redirect('/login')



@app.route('/forgot', methods=['GET', 'POST'])
def forgot():
    if request.method == 'POST':
        email = request.form['email'].strip()

        conn = get_db_connection()
        cur = conn.cursor(dictionary=True)
        cur.execute("SELECT * FROM users WHERE email=%s", (email,))
        user = cur.fetchone()
        conn.close()

        if not user:
            flash("Email not registered.", "danger")
            return redirect('/forgot')

        token = s.dumps(email, salt="reset-password")
        reset_link = url_for('reset_password', token=token, _external=True)

        print("RESET LINK:", reset_link)  

        flash("Password reset link sent! (Check console in dev mode)", "info")
        return redirect('/login')

    return render_template("forgot.html")


@app.route('/reset/<token>', methods=['GET', 'POST'])
def reset_password(token):
    try:
        email = s.loads(token, salt="reset-password", max_age=600)
    except:
        flash("Reset link expired or invalid!", "danger")
        return redirect('/forgot')

    if request.method == 'POST':
        password = request.form['password']
        hashed_pw = generate_password_hash(password)

        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("UPDATE users SET password=%s WHERE email=%s", (hashed_pw, email))
        conn.commit()
        conn.close()

        flash("Password reset successfully!", "success")
        return redirect('/login')

    return render_template("reset.html", token=token)



@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect('/login')

    user_id = session['user_id']

    conn = get_db_connection()
    cur = conn.cursor(dictionary=True)


    cur.execute("SELECT COUNT(*) AS total FROM notes WHERE user_id=%s", (user_id,))
    total = cur.fetchone()['total']

    cur.execute("""
        SELECT created_at, title FROM notes 
        WHERE user_id=%s ORDER BY created_at DESC LIMIT 1
    """, (user_id,))
    last = cur.fetchone()

    cur.execute("SELECT content FROM notes WHERE user_id=%s", (user_id,))
    contents = cur.fetchall()
    total_words = sum(len(n['content'].split()) for n in contents)

    cur.execute("""
        SELECT id, title, created_at FROM notes 
        WHERE user_id=%s ORDER BY created_at DESC LIMIT 5
    """, (user_id,))
    recent = cur.fetchall()

    conn.close()

    return render_template("dashboard.html",
                           total=total,
                           last=last,
                           total_words=total_words,
                           recent=recent)



@app.route('/addnote', methods=['GET', 'POST'])
def addnote():
    if 'user_id' not in session:
        return redirect('/login')

    if request.method == 'POST':
        title = request.form['title'].strip()
        content = request.form['content'].strip()

        conn = get_db_connection()
        cur = conn.cursor()

        cur.execute("INSERT INTO notes (title,content,user_id) VALUES (%s,%s,%s)",
                    (title, content, session['user_id']))
        conn.commit()
        conn.close()

        flash("Note added!", "success")
        return redirect('/viewall')

    return render_template("addnote.html")


@app.route('/viewall')
def viewall():
    if 'user_id' not in session:
        return redirect('/login')

    user_id = session['user_id']
    search = request.args.get('search', '')

    conn = get_db_connection()
    cur = conn.cursor(dictionary=True)

    if search:
        cur.execute("""
            SELECT * FROM notes
            WHERE user_id=%s AND (title LIKE %s OR content LIKE %s)
            ORDER BY created_at DESC
        """, (user_id, f"%{search}%", f"%{search}%"))
    else:
        cur.execute("SELECT * FROM notes WHERE user_id=%s ORDER BY created_at DESC",
                    (user_id,))

    notes = cur.fetchall()
    conn.close()

    return render_template("viewnotes.html", notes=notes, search=search)


@app.route('/viewnotes/<int:id>')
def viewnotes(id):
    if 'user_id' not in session:
        return redirect('/login')

    conn = get_db_connection()
    cur = conn.cursor(dictionary=True)

    cur.execute("SELECT * FROM notes WHERE id=%s AND user_id=%s",
                (id, session['user_id']))
    note = cur.fetchone()

    if not note:
        flash("Unauthorized access!", "danger")
        return redirect('/viewall')

    conn.close()
    return render_template("singlenote.html", note=note)


@app.route('/updatenote/<int:id>', methods=['GET', 'POST'])
def updatenote(id):
    if 'user_id' not in session:
        return redirect('/login')

    conn = get_db_connection()
    cur = conn.cursor(dictionary=True)

    cur.execute("SELECT * FROM notes WHERE id=%s AND user_id=%s",
                (id, session['user_id']))
    note = cur.fetchone()

    if request.method == 'POST':
        title = request.form['title'].strip()
        content = request.form['content'].strip()

        cur2 = conn.cursor()
        cur2.execute("UPDATE notes SET title=%s, content=%s WHERE id=%s",
                     (title, content, id))
        conn.commit()
        conn.close()

        flash("Note updated!", "success")
        return redirect('/viewall')

    return render_template("updatenote.html", note=note)


@app.route('/deletenote/<int:id>', methods=['POST'])
def deletenote(id):
    if 'user_id' not in session:
        return redirect('/login')

    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("DELETE FROM notes WHERE id=%s AND user_id=%s",
                (id, session['user_id']))
    conn.commit()
    conn.close()

    flash("Note deleted!", "info")
    return redirect('/viewall')



if __name__ == "__main__":
    app.run(debug=True)
