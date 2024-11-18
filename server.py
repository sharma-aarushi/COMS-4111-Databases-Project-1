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
from datetime import date

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
    global current_user
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
            next_page = request.args.get('next')
            flash_message = request.args.get('flash')
            
            if next_page:
                if flash_message:
                    flash(flash_message)
                return redirect(next_page)
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
    
# Check if user is logged in
def is_logged_in():
    global current_user
    return current_user is not None

def get_current_user():
    global current_user
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
        WHERE L.status != 'sold'
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
               L.status, L.link, L.dateadded, U.name AS owner_name, L.createdby AS seller_uni
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
    return render_template("view-item.html", item=listing, listing_id=listing['listingid'], seller_uni=listing['seller_uni'])

# Wishlist route
@app.route('/wishlist')
def wishlist():
    user_uni = get_current_user()
    if not user_uni:
        flash("Please log in to view your wishlist.")
        return redirect(url_for('login'))

    # Query to get wishlist items for the user where the item is available (not sold)
    query = text("""
        SELECT L.listingid, L.title, L.description, L.price, L.condition, L.status, L.link, L.dateadded
        FROM Listings L
        JOIN In_Wishlist IW ON L.listingid = IW.listing_id
        WHERE IW.uni = :user_uni AND L.status != 'sold'
    """)

    with g.conn as conn:
        wishlist_items = conn.execute(query, {'user_uni': user_uni}).fetchall()

    return render_template("wishlist.html", wishlist_items=wishlist_items)

# Add to wishlist
@app.route('/add_to_wishlist/<int:listing_id>', methods=['POST'])
def add_to_wishlist(listing_id):
    user_uni = get_current_user()
    if not user_uni:
        flash("Please log in to add items to your wishlist.")
        return redirect(url_for('login', next=url_for('view_item', listing_id=listing_id), flash="Item added to wishlist successfully"))

    # Check if item is already in wishlist
    check_query = text("SELECT 1 FROM In_Wishlist WHERE uni = :user_uni AND listing_id = :listing_id")
    insert_query = text("INSERT INTO In_Wishlist (uni, listing_id, dateadded) VALUES (:user_uni, :listing_id, :dateadded)")

    with g.conn as conn:
        existing_entry = conn.execute(check_query, {'user_uni': user_uni, 'listing_id': listing_id}).fetchone()
        
        if existing_entry:
            flash("Item is already in your wishlist.")
        else:
            conn.execute(insert_query, {
                'user_uni': user_uni,
                'listing_id': listing_id,
                'dateadded': date.today()
            })
            g.conn.commit()
            flash("Item added to wishlist successfully.")
    
    return redirect(url_for('view_item', listing_id=listing_id))

@app.route('/remove_from_wishlist/<int:listing_id>', methods=['POST'])
def remove_from_wishlist(listing_id):
    user_uni = get_current_user()
    if not user_uni:
        flash("Please log in to manage your wishlist.")
        return redirect(url_for('login'))

    delete_query = text("DELETE FROM In_Wishlist WHERE uni = :user_uni AND listing_id = :listing_id")
    with g.conn as conn:
        conn.execute(delete_query, {'user_uni': user_uni, 'listing_id': listing_id})
        g.conn.commit()

    flash("Item removed from wishlist.")
    return redirect(url_for('wishlist'))
    
# Buy item
@app.route('/buy_item/<int:listing_id>', methods=['POST'])
def buy_item(listing_id):
    user_uni = get_current_user()
    if not user_uni:
        flash("Please log in to purchase an item.")
        return redirect(url_for('login'))

    try:
        with g.conn as conn:
            item_query = text("SELECT title, status, price, createdby FROM Listings WHERE listingid = :listing_id")
            item = conn.execute(item_query, {'listing_id': listing_id}).fetchone()

            if item is None:
                flash("Listing not found.")
                return redirect(url_for('show_popular_listings'))

            if item.status == 'sold':
                flash("Sorry, this item is already sold.")
                return redirect(url_for('view_item', listing_id=listing_id))

            # Update the listing status to 'sold'
            update_query = text("""
                UPDATE Listings
                SET status = 'sold'
                WHERE listingid = :listing_id AND status = 'available'
            """)
            result = conn.execute(update_query, {'listing_id': listing_id})

            if result.rowcount > 0:
                # If the item was marked as sold, insert the transaction into Transactions table
                transaction_query = text("""
                    INSERT INTO Transactions (transactiondate, buyer, listingid, amount, seller)
                    VALUES (:transactiondate, :buyer, :listingid, :amount, :seller)
                """)
                conn.execute(transaction_query, {
                    'transactiondate': date.today(),
                    'buyer': user_uni,
                    'listingid': listing_id,
                    'amount': item.price,
                    'seller': item.createdby
                })
                conn.commit()

                flash("Purchase completed successfully!")
                return render_template("purchase_success.html", item=item)

            else:
                flash("An error occurred while processing your purchase.")
                return redirect(url_for('view_item', listing_id=listing_id))

    except Exception as e:
        print(f"An error occurred: {e}")
        flash("An error occurred while processing your request.")
        return redirect(url_for('view_item', listing_id=listing_id))

# Delete user
@app.route('/delete_account', methods=['POST'])
def delete_account():
    user_uni = get_current_user()
    if not user_uni:
        flash("You need to be logged in to delete your account.")
        return redirect(url_for('login'))

    delete_wishlist_query = text("DELETE FROM In_Wishlist WHERE uni = :user_uni")
    delete_listings_query = text("DELETE FROM Listings WHERE createdby = :user_uni")
    update_messages_query = text("UPDATE Messages SET sender = 'deleted user', receiver = 'deleted user' WHERE sender = :user_uni OR receiver = :user_uni")
    delete_user_query = text("DELETE FROM Users WHERE uni = :user_uni")

    with g.conn as conn:
        conn.execute(delete_wishlist_query, {'user_uni': user_uni})
        conn.execute(delete_listings_query, {'user_uni': user_uni})
        conn.execute(update_messages_query, {'user_uni': user_uni})
        conn.execute(delete_user_query, {'user_uni': user_uni})
        g.conn.commit()

    global current_user
    current_user = None
    flash("Your account and associated data have been deleted.")
    return redirect(url_for('show_popular_listings'))

#user's listing

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

        # Ensure all fields are filled
        if not all([title, location, category, description, price, condition, status, link]):
            flash("All fields, including the link, are required.")
            return redirect(url_for('new_listing'))
        
        # Convert price to float and handle errors
        try:
            price = float(price)
            if price < 0:
                flash("Please enter a positive number for the price.")
                print(price)
                # return redirect(url_for('new_listing'))
        except ValueError:
            flash("Invalid price value.")
            # return redirect(url_for('new_listing'))

        # Insert the new listing into the database
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

        # Update the listing in the database
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
    
    # Query to fetch the current details of the listing
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

@app.route('/delete_listing/<int:listing_id>', methods=['POST'])
def delete_listing(listing_id):
    user_uni = get_current_user()
    if not user_uni:
        flash("Please log in to delete the listing.")
        return redirect(url_for('login'))

    # Delete the listing from the database
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
    
# Message seller
@app.route('/message_seller/<int:listing_id>')
def message_seller(listing_id):
    if not is_logged_in():
        flash("Please log in to send a message.")
        return redirect(url_for('login'))

    sender = get_current_user()  # Get the logged-in user's UNI
    recipient = request.form.get('recipient_uni')  # Seller's UNI from form data
    message_content = request.form.get('message')

    if not message_content:
        flash("Message cannot be empty.")
        return redirect(url_for('view_item', listing_id=listing_id))

    # Insert the message into the Messages table
    insert_query = text("""
        INSERT INTO Messages (content, timestamp, sender, receiver)
        VALUES (:content, :timestamp, :sender, :receiver)
    """)

    try:
        with g.conn as conn:
            conn.execute(insert_query, {
                'content': message_content,
                'timestamp': datetime.now(),
                'sender': sender,
                'receiver': recipient
            })
            conn.commit()
            flash("Message sent to the seller.")
    except Exception as e:
        print(f"An error occurred: {e}")
        flash("Failed to send the message.")

    return redirect(url_for('view_item', listing_id=listing_id))

@app.route('/message_overview')
def message_overview():
    user_uni = get_current_user()
    if not user_uni:
        flash("Please log in to view your messages.")
        return redirect(url_for('login'))

    # Get unique conversations for the current user based on sender, receiver, and listing_id
    query = text("""
        SELECT DISTINCT listing_id, 
               CASE 
                   WHEN sender = :user_uni THEN receiver 
                   ELSE sender 
               END AS other_user
        FROM Messages
        WHERE sender = :user_uni OR receiver = :user_uni
        ORDER BY listing_id, other_user;
    """)

    with g.conn as conn:
        conversations = conn.execute(query, {'user_uni': user_uni}).fetchall()

    conversations = [dict(row._mapping) for row in conversations]

    return render_template("message_overview.html", conversations=conversations)

@app.route('/view_conversation/<string:recipient_uni>/<int:listing_id>')
def view_conversation(recipient_uni, listing_id):
    # Get the current user
    user_uni = get_current_user()
    if not user_uni:
        flash("Please log in to view conversations.")
        return redirect(url_for('login'))

    # Fetch messages between the current user and the recipient for the specific listing
    query = text("""
        SELECT content, timestamp, sender, receiver
        FROM Messages
        WHERE listing_id = :listing_id AND 
              ((sender = :current_user AND receiver = :recipient_uni) 
           OR (sender = :recipient_uni AND receiver = :current_user))
        ORDER BY timestamp ASC
    """)
    
    with g.conn as conn:
        result = conn.execute(query, {
            'current_user': user_uni,
            'recipient_uni': recipient_uni,
            'listing_id': listing_id
        })

        messages = [row._mapping for row in result]

    return render_template("messages.html", messages=messages, recipient_uni=recipient_uni, listing_id=listing_id, user_uni=user_uni)

@app.route('/send_message/<int:listing_id>', methods=['POST'])
def send_message(listing_id):
    if not is_logged_in():
        flash("Please log in to send a message.")
        return redirect(url_for('login'))

    sender = get_current_user()  # Get the logged-in user's UNI
    recipient = request.form.get('receiver_uni')  # UNI of the other party (either buyer or seller)
    message_content = request.form.get('message')

    if not message_content:
        flash("Message cannot be empty.")
        return redirect(url_for('view_item', listing_id=listing_id))

    # Insert the message with listing_id into the Messages table
    insert_query = text("""
        INSERT INTO Messages (content, timestamp, sender, receiver, listing_id)
        VALUES (:content, :timestamp, :sender, :receiver, :listing_id)
    """)

    try:
        with g.conn as conn:
            conn.execute(insert_query, {
                'content': message_content,
                'timestamp': datetime.now(),
                'sender': sender,
                'receiver': recipient,
                'listing_id': listing_id
            })
            conn.commit()
            flash("Message sent successfully.")
    except Exception as e:
        print(f"An error occurred: {e}")
        flash("Failed to send the message.")

    return redirect(url_for('view_conversation', recipient_uni=recipient, listing_id=listing_id))

@app.route('/messages', methods=['GET','POST'])
@app.route('/messages/<int:listing_id>', methods=['GET','POST'])
def messages(listing_id=None):
    print("MESSAGES")
    # Check if the user is logged in
    if not current_user:
        flash("Please log in to view messages.")
        return redirect(url_for('login'))

    # If listing_id is provided, fetch the recipient_uni (seller) based on createdby attribute of Listings table
    recipient_uni = None
    print(listing_id)
    if listing_id:
        print("listing id")
        query = text("SELECT createdby FROM Listings WHERE listingid = :listing_id")
        with g.conn as conn:
            result = conn.execute(query, {'listing_id': listing_id}).fetchone()
            if result:
                recipient_uni = result._mapping['createdby']

    # If recipient_uni is not found, redirect to message overview
    if not recipient_uni:
        flash("Recipient not found.")
        return redirect(url_for('message_overview'))

    # Now that we have recipient_uni, fetch all messages between current_user and recipient_uni
    # query = text("""
    #     SELECT content, timestamp, sender, receiver
    #     FROM Messages
    #     WHERE (sender = :current_user AND receiver = :recipient_uni) 
    #        OR (sender = :recipient_uni AND receiver = :current_user)
    #     ORDER BY timestamp ASC
    # """)

    query = text("""
        INSERT INTO Messages (content, timestamp, sender, receiver)
        VALUES (:content, :timestamp, :sender, :receiver)
    """)

    # print(query)

    with g.conn as conn:
        messages = conn.execute(query, {
            'current_user': current_user,
            'recipient_uni': recipient_uni
        }).fetchall()

    return render_template("messages.html", messages=messages, recipient_uni=recipient_uni)

# Search function
@app.route('/search', methods=['GET'])
def search():
    keyword = request.args.get('query', '').strip()

    if not keyword:
        flash("Please enter a keyword to search.")
        return redirect(url_for('show_popular_listings'))

    # SQL query to search for the keyword in title, description, and user name, excluding sold listings
    query = text("""
        SELECT L.listingid, L.title, L.description, L.link, U.name AS createdby
        FROM Listings L
        JOIN Users U ON L.createdby = U.uni
        WHERE (L.title ILIKE :kw OR L.description ILIKE :kw OR U.name ILIKE :kw)
          AND L.status != 'sold'
    """)
    search_keyword = f"%{keyword}%"
    
    with g.conn as conn:
        results = conn.execute(query, {'kw': search_keyword}).fetchall()

    return render_template("search_results.html", keyword=keyword, results=results)

# Advanced search function
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
        createdby = request.args.get('createdby', '').strip()

        # Query excluding sold listings
        query = """
            SELECT L.listingid, L.title, L.description, L.price, L.condition, L.status, L.location, L.link, L.dateadded, U.name AS createdby
            FROM Listings L
            JOIN Users U ON L.createdby = U.uni
            WHERE L.status != 'sold'
        """
        filters = {}

        if keyword:
            query += " AND (L.title ILIKE :keyword OR L.description ILIKE :keyword)"
            filters['keyword'] = f"%{keyword}%"
        if location:
            query += " AND L.location ILIKE :location"
            filters['location'] = f"%{location}%"
        if min_price:
            query += " AND L.price >= :min_price"
            filters['min_price'] = min_price
        if max_price:
            query += " AND L.price <= :max_price"
            filters['max_price'] = max_price
        if condition:
            query += " AND L.condition = :condition"
            filters['condition'] = condition
        if status:
            query += " AND L.status = :status"
            filters['status'] = status
        if date_added:
            query += " AND L.dateadded >= :date_added"
            filters['date_added'] = date_added
        if createdby:
            query += " AND U.name ILIKE :createdby"
            filters['createdby'] = f"%{createdby}%"

        with g.conn as conn:
            results = conn.execute(text(query), filters).fetchall()

        return render_template("search_results.html", keyword=keyword, results=results)

    return render_template("advanced_search.html")

# Highlight filter function
@app.template_filter('highlight')
def highlight(text, keyword):
    """Highlight occurrences of keyword in the text with a span tag."""
    escaped_keyword = re.escape(keyword)  # Escape special characters in keyword
    highlighted_text = re.sub(f"({escaped_keyword})", r'<span class="highlight">\1</span>', text, flags=re.IGNORECASE)
    return Markup(highlighted_text)

if __name__ == "__main__":
    import click

    @click.command()
    @click.option('--debug', is_flag=True)
    @click.option('--threaded', is_flag=True)
    @click.argument('HOST', default='0.0.0.0')
    @click.argument('PORT', default=8141, type=int)
    def run(debug, threaded, host, port):
        HOST, PORT = host, port
        print("running on %s:%d" % (HOST, PORT))
        app.run(host=HOST, port=PORT)
        #app.run(host=HOST, port=PORT, debug=debug, threaded=threaded)
    run()