# Wanderer

## Overview
This repository contains the source code for the Wanderer project.

## Prerequisites
* Python 3.x
* pip

## Installation

1.  **Clone the repository:**
    ```bash
    git clone <repository-url>
    cd dhou--wanderer
    ```

2.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

## Configuration
Create a `.env` file in the root directory and add the following variables:
```
SECRET_KEY=your_secret_key
MONGO_URI=your_mongodb_connection_string
MAIL_PASS=your_email_password
RAZORPAY_KEY_ID=your_razorpay_key_id
RAZORPAY_KEY_SECRET=your_razorpay_key_secret
GOOGLE_CLIENT_ID=your_google_client_id
GOOGLE_CLIENT_SECRET=your_google_client_secret
ADMIN_PASSWORD=your_admin_password
```

## Deployment
This project includes a `Procfile` and is configured for deployment on platforms like Heroku.

## License
This project is licensed under the MIT License - see the LICENSE.md file for details.