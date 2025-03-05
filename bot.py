import os
import json
import logging
import datetime
from pathlib import Path
import aiohttp
from dotenv import load_dotenv
import discord
from discord import app_commands
from discord.ext import commands
import math

load_dotenv()

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('platanotorrino-bot')

TOKEN = os.getenv('DISCORD_TOKEN')
CLIENT_ID = os.getenv('CLIENT_ID')

if not TOKEN or not CLIENT_ID:
    logger.error("Missing environment variables. Please set DISCORD_TOKEN and CLIENT_ID.")
    exit(1)

intents = discord.Intents.default()
intents.message_content = True  
bot = commands.Bot(command_prefix='!', intents=intents)

logger.info("Note: This bot uses privileged intents. Make sure to enable them in the Discord Developer Portal.")
logger.info("Visit: https://discord.com/developers/applications/ -> Your Application -> Bot -> Privileged Gateway Intents")

# Data directory setup
DATA_DIR = Path(__file__).parent / 'data'
DATA_DIR.mkdir(exist_ok=True)

MEETUPS_FILE = DATA_DIR / 'meetups.json'

if not MEETUPS_FILE.exists():
    default_meetups = {"meetups": []}
    with open(MEETUPS_FILE, 'w', encoding='utf-8') as f:
        json.dump(default_meetups, f, indent=2)

def get_meetups():
    try:
        with open(MEETUPS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Error reading meetups file: {e}")
        return {"meetups": []}

def save_meetups(meetups_data):
    try:
        with open(MEETUPS_FILE, 'w', encoding='utf-8') as f:
            json.dump(meetups_data, f, indent=2)
        return True
    except Exception as e:
        logger.error(f"Error saving meetups file: {e}")
        return False

def generate_meetup_id():
    meetups_data = get_meetups()
    ids = [meetup["id"] for meetup in meetups_data["meetups"]]
    return max(ids) + 1 if ids else 1

async def fetch_nekotina_gif(type):
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"https://nekotina.com/api/v2/{type}") as response:
                if response.status != 200:
                    raise Exception(f"Error fetching {type} GIF: {response.status}")
                data = await response.json()
                return data["url"]
    except Exception as e:
        logger.error(f"Error fetching {type} GIF: {e}")
        return None

@bot.event
async def on_ready():
    logger.info(f'Logged in as {bot.user.name} ({bot.user.id})')
    try:
        synced = await bot.tree.sync()
        logger.info(f"Synced {len(synced)} command(s)")
    except Exception as e:
        logger.error(f"Failed to sync commands: {e}")

@bot.tree.command(name="botinfo", description="Muestra información sobre el bot")
async def botinfo(interaction: discord.Interaction):
    await interaction.response.defer()
    
    bot_name = bot.user.name
    bot_avatar = bot.user.display_avatar.url
    bot_creation_date = bot.user.created_at
    formatted_creation_date = bot_creation_date.strftime("%A, %d de %B de %Y, %H:%M")
    
    total_lines = 0
    total_size = 0
    
    bot_file_path = Path(__file__)
    if bot_file_path.is_file():
        total_size = bot_file_path.stat().st_size
        with open(bot_file_path, 'r', encoding='utf-8', errors='ignore') as f:
            total_lines = sum(1 for _ in f)
    
    def format_bytes(bytes, decimals=2):
        if bytes == 0:
            return '0 Bytes'
        k = 1024
        dm = max(0, decimals)
        sizes = ['Bytes', 'KB', 'MB', 'GB', 'TB']
        i = int(math.log(bytes, k))
        return f"{bytes / (k ** i):.{dm}f} {sizes[i]}"
    
    embed = discord.Embed(
        title=f"Información de {bot_name}",
        description="A Discord bot for managing and displaying meetups",
        color=0xffdd9e
    )
    embed.set_thumbnail(url=bot_avatar)
    embed.add_field(name="🤖 Nombre", value=bot_name, inline=True)
    embed.add_field(name="📅 Creado el", value=formatted_creation_date, inline=True)
    embed.add_field(name="🔢 Versión", value="1.0.0", inline=True)
    embed.add_field(name="📊 Estadísticas", value=f"**Líneas de código:** {total_lines}\n**Tamaño total:** {format_bytes(total_size)}", inline=False)
    embed.add_field(name="👨‍💻 Autor", value="Platanotorrino Team", inline=True)
    embed.add_field(name="🔧 Tecnologías", value="Discord.py, Python", inline=True)
    embed.set_footer(text="Platanotorrino Discord Bot")
    embed.timestamp = datetime.datetime.now()
    
    await interaction.followup.send(embed=embed)

@bot.tree.command(name="quedadas", description="Muestra las quedadas activas y pendientes")
async def quedadas(interaction: discord.Interaction):
    meetups_data = get_meetups()
    
    if not meetups_data["meetups"]:
        await interaction.response.send_message("No hay ninguna quedada pendiente actualmente.")
        return
    
    embed = discord.Embed(
        title="Quedadas",
        description="Lista de quedadas activas y pendientes",
        color=0xffdd9e
    )
    embed.timestamp = datetime.datetime.now()
    embed.set_footer(text="Platanotorrino Discord Bot")
    
    view = discord.ui.View()
    
    for meetup in meetups_data["meetups"]:
        status_emoji = "🟢" if meetup["status"] == "activo" else "🟡"
        date = datetime.datetime.fromisoformat(meetup["date"].replace('Z', '+00:00'))
        formatted_date = date.strftime("%A, %d de %B de %Y, %H:%M")
        
        participants_text = "Ninguno"
        if meetup["participants"] and len(meetup["participants"]) > 0:
            participants_text = ", ".join(meetup["participants"])
        
        embed.add_field(
            name=f"{status_emoji} {meetup['title']}",
            value=f"**Descripción:** {meetup['description']}\n**Fecha:** {formatted_date}\n**Lugar:** {meetup['location']}\n**Estado:** {meetup['status']}\n**Participantes:** {participants_text}",
            inline=False
        )
        
        button = discord.ui.Button(label="Unirse a esta quedada", custom_id=f"join_meetup_{meetup['id']}", style=discord.ButtonStyle.primary)
        view.add_item(button)
    
    await interaction.response.send_message(embed=embed, view=view)

@bot.tree.command(name="crear-quedada", description="Crea una nueva quedada")
@app_commands.describe(
    titulo="Título de la quedada",
    descripcion="Descripción de la quedada",
    fecha="Fecha de la quedada (YYYY-MM-DD)",
    hora="Hora de la quedada (HH:MM)",
    lugar="Lugar de la quedada",
    estado="Estado de la quedada"
)
@app_commands.choices(estado=[
    app_commands.Choice(name="Activo", value="activo"),
    app_commands.Choice(name="Pendiente", value="pendiente")
])
async def crear_quedada(
    interaction: discord.Interaction, 
    titulo: str, 
    descripcion: str, 
    fecha: str, 
    hora: str, 
    lugar: str, 
    estado: str
):
    import re
    date_regex = re.compile(r'^\d{4}-\d{2}-\d{2}$')
    time_regex = re.compile(r'^\d{2}:\d{2}$')
    
    if not date_regex.match(fecha):
        await interaction.response.send_message("El formato de fecha debe ser YYYY-MM-DD (por ejemplo, 2023-12-31)", ephemeral=True)
        return
    
    if not time_regex.match(hora):
        await interaction.response.send_message("El formato de hora debe ser HH:MM (por ejemplo, 18:30)", ephemeral=True)
        return
    
    try:
        year, month, day = map(int, fecha.split('-'))
        hours, minutes = map(int, hora.split(':'))
        date = datetime.datetime(year, month, day, hours, minutes, tzinfo=datetime.timezone.utc)
    except ValueError:
        await interaction.response.send_message("La fecha y hora proporcionadas no son válidas", ephemeral=True)
        return
    
    new_meetup = {
        "id": generate_meetup_id(),
        "title": titulo,
        "description": descripcion,
        "date": date.isoformat(),
        "location": lugar,
        "status": estado,
        "participants": []
    }
    
    meetups_data = get_meetups()
    meetups_data["meetups"].append(new_meetup)
    
    if save_meetups(meetups_data):
        embed = discord.Embed(
            title="Nueva Quedada Creada",
            description=f'La quedada "{titulo}" ha sido creada correctamente.',
            color=0xffdd9e
        )
        embed.add_field(name="Descripción", value=descripcion, inline=False)
        embed.add_field(name="Fecha y Hora", value=date.strftime("%A, %d de %B de %Y, %H:%M"), inline=False)
        embed.add_field(name="Lugar", value=lugar, inline=True)
        embed.add_field(name="Estado", value=estado, inline=True)
        embed.timestamp = datetime.datetime.now()
        embed.set_footer(text="Platanotorrino Discord Bot")
        
        view = discord.ui.View()
        button = discord.ui.Button(label="Unirse a esta quedada", custom_id=f"join_meetup_{new_meetup['id']}", style=discord.ButtonStyle.primary)
        view.add_item(button)
        
        await interaction.response.send_message(embed=embed, view=view)
    else:
        await interaction.response.send_message("Ha ocurrido un error al crear la quedada", ephemeral=True)

@bot.tree.command(name="hug", description="Da un abrazo a otro usuario")
@app_commands.describe(usuario="Usuario al que quieres abrazar")
async def hug(interaction: discord.Interaction, usuario: discord.Member):
    await interaction.response.defer()
    
    gif_url = await fetch_nekotina_gif("hug")
    
    embed = discord.Embed(
        title="¡Abrazo!",
        description=f"{interaction.user.mention} le ha dado un cálido abrazo a {usuario.mention} 🤗",
        color=0xffafc9
    )
    embed.set_image(url=gif_url or "https://media.giphy.com/media/u9BxQbM5bxvwY/giphy.gif")
    embed.timestamp = datetime.datetime.now()
    embed.set_footer(text="Platanotorrino Discord Bot")
    
    await interaction.followup.send(embed=embed)

@bot.tree.command(name="pat", description="Da una palmadita a otro usuario")
@app_commands.describe(usuario="Usuario al que quieres dar una palmadita")
async def pat(interaction: discord.Interaction, usuario: discord.Member):
    await interaction.response.defer()
    
    gif_url = await fetch_nekotina_gif("pat")
    
    embed = discord.Embed(
        title="¡Palmadita!",
        description=f"{interaction.user.mention} le ha dado una suave palmadita a {usuario.mention} 👋",
        color=0xb8e986
    )
    embed.set_image(url=gif_url or "https://media.giphy.com/media/ARSp9T4wwxNcs/giphy.gif")
    embed.timestamp = datetime.datetime.now()
    embed.set_footer(text="Platanotorrino Discord Bot")
    
    await interaction.followup.send(embed=embed)

@bot.tree.command(name="highfive", description="Choca los cinco con otro usuario")
@app_commands.describe(usuario="Usuario con el que quieres chocar los cinco")
async def highfive(interaction: discord.Interaction, usuario: discord.Member):
    await interaction.response.defer()
    
    gif_url = await fetch_nekotina_gif("highfive")
    
    embed = discord.Embed(
        title="¡Choca esos cinco!",
        description=f"{interaction.user.mention} ha chocado los cinco con {usuario.mention} ✋",
        color=0xffd700
    )
    embed.set_image(url=gif_url or "https://media.giphy.com/media/3oEjHV0z8S7WM4MwnK/giphy.gif")
    embed.timestamp = datetime.datetime.now()
    embed.set_footer(text="Platanotorrino Discord Bot")
    
    await interaction.followup.send(embed=embed)

@bot.tree.command(name="poke", description="Toca a otro usuario para llamar su atención")
@app_commands.describe(usuario="Usuario al que quieres tocar")
async def poke(interaction: discord.Interaction, usuario: discord.Member):
    await interaction.response.defer()
    
    gif_url = await fetch_nekotina_gif("poke")
    
    embed = discord.Embed(
        title="¡Toque!",
        description=f"{interaction.user.mention} ha tocado a {usuario.mention} para llamar su atención 👉",
        color=0x87ceeb
    )
    embed.set_image(url=gif_url or "https://media.giphy.com/media/pWd3gD577gOqs/giphy.gif")
    embed.timestamp = datetime.datetime.now()
    embed.set_footer(text="Platanotorrino Discord Bot")
    
    await interaction.followup.send(embed=embed)

@bot.tree.command(name="help", description="Muestra todos los comandos disponibles")
@app_commands.describe(categoria="Categoría de comandos a mostrar (opcional)")
@app_commands.choices(categoria=[
    app_commands.Choice(name="Todos", value="todos"),
    app_commands.Choice(name="Administración", value="admin"),
    app_commands.Choice(name="Quedadas", value="quedadas"),
    app_commands.Choice(name="Interacción", value="interaccion"),
    app_commands.Choice(name="Utilidades", value="utilidades")
])
async def help_command(interaction: discord.Interaction, categoria: str = "todos"):
    await interaction.response.defer()
    
    categories = {
        "admin": {
            "name": "🛠️ Administración",
            "description": "Comandos para administrar el bot y el servidor",
            "commands": ["botinfo"]
        },
        "quedadas": {
            "name": "📅 Quedadas",
            "description": "Comandos para gestionar quedadas",
            "commands": ["quedadas", "crear-quedada", "eliminar-quedada"]
        },
        "interaccion": {
            "name": "👋 Interacción",
            "description": "Comandos para interactuar con otros usuarios",
            "commands": ["hug", "pat", "highfive", "poke", "slap", "kiss", "dance"]
        },
        "utilidades": {
            "name": "🔧 Utilidades",
            "description": "Comandos de utilidad general",
            "commands": ["help"]
        }
    }
    
    all_commands = bot.tree.get_commands()
    
    embed = discord.Embed(
        title="Comandos Disponibles",
        description="Aquí tienes una lista de los comandos disponibles",
        color=0x3498db
    )
    
    def add_commands_to_embed(commands_list):
        for cmd in commands_list:
            params_info = ""
            if hasattr(cmd, 'parameters') and cmd.parameters:
                params = [f"<{param.name}>" for param in cmd.parameters]
                if params:
                    params_info = f" {' '.join(params)}"
            
            embed.add_field(
                name=f"/{cmd.name}{params_info}",
                value=cmd.description or "Sin descripción disponible",
                inline=False
            )
    
    if categoria != "todos" and categoria in categories:
        cat_info = categories[categoria]
        embed.title = f"Comandos de {cat_info['name']}"
        embed.description = cat_info['description']
        
        category_commands = [cmd for cmd in all_commands if cmd.name in cat_info['commands']]
        category_commands.sort(key=lambda x: x.name)
        
        add_commands_to_embed(category_commands)
    else:
        for cat_id, cat_info in categories.items():
            embed.add_field(
                name=cat_info['name'],
                value=cat_info['description'],
                inline=False
            )
            
            category_commands = [cmd for cmd in all_commands if cmd.name in cat_info['commands']]
            category_commands.sort(key=lambda x: x.name)
            
            for cmd in category_commands:
                params_info = ""
                if hasattr(cmd, 'parameters') and cmd.parameters:
                    params = [f"<{param.name}>" for param in cmd.parameters]
                    if params:
                        params_info = f" {' '.join(params)}"
                
                embed.add_field(
                    name=f"  /{cmd.name}{params_info}",
                    value=f"  {cmd.description or 'Sin descripción disponible'}",
                    inline=False
                )
    
    embed.set_footer(text="Usa /help <categoria> para ver comandos específicos")
    embed.timestamp = datetime.datetime.now()
    
    await interaction.followup.send(embed=embed)

@bot.tree.command(name="eliminar-quedada", description="Elimina una quedada existente")
@app_commands.describe(id_quedada="ID de la quedada a eliminar")
async def eliminar_quedada(interaction: discord.Interaction, id_quedada: int):
    if not interaction.user.guild_permissions.manage_messages:
        await interaction.response.send_message("No tienes permisos para eliminar quedadas", ephemeral=True)
        return
    
    meetups_data = get_meetups()
    
    meetup_index = None
    for i, meetup in enumerate(meetups_data["meetups"]):
        if meetup["id"] == id_quedada:
            meetup_index = i
            break
    
    if meetup_index is None:
        await interaction.response.send_message(f"No se encontró ninguna quedada con ID {id_quedada}", ephemeral=True)
        return
    
    meetup = meetups_data["meetups"][meetup_index]
    
    del meetups_data["meetups"][meetup_index]
    
    if save_meetups(meetups_data):
        embed = discord.Embed(
            title="Quedada Eliminada",
            description=f'La quedada "{meetup["title"]}" ha sido eliminada correctamente.',
            color=0xff6961
        )
        embed.add_field(name="ID", value=str(meetup["id"]), inline=True)
        embed.add_field(name="Estado", value=meetup["status"], inline=True)
        embed.timestamp = datetime.datetime.now()
        embed.set_footer(text="Platanotorrino Discord Bot")
        
        await interaction.response.send_message(embed=embed)
    else:
        await interaction.response.send_message("Ha ocurrido un error al eliminar la quedada", ephemeral=True)

@bot.tree.command(name="slap", description="Da una bofetada a otro usuario")
@app_commands.describe(usuario="Usuario al que quieres dar una bofetada")
async def slap(interaction: discord.Interaction, usuario: discord.Member):
    await interaction.response.defer()
    
    gif_url = await fetch_nekotina_gif("slap")
    
    embed = discord.Embed(
        title="¡Bofetada!",
        description=f"{interaction.user.mention} le ha dado una bofetada a {usuario.mention} 👋💥",
        color=0xff6347
    )
    embed.set_image(url=gif_url or "https://media.giphy.com/media/Zau0yrl17uzdK/giphy.gif")
    embed.timestamp = datetime.datetime.now()
    embed.set_footer(text="Platanotorrino Discord Bot")
    
    await interaction.followup.send(embed=embed)

@bot.tree.command(name="kiss", description="Da un beso a otro usuario")
@app_commands.describe(usuario="Usuario al que quieres dar un beso")
async def kiss(interaction: discord.Interaction, usuario: discord.Member):
    await interaction.response.defer()
    
    gif_url = await fetch_nekotina_gif("kiss")
    
    embed = discord.Embed(
        title="¡Beso!",
        description=f"{interaction.user.mention} le ha dado un dulce beso a {usuario.mention} 💋",
        color=0xff69b4
    )
    embed.set_image(url=gif_url or "https://media.giphy.com/media/G3va31oEEnIkM/giphy.gif")
    embed.timestamp = datetime.datetime.now()
    embed.set_footer(text="Platanotorrino Discord Bot")
    
    await interaction.followup.send(embed=embed)

@bot.tree.command(name="dance", description="Baila con otro usuario")
@app_commands.describe(usuario="Usuario con el que quieres bailar")
async def dance(interaction: discord.Interaction, usuario: discord.Member):
    await interaction.response.defer()
    
    gif_url = await fetch_nekotina_gif("dance")
    
    embed = discord.Embed(
        title="¡A bailar!",
        description=f"{interaction.user.mention} está bailando con {usuario.mention} 💃🕺",
        color=0x9370db
    )
    embed.set_image(url=gif_url or "https://media.giphy.com/media/l3q2Cy90VMhfoA8HC/giphy.gif")
    embed.timestamp = datetime.datetime.now()
    embed.set_footer(text="Platanotorrino Discord Bot")
    
    await interaction.followup.send(embed=embed)

if __name__ == "__main__":
    bot.run(TOKEN)