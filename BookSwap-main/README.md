
# 📚 BookSwap-VIT

BookSwap is a web platform that allows VIT students to exchange books with each other through a simple, secure, and chat-based interface.

---

## 🚀 Features

- 📖 List books to give away or request
- 🧑‍🤝‍🧑 Chat-based real-time messaging
- 🔐 Google OAuth 2.0 (VIT email only)
- 🌙 Dark mode support
- 🔄 Real-time updates without refresh
- ✅ Secure backend with Supabase

---

## 🛠 Tech Stack

- **Frontend:** HTML, TailwindCSS, JavaScript
- **Backend:** Flask (Python)
- **Database & Auth:** [Supabase](https://supabase.io)
- **OAuth:** Google OAuth 2.0 via [Authlib](https://docs.authlib.org/)
- **Deployment:** [Render](https://render.com)

---

## 🧪 Local Setup

✅ 1. Clone the repository
  git clone https://github.com/your-username/BookSwap-VIT-2.git
  cd BookSwap-VIT-2

✅ 2. Create and activate a virtual environment
  python -m venv venv
  # Activate it
  # On Windows:
  venv\Scripts\activate
  # On macOS/Linux:
  source venv/bin/activate

✅ 3. Install dependencies
  pip install -r requirements.txt
  
✅ 4. Create a .env file
In the project root, create a .env file with your environment variables, such as:

SUPABASE_URL=https://xyzcompany.supabase.co
SUPABASE_KEY=your_anon_or_service_key
GOOGLE_CLIENT_ID=your_google_client_id
GOOGLE_CLIENT_SECRET=your_google_client_secret
SECRET_KEY=your_flask_secret_key

✅ 5. Run the Flask server
  python main.py
  Or, if you're using Gunicorn:
  gunicorn main:app
  
✅ 6. Visit in browser
Open: http://localhost:5000
