import asyncio
import io
import json
import os

import arabic_reshaper
import discord
from bidi.algorithm import get_display
from discord import app_commands
from PIL import Image, ImageDraw, ImageFont

# ============================ الإعدادات ============================
TOKEN = ""
GUILD_ID = 1544037049492049992             # ID السيرفر (عشان الأوامر تظهر فوراً)
WELCOME_CHANNEL_ID = 1559259010547581030   # روم الترحيب
GOODBYE_CHANNEL_ID = 1555921490870796369  # روم الوداع
AUTO_ROLE_ID = 1556070092515582102         # الرتبة اللي ياخذها العضو الجديد

NICK_FORMAT = "✦ {name}"                  # شكل الاسم الجديد، مثال: "✦ يوسف"
EMBED_COLOR = 0xC9965A                    # اللون الدهبي

# نص الرسالة الافتراضي لداعمين السيرفر (تقدر تعدله وقت الإرسال كمان)
BOOSTER_MESSAGE = (
    "هلا فيك! 🤍\n"
    "شكراً لدعمك سيرفر أثر، وجودك يفرق معنا."
)

GOODBYE_TEXT = "فارقنا {name}، نتمنى له التوفيق 🤍"

AUTOREPLY_FILE = "autoreplies.json"       # بيتسوى لحاله

TEMPLATE_PATH = "template.png"            # الديزاين (1774x887)
FONT_PATH = "font.ttf"                    # Cairo-Bold.ttf بعد تغيير اسمه

AVATAR_CENTER = (428, 447)
AVATAR_RADIUS = 270
RING_COLOR = (201, 150, 90)
RING_WIDTH = 8

NAME_CENTER = (1240, 675)
NAME_MAX_WIDTH = 700
NAME_MAX_SIZE = 90
NAME_MIN_SIZE = 30
NAME_COLOR = (255, 255, 255)

OLD_NAME_BOX = (880, 610, 1600, 760)      # None لو التمبلت نضيف من الاسم
# ===================================================================


# ------------------------- كرت الترحيب -------------------------
def prep_text(text: str) -> str:
    return get_display(arabic_reshaper.reshape(text))


def circle_mask(size: int) -> Image.Image:
    scale = 4
    big = Image.new("L", (size * scale, size * scale), 0)
    ImageDraw.Draw(big).ellipse((0, 0, size * scale - 1, size * scale - 1), fill=255)
    return big.resize((size, size), Image.LANCZOS)


def build_card(name: str, avatar_bytes: bytes) -> io.BytesIO:
    card = Image.open(TEMPLATE_PATH).convert("RGBA")
    draw = ImageDraw.Draw(card)

    if OLD_NAME_BOX:
        x1, y1, x2, y2 = OLD_NAME_BOX
        bg = card.getpixel((NAME_CENTER[0], min(y2 + 30, card.height - 1)))
        draw.rectangle(OLD_NAME_BOX, fill=bg)

    d = AVATAR_RADIUS * 2
    avatar = Image.open(io.BytesIO(avatar_bytes)).convert("RGBA").resize((d, d), Image.LANCZOS)
    cx, cy = AVATAR_CENTER
    ring_r = AVATAR_RADIUS + RING_WIDTH
    draw.ellipse((cx - ring_r, cy - ring_r, cx + ring_r, cy + ring_r), fill=RING_COLOR)
    card.paste(avatar, (cx - AVATAR_RADIUS, cy - AVATAR_RADIUS), circle_mask(d))

    text = prep_text(name)
    size = NAME_MAX_SIZE
    while True:
        font = ImageFont.truetype(FONT_PATH, size, layout_engine=ImageFont.Layout.BASIC)
        width = draw.textlength(text, font=font)
        if width <= NAME_MAX_WIDTH or size <= NAME_MIN_SIZE:
            break
        size -= 2
    draw.text(NAME_CENTER, text, font=font, fill=NAME_COLOR, anchor="mm")

    out = io.BytesIO()
    card.convert("RGB").save(out, format="PNG")
    out.seek(0)
    return out


# ------------------------- الردود التلقائية -------------------------
def load_replies() -> dict:
    if os.path.exists(AUTOREPLY_FILE):
        with open(AUTOREPLY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_replies() -> None:
    with open(AUTOREPLY_FILE, "w", encoding="utf-8") as f:
        json.dump(replies, f, ensure_ascii=False, indent=2)


replies = load_replies()  # {"كلمة": {"reply": "...", "dm": false}}


# ------------------------- البوت -------------------------
intents = discord.Intents.default()
intents.members = True          # Server Members Intent
intents.message_content = True  # Message Content Intent (للردود التلقائية)


class AtharBot(discord.Client):
    def __init__(self):
        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(self)

    async def setup_hook(self):
        guild = discord.Object(id=GUILD_ID)
        self.tree.copy_global_to(guild=guild)
        await self.tree.sync(guild=guild)


client = AtharBot()


@client.event
async def on_ready():
    print(f"Logged in as {client.user}")


# ---- دخول عضو: رتبة + اسم + كرت ترحيب ----
@client.event
async def on_member_join(member: discord.Member):
    guild = member.guild

    if not member.bot:
        role = guild.get_role(AUTO_ROLE_ID)
        if role:
            try:
                await member.add_roles(role, reason="Auto role")
            except discord.Forbidden:
                print("ما أقدر أعطي الرتبة: ارفع رتبة البوت فوق الرتبة المطلوبة")

        try:
            await member.edit(nick=NICK_FORMAT.format(name=member.display_name)[:32],
                              reason="Auto nickname")
        except discord.Forbidden:
            print(f"ما أقدر أغير اسم {member}: صلاحية Manage Nicknames أو ترتيب الرتب")

    channel = guild.get_channel(WELCOME_CHANNEL_ID)
    if channel is None:
        return
    avatar_bytes = await member.display_avatar.replace(format="png", size=512).read()
    buffer = await asyncio.to_thread(build_card, member.display_name, avatar_bytes)
    await channel.send(
        content=f"{member.mention} حياك الله في أثر 🎶",
        file=discord.File(buffer, filename="welcome.png"),
    )


# ---- خروج عضو: Embed وداع بصورته ----
@client.event
async def on_member_remove(member: discord.Member):
    channel = member.guild.get_channel(GOODBYE_CHANNEL_ID)
    if channel is None:
        return
    embed = discord.Embed(
        title="وداعاً 👋",
        description=GOODBYE_TEXT.format(name=f"**{member.display_name}**"),
        color=EMBED_COLOR,
    )
    embed.set_thumbnail(url=member.display_avatar.url)
    embed.set_footer(text=f"عدد الأعضاء الآن: {member.guild.member_count}")
    await channel.send(embed=embed)


# ---- الردود التلقائية ----
@client.event
async def on_message(message: discord.Message):
    if message.author.bot or message.guild is None:
        return
    text = message.content.lower()
    for keyword, data in replies.items():
        if keyword in text:
            if data.get("dm"):
                try:
                    await message.author.send(data["reply"])
                except discord.Forbidden:
                    pass
            else:
                await message.reply(data["reply"], mention_author=False)
            break


# ====================== أمر /embed ======================
class EmbedModal(discord.ui.Modal, title="سوّي Embed"):
    title_in = discord.ui.TextInput(label="العنوان", required=False, max_length=256)
    desc_in = discord.ui.TextInput(label="المحتوى", style=discord.TextStyle.paragraph,
                                   max_length=4000)
    color_in = discord.ui.TextInput(label="اللون (مثال: #c9965a)", required=False,
                                    default="#c9965a", max_length=7)
    image_in = discord.ui.TextInput(label="رابط صورة (اختياري)", required=False)
    footer_in = discord.ui.TextInput(label="الفوتر (اختياري)", required=False, max_length=200)

    def __init__(self, channel: discord.abc.Messageable):
        super().__init__()
        self.channel = channel

    async def on_submit(self, interaction: discord.Interaction):
        try:
            color = int(self.color_in.value.strip().lstrip("#"), 16)
        except ValueError:
            color = EMBED_COLOR

        embed = discord.Embed(
            title=self.title_in.value or None,
            description=self.desc_in.value,
            color=color,
        )
        if self.image_in.value.startswith("http"):
            embed.set_image(url=self.image_in.value)
        if self.footer_in.value:
            embed.set_footer(text=self.footer_in.value)

        await self.channel.send(embed=embed)
        await interaction.response.send_message("تم الإرسال ✅", ephemeral=True)


@client.tree.command(name="embed", description="إرسال Embed مخصص")
@app_commands.describe(channel="الروم اللي يتسند فيه الـ Embed (الافتراضي: الروم الحالي)")
@app_commands.default_permissions(administrator=True)
@app_commands.guild_only()
async def embed_cmd(interaction: discord.Interaction, channel: discord.TextChannel = None):
    await interaction.response.send_modal(EmbedModal(channel or interaction.channel))


# ====================== أمر /dm (رسالة على الخاص لشخص) ======================
class DMModal(discord.ui.Modal, title="رسالة على الخاص"):
    text_in = discord.ui.TextInput(label="نص الرسالة", style=discord.TextStyle.paragraph,
                                   max_length=2000)

    def __init__(self, target: discord.Member):
        super().__init__()
        self.target = target

    async def on_submit(self, interaction: discord.Interaction):
        try:
            await self.target.send(self.text_in.value)
        except (discord.Forbidden, discord.HTTPException):
            await interaction.response.send_message(
                "ما قدرت أرسل له، الخاص مقفول عنده ❌", ephemeral=True)
            return
        await interaction.response.send_message(
            f"وصلت الرسالة لـ {self.target.display_name} ✅", ephemeral=True)


@client.tree.command(name="dm", description="البوت يرسل رسالة على الخاص لشخص")
@app_commands.describe(member="الشخص اللي توصله الرسالة")
@app_commands.default_permissions(administrator=True)
@app_commands.guild_only()
async def dm_cmd(interaction: discord.Interaction, member: discord.Member):
    await interaction.response.send_modal(DMModal(member))


# ====================== رسالة لداعمين السيرفر ======================
class BoosterModal(discord.ui.Modal, title="رسالة لداعمين السيرفر"):
    msg = discord.ui.TextInput(label="نص الرسالة", style=discord.TextStyle.paragraph,
                               default=BOOSTER_MESSAGE, max_length=2000)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        guild = interaction.guild
        await guild.chunk()
        ok = failed = 0
        for member in guild.premium_subscribers:
            try:
                await member.send(self.msg.value)
                ok += 1
            except (discord.Forbidden, discord.HTTPException):
                failed += 1  # الخاص مقفول عنده
            await asyncio.sleep(1.5)  # عشان ما ناخذ rate limit
        await interaction.followup.send(
            f"وصلت لـ {ok} داعم ✅ | فشلت مع {failed} (الخاص مقفول)", ephemeral=True
        )


@client.tree.command(name="dm_boosters", description="إرسال رسالة خاصة لكل داعمي السيرفر")
@app_commands.default_permissions(administrator=True)
@app_commands.guild_only()
async def dm_boosters(interaction: discord.Interaction):
    await interaction.response.send_modal(BoosterModal())


# ====================== الردود التلقائية: الأوامر ======================
autoreply = app_commands.Group(
    name="autoreply",
    description="إدارة الردود التلقائية",
    guild_only=True,
    default_permissions=discord.Permissions(administrator=True),
)


@autoreply.command(name="add", description="إضافة رد تلقائي")
@app_commands.describe(keyword="الكلمة اللي البوت يرد عليها",
                       reply="نص الرد",
                       dm="يرسل الرد على الخاص بدل الروم؟")
async def ar_add(interaction: discord.Interaction, keyword: str, reply: str, dm: bool = False):
    replies[keyword.lower().strip()] = {"reply": reply, "dm": dm}
    save_replies()
    where = "الخاص" if dm else "نفس الروم"
    await interaction.response.send_message(f"تمت الإضافة ✅ ({where})", ephemeral=True)


@autoreply.command(name="remove", description="حذف رد تلقائي")
async def ar_remove(interaction: discord.Interaction, keyword: str):
    if replies.pop(keyword.lower().strip(), None) is None:
        await interaction.response.send_message("ما لقيت هالكلمة.", ephemeral=True)
        return
    save_replies()
    await interaction.response.send_message("تم الحذف ✅", ephemeral=True)


@autoreply.command(name="list", description="عرض كل الردود التلقائية")
async def ar_list(interaction: discord.Interaction):
    if not replies:
        await interaction.response.send_message("ما فيه ردود حالياً.", ephemeral=True)
        return
    lines = [f"• `{k}` → {v['reply'][:60]} {'(خاص)' if v['dm'] else ''}"
             for k, v in replies.items()]
    await interaction.response.send_message("\n".join(lines)[:1900], ephemeral=True)


client.tree.add_command(autoreply)

client.run(TOKEN)
