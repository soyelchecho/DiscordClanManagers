# 🏰 Discord Clan Manager Bot

Bot completo de Discord para gestionar clanes con roles, canales privados, invitaciones permanentes y backups automáticos en la nube.

---

## 📑 Tabla de Contenidos

1. [Características](#-características)
2. [Arquitectura del Sistema](#-arquitectura-del-sistema)
3. [Configuración Inicial](#-configuración-inicial)
4. [Uso del Bot](#-uso-del-bot)
5. [Deployment en DigitalOcean](#-deployment-en-digitalocean)
6. [Sistema de Backups con Backblaze B2](#-sistema-de-backups-con-backblaze-b2)
7. [Estructura del Proyecto](#-estructura-del-proyecto)
8. [Solución de Problemas](#-solución-de-problemas)

---

## 🚀 Características

- ✅ **Sistema de Tickets**: Botones para abrir tickets privados (threads)
- ✅ **Gestión de Clanes**: Crear clanes con roles y categorías automáticas
- ✅ **Canales Privados**: Cada clan tiene canales que solo ven sus miembros + admins
- ✅ **Invitaciones Permanentes**: Enlaces que nunca expiran
- ✅ **Base de datos SQLite**: Robusta, con transacciones ACID
- ✅ **Backups Automáticos**: A Backblaze B2 cada 6 horas
- ✅ **Slash Commands**: Comandos modernos con `/`
- ✅ **Restauración de Backups**: Sistema completo de recuperación

---

## 🏗️ Arquitectura del Sistema

```
┌─────────────────────────────────────────────────────────┐
│                    DISCORD SERVER                        │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │  Categoría   │  │  Categoría   │  │  Categoría   │  │
│  │   Clan A     │  │   Clan B     │  │   Clan C     │  │
│  └──────────────┘  └──────────────┘  └──────────────┘  │
└─────────────────────────────────────────────────────────┘
                         ↓ Gestiona
┌─────────────────────────────────────────────────────────┐
│              DISCORD CLAN MANAGER BOT                    │
│                  (Python + Discord.py)                   │
└─────────────────────────────────────────────────────────┘
                         ↓ Guarda datos
┌─────────────────────────────────────────────────────────┐
│                   SQLite Database                        │
│                  (clan_data.db)                          │
└─────────────────────────────────────────────────────────┘
                         ↓ Backup cada 6h
┌─────────────────────────────────────────────────────────┐
│              Backblaze B2 Cloud Storage                  │
│           (Backups comprimidos últimos 30 días)          │
└─────────────────────────────────────────────────────────┘

Host: DigitalOcean Droplet (Ubuntu 22.04)
```

---

## ⚙️ Configuración Inicial

### 1️⃣ Crear Bot en Discord

1. Ve a https://discord.com/developers/applications
2. Click **New Application** → Pon un nombre
3. Ve a **Bot** → Click **Add Bot**
4. Copia el **Token** (lo usarás después)
5. Activa estos **Privileged Gateway Intents**:
   - ✅ Message Content Intent
   - ✅ Server Members Intent
6. Ve a **OAuth2 > URL Generator**:
   - **Scopes**: `bot`, `applications.commands`
   - **Bot Permissions**:
     - Manage Roles
     - Manage Channels
     - Create Instant Invite
     - View Channels
     - Send Messages
     - Create Public/Private Threads
     - Send Messages in Threads
     - Manage Messages
     - Embed Links
7. Copia la URL generada e invita el bot a tu servidor

### 2️⃣ Configurar Variables de Entorno

Crea un archivo `.env` (copia de `.env.example`):

```bash
# Discord
DISCORD_TOKEN=MTIxxxxxxxxxxxxxxxxxxxxxxxxxxx.xxxxxx.xxxxxxxxxxxxxxxxxxxxxxxxxxx
GUILD_ID=123456789012345678
TICKET_CHANNEL_ID=123456789012345678

# Backblaze B2 (opcional, para backups automáticos)
B2_BUCKET_NAME=discord-clan-bot-backups
B2_KEY_ID=0031xxxxxxxxxxxxxxxxxxxx
B2_APP_KEY=K0031xxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

**Cómo obtener IDs:**
- Activa "Developer Mode" en Discord (Settings > Advanced > Developer Mode)
- Click derecho en servidor/canal → Copy ID

### 3️⃣ Instalar Dependencias (Local)

```bash
# Clonar repositorio
git clone https://github.com/tu-usuario/DiscordClanManagers.git
cd DiscordClanManagers

# Instalar dependencias
pip install -r requirements.txt

# Probar el bot
python main.py
```

---

## 🎮 Uso del Bot

### Comandos de Administración

#### `/setup_tickets`
**Quién puede usarlo:** Solo administradores del servidor

Crea el mensaje con botón para que los usuarios abran tickets y creen clanes.

```
/setup_tickets
```

### Comandos de Creación de Clanes

#### `/crear_clan`
**Dónde usarlo:** Dentro de un ticket (thread privado)

Crea un nuevo clan con toda su estructura.

```
/crear_clan nombre:Los Guerreros
```

**Esto crea automáticamente:**
- 🎭 Rol: `Clan-Los Guerreros`
- 📂 Categoría: `🏰 Los Guerreros`
- 📢 Canal de anuncios (solo admins escriben)
- ⚙️ Canal de administración (solo creador + admins)
- 💬 Canal general del clan
- 🔗 Invitación permanente

### Comandos del Creador del Clan

Estos comandos se usan en el **canal de administración** del clan:

#### `/agregar_canal_texto`
```
/agregar_canal_texto nombre_canal:estrategias
```

#### `/agregar_canal_voz`
```
/agregar_canal_voz nombre_canal:Sala de Guerra
```

#### `/listar_canales`
```
/listar_canales
```

### Comandos Públicos

#### `/info_clan`
Ver información de un clan específico o lista de todos los clanes.

```
/info_clan nombre_clan:Los Guerreros
/info_clan
```

---

## 🚀 Deployment en DigitalOcean

### Costos
- **Droplet**: $6-12/mes
- **Backblaze B2**: ~$0/mes (primeros 10GB gratis)
- **Total**: $6-12/mes

### Paso 1: Crear Droplet

1. Ve a https://www.digitalocean.com
2. Click **Create** → **Droplets**
3. Configuración:
   - **Region**: New York (mejor para Latinoamérica)
   - **Image**: Ubuntu 22.04 LTS
   - **Droplet Type**: Basic - Shared CPU
   - **CPU Options**: Regular (SSD)
   - **Size**:
     - $6/mo (1GB RAM) - Para empezar
     - $12/mo (2GB RAM) - Recomendado
   - **Authentication**: SSH Key (recomendado)
   - **Hostname**: `discord-clan-bot`
4. Click **Create Droplet**
5. Copia la IP asignada

### Paso 2: Conectar al Droplet

```bash
ssh root@TU_IP_AQUI
# Ingresa contraseña si no usas SSH key
```

### Paso 3: Configuración Automática

Ejecuta este script de instalación:

```bash
# Actualizar sistema
apt update && apt upgrade -y

# Instalar dependencias
apt install -y python3 python3-pip git nano ufw htop fail2ban

# Configurar firewall
ufw allow OpenSSH
ufw --force enable

# Crear usuario para el bot
adduser --disabled-password --gecos "" botuser
usermod -aG sudo botuser

# Cambiar a usuario botuser
su - botuser
```

### Paso 4: Subir Código del Bot

**Opción A: Usar Git**
```bash
cd ~
git clone https://github.com/TU_USUARIO/DiscordClanManagers.git
cd DiscordClanManagers
```

**Opción B: Subir archivos desde tu PC**
```bash
# En tu PC (PowerShell/CMD):
scp -r C:\Users\SergioR\Documents\PycharmProjects\DiscordClanManagers root@TU_IP:/home/botuser/
```

### Paso 5: Configurar el Bot

```bash
cd ~/DiscordClanManagers

# Instalar dependencias
pip3 install -r requirements.txt

# Configurar variables de entorno
nano .env
```

Pega tu configuración:
```
DISCORD_TOKEN=tu_token_aqui
GUILD_ID=tu_guild_id
TICKET_CHANNEL_ID=tu_canal_id

# Backblaze B2 (configurar después)
B2_BUCKET_NAME=discord-clan-bot-backups
B2_KEY_ID=
B2_APP_KEY=
```

Guardar: `Ctrl + O` → Enter → `Ctrl + X`

### Paso 6: Probar el Bot

```bash
python3 main.py
```

Deberías ver:
```
Bot ha iniciado sesión
Bot conectado a 1 servidores
Base de datos SQLite inicializada
Sincronizados 6 comandos de barra
```

Si funciona, presiona `Ctrl + C` para detener.

### Paso 7: Configurar como Servicio (Autostart)

Volver a root:
```bash
exit  # Salir de botuser
```

Crear servicio systemd:
```bash
nano /etc/systemd/system/discord-clan-bot.service
```

Pegar esta configuración:
```ini
[Unit]
Description=Discord Clan Manager Bot
After=network.target

[Service]
Type=simple
User=botuser
WorkingDirectory=/home/botuser/DiscordClanManagers
ExecStart=/usr/bin/python3 /home/botuser/DiscordClanManagers/main.py
Restart=always
RestartSec=10

NoNewPrivileges=true
PrivateTmp=true

StandardOutput=append:/home/botuser/DiscordClanManagers/bot.log
StandardError=append:/home/botuser/DiscordClanManagers/bot_error.log

[Install]
WantedBy=multi-user.target
```

Guardar y activar:
```bash
systemctl daemon-reload
systemctl enable discord-clan-bot.service
systemctl start discord-clan-bot.service

# Verificar estado
systemctl status discord-clan-bot.service
```

Deberías ver **active (running)** en verde ✅

### Paso 8: Configurar Memoria Swap (Opcional)

Si tu Droplet tiene poca RAM:

```bash
fallocate -l 2G /swapfile
chmod 600 /swapfile
mkswap /swapfile
swapon /swapfile
echo '/swapfile none swap sw 0 0' >> /etc/fstab
```

### Comandos Útiles del Droplet

**Ver logs en tiempo real:**
```bash
tail -f /home/botuser/DiscordClanManagers/bot.log
```

**Reiniciar bot:**
```bash
systemctl restart discord-clan-bot
```

**Ver estado:**
```bash
systemctl status discord-clan-bot
```

**Detener bot:**
```bash
systemctl stop discord-clan-bot
```

**Actualizar código:**
```bash
# Subir nuevos archivos desde tu PC
scp main.py root@TU_IP:/home/botuser/DiscordClanManagers/

# Reiniciar bot
systemctl restart discord-clan-bot
```

---

## 💾 Sistema de Backups con Backblaze B2

### Por Qué Backblaze B2

- 💰 **10 GB gratis** permanentemente
- 📦 Costo después: $0.006/GB/mes (~$0.10/mes para el bot)
- ☁️ Backups en la nube (seguro si el Droplet falla)
- 🔄 Restauración fácil
- 🤝 Compatible con API de S3

### Paso 1: Crear Cuenta en Backblaze B2

1. Ve a https://www.backblaze.com/b2/sign-up.html
2. Regístrate (gratis, sin tarjeta de crédito para empezar)
3. Verifica tu email
4. Inicia sesión en https://www.backblaze.com

### Paso 2: Crear Bucket

1. En el dashboard, click **B2 Cloud Storage**
2. Click **Create a Bucket**
3. Configuración:
   - **Bucket Name**: `discord-clan-bot-backups`
   - **Files in Bucket**: Private
   - **Object Lock**: Disabled
   - **Encryption**: Disabled
4. Click **Create a Bucket**

### Paso 3: Crear Application Key

1. En el menú, click **App Keys**
2. Click **Add a New Application Key**
3. Configuración:
   - **Name**: `discord-bot-backup-key`
   - **Allow access to Bucket(s)**: Selecciona `discord-clan-bot-backups`
   - **Type of Access**: Read and Write
   - **Allow List All Bucket Names**: ✓
4. Click **Create New Key**
5. **⚠️ IMPORTANTE**: Copia y guarda inmediatamente:
   - **keyID**: `0031xxxxxxxxxxxxx`
   - **applicationKey**: `K0031xxxxxxxxxxxxxx`

   ⚠️ La applicationKey solo se muestra una vez!

### Paso 4: Configurar Credenciales en el Droplet

```bash
ssh root@TU_IP

# Editar .env
nano /home/botuser/DiscordClanManagers/.env
```

Agregar las credenciales de B2:
```bash
B2_BUCKET_NAME=discord-clan-bot-backups
B2_KEY_ID=0031xxxxxxxxxxxxxxxxxxxx
B2_APP_KEY=K0031xxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

### Paso 5: Instalar B2 CLI

```bash
pip3 install b2

# Verificar instalación
b2 version
```

### Paso 6: Probar Backup Manual

```bash
cd /home/botuser/DiscordClanManagers
python3 backup_manager.py
```

Deberías ver:
```
=== Iniciando proceso de backup ===
Backup local creado: backups/clan_data_backup_20250121_143022.db.gz
Autorizando con Backblaze B2...
Subiendo clan_data_backup_20250121_143022.db.gz a B2...
Backup subido exitosamente a B2
=== Proceso de backup finalizado ===
```

### Paso 7: Configurar Backups Automáticos

**Opción A: Cron Job (Más simple)**

```bash
# Editar crontab del usuario botuser
su - botuser
crontab -e

# Agregar esta línea (backup cada 6 horas):
0 */6 * * * cd /home/botuser/DiscordClanManagers && /usr/bin/python3 backup_manager.py >> /home/botuser/backup.log 2>&1

# Guardar y salir
```

**Opción B: Systemd Timer (Más robusto)**

Volver a root:
```bash
exit
```

Crear servicio:
```bash
nano /etc/systemd/system/discord-bot-backup.service
```

Contenido:
```ini
[Unit]
Description=Discord Bot Backup Service
After=network.target

[Service]
Type=oneshot
User=botuser
WorkingDirectory=/home/botuser/DiscordClanManagers
ExecStart=/usr/bin/python3 /home/botuser/DiscordClanManagers/backup_manager.py
StandardOutput=append:/home/botuser/backup.log
StandardError=append:/home/botuser/backup_error.log
```

Crear timer:
```bash
nano /etc/systemd/system/discord-bot-backup.timer
```

Contenido:
```ini
[Unit]
Description=Discord Bot Backup Timer
Requires=discord-bot-backup.service

[Timer]
OnBootSec=15min
OnUnitActiveSec=6h
Persistent=true

[Install]
WantedBy=timers.target
```

Activar:
```bash
systemctl daemon-reload
systemctl enable discord-bot-backup.timer
systemctl start discord-bot-backup.timer

# Verificar
systemctl status discord-bot-backup.timer
```

### Paso 8: Verificar Backups

**Ver logs de backup:**
```bash
tail -f /home/botuser/backup.log
```

**Listar backups locales:**
```bash
ls -lh /home/botuser/DiscordClanManagers/backups/
```

**Listar backups en B2:**
```bash
b2 authorize-account $B2_KEY_ID $B2_APP_KEY
b2 ls --recursive discord-clan-bot-backups
```

### Restaurar Backups

**Script Interactivo:**

```bash
cd /home/botuser/DiscordClanManagers
python3 restore_backup.py
```

Menú:
```
=== Restauración de Backup ===

Opciones:
1. Restaurar desde backup local
2. Restaurar desde Backblaze B2
3. Salir

Selecciona una opción (1-3):
```

**Restauración Manual desde B2:**

```bash
# 1. Listar backups disponibles
b2 authorize-account $B2_KEY_ID $B2_APP_KEY
b2 ls discord-clan-bot-backups

# 2. Descargar backup específico
b2 download-file-by-name discord-clan-bot-backups clan_data_backup_20250121_143022.db.gz /tmp/backup.db.gz

# 3. Restaurar
cd /home/botuser/DiscordClanManagers
python3 -c "from restore_backup import restore_backup; restore_backup('/tmp/backup.db.gz')"

# 4. Reiniciar bot
systemctl restart discord-clan-bot
```

### Limpieza de Backups Antiguos

El sistema limpia automáticamente:
- **Backups locales**: Últimos 7 días
- **Backups en B2**: Últimos 30 días

---

## 📂 Estructura del Proyecto

```
DiscordClanManagers/
├── main.py                  # Bot principal
├── database.py              # Manejo de SQLite
├── backup_manager.py        # Sistema de backups a B2
├── restore_backup.py        # Restauración de backups
├── requirements.txt         # Dependencias Python
├── .env.example            # Plantilla de configuración
├── .gitignore              # Archivos a ignorar en Git
├── README.md               # Esta documentación
├── setup_server.sh         # Script de instalación del servidor
│
├── clan_data.db            # Base de datos SQLite (generado)
├── backups/                # Backups locales (generado)
│   └── clan_data_backup_*.db.gz
│
└── *.log                   # Archivos de logs (generados)
```

### Componentes Principales

#### `main.py`
Bot de Discord con todos los comandos:
- Sistema de tickets con botones
- Creación y gestión de clanes
- Slash commands modernos
- Integración con database.py

#### `database.py`
Manejo completo de SQLite:
- Context managers para conexiones
- Funciones CRUD (Create, Read, Update, Delete)
- Migración automática desde JSON
- Transacciones ACID (no se corrompe)

#### `backup_manager.py`
Sistema de backups:
- Compresión con gzip
- Subida a Backblaze B2
- Limpieza de backups antiguos
- Logging detallado

#### `restore_backup.py`
Sistema de restauración:
- Interfaz interactiva
- Descarga desde B2
- Backup de seguridad antes de restaurar
- Validación de archivos

---

## 🎯 Estructura de un Clan

Cuando se crea un clan, el bot genera automáticamente:

### Categoría: `🏰 Nombre del Clan`

**Canales base:**
- 📢 **anuncios** (solo admins escriben)
  - Contiene invitación permanente
  - Miembros del clan pueden leer
- ⚙️ **administracion** (solo creador + admins)
  - Panel de control del clan
  - Comandos de gestión
- 💬 **general** (todos los del clan)
  - Chat general del clan

**Canales adicionales:**
- Los que agregue el creador con `/agregar_canal_texto` o `/agregar_canal_voz`

### Rol: `Clan-[Nombre]`
- Hoisted (visible en lista de miembros)
- Permite acceso a todos los canales del clan
- Se asigna automáticamente con la invitación

### Permisos

| Tipo de Usuario | Permisos |
|-----------------|----------|
| **Admins del servidor** | Ver todos los canales de todos los clanes |
| **Creador del clan** | Gestionar solo su clan (agregar canales, etc) |
| **Miembros del clan** | Ver solo canales de su clan |
| **Otros usuarios** | No ven nada del clan |

---

## 🔧 Solución de Problemas

### El bot no inicia

**Ver logs:**
```bash
tail -f /home/botuser/DiscordClanManagers/bot_error.log
```

**Errores comunes:**

1. **Token inválido:**
   ```
   discord.errors.LoginFailure: Improper token has been passed
   ```
   Solución: Verifica el token en `.env`

2. **Intents no habilitados:**
   ```
   discord.errors.PrivilegedIntentsRequired
   ```
   Solución: Activa los intents en Discord Developer Portal

3. **Módulo no encontrado:**
   ```
   ModuleNotFoundError: No module named 'discord'
   ```
   Solución: `pip3 install -r requirements.txt`

### Los comandos no aparecen

```bash
# Verificar que el bot esté conectado
systemctl status discord-clan-bot

# Ver logs
tail -f /home/botuser/DiscordClanManagers/bot.log

# Reiniciar bot para forzar sync
systemctl restart discord-clan-bot
```

Espera 5-10 minutos para que Discord sincronice los comandos.

### Backups no se suben a B2

**Verificar credenciales:**
```bash
cat /home/botuser/DiscordClanManagers/.env | grep B2
```

**Probar autorización manual:**
```bash
b2 authorize-account $B2_KEY_ID $B2_APP_KEY
b2 ls discord-clan-bot-backups
```

**Ver logs de backup:**
```bash
tail -f /home/botuser/backup.log
```

### Base de datos corrupta

**Restaurar desde backup:**
```bash
cd /home/botuser/DiscordClanManagers
python3 restore_backup.py
```

Selecciona el backup más reciente de B2.

### Droplet sin memoria

**Verificar memoria:**
```bash
free -h
```

**Agregar swap:**
```bash
sudo fallocate -l 2G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
```

### Bot se cae constantemente

**Ver por qué se reinicia:**
```bash
sudo journalctl -u discord-clan-bot -n 100
```

**Verificar recursos:**
```bash
htop
```

Si el Droplet es muy pequeño, considera hacer upgrade:
- $6/mo → $12/mo (2GB RAM)

---

## 💰 Resumen de Costos

| Servicio | Costo | Detalle |
|----------|-------|---------|
| **DigitalOcean Droplet** | $6-12/mes | Servidor 24/7 |
| **Backblaze B2** | ~$0/mes | Primeros 10GB gratis |
| **Dominio** (opcional) | $10/año | Para URL personalizada |
| **Total mínimo** | **$6/mes** | ~$0.20 por día |

---

## 🎓 Resumen Rápido

### Para probar localmente:
```bash
git clone https://github.com/tu-usuario/DiscordClanManagers.git
cd DiscordClanManagers
pip install -r requirements.txt
cp .env.example .env
# Editar .env con tu token
python main.py
```

### Para deployar en producción:
1. Crear Droplet en DigitalOcean ($6-12/mes)
2. Seguir pasos de [Deployment](#-deployment-en-digitalocean)
3. Configurar backups en Backblaze B2 (gratis)
4. ¡Listo! Bot 24/7 con backups automáticos

### Comandos esenciales:
```bash
# Crear clan
/crear_clan nombre:Mi Clan

# Gestionar canales (en canal admin del clan)
/agregar_canal_texto nombre_canal:gaming
/agregar_canal_voz nombre_canal:Voz 1
/listar_canales

# Ver información
/info_clan nombre_clan:Mi Clan
/info_clan
```

---

## 📞 Soporte

Si tienes problemas:
1. Revisa la sección [Solución de Problemas](#-solución-de-problemas)
2. Verifica los logs del bot
3. Consulta la documentación de Discord.py: https://discordpy.readthedocs.io/

---

**¡Disfruta tu bot de clanes!** 🎮🏰
