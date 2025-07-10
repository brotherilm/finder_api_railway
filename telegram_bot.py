import os
import logging
from telegram import Update
from telegram.ext import Application, MessageHandler, filters, ContextTypes
import asyncpg
from datetime import datetime
from urllib.parse import quote

# Konfigurasi Bot
TOKEN = "8186303125:AAEU3cKzbllqtiot55iRbDf0Q5yK44EelGA"
BOT_USERNAME = "@StoreDB_airdropbot"

# Konfigurasi Database
DB_CONFIG = {
    "user": "neondb_owner",
    "password": "npg_ntWwHqA9dKI2",
    "database": "neondb",
    "host": "ep-lucky-shape-a14jznh2-pooler.ap-southeast-1.aws.neon.tech",
    "port": "5432",
    "ssl": "require"
}

# Setup logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

async def create_db_pool():
    try:
        pool = await asyncpg.create_pool(
            user=DB_CONFIG['user'],
            password=DB_CONFIG['password'],
            database=DB_CONFIG['database'],
            host=DB_CONFIG['host'],
            port=DB_CONFIG['port'],
            ssl=DB_CONFIG['ssl']
        )
        logger.info("Koneksi database berhasil dibuat")
        return pool
    except Exception as e:
        logger.error(f"Gagal membuat koneksi database: {e}")
        raise

async def save_message_to_db(message_text: str, db_pool, source_link=None, is_forwarded=False):
    try:
        async with db_pool.acquire() as connection:
            await connection.execute(
                """INSERT INTO messages 
                (message, source_link, is_forwarded) 
                VALUES ($1, $2, $3)""",
                message_text,
                source_link,
                is_forwarded
            )
            logger.info(f"Pesan disimpan: {message_text[:100]}... | Link: {source_link}")
    except Exception as e:
        logger.error(f"Gagal menyimpan pesan ke database: {e}")
        raise

def generate_group_link(chat_id, message_id=None):
    """Generate link grup/channel Telegram"""
    base_url = "https://t.me/c/"
    chat_id_str = str(chat_id).replace('-100', '')
    if message_id:
        return f"{base_url}{chat_id_str}/{message_id}"
    return f"{base_url}{chat_id_str}"

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message
    if not message:
        return

    message_type = message.chat.type
    
    # Ambil teks pesan (baik dari text biasa atau caption media)
    message_text = message.text or message.caption
    
    # Jika tidak ada teks sama sekali (hanya gambar tanpa caption)
    if not message_text:
        await message.reply_text("Maaf, saya hanya menyimpan teks. Gambar tidak disimpan.")
        return

    # Cek jika pesan diforward dan dapatkan link sumber
    source_link = None
    is_forwarded = False
    
    if hasattr(message, 'forward_origin'):
        if message.forward_origin.type == "channel":
            try:
                chat_id = message.forward_origin.chat.id
                message_id = message.forward_origin.message_id
                source_link = generate_group_link(chat_id, message_id)
                is_forwarded = True
            except Exception as e:
                logger.error(f"Gagal generate link channel: {e}")
        elif message.forward_origin.type == "chat":
            try:
                chat_id = message.forward_origin.sender_chat.id
                source_link = generate_group_link(chat_id)
                is_forwarded = True
            except Exception as e:
                logger.error(f"Gagal generate link grup: {e}")

    logger.info(f'User ({message.chat.id}) in {message_type}: "{message_text[:100]}..." | Forwarded: {is_forwarded}')

    if message_type == 'private':
        try:
            await save_message_to_db(
                message_text, 
                context.application.db_pool,
                source_link,
                is_forwarded
            )
            
            reply_text = "Pesan teks Anda telah disimpan ke database!"
            if is_forwarded and source_link:
                reply_text += f"\n\nLink sumber: {source_link}"
                
            await message.reply_text(reply_text)
        except Exception as e:
            await message.reply_text("Maaf, terjadi kesalahan saat menyimpan pesan.")
            logger.error(f"Error: {e}")
    else:
        await message.reply_text("Silakan kirim pesan secara private ke bot ini.")

async def error(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.error(f'Update {update} caused error {context.error}')

async def post_init(application: Application):
    """Fungsi yang dijalankan setelah inisialisasi aplikasi"""
    application.db_pool = await create_db_pool()

if __name__ == '__main__':
    # Membuat aplikasi dengan post_init handler
    app = Application.builder() \
        .token(TOKEN) \
        .post_init(post_init) \
        .build()

    # Handlers - menerima semua pesan yang mengandung teks atau caption
    app.add_handler(MessageHandler(
        filters.TEXT | filters.CAPTION | filters.PHOTO, 
        handle_message
    ))
    app.add_error_handler(error)

    logger.info(f'Bot sedang berjalan... {BOT_USERNAME}')
    app.run_polling()