import os
import asyncio
import logging
from aiogram import Bot, Dispatcher, types, F
from aiogram.types import FSInputFile
from aiogram.filters import Command
from pydub import AudioSegment
import speech_recognition as sr
from deep_translator import GoogleTranslator
from gtts import gTTS # Yangi kutubxona

# --- SOZLAMALAR ---
# Railway Environment Variables dan o'qib oladi
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = os.getenv("ADMIN_ID")

# Logging
logging.basicConfig(level=logging.INFO)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# --- YORDAMCHI FUNKSIYALAR ---

def speech_to_text(file_path):
    """Audioni matnga aylantiradi (Google Free API)"""
    r = sr.Recognizer()
    with sr.AudioFile(file_path) as source:
        r.adjust_for_ambient_noise(source)
        audio_data = r.record(source)
        try:
            text = r.recognize_google(audio_data, language="uz-UZ")
            return text
        except sr.UnknownValueError:
            return None
        except sr.RequestError:
            return "API_ERROR"

def translate_text(text):
    """Matnni ingliz tiliga tarjima qiladi"""
    try:
        translator = GoogleTranslator(source='auto', target='en')
        return translator.translate(text)
    except Exception as e:
        logging.error(f"Translation error: {e}")
        return None

def text_to_speech_gtts(text, output_file):
    """Matnni Google TTS orqali ovozga aylantiradi (Bepul, standart ovoz)"""
    try:
        # 'lang' ni 'en' (inglizcha) deb belgilaymiz
        tts = gTTS(text=text, lang='en')
        tts.save(output_file)
        return True
    except Exception as e:
        logging.error(f"gTTS Error: {e}")
        return False

# --- HANDLERLAR ---

async def is_admin(user_id):
    """Foydalanuvchi Admin ekanligini tekshiradi"""
    try:
        return int(user_id) == int(ADMIN_ID)
    except:
        return False

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    if await is_admin(message.from_user.id):
        await message.answer(
            "Salom Admin! ✅ Bepul rejimga o'tildi.\n"
            "Men o'zbekcha audioni qabul qilib, ingliz tilida **standart robotik ovozda** qaytaraman."
        )
    else:
        await message.answer("Uzr, bu bot shaxsiy foydalanish uchun.")

@dp.message(F.voice | F.audio)
async def handle_audio(message: types.Message):
    if not await is_admin(message.from_user.id):
        return

    wait_msg = await message.answer("⏳ Audio qabul qilindi. Jarayon boshlandi...")
    
    file_id = message.voice.file_id if message.voice else message.audio.file_id
    ogg_path = f"temp_{file_id}.ogg"
    wav_path = f"temp_{file_id}.wav"
    mp3_output = f"final_{file_id}.mp3"

    try:
        file = await bot.get_file(file_id)
        await bot.download_file(file.file_path, ogg_path)

        # OGG -> WAV konvertatsiya
        audio = AudioSegment.from_file(ogg_path)
        audio.export(wav_path, format="wav")

        # 1. STT (Matnga o'girish)
        await wait_msg.edit_text("⏳ Eshitilmoqda (STT)...")
        uz_text = await asyncio.to_thread(speech_to_text, wav_path)

        if not uz_text:
            await wait_msg.edit_text("❌ Ovozni tushunib bo'lmadi.")
            return
        
        # 2. Tarjima
        await wait_msg.edit_text(f"📝 {uz_text}\n\n🇬🇧 Tarjima qilinmoqda...")
        en_text = await asyncio.to_thread(translate_text, uz_text)

        if not en_text:
            await wait_msg.edit_text("❌ Tarjimada xatolik.")
            return

        # 3. TTS (Ovozlashtirish - gTTS)
        await wait_msg.edit_text(f"🇬🇧 {en_text}\n\n🎙 Ovoz yozilmoqda (standart TTS)...")
        success = await asyncio.to_thread(text_to_speech_gtts, en_text, mp3_output)

        if success:
            # Faylni yuborish
            audio_file = FSInputFile(mp3_output)
            await message.answer_audio(
                audio_file, 
                caption=f"🇺🇿: {uz_text}\n🇬🇧: {en_text}",
                performer="gTTS",
                title="English Translation"
            )
            await wait_msg.delete()
        else:
            await wait_msg.edit_text("❌ gTTS bilan ovoz yaratishda xatolik yuz berdi.")

    except Exception as e:
        await wait_msg.edit_text(f"Umumiy xatolik: {str(e)}")
        logging.error(e)
    
    finally:
        # Fayllarni tozalash
        for f in [ogg_path, wav_path, mp3_output]:
            if os.path.exists(f):
                try:
                    os.remove(f)
                except:
                    pass

# --- MAIN ---
async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
