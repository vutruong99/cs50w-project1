import os
import json
import requests

from flask import Flask, session, render_template, request, redirect, g, url_for, jsonify
from flask_session import Session
from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker
from helpers import login_required

app = Flask(__name__)

# Check for environment variable
if not os.getenv("DATABASE_URL"):
    raise RuntimeError("DATABASE_URL is not set")

# Configure session to use filesystem
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Set up database
engine = create_engine(os.getenv("DATABASE_URL"))
db = scoped_session(sessionmaker(bind=engine))


@app.route("/")
def index():
    return render_template("index.html")

@app.route("/login", methods=["POST","GET"])
def login():
    name=request.form.get("name")
    password=request.form.get("password")

    session.clear()

    if request.method == "POST":
        if db.execute("SELECT * FROM users WHERE username=:name AND password=:password",{"name":name,"password":password}).rowcount==1:
            session['username']=name
            return redirect(url_for('home'))

    else:
        return render_template('error.html',message="wrong username or password")

@app.route('/home', methods=["POST","GET"])
@login_required
def home():
    return render_template('home.html')


@app.route('/logout')
def logout():
    session.clear()
    return render_template('index.html')

@app.route("/signingup")
def signingup():
    return render_template("signup.html")

@app.route("/signup", methods=["POST"])
def signup():
    session.clear()

    if not request.form.get("name"):
        return render_template("error.html",message="Please provide a username")

    name=request.form.get("name")

    if db.execute("SELECT * FROM users WHERE username=:name", {"name":name}).rowcount !=0:
        return render_template('error.html',message="Username already exists")

    if not request.form.get("password"):
        return render_template("error.html",message="Please provide a password")

    password=request.form.get("password")

    db.execute("INSERT INTO users (username,password) VALUES(:name,:password)",
    {"name":name,"password":password})
    db.commit()

    return render_template('signup-success.html')

@app.route("/search",methods=["POST"])
@login_required
def search():
    query = "%" + request.form.get("query") + "%"

    books = db.execute("SELECT * FROM books WHERE isbn LIKE :query OR LOWER(title) LIKE :query OR title LIKE :query OR author LIKE :query OR LOWER(author) LIKE :query",
    {"query":query}).fetchall()

    if len(books)==0:
        return render_template("home.html",message="No book found")
    else:
       return render_template("home.html", books=books)

@app.route("/book/<isbn>", methods=["POST","GET"])
@login_required
def book(isbn):
    print(isbn)
    if request.method=="POST":
        currentUser = session["username"]


        review = request.form.get("review")
        rating = int(request.form.get("rating"))

        bookISBN = db.execute("SELECT isbn from books where isbn=:isbn", {"isbn":isbn}).fetchone()

        if db.execute("SELECT * FROM reviews WHERE username=:username AND isbn=:isbn", {"username":currentUser, "isbn":isbn}).rowcount!=0:
            return render_template('error.html',message="You have already submitted a review")

        db.execute("INSERT INTO reviews (username, review, rating, isbn) VALUES (:username, :review, :rating, :isbn)", {"username":currentUser,"review":review,"rating":rating,"isbn":isbn})
        db.commit()

        return redirect("/book/" + isbn)
    else:
        currentUser = session["username"]
        book = db.execute("SELECT * FROM books WHERE isbn=:isbn", {"isbn":isbn}).fetchall()

        if book is None:
            return render_template("error.html")

        res_raw = requests.get("https://www.goodreads.com/book/review_counts.json",
        params={"key":"brbzGhv58q1FVtM6Xx9FOg", "isbns":isbn})

        try:
            res = res_raw.json()
        except:
            print(f"Response code: {res_raw.status_code}")
            print(f"Response text: {res_raw.text}")
            raise

        goodreads = res

        reviews = db.execute("SELECT username, review, rating FROM reviews WHERE isbn=:isbn",{"isbn":isbn}).fetchall()

        return render_template("book.html", book=book, goodreads=goodreads, reviews=reviews)

@app.route("/api/<isbn>")
def api(isbn):

    res = db.execute("SELECT books.isbn, title, author, year, COUNT(review) as reviews_count, AVG(rating) as average_rating FROM books JOIN reviews ON books.isbn=reviews.isbn GROUP BY books.isbn, title, author, year", {"isbn":isbn}).fetchone()

    result=dict(res.items())

    result['average_rating'] = float('%.2f'%result['average_rating'])
    return jsonify(result)
