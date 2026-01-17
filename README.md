# Wanderer - Travel Beyond the Ordinary

A full-stack Flask application for a travel agency, featuring trip bookings, payment integration, and an admin dashboard.

## Features

- **User Authentication**: Sign up/Login via Email or Google OAuth.
- **Trip Booking**: Browse destinations and book trips.
- **Payments**: Integrated with Razorpay for secure transactions.
- **Admin Dashboard**: CMS to manage trips, view bookings, and track revenue.
- **Email Notifications**: Automated booking confirmations and payment receipts.
- **Responsive Design**: Mobile-friendly UI with video backgrounds.

## Tech Stack

- **Backend**: Python, Flask
- **Database**: MongoDB Atlas
- **Frontend**: HTML, CSS, JavaScript
- **Payment Gateway**: Razorpay
- **Deployment**: Ready for Render/Heroku (Gunicorn)

## Setup Instructions

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd dhou--wanderer
   ```

2. **Install Dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Environment Variables**
   Create a `.env` file in the root directory with the following keys:
   ```env
   SECRET_KEY=your_secret_key
   MONGO_URI=your_mongodb_connection_string
   MAIL_USERNAME=your_email@gmail.com
   MAIL_PASS=your_app_password
   RAZORPAY_KEY_ID=your_razorpay_key
   RAZORPAY_KEY_SECRET=your_razorpay_secret
   GOOGLE_CLIENT_ID=your_google_client_id
   GOOGLE_CLIENT_SECRET=your_google_client_secret
   ADMIN_PASSWORD=your_admin_password
   ```

4. **Run the Application**
   ```bash
   python app.py
   ```
   Visit `http://localhost:5000` in your browser.

## Deployment

This project includes a `Procfile` and is configured for deployment on platforms like Render or Heroku.

1. Push code to GitHub.
2. Connect repository to Render/Heroku.
3. Add environment variables in the dashboard.
4. Deploy!