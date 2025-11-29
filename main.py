import os
import asyncio
import logging
import requests
from aiogram import Bot, Dispatcher, types, F
from aiogram.types import FSInputFile
from aiogram.filters import Command
from pydub import AudioSegment
import speech_recognition as sr
from deep_translator import GoogleTranslator

# --- SOZLAMALAR ---
# Railway Environment Variables dan o'qib oladi
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = os.getenv("ADMIN_ID") # String kelishi mumkin, pastda int ga o'giramiz
ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY")
# Agar Voice ID kiritilmasa, avtomatik "Antoni" ni oladi
ELEVENLABS_VOICE_ID = os.getenv("ELEVENLABS_VOICE_ID", "ErXwobaYiN019PkySvjV") 

# Logging
logging.basicConfig(level=logging.INFO)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# --- YORDAMCHI FUNKSIYALAR ---

def speech_to_text(file_path):
    """O'zbekcha audioni matnga aylantiradi"""
    r = sr.Recognizer()
    with sr.AudioFile(file_path) as source:
        # Shovqinni tozalashga urinib ko'ramiz
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
    """O'zbekchadan Inglizchaga tarjima"""
    try:
        translator = GoogleTranslator(source='auto', target='en')
        return translator.translate(text)
    except Exception as e:
        logging.error(f"Translation error: {e}")
        return None

def text_to_speech_elevenlabs(text, output_file):
    """Matnni ovozga aylantiradi (ElevenLabs)"""
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{ELEVENLABS_VOICE_ID}"
    
    headers = {
        "Accept": "audio/mpeg",
        "Content-Type": "application/json",
        "xi-api-key": ELEVENLABS_API_KEY
    }
    
    data = {
        "text": text,
        "model_id": "eleven_multilingual_v2", # Tilni yaxshi tushunadigan model
        "voice_settings": {
            "stability": 0.5,
            "similarity_boost": 0.75
        }
    }

    try:
        response = requests.post(url, json=data, headers=headers)
        if response.status_code == 200:
            with open(output_file, 'wb') as f:
                f.write(response.content)
            return True
        else:
            logging.error(f"ElevenLabs Error: {response.text}")
            return False
    except Exception as e:
        logging.error(f"TTS Error: {e}")
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
        await message.answer(f"Salom Admin! 👨‍🎓\nMen tayyorman. Menga o'zbekcha gapirilgan audio yuboring, men uni ingliz tilida 'Talaba' ovozida qaytaraman.")
    else:
        # Admin bo'lmasa javob bermaydi yoki rad etadi
        await message.answer("Uzr, bu bot shaxsiy foydalanish uchun.")

@dp.message(F.voice | F.audio)
async def handle_audio(message: types.Message):
    # 1. Admin tekshiruvi
    if not await is_admin(message.from_user.id):
        return

    wait_msg = await message.answer("⏳ Audio qabul qilindi...")
    
    # Vaqtinchalik fayl nomlari
    file_id = message.voice.file_id if message.voice else message.audio.file_id
    ogg_path = f"temp_{file_id}.ogg"
    wav_path = f"temp_{file_id}.wav"
    mp3_output = f"final_{file_id}.mp3"

    try:
        # 2. Faylni yuklab olish
        file = await bot.get_file(file_id)
        await bot.download_file(file.file_path, ogg_path)

        # 3. Formatni o'zgartirish (OGG -> WAV)
        # SpeechRecognition faqat WAV (PCM) formatini qabul qiladi
        audio = AudioSegment.from_file(ogg_path)
        audio.export(wav_path, format="wav")

        # 4. STT (Matnga o'girish)
        await wait_msg.edit_text("⏳ Eshitilmoqda (STT)...")
        uz_text = await asyncio.to_thread(speech_to_text, wav_path)

        if not uz_text:
            await wait_msg.edit_text("❌ Ovozni tushunib bo'lmadi. Iltimos, donaroq gapiring.")
            return
        
        # 5. Tarjima
        await wait_msg.edit_text(f"📝 {uz_text}\n\n🇬🇧 Tarjima qilinmoqda...")
        en_text = await asyncio.to_thread(translate_text, uz_text)

        if not en_text:
            await wait_msg.edit_text("❌ Tarjimada xatolik.")
            return

        # 6. TTS (Ovozlashtirish)
        await wait_msg.edit_text(f"🇬🇧 {en_text}\n\n🎙 Ovoz yozilmoqda...")
        success = await asyncio.to_thread(text_to_speech_elevenlabs, en_text, mp3_output)

        if success:
            # Faylni yuborish
            audio_file = FSInputFile(mp3_output)
            await message.answer_audio(
                audio_file, 
                caption=f"🇺🇿: {uz_text}\n🇬🇧: {en_text}",
                performer="AI Student",
                title="English Translation"
            )
            await wait_msg.delete()
        else:
            await wait_msg.edit_text("❌ ElevenLabs kvotasi tugagan yoki API xato.")

    except Exception as e:
        await wait_msg.edit_text(f"Xatolik: {str(e)}")
        logging.error(e)
    
    finally:
        # Fayllarni tozalash (joyni tejash uchun muhim)
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
