from flask import Flask, render_template, redirect, url_for, request, session, jsonify, flash
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from flask_mail import Mail, Message
from werkzeug.security import generate_password_hash, check_password_hash
import os
from sqlalchemy import *
from sqlalchemy.pool import NullPool
from flask import Flask, request, render_template, g, redirect, Response, abort, jsonify
from datetime import datetime
from sqlalchemy import inspect, text


# App setup
tmpl_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'templates')
app = Flask(__name__, template_folder=tmpl_dir)
app.secret_key = 'your_secret_key'

# Database setup
DATABASEURI = "postgresql://as6322:624309@104.196.222.236/proj1part2"
engine = create_engine(DATABASEURI, poolclass=NullPool)

@app.before_request
def before_request():
    try:
        g.conn = engine.connect()
    except:
        print("Problem connecting to database")
        g.conn = None

@app.teardown_request
def teardown_request(exception):
    try:
        g.conn.close()
    except Exception as e:
        pass

@app.route('/')
def show_popular_listings():
    query = text("""
        SELECT L.listingid, L.title AS listing_title, COUNT(IW.listing_id) AS times_added_to_wishlist, L.link
        FROM Listings L
        JOIN In_Wishlist IW ON L.listingid = IW.listing_id
        GROUP BY L.listingid, L.title, L.link
        ORDER BY times_added_to_wishlist DESC
        LIMIT 5 ;
    """)

    with g.conn as conn:
        result = conn.execute(query)
        popular_items = [dict(row._mapping) for row in result]

    return render_template("home.html", popular_items=popular_items)

@app.route('/test')
def test_page():
    return "Flask is working!"

@app.route('/view/<int:listing_id>')
def view_item(listing_id):
    query = text("""
        SELECT title, location, category, creatorid, description, price, condition, status, link
        FROM Listings
        WHERE listingid = :listing_id
    """)

    with g.conn as conn:
        result = conn.execute(query, {'listing_id': listing_id}).fetchone()

    if result is None:
        flash("Listing not found.")
        return redirect(url_for('show_popular_listings'))

    listing = dict(result)
    return render_template("view-item.html", listing=listing)

@app.route('/create_listing', methods=['POST'])
def create_listing():
    title = request.form.get('title')
    location = request.form.get('location')
    category = request.form.get('category')
    creatorid = request.form.get('creatorid')
    description = request.form.get('description')
    price = request.form.get('price')
    condition = request.form.get('condition')
    status = request.form.get('status')
    
    if not all([title, location, category, creatorid, description, price, condition, status]):
        flash("All fields are required.")
        return redirect('/new_listing')
    
    try:
        price = float(price)
    except ValueError:
        flash("Invalid price value.")
        return redirect('/new_listing')

    query = text("""
        INSERT INTO Listings (title, location, category, creatorid, description, price, condition, status)
        VALUES (:title, :location, :category, :creatorid, :description, :price, :condition, :status)
    """)

    try:
        with g.conn as conn:
            conn.execute(query, {
                'title': title,
                'location': location,
                'category': category,
                'creatorid': creatorid,
                'description': description,
                'price': price,
                'condition': condition,
                'status': status
            })
            flash("Listing created successfully.")
    except Exception as e:
        flash(f"An error occurred: {str(e)}")
        return redirect('/new_listing')

    return redirect('/')

if __name__ == "__main__":
    import click

    @click.command()
    @click.option('--debug', is_flag=True)
    @click.option('--threaded', is_flag=True)
    @click.argument('HOST', default='0.0.0.0')
    @click.argument('PORT', default=8111, type=int)
    def run(debug, threaded, host, port):
        HOST, PORT = host, port
        print("running on %s:%d" % (HOST, PORT))
        app.run(host=HOST, port=PORT, debug=debug, threaded=threaded)

    run()
