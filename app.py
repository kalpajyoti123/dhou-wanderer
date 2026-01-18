import os
import re
import datetime
import time
import certifi
from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_mail import Mail, Message
from werkzeug.security import generate_password_hash, check_password_hash
from pymongo import MongoClient
from bson.objectid import ObjectId
from itsdangerous import URLSafeTimedSerializer
from werkzeug.utils import secure_filename
from dotenv import load_dotenv
from werkzeug.middleware.proxy_fix import ProxyFix
import razorpay
import cloudinary
import cloudinary.uploader
import cloudinary.api
import io
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors

load_dotenv(os.path.join(os.path.dirname(__file__), '.env'), override=True)

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY')

# Fix for HTTPS redirects on platforms like Heroku/Render
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)

# --- 1. FOLDER PERMISSIONS & CONFIGURATION ---
# This path matches the subfolders you requested
UPLOAD_FOLDER = os.path.join(app.root_path, 'static', 'wp-content', 'uploads', '2021', '01')
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'mp4'}

# Apply Folder Permissions: Automatically creates the directory path if it doesn't exist
try:
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
except OSError:
    print("⚠️ Warning: Could not create upload folder. (Likely read-only filesystem on Vercel)")

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# --- 2. MONGODB ATLAS CONNECTION ---
ca = certifi.where()
MONGO_URI = os.environ.get('MONGO_URI') # Ensure this is set in your environment variables

# Initialize collections to None to prevent NameError if connection fails
bookings_collection = None
trips_collection = None
users_collection = None
reviews_collection = None

try:
    if not MONGO_URI or "replace_with" in MONGO_URI or "your_mongo_string" in MONGO_URI:
        raise ValueError("Invalid MONGO_URI detected. Please check your .env file.")

    client = MongoClient(MONGO_URI, tlsCAFile=ca)
    client.admin.command('ping') # Force connection check
    db = client['dhou-wanderer']
    bookings_collection = db['bookings']
    trips_collection = db['trips'] 
    users_collection = db['users']
    reviews_collection = db['reviews']
    print("✅ Successfully connected to MongoDB Atlas!")
except Exception as e:
    if "DNS query name does not exist" in str(e):
        print("\n❌ CONFIG ERROR: The MongoDB address in your .env file is incorrect.")
        print("   Please copy the full connection string from MongoDB Atlas (Connect -> Drivers).\n")
    print(f"❌ MongoDB Connection Error: {e}")

# --- 3. EMAIL CONFIGURATION ---
mail_username = os.environ.get('MAIL_USERNAME')
mail_password = os.environ.get('MAIL_PASS')

if not mail_username or not mail_password:
    print("\n❌ CONFIG ERROR: Email credentials (MAIL_USERNAME or MAIL_PASS) are missing.\n   Emails will NOT be sent. Check your .env file.\n")

app.config.update(
    MAIL_SERVER='smtp.gmail.com',
    MAIL_PORT=587,
    MAIL_USE_TLS=True,
    MAIL_USERNAME=mail_username,
    MAIL_PASSWORD=mail_password,
    MAIL_DEFAULT_SENDER=('Wanderer Travels', mail_username) if mail_username else None
)
mail = Mail(app)

# --- RAZORPAY CONFIGURATION ---
razorpay_client = razorpay.Client(auth=(os.environ.get('RAZORPAY_KEY_ID'), os.environ.get('RAZORPAY_KEY_SECRET')))

# --- CLOUDINARY CONFIGURATION ---
cloudinary.config(
    cloud_name=os.environ.get('CLOUDINARY_CLOUD_NAME'),
    api_key=os.environ.get('CLOUDINARY_API_KEY'),
    api_secret=os.environ.get('CLOUDINARY_API_SECRET')
)

if not os.environ.get('CLOUDINARY_API_KEY') or not os.environ.get('CLOUDINARY_API_SECRET'):
    print("\n❌ CONFIG ERROR: Cloudinary credentials (API KEY or SECRET) are missing.\n   Image uploads will fail. Please check your .env file.\n")

# --- 4. WEBSITE ROUTES ---

@app.route('/')
def home():
    if trips_collection is None: return "Database Connection Error", 500
    
    # Search Logic
    search_query = request.args.get('q')
    query = {"name": {"$regex": search_query, "$options": "i"}} if search_query else {}
    
    all_trips = list(trips_collection.find(query))
    return render_template('index.html', trips=all_trips, search_query=search_query)

@app.route('/itinerary/<trip_name>')
def trip_details(trip_name):
    if trips_collection is None: return "Database Connection Error", 500
    
    # Use regex for case-insensitive matching (handles 'Bihar', 'bihar', 'Bihar Trip' vs 'bihar-trip')
    search_name = re.escape(trip_name.replace('-', ' '))
    trip_data = trips_collection.find_one({"name": {"$regex": f"^{search_name}$", "$options": "i"}})
    
    if not trip_data:
        return "Trip not found", 404
        
    # Fetch reviews
    reviews = []
    avg_rating = 0
    review_count = 0
    page = request.args.get('page', 1, type=int)
    sort_option = request.args.get('sort', 'newest')
    per_page = 5
    total_pages = 1

    if reviews_collection is not None:
        query = {"trip_name": trip_data['name']}
        review_count = reviews_collection.count_documents(query)
        
        if review_count > 0:
            # Calculate average rating using aggregation
            pipeline = [{"$match": query}, {"$group": {"_id": None, "avg_rating": {"$avg": "$rating"}}}]
            agg_result = list(reviews_collection.aggregate(pipeline))
            if agg_result: avg_rating = agg_result[0]['avg_rating']
            
            total_pages = (review_count + per_page - 1) // per_page
            
            # Sort Logic
            sort_criteria = [("date", -1)] # Default: Newest
            if sort_option == 'oldest':
                sort_criteria = [("date", 1)]
            elif sort_option == 'highest':
                sort_criteria = [("rating", -1)]
            elif sort_option == 'lowest':
                sort_criteria = [("rating", 1)]

            reviews = list(reviews_collection.find(query).sort(sort_criteria).skip((page - 1) * per_page).limit(per_page))
            
    return render_template('details.html', trip=trip_data, reviews=reviews, avg_rating=round(avg_rating, 1), review_count=review_count, page=page, total_pages=total_pages, sort_option=sort_option)

@app.route('/submit-review', methods=['POST'])
def submit_review():
    if reviews_collection is None: return "Database Connection Error", 500
    
    trip_name = request.form.get('trip_name')
    rating = request.form.get('rating')
    comment = request.form.get('comment')
    user_name = request.form.get('user_name') or "Traveler"
    
    if rating:
        reviews_collection.insert_one({
            "trip_name": trip_name, "user_name": user_name, "rating": int(rating), "comment": comment, "date": datetime.datetime.now().strftime("%Y-%m-%d")
        })
        
    return redirect(url_for('trip_details', trip_name=trip_name.lower().replace(' ', '-')))

@app.route('/book', methods=['POST'])
def book_trip():
    if bookings_collection is None: return "Database Connection Error", 500

    destination = request.form.get('destination', 'Expedition')
    user_name = request.form.get('full_name', 'Traveler')
    user_email = request.form.get('email')
    travel_date = request.form.get('travel_date')
    
    booking_doc = {
        'name': user_name, 'email': user_email, 'trip': destination,
        'travel_date': travel_date,
        'status': 'Pending', 'date': datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
        'payment_status': 'Unpaid'
    }
    
    booking_id = None
    try:
        result = bookings_collection.insert_one(booking_doc)
        booking_id = result.inserted_id
        
        try:
            msg = Message(f"Booking Received: {destination}", recipients=[user_email])
            msg.html = render_template('emails/booking_confirmation.html', name=user_name, trip=destination)
            mail.send(msg)
            print(f"✅ Booking Email sent to {user_email}")
        except Exception as email_error:
            print(f"❌ Email sending failed: {email_error}")

        return redirect(url_for('payment_page', booking_id=booking_id))
    except Exception as e:
        print(f"Error: {e}")
        flash("An error occurred while processing your booking. Please try again.")
        return redirect(url_for('trip_details', trip_name=destination.replace(' ', '-').lower()))

@app.route('/payment')
def payment_page():
    booking_id = request.args.get('booking_id')
    if not booking_id: return redirect(url_for('home'))
    
    if bookings_collection is None: return "Database Connection Error", 500
    
    booking = bookings_collection.find_one({"_id": ObjectId(booking_id)})
    if not booking: return "Booking not found", 404
    
    trip_name = booking.get('trip')
    trip = trips_collection.find_one({"name": trip_name})
    price = int(trip.get('price', 0)) if trip else 0
    
    # Create Razorpay Order
    amount_paise = price * 100
    order_data = {
        "amount": amount_paise,
        "currency": "INR",
        "receipt": str(booking_id),
        "notes": {"trip": trip_name, "email": booking.get('email')}
    }
    
    try:
        order = razorpay_client.order.create(data=order_data)
        bookings_collection.update_one({"_id": ObjectId(booking_id)}, {"$set": {"razorpay_order_id": order['id']}})
    except Exception as e:
        return f"Error creating payment order: {e}", 500

    return render_template('payment.html', 
                           trip=trip_name, 
                           amount=price, 
                           order=order,
                           key_id=os.environ.get('RAZORPAY_KEY_ID'),
                           user_email=booking.get('email'),
                           user_name=booking.get('name'))

def create_invoice(booking, price, payment_id):
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=letter)
    width, height = letter
    
    # Define Colors
    primary_color = colors.HexColor("#28a745")
    text_color = colors.HexColor("#333333")
    light_gray = colors.HexColor("#f4f4f4")
    
    # --- Header Section ---
    # Logo: Try to load from static folder, fallback to text
    logo_path = os.path.join(app.root_path, 'static', 'img', 'logo.png')
    logo_drawn = False
    
    # Debugging for Vercel Logs
    if os.path.exists(logo_path):
        print(f"✅ Logo found at: {logo_path}, Size: {os.path.getsize(logo_path)} bytes")
        try:
            c.drawImage(logo_path, 50, height - 100, width=120, height=50, preserveAspectRatio=True, mask='auto')
            logo_drawn = True
        except Exception as e:
            print(f"❌ Error drawing logo: {e}")
            pass
    else:
        print(f"❌ Logo NOT found at: {logo_path}")

    if not logo_drawn:
        c.setFont("Helvetica-Bold", 24)
        c.setFillColor(primary_color)
        c.drawString(50, height - 80, "Wanderer")

    # Invoice Details (Top Right)
    c.setFillColor(text_color)
    c.setFont("Helvetica-Bold", 20)
    c.drawRightString(width - 50, height - 70, "INVOICE")
    
    c.setFont("Helvetica", 10)
    c.drawRightString(width - 50, height - 90, f"Date: {datetime.datetime.now().strftime('%Y-%m-%d')}")
    c.drawRightString(width - 50, height - 105, f"ID: {payment_id}")
    
    c.setStrokeColor(colors.lightgrey)
    c.line(50, height - 120, width - 50, height - 120)
    
    # --- Bill To Section ---
    c.setFont("Helvetica-Bold", 12)
    c.drawString(50, height - 150, "Billed To:")
    
    c.setFont("Helvetica", 12)
    c.drawString(50, height - 170, booking.get('name', 'Traveler'))
    c.drawString(50, height - 190, booking.get('email', ''))
    
    # --- Table Header ---
    y = height - 240
    c.setFillColor(light_gray)
    c.rect(50, y, width - 100, 30, fill=1, stroke=0)
    
    c.setFillColor(text_color)
    c.setFont("Helvetica-Bold", 10)
    c.drawString(60, y + 10, "DESCRIPTION")
    c.drawRightString(width - 60, y + 10, "AMOUNT")
    
    # --- Table Content ---
    y -= 30
    c.setFont("Helvetica", 10)
    c.drawString(60, y + 10, f"Trip Package: {booking.get('trip')}")
    c.drawRightString(width - 60, y + 10, f"INR {price:,.2f}")
    
    c.setStrokeColor(colors.lightgrey)
    c.line(50, y, width - 50, y)
    
    # --- Total ---
    y -= 40
    c.setFont("Helvetica-Bold", 12)
    c.drawString(width - 200, y, "Total:")
    c.setFillColor(primary_color)
    c.drawString(width - 60, y, f"INR {price:,.2f}")
    
    # --- Footer ---
    c.setFillColor(text_color)
    c.setFont("Helvetica-Oblique", 10)
    c.drawCentredString(width / 2, 50, "Thank you for traveling with Wanderer!")
    
    c.save()
    buffer.seek(0)
    return buffer

@app.route('/payment/verify', methods=['POST'])
def payment_verify():
    # Get payment details from form
    payment_id = request.form.get('razorpay_payment_id')
    order_id = request.form.get('razorpay_order_id')
    signature = request.form.get('razorpay_signature')
    
    params_dict = {
        'razorpay_order_id': order_id,
        'razorpay_payment_id': payment_id,
        'razorpay_signature': signature
    }
    
    try:
        # Verify signature
        razorpay_client.utility.verify_payment_signature(params_dict)
        
        if bookings_collection is not None:
            booking = bookings_collection.find_one({'razorpay_order_id': order_id})
            if booking:
                print(f"✅ Payment Verified. Updating Booking {booking['_id']} to Paid/Confirmed.")
                bookings_collection.update_one({'_id': booking['_id']}, {'$set': {'payment_status': 'Paid', 'status': 'Confirmed'}})
                
                # Send Receipt Email
                try:
                    msg = Message(f"Booking Successful: {booking['trip']}", recipients=[booking['email']])
                    msg.html = render_template('emails/booking_success_email.html', name=booking['name'], trip=booking['trip'], payment_id=payment_id, date=datetime.datetime.now().strftime("%d %b, %Y"))
                    
                    # Generate and Attach Invoice
                    trip_data = trips_collection.find_one({"name": booking['trip']})
                    price = trip_data.get('price', '0') if trip_data else '0'
                    pdf = create_invoice(booking, price, payment_id)
                    msg.attach("Invoice.pdf", "application/pdf", pdf.read())
                    
                    mail.send(msg)
                    print(f"✅ Receipt Email sent to {booking['email']}")
                except Exception as e:
                    print(f"❌ Error sending receipt email: {e}")
                
                return render_template('booking_success.html', booking=booking)
            else:
                print(f"❌ Error: Booking not found for Order ID {order_id}")

        return redirect(url_for('home'))
    except razorpay.errors.SignatureVerificationError:
        return "Payment Verification Failed", 400

# --- 5. ADMIN CMS ROUTES ---

@app.route('/admin-login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        password = request.form.get('password')
        # Securely check against Environment Variable (Owner controlled)
        if password == os.environ.get('ADMIN_PASSWORD'):
            session['admin_logged_in'] = True
            return redirect(url_for('admin_page'))
        flash("Invalid Admin Password")
    return render_template('admin_login.html')

@app.route('/admin-forgot-password')
def admin_forgot_password():
    admin_email = os.environ.get('MAIL_USERNAME')
    if not admin_email:
        flash("Admin email is not configured in .env")
        return redirect(url_for('admin_login'))

    try:
        msg = Message("Admin Password Reminder", recipients=[admin_email])
        msg.body = f"Hello,\n\nYour Admin Password is: {os.environ.get('ADMIN_PASSWORD')}\n\nKeep it safe!"
        mail.send(msg)
        flash(f"Password reminder sent to {admin_email}")
    except Exception as e:
        print(f"Error sending email: {e}")
        flash("Error sending email. Please check server logs.")
    return redirect(url_for('admin_login'))

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('home'))

@app.route('/admin-dashboard')
def admin_page():
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin_login'))
    
    if bookings_collection is None or trips_collection is None:
        return "Database Connection Error", 500

    all_bookings = list(bookings_collection.find().sort('_id', -1))
    all_trips = list(trips_collection.find())
    
    # Dynamic revenue calculation based on actual trip prices
    # Added safety check: (t.get('price') or 0) ensures we don't crash on empty strings or None
    trip_prices = {}
    for t in all_trips:
        try: trip_prices[t.get('name')] = int(t.get('price') or 0)
        except ValueError: trip_prices[t.get('name')] = 0
        
    total_revenue = sum(trip_prices.get(b.get('trip'), 0) for b in all_bookings if b.get('status') == 'Confirmed')
    
    return render_template('admin.html', bookings=all_bookings, trips=all_trips, revenue=total_revenue)

@app.route('/admin/add-trip', methods=['POST'])
def add_new_trip():
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin_login'))
    
    if trips_collection is None: return "Database Connection Error", 500

    # VALIDATION: Ensure Trip Name is present
    name = request.form.get('name')
    if not name:
        flash("Trip Name is required")
        return redirect(url_for('admin_page'))

    # Applying Form Config: enctype allows 'image_file' to be sent as a file object
    file = request.files.get('image_file')
    filename = "https://via.placeholder.com/400x300?text=No+Image"
    
    if file and allowed_file(file.filename):
        try:
            upload_result = cloudinary.uploader.upload(file)
            filename = upload_result['secure_url']
        except Exception as e:
            flash(f"Error uploading image: {e}")
            return redirect(url_for('admin_page'))

    trip_doc = {
        "name": name,
        "description": request.form.get('description'),
        "price": request.form.get('price'),
        "image": filename,
        "spots": request.form.get('spots')
    }

    trips_collection.insert_one(trip_doc)
    return redirect(url_for('admin_page'))

@app.route('/admin/edit-trip/<trip_id>', methods=['GET', 'POST'])
def edit_trip(trip_id):
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin_login'))
    
    if trips_collection is None: return "Database Connection Error", 500

    try:
        trip = trips_collection.find_one({"_id": ObjectId(trip_id)})
    except:
        return "Invalid Trip ID", 400

    if request.method == 'POST':
        name = request.form.get('name')
        if not name:
            flash("Trip Name is required")
            return redirect(url_for('edit_trip', trip_id=trip_id))

        update_data = {
            "name": name,
            "description": request.form.get('description'),
            "price": request.form.get('price'),
            "spots": request.form.get('spots')
        }

        file = request.files.get('image_file')
        if file and allowed_file(file.filename):
            try:
                upload_result = cloudinary.uploader.upload(file)
                update_data["image"] = upload_result['secure_url']
            except Exception as e:
                flash(f"Error uploading main image: {e}")
                return redirect(url_for('edit_trip', trip_id=trip_id))
            
        # --- Itinerary Processing ---
        itinerary = []
        # Get list of indices from the hidden inputs to know which days were submitted
        day_indices = request.form.getlist('day_indices')
        
        for index in day_indices:
            day_title = request.form.get(f'day_title_{index}')
            if not day_title: continue # Skip empty days

            day_desc = request.form.get(f'day_desc_{index}')
            existing_day_img = request.form.get(f'existing_day_img_{index}')
            
            day_image_name = existing_day_img
            
            # Check if a new image was uploaded for this specific day
            day_file = request.files.get(f'day_image_{index}')
            if day_file and allowed_file(day_file.filename):
                try:
                    upload_result = cloudinary.uploader.upload(day_file)
                    day_image_name = upload_result['secure_url']
                except Exception as e:
                    flash(f"Error uploading itinerary image: {e}")
                    return redirect(url_for('edit_trip', trip_id=trip_id))
            
            itinerary.append({
                "title": day_title,
                "description": day_desc,
                "image": day_image_name
            })
            
        update_data['itinerary'] = itinerary
        
        trips_collection.update_one({"_id": ObjectId(trip_id)}, {"$set": update_data})
        return redirect(url_for('admin_page'))

    return render_template('edit_trip.html', trip=trip)

@app.route('/admin/delete-trip/<trip_id>')
def delete_trip(trip_id):
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin_login'))
    if trips_collection is None: return "Database Connection Error", 500
    trips_collection.delete_one({"_id": ObjectId(trip_id)})
    return redirect(url_for('admin_page'))

@app.route('/update-status/<booking_id>/<new_status>')
def update_status(booking_id, new_status):
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin_login'))
    if bookings_collection is None: return "Database Connection Error", 500
    bookings_collection.update_one({'_id': ObjectId(booking_id)}, {'$set': {'status': new_status}})
    return redirect(url_for('admin_page'))

# --- DEBUG ROUTE (Use this to check files on Vercel) ---
@app.route('/debug-files')
def debug_files():
    output = ["<h1>File System Debug</h1>"]
    
    cwd = os.getcwd()
    output.append(f"<strong>Current Working Directory:</strong> {cwd}")
    output.append(f"<strong>App Root Path:</strong> {app.root_path}")
    
    # 1. Check static/img folder (Where logo usually is)
    img_path = os.path.join(app.root_path, 'static', 'img')
    output.append(f"<h3>Checking {img_path}</h3>")
    
    if os.path.exists(img_path):
        output.append("✅ static/img folder exists.")
        files = os.listdir(img_path)
        for f in files:
            f_path = os.path.join(img_path, f)
            size = os.path.getsize(f_path)
            output.append(f" - {f}: {size} bytes")
            if size < 200:
                output.append(f"   ❌ <strong>CRITICAL ERROR:</strong> {f} is only {size} bytes. This is a Git LFS pointer, not an image. You MUST run the git fix commands.")
            else:
                output.append(f"   ✅ {f} looks like a valid image file.")
    else:
        output.append("❌ static/img folder NOT found.")

    # 2. Check Uploads folder (Where 'other' images might be)
    upload_path = os.path.join(app.root_path, 'static', 'wp-content', 'uploads', '2021', '01')
    output.append(f"<h3>Checking {upload_path}</h3>")
    
    if os.path.exists(upload_path):
        output.append(f"✅ Folder exists. Files: {os.listdir(upload_path)}")
    else:
        output.append("❌ Folder NOT found. (This is expected if .gitignore blocks it)")

    return "<br>".join(output)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0')