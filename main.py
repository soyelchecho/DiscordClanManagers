import discord
from discord.ext import commands
import os
import asyncio
import logging
from dotenv import load_dotenv
from database import (
    init_database, migrate_from_json, crear_clan, obtener_clan,
    obtener_todos_clanes, clan_existe, obtener_clan_por_canal_admin,
    agregar_canal_extra, obtener_estadisticas
)

load_dotenv()

logging.basicConfig(level=logging.INFO)

intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.members = True

bot = commands.Bot(command_prefix='/', intents=intents)

@bot.event
async def on_ready():
    print(f'{bot.user} ha iniciado sesión')
    print(f'Bot conectado a {len(bot.guilds)} servidores')

    # Inicializar base de datos
    init_database()
    print('Base de datos SQLite inicializada')

    # Migrar datos de JSON si existen
    migrate_from_json()

    try:
        synced = await bot.tree.sync()
        print(f'Sincronizados {len(synced)} comandos de barra')
    except Exception as e:
        print(f'Error al sincronizar comandos: {e}')

class TicketView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label='🎫 Crear Ticket', style=discord.ButtonStyle.green)
    async def create_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        user = interaction.user
        
        # Crear thread privado
        ticket_thread = await interaction.channel.create_thread(
            name=f'ticket-{user.display_name}',
            type=discord.ChannelType.private_thread
        )
        
        await ticket_thread.add_user(user)
        
        embed = discord.Embed(
            title="🎫 Sistema de Tickets",
            description=f"¡Hola {user.mention}! Este es tu ticket privado.\n\n**Comandos disponibles:**\n`/crear_clan <nombre>` - Crear un nuevo clan\n`/info_clan <nombre>` - Ver información de un clan",
            color=0x00ff00
        )
        
        await ticket_thread.send(embed=embed)
        
        await interaction.response.send_message(
            f"✅ Ticket creado: {ticket_thread.mention}",
            ephemeral=True
        )

@bot.tree.command(name='setup_tickets', description='Configurar el sistema de tickets para clanes')
@discord.app_commands.describe()
async def setup_tickets(interaction: discord.Interaction):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ Solo administradores pueden usar este comando.", ephemeral=True)
        return
    
    embed = discord.Embed(
        title="🏰 Sistema de Gestión de Clanes",
        description="Haz clic en el botón para abrir un ticket y gestionar tu clan.",
        color=0x0099ff
    )
    
    view = TicketView()
    await interaction.response.send_message(embed=embed, view=view)

@bot.tree.command(name='crear_clan', description='Crear un nuevo clan')
@discord.app_commands.describe(nombre_clan='Nombre del clan a crear')
async def crear_clan(interaction: discord.Interaction, nombre_clan: str):
    if not isinstance(interaction.channel, discord.Thread):
        await interaction.response.send_message("❌ Este comando solo se puede usar dentro de un ticket.", ephemeral=True)
        return
    
    guild = interaction.guild
    autor = interaction.user

    if clan_existe(nombre_clan):
        await interaction.response.send_message(f"❌ El clan '{nombre_clan}' ya existe.", ephemeral=True)
        return

    await interaction.response.defer()
    
    try:
        # Crear rol del clan
        clan_role = await guild.create_role(
            name=f"Clan-{nombre_clan}",
            mentionable=True,
            hoist=True
        )
        
        # Crear categoría para el clan
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            clan_role: discord.PermissionOverwrite(read_messages=True),
            guild.me: discord.PermissionOverwrite(read_messages=True)
        }
        
        # Agregar permisos para administradores
        for role in guild.roles:
            if role.permissions.administrator:
                overwrites[role] = discord.PermissionOverwrite(read_messages=True)
        
        categoria = await guild.create_category(
            f"🏰 {nombre_clan}",
            overwrites=overwrites
        )
        
        # Canal de anuncios (solo admins pueden escribir)
        admin_overwrites = overwrites.copy()
        admin_overwrites[clan_role] = discord.PermissionOverwrite(
            read_messages=True,
            send_messages=False
        )
        
        canal_anuncios = await categoria.create_text_channel(
            "📢-anuncios",
            overwrites=admin_overwrites
        )
        
        # Canal de administración del clan
        admin_only_overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            autor: discord.PermissionOverwrite(read_messages=True, send_messages=True),
            guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True)
        }
        
        for role in guild.roles:
            if role.permissions.administrator:
                admin_only_overwrites[role] = discord.PermissionOverwrite(read_messages=True)
        
        canal_admin = await categoria.create_text_channel(
            "⚙️-administracion",
            overwrites=admin_only_overwrites
        )
        
        # Canal general del clan
        canal_general = await categoria.create_text_channel(
            "💬-general",
            overwrites=overwrites
        )
        
        # Crear invitación permanente
        invite = await canal_anuncios.create_invite(
            max_age=0,  # No expira
            max_uses=0,  # Usos ilimitados
            unique=True
        )
        
        # Asignar rol al creador
        await autor.add_roles(clan_role)

        # Guardar datos del clan en SQLite
        crear_clan(
            nombre=nombre_clan,
            creador_id=autor.id,
            rol_id=clan_role.id,
            categoria_id=categoria.id,
            canal_anuncios_id=canal_anuncios.id,
            canal_admin_id=canal_admin.id,
            canal_general_id=canal_general.id,
            invite_code=invite.code
        )
        
        # Enviar mensaje en el canal de anuncios
        embed_anuncios = discord.Embed(
            title=f"🏰 Bienvenido al Clan {nombre_clan}",
            description=f"¡Únete al clan usando este enlace!\n\n🔗 **Invitación:** {invite.url}\n\n*Esta invitación nunca expira*",
            color=0x00ff00
        )
        await canal_anuncios.send(embed=embed_anuncios)
        
        # Enviar mensaje en el canal de administración
        embed_admin = discord.Embed(
            title="⚙️ Panel de Administración del Clan",
            description=f"¡Hola {autor.mention}! Aquí puedes gestionar tu clan.\n\n**Comandos disponibles:**\n`/agregar_canal_texto <nombre>` - Agregar canal de texto\n`/agregar_canal_voz <nombre>` - Agregar canal de voz\n`/listar_canales` - Ver canales del clan\n`/eliminar_canal <nombre>` - Eliminar canal",
            color=0x0099ff
        )
        await canal_admin.send(embed=embed_admin)
        
        await interaction.followup.send(f"✅ ¡Clan '{nombre_clan}' creado exitosamente!\n\n📂 Categoría: {categoria.mention}\n🎭 Rol: {clan_role.mention}\n🔗 Invitación: {invite.url}")
        
    except Exception as e:
        await interaction.followup.send(f"❌ Error al crear el clan: {str(e)}")

@bot.tree.command(name='agregar_canal_texto', description='Agregar un canal de texto al clan')
@discord.app_commands.describe(nombre_canal='Nombre del canal de texto a crear')
async def agregar_canal_texto(interaction: discord.Interaction, nombre_canal: str):
    await agregar_canal(interaction, nombre_canal, 'texto')

@bot.tree.command(name='agregar_canal_voz', description='Agregar un canal de voz al clan')
@discord.app_commands.describe(nombre_canal='Nombre del canal de voz a crear')
async def agregar_canal_voz(interaction: discord.Interaction, nombre_canal: str):
    await agregar_canal(interaction, nombre_canal, 'voz')

async def agregar_canal(interaction, nombre_canal, tipo_canal):
    if not isinstance(interaction.channel, discord.TextChannel):
        await interaction.response.send_message("❌ Este comando solo se puede usar en canales de texto.", ephemeral=True)
        return
    
    # Buscar el clan del canal actual
    clan_nombre = obtener_clan_por_canal_admin(interaction.channel.id)

    if not clan_nombre:
        await interaction.response.send_message("❌ Este no es un canal de administración de clan válido.", ephemeral=True)
        return

    clan_data = obtener_clan(clan_nombre)

    # Verificar permisos
    if interaction.user.id != clan_data['creador'] and not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ Solo el creador del clan o administradores pueden usar este comando.", ephemeral=True)
        return

    await interaction.response.defer()

    try:
        guild = interaction.guild
        categoria_id = clan_data['categoria_id']
        categoria = guild.get_channel(categoria_id)
        clan_role = guild.get_role(clan_data['rol_id'])
        
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            clan_role: discord.PermissionOverwrite(read_messages=True),
            guild.me: discord.PermissionOverwrite(read_messages=True)
        }
        
        for role in guild.roles:
            if role.permissions.administrator:
                overwrites[role] = discord.PermissionOverwrite(read_messages=True)
        
        if tipo_canal == 'texto':
            nuevo_canal = await categoria.create_text_channel(
                nombre_canal,
                overwrites=overwrites
            )
        else:  # voz
            nuevo_canal = await categoria.create_voice_channel(
                nombre_canal,
                overwrites=overwrites
            )
        
        # Guardar canal extra en SQLite
        agregar_canal_extra(clan_nombre, nuevo_canal.id, nombre_canal, tipo_canal)
        
        await interaction.followup.send(f"✅ Canal {tipo_canal} '{nombre_canal}' creado exitosamente: {nuevo_canal.mention}")
        
    except Exception as e:
        await interaction.followup.send(f"❌ Error al crear el canal: {str(e)}")

@bot.tree.command(name='listar_canales', description='Ver todos los canales del clan')
async def listar_canales(interaction: discord.Interaction):
    clan_nombre = obtener_clan_por_canal_admin(interaction.channel.id)

    if not clan_nombre:
        await interaction.response.send_message("❌ Este no es un canal de administración de clan válido.", ephemeral=True)
        return

    data = obtener_clan(clan_nombre)
    guild = interaction.guild
    
    embed = discord.Embed(
        title=f"📋 Canales del Clan {clan_nombre}",
        color=0x0099ff
    )
    
    canales_base = [
        f"📢 <#{data['canal_anuncios_id']}>",
        f"⚙️ <#{data['canal_admin_id']}>",
        f"💬 <#{data['canal_general_id']}>"
    ]
    
    embed.add_field(
        name="Canales Base",
        value="\n".join(canales_base),
        inline=False
    )
    
    if data['canales_extra']:
        canales_extra = []
        for canal in data['canales_extra']:
            emoji = "💬" if canal['tipo'] == 'texto' else "🔊"
            canales_extra.append(f"{emoji} <#{canal['id']}>")
        
        embed.add_field(
            name="Canales Adicionales",
            value="\n".join(canales_extra),
            inline=False
        )
    
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name='info_clan', description='Ver información de un clan o lista de clanes')
@discord.app_commands.describe(nombre_clan='Nombre del clan (opcional)')
async def info_clan(interaction: discord.Interaction, nombre_clan: str = None):
    if nombre_clan and clan_existe(nombre_clan):
        data = obtener_clan(nombre_clan)
        guild = interaction.guild

        creador = guild.get_member(data['creador'])
        clan_role = guild.get_role(data['rol_id'])

        embed = discord.Embed(
            title=f"🏰 Información del Clan {nombre_clan}",
            color=0x0099ff
        )

        embed.add_field(name="👑 Creador", value=creador.mention if creador else "Desconocido", inline=True)
        embed.add_field(name="👥 Miembros", value=len(clan_role.members) if clan_role else "0", inline=True)
        embed.add_field(name="🔗 Invitación", value=f"https://discord.gg/{data['invite_code']}", inline=False)

        await interaction.response.send_message(embed=embed)
    else:
        todos_los_clanes = obtener_todos_clanes()
        clanes_disponibles = list(todos_los_clanes.keys())
        if clanes_disponibles:
            embed = discord.Embed(
                title="🏰 Clanes Disponibles",
                description="\n".join([f"• {clan}" for clan in clanes_disponibles]),
                color=0x0099ff
            )
        else:
            embed = discord.Embed(
                title="🏰 No hay clanes creados",
                description="Usa `/crear_clan <nombre>` para crear el primero.",
                color=0xff9900
            )
        
        await interaction.response.send_message(embed=embed)

if __name__ == '__main__':
    bot.run(os.getenv('DISCORD_TOKEN'))
