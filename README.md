# 🎶 Athr Bot | بوت أثر

بوت ديسكورد مكتوب بـ Python لسيرفر **أثر**: ترحيب بكرت مخصص، وداع، رتب وأسماء تلقائية، رسائل Embed، رسائل خاصة، وردود تلقائية.

A Discord bot written in Python for the **Athr** server: custom welcome cards, goodbye embeds, automatic roles and nicknames, custom embeds, DMs, and auto replies.

---

## ✨ المميزات | Features

**تشتغل تلقائياً | Automatic**
- 🎴 **كرت ترحيب**: صورة العضو واسمه على ديزاين مخصص (يدعم العربي).
- 🏷️ **رتبة تلقائية** للعضو الجديد.
- ✏️ **تغيير الاسم تلقائياً** حسب صيغة تحددها (مثل `✦ Name`).
- 👋 **رسالة وداع** (Embed) بصورة العضو واسمه.
- 💬 **ردود تلقائية** على كلمات تحددها.

**بالأوامر | Slash commands (Admin only)**

| الأمر | الوظيفة |
|---|---|
| `/embed` | إرسال Embed مخصص (عنوان، محتوى، لون، صورة، فوتر) |
| `/dm` | إرسال رسالة خاصة لشخص معيّن |
| `/dm_boosters` | إرسال رسالة خاصة لكل داعمي السيرفر (Boosters) |
| `/autoreply add` | إضافة رد تلقائي (في الروم أو على الخاص) |
| `/autoreply remove` | حذف رد تلقائي |
| `/autoreply list` | عرض كل الردود التلقائية |

---

## 📁 الملفات | Project structure

```
.
├── bot.py             # كود البوت (ملف واحد)
├── template.png       # ديزاين كرت الترحيب (1774x887)
├── font.ttf           # خط Cairo Bold
├── requirements.txt   # المكتبات
└── autoreplies.json   # يتسوى تلقائياً عند إضافة أول رد
```

---

## 🚀 التشغيل | Setup

### 1) تجهيز البوت في Developer Portal
1. افتح [Discord Developer Portal](https://discord.com/developers/applications) وأنشئ تطبيق جديد.
2. من تبويب **Bot**: انسخ التوكن.
3. فعّل **Privileged Gateway Intents**:
   - ✅ Server Members Intent
   - ✅ Message Content Intent
4. من **OAuth2 → URL Generator**:
   - Scopes: `bot` و `applications.commands`
   - Permissions: `Manage Roles`, `Manage Nicknames`, `View Channels`, `Send Messages`, `Embed Links`, `Attach Files`
5. افتح الرابط وأضف البوت لسيرفرك.
6. في إعدادات السيرفر → Roles: **ارفع رتبة البوت فوق الرتبة التلقائية**.

### 2) الـ IDs
فعّل **Developer Mode** من إعدادات ديسكورد (Advanced)، وبعدها كليك يمين → Copy ID على: السيرفر، روم الترحيب، روم الوداع، والرتبة.

### 3) التنصيب
```bash
git clone https://github.com/<your-username>/<repo-name>.git
cd <repo-name>
python -m pip install -r requirements.txt
```

نزّل خط **Cairo** من Google Fonts، وسمّي ملف `Cairo-Bold.ttf` إلى `font.ttf`، وحطه جنب `bot.py` مع `template.png`.

### 4) الإعدادات
افتح `bot.py` وعدّل القيم في أول الملف:

```python
TOKEN = "PUT_YOUR_TOKEN_HERE"
GUILD_ID = 123456789012345678
WELCOME_CHANNEL_ID = 123456789012345678
GOODBYE_CHANNEL_ID = 123456789012345678
AUTO_ROLE_ID = 123456789012345678
NICK_FORMAT = "✦ {name}"
```

> ⚠️ **تحذير:** لا ترفع التوكن الحقيقي على GitHub أبداً. اترك `PUT_YOUR_TOKEN_HERE` في النسخة المرفوعة. لو اتسرّب التوكن، اعمل **Reset Token** فوراً من Developer Portal.

### 5) التشغيل
```bash
python bot.py
```
لما تظهر رسالة `Logged in as ...` يبقى البوت شغال.

---

## 🎨 تخصيص الكرت | Customizing the card

إحداثيات الكرت مضبوطة على ديزاين بحجم **1774×887**. لو غيّرت الديزاين عدّل هذه القيم في `bot.py`:

| المتغير | معناه |
|---|---|
| `AVATAR_CENTER` / `AVATAR_RADIUS` | مكان وحجم صورة العضو |
| `NAME_CENTER` / `NAME_MAX_WIDTH` | مكان الاسم وأقصى عرض له |
| `OLD_NAME_BOX` | المنطقة اللي تتغطى لإخفاء الاسم القديم (`None` لو التمبلت نضيف) |

---

## ❓ ملاحظات | Notes

- البوت **لا يكدر** يغير اسم صاحب السيرفر أو من رتبته أعلى من رتبة البوت.
- الرسائل الخاصة تفشل إذا العضو قافل الخاص، والبوت يخبرك بعدد اللي فشلت معهم.
- لتشغيله 24/7 استخدم استضافة (VPS, Railway, Render...).

---

صُنع لسيرفر **أثر | Athr** 🤍
