import discord
from discord.ext import commands
from discord import app_commands
import os
import asyncio
import logging
from dotenv import load_dotenv
from datetime import datetime
from database import (
    init_database, crear_clan, obtener_clan, obtener_todos_clanes,
    clan_existe, obtener_clan_por_canal_admin, agregar_canal_extra,
    agregar_xp_clan, agregar_miembro_clan, obtener_miembros_clan,
    obtener_rol_miembro, es_miembro_clan, crear_invitacion,
    obtener_invitacion, aceptar_invitacion, rechazar_invitacion,
    contar_canales_extra, limpiar_invitaciones_expiradas, NIVELES_CLAN
)

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] [%(levelname)-8s] %(name)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.members = True
intents.dm_messages = True

bot = commands.Bot(command_prefix='!', intents=intents)

# ==================== EVENTOS ====================

@bot.event
async def on_ready():
    logger.info(f'{bot.user} ha iniciado sesión')
    logger.info(f'Bot conectado a {len(bot.guilds)} servidores')

    # Inicializar base de datos
    init_database()
    logger.info('Base de datos SQLite inicializada')

    # Limpiar invitaciones expiradas
    limpiar_invitaciones_expiradas()

    try:
        logger.info('Iniciando sincronización de comandos...')
        guild_id = os.getenv('GUILD_ID')
        logger.info(f'GUILD_ID obtenido: {guild_id}')

        if guild_id:
            guild_id = int(guild_id)
            guild = discord.Object(id=guild_id)

            # Sincronizar comandos
            logger.info(f'Sincronizando comandos en servidor {guild_id}...')
            bot.tree.copy_global_to(guild=guild)
            synced = await bot.tree.sync(guild=guild)
            logger.info(f'✅ Sincronizados {len(synced)} comandos en servidor {guild_id}')
            logger.info(f'Comandos sincronizados: {[cmd.name for cmd in synced]}')
        else:
            logger.warning('GUILD_ID no encontrado, sincronizando globalmente...')
            synced = await bot.tree.sync()
            logger.info(f'✅ Sincronizados {len(synced)} comandos globalmente')
    except Exception as e:
        logger.error(f'❌ Error al sincronizar comandos: {e}')
        logger.exception(e)

@bot.event
async def on_member_join(member):
    """Detectar cuando alguien se une mediante invitación permanente y dar XP"""
    try:
        # Obtener las invitaciones actuales
        invites_after = await member.guild.invites()

        # Buscar en todos los clanes cuál invitación se usó
        clanes = obtener_todos_clanes()

        for clan_nombre, clan_info in clanes.items():
            # Verificar si la invitación del clan fue usada
            invite_code = clan_info.get('invite_code')
            if not invite_code:
                continue

            # Buscar la invitación en la lista
            for invite in invites_after:
                if invite.code == invite_code:
                    # Esta es una invitación permanente de un clan
                    # Agregar el miembro al clan como Recluta por defecto
                    clan_role = member.guild.get_role(clan_info['rol_id'])

                    if clan_role:
                        # Asignar rol de Discord
                        await member.add_roles(clan_role)

                        # Agregar a la base de datos
                        agregar_miembro_clan(
                            clan_nombre=clan_nombre,
                            usuario_id=member.id,
                            rol='Recluta',
                            invitado_por=None  # No sabemos quién compartió el link
                        )

                        # Dar XP al clan (+50 XP por nuevo miembro)
                        resultado = agregar_xp_clan(
                            clan_nombre=clan_nombre,
                            cantidad_xp=50,
                            razon="Nuevo miembro se unió mediante invitación permanente",
                            usuario_id=member.id,
                            origen="invitacion_permanente"
                        )

                        # Notificar en el canal general
                        canal_general = member.guild.get_channel(clan_info['canal_general_id'])
                        if canal_general:
                            embed = discord.Embed(
                                title="🎉 ¡Nuevo Miembro!",
                                description=f"{member.mention} se ha unido al clan mediante la invitación permanente",
                                color=0x00ff00
                            )
                            embed.add_field(name="Rol asignado", value="Recluta", inline=True)
                            embed.add_field(name="XP ganado", value="+50 XP", inline=True)

                            if resultado and resultado.get('subio_nivel'):
                                embed.add_field(
                                    name="🎊 ¡NIVEL SUBIDO!",
                                    value=f"Nivel {resultado['nivel_anterior']} → {resultado['nivel_nuevo']}\n"
                                          f"Nuevos límites desbloqueados!",
                                    inline=False
                                )

                            await canal_general.send(embed=embed)

                        logger.info(f"Usuario {member.name} se unió al clan {clan_nombre} mediante invitación permanente (+50 XP)")
                        break

    except Exception as e:
        logger.error(f"Error en on_member_join: {e}")
        logger.exception(e)

# ==================== VISTAS/UI ====================

class InvitacionView(discord.ui.View):
    def __init__(self, invitacion_id: int):
        super().__init__(timeout=None)
        self.invitacion_id = invitacion_id

    @discord.ui.button(label='✅ Aceptar', style=discord.ButtonStyle.green, custom_id='aceptar_invitacion')
    async def aceptar(self, interaction: discord.Interaction, button: discord.ui.Button):
        invitacion = obtener_invitacion(self.invitacion_id)

        if not invitacion or invitacion['usuario_invitado_id'] != interaction.user.id:
            await interaction.response.send_message("❌ Esta invitación no es para ti.", ephemeral=True)
            return

        if invitacion['estado'] != 'pendiente':
            await interaction.response.send_message("❌ Esta invitación ya no está disponible.", ephemeral=True)
            return

        # Aceptar invitación
        if aceptar_invitacion(self.invitacion_id):
            clan_info = obtener_clan(invitacion['clan_nombre'])

            embed = discord.Embed(
                title="✅ ¡Te has unido al clan!",
                description=f"Ahora eres parte de **{invitacion['clan_nombre']}**",
                color=0x00ff00
            )
            embed.add_field(name="Rol asignado", value=invitacion['rol_asignado'])
            embed.add_field(name="Nivel del clan", value=f"Nivel {clan_info['nivel']}")

            # Desactivar botones
            for item in self.children:
                item.disabled = True

            await interaction.response.edit_message(embed=embed, view=self)

            # Notificar en el canal del clan si existe
            try:
                guild = bot.get_guild(int(os.getenv('GUILD_ID')))
                canal_general = guild.get_channel(clan_info['canal_general_id'])
                if canal_general:
                    await canal_general.send(f"🎉 {interaction.user.mention} se ha unido al clan!")
            except:
                pass
        else:
            await interaction.response.send_message("❌ Error al aceptar la invitación.", ephemeral=True)

    @discord.ui.button(label='❌ Rechazar', style=discord.ButtonStyle.red, custom_id='rechazar_invitacion')
    async def rechazar(self, interaction: discord.Interaction, button: discord.ui.Button):
        invitacion = obtener_invitacion(self.invitacion_id)

        if not invitacion or invitacion['usuario_invitado_id'] != interaction.user.id:
            await interaction.response.send_message("❌ Esta invitación no es para ti.", ephemeral=True)
            return

        if rechazar_invitacion(self.invitacion_id):
            embed = discord.Embed(
                title="❌ Invitación rechazada",
                description=f"Has rechazado la invitación a **{invitacion['clan_nombre']}**",
                color=0xff0000
            )

            # Desactivar botones
            for item in self.children:
                item.disabled = True

            await interaction.response.edit_message(embed=embed, view=self)
        else:
            await interaction.response.send_message("❌ Error al rechazar la invitación.", ephemeral=True)

# ==================== COMANDOS PÚBLICOS ====================

@bot.tree.command(name='crear_clan', description='Iniciar proceso de creación de un clan')
async def crear_clan_cmd(interaction: discord.Interaction):
    """Crear un nuevo clan con flujo interactivo en thread privado"""

    await interaction.response.defer(ephemeral=True)

    try:
        guild = interaction.guild
        autor = interaction.user

        # Obtener el canal configurado para threads desde .env
        thread_channel_id = os.getenv('THREAD_CHANNEL_ID')

        if not thread_channel_id:
            # Si no está configurado, usar el canal actual
            canal_para_thread = interaction.channel
        else:
            canal_para_thread = guild.get_channel(int(thread_channel_id))

        if not canal_para_thread:
            await interaction.followup.send(
                "❌ No se pudo encontrar el canal para crear threads. Contacta a un administrador.",
                ephemeral=True
            )
            return

        # Verificar que el canal sea de texto
        if not isinstance(canal_para_thread, discord.TextChannel):
            await interaction.followup.send(
                "❌ El canal configurado no es un canal de texto válido.",
                ephemeral=True
            )
            return

        # Crear thread privado
        try:
            thread = await canal_para_thread.create_thread(
                name=f"🏰 Crear Clan - {autor.name}",
                type=discord.ChannelType.private_thread,
                invitable=False,
                auto_archive_duration=60  # Se archiva después de 1 hora de inactividad
            )

            # Agregar al usuario al thread
            await thread.add_user(autor)

        except discord.Forbidden:
            await interaction.followup.send(
                "❌ No tengo permisos para crear threads privados en ese canal.",
                ephemeral=True
            )
            return
        except discord.HTTPException as e:
            await interaction.followup.send(
                f"❌ Error al crear el thread: {str(e)}\n"
                f"El canal debe ser un canal de texto normal (no anuncios, no foro).",
                ephemeral=True
            )
            return

        # Mensaje de bienvenida en el thread
        embed_inicio = discord.Embed(
            title="🏰 Creación de Clan",
            description=f"¡Hola {autor.mention}! Vamos a crear tu clan paso a paso.\n\n"
                        f"Este thread es **privado** - solo tú y los administradores pueden verlo.",
            color=0x0099ff
        )
        embed_inicio.add_field(
            name="📝 Paso 1: Nombre del Clan",
            value="Por favor, escribe el nombre que deseas para tu clan.\n"
                  "**Requisitos:**\n"
                  "• Entre 3 y 32 caracteres\n"
                  "• Sin caracteres especiales extraños\n"
                  "• Debe ser único",
            inline=False
        )

        await thread.send(embed=embed_inicio)

        # Confirmar al usuario
        await interaction.followup.send(
            f"✅ Thread privado creado: {thread.mention}\n"
            f"Continúa allí con la creación de tu clan.",
            ephemeral=True
        )

        # Iniciar el flujo interactivo
        def check_author(m):
            return m.author == autor and m.channel == thread

        # Esperar nombre
        nombre = None
        intentos = 0
        max_intentos = 3

        while intentos < max_intentos:
            try:
                msg_nombre = await bot.wait_for('message', check=check_author, timeout=300.0)
                nombre = msg_nombre.content.strip()

                # Validar nombre
                if len(nombre) < 3 or len(nombre) > 32:
                    await thread.send("❌ El nombre debe tener entre 3 y 32 caracteres. Intenta de nuevo:")
                    intentos += 1
                    continue

                if clan_existe(nombre):
                    await thread.send(f"❌ El clan '{nombre}' ya existe. Elige otro nombre:")
                    intentos += 1
                    continue

                # Nombre válido
                break

            except asyncio.TimeoutError:
                await thread.send("⏱️ Se acabó el tiempo. Usa `/crear_clan` nuevamente para reintentar.")
                return

        if intentos >= max_intentos:
            await thread.send("❌ Demasiados intentos fallidos. Usa `/crear_clan` nuevamente.")
            return

        # Confirmar nombre
        await thread.send(f"✅ Nombre del clan: **{nombre}**")

        # Paso 2: Descripción
        embed_desc = discord.Embed(
            title="📝 Paso 2: Descripción del Clan",
            description="Escribe una breve descripción de tu clan.\n"
                        "Puedes escribir `ninguna` o `skip` si no quieres agregar descripción ahora.",
            color=0x0099ff
        )
        await thread.send(embed=embed_desc)

        try:
            msg_desc = await bot.wait_for('message', check=check_author, timeout=300.0)
            descripcion = msg_desc.content.strip()

            if descripcion.lower() in ['ninguna', 'skip', 'no', 'none']:
                descripcion = ""
                await thread.send("✅ Sin descripción.")
            else:
                await thread.send(f"✅ Descripción: {descripcion}")

        except asyncio.TimeoutError:
            descripcion = ""
            await thread.send("⏱️ Sin descripción (tiempo agotado).")

        # Paso 3: Confirmación
        embed_confirmacion = discord.Embed(
            title="🏰 Confirmación Final",
            description="Revisa los datos de tu clan:",
            color=0x00ff00
        )
        embed_confirmacion.add_field(name="Nombre", value=nombre, inline=False)
        embed_confirmacion.add_field(name="Descripción", value=descripcion or "Sin descripción", inline=False)
        embed_confirmacion.add_field(
            name="¿Crear el clan?",
            value="Escribe `confirmar` para crear el clan o `cancelar` para abortar.",
            inline=False
        )

        await thread.send(embed=embed_confirmacion)

        try:
            msg_confirm = await bot.wait_for('message', check=check_author, timeout=120.0)

            if msg_confirm.content.lower() not in ['confirmar', 'si', 'yes', 'confirm']:
                await thread.send("❌ Creación cancelada.")
                return

        except asyncio.TimeoutError:
            await thread.send("⏱️ Se acabó el tiempo. Creación cancelada.")
            return

        # Crear el clan
        await thread.send("⏳ Creando clan...")

        # Crear rol del clan
        clan_role = await guild.create_role(
            name=f"Clan-{nombre}",
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
            f"🏰 {nombre}",
            overwrites=overwrites
        )

        # Canal de anuncios (solo admins pueden escribir, contiene invitación secreta)
        admin_overwrites = overwrites.copy()
        admin_overwrites[clan_role] = discord.PermissionOverwrite(
            read_messages=True,
            send_messages=False
        )

        canal_anuncios = await categoria.create_text_channel(
            "📢-anuncios",
            overwrites=admin_overwrites
        )

        # Canal de administración del clan (solo creador + admins servidor)
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

        # Crear invitación permanente SECRETA
        invite = await canal_anuncios.create_invite(
            max_age=0,  # No expira
            max_uses=0,  # Usos ilimitados
            unique=True
        )

        # Asignar rol al creador
        await autor.add_roles(clan_role)

        # Guardar en base de datos
        crear_clan(
            nombre=nombre,
            creador_id=autor.id,
            descripcion=descripcion,
            rol_id=clan_role.id,
            categoria_id=categoria.id,
            canal_anuncios_id=canal_anuncios.id,
            canal_admin_id=canal_admin.id,
            canal_general_id=canal_general.id,
            invite_code=invite.code
        )

        # Mensaje en anuncios (solo visible para admins y creador)
        embed_anuncios = discord.Embed(
            title=f"🏰 Bienvenido al Clan {nombre}",
            description=f"**Invitación Permanente (SECRETA)**\n\n🔗 {invite.url}\n\n⚠️ Solo comparte este enlace con personas de confianza.\nPara invitar oficialmente, usa `/invitar_clan`",
            color=0x00ff00
        )
        await canal_anuncios.send(embed=embed_anuncios)

        # Mensaje en administración
        embed_admin = discord.Embed(
            title="⚙️ Panel de Administración del Clan",
            description=f"¡Hola {autor.mention}! Tu clan ha sido creado.\n\n**📊 Estado Inicial:**\n• Nivel: 1\n• XP: 0/500\n• Límite de miembros: 10\n• Canales texto extra: 0/3\n• Canales voz extra: 0/2\n\n**Comandos disponibles:**\n`/agregar_canal` - Agregar canal\n`/stats_clan` - Ver estadísticas\n`/invitar_clan` - Invitar miembro\n`/gestionar_miembros` - Ver/gestionar miembros\n`/ver_invitacion` - Ver invitación secreta",
            color=0x0099ff
        )
        await canal_admin.send(embed=embed_admin)

        # Respuesta en el thread
        embed_exito = discord.Embed(
            title="✅ ¡Clan Creado Exitosamente!",
            description=f"Tu clan **{nombre}** ha sido creado.",
            color=0x00ff00
        )
        embed_exito.add_field(name="📂 Categoría", value=categoria.mention, inline=False)
        embed_exito.add_field(name="🎭 Rol", value=clan_role.mention, inline=True)
        embed_exito.add_field(name="📊 Nivel", value="1 (0/500 XP)", inline=True)
        embed_exito.add_field(name="👥 Límite", value="10 miembros", inline=True)
        embed_exito.add_field(
            name="🔐 Invitación Secreta",
            value=f"Disponible en {canal_anuncios.mention}",
            inline=False
        )

        await thread.send(embed=embed_exito)
        await thread.send("Puedes cerrar este thread cuando quieras. ¡Disfruta tu clan! 🎉")

    except Exception as e:
        logger.error(f"Error al crear clan: {e}")
        logger.exception(e)
        try:
            await thread.send(f"❌ Error al crear el clan: {str(e)}")
        except:
            await interaction.followup.send(
                f"❌ Error al crear el clan: {str(e)}",
                ephemeral=True
            )

@bot.tree.command(name='listar_clanes', description='Ver todos los clanes disponibles en el servidor')
async def listar_clanes(interaction: discord.Interaction):
    """Listar todos los clanes con información básica"""

    clanes = obtener_todos_clanes()

    if not clanes:
        embed = discord.Embed(
            title="🏰 No hay clanes creados",
            description="Usa `/crear_clan` para crear el primero.",
            color=0xff9900
        )
        await interaction.response.send_message(embed=embed)
        return

    embed = discord.Embed(
        title=f"🏰 Clanes en {interaction.guild.name}",
        description=f"Total: {len(clanes)} clanes",
        color=0x0099ff
    )

    for nombre, info in list(clanes.items())[:10]:  # Máximo 10 para no saturar
        nivel_config = NIVELES_CLAN[info['nivel']]

        creador = interaction.guild.get_member(info['creador'])
        creador_str = creador.mention if creador else "Desconocido"

        embed.add_field(
            name=f"{'⭐' * info['nivel']} {nombre}",
            value=f"**Líder:** {creador_str}\n"
                  f"**Nivel:** {info['nivel']} ({info['xp_actual']} XP)\n"
                  f"**Miembros:** {info['total_miembros']}/{nivel_config['limite_miembros']}\n"
                  f"**Descripción:** {info['descripcion'] or 'Sin descripción'}",
            inline=False
        )

    if len(clanes) > 10:
        embed.set_footer(text=f"Mostrando 10 de {len(clanes)} clanes. Usa /info_clan para ver uno específico.")

    await interaction.response.send_message(embed=embed)

@bot.tree.command(name='info_clan', description='Ver información detallada de un clan')
@app_commands.describe(nombre='Nombre del clan')
async def info_clan(interaction: discord.Interaction, nombre: str):
    """Mostrar información detallada de un clan (SIN invitación)"""

    if not clan_existe(nombre):
        await interaction.response.send_message(
            f"❌ El clan '{nombre}' no existe.",
            ephemeral=True
        )
        return

    clan_info = obtener_clan(nombre)
    miembros = obtener_miembros_clan(nombre)
    nivel_config = NIVELES_CLAN[clan_info['nivel']]

    # Creador
    creador = interaction.guild.get_member(clan_info['creador'])
    creador_str = creador.mention if creador else "Desconocido"

    # Rol del clan
    clan_role = interaction.guild.get_role(clan_info['rol_id'])

    embed = discord.Embed(
        title=f"🏰 {nombre}",
        description=clan_info['descripcion'] or "Sin descripción",
        color=clan_role.color if clan_role else 0x0099ff
    )

    # Información básica
    embed.add_field(
        name="👑 Líder",
        value=creador_str,
        inline=True
    )

    embed.add_field(
        name="📊 Nivel",
        value=f"{'⭐' * clan_info['nivel']} Nivel {clan_info['nivel']}",
        inline=True
    )

    embed.add_field(
        name="💎 XP",
        value=f"{clan_info['xp_actual']}/{clan_info['xp_siguiente_nivel'] if clan_info['nivel'] < 6 else 'MAX'}",
        inline=True
    )

    # Miembros
    lideres = [m for m in miembros if m['rol'] == 'Líder']
    colideres = [m for m in miembros if m['rol'] == 'Co-Líder']

    miembros_str = f"**Total:** {clan_info['total_miembros']}/{nivel_config['limite_miembros']}\n"
    if lideres:
        miembros_str += f"👑 {len(lideres)} Líder(es)\n"
    if colideres:
        miembros_str += f"⚔️ {len(colideres)} Co-Líder(es)\n"

    embed.add_field(
        name="👥 Miembros",
        value=miembros_str,
        inline=False
    )

    # Canales
    canales_texto_usados = contar_canales_extra(nombre, 'texto')
    canales_voz_usados = contar_canales_extra(nombre, 'voz')

    embed.add_field(
        name="📁 Canales",
        value=f"💬 Texto: {canales_texto_usados}/{nivel_config['canales_texto']}\n"
              f"🔊 Voz: {canales_voz_usados}/{nivel_config['canales_voz']}",
        inline=True
    )

    # Fecha de creación
    fecha = datetime.fromisoformat(clan_info['fecha_creacion'])
    embed.set_footer(text=f"Creado el {fecha.strftime('%d/%m/%Y')}")

    await interaction.response.send_message(embed=embed)

@bot.tree.command(name='invitar_clan', description='Invitar a alguien a tu clan')
@app_commands.describe(
    usuario='Usuario a invitar',
    clan='Nombre del clan',
    rol='Rol que tendrá en el clan'
)
@app_commands.choices(rol=[
    app_commands.Choice(name='Recluta', value='Recluta'),
    app_commands.Choice(name='Miembro', value='Miembro'),
])
async def invitar_clan(interaction: discord.Interaction, usuario: discord.Member, clan: str, rol: app_commands.Choice[str]):
    """Invitar a un usuario al clan mediante DM"""

    # Validaciones
    if not clan_existe(clan):
        await interaction.response.send_message(
            f"❌ El clan '{clan}' no existe.",
            ephemeral=True
        )
        return

    # Verificar que quien invita es Líder o Co-Líder
    rol_invitador = obtener_rol_miembro(clan, interaction.user.id)
    if rol_invitador not in ['Líder', 'Co-Líder']:
        await interaction.response.send_message(
            "❌ Solo Líderes y Co-Líderes pueden invitar miembros.",
            ephemeral=True
        )
        return

    # Verificar que el usuario no esté en el clan
    if es_miembro_clan(clan, usuario.id):
        await interaction.response.send_message(
            f"❌ {usuario.mention} ya es miembro del clan.",
            ephemeral=True
        )
        return

    # Verificar límite de miembros
    clan_info = obtener_clan(clan)
    if clan_info['total_miembros'] >= clan_info['limite_miembros']:
        await interaction.response.send_message(
            f"❌ El clan ha alcanzado su límite de {clan_info['limite_miembros']} miembros.\n"
            f"Sube de nivel el clan para aumentar el límite.",
            ephemeral=True
        )
        return

    await interaction.response.defer(ephemeral=True)

    # Crear invitación en DB
    invitacion_id = crear_invitacion(
        clan_nombre=clan,
        usuario_invitado_id=usuario.id,
        usuario_que_invita_id=interaction.user.id,
        rol_asignado=rol.value,
        horas_expiracion=48
    )

    if not invitacion_id:
        await interaction.followup.send(
            "❌ Error al crear la invitación.",
            ephemeral=True
        )
        return

    # Enviar DM al usuario
    try:
        embed = discord.Embed(
            title="🏰 Invitación a Clan",
            description=f"{interaction.user.mention} te ha invitado a unirte al clan **{clan}**",
            color=0x00ff00
        )

        embed.add_field(
            name="📋 Información del Clan",
            value=f"**Nivel:** {clan_info['nivel']} ({'⭐' * clan_info['nivel']})\n"
                  f"**Miembros:** {clan_info['total_miembros']}/{clan_info['limite_miembros']}\n"
                  f"**Descripción:** {clan_info['descripcion'] or 'Sin descripción'}",
            inline=False
        )

        embed.add_field(
            name="🎭 Rol que recibirás",
            value=rol.value,
            inline=True
        )

        embed.add_field(
            name="⏰ Expiración",
            value="48 horas",
            inline=True
        )

        view = InvitacionView(invitacion_id)
        await usuario.send(embed=embed, view=view)

        await interaction.followup.send(
            f"✅ Invitación enviada a {usuario.mention}",
            ephemeral=True
        )

    except discord.Forbidden:
        await interaction.followup.send(
            f"❌ No pude enviar DM a {usuario.mention}. Sus DMs están cerrados.",
            ephemeral=True
        )

# ==================== COMANDOS DE ADMINISTRACIÓN DEL CLAN ====================

@bot.tree.command(name='agregar_canal', description='Agregar un canal al clan')
@app_commands.describe(
    tipo='Tipo de canal',
    nombre='Nombre del canal'
)
@app_commands.choices(tipo=[
    app_commands.Choice(name='💬 Texto', value='texto'),
    app_commands.Choice(name='🔊 Voz', value='voz'),
])
async def agregar_canal(interaction: discord.Interaction, tipo: app_commands.Choice[str], nombre: str):
    """Agregar un canal de texto o voz al clan"""

    # Verificar que se use en un canal de administración
    clan_nombre = obtener_clan_por_canal_admin(interaction.channel.id)

    if not clan_nombre:
        await interaction.response.send_message(
            "❌ Este comando solo se puede usar en el canal de administración del clan.",
            ephemeral=True
        )
        return

    # Verificar permisos
    rol_usuario = obtener_rol_miembro(clan_nombre, interaction.user.id)
    if rol_usuario not in ['Líder', 'Co-Líder'] and not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message(
            "❌ Solo Líderes, Co-Líderes o Administradores pueden agregar canales.",
            ephemeral=True
        )
        return

    # Verificar límite de canales según nivel
    clan_info = obtener_clan(clan_nombre)
    canales_usados = contar_canales_extra(clan_nombre, tipo.value)

    limite = clan_info[f'limite_canales_{tipo.value}']

    if canales_usados >= limite:
        await interaction.response.send_message(
            f"❌ Has alcanzado el límite de canales de {tipo.name}: {canales_usados}/{limite}\n"
            f"Sube de nivel el clan para desbloquear más canales.",
            ephemeral=True
        )
        return

    await interaction.response.defer()

    try:
        guild = interaction.guild
        categoria_id = clan_info['categoria_id']
        categoria = guild.get_channel(categoria_id)
        clan_role = guild.get_role(clan_info['rol_id'])

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            clan_role: discord.PermissionOverwrite(read_messages=True),
            guild.me: discord.PermissionOverwrite(read_messages=True)
        }

        for role in guild.roles:
            if role.permissions.administrator:
                overwrites[role] = discord.PermissionOverwrite(read_messages=True)

        if tipo.value == 'texto':
            nuevo_canal = await categoria.create_text_channel(
                nombre,
                overwrites=overwrites
            )
        else:  # voz
            nuevo_canal = await categoria.create_voice_channel(
                nombre,
                overwrites=overwrites
            )

        # Guardar en DB
        agregar_canal_extra(clan_nombre, nuevo_canal.id, nombre, tipo.value)

        await interaction.followup.send(
            f"✅ Canal {tipo.name} **{nombre}** creado: {nuevo_canal.mention if tipo.value == 'texto' else nuevo_canal.name}\n"
            f"Canales {tipo.name}: {canales_usados + 1}/{limite}"
        )

    except Exception as e:
        logger.error(f"Error al crear canal: {e}")
        await interaction.followup.send(
            f"❌ Error al crear el canal: {str(e)}"
        )

@bot.tree.command(name='stats_clan', description='Ver estadísticas del clan')
async def stats_clan(interaction: discord.Interaction):
    """Ver estadísticas y progreso del clan"""

    # Verificar que se use en un canal del clan
    clan_nombre = obtener_clan_por_canal_admin(interaction.channel.id)

    if not clan_nombre:
        await interaction.response.send_message(
            "❌ Este comando solo se puede usar en canales del clan.",
            ephemeral=True
        )
        return

    clan_info = obtener_clan(clan_nombre)
    nivel_config = NIVELES_CLAN[clan_info['nivel']]

    embed = discord.Embed(
        title=f"📊 Estadísticas de {clan_nombre}",
        color=0x0099ff
    )

    # Nivel y XP
    if clan_info['nivel'] < 6:
        xp_para_siguiente = clan_info['xp_siguiente_nivel'] - clan_info['xp_actual']
        progreso = (clan_info['xp_actual'] / clan_info['xp_siguiente_nivel']) * 100

        embed.add_field(
            name="💎 Experiencia",
            value=f"**Nivel:** {clan_info['nivel']} {'⭐' * clan_info['nivel']}\n"
                  f"**XP:** {clan_info['xp_actual']}/{clan_info['xp_siguiente_nivel']}\n"
                  f"**Progreso:** {progreso:.1f}%\n"
                  f"**Faltan:** {xp_para_siguiente} XP para nivel {clan_info['nivel'] + 1}",
            inline=False
        )
    else:
        embed.add_field(
            name="💎 Experiencia",
            value=f"**Nivel:** 6 ⭐⭐⭐⭐⭐⭐ (MÁXIMO)\n"
                  f"**XP:** {clan_info['xp_actual']}",
            inline=False
        )

    # Miembros
    embed.add_field(
        name="👥 Miembros",
        value=f"{clan_info['total_miembros']}/{nivel_config['limite_miembros']}",
        inline=True
    )

    # Canales
    canales_texto = contar_canales_extra(clan_nombre, 'texto')
    canales_voz = contar_canales_extra(clan_nombre, 'voz')

    embed.add_field(
        name="📁 Canales",
        value=f"💬 Texto: {canales_texto}/{nivel_config['canales_texto']}\n"
              f"🔊 Voz: {canales_voz}/{nivel_config['canales_voz']}",
        inline=True
    )

    # Siguiente nivel
    if clan_info['nivel'] < 6:
        siguiente_nivel = NIVELES_CLAN[clan_info['nivel'] + 1]
        embed.add_field(
            name=f"🎯 Al alcanzar Nivel {clan_info['nivel'] + 1}",
            value=f"👥 Miembros: {siguiente_nivel['limite_miembros']}\n"
                  f"💬 Canales texto: {siguiente_nivel['canales_texto']}\n"
                  f"🔊 Canales voz: {siguiente_nivel['canales_voz']}",
            inline=False
        )

    await interaction.response.send_message(embed=embed)

@bot.tree.command(name='gestionar_miembros', description='Ver y gestionar miembros del clan')
async def gestionar_miembros(interaction: discord.Interaction):
    """Ver lista de miembros del clan con sus roles"""

    # Verificar que se use en canal de admin
    clan_nombre = obtener_clan_por_canal_admin(interaction.channel.id)

    if not clan_nombre:
        await interaction.response.send_message(
            "❌ Este comando solo se puede usar en el canal de administración.",
            ephemeral=True
        )
        return

    # Verificar permisos
    rol_usuario = obtener_rol_miembro(clan_nombre, interaction.user.id)
    if rol_usuario not in ['Líder', 'Co-Líder'] and not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message(
            "❌ Solo Líderes y Co-Líderes pueden gestionar miembros.",
            ephemeral=True
        )
        return

    miembros = obtener_miembros_clan(clan_nombre)

    if not miembros:
        await interaction.response.send_message(
            "❌ No hay miembros en este clan.",
            ephemeral=True
        )
        return

    embed = discord.Embed(
        title=f"👥 Miembros de {clan_nombre}",
        description=f"Total: {len(miembros)} miembros",
        color=0x0099ff
    )

    # Agrupar por rol
    roles = {'Líder': [], 'Co-Líder': [], 'Miembro': [], 'Recluta': []}

    for miembro in miembros:
        usuario = interaction.guild.get_member(miembro['usuario_id'])
        if usuario:
            roles[miembro['rol']].append(usuario.mention)

    for rol, usuarios in roles.items():
        if usuarios:
            emoji = {'Líder': '👑', 'Co-Líder': '⚔️', 'Miembro': '🛡️', 'Recluta': '🗡️'}[rol]
            embed.add_field(
                name=f"{emoji} {rol} ({len(usuarios)})",
                value='\n'.join(usuarios) or 'Ninguno',
                inline=False
            )

    await interaction.response.send_message(embed=embed)

@bot.tree.command(name='ver_invitacion', description='Ver la invitación secreta del clan')
async def ver_invitacion(interaction: discord.Interaction):
    """Mostrar la invitación permanente del clan (solo para Líder y admins)"""

    # Verificar que se use en canal de admin
    clan_nombre = obtener_clan_por_canal_admin(interaction.channel.id)

    if not clan_nombre:
        await interaction.response.send_message(
            "❌ Este comando solo se puede usar en el canal de administración.",
            ephemeral=True
        )
        return

    # Verificar permisos (solo Líder o Admin servidor)
    rol_usuario = obtener_rol_miembro(clan_nombre, interaction.user.id)
    if rol_usuario != 'Líder' and not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message(
            "❌ Solo el Líder del clan o Administradores del servidor pueden ver la invitación.",
            ephemeral=True
        )
        return

    clan_info = obtener_clan(clan_nombre)

    embed = discord.Embed(
        title="🔐 Invitación Secreta del Clan",
        description=f"**Enlace permanente:**\nhttps://discord.gg/{clan_info['invite_code']}\n\n"
                    f"⚠️ **IMPORTANTE:**\n"
                    f"• Esta invitación nunca expira\n"
                    f"• Compártela solo con personas de confianza\n"
                    f"• Para invitaciones oficiales, usa `/invitar_clan`",
        color=0xff9900
    )

    await interaction.response.send_message(embed=embed, ephemeral=True)

# ==================== EJECUTAR BOT ====================

if __name__ == '__main__':
    bot.run(os.getenv('DISCORD_TOKEN'))
