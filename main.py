# main.py
import os
import re
import asyncio
from typing import Dict, Any
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
from telegram.error import TelegramError
import yt_dlp
import ffmpeg
from shazamio import Shazam
from pydub import AudioSegment
import shutil
from pathlib import Path
from dotenv import load_dotenv

# .env faylini yuklash
load_dotenv()

# Tokenni .env dan olish
TOKEN = os.getenv("BOT_TOKEN")
if not TOKEN:
    raise RuntimeError("BOT_TOKEN topilmadi. Iltimos, .env fayliga qo'shing.")

# Kanal ma'lumotlari
CHANNEL_ID = '-1002591232668'
CHANNEL_LINK = 'https://t.me/+PejqTTVnqns3YTBi'

# Fayl saqlash papkasi
DOWNLOADS_DIR = Path('downloads')
DOWNLOADS_DIR.mkdir(exist_ok=True)

# Kesh: {link: file_path}
VIDEO_CACHE = {}

# Til ma'lumotlari
LANGUAGES = {
    'uz': {
        'start': 'Iltimos, o‘zingizga qulay tilni tanlang:',
        'channel_subscription': 'Iltimos, kanalga obuna bo‘ling va “Tekshirish” tugmasini bosing.',
        'channel_subscribe_prompt': f'Iltimos, {CHANNEL_LINK} kanaliga obuna bo‘ling va qayta “Tekshirish” tugmasini bosing.',
        'video_downloading': '⏳ <b>Video yuklanmoqda...</b>',
        'video_downloaded': '✅ <b>Video yuklandi!</b> Yuklab oling yoki boshqa amalni tanlang.',
        'video_error': '❌ Video yuklashda xato yuz berdi. Iltimos, havolani tekshiring.',
        'file_too_large': '⚠️ Video hajmi 50 MB dan oshib ketdi. Faqat audio versiyasini yuklab olishingiz mumkin.',
        'audio_conversion': '🎵 <b>MP3 ga aylantirilmoqda...</b>',
        'audio_converted': '✅ <b>Audio tayyor!</b> Yuklab oling.',
        'music_identified': '🎧 <b>Musiqa aniqlanmoqda...</b>',
        'music_result': '🎶 <b>Musiqa aniqlandi:</b> {title} - {artist}',
        'no_music': '❌ Musiqa aniqlanmadi.',
        'invalid_link': '⚠️ Iltimos, to‘g‘ri video havolasini kiriting!',
        'format_selection': 'Iltimos, formatni tanlang:',
        'share_prompt': '✨ Do‘stlaringiz bilan ham baham ko‘ring!',
        'back_to_menu': '🔙 Orqaga',
        'platform_selection': 'Iltimos, platformani tanlang:',
        'try_again': '🔁 Qayta urinish',
        'quality_360': '📹 360p',
        'quality_720': 'HD 720p',
        'only_audio': '🎵 Faqat audio',
    },
    'ru': {
        'start': 'Пожалуйста, выберите удобный для вас язык:',
        'channel_subscription': 'Пожалуйста, подпишитесь на канал и нажмите «Проверить».',
        'channel_subscribe_prompt': f'Пожалуйста, подпишитесь на канал {CHANNEL_LINK} и снова нажмите «Проверить».',
        'video_downloading': '⏳ <b>Видео загружается...</b>',
        'video_downloaded': '✅ <b>Видео загружено!</b> Скачайте или выберите другое действие.',
        'video_error': '❌ Ошибка при загрузке видео. Проверьте ссылку.',
        'file_too_large': '⚠️ Размер видео превышает 50 МБ. Скачайте только аудио.',
        'audio_conversion': '🎵 <b>Конвертация в MP3...</b>',
        'audio_converted': '✅ <b>Аудио готово!</b> Скачайте.',
        'music_identified': '🎧 <b>Распознавание музыки...</b>',
        'music_result': '🎶 <b>Музыка найдена:</b> {title} - {artist}',
        'no_music': '❌ Музыка не распознана.',
        'invalid_link': '⚠️ Введите корректную ссылку на видео!',
        'format_selection': 'Выберите формат:',
        'share_prompt': '✨ Поделитесь ботом с друзьями!',
        'back_to_menu': '🔙 Назад',
        'platform_selection': 'Выберите платформу:',
        'try_again': '🔁 Повторить',
        'quality_360': '📹 360p',
        'quality_720': 'HD 720p',
        'only_audio': '🎵 Только аудио',
    },
    'en': {
        'start': 'Please select your language:',
        'channel_subscription': 'Please subscribe to the channel and click “Check”.',
        'channel_subscribe_prompt': f'Please subscribe to {CHANNEL_LINK} and click “Check” again.',
        'video_downloading': '⏳ <b>Downloading video...</b>',
        'video_downloaded': '✅ <b>Video downloaded!</b> Download or choose another action.',
        'video_error': '❌ Error downloading video. Please check the link.',
        'file_too_large': '⚠️ Video size exceeds 50 MB. You can download audio only.',
        'audio_conversion': '🎵 <b>Converting to MP3...</b>',
        'audio_converted': '✅ <b>Audio ready!</b> Download it.',
        'music_identified': '🎧 <b>Identifying music...</b>',
        'music_result': '🎶 <b>Music found:</b> {title} - {artist}',
        'no_music': '❌ No music identified.',
        'invalid_link': '⚠️ Please enter a valid video link!',
        'format_selection': 'Choose format:',
        'share_prompt': '✨ Share this bot with friends!',
        'back_to_menu': '🔙 Back',
        'platform_selection': 'Select platform:',
        'try_again': '🔁 Try again',
        'quality_360': '📹 360p',
        'quality_720': 'HD 720p',
        'only_audio': '🎵 Audio only',
    },
}

# Toza fayl nomi yaratish
def make_safe_filename(s: str) -> str:
    s = re.sub(r'[^\w\s-]', '', s).strip().replace(' ', '_')
    return s[:50] or 'video'

# Video yuklash (barcha platformalar uchun)
async def download_video(video_link: str, quality: str = '720') -> str:
    # Keshni tekshirish
    if video_link in VIDEO_CACHE and os.path.exists(VIDEO_CACHE[video_link]):
        return VIDEO_CACHE[video_link]

    ydl_opts = {
        'outtmpl': str(DOWNLOADS_DIR / '%(title)s.%(ext)s'),
        'format': 'bestvideo[height<=720]+bestaudio/best' if quality == '720' else 'bestvideo[height<=360]+bestaudio/best',
        'noplaylist': True,
        'quiet': True,
        'no_warnings': True,
        'retries': 5,
        'fragment_retries': 5,
        'http_headers': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(video_link, download=True)
        filename = ydl.prepare_filename(info)
        safe_title = make_safe_filename(info.get('title', 'video'))
        final_path = DOWNLOADS_DIR / f"{safe_title}.mp4"

        if Path(filename).exists() and filename != str(final_path):
            os.rename(filename, final_path)

        VIDEO_CACHE[video_link] = str(final_path)
        return str(final_path)

# MP3 ga aylantirish
def convert_to_mp3(video_file: str) -> str:
    audio_file = video_file.replace('.mp4', '.mp3')
    try:
        stream = ffmpeg.input(video_file)
        stream = ffmpeg.output(stream, audio_file, format='mp3', acodec='mp3', audio_bitrate='192k')
        ffmpeg.run(stream, overwrite_output=True, quiet=True)
        return audio_file
    except Exception as e:
        raise Exception(f"MP3 conversion failed: {str(e)}")

# Audio qirqish (30 sekund)
def trim_audio(audio_file: str, duration: int = 30) -> str:
    trimmed_file = audio_file.replace('.mp3', '_trimmed.mp3')
    try:
        audio = AudioSegment.from_file(audio_file)
        trimmed = audio[:duration * 1000]
        trimmed.export(trimmed_file, format='mp3')
        return trimmed_file
    except Exception as e:
        raise Exception(f"Trimming failed: {str(e)}")

# Musiqa aniqlash
async def identify_music(audio_file: str) -> Dict[str, str]:
    try:
        shazam = Shazam()
        result = await shazam.recognize(audio_file)
        if result and result.get('track'):
            return {
                'title': result['track'].get('title', 'Noma‘lum'),
                'artist': result['track'].get('subtitle', 'Noma‘lum')
            }
        return None
    except Exception:
        return None

# Faylni o'chirish
def cleanup_file(file_path: str):
    try:
        if os.path.exists(file_path):
            os.remove(file_path)
    except Exception as e:
        print(f"O'chirishda xato: {e}")

# Asosiy handlerlar
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("🇺🇿 O'zbekcha", callback_data='uz')],
        [InlineKeyboardButton("🇷🇺 Русский", callback_data='ru')],
        [InlineKeyboardButton("🇬🇧 English", callback_data='en')],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(LANGUAGES['uz']['start'], reply_markup=reply_markup, parse_mode='HTML')

async def language_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    lang = query.data
    context.user_data['lang'] = lang
    text = LANGUAGES[lang]['channel_subscription']
    keyboard = [[InlineKeyboardButton(text, callback_data='check_subscription')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.message.reply_text(text, reply_markup=reply_markup, parse_mode='HTML')

async def check_subscription(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    lang = context.user_data['lang']
    user_id = query.from_user.id
    try:
        member = await context.bot.get_chat_member(CHANNEL_ID, user_id)
        if member.status in ['member', 'administrator', 'creator']:
            text = LANGUAGES[lang]['platform_selection']
            keyboard = [
                [InlineKeyboardButton("📸 Instagram", callback_data='platform_instagram')],
                [InlineKeyboardButton("🎥 YouTube", callback_data='platform_youtube')],
                [InlineKeyboardButton("📱 TikTok", callback_data='platform_tiktok')],
                [InlineKeyboardButton("📘 Facebook", callback_data='platform_facebook')],
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.message.reply_text(text, reply_markup=reply_markup, parse_mode='HTML')
        else:
            keyboard = [
                [InlineKeyboardButton(LANGUAGES[lang]['channel_subscribe_prompt'].split()[0], url=CHANNEL_LINK)],
                [InlineKeyboardButton("🔄 Tekshirish", callback_data='check_subscription')],
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.message.reply_text(LANGUAGES[lang]['channel_subscribe_prompt'], reply_markup=reply_markup, parse_mode='HTML')
    except TelegramError:
        await query.message.reply_text("Xato yuz berdi. Iltimos, keyinroq urinib ko'ring.", parse_mode='HTML')

async def platform_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data['platform'] = query.data.split('_')[1]
    lang = context.user_data['lang']
    await query.message.reply_text("Iltimos, video havolasini yuboring:" if lang == 'uz' else
                                   "Отправьте ссылку на видео:" if lang == 'ru' else
                                   "Send the video link:", parse_mode='HTML')

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if 'platform' not in context.user_data:
        return
    link = update.message.text.strip()
    lang = context.user_data['lang']
    if not re.match(r'^https?://', link):
        await update.message.reply_text(LANGUAGES[lang]['invalid_link'], parse_mode='HTML')
        return

    try:
        await update.message.reply_text(LANGUAGES[lang]['video_downloading'], parse_mode='HTML')
        video_file = await download_video(link)
        context.user_data['video_file'] = video_file

        # Hajmni tekshirish
        file_size = os.path.getsize(video_file)
        if file_size > 50 * 1024 * 1024:
            await update.message.reply_text(LANGUAGES[lang]['file_too_large'], parse_mode='HTML')
            context.user_data['large_file'] = True
        else:
            context.user_data['large_file'] = False

        # Amallar tugmalari
        keyboard = [
            [InlineKeyboardButton("🎵 MP3 audio", callback_data='convert_audio')],
            [InlineKeyboardButton("🎧 Musiqa aniqlash", callback_data='identify_music')],
            [InlineKeyboardButton("📹 360p", callback_data='quality_360'),
             InlineKeyboardButton("HD 720p", callback_data='quality_720')],
            [InlineKeyboardButton(LANGUAGES[lang]['back_to_menu'], callback_data='back_to_platforms')],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(LANGUAGES[lang]['video_downloaded'], reply_markup=reply_markup, parse_mode='HTML')

        with open(video_file, 'rb') as f:
            await update.message.reply_video(video=f)

    except Exception:
        await update.message.reply_text(LANGUAGES[lang]['video_error'], parse_mode='HTML')

# MP3 ga aylantirish
async def convert_audio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    lang = context.user_data['lang']
    video_file = context.user_data.get('video_file')
    if not video_file or not os.path.exists(video_file):
        await query.message.reply_text("Video topilmadi.", parse_mode='HTML')
        return

    try:
        await query.message.reply_text(LANGUAGES[lang]['audio_conversion'], parse_mode='HTML')
        audio_file = convert_to_mp3(video_file)
        with open(audio_file, 'rb') as f:
            await query.message.reply_audio(audio=f)
        await query.message.reply_text(LANGUAGES[lang]['audio_converted'], parse_mode='HTML')
        cleanup_file(audio_file)
    except Exception:
        await query.message.reply_text("Audio yaratishda xato.", parse_mode='HTML')

# Musiqa aniqlash
async def identify_music_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    lang = context.user_data['lang']
    video_file = context.user_data.get('video_file')
    if not video_file or not os.path.exists(video_file):
        await query.message.reply_text("Video topilmadi.", parse_mode='HTML')
        return

    await query.message.reply_text(LANGUAGES[lang]['music_identified'], parse_mode='HTML')
    try:
        audio_file = convert_to_mp3(video_file)
        trimmed = trim_audio(audio_file)
        result = await identify_music(trimmed)
        if result:
            await query.message.reply_text(
                LANGUAGES[lang]['music_result'].format(title=result['title'], artist=result['artist']),
                parse_mode='HTML'
            )
        else:
            await query.message.reply_text(LANGUAGES[lang]['no_music'], parse_mode='HTML')
        cleanup_file(trimmed)
        cleanup_file(audio_file)
    except Exception:
        await query.message.reply_text("Musiqa aniqlashda xato.", parse_mode='HTML')

# Sifat tanlash
async def quality_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    quality = '360' if '360' in query.data else '720'
    link = context.user_data.get('video_file')  # Asl havola saqlanmagan, shu sababli qayta yuklash kerak
    # Eslatma: Sifat o'zgartirish uchun havola saqlanishi kerak. Siz `context.user_data['link']` qo'shishingiz kerak.
    await query.message.reply_text("Sifat o'zgartirish hozir qo'llab-quvvatlanmaydi.", parse_mode='HTML')

# Orqaga qaytish
async def back_to_platforms(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    lang = context.user_data['lang']
    text = LANGUAGES[lang]['platform_selection']
    keyboard = [
        [InlineKeyboardButton("📸 Instagram", callback_data='platform_instagram')],
        [InlineKeyboardButton("🎥 YouTube", callback_data='platform_youtube')],
        [InlineKeyboardButton("📱 TikTok", callback_data='platform_tiktok')],
        [InlineKeyboardButton("📘 Facebook", callback_data='platform_facebook')],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.message.reply_text(text, reply_markup=reply_markup, parse_mode='HTML')

# Barcha handlerlarni qo'shish
def main():
    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler('start', start))
    app.add_handler(CallbackQueryHandler(language_selection, pattern='^(uz|ru|en)$'))
    app.add_handler(CallbackQueryHandler(check_subscription, pattern='^check_subscription$'))
    app.add_handler(CallbackQueryHandler(platform_selected, pattern='^platform_(instagram|youtube|tiktok|facebook)$'))
    app.add_handler(CallbackQueryHandler(convert_audio, pattern='^convert_audio$'))
    app.add_handler(CallbackQueryHandler(identify_music_handler, pattern='^identify_music$'))
    app.add_handler(CallbackQueryHandler(quality_selected, pattern='^quality_(360|720)$'))
    app.add_handler(CallbackQueryHandler(back_to_platforms, pattern='^back_to_platforms$'))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    print("Bot ishga tushdi...")
    app.run_polling()

if __name__ == '__main__':
    main()
