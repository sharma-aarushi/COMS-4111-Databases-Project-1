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
from datetime import date
import re
from markupsafe import Markup

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

# @app.route('/test')
# def test_page():
#     return "Flask is working!"

@app.route('/view/<int:listing_id>')
def view_item(listing_id):
    # Query to get item details along with the owner's name
    query = text("""
        SELECT L.listingid, L.title, L.location, L.category, L.description, L.price, L.condition, 
               L.status, L.link, L.dateadded, U.name AS owner_name
        FROM Listings L
        JOIN Users U ON L.createdby = U.uni
        WHERE L.listingid = :listing_id
    """)

    with g.conn as conn:
        result = conn.execute(query, {'listing_id': listing_id}).fetchone()

    if result is None:
        flash("Listing not found.")
        return redirect(url_for('show_popular_listings'))

    # Convert the result to a dictionary-like object using _mapping
    listing = result._mapping
    return render_template("view-item.html", item=listing)

@app.route('/message_seller/<int:listing_id>', methods=['POST'])
def message_seller(listing_id):
    message = request.form.get('message')
    # Logic to send the message to the seller
    flash("Message sent to the seller.")
    return redirect(url_for('view_item', listing_id=listing_id))

@app.route('/add_to_wishlist/<int:listing_id>', methods=['POST'])
def add_to_wishlist(listing_id):
    # Logic to add item to wishlist
    flash("Item added to wishlist.")
    return redirect(url_for('view_item', listing_id=listing_id))

@app.route('/buy_item/<int:listing_id>', methods=['POST'])
def buy_item(listing_id):
    # Logic to handle the purchase
    flash("Purchase successful.")
    return redirect(url_for('view_item', listing_id=listing_id))

@app.route('/new_listing', methods=['POST'])
def new_listing():
    title = request.form.get('title')
    location = request.form.get('location')
    category = request.form.get('category')
    creatorid = request.form.get('creatorid')
    description = request.form.get('description')
    price = request.form.get('price')
    condition = request.form.get('condition')
    status = request.form.get('status')
    
    # Automatically set today's date
    dateadded = date.today()
    
    if not all([title, location, category, creatorid, description, price, condition, status]):
        flash("All fields are required.")
        return redirect('/new_listing')
    
    try:
        price = float(price)
    except ValueError:
        flash("Invalid price value.")
        return redirect('/new_listing')

    query = text("""
        INSERT INTO Listings (title, location, category, creatorid, description, price, condition, status, dateadded)
        VALUES (:title, :location, :category, :creatorid, :description, :price, :condition, :status, :dateadded)
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
                'status': status,
                'dateadded': dateadded
            })
            flash("Listing created successfully.")
    except Exception as e:
        flash(f"An error occurred: {str(e)}")
        return redirect('/new_listing')

    return redirect('/')

@app.route('/search')
def search():
    keyword = request.args.get('query', '').strip()
    
    if not keyword:
        flash("Please enter a keyword to search.")
        return redirect(url_for('show_popular_listings'))

    # SQL query to search for the keyword in the relevant columns
    query = text("""
        SELECT listingid, title, description, link
        FROM Listings
        WHERE title ILIKE :kw 
           OR location ILIKE :kw
           OR category ILIKE :kw
           OR description ILIKE :kw
           OR condition::TEXT ILIKE :kw
           OR status ILIKE :kw
    """)

    # Use wildcard % for partial matches with the keyword
    search_keyword = f"%{keyword}%"

    with g.conn as conn:
        results = conn.execute(query, {'kw': search_keyword}).fetchall()

    return render_template("search_results.html", keyword=keyword, results=results)

#TODO: Fix highlighting
@app.template_filter('highlight')
def highlight(text, keyword, limit=None):
    # Optional truncation
    if limit and len(text) > limit:
        text = text[:limit] + "..."

    # Escape keyword for any special characters and add markers around matches
    pattern = re.compile(re.escape(keyword), re.IGNORECASE)
    highlighted_text = pattern.sub(r"|||<span class='highlight'>\g<0></span>|||", text)
    
    # Replace the markers to prevent direct HTML injection
    return highlighted_text.replace("|||", "")



######
#USER TESTING
######

from datetime import datetime

@app.route('/messages')
def messages():
    demo_uni = "demo_uni"  # Replace with actual demo user UNI
    query = text("""
        SELECT M.*, U.name AS sender_name, L.title AS listing_title
        FROM Messages M
        JOIN Users U ON M.sender_uni = U.uni
        LEFT JOIN Listings L ON M.listing_id = L.listingid
        WHERE M.sender_uni = :demo_uni OR M.receiver_uni = :demo_uni
        ORDER BY M.timestamp DESC
    """)
    
    with g.conn as conn:
        result = conn.execute(query, {'demo_uni': demo_uni}).fetchall()
    
    messages = [dict(row._mapping) for row in result]
    return render_template("messages.html", messages=messages, demo_uni=demo_uni)


@app.route('/send_message', methods=['POST'])
def send_message():
    demo_uni = "demo_uni"  # Replace with actual demo user UNI
    receiver_uni = request.form.get('receiver_uni')
    listing_id = request.form.get('listing_id')
    message_text = request.form.get('message')

    if not receiver_uni or not message_text:
        flash("Message and receiver are required.")
        return redirect(request.referrer)

    query = text("""
        INSERT INTO Messages (sender_uni, receiver_uni, listing_id, message, timestamp)
        VALUES (:sender_uni, :receiver_uni, :listing_id, :message, :timestamp)
    """)

    with g.conn as conn:
        conn.execute(query, {
            'sender_uni': demo_uni,
            'receiver_uni': receiver_uni,
            'listing_id': listing_id,
            'message': message_text,
            'timestamp': datetime.now()
        })
        flash("Message sent successfully.")
    
    return redirect(url_for('messages'))

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
