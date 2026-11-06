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

# ============================ الألعاب ============================
import random

SCORES_FILE = "scores.json"   # بيتسوى تلقائياً مع أول نتيجة
MAX_PLAYERS = 20
MIN_CHAIRS = 3
POINTS_ROULETTE = 5
POINTS_CHAIRS = 5
POINTS_XO = 3
POINTS_DRAW = 1


def load_scores() -> dict:
    if os.path.exists(SCORES_FILE):
        try:
            with open(SCORES_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                return {k: v for k, v in data.items() if isinstance(v, dict)}
        except (json.JSONDecodeError, OSError):
            pass
    return {}


scores = load_scores()


def save_scores() -> None:
    with open(SCORES_FILE, "w", encoding="utf-8") as f:
        json.dump(scores, f, ensure_ascii=False, indent=2)


def record_result(user, points: int, win: bool = False) -> None:
    key = str(user.id)
    data = scores.setdefault(key, {"name": str(user), "points": 0, "wins": 0, "games": 0})
    data["name"] = str(user)
    data["points"] = int(data.get("points", 0)) + points
    data["wins"] = int(data.get("wins", 0)) + (1 if win else 0)
    data["games"] = int(data.get("games", 0)) + 1
    save_scores()


active_games: dict = {}   # channel_id -> جلسة اللعبة


def is_admin(interaction: discord.Interaction) -> bool:
    perms = getattr(interaction.user, "guild_permissions", None)
    return bool(perms and perms.administrator)


def disable_view(view: discord.ui.View) -> None:
    for child in view.children:
        if hasattr(child, "disabled"):
            child.disabled = True


# ------------------------- الروليت -------------------------
class RouletteSession:
    def __init__(self, host: discord.Member, channel_id: int):
        self.host = host
        self.channel_id = channel_id
        self.players: list = []
        self.eliminated: list = []
        self.current = None
        self.message = None
        self.phase = "join"          # join | spinning | pick | spin | done
        self.pick_event = asyncio.Event()
        self.pick_task = None

    def embed(self, status: str = None) -> discord.Embed:
        embed = discord.Embed(title="🎡 روليت أثر", color=EMBED_COLOR)
        if self.players:
            lines = []
            for i, p in enumerate(self.players, 1):
                mark = "🎯 " if self.current and p.id == self.current.id else ""
                lines.append(f"{i}. {mark}{p.mention}")
            desc = "\n".join(lines)
        else:
            desc = "لسه محدش انضم."
        if self.eliminated:
            desc += "\n\n**خرجوا:** " + "، ".join(p.display_name for p in self.eliminated)
        embed.description = desc
        if status:
            embed.add_field(name="الحالة", value=status, inline=False)
        embed.set_footer(text=f"اللاعبين: {len(self.players)} | صاحب الجلسة: {self.host.display_name}")
        return embed

    def result_embed(self, winner, last_out) -> discord.Embed:
        embed = discord.Embed(title="🏆 نهاية الروليت", color=EMBED_COLOR)
        if winner:
            embed.description = (
                f"الفائز: {winner.mention} 🎉\n"
                f"آخر من خرج: {last_out.display_name}\n"
                f"+{POINTS_ROULETTE} نقطة"
            )
        else:
            embed.description = "اللعبة انتهت بدون فائز."
        return embed

    def start_pick_timer(self) -> None:
        self.pick_event.clear()
        if self.pick_task and not self.pick_task.done():
            self.pick_task.cancel()

        async def runner():
            try:
                await asyncio.wait_for(self.pick_event.wait(), 30)
            except asyncio.TimeoutError:
                await self.timeout_pick()

        self.pick_task = asyncio.create_task(runner())

    async def timeout_pick(self) -> None:
        if self.phase != "pick" or self.current is None:
            return
        candidates = [p for p in self.players if p.id != self.current.id]
        if not candidates:
            return
        await self.eliminate(random.choice(candidates), timed_out=True)

    async def eliminate(self, target, timed_out: bool = False) -> None:
        if target not in self.players:
            return
        self.pick_event.set()
        self.eliminated.append(target)
        self.players = [p for p in self.players if p.id != target.id]
        self.current = None

        if len(self.players) <= 1:
            winner = self.players[0] if self.players else None
            self.phase = "done"
            view = RouletteView(self)
            disable_view(view)
            if self.message:
                try:
                    await self.message.edit(embed=self.result_embed(winner, target), view=view)
                except discord.HTTPException:
                    pass
            self.finish(winner)
            return

        self.phase = "spin"
        view = RouletteView(self)
        status = f"❌ خرج {target.display_name}"
        if timed_out:
            status += " (انتهى وقته)"
        if self.message:
            try:
                await self.message.edit(embed=self.embed(status), view=view)
            except discord.HTTPException:
                pass

    def finish(self, winner) -> None:
        self.phase = "done"
        for p in self.players:
            if winner and p.id == winner.id:
                record_result(p, POINTS_ROULETTE, win=True)
            else:
                record_result(p, 0)
        for p in self.eliminated:
            record_result(p, 0)
        active_games.pop(self.channel_id, None)

    async def cancel(self) -> None:
        self.phase = "done"
        self.pick_event.set()
        if self.pick_task and not self.pick_task.done():
            self.pick_task.cancel()
        view = RouletteView(self)
        disable_view(view)
        if self.message:
            try:
                await self.message.edit(
                    embed=discord.Embed(title="🎡 روليت أثر", color=EMBED_COLOR,
                                        description="تم إلغاء الجلسة."),
                    view=view,
                )
            except discord.HTTPException:
                pass
        active_games.pop(self.channel_id, None)


class RouletteView(discord.ui.View):
    def __init__(self, session: RouletteSession):
        super().__init__(timeout=None)
        self.session = session
        self.join_button = discord.ui.Button(label="انضممت ✅", style=discord.ButtonStyle.success, emoji="🎡")
        self.join_button.callback = self.on_join
        self.spin_button = discord.ui.Button(label="لف العجلة 🎯", style=discord.ButtonStyle.primary, emoji="🎰")
        self.spin_button.callback = self.on_spin
        self.add_item(self.join_button)
        self.add_item(self.spin_button)
        self.refresh()

    def refresh(self):
        can_join = self.session.phase == "join"
        self.join_button.disabled = not can_join
        self.spin_button.disabled = self.session.phase not in ("join", "spin")

    async def on_join(self, interaction: discord.Interaction):
        s = self.session
        if s.phase != "join":
            await interaction.response.send_message("الانضمام خلص في الجلسة دي.", ephemeral=True)
            return
        if interaction.user.bot:
            await interaction.response.send_message("البوتات ما تلعبش 🤖", ephemeral=True)
            return
        if any(p.id == interaction.user.id for p in s.players):
            await interaction.response.send_message("أنت منضم بالفعل ✅", ephemeral=True)
            return
        if len(s.players) >= MAX_PLAYERS:
            await interaction.response.send_message(f"الحد الأقصى {MAX_PLAYERS} لاعب.", ephemeral=True)
            return
        s.players.append(interaction.user)
        self.refresh()
        await interaction.response.edit_message(
            embed=s.embed("انضممت! استنى صاحب الجلسة يلف."), view=self)

    async def on_spin(self, interaction: discord.Interaction):
        s = self.session
        if not is_admin(interaction) and interaction.user.id != s.host.id:
            await interaction.response.send_message("صاحب الجلسة أو الأدمن فقط يقدر يلف.", ephemeral=True)
            return
        if s.phase not in ("join", "spin"):
            await interaction.response.send_message("اللف مش متاح دلوقتي.", ephemeral=True)
            return
        if len(s.players) < 2:
            await interaction.response.send_message("محتاج لاعبين على الأقل 2.", ephemeral=True)
            return

        await interaction.response.defer()
        s.phase = "spinning"
        self.refresh()
        if s.message:
            try:
                await s.message.edit(embed=s.embed("العجلة بتلف… 🎲"), view=self)
            except discord.HTTPException:
                pass
        for _ in range(8):
            name = random.choice(s.players).display_name
            if s.message:
                try:
                    await s.message.edit(embed=s.embed(f"بتلف… {name}"))
                except discord.HTTPException:
                    pass
            await asyncio.sleep(0.22)

        chosen = random.choice(s.players)
        s.current = chosen
        s.phase = "pick"
        if s.message:
            try:
                await s.message.edit(
                    embed=s.embed(f"🎯 العجلة وقفت على {chosen.display_name}! اختار مين يخرج."),
                    view=RoulettePickView(s),
                )
            except discord.HTTPException:
                pass
        s.start_pick_timer()


class RoulettePickView(discord.ui.View):
    def __init__(self, session: RouletteSession):
        super().__init__(timeout=None)
        self.session = session
        for p in session.players:
            if session.current and p.id == session.current.id:
                continue
            btn = discord.ui.Button(label=p.display_name[:80], style=discord.ButtonStyle.secondary, emoji="👈")
            btn.callback = self.make_callback(p)
            self.add_item(btn)

    def make_callback(self, target):
        async def callback(interaction: discord.Interaction):
            s = self.session
            if s.phase != "pick" or s.current is None:
                await interaction.response.send_message("الاختيار خلص.", ephemeral=True)
                return
            if interaction.user.id != s.current.id:
                await interaction.response.send_message("اللي وقفت عليه العجلة هو اللي يختار.", ephemeral=True)
                return
            await interaction.response.defer()
            await s.eliminate(target)

        return callback


# ------------------------- الكراسي -------------------------
class ChairsSession:
    def __init__(self, host: discord.Member, channel_id: int):
        self.host = host
        self.channel_id = channel_id
        self.players: list = []
        self.eliminated: list = []
        self.message = None
        self.phase = "join"          # join | playing | done
        self.round = 0

    def embed(self, status: str = None, chairs: int = None, out: str = None) -> discord.Embed:
        embed = discord.Embed(title="🪑 لعبة الكراسي", color=EMBED_COLOR)
        if chairs is not None:
            embed.description = "🪑 " * chairs + f"\nعدد الكراسي: {chairs}"
        if self.players:
            players = "\n".join(f"• {p.mention}" for p in self.players)
            embed.add_field(name="اللاعبين", value=players, inline=False)
        else:
            embed.add_field(name="اللاعبين", value="لسه محدش انضم.", inline=False)
        if out:
            embed.add_field(name="خرج", value=out, inline=False)
        if status:
            embed.add_field(name="الحالة", value=status, inline=False)
        embed.set_footer(text=f"اللاعبين: {len(self.players)} | صاحب الجلسة: {self.host.display_name}")
        return embed

    async def run(self):
        if len(self.players) < MIN_CHAIRS:
            return
        self.phase = "playing"
        view = ChairsView(self)
        disable_view(view)
        if self.message:
            try:
                await self.message.edit(embed=self.embed("بدأت اللعبة! 🪑"), view=view)
            except discord.HTTPException:
                pass

        while len(self.players) > 1 and self.phase == "playing":
            self.round += 1
            chairs = len(self.players) - 1
            if self.message:
                try:
                    await self.message.edit(
                        embed=self.embed(f"الجولة {self.round} — كرسي واحد بيتشال…", chairs=chairs))
                except discord.HTTPException:
                    pass
            await asyncio.sleep(2)
            if self.phase != "playing":
                return
            loser = random.choice(self.players)
            self.players = [p for p in self.players if p.id != loser.id]
            self.eliminated.append(loser)
            if self.message:
                try:
                    await self.message.edit(
                        embed=self.embed(f"❌ {loser.display_name} ما لقاش كرسي وخرج!",
                                         chairs=chairs, out=loser.display_name))
                except discord.HTTPException:
                    pass
            await asyncio.sleep(2)

        if self.phase != "playing":
            return
        winner = self.players[0] if self.players else None
        if self.message:
            try:
                await self.message.edit(embed=self.result_embed(winner), view=view)
            except discord.HTTPException:
                pass
        self.finish(winner)

    def result_embed(self, winner) -> discord.Embed:
        embed = discord.Embed(title="🏆 نهاية الكراسي", color=EMBED_COLOR)
        if winner:
            embed.description = f"الفائز: {winner.mention} 🎉\n+{POINTS_CHAIRS} نقطة"
        else:
            embed.description = "اللعبة انتهت بدون فائز."
        return embed

    def finish(self, winner) -> None:
        self.phase = "done"
        for p in self.players:
            if winner and p.id == winner.id:
                record_result(p, POINTS_CHAIRS, win=True)
            else:
                record_result(p, 0)
        for p in self.eliminated:
            record_result(p, 0)
        active_games.pop(self.channel_id, None)

    async def cancel(self) -> None:
        self.phase = "done"
        view = ChairsView(self)
        disable_view(view)
        if self.message:
            try:
                await self.message.edit(
                    embed=discord.Embed(title="🪑 لعبة الكراسي", color=EMBED_COLOR,
                                        description="تم إلغاء الجلسة."),
                    view=view,
                )
            except discord.HTTPException:
                pass
        active_games.pop(self.channel_id, None)


class ChairsView(discord.ui.View):
    def __init__(self, session: ChairsSession):
        super().__init__(timeout=None)
        self.session = session
        self.join_button = discord.ui.Button(label="انضممت 🪑", style=discord.ButtonStyle.success, emoji="🪑")
        self.join_button.callback = self.on_join
        self.start_button = discord.ui.Button(label="ابدأ الكراسي ▶️", style=discord.ButtonStyle.primary, emoji="🎮")
        self.start_button.callback = self.on_start
        self.add_item(self.join_button)
        self.add_item(self.start_button)
        self.refresh()

    def refresh(self):
        can_join = self.session.phase == "join"
        self.join_button.disabled = not can_join
        self.start_button.disabled = not can_join

    async def on_join(self, interaction: discord.Interaction):
        s = self.session
        if s.phase != "join":
            await interaction.response.send_message("الانضمام خلص في الجلسة دي.", ephemeral=True)
            return
        if interaction.user.bot:
            await interaction.response.send_message("البوتات ما تلعبش 🤖", ephemeral=True)
            return
        if any(p.id == interaction.user.id for p in s.players):
            await interaction.response.send_message("أنت منضم بالفعل ✅", ephemeral=True)
            return
        if len(s.players) >= MAX_PLAYERS:
            await interaction.response.send_message(f"الحد الأقصى {MAX_PLAYERS} لاعب.", ephemeral=True)
            return
        s.players.append(interaction.user)
        self.refresh()
        await interaction.response.edit_message(embed=s.embed("انضممت! مستنيين نبدأ."), view=self)

    async def on_start(self, interaction: discord.Interaction):
        s = self.session
        if not is_admin(interaction) and interaction.user.id != s.host.id:
            await interaction.response.send_message("صاحب الجلسة أو الأدمن فقط يبدأ.", ephemeral=True)
            return
        if s.phase != "join":
            await interaction.response.send_message("اللعبة بدأت بالفعل.", ephemeral=True)
            return
        if len(s.players) < MIN_CHAIRS:
            await interaction.response.send_message(f"محتاج {MIN_CHAIRS} لاعبين على الأقل.", ephemeral=True)
            return
        await interaction.response.defer()
        await s.run()


# ------------------------- X-O -------------------------
XO_LINES = [(0, 1, 2), (3, 4, 5), (6, 7, 8),
            (0, 3, 6), (1, 4, 7), (2, 5, 8),
            (0, 4, 8), (2, 4, 6)]


class XOGame:
    def __init__(self, x_player, o_player, channel_id: int):
        self.x_player = x_player
        self.o_player = o_player
        self.channel_id = channel_id
        self.board = [None] * 9
        self.turn = "X"
        self.finished = False

    def player_of(self, mark):
        return self.x_player if mark == "X" else self.o_player

    def embed(self, status: str = None) -> discord.Embed:
        embed = discord.Embed(title="❌⭕ X-O", color=EMBED_COLOR)
        if status:
            embed.description = status
        embed.add_field(name="X", value=self.x_player.mention, inline=True)
        embed.add_field(name="O", value=self.o_player.mention, inline=True)
        if not self.finished:
            embed.set_footer(text=f"دور: {self.player_of(self.turn).display_name}")
        return embed

    def check_winner(self):
        for a, b, c in XO_LINES:
            if self.board[a] and self.board[a] == self.board[b] == self.board[c]:
                return self.board[a]
        return None

    async def play(self, interaction: discord.Interaction, index: int, view: "XOBoardView"):
        if self.finished:
            await interaction.response.send_message("اللعبة انتهت.", ephemeral=True)
            return
        expected = self.player_of(self.turn)
        if interaction.user.id != expected.id:
            await interaction.response.send_message(f"دور {expected.display_name} الآن.", ephemeral=True)
            return
        if self.board[index] is not None:
            await interaction.response.send_message("الخانة مشغولة.", ephemeral=True)
            return

        self.board[index] = self.turn
        view.buttons[index].label = "❌" if self.turn == "X" else "⭕"

        winner = self.check_winner()
        if winner:
            self.finished = True
            disable_view(view)
            record_result(self.player_of(winner), POINTS_XO, win=True)
            record_result(self.player_of("O" if winner == "X" else "X"), 0)
            active_games.pop(self.channel_id, None)
            embed = discord.Embed(
                title="🏆 نهاية X-O", color=EMBED_COLOR,
                description=f"الفائز: {self.player_of(winner).mention} 🎉\n+{POINTS_XO} نقطة")
            await interaction.response.edit_message(embed=embed, view=view)
            return

        if all(self.board):
            self.finished = True
            disable_view(view)
            record_result(self.x_player, POINTS_DRAW)
            record_result(self.o_player, POINTS_DRAW)
            active_games.pop(self.channel_id, None)
            embed = discord.Embed(
                title="🤝 تعادل!", color=EMBED_COLOR,
                description=f"محدش كسب… +{POINTS_DRAW} نقطة لكل لاعب.")
            await interaction.response.edit_message(embed=embed, view=view)
            return

        self.turn = "O" if self.turn == "X" else "X"
        await interaction.response.edit_message(embed=self.embed(), view=view)


class XOBoardView(discord.ui.View):
    def __init__(self, game: XOGame):
        super().__init__(timeout=300)
        self.game = game
        self.buttons = []
        self.message = None
        for row in range(3):
            for col in range(3):
                index = row * 3 + col
                btn = discord.ui.Button(label="⬜", style=discord.ButtonStyle.secondary, row=row)
                btn.callback = self.make_callback(index)
                self.buttons.append(btn)
                self.add_item(btn)

    def make_callback(self, index: int):
        async def callback(interaction: discord.Interaction):
            await self.game.play(interaction, index, self)

        return callback

    async def on_timeout(self):
        if self.game.finished:
            return
        self.game.finished = True
        disable_view(self)
        active_games.pop(self.game.channel_id, None)
        if self.message:
            try:
                await self.message.edit(
                    embed=discord.Embed(title="⌛ انتهى الوقت", color=EMBED_COLOR,
                                        description="اللعبة اتلغت بسبب عدم اللعب."),
                    view=self)
            except discord.HTTPException:
                pass


class XOAcceptView(discord.ui.View):
    def __init__(self, challenger, opponent):
        super().__init__(timeout=180)
        self.challenger = challenger
        self.opponent = opponent
        self.accept_button = discord.ui.Button(label="أقبل التحدي ✅", style=discord.ButtonStyle.success, emoji="❌")
        self.accept_button.callback = self.on_accept
        self.decline_button = discord.ui.Button(label="رفض", style=discord.ButtonStyle.danger)
        self.decline_button.callback = self.on_decline
        self.add_item(self.accept_button)
        self.add_item(self.decline_button)

    async def on_accept(self, interaction: discord.Interaction):
        if interaction.user.id != self.opponent.id:
            await interaction.response.send_message("صاحب التحدي فقط يقدر يقبل.", ephemeral=True)
            return
        if interaction.channel_id in active_games:
            await interaction.response.send_message("فيه لعبة شغالة في الروم بالفعل.", ephemeral=True)
            return
        game = XOGame(self.challenger, self.opponent, interaction.channel_id)
        board_view = XOBoardView(game)
        board_view.message = interaction.message
        await interaction.response.edit_message(
            embed=game.embed("دور X ❌ ابدأ!"), view=board_view)
        active_games[interaction.channel_id] = game

    async def on_decline(self, interaction: discord.Interaction):
        if interaction.user.id != self.opponent.id:
            await interaction.response.send_message("صاحب التحدي فقط يقدر يرفض.", ephemeral=True)
            return
        await interaction.response.edit_message(
            embed=discord.Embed(title="❌⭕ X-O", color=EMBED_COLOR,
                                description=f"{self.opponent.display_name} رفض التحدي."),
            view=None)


# ------------------------- أوامر الألعاب -------------------------
roulette_group = app_commands.Group(
    name="roulette",
    description="لعبة الروليت 🎡",
    guild_only=True,
    default_permissions=discord.Permissions(administrator=True),
)


@roulette_group.command(name="start", description="بدء جلسة روليت جديدة")
async def roulette_start(interaction: discord.Interaction):
    if not is_admin(interaction):
        await interaction.response.send_message("اللعبة دي للأدمن فقط.", ephemeral=True)
        return
    if interaction.channel_id in active_games:
        await interaction.response.send_message("فيه لعبة شغالة في الروم بالفعل.", ephemeral=True)
        return
    session = RouletteSession(interaction.user, interaction.channel_id)
    view = RouletteView(session)
    await interaction.response.send_message(
        embed=session.embed("دوس «انضممت» وبعدها صاحب الجلسة يلف 🎡"), view=view)
    session.message = await interaction.original_response()
    active_games[interaction.channel_id] = session


@roulette_group.command(name="stop", description="إلغاء جلسة الروليت")
async def roulette_stop(interaction: discord.Interaction):
    if not is_admin(interaction):
        await interaction.response.send_message("اللعبة دي للأدمن فقط.", ephemeral=True)
        return
    session = active_games.get(interaction.channel_id)
    if not isinstance(session, RouletteSession):
        await interaction.response.send_message("ما فيه جلسة روليت شغالة.", ephemeral=True)
        return
    await session.cancel()
    await interaction.response.send_message("تم إلغاء الجلسة ✅", ephemeral=True)


chairs_group = app_commands.Group(
    name="chairs",
    description="لعبة الكراسي 🪑",
    guild_only=True,
    default_permissions=discord.Permissions(administrator=True),
)


@chairs_group.command(name="start", description="بدء لعبة الكراسي")
async def chairs_start(interaction: discord.Interaction):
    if not is_admin(interaction):
        await interaction.response.send_message("اللعبة دي للأدمن فقط.", ephemeral=True)
        return
    if interaction.channel_id in active_games:
        await interaction.response.send_message("فيه لعبة شغالة في الروم بالفعل.", ephemeral=True)
        return
    session = ChairsSession(interaction.user, interaction.channel_id)
    view = ChairsView(session)
    await interaction.response.send_message(
        embed=session.embed("دوس «انضممت» وبعدها ابدأ 🪑"), view=view)
    session.message = await interaction.original_response()
    active_games[interaction.channel_id] = session


@chairs_group.command(name="stop", description="إلغاء لعبة الكراسي")
async def chairs_stop(interaction: discord.Interaction):
    if not is_admin(interaction):
        await interaction.response.send_message("اللعبة دي للأدمن فقط.", ephemeral=True)
        return
    session = active_games.get(interaction.channel_id)
    if not isinstance(session, ChairsSession):
        await interaction.response.send_message("ما فيه لعبة كراسي شغالة.", ephemeral=True)
        return
    await session.cancel()
    await interaction.response.send_message("تم إلغاء الجلسة ✅", ephemeral=True)


@client.tree.command(name="xo", description="تحدي لاعب في X-O")
@app_commands.describe(opponent="اللاعب اللي هتحداه")
@app_commands.guild_only()
async def xo_cmd(interaction: discord.Interaction, opponent: discord.Member):
    if opponent.bot:
        await interaction.response.send_message("البوتات ما تلعبش 🤖", ephemeral=True)
        return
    if opponent.id == interaction.user.id:
        await interaction.response.send_message("تحد نفسك؟ 😄", ephemeral=True)
        return
    if interaction.channel_id in active_games:
        await interaction.response.send_message("فيه لعبة شغالة في الروم بالفعل.", ephemeral=True)
        return
    view = XOAcceptView(interaction.user, opponent)
    embed = discord.Embed(
        title="❌⭕ X-O", color=EMBED_COLOR,
        description=f"{interaction.user.mention} تحدى {opponent.mention}!\nدور X ❌ يبدأ.")
    await interaction.response.send_message(embed=embed, view=view)


@client.tree.command(name="leaderboard", description="أفضل اللاعبين في الألعاب")
@app_commands.guild_only()
async def leaderboard_cmd(interaction: discord.Interaction):
    if not scores:
        await interaction.response.send_message("لسه مفيش نقاط… العبوا الأول! 🎮", ephemeral=True)
        return
    top = sorted(
        scores.items(),
        key=lambda item: (item[1].get("points", 0), item[1].get("wins", 0)),
        reverse=True,
    )[:10]
    lines = [
        f"**{i}.** {data.get('name', 'لاعب')} — {data.get('points', 0)} نقطة • {data.get('wins', 0)} فوز"
        for i, (_, data) in enumerate(top, 1)
    ]
    embed = discord.Embed(
        title="🏆 لوحة صدارة أثر",
        description="\n".join(lines),
        color=EMBED_COLOR,
    )
    embed.set_footer(text="الألعاب: الروليت • الكراسي • X-O")
    await interaction.response.send_message(embed=embed)


@client.tree.command(name="score", description="نقاطك في الألعاب")
@app_commands.guild_only()
async def score_cmd(interaction: discord.Interaction):
    data = scores.get(str(interaction.user.id))
    if not data:
        await interaction.response.send_message("لسه ماعندكش نقاط… العب الأول! 🎮", ephemeral=True)
        return
    embed = discord.Embed(
        title="🎮 نقاطك", color=EMBED_COLOR,
        description=(f"**{data.get('points', 0)}** نقطة\n"
                     f"**{data.get('wins', 0)}** فوز\n"
                     f"**{data.get('games', 0)}** لعبة"))
    await interaction.response.send_message(embed=embed, ephemeral=True)


client.tree.add_command(roulette_group)
client.tree.add_command(chairs_group)

client.run(TOKEN)
