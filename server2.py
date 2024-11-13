"""
Columbia's COMS W4111.001 Introduction to Databases
Example Webserver
To run locally:
    python3 server.py
Go to http://localhost:8111 in your browser.
A debugger such as "pdb" may be helpful for debugging.
Read about it online.
"""
import os
from sqlalchemy import *
from sqlalchemy.pool import NullPool
from flask import Flask, request, render_template, g, redirect, Response, abort, jsonify
from datetime import datetime
from sqlalchemy import inspect, text

tmpl_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'templates')
app = Flask(__name__, template_folder=tmpl_dir)

DATABASEURI = "postgresql://as6322:624309@104.196.222.236/proj1part2"

engine = create_engine(DATABASEURI)

@app.route('/')
def show_popular_listings():
    query = text("""
        SELECT L.listingid, L.title AS listing_title, COUNT(IW.listing_id) AS times_added_to_wishlist
        FROM Listings L
        JOIN In_Wishlist IW ON L.listingid = IW.listing_id
        GROUP BY L.listingid, L.title
        ORDER BY times_added_to_wishlist DESC
        LIMIT 5;
    """)

    with engine.connect() as conn:
        result = conn.execute(query)
        popular_items = [dict(row._mapping) for row in result]

    return render_template("home.html", popular_items=popular_items)

# conn.execute(text("""CREATE TABLE IF NOT EXISTS test (
#   id serial,
#   name text
# );"""))
# conn.execute(text("""INSERT INTO test(name) VALUES ('grace hopper'), ('alan turing'), ('ada lovelace');"""))
# conn.commit()

@app.before_request
def before_request():
    try:
        g.conn = engine.connect()
    except:
        print("uh oh, problem connecting to database")
        import traceback; traceback.print_exc()
        g.conn = None

@app.teardown_request
def teardown_request(exception):
    try:
        g.conn.close()
    except Exception as e:
        pass

# @app.route('/example_index')
# def example_index():
#     print(request.args)
#     cursor = g.conn.execute(text("SELECT name FROM test"))
#     g.conn.commit()
#     names = [result[0] for result in cursor]
#     cursor.close()
#     context = dict(data=names)
#     return render_template("index.html", **context)

@app.route('/another')
def another():
    return render_template("another.html")

# @app.route('/add', methods=['POST'])
# def add(): 
#     name = request.form['name']
#     params_dict = {"name":name}
#     g.conn.execute(text('INSERT INTO test(name) VALUES (:name)'), params_dict)
#     g.conn.commit()
#     return redirect('/')

@app.route('/new_listing')
def new_listing():
    return render_template('create_listing.html')

@app.route('/create_listing', methods=['POST'])
def create_listing():
    # Capture form data
    title = request.form.get('title')
    location = request.form.get('location')
    category = request.form.get('category')
    creatorid = request.form.get('creatorid')
    description = request.form.get('description')
    price = request.form.get('price')
    condition = request.form.get('condition')
    status = request.form.get('status')
    
    # Basic validation for required fields
    if not all([title, location, category, creatorid, description, price, condition, status]):
        return "All fields are required.", 400
    
    try:
        # Convert price to a float
        price = float(price)
    except ValueError:
        return "Invalid price value.", 400

    # SQLAlchemy insert query with error handling
    query = text("""
        INSERT INTO Listings (title, location, category, creatorid, description, price, condition, status)
        VALUES (:title, :location, :category, :creatorid, :description, :price, :condition, :status)
    """)
    
    # Attempt to execute the query with error checking
    try:
        with engine.connect() as conn:
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
            conn.commit()
    except IntegrityError as e:
        # Catch constraint violations, e.g., unique key violation
        return "Error: A listing with this primary key or other constraint already exists.", 400
    except Exception as e:
        # Catch any other database-related errors
        return f"An error occurred: {str(e)}", 500

    return redirect('/')

# Finding the seller of a listing
@app.route('/seller/<int:listing_id>')
def find_seller(listing_id):
    query = text("""
        SELECT U.name AS seller_name, L.title AS listing_title, T.transactionDate, T.amount
        FROM Transactions T
        JOIN Listings L ON T.listingID = L.listingID
        JOIN Users U ON L.createdBy = U.uni
        WHERE T.listingID = :listing_id;
    """)

    # Execute the query
    with engine.connect() as conn:
        result = conn.execute(query, {'listing_id': listing_id}).fetchone()

    # Check if the listing was found
    if result is None:
        return "Listing not found or no associated seller", 404

    # Convert the result to a dictionary for easy access in the template
    listing_info = dict(result)

    # Render the template to display seller and listing information
    return render_template("seller_info.html", listing=listing_info)

#############
@app.route('/login')
def login():
    abort(401)

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
