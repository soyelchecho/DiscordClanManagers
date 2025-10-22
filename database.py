import sqlite3
import json
from contextlib import contextmanager
from typing import Dict, List, Optional
import logging

logger = logging.getLogger(__name__)

DATABASE_FILE = 'clan_data.db'

@contextmanager
def get_db_connection():
    """Context manager para conexiones a la base de datos"""
    conn = sqlite3.connect(DATABASE_FILE)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception as e:
        conn.rollback()
        logger.error(f"Error en transacción de base de datos: {e}")
        raise
    finally:
        conn.close()

def init_database():
    """Inicializar la base de datos con las tablas necesarias"""
    with get_db_connection() as conn:
        cursor = conn.cursor()

        # Tabla de clanes
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS clanes (
                nombre TEXT PRIMARY KEY,
                creador_id INTEGER NOT NULL,
                rol_id INTEGER NOT NULL,
                categoria_id INTEGER NOT NULL,
                canal_anuncios_id INTEGER NOT NULL,
                canal_admin_id INTEGER NOT NULL,
                canal_general_id INTEGER NOT NULL,
                invite_code TEXT NOT NULL,
                fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Tabla de canales adicionales
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS canales_clan (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                clan_nombre TEXT NOT NULL,
                canal_id INTEGER NOT NULL,
                nombre TEXT NOT NULL,
                tipo TEXT NOT NULL,
                fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (clan_nombre) REFERENCES clanes(nombre) ON DELETE CASCADE
            )
        ''')

        # Índices para mejorar performance
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_canales_clan_nombre
            ON canales_clan(clan_nombre)
        ''')

        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_clanes_creador
            ON clanes(creador_id)
        ''')

        logger.info("Base de datos inicializada correctamente")

def migrate_from_json():
    """Migrar datos existentes de JSON a SQLite"""
    try:
        with open('clan_data.json', 'r', encoding='utf-8') as f:
            json_data = json.load(f)

        if not json_data:
            logger.info("No hay datos JSON para migrar")
            return

        with get_db_connection() as conn:
            cursor = conn.cursor()

            for nombre_clan, data in json_data.items():
                # Insertar clan
                cursor.execute('''
                    INSERT OR REPLACE INTO clanes
                    (nombre, creador_id, rol_id, categoria_id, canal_anuncios_id,
                     canal_admin_id, canal_general_id, invite_code)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    nombre_clan,
                    data['creador'],
                    data['rol_id'],
                    data['categoria_id'],
                    data['canal_anuncios_id'],
                    data['canal_admin_id'],
                    data['canal_general_id'],
                    data['invite_code']
                ))

                # Insertar canales adicionales
                for canal in data.get('canales_extra', []):
                    cursor.execute('''
                        INSERT INTO canales_clan (clan_nombre, canal_id, nombre, tipo)
                        VALUES (?, ?, ?, ?)
                    ''', (nombre_clan, canal['id'], canal['nombre'], canal['tipo']))

        logger.info(f"Migrados {len(json_data)} clanes desde JSON")

    except FileNotFoundError:
        logger.info("No se encontró archivo JSON para migrar")
    except Exception as e:
        logger.error(f"Error al migrar desde JSON: {e}")
        raise

# ========== FUNCIONES CRUD ==========

def crear_clan(nombre: str, creador_id: int, rol_id: int, categoria_id: int,
               canal_anuncios_id: int, canal_admin_id: int, canal_general_id: int,
               invite_code: str) -> bool:
    """Crear un nuevo clan"""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO clanes
                (nombre, creador_id, rol_id, categoria_id, canal_anuncios_id,
                 canal_admin_id, canal_general_id, invite_code)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (nombre, creador_id, rol_id, categoria_id, canal_anuncios_id,
                  canal_admin_id, canal_general_id, invite_code))
        return True
    except sqlite3.IntegrityError:
        logger.warning(f"El clan '{nombre}' ya existe")
        return False
    except Exception as e:
        logger.error(f"Error al crear clan: {e}")
        return False

def obtener_clan(nombre: str) -> Optional[Dict]:
    """Obtener información de un clan"""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM clanes WHERE nombre = ?', (nombre,))
            row = cursor.fetchone()

            if not row:
                return None

            # Obtener canales adicionales
            cursor.execute('''
                SELECT canal_id, nombre, tipo
                FROM canales_clan
                WHERE clan_nombre = ?
            ''', (nombre,))
            canales_extra = [
                {'id': r['canal_id'], 'nombre': r['nombre'], 'tipo': r['tipo']}
                for r in cursor.fetchall()
            ]

            return {
                'creador': row['creador_id'],
                'rol_id': row['rol_id'],
                'categoria_id': row['categoria_id'],
                'canal_anuncios_id': row['canal_anuncios_id'],
                'canal_admin_id': row['canal_admin_id'],
                'canal_general_id': row['canal_general_id'],
                'invite_code': row['invite_code'],
                'canales_extra': canales_extra
            }
    except Exception as e:
        logger.error(f"Error al obtener clan: {e}")
        return None

def obtener_todos_clanes() -> Dict[str, Dict]:
    """Obtener todos los clanes"""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT nombre FROM clanes')
            nombres = [row['nombre'] for row in cursor.fetchall()]

            return {nombre: obtener_clan(nombre) for nombre in nombres}
    except Exception as e:
        logger.error(f"Error al obtener todos los clanes: {e}")
        return {}

def clan_existe(nombre: str) -> bool:
    """Verificar si un clan existe"""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT 1 FROM clanes WHERE nombre = ? LIMIT 1', (nombre,))
            return cursor.fetchone() is not None
    except Exception as e:
        logger.error(f"Error al verificar clan: {e}")
        return False

def obtener_clan_por_canal_admin(canal_id: int) -> Optional[str]:
    """Obtener nombre del clan por ID del canal de administración"""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT nombre FROM clanes WHERE canal_admin_id = ?
            ''', (canal_id,))
            row = cursor.fetchone()
            return row['nombre'] if row else None
    except Exception as e:
        logger.error(f"Error al buscar clan por canal admin: {e}")
        return None

def agregar_canal_extra(clan_nombre: str, canal_id: int, nombre: str, tipo: str) -> bool:
    """Agregar un canal adicional al clan"""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO canales_clan (clan_nombre, canal_id, nombre, tipo)
                VALUES (?, ?, ?, ?)
            ''', (clan_nombre, canal_id, nombre, tipo))
        return True
    except Exception as e:
        logger.error(f"Error al agregar canal extra: {e}")
        return False

def eliminar_clan(nombre: str) -> bool:
    """Eliminar un clan y todos sus canales asociados"""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            # Los canales se eliminan automáticamente por CASCADE
            cursor.execute('DELETE FROM clanes WHERE nombre = ?', (nombre,))
        return True
    except Exception as e:
        logger.error(f"Error al eliminar clan: {e}")
        return False

def obtener_estadisticas() -> Dict:
    """Obtener estadísticas generales"""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()

            cursor.execute('SELECT COUNT(*) as total FROM clanes')
            total_clanes = cursor.fetchone()['total']

            cursor.execute('SELECT COUNT(*) as total FROM canales_clan')
            total_canales_extra = cursor.fetchone()['total']

            return {
                'total_clanes': total_clanes,
                'total_canales_extra': total_canales_extra
            }
    except Exception as e:
        logger.error(f"Error al obtener estadísticas: {e}")
        return {'total_clanes': 0, 'total_canales_extra': 0}
