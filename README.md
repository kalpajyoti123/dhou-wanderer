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
- **Storage**: Git LFS for large media files

## Setup Instructions

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd dhou--wanderer
   ```
   *Note: Run `git lfs install` and `git lfs pull` to download large media files.*

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
   MAIL_PASS=your_16_char_app_password  # Generate this in Google Account > Security > App Passwords
   RAZORPAY_KEY_ID=your_razorpay_key
   RAZORPAY_KEY_SECRET=your_razorpay_secret
   ADMIN_PASSWORD=your_admin_password
   CLOUDINARY_CLOUD_NAME=ddqpoqxwq
   CLOUDINARY_API_KEY=your_api_key
   CLOUDINARY_API_SECRET=BDzHYOKfXg9Y1ZGDQsdzfBMiL-A
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

### Vercel Deployment
1. A `vercel.json` file is included for configuration.
2. Push your code to GitHub and import the repository into Vercel.
3. Add your environment variables in the Vercel Dashboard (Settings > Environment Variables).

**⚠️ LFS Warning**: Vercel does not download Git LFS files during deployment. Large videos (like `hero.mp4`) must be hosted externally (e.g., AWS S3, Cloudinary) or they will appear broken.
**⚠️ Important Limitation**: Vercel uses an ephemeral file system. User uploads (profile pictures, trip images) will **NOT** persist after the request finishes. To support uploads on Vercel, you must update the code to store images in a cloud storage service like AWS S3 or Cloudinary.

## Troubleshooting

### Database Connection Error
If you see a database connection error after deployment:
1. **MongoDB Atlas IP Whitelist**: Go to MongoDB Atlas > Network Access > Add IP Address. Select **"Allow Access from Anywhere"** (0.0.0.0/0). Cloud platforms like Render/Heroku use dynamic IPs, so whitelisting a specific IP won't work.
2. **Environment Variables**: Ensure `MONGO_URI` is correctly set in your cloud provider's dashboard (Settings > Environment Variables).
3. **SSL Certificate**: If using Python, you might need `certifi` to fix SSL handshake errors.
   - Install it: `pip install certifi`
   - Update your connection code:
     ```python
     import certifi
     client = MongoClient(os.getenv('MONGO_URI'), tlsCAFile=certifi.where())
     ```

### Images Broken (LFS Issue)
If your images (logo, backgrounds) appear broken on Vercel, they might still be stored as "LFS Pointers" (tiny text files) instead of actual images.
To fix this, run these commands in your terminal:
```bash
git lfs uninstall
rm .gitattributes
git rm -r --cached static
git add static
git commit -m "Fix: Force re-add static images to remove LFS"
git push origin main
```