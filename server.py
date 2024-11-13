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

# Define global users and current user
USERS = {
    "user1": "demo_uni",  # Replace with actual UNI for user1
    "user2": "test_uni"   # Replace with actual UNI for user2
}
current_user = USERS["user1"]  # Default to user1

@app.route('/switch_user/<string:user>')
def switch_user(user):
    global current_user
    if user in USERS:
        current_user = USERS[user]
        flash(f"Switched to {user}.")
    else:
        flash("User not found.")
    return redirect(url_for('profile'))


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

@app.route('//<int:listing_id>')
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


##Messages

@app.route('/message_seller/<int:listing_id>', methods=['POST'])
def message_seller(listing_id):
    message = request.form.get('message')
    
    # Query to get the seller's UNI (createdby) from the Listings table based on listing_id
    query = text("SELECT createdby FROM Listings WHERE listingid = :listing_id")
    
    with g.conn as conn:
        result = conn.execute(query, {'listing_id': listing_id}).fetchone()
        
        if result is None:
            flash("Seller not found.")
            return redirect(url_for('view_item', listing_id=listing_id))
        
        recipient_uni = result._mapping['createdby']  # Seller's UNI from the Listings table

        # Insert the message into Messages table
        insert_query = text("""
            INSERT INTO Messages (content, timestamp, sender, receiver)
            VALUES (:content, :timestamp, :sender, :receiver)
        """)
        
        conn.execute(insert_query, {
            'content': message,
            'timestamp': datetime.now(),
            'sender': current_user,
            'receiver': recipient_uni
        })
        conn.commit()  # Commit the transaction

    flash("Message sent to the seller.")
    return redirect(url_for('view_item', listing_id=listing_id))

@app.route('/messages_overview')
def message_overview():
    # Get unique conversations for the current user based on sender and receiver
    query = text("""
        SELECT DISTINCT CASE 
            WHEN sender = :current_user THEN receiver 
            ELSE sender 
        END AS other_user
        FROM Messages
        WHERE sender = :current_user OR receiver = :current_user
    """)
    
    with g.conn as conn:
        conversations = conn.execute(query, {'current_user': current_user}).fetchall()

    return render_template("message_overview.html", conversations=conversations)

@app.route('/messages/<string:recipient_uni>')
def view_conversation(recipient_uni):
    # Query to fetch the conversation between the current user and recipient_uni
    query = text("""
        SELECT content, timestamp, sender, receiver
        FROM Messages
        WHERE (sender = :current_user AND receiver = :recipient_uni) 
           OR (sender = :recipient_uni AND receiver = :current_user)
        ORDER BY timestamp
    """)

    with g.conn as conn:
        messages = conn.execute(query, {
            'current_user': current_user,
            'recipient_uni': recipient_uni
        }).fetchall()

    # Pass the messages and recipient information to the template
    return render_template("view_conversation.html", messages=messages, recipient_uni=recipient_uni)
##EO Messages

@app.route('/add_to_wishlist/<int:listing_id>', methods=['POST'])
def add_to_wishlist(listing_id):
    # Logic to add item to wishlist
    flash("Item added to wishlist.")
    return redirect(url_for('view_item', listing_id=listing_id))

@app.route('/buy_item/<int:listing_id>', methods=['POST'])
def buy_item(listing_id):
    # Check the status before proceeding
    query = text("SELECT status FROM Listings WHERE listingid = :listing_id")
    with g.conn as conn:
        status = conn.execute(query, {'listing_id': listing_id}).scalar()

    if status == 'sold':
        flash("Sorry, this item is already sold.")
        return redirect(url_for('view_item', listing_id=listing_id))

    # Update the status to 'sold'
    update_query = text("""
        UPDATE Listings
        SET status = 'sold'
        WHERE listingid = :listing_id AND status = 'available'
    """)

    with g.conn as conn:
        result = conn.execute(update_query, {'listing_id': listing_id})
        if result.rowcount > 0:
            g.conn.commit()
            return redirect(url_for('purchase_success', listing_id=listing_id))
        else:
            flash("An error occurred while processing your purchase.")
            return redirect(url_for('view_item', listing_id=listing_id))

@app.route('/purchase_success/<int:listing_id>',methods=['POST'])
def purchase_success(listing_id):
    # Flash a success message
    flash("Purchase completed successfully!")
    
    # Query to get item details using listing_id
    query = text("""
        SELECT title, price, description, link
        FROM Listings
        WHERE listingid = :listing_id
    """)
    
    with g.conn as conn:
        result = conn.execute(query, {'listing_id': listing_id}).fetchone()
    
    if result is None:
        flash("Listing not found.")
        return redirect(url_for('show_popular_listings'))
    
    listing = result._mapping  # Convert to dictionary-like object
    
    # Render the purchase_success.html template, passing listing details
    return render_template("purchase_success.html", item=listing)



from sqlalchemy import text

@app.route('/new_listing', methods=['GET', 'POST'])
def new_listing():
    if request.method == 'POST':
        title = request.form.get('title')
        location = request.form.get('location')
        category = request.form.get('category')
        description = request.form.get('description')
        price = request.form.get('price')
        condition = request.form.get('condition')
        status = request.form.get('status')
        link = request.form.get('link')
        createdby = current_user  # Assign current user ID

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
    user_uni = current_user  # Use the current user

    if g.conn is None:
        g.conn = engine.connect()

    with g.conn.begin() as transaction:
        try:
            # Fetch listings for the current user
            query = text("""
                SELECT listingid, title, dateadded 
                FROM Listings 
                WHERE createdby = :user_uni
            """)
            listings = g.conn.execute(query, {'user_uni': user_uni}).fetchall()

            # Fetch the user's name
            user_query = text("SELECT name FROM Users WHERE uni = :user_uni")
            user_name = g.conn.execute(user_query, {'user_uni': user_uni}).scalar()

            transaction.commit()
        except Exception as e:
            print(f"Error during database transaction: {e}")
            transaction.rollback()
            flash("An error occurred while fetching the profile.")
            return redirect(url_for('show_popular_listings'))

    return render_template("profile.html", listings=listings, user_name=user_name)

@app.route('/messages', defaults={'listing_id': None})
@app.route('/messages/<int:listing_id>')
def messages(listing_id=None):
    # If listing_id is provided, fetch the `recipient_uni` (seller) based on `createdby` attribute
    recipient_uni = None
    if listing_id:
        query = text("SELECT createdby FROM Listings WHERE listingid = :listing_id")
        with g.conn as conn:
            result = conn.execute(query, {'listing_id': listing_id}).fetchone()
            if result:
                recipient_uni = result._mapping['createdby']

    if not recipient_uni:
        flash("Recipient not found.")
        return redirect(url_for('message_overview'))

    # Now that we have recipient_uni, fetch all messages between current_user and recipient_uni
    query = text("""
        SELECT content, timestamp, sender, receiver
        FROM Messages
        WHERE (sender = :current_user AND receiver = :recipient_uni) 
           OR (sender = :recipient_uni AND receiver = :current_user)
        ORDER BY timestamp ASC
    """)

    with g.conn as conn:
        messages = conn.execute(query, {
            'current_user': current_user,
            'recipient_uni': recipient_uni
        }).fetchall()

    return render_template("messages.html", messages=messages, recipient_uni=recipient_uni)

@app.route('/edit_listing/<int:listing_id>', methods=['GET', 'POST'])
def edit_listing(listing_id):
    demo_uni = current_user  # Replace with actual demo user UNI for testing
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
                    'demo_uni': current_user
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
            result = conn.execute(query, {'listing_id': listing_id, 'demo_uni': current_user}).fetchone()
        
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
            print(f"Attempting to delete listing with ID {listing_id} for user {current_user}")
            
            # Execute delete query
            result = conn.execute(query, {'listing_id': listing_id, 'demo_uni': current_user})
            
            # Commit the transaction
            g.conn.commit()  # Explicitly commit the deletion
            print(f"Deleted listing with ID {listing_id} for user {current_user}")  # Confirm deletion
            
            flash("Listing deleted successfully.")
    except Exception as e:
        # Print error message for debugging
        print(f"An error occurred during deletion: {e}")
        flash("An error occurred while trying to delete the listing.")
    
    return redirect(url_for('profile'))
 
@app.route('/send_message', methods=['POST'])
def send_message():
    sender_uni = current_user  # Use the global current_user variable
    receiver_uni = request.form.get('receiver_uni')
    message_text = request.form.get('message')

    if not receiver_uni or not message_text:
        flash("Message and receiver are required.")
        return redirect(request.referrer)

    # SQL query to insert a new message
    query = text("""
        INSERT INTO Messages (content, timestamp, sender, receiver)
        VALUES (:message_text, :timestamp, :sender_uni, :receiver_uni)
    """)

    try:
        with g.conn as conn:
            conn.execute(query, {
                'message_text': message_text,
                'timestamp': datetime.now(),
                'sender_uni': sender_uni,
                'receiver_uni': receiver_uni
            })
            flash("Message sent successfully.")
    except Exception as e:
        print(f"An error occurred while sending the message: {e}")
        flash("An error occurred while trying to send the message.")
    
    return redirect(url_for('messages'))

if __name__ == "__main__":
    import click

    @click.command()
    @click.option('--debug', is_flag=True)
    @click.option('--threaded', is_flag=True)
    @click.argument('HOST', default='0.0.0.0')
    @click.argument('PORT', default=8116, type=int)
    def run(debug, threaded, host, port):
        HOST, PORT = host, port
        print("running on %s:%d" % (HOST, PORT))
        app.run(host=HOST, port=PORT, debug=debug, threaded=threaded)
    run()

