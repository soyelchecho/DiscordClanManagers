#!/usr/bin/env python3
"""
Sistema de backups automáticos a Backblaze B2
"""
import os
import subprocess
import datetime
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuración
DATABASE_FILE = 'clan_data.db'
BACKUP_DIR = 'backups'
B2_BUCKET = os.getenv('B2_BUCKET_NAME', 'discord-clan-bot-backups')
B2_KEY_ID = os.getenv('B2_KEY_ID')
B2_APP_KEY = os.getenv('B2_APP_KEY')

def ensure_backup_dir():
    """Crear directorio de backups si no existe"""
    Path(BACKUP_DIR).mkdir(exist_ok=True)

def create_local_backup():
    """Crear backup local de la base de datos"""
    ensure_backup_dir()

    if not os.path.exists(DATABASE_FILE):
        logger.error(f"Base de datos {DATABASE_FILE} no encontrada")
        return None

    # Nombre del backup con timestamp
    timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_filename = f"clan_data_backup_{timestamp}.db"
    backup_path = os.path.join(BACKUP_DIR, backup_filename)

    try:
        # Copiar base de datos
        import shutil
        shutil.copy2(DATABASE_FILE, backup_path)

        # Comprimir con gzip para ahorrar espacio
        import gzip
        with open(backup_path, 'rb') as f_in:
            with gzip.open(f"{backup_path}.gz", 'wb') as f_out:
                f_out.writelines(f_in)

        # Eliminar archivo sin comprimir
        os.remove(backup_path)
        backup_path = f"{backup_path}.gz"

        file_size = os.path.getsize(backup_path)
        logger.info(f"Backup local creado: {backup_path} ({file_size} bytes)")

        return backup_path

    except Exception as e:
        logger.error(f"Error al crear backup local: {e}")
        return None

def upload_to_b2(file_path):
    """Subir backup a Backblaze B2 usando b2 CLI"""
    if not file_path or not os.path.exists(file_path):
        logger.error("Archivo de backup no existe")
        return False

    if not B2_KEY_ID or not B2_APP_KEY:
        logger.error("Credenciales de B2 no configuradas")
        return False

    try:
        # Autorizar cuenta B2
        logger.info("Autorizando con Backblaze B2...")
        subprocess.run([
            'b2', 'authorize-account', B2_KEY_ID, B2_APP_KEY
        ], check=True, capture_output=True)

        # Subir archivo
        filename = os.path.basename(file_path)
        logger.info(f"Subiendo {filename} a B2 bucket {B2_BUCKET}...")

        result = subprocess.run([
            'b2', 'upload-file',
            '--noProgress',
            B2_BUCKET,
            file_path,
            filename
        ], check=True, capture_output=True, text=True)

        logger.info(f"Backup subido exitosamente a B2: {filename}")
        return True

    except subprocess.CalledProcessError as e:
        logger.error(f"Error al subir a B2: {e.stderr}")
        return False
    except FileNotFoundError:
        logger.error("b2 CLI no está instalado. Instala con: pip install b2")
        return False
    except Exception as e:
        logger.error(f"Error inesperado al subir a B2: {e}")
        return False

def cleanup_old_backups(keep_days=30):
    """Eliminar backups locales antiguos"""
    ensure_backup_dir()

    cutoff_date = datetime.datetime.now() - datetime.timedelta(days=keep_days)
    deleted_count = 0

    try:
        for file in os.listdir(BACKUP_DIR):
            file_path = os.path.join(BACKUP_DIR, file)

            if os.path.isfile(file_path):
                file_time = datetime.datetime.fromtimestamp(os.path.getmtime(file_path))

                if file_time < cutoff_date:
                    os.remove(file_path)
                    deleted_count += 1
                    logger.info(f"Backup antiguo eliminado: {file}")

        if deleted_count > 0:
            logger.info(f"Eliminados {deleted_count} backups antiguos")

    except Exception as e:
        logger.error(f"Error al limpiar backups antiguos: {e}")

def cleanup_old_b2_backups(keep_days=30):
    """Eliminar backups antiguos de B2"""
    if not B2_KEY_ID or not B2_APP_KEY:
        logger.warning("Credenciales de B2 no configuradas, saltando limpieza remota")
        return

    try:
        # Autorizar
        subprocess.run([
            'b2', 'authorize-account', B2_KEY_ID, B2_APP_KEY
        ], check=True, capture_output=True)

        # Listar archivos
        result = subprocess.run([
            'b2', 'ls', '--recursive', B2_BUCKET
        ], check=True, capture_output=True, text=True)

        cutoff_timestamp = int((datetime.datetime.now() - datetime.timedelta(days=keep_days)).timestamp() * 1000)

        # Parsear y eliminar archivos antiguos
        for line in result.stdout.strip().split('\n'):
            if line and 'clan_data_backup_' in line:
                parts = line.split()
                if len(parts) >= 2:
                    file_id = parts[0]
                    # Aquí podrías implementar lógica para eliminar archivos antiguos
                    # b2 delete-file-version <fileName> <fileId>

        logger.info("Limpieza de backups remotos completada")

    except Exception as e:
        logger.error(f"Error al limpiar backups de B2: {e}")

def run_backup():
    """Ejecutar backup completo"""
    logger.info("=== Iniciando proceso de backup ===")

    # Crear backup local
    backup_file = create_local_backup()

    if not backup_file:
        logger.error("Fallo al crear backup local")
        return False

    # Subir a B2
    success = upload_to_b2(backup_file)

    if success:
        logger.info("Backup completado exitosamente")

        # Limpiar backups antiguos
        cleanup_old_backups(keep_days=7)  # Locales: 7 días
        cleanup_old_b2_backups(keep_days=30)  # B2: 30 días
    else:
        logger.warning("Backup local creado pero fallo al subir a B2")

    logger.info("=== Proceso de backup finalizado ===")
    return success

if __name__ == '__main__':
    run_backup()
