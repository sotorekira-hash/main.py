import sqlite3
from flask import Flask, render_template, request, redirect, url_for
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes, ConversationHandler
import threading

# --- CONFIGURATION ---
TOKEN = "8580570797:AAHkwZwKPi2V40-1Nfs_1ajXL-dRCIJwvw0"
ADMIN_ID = 5169380878
QR_IMAGE_URL = "https://severe-rose-lejstuwqmj.edgeone.app/IMG_6051.jpeg"

# Bot States
GET_GAME_ID, GET_RECEIPT = range(2)

# --- DATABASE ENGINE ---
def get_db():
    conn = sqlite3.connect('business.db', check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    db = get_db()
    db.execute('CREATE TABLE IF NOT EXISTS products (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, diamonds INTEGER, price REAL)')
    db.execute('CREATE TABLE IF NOT EXISTS orders (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id TEXT, game_id TEXT, item TEXT, status TEXT DEFAULT "PENDING")')
    db.execute('CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY)')
    db.commit()

# --- FLASK WEBSITE (ADMIN PANEL) ---
web_app = Flask(__name__)

@web_app.route('/')
def dashboard():
    db = get_db()
    prods = db.execute('SELECT * FROM products').fetchall()
    orders = db.execute('SELECT * FROM orders ORDER BY id DESC').fetchall()
    return f"""
    <html>
        <head><title>Topup Admin</title><style>body{{font-family:sans-serif; padding:20px;}} table{{width:100%; border-collapse:collapse;}} th,td{{border:1px solid #ddd; padding:8px;}}</style></head>
        <body>
            <h1>💎 Topup Business Dashboard</h1>
            <h2>Add Product</h2>
            <form action="/add_prod" method="post">
                <input name="name" placeholder="Name"> <input name="dia" placeholder="Diamonds"> <input name="price" placeholder="Price">
                <button type="submit">Add</button>
            </form>
            <hr>
            <h2>Recent Orders</h2>
            <table>
                <tr><th>ID</th><th>User</th><th>Game ID</th><th>Item</th><th>Status</th></tr>
                {"".join([f"<tr><td>{o['id']}</td><td>{o['user_id']}</td><td>{o['game_id']}</td><td>{o['item']}</td><td>{o['status']}</td></tr>" for o in orders])}
            </table>
        </body>
    </html>
    """

@web_app.route('/add_prod', methods=['POST'])
def add_prod():
    db = get_db()
    db.execute('INSERT INTO products (name, diamonds, price) VALUES (?,?,?)', (request.form['name'], request.form['dia'], request.form['price']))
    db.commit()
    return redirect('/')

# --- TELEGRAM BOT LOGIC ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db = get_db()
    db.execute('INSERT OR IGNORE INTO users (user_id) VALUES (?)', (update.effective_user.id,))
    db.commit()
    kb = [[InlineKeyboardButton("🛍 Shop", callback_query_data='shop')]]
    await update.message.reply_text("Welcome to the Bot! Shop via the button below.", reply_markup=InlineKeyboardMarkup(kb))

async def show_shop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db = get_db()
    prods = db.execute('SELECT * FROM products').fetchall()
    kb = [[InlineKeyboardButton(f"{p['name']} - ${p['price']}", callback_data=f"buy_{p['id']}")] for p in prods]
    await update.callback_query.edit_message_text("Select Item:", reply_markup=InlineKeyboardMarkup(kb))

async def buy_item(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    pid = query.data.split('_')[1]
    db = get_db()
    p = db.execute('SELECT * FROM products WHERE id=?', (pid,)).fetchone()
    context.user_data['item'] = f"{p['name']} ({p['diamonds']}💎)"
    await query.edit_message_text("Enter your Game ID:")
    return GET_GAME_ID

async def handle_gid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['gid'] = update.message.text
    await update.message.reply_photo(photo=QR_IMAGE_URL, caption="Pay via QR and send receipt screenshot.")
    return GET_RECEIPT

async def handle_receipt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db = get_db()
    db.execute('INSERT INTO orders (user_id, game_id, item) VALUES (?,?,?)', 
               (update.effective_user.id, context.user_data['gid'], context.user_data['item']))
    db.commit()
    await update.message.reply_text("✅ Success! Admin is checking the dashboard.")
    await context.bot.send_message(ADMIN_ID, "🔔 New order on the Website Dashboard!")
    return ConversationHandler.END

# --- RUNNER ---
def run_bot():
    init_db()
    app = Application.builder().token(TOKEN).build()
    
    conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(buy_item, pattern='^buy_')],
        states={
            GET_GAME_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_gid)],
            GET_RECEIPT: [MessageHandler(filters.PHOTO, handle_receipt)],
        },
        fallbacks=[CommandHandler("start", start)]
    )
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(show_shop, pattern='shop'))
    app.add_handler(conv)
    app.run_polling()

if __name__ == '__main__':
    # Start Bot in a separate thread
    threading.Thread(target=run_bot).start()
    # Start Website
    print("Website running at http://127.0.0.1:5000")
    web_app.run(port=5000)
