import sqlite3
import json
from contextlib import contextmanager
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

DATABASE_FILE = 'clan_data.db'

# Configuración de niveles de clanes
NIVELES_CLAN = {
    1: {'xp_requerido': 0, 'limite_miembros': 10, 'canales_texto': 3, 'canales_voz': 2},
    2: {'xp_requerido': 500, 'limite_miembros': 20, 'canales_texto': 5, 'canales_voz': 3},
    3: {'xp_requerido': 1500, 'limite_miembros': 35, 'canales_texto': 8, 'canales_voz': 5},
    4: {'xp_requerido': 3500, 'limite_miembros': 50, 'canales_texto': 12, 'canales_voz': 7},
    5: {'xp_requerido': 7000, 'limite_miembros': 75, 'canales_texto': 15, 'canales_voz': 10},
    6: {'xp_requerido': 15000, 'limite_miembros': 100, 'canales_texto': 999, 'canales_voz': 999},
}

@contextmanager
def get_db_connection():
    """Context manager para conexiones a la base de datos"""
    conn = sqlite3.connect(DATABASE_FILE)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
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

        # Tabla de clanes (actualizada)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS clanes (
                nombre TEXT PRIMARY KEY,
                creador_id INTEGER NOT NULL,
                descripcion TEXT DEFAULT '',
                nivel INTEGER DEFAULT 1,
                xp_actual INTEGER DEFAULT 0,
                fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                total_miembros_actuales INTEGER DEFAULT 1,
                total_miembros_historico INTEGER DEFAULT 1,
                rol_id INTEGER NOT NULL,
                categoria_id INTEGER NOT NULL,
                canal_anuncios_id INTEGER NOT NULL,
                canal_admin_id INTEGER NOT NULL,
                canal_general_id INTEGER NOT NULL,
                invite_code TEXT NOT NULL,
                color_rol TEXT DEFAULT NULL
            )
        ''')

        # Tabla de miembros del clan
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS miembros_clan (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                clan_nombre TEXT NOT NULL,
                usuario_id INTEGER NOT NULL,
                rol_clan TEXT DEFAULT 'Recluta',
                fecha_union TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                activo INTEGER DEFAULT 1,
                FOREIGN KEY (clan_nombre) REFERENCES clanes(nombre) ON DELETE CASCADE,
                UNIQUE(clan_nombre, usuario_id)
            )
        ''')

        # Tabla de invitaciones pendientes
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS invitaciones_pendientes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                clan_nombre TEXT NOT NULL,
                usuario_invitado_id INTEGER NOT NULL,
                usuario_que_invita_id INTEGER NOT NULL,
                rol_asignado TEXT DEFAULT 'Recluta',
                mensaje_dm_id INTEGER,
                fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                fecha_expiracion TIMESTAMP NOT NULL,
                estado TEXT DEFAULT 'pendiente',
                FOREIGN KEY (clan_nombre) REFERENCES clanes(nombre) ON DELETE CASCADE
            )
        ''')

        # Tabla de historial de XP
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS historial_xp (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                clan_nombre TEXT NOT NULL,
                cantidad_xp INTEGER NOT NULL,
                razon TEXT NOT NULL,
                origen TEXT DEFAULT 'sistema',
                fecha TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                usuario_id INTEGER,
                FOREIGN KEY (clan_nombre) REFERENCES clanes(nombre) ON DELETE CASCADE
            )
        ''')

        # Tabla de canales adicionales del clan
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
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_miembros_clan ON miembros_clan(clan_nombre)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_miembros_usuario ON miembros_clan(usuario_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_invitaciones_estado ON invitaciones_pendientes(estado)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_historial_clan ON historial_xp(clan_nombre)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_canales_clan ON canales_clan(clan_nombre)')

        logger.info("Base de datos v2 inicializada correctamente")

# ==================== FUNCIONES DE CLANES ====================

def crear_clan(nombre: str, creador_id: int, descripcion: str, rol_id: int,
               categoria_id: int, canal_anuncios_id: int, canal_admin_id: int,
               canal_general_id: int, invite_code: str) -> bool:
    """Crear un nuevo clan"""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()

            # Crear clan
            cursor.execute('''
                INSERT INTO clanes
                (nombre, creador_id, descripcion, rol_id, categoria_id, canal_anuncios_id,
                 canal_admin_id, canal_general_id, invite_code)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (nombre, creador_id, descripcion, rol_id, categoria_id, canal_anuncios_id,
                  canal_admin_id, canal_general_id, invite_code))

            # Agregar creador como miembro con rol Líder
            cursor.execute('''
                INSERT INTO miembros_clan (clan_nombre, usuario_id, rol_clan)
                VALUES (?, ?, 'Líder')
            ''', (nombre, creador_id))

        return True
    except sqlite3.IntegrityError:
        logger.warning(f"El clan '{nombre}' ya existe")
        return False
    except Exception as e:
        logger.error(f"Error al crear clan: {e}")
        return False

def obtener_clan(nombre: str) -> Optional[Dict]:
    """Obtener información completa de un clan"""
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

            # Obtener configuración de nivel
            nivel_config = NIVELES_CLAN.get(row['nivel'], NIVELES_CLAN[1])

            return {
                'creador': row['creador_id'],
                'descripcion': row['descripcion'],
                'nivel': row['nivel'],
                'xp_actual': row['xp_actual'],
                'xp_siguiente_nivel': NIVELES_CLAN.get(row['nivel'] + 1, {'xp_requerido': 0})['xp_requerido'] if row['nivel'] < 6 else 0,
                'limite_miembros': nivel_config['limite_miembros'],
                'limite_canales_texto': nivel_config['canales_texto'],
                'limite_canales_voz': nivel_config['canales_voz'],
                'total_miembros': row['total_miembros_actuales'],
                'rol_id': row['rol_id'],
                'categoria_id': row['categoria_id'],
                'canal_anuncios_id': row['canal_anuncios_id'],
                'canal_admin_id': row['canal_admin_id'],
                'canal_general_id': row['canal_general_id'],
                'invite_code': row['invite_code'],
                'color_rol': row['color_rol'],
                'fecha_creacion': row['fecha_creacion'],
                'canales_extra': canales_extra
            }
    except Exception as e:
        logger.error(f"Error al obtener clan: {e}")
        return None

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

def obtener_todos_clanes() -> Dict[str, Dict]:
    """Obtener lista de todos los clanes con info básica"""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT nombre, creador_id, descripcion, nivel, xp_actual,
                       total_miembros_actuales, fecha_creacion
                FROM clanes
                ORDER BY nivel DESC, xp_actual DESC
            ''')

            clanes = {}
            for row in cursor.fetchall():
                clanes[row['nombre']] = {
                    'creador': row['creador_id'],
                    'descripcion': row['descripcion'],
                    'nivel': row['nivel'],
                    'xp_actual': row['xp_actual'],
                    'total_miembros': row['total_miembros_actuales'],
                    'fecha_creacion': row['fecha_creacion']
                }

            return clanes
    except Exception as e:
        logger.error(f"Error al obtener todos los clanes: {e}")
        return {}

# ==================== FUNCIONES DE XP ====================

def agregar_xp_clan(clan_nombre: str, cantidad_xp: int, razon: str,
                    usuario_id: int = None, origen: str = "sistema") -> Optional[Dict]:
    """
    Función genérica para agregar XP a un clan

    Returns:
        {
            'xp_anterior': 450,
            'xp_nuevo': 500,
            'nivel_anterior': 1,
            'nivel_nuevo': 2,
            'subio_nivel': True,
            'nuevo_limite_miembros': 20
        }
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()

            # Obtener estado actual del clan
            cursor.execute('''
                SELECT nivel, xp_actual FROM clanes WHERE nombre = ?
            ''', (clan_nombre,))
            row = cursor.fetchone()

            if not row:
                logger.error(f"Clan '{clan_nombre}' no encontrado")
                return None

            nivel_anterior = row['nivel']
            xp_anterior = row['xp_actual']
            xp_nuevo = xp_anterior + cantidad_xp

            # Calcular nuevo nivel
            nivel_nuevo = nivel_anterior
            for nivel, config in sorted(NIVELES_CLAN.items(), reverse=True):
                if xp_nuevo >= config['xp_requerido']:
                    nivel_nuevo = nivel
                    break

            # Actualizar clan
            cursor.execute('''
                UPDATE clanes
                SET xp_actual = ?, nivel = ?
                WHERE nombre = ?
            ''', (xp_nuevo, nivel_nuevo, clan_nombre))

            # Registrar en historial
            cursor.execute('''
                INSERT INTO historial_xp
                (clan_nombre, cantidad_xp, razon, origen, usuario_id)
                VALUES (?, ?, ?, ?, ?)
            ''', (clan_nombre, cantidad_xp, razon, origen, usuario_id))

            subio_nivel = nivel_nuevo > nivel_anterior

            return {
                'xp_anterior': xp_anterior,
                'xp_nuevo': xp_nuevo,
                'nivel_anterior': nivel_anterior,
                'nivel_nuevo': nivel_nuevo,
                'subio_nivel': subio_nivel,
                'nuevo_limite_miembros': NIVELES_CLAN[nivel_nuevo]['limite_miembros'],
                'nuevos_canales_texto': NIVELES_CLAN[nivel_nuevo]['canales_texto'],
                'nuevos_canales_voz': NIVELES_CLAN[nivel_nuevo]['canales_voz']
            }

    except Exception as e:
        logger.error(f"Error al agregar XP: {e}")
        return None

# ==================== FUNCIONES DE MIEMBROS ====================

def agregar_miembro_clan(clan_nombre: str, usuario_id: int, rol_clan: str = 'Recluta') -> bool:
    """Agregar un miembro al clan"""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()

            # Agregar miembro
            cursor.execute('''
                INSERT INTO miembros_clan (clan_nombre, usuario_id, rol_clan)
                VALUES (?, ?, ?)
            ''', (clan_nombre, usuario_id, rol_clan))

            # Actualizar contador de miembros
            cursor.execute('''
                UPDATE clanes
                SET total_miembros_actuales = total_miembros_actuales + 1,
                    total_miembros_historico = total_miembros_historico + 1
                WHERE nombre = ?
            ''', (clan_nombre,))

            # Dar XP por nuevo miembro (+50 XP)
            agregar_xp_clan(clan_nombre, 50, f"Nuevo miembro unido", usuario_id, "sistema")

        return True
    except sqlite3.IntegrityError:
        logger.warning(f"Usuario {usuario_id} ya está en el clan '{clan_nombre}'")
        return False
    except Exception as e:
        logger.error(f"Error al agregar miembro: {e}")
        return False

def obtener_miembros_clan(clan_nombre: str) -> List[Dict]:
    """Obtener lista de miembros del clan"""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT usuario_id, rol_clan, fecha_union, activo
                FROM miembros_clan
                WHERE clan_nombre = ? AND activo = 1
                ORDER BY
                    CASE rol_clan
                        WHEN 'Líder' THEN 1
                        WHEN 'Co-Líder' THEN 2
                        WHEN 'Miembro' THEN 3
                        WHEN 'Recluta' THEN 4
                    END,
                    fecha_union
            ''', (clan_nombre,))

            return [
                {
                    'usuario_id': r['usuario_id'],
                    'rol': r['rol_clan'],
                    'fecha_union': r['fecha_union']
                }
                for r in cursor.fetchall()
            ]
    except Exception as e:
        logger.error(f"Error al obtener miembros: {e}")
        return []

def obtener_rol_miembro(clan_nombre: str, usuario_id: int) -> Optional[str]:
    """Obtener el rol de un miembro en el clan"""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT rol_clan FROM miembros_clan
                WHERE clan_nombre = ? AND usuario_id = ? AND activo = 1
            ''', (clan_nombre, usuario_id))
            row = cursor.fetchone()
            return row['rol_clan'] if row else None
    except Exception as e:
        logger.error(f"Error al obtener rol: {e}")
        return None

def es_miembro_clan(clan_nombre: str, usuario_id: int) -> bool:
    """Verificar si un usuario es miembro del clan"""
    return obtener_rol_miembro(clan_nombre, usuario_id) is not None

# ==================== FUNCIONES DE INVITACIONES ====================

def crear_invitacion(clan_nombre: str, usuario_invitado_id: int, usuario_que_invita_id: int,
                     rol_asignado: str = 'Recluta', horas_expiracion: int = 48) -> Optional[int]:
    """Crear una invitación pendiente"""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()

            fecha_expiracion = datetime.now() + timedelta(hours=horas_expiracion)

            cursor.execute('''
                INSERT INTO invitaciones_pendientes
                (clan_nombre, usuario_invitado_id, usuario_que_invita_id, rol_asignado, fecha_expiracion)
                VALUES (?, ?, ?, ?, ?)
            ''', (clan_nombre, usuario_invitado_id, usuario_que_invita_id, rol_asignado, fecha_expiracion))

            return cursor.lastrowid
    except Exception as e:
        logger.error(f"Error al crear invitación: {e}")
        return None

def obtener_invitacion(invitacion_id: int) -> Optional[Dict]:
    """Obtener información de una invitación"""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM invitaciones_pendientes WHERE id = ?
            ''', (invitacion_id,))
            row = cursor.fetchone()

            if not row:
                return None

            return dict(row)
    except Exception as e:
        logger.error(f"Error al obtener invitación: {e}")
        return None

def aceptar_invitacion(invitacion_id: int) -> bool:
    """Aceptar una invitación"""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()

            # Obtener invitación
            cursor.execute('''
                SELECT clan_nombre, usuario_invitado_id, rol_asignado, estado, fecha_expiracion
                FROM invitaciones_pendientes WHERE id = ?
            ''', (invitacion_id,))
            row = cursor.fetchone()

            if not row or row['estado'] != 'pendiente':
                return False

            # Verificar si expiró
            if datetime.fromisoformat(row['fecha_expiracion']) < datetime.now():
                cursor.execute('''
                    UPDATE invitaciones_pendientes SET estado = 'expirada' WHERE id = ?
                ''', (invitacion_id,))
                return False

            # Agregar miembro al clan
            agregar_miembro_clan(row['clan_nombre'], row['usuario_invitado_id'], row['rol_asignado'])

            # Actualizar estado de invitación
            cursor.execute('''
                UPDATE invitaciones_pendientes SET estado = 'aceptada' WHERE id = ?
            ''', (invitacion_id,))

        return True
    except Exception as e:
        logger.error(f"Error al aceptar invitación: {e}")
        return False

def rechazar_invitacion(invitacion_id: int) -> bool:
    """Rechazar una invitación"""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE invitaciones_pendientes
                SET estado = 'rechazada'
                WHERE id = ? AND estado = 'pendiente'
            ''', (invitacion_id,))
            return cursor.rowcount > 0
    except Exception as e:
        logger.error(f"Error al rechazar invitación: {e}")
        return False

# ==================== FUNCIONES DE CANALES ====================

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

def contar_canales_extra(clan_nombre: str, tipo: str = None) -> int:
    """Contar canales extra del clan por tipo"""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            if tipo:
                cursor.execute('''
                    SELECT COUNT(*) as total FROM canales_clan
                    WHERE clan_nombre = ? AND tipo = ?
                ''', (clan_nombre, tipo))
            else:
                cursor.execute('''
                    SELECT COUNT(*) as total FROM canales_clan
                    WHERE clan_nombre = ?
                ''', (clan_nombre,))

            return cursor.fetchone()['total']
    except Exception as e:
        logger.error(f"Error al contar canales: {e}")
        return 0

# ==================== FUNCIONES DE UTILIDAD ====================

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

def limpiar_invitaciones_expiradas():
    """Marcar invitaciones expiradas"""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE invitaciones_pendientes
                SET estado = 'expirada'
                WHERE estado = 'pendiente' AND fecha_expiracion < datetime('now')
            ''')
            logger.info(f"Limpiadas {cursor.rowcount} invitaciones expiradas")
    except Exception as e:
        logger.error(f"Error al limpiar invitaciones: {e}")
