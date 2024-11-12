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

@app.route('/test')
def test_page():
    try:
        # Define the SQL query with named parameters
        query = text("INSERT INTO Users (uni, name, columbiaemail, verificationstatus) VALUES (:uni, :name, :columbiaemail, :verificationstatus)")
        
        # Execute the query with a dictionary of parameters
        g.conn.execute(query, {
            "uni": "test_uni2",
            "name": "test_name2",
            "columbiaemail": "test2@test.com",
            "verificationstatus": "t"
        })
        
        # Commit the transaction
        g.conn.commit()
        flash("User created successfully.")
    except Exception as e:
        print("Error occurred:", e)
        flash("An error occurred while trying to create the user.")
    
    return render_template("create_listing.html")

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

from sqlalchemy import text

@app.route('/new_listing', methods=['GET', 'POST'])
def new_listing():
    if request.method == 'POST':
        # Get form data
        title = request.form.get('title')
        location = request.form.get('location')
        category = request.form.get('category')
        description = request.form.get('description')
        price = request.form.get('price')
        condition = request.form.get('condition')
        status = request.form.get('status')
        link = request.form.get('link')
        createdby = "demo_uni"  # Assigning demo user ID for testing
        
        # Automatically set today's date
        dateadded = date.today()

        # Check if all fields are provided
        if not all([title, location, category, description, price, condition, status, link]):
            flash("All fields, including the link, are required.")
            return redirect(url_for('new_listing'))
        
        # Convert price to float and handle exceptions
        try:
            price = float(price)
        except ValueError:
            flash("Invalid price value.")
            return redirect(url_for('new_listing'))

        # Insert listing into the database using text() with named parameters
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
                g.conn.commit()  # Explicitly call commit here
                flash("Listing created successfully.")
        except Exception as e:
            print(f"An error occurred during insertion: {e}")
            flash("An error occurred while inserting data. Ensure all fields are correct.")
            return redirect(url_for('new_listing'))

        return redirect(url_for('show_popular_listings'))

    # Render the form to create a new listing
    return render_template("create_listing.html")


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

@app.route('/profile')
def profile():
    user_uni = "demo_uni"  # Replace with session or actual user ID for real scenarios

    # Reconnect if the connection is closed
    if g.conn is None:
        g.conn = engine.connect()

    # Start a transaction to ensure commit handling
    with g.conn.begin() as transaction:
        try:
            # Fetch listings for the user
            query = text("""
                SELECT listingid, title, dateadded 
                FROM Listings 
                WHERE createdby = :user_uni
            """)
            listings = g.conn.execute(query, {'user_uni': user_uni}).fetchall()

            # Fetch the user's name
            user_query = text("SELECT name FROM Users WHERE uni = :user_uni")
            user_name = g.conn.execute(user_query, {'user_uni': user_uni}).scalar()

            # Explicitly commit the transaction if needed (not typically required for SELECT)
            transaction.commit()

        except Exception as e:
            print(f"Error during database transaction: {e}")
            transaction.rollback()  # Rollback in case of error
            flash("An error occurred while fetching the profile.")
            return redirect(url_for('show_popular_listings'))

    return render_template("profile.html", listings=listings, user_name=user_name)

@app.route('/messages')
def messages():
    user_uni = "demo_uni"  # Replace with session or actual user ID for real scenarios
    query = text("""
        SELECT m.content, m.timestamp, u.name AS sender_name, 
               CASE WHEN m.sender = :user_uni THEN 'sent' ELSE 'received' END AS message_type 
        FROM Messages m
        JOIN Users u ON (m.sender = u.uni OR m.receiver = u.uni)
        WHERE (m.sender = :user_uni OR m.receiver = :user_uni)
        ORDER BY m.timestamp DESC
    """)
    with g.conn as conn:
        messages = conn.execute(query, {'user_uni': user_uni}).fetchall()
    
    return render_template("messages.html", messages=messages)

@app.route('/edit_listing/<int:listing_id>', methods=['GET', 'POST'])
def edit_listing(listing_id):
    demo_uni = "demo_uni"  # Replace with actual demo user UNI for testing
    if request.method == 'POST':
        # Get form data for editable fields
        title = request.form.get('title')
        location = request.form.get('location')
        category = request.form.get('category')
        description = request.form.get('description')
        price = request.form.get('price')
        condition = request.form.get('condition')
        status = request.form.get('status')
        link = request.form.get('link')
        
        # Ensure link is not left blank
        if not link:
            flash("The link field cannot be left blank.")
            return redirect(url_for('edit_listing', listing_id=listing_id))
        
        # Convert price to float and handle exceptions
        try:
            price = float(price)
        except ValueError:
            flash("Invalid price value.")
            return redirect(url_for('edit_listing', listing_id=listing_id))

        # Update query only for the editable fields
        query = text("""
            UPDATE Listings
            SET title = :title, location = :location, category = :category, description = :description,
                price = :price, condition = :condition, status = :status, link = :link
            WHERE listingid = :listing_id AND createdby = :demo_uni
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
                    'demo_uni': demo_uni
                })
                g.conn.commit()  # Explicitly call commit for the update
                flash("Listing updated successfully.")
        except Exception as e:
            print(f"Error during update: {e}")
            flash("An error occurred while updating the listing.")
            return redirect(url_for('edit_listing', listing_id=listing_id))

        return redirect(url_for('profile'))
    else:
        # Fetch current data for the listing for pre-filling the edit form, including `listingid` for the form action URL
        query = text("""
            SELECT listingid, title, location, category, description, price, condition, status, link
            FROM Listings
            WHERE listingid = :listing_id AND createdby = :demo_uni
        """)
        
        with g.conn as conn:
            result = conn.execute(query, {'listing_id': listing_id, 'demo_uni': demo_uni}).fetchone()
        
        if result:
            listing = result._mapping  # Convert to dictionary-like object for template rendering
            return render_template("edit_listing.html", listing=listing)
        else:
            flash("Listing not found or unauthorized.")
            return redirect(url_for('profile'))

@app.route('/delete_listing/<int:listing_id>', methods=['POST'])
def delete_listing(listing_id):
    demo_uni = "demo_uni"  # Demo user UNI for testing
    query = text("""
        DELETE FROM Listings 
        WHERE listingid = :listing_id AND createdby = :demo_uni
    """)

    try:
        with g.conn as conn:
            # Debugging print to confirm route is accessed
            print(f"Attempting to delete listing with ID {listing_id} for user {demo_uni}")
            
            # Execute delete query
            result = conn.execute(query, {'listing_id': listing_id, 'demo_uni': demo_uni})
            
            # Commit the transaction
            g.conn.commit()  # Explicitly commit the deletion
            print(f"Deleted listing with ID {listing_id} for user {demo_uni}")  # Confirm deletion
            
            flash("Listing deleted successfully.")
    except Exception as e:
        # Print error message for debugging
        print(f"An error occurred during deletion: {e}")
        flash("An error occurred while trying to delete the listing.")
    
    return redirect(url_for('profile'))
 

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
    @click.argument('PORT', default=8114, type=int)
    def run(debug, threaded, host, port):
        HOST, PORT = host, port
        print("running on %s:%d" % (HOST, PORT))
        app.run(host=HOST, port=PORT, debug=debug, threaded=threaded)
    run()
