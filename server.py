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

# Global variable to store the current user's UNI
current_user = None

# Database connection management
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

# Login route
@app.route('/login', methods=['GET', 'POST'])
def login():
    global current_user  # Use global variable to set current user

    if request.method == 'POST':
        uni = request.form.get('uni')
        
        # Query to verify UNI exists in the Users table
        query = text("SELECT * FROM Users WHERE uni = :uni")
        with g.conn as conn:
            result = conn.execute(query, {'uni': uni}).fetchone()
        
        if result:
            # UNI exists, set global current_user
            current_user = uni
            flash("Login successful.")
            return redirect(url_for('profile'))
        else:
            flash("User does not exist. Please try again.")
            return redirect(url_for('login'))
    
    return render_template("login.html")

# Logout route
@app.route('/logout')
def logout():
    global current_user
    current_user = None  # Clear the current user
    flash("Logged out successfully.")
    return redirect(url_for('login'))
    
# Utility function to check if user is logged in
def is_logged_in():
    global current_user
    return current_user is not None

# Utility function to check if user is logged in
def get_current_user():
    return current_user

@app.context_processor
def inject_user():
    return {'current_user': current_user}

# Home page with popular listings
@app.route('/')
def show_popular_listings():
    query = text("""
        SELECT L.listingid, L.title AS listing_title, COUNT(IW.listing_id) AS times_added_to_wishlist, L.link
        FROM Listings L
        JOIN In_Wishlist IW ON L.listingid = IW.listing_id
        GROUP BY L.listingid, L.title, L.link
        ORDER BY times_added_to_wishlist DESC
        LIMIT 5;
    """)

    with g.conn as conn:
        result = conn.execute(query)
        popular_items = [dict(row._mapping) for row in result]

    return render_template("home.html", popular_items=popular_items)

# Profile route
@app.route('/profile')
def profile():
    user_uni = get_current_user()
    if not user_uni:
        flash("Please log in to access your profile.")
        return redirect(url_for('login'))
    
    with g.conn as conn:
        # Fetch listings for the logged-in UNI
        listings_query = text("SELECT listingid, title, dateadded FROM Listings WHERE createdby = :user_uni")
        listings = conn.execute(listings_query, {'user_uni': user_uni}).fetchall()
        
        # Fetch the user's name
        user_query = text("SELECT name FROM Users WHERE uni = :user_uni")
        user_name = conn.execute(user_query, {'user_uni': user_uni}).scalar()

    return render_template("profile.html", listings=listings, user_name=user_name)

# View item
@app.route('/view_item/<int:listing_id>')
def view_item(listing_id):
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

    listing = result._mapping
    return render_template("view-item.html", item=listing)

# Add to wishlist
@app.route('/add_to_wishlist/<int:listing_id>', methods=['POST'])
def add_to_wishlist(listing_id):
    user_uni = get_current_user()
    if not user_uni:
        flash("Please log in to add items to your wishlist.")
        return redirect(url_for('login'))

    query = text("INSERT INTO In_Wishlist (uni, listing_id) VALUES (:user_uni, :listing_id)")
    with g.conn as conn:
        conn.execute(query, {'user_uni': user_uni, 'listing_id': listing_id})
        g.conn.commit()
    
    flash("Item added to wishlist.")
    return redirect(url_for('view_item', listing_id=listing_id))

@app.route('/new_listing', methods=['GET', 'POST'])
def new_listing():
    user_uni = get_current_user()
    if not user_uni:
        flash("Please log in to create a new listing.")
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        title = request.form.get('title')
        location = request.form.get('location')
        category = request.form.get('category')
        description = request.form.get('description')
        price = request.form.get('price')
        condition = request.form.get('condition')
        status = request.form.get('status')
        link = request.form.get('link')
        createdby = user_uni  # Assign the logged-in user's UNI

        dateadded = date.today()

        if not all([title, location, category, description, price, condition, status, link]):
            flash("All fields, including the link, are required.")
            return redirect(url_for('new_listing'))
        
        try:
            price = float(price)
        except ValueError:
            flash("Invalid price value.")
            return redirect(url_for('new_listing'))

        query = text("""
            INSERT INTO Listings (title, location, category, createdby, description, price, condition, status, link, dateadded)
            VALUES (:title, :location, :category, :createdby, :description, :price, :condition, :status, :link, :dateadded)
        """)

        try:
            with g.conn as conn:
                conn.execute(query, {
                    'title': title,
                    'location': location,
                    'category': category,
                    'createdby': createdby,
                    'description': description,
                    'price': price,
                    'condition': condition,
                    'status': status,
                    'link': link,
                    'dateadded': dateadded
                })
                g.conn.commit()
                flash("Listing created successfully.")
        except Exception as e:
            print(f"An error occurred during insertion: {e}")
            flash("An error occurred while inserting data. Ensure all fields are correct.")
            return redirect(url_for('new_listing'))

        return redirect(url_for('show_popular_listings'))

    return render_template("create_listing.html")

# Edit Listing
@app.route('/edit_listing/<int:listing_id>', methods=['GET', 'POST'])
def edit_listing(listing_id):
    user_uni = get_current_user()
    if not user_uni:
        flash("Please log in to edit the listing.")
        return redirect(url_for('login'))

    if request.method == 'POST':
        title = request.form.get('title')
        location = request.form.get('location')
        category = request.form.get('category')
        description = request.form.get('description')
        price = request.form.get('price')
        condition = request.form.get('condition')
        status = request.form.get('status')
        link = request.form.get('link')

        try:
            price = float(price)
        except ValueError:
            flash("Invalid price value.")
            return redirect(url_for('edit_listing', listing_id=listing_id))

        query = text("""
            UPDATE Listings
            SET title = :title, location = :location, category = :category, description = :description,
                price = :price, condition = :condition, status = :status, link = :link
            WHERE listingid = :listing_id AND createdby = :user_uni
        """)
        
        try:
            with g.conn as conn:
                conn.execute(query, {
                    'title': title,
                    'location': location,
                    'category': category,
                    'description': description,
                    'price': price,
                    'condition': condition,
                    'status': status,
                    'link': link,
                    'listing_id': listing_id,
                    'user_uni': user_uni
                })
                g.conn.commit()
                flash("Listing updated successfully.")
        except Exception as e:
            print(f"Error during update: {e}")
            flash("An error occurred while updating the listing.")
            return redirect(url_for('edit_listing', listing_id=listing_id))

        return redirect(url_for('profile'))
    
    query = text("""
        SELECT listingid, title, location, category, description, price, condition, status, link
        FROM Listings
        WHERE listingid = :listing_id AND createdby = :user_uni
    """)

    with g.conn as conn:
        result = conn.execute(query, {'listing_id': listing_id, 'user_uni': user_uni}).fetchone()
    
    if result:
        listing = result._mapping
        return render_template("edit_listing.html", listing=listing)
    else:
        flash("Listing not found or unauthorized.")
        return redirect(url_for('profile'))

# Delete Listing
@app.route('/delete_listing/<int:listing_id>', methods=['POST'])
def delete_listing(listing_id):
    user_uni = get_current_user()
    if not user_uni:
        flash("Please log in to delete the listing.")
        return redirect(url_for('login'))

    query = text("""
        DELETE FROM Listings 
        WHERE listingid = :listing_id AND createdby = :user_uni
    """)

    try:
        with g.conn as conn:
            result = conn.execute(query, {'listing_id': listing_id, 'user_uni': user_uni})
            g.conn.commit()
            flash("Listing deleted successfully.")
    except Exception as e:
        print(f"An error occurred during deletion: {e}")
        flash("An error occurred while trying to delete the listing.")
    
    return redirect(url_for('profile'))

@app.route('/message_seller/<int:listing_id>', methods=['POST'])
def message_seller(listing_id):
    user_uni = get_current_user()
    if not user_uni:
        flash("Please log in to send a message to the seller.")
        return redirect(url_for('login'))

    message = request.form.get('message')
    query = text("SELECT createdby FROM Listings WHERE listingid = :listing_id")

    with g.conn as conn:
        result = conn.execute(query, {'listing_id': listing_id}).fetchone()

        if result is None:
            flash("Seller not found.")
            return redirect(url_for('view_item', listing_id=listing_id))

        recipient_uni = result._mapping['createdby']

        insert_query = text("""
            INSERT INTO Messages (content, timestamp, sender, receiver)
            VALUES (:content, :timestamp, :sender, :receiver)
        """)

        conn.execute(insert_query, {
            'content': message,
            'timestamp': datetime.now(),
            'sender': user_uni,
            'receiver': recipient_uni
        })
        conn.commit()

    flash("Message sent to the seller.")
    return redirect(url_for('view_item', listing_id=listing_id))

# Message Overview
@app.route('/messages_overview')
def message_overview():
    user_uni = get_current_user()
    if not user_uni:
        flash("Please log in to view your messages.")
        return redirect(url_for('login'))

    query = text("""
        SELECT DISTINCT CASE 
            WHEN sender = :user_uni THEN receiver 
            ELSE sender 
        END AS other_user
        FROM Messages
        WHERE sender = :user_uni OR receiver = :user_uni
    """)

    with g.conn as conn:
        conversations = conn.execute(query, {'user_uni': user_uni}).fetchall()

    return render_template("message_overview.html", conversations=conversations)

# View specific conversation
@app.route('/messages/<string:recipient_uni>')
def view_conversation(recipient_uni):
    user_uni = get_current_user()
    if not user_uni:
        flash("Please log in to view messages.")
        return redirect(url_for('login'))

    query = text("""
        SELECT content, timestamp, sender, receiver
        FROM Messages
        WHERE (sender = :user_uni AND receiver = :recipient_uni) 
           OR (sender = :recipient_uni AND receiver = :user_uni)
        ORDER BY timestamp
    """)

    with g.conn as conn:
        messages = conn.execute(query, {
            'user_uni': user_uni,
            'recipient_uni': recipient_uni
        }).fetchall()

    return render_template("view_conversation.html", messages=messages, recipient_uni=recipient_uni)

@app.route('/search', methods=['GET'])
def search():
    keyword = request.args.get('query', '').strip()

    if not keyword:
        flash("Please enter a keyword to search.")
        return redirect(url_for('show_popular_listings'))

    query = text("""
        SELECT listingid, title, description, link
        FROM Listings
        WHERE title ILIKE :kw 
           OR description ILIKE :kw
    """)
    search_keyword = f"%{keyword}%"
    
    with g.conn as conn:
        results = conn.execute(query, {'kw': search_keyword}).fetchall()

    return render_template("search_results.html", keyword=keyword, results=results)

@app.route('/advanced_search', methods=['GET'])
def advanced_search():
    if request.args:
        keyword = request.args.get('query', '').strip()
        location = request.args.get('location', '').strip()
        min_price = request.args.get('min_price')
        max_price = request.args.get('max_price')
        condition = request.args.get('condition', '').strip()
        status = request.args.get('status', '').strip()
        date_added = request.args.get('date_added')

        query = """
            SELECT listingid, title, description, price, condition, status, location, link, dateadded
            FROM Listings
            WHERE TRUE
        """
        filters = {}

        if keyword:
            query += " AND (title ILIKE :keyword OR description ILIKE :keyword)"
            filters['keyword'] = f"%{keyword}%"
        if location:
            query += " AND location ILIKE :location"
            filters['location'] = f"%{location}%"
        if min_price:
            query += " AND price >= :min_price"
            filters['min_price'] = min_price
        if max_price:
            query += " AND price <= :max_price"
            filters['max_price'] = max_price
        if condition:
            query += " AND condition = :condition"
            filters['condition'] = condition
        if status:
            query += " AND status = :status"
            filters['status'] = status
        if date_added:
            query += " AND dateadded >= :date_added"
            filters['date_added'] = date_added

        with g.conn as conn:
            results = conn.execute(text(query), filters).fetchall()

        return render_template("search_results.html", keyword=keyword, results=results)

    return render_template("advanced_search.html")

import re
from markupsafe import Markup

# Highlight filter to be used in Jinja templates
@app.template_filter('highlight')
def highlight(text, keyword, limit=None):
    if limit and len(text) > limit:
        text = text[:limit] + "..."

    if keyword:
        pattern = re.compile(re.escape(keyword), re.IGNORECASE)
        highlighted_text = pattern.sub(r"<span class='highlight'>\g<0></span>", text)
        return Markup(highlighted_text)
    return text

if __name__ == "__main__":
    import click

    @click.command()
    @click.option('--debug', is_flag=True)
    @click.option('--threaded', is_flag=True)
    @click.argument('HOST', default='0.0.0.0')
    @click.argument('PORT', default=8119, type=int)
    def run(debug, threaded, host, port):
        HOST, PORT = host, port
        print("running on %s:%d" % (HOST, PORT))
        app.run(host=HOST, port=PORT, debug=debug, threaded=threaded)
    run()
