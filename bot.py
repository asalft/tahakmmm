import os
import logging
from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.tl.functions.account import UpdateProfileRequest
from telethon.tl.functions.auth import SendCodeRequest, SignInRequest
from telethon.tl.functions.account import ChangePhoneRequest
from telethon.tl.functions.photos import UploadProfilePhotoRequest
import asyncio
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, ConversationHandler
from datetime import datetime
import pytz

# إعدادات التسجيل
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# بيانات التطبيق - احصل عليها من https://my.telegram.org
API_ID = '27227913'
API_HASH = 'ba805b182eca99224403dbcd5d4f50aa'

# توكن البوت - احصل عليه من @BotFather
BOT_TOKEN = '8312961595:AAGq7D-kYigx449kW6c-PLxevs1dBGcTSgs'

# حالات المحادثة
PHONE, CODE, NEW_PHONE, NEW_CODE = range(4)
POST_TEXT, POST_INTERVAL, POST_COUNT, POST_TARGET = range(4, 8)
CHANGE_PHOTO = 8

# تخزين البيانات المؤقتة
user_sessions = {}

class TelethonManager:
    def __init__(self):
        self.client = None
        self.phone = None
        
    async def start_session(self, phone):
        """بدء جلسة Telethon"""
        try:
            self.client = TelegramClient(StringSession(), API_ID, API_HASH)
            await self.client.connect()
            self.phone = phone
            return True, "تم بدء الجلسة بنجاح"
        except Exception as e:
            return False, f"خطأ في بدء الجلسة: {str(e)}"
    
    async def send_code(self, phone):
        """إرسال رمز التحقق"""
        try:
            await self.client.send_code_request(phone)
            return True, "تم إرسال رمز التحقق"
        except Exception as e:
            return False, f"خطأ في إرسال الرمز: {str(e)}"
    
    async def sign_in(self, code):
        """تسجيل الدخول بالرمز"""
        try:
            await self.client.sign_in(phone=self.phone, code=code)
            
            if self.client.is_user_authorized():
                return True, "تم تسجيل الدخول بنجاح"
            else:
                return False, "يحتاج الحساب إلى التحقق بخطوتين"
                
        except Exception as e:
            return False, f"خطأ في تسجيل الدخول: {str(e)}"
    
    async def change_phone_number(self, new_phone):
        """تغيير رقم الهاتف"""
        try:
            result = await self.client(SendCodeRequest(
                phone_number=new_phone,
                settings=None
            ))
            return True, "تم إرسال رمز التحقق للرقم الجديد", result.phone_code_hash
        except Exception as e:
            return False, f"خطأ في تغيير رقم الهاتف: {str(e)}", None
    
    async def confirm_phone_change(self, code, phone_code_hash):
        """تأكيد تغيير رقم الهاتف"""
        try:
            result = await self.client(ChangePhoneRequest(
                phone_number=self.phone,
                phone_code_hash=phone_code_hash,
                phone_code=code
            ))
            return True, "تم تغيير رقم الهاتف بنجاح"
        except Exception as e:
            return False, f"خطأ في تأكيد تغيير الرقم: {str(e)}"

    async def get_account_info(self):
        """الحصول على معلومات الحساب"""
        try:
            me = await self.client.get_me()
            return True, me
        except Exception as e:
            return False, f"خطأ في الحصول على معلومات الحساب: {str(e)}"
    
    async def update_profile_with_time(self):
        """تحديث الملف الشخصي مع إضافة الوقت"""
        try:
            # الحصول على الوقت الحالي بتوقيت العراق/بغداد
            iraq_tz = pytz.timezone('Asia/Baghdad')
            current_time = datetime.now(iraq_tz)
            time_str = current_time.strftime("%I:%M %p")
            
            me = await self.client.get_me()
            current_first_name = me.first_name or ""
            
            # إضافة الوقت إلى الاسم
            new_first_name = f"{current_first_name} | {time_str}"
            
            await self.client(UpdateProfileRequest(
                first_name=new_first_name
            ))
            return True, f"تم تحديث الاسم إلى: {new_first_name}"
        except Exception as e:
            return False, f"خطأ في تحديث الملف الشخصي: {str(e)}"
    
    async def change_profile_photo(self, photo_path):
        """تغيير صورة الملف الشخصي"""
        try:
            await self.client(UploadProfilePhotoRequest(
                file=await self.client.upload_file(photo_path)
            ))
            return True, "تم تغيير صورة الملف الشخصي بنجاح"
        except Exception as e:
            return False, f"خطأ في تغيير الصورة: {str(e)}"
    
    async def auto_post_message(self, text, interval, count, target):
        """النشر التلقائي للرسائل"""
        try:
            for i in range(count):
                await self.client.send_message(target, text)
                logger.info(f"تم إرسال الرسالة {i+1}/{count} إلى {target}")
                
                if i < count - 1:
                    await asyncio.sleep(interval)
            
            return True, f"تم إرسال {count} رسالة بنجاح"
        except Exception as e:
            return False, f"خطأ في النشر التلقائي: {str(e)}"

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """بدء المحادثة مع البوت"""
    user_id = update.effective_user.id
    
    if user_id not in user_sessions:
        user_sessions[user_id] = {'manager': TelethonManager()}
    
    keyboard = [
        [KeyboardButton("بدء جلسة جديدة"), KeyboardButton("تغيير رقم الهاتف")],
        [KeyboardButton("معلومات الحساب"), KeyboardButton("إنهاء الجلسة")],
        [KeyboardButton("النشر التلقائي"), KeyboardButton("تحديث الاسم بالوقت")],
        [KeyboardButton("تغيير صورة الملف الشخصي")]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    
    await update.message.reply_text(
        "مرحباً! أنا بوت لإدارة جلسات Telethon.\n"
        "اختر أحد الخيارات:",
        reply_markup=reply_markup
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة الرسائل النصية"""
    text = update.message.text
    user_id = update.effective_user.id
    
    if text == "بدء جلسة جديدة":
        await update.message.reply_text("أرسل رقم هاتفك مع رمز الدولة (مثال: +1234567890):")
        return PHONE
    
    elif text == "تغيير رقم الهاتف":
        if user_id in user_sessions and user_sessions[user_id].get('client'):
            await update.message.reply_text("أرسل رقم الهاتف الجديد مع رمز الدولة:")
            return NEW_PHONE
        else:
            await update.message.reply_text("يجب بدء جلسة أولاً!")
            return ConversationHandler.END
    
    elif text == "معلومات الحساب":
        if user_id in user_sessions and user_sessions[user_id].get('client'):
            client = user_sessions[user_id]['client']
            me = await client.get_me()
            info = f"الاسم: {me.first_name}\n"
            if me.last_name:
                info += f"الاسم الأخير: {me.last_name}\n"
            info += f"اسم المستخدم: @{me.username}\n" if me.username else "لا يوجد اسم مستخدم\n"
            info += f"رقم الهاتف: {me.phone}\n"
            info += f"معرف الحساب: {me.id}"
            
            await update.message.reply_text(info)
        else:
            await update.message.reply_text("لا توجد جلسة نشطة!")
    
    elif text == "إنهاء الجلسة":
        if user_id in user_sessions and user_sessions[user_id].get('client'):
            await user_sessions[user_id]['client'].disconnect()
            user_sessions[user_id]['client'] = None
            user_sessions[user_id]['manager'] = None
            await update.message.reply_text("تم إنهاء الجلسة بنجاح!")
        else:
            await update.message.reply_text("لا توجد جلسة نشطة!")
    
    elif text == "النشر التلقائي":
        if user_id in user_sessions and user_sessions[user_id].get('client'):
            await update.message.reply_text("أرسل النص الذي تريد نشره:")
            return POST_TEXT
        else:
            await update.message.reply_text("يجب بدء جلسة أولاً!")
            return ConversationHandler.END
    
    elif text == "تحديث الاسم بالوقت":
        if user_id in user_sessions and user_sessions[user_id].get('client'):
            manager = user_sessions[user_id]['manager']
            success, message = await manager.update_profile_with_time()
            await update.message.reply_text(message)
        else:
            await update.message.reply_text("يجب بدء جلسة أولاً!")
    
    elif text == "تغيير صورة الملف الشخصي":
        if user_id in user_sessions and user_sessions[user_id].get('client'):
            await update.message.reply_text("أرسل الصورة التي تريد تعيينها كصورة للملف الشخصي:")
            return CHANGE_PHOTO
        else:
            await update.message.reply_text("يجب بدء جلسة أولاً!")
            return ConversationHandler.END
    
    return ConversationHandler.END

async def get_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """الحصول على رقم الهاتف"""
    phone = update.message.text
    user_id = update.effective_user.id
    
    user_sessions[user_id]['phone'] = phone
    
    manager = user_sessions[user_id]['manager']
    success, message = await manager.start_session(phone)
    
    if success:
        success, message = await manager.send_code(phone)
        if success:
            await update.message.reply_text("تم إرسال رمز التحقق. أرسل الرمز:")
            return CODE
        else:
            await update.message.reply_text(message)
            return ConversationHandler.END
    else:
        await update.message.reply_text(message)
        return ConversationHandler.END

async def get_code(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """الحصول على رمز التحقق"""
    code = update.message.text
    user_id = update.effective_user.id
    
    manager = user_sessions[user_id]['manager']
    success, message = await manager.sign_in(code)
    
    if success:
        user_sessions[user_id]['client'] = manager.client
        await update.message.reply_text("تم تسجيل الدخول بنجاح! يمكنك الآن استخدام الخدمات.")
    else:
        await update.message.reply_text(message)
    
    return ConversationHandler.END

async def get_new_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """الحصول على رقم الهاتف الجديد"""
    new_phone = update.message.text
    user_id = update.effective_user.id
    
    user_sessions[user_id]['new_phone'] = new_phone
    
    manager = user_sessions[user_id]['manager']
    success, message, phone_code_hash = await manager.change_phone_number(new_phone)
    
    if success:
        user_sessions[user_id]['phone_code_hash'] = phone_code_hash
        await update.message.reply_text("تم إرسال رمز التحقق للرقم الجديد. أرسل الرمز:")
        return NEW_CODE
    else:
        await update.message.reply_text(message)
        return ConversationHandler.END

async def get_new_code(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """الحصول على رمز التحقق الجديد"""
    code = update.message.text
    user_id = update.effective_user.id
    
    manager = user_sessions[user_id]['manager']
    phone_code_hash = user_sessions[user_id]['phone_code_hash']
    
    success, message = await manager.confirm_phone_change(code, phone_code_hash)
    
    if success:
        await update.message.reply_text("تم تغيير رقم الهاتف بنجاح!")
    else:
        await update.message.reply_text(message)
    
    return ConversationHandler.END

# دوال النشر التلقائي
async def get_post_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """الحصول على نص النشر"""
    text = update.message.text
    user_id = update.effective_user.id
    
    user_sessions[user_id]['post_text'] = text
    await update.message.reply_text("أرسل الفترة الزمنية بين كل نشر (بالثواني):")
    return POST_INTERVAL

async def get_post_interval(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """الحصول على الفترة الزمنية"""
    try:
        interval = int(update.message.text)
        user_id = update.effective_user.id
        
        if interval < 1:
            await update.message.reply_text("يجب أن تكون الفترة الزمنية أكبر من 0 ثانية. أعد إدخال الرقم:")
            return POST_INTERVAL
        
        user_sessions[user_id]['post_interval'] = interval
        await update.message.reply_text("أرسل عدد المرات التي تريد نشر الرسالة فيها:")
        return POST_COUNT
    except ValueError:
        await update.message.reply_text("يرجى إدخال رقم صحيح. أعد إدخال الفترة الزمنية:")
        return POST_INTERVAL

async def get_post_count(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """الحصول على عدد مرات النشر"""
    try:
        count = int(update.message.text)
        user_id = update.effective_user.id
        
        if count < 1:
            await update.message.reply_text("يجب أن يكون العدد أكبر من 0. أعد إدخال الرقم:")
            return POST_COUNT
        
        user_sessions[user_id]['post_count'] = count
        await update.message.reply_text("أرسل رابط المجموعة أو المعرف (مثال: @group_username):")
        return POST_TARGET
    except ValueError:
        await update.message.reply_text("يرجى إدخال رقم صحيح. أعد إدخال عدد المرات:")
        return POST_COUNT

async def get_post_target(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """الحصول على الهدف للنشر"""
    target = update.message.text
    user_id = update.effective_user.id
    
    if 't.me/' in target:
        target = target.split('t.me/')[-1].split('/')[0]
    
    user_sessions[user_id]['post_target'] = target
    
    manager = user_sessions[user_id]['manager']
    text = user_sessions[user_id]['post_text']
    interval = user_sessions[user_id]['post_interval']
    count = user_sessions[user_id]['post_count']
    
    await update.message.reply_text(f"بدء النشر التلقائي...")
    
    success, message = await manager.auto_post_message(text, interval, count, target)
    await update.message.reply_text(message)
    
    return ConversationHandler.END

async def change_profile_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """تغيير صورة الملف الشخصي"""
    user_id = update.effective_user.id
    
    if update.message.photo:
        photo_file = await update.message.photo[-1].get_file()
        file_path = f"temp_photo_{user_id}.jpg"
        await photo_file.download_to_drive(file_path)
        
        manager = user_sessions[user_id]['manager']
        success, message = await manager.change_profile_photo(file_path)
        
        try:
            os.remove(file_path)
        except:
            pass
        
        await update.message.reply_text(message)
    else:
        await update.message.reply_text("يرجى إرسال صورة صالحة.")
    
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """إلغاء العملية"""
    await update.message.reply_text("تم إلغاء العملية.")
    return ConversationHandler.END

def main():
    """الدالة الرئيسية لتشغيل البوت"""
    application = Application.builder().token(BOT_TOKEN).build()
    
    conv_handler = ConversationHandler(
        entry_points=[MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message)],
        states={
            PHONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_phone)],
            CODE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_code)],
            NEW_PHONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_new_phone)],
            NEW_CODE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_new_code)],
            POST_TEXT: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_post_text)],
            POST_INTERVAL: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_post_interval)],
            POST_COUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_post_count)],
            POST_TARGET: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_post_target)],
            CHANGE_PHOTO: [MessageHandler(filters.PHOTO, change_profile_photo)],
        },
        fallbacks=[CommandHandler('cancel', cancel)],
    )
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(conv_handler)
    
    print("البوت يعمل...")
    application.run_polling()

if __name__ == '__main__':
    main()