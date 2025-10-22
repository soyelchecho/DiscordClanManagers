#!/usr/bin/env python3
"""
Script para restaurar backups desde Backblaze B2
"""
import os
import subprocess
import gzip
import shutil
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DATABASE_FILE = 'clan_data.db'
BACKUP_DIR = 'backups'
B2_BUCKET = os.getenv('B2_BUCKET_NAME', 'discord-clan-bot-backups')
B2_KEY_ID = os.getenv('B2_KEY_ID')
B2_APP_KEY = os.getenv('B2_APP_KEY')

def list_local_backups():
    """Listar backups locales disponibles"""
    if not os.path.exists(BACKUP_DIR):
        logger.warning("No hay directorio de backups")
        return []

    backups = []
    for file in sorted(os.listdir(BACKUP_DIR), reverse=True):
        if file.startswith('clan_data_backup_') and file.endswith('.gz'):
            file_path = os.path.join(BACKUP_DIR, file)
            file_size = os.path.getsize(file_path)
            backups.append({
                'filename': file,
                'path': file_path,
                'size': file_size
            })

    return backups

def list_b2_backups():
    """Listar backups disponibles en B2"""
    if not B2_KEY_ID or not B2_APP_KEY:
        logger.error("Credenciales de B2 no configuradas")
        return []

    try:
        # Autorizar
        subprocess.run([
            'b2', 'authorize-account', B2_KEY_ID, B2_APP_KEY
        ], check=True, capture_output=True)

        # Listar archivos
        result = subprocess.run([
            'b2', 'ls', '--recursive', '--json', B2_BUCKET
        ], check=True, capture_output=True, text=True)

        import json
        files = []

        for line in result.stdout.strip().split('\n'):
            if line:
                try:
                    file_info = json.loads(line)
                    if 'fileName' in file_info and 'clan_data_backup_' in file_info['fileName']:
                        files.append({
                            'filename': file_info['fileName'],
                            'file_id': file_info.get('fileId', ''),
                            'size': file_info.get('size', 0),
                            'upload_time': file_info.get('uploadTimestamp', 0)
                        })
                except json.JSONDecodeError:
                    pass

        return sorted(files, key=lambda x: x['upload_time'], reverse=True)

    except subprocess.CalledProcessError as e:
        logger.error(f"Error al listar backups de B2: {e.stderr}")
        return []
    except Exception as e:
        logger.error(f"Error inesperado: {e}")
        return []

def download_from_b2(filename, destination):
    """Descargar backup desde B2"""
    if not B2_KEY_ID or not B2_APP_KEY:
        logger.error("Credenciales de B2 no configuradas")
        return False

    try:
        # Autorizar
        subprocess.run([
            'b2', 'authorize-account', B2_KEY_ID, B2_APP_KEY
        ], check=True, capture_output=True)

        # Descargar archivo
        logger.info(f"Descargando {filename} desde B2...")
        subprocess.run([
            'b2', 'download-file-by-name',
            B2_BUCKET,
            filename,
            destination
        ], check=True, capture_output=True)

        logger.info(f"Descarga completada: {destination}")
        return True

    except subprocess.CalledProcessError as e:
        logger.error(f"Error al descargar desde B2: {e.stderr}")
        return False
    except Exception as e:
        logger.error(f"Error inesperado: {e}")
        return False

def restore_backup(backup_path, backup_current=True):
    """Restaurar backup a la base de datos principal"""
    if not os.path.exists(backup_path):
        logger.error(f"Archivo de backup no encontrado: {backup_path}")
        return False

    try:
        # Hacer backup de la base de datos actual
        if backup_current and os.path.exists(DATABASE_FILE):
            current_backup = f"{DATABASE_FILE}.before_restore"
            shutil.copy2(DATABASE_FILE, current_backup)
            logger.info(f"Base de datos actual respaldada en: {current_backup}")

        # Descomprimir backup
        temp_file = 'temp_restore.db'

        with gzip.open(backup_path, 'rb') as f_in:
            with open(temp_file, 'wb') as f_out:
                shutil.copyfileobj(f_in, f_out)

        # Reemplazar base de datos
        if os.path.exists(DATABASE_FILE):
            os.remove(DATABASE_FILE)

        shutil.move(temp_file, DATABASE_FILE)

        logger.info(f"✅ Backup restaurado exitosamente desde: {backup_path}")
        return True

    except Exception as e:
        logger.error(f"Error al restaurar backup: {e}")
        return False

def interactive_restore():
    """Restauración interactiva"""
    print("\n=== Restauración de Backup ===\n")

    print("Opciones:")
    print("1. Restaurar desde backup local")
    print("2. Restaurar desde Backblaze B2")
    print("3. Salir")

    choice = input("\nSelecciona una opción (1-3): ").strip()

    if choice == '1':
        # Restaurar desde local
        backups = list_local_backups()

        if not backups:
            print("\n❌ No hay backups locales disponibles")
            return

        print("\n📦 Backups locales disponibles:\n")
        for i, backup in enumerate(backups, 1):
            size_mb = backup['size'] / (1024 * 1024)
            print(f"{i}. {backup['filename']} ({size_mb:.2f} MB)")

        selection = input(f"\nSelecciona backup (1-{len(backups)}): ").strip()

        try:
            index = int(selection) - 1
            if 0 <= index < len(backups):
                backup_path = backups[index]['path']
                confirm = input(f"\n⚠️  Restaurar {backups[index]['filename']}? (s/n): ").lower()

                if confirm == 's':
                    if restore_backup(backup_path):
                        print("\n✅ Restauración completada exitosamente")
                    else:
                        print("\n❌ Error en la restauración")
                else:
                    print("\nRestauración cancelada")
            else:
                print("\n❌ Selección inválida")
        except ValueError:
            print("\n❌ Entrada inválida")

    elif choice == '2':
        # Restaurar desde B2
        backups = list_b2_backups()

        if not backups:
            print("\n❌ No hay backups en B2 o error al listar")
            return

        print("\n☁️  Backups en Backblaze B2:\n")
        for i, backup in enumerate(backups, 1):
            size_mb = backup['size'] / (1024 * 1024)
            print(f"{i}. {backup['filename']} ({size_mb:.2f} MB)")

        selection = input(f"\nSelecciona backup (1-{len(backups)}): ").strip()

        try:
            index = int(selection) - 1
            if 0 <= index < len(backups):
                filename = backups[index]['filename']
                confirm = input(f"\n⚠️  Descargar y restaurar {filename}? (s/n): ").lower()

                if confirm == 's':
                    # Crear directorio de backups si no existe
                    Path(BACKUP_DIR).mkdir(exist_ok=True)

                    # Descargar
                    download_path = os.path.join(BACKUP_DIR, filename)
                    if download_from_b2(filename, download_path):
                        # Restaurar
                        if restore_backup(download_path):
                            print("\n✅ Restauración completada exitosamente")
                        else:
                            print("\n❌ Error en la restauración")
                    else:
                        print("\n❌ Error al descargar backup")
                else:
                    print("\nRestauración cancelada")
            else:
                print("\n❌ Selección inválida")
        except ValueError:
            print("\n❌ Entrada inválida")

    elif choice == '3':
        print("\nSaliendo...")
        return

    else:
        print("\n❌ Opción inválida")

if __name__ == '__main__':
    interactive_restore()
