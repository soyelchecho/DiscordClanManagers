#!/bin/bash

# Script de instalación automática para DigitalOcean Droplet
# Discord Clan Manager Bot

echo "🚀 Iniciando instalación del Discord Clan Manager Bot..."

# Colores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Función para imprimir con color
print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

print_error() {
    echo -e "${RED}✗ $1${NC}"
}

print_info() {
    echo -e "${YELLOW}ℹ $1${NC}"
}

# Verificar que se está ejecutando como root
if [ "$EUID" -ne 0 ]; then
    print_error "Por favor ejecuta este script como root (usa sudo)"
    exit 1
fi

print_info "Paso 1: Actualizando el sistema..."
apt update && apt upgrade -y
print_success "Sistema actualizado"

print_info "Paso 2: Instalando dependencias..."
apt install -y python3 python3-pip git nano ufw htop fail2ban
print_success "Dependencias instaladas"

print_info "Paso 3: Configurando firewall..."
ufw --force enable
ufw allow OpenSSH
print_success "Firewall configurado"

print_info "Paso 4: Configurando fail2ban para seguridad..."
systemctl enable fail2ban
systemctl start fail2ban
print_success "Fail2ban configurado"

print_info "Paso 5: Creando usuario 'botuser'..."
if id "botuser" &>/dev/null; then
    print_info "Usuario 'botuser' ya existe, saltando..."
else
    adduser --disabled-password --gecos "" botuser
    usermod -aG sudo botuser
    print_success "Usuario 'botuser' creado"
fi

print_info "Paso 6: Configurando directorio del bot..."
BOT_DIR="/home/botuser/DiscordClanManagers"
mkdir -p "$BOT_DIR"

print_info "Paso 7: Instalando dependencias de Python..."
pip3 install discord.py python-dotenv

print_success "Dependencias de Python instaladas"

print_info "Paso 8: Configurando memoria swap (2GB)..."
if [ -f /swapfile ]; then
    print_info "Swap ya existe, saltando..."
else
    fallocate -l 2G /swapfile
    chmod 600 /swapfile
    mkswap /swapfile
    swapon /swapfile
    echo '/swapfile none swap sw 0 0' >> /etc/fstab
    print_success "Swap configurado (2GB)"
fi

print_info "Paso 9: Creando archivo de servicio systemd..."
cat > /etc/systemd/system/discord-clan-bot.service <<EOF
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

# Seguridad adicional
NoNewPrivileges=true
PrivateTmp=true

# Logs
StandardOutput=append:/home/botuser/DiscordClanManagers/bot.log
StandardError=append:/home/botuser/DiscordClanManagers/bot_error.log

[Install]
WantedBy=multi-user.target
EOF

print_success "Servicio systemd creado"

print_info "Paso 10: Configurando permisos..."
chown -R botuser:botuser "$BOT_DIR"
chmod -R 755 "$BOT_DIR"
print_success "Permisos configurados"

echo ""
print_success "========================================="
print_success "  Instalación completada exitosamente"
print_success "========================================="
echo ""
print_info "Próximos pasos:"
echo "  1. Sube los archivos del bot a: $BOT_DIR"
echo "  2. Crea el archivo .env con tu token de Discord"
echo "  3. Ejecuta: sudo systemctl daemon-reload"
echo "  4. Ejecuta: sudo systemctl enable discord-clan-bot"
echo "  5. Ejecuta: sudo systemctl start discord-clan-bot"
echo "  6. Verifica: sudo systemctl status discord-clan-bot"
echo ""
print_info "Para ver logs en tiempo real:"
echo "  tail -f /home/botuser/DiscordClanManagers/bot.log"
echo ""
print_info "Para reiniciar el bot:"
echo "  sudo systemctl restart discord-clan-bot"
echo ""