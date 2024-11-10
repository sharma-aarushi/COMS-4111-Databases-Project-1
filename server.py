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

    return render_template("index.html", popular_items=popular_items)

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

@app.route('/add', methods=['POST'])
def add(): 
    name = request.form['name']
    params_dict = {"name":name}
    g.conn.execute(text('INSERT INTO test(name) VALUES (:name)'), params_dict)
    g.conn.commit()
    return redirect('/')

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
