import json
import sqlite3
from pathlib import Path
from typing import Any

RUTA_DATOS = Path(__file__).resolve().parent / "datos"
RUTA_DATOS.mkdir(parents=True, exist_ok=True)
RUTA_BD = RUTA_DATOS / "agroia.db"

COLUMNAS_NUEVAS = {
    "departamento": "TEXT DEFAULT 'Sin especificar'",
    "riesgo_real": "TEXT",
    "puntaje_riesgo": "REAL DEFAULT 0",
    "tiempo_ms": "REAL DEFAULT 0",
    "factores": "TEXT DEFAULT '[]'",
    "metodo_ia": "TEXT DEFAULT 'Híbrido: reglas agroclimáticas + aptitud provincial + Random Forest'",
    "aptitud_cultivo": "TEXT DEFAULT 'Sin referencia'",
    "impacto_ubicacion": "REAL DEFAULT 0",
    "detalle_aptitud": "TEXT DEFAULT ''",
    "responsable_validacion": "TEXT DEFAULT ''",
    "fecha_validacion": "TEXT DEFAULT ''",
    "observacion_validacion": "TEXT DEFAULT ''",
    "riesgo_modelo": "TEXT DEFAULT ''",
    "riesgo_reglas": "TEXT DEFAULT ''",
    "bloqueo_critico": "INTEGER DEFAULT 0",
    "zonas_recomendadas": "TEXT DEFAULT '[]'",
    "arbol_decision": "TEXT DEFAULT '{}'",
    "latitud": "REAL",
    "longitud": "REAL",
    "altitud_msnm": "REAL",
}


def obtener_conexion() -> sqlite3.Connection:
    conexion = sqlite3.connect(RUTA_BD)
    conexion.row_factory = sqlite3.Row
    return conexion


def iniciar_base_datos() -> None:
    with obtener_conexion() as conexion:
        conexion.execute(
            """
            CREATE TABLE IF NOT EXISTS evaluaciones (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                productor TEXT NOT NULL,
                departamento TEXT DEFAULT 'Sin especificar',
                cultivo TEXT NOT NULL,
                provincia TEXT NOT NULL,
                distrito TEXT NOT NULL,
                latitud REAL,
                longitud REAL,
                altitud_msnm REAL,
                etapa TEXT NOT NULL,
                fecha_siembra TEXT NOT NULL,
                area_hectareas REAL NOT NULL,
                temperatura_minima REAL NOT NULL,
                humedad_suelo TEXT NOT NULL,
                lluvia_acumulada REAL NOT NULL,
                historial_perdidas INTEGER NOT NULL,
                observaciones TEXT,
                riesgo TEXT NOT NULL,
                probabilidad REAL NOT NULL,
                causa TEXT NOT NULL,
                recomendaciones TEXT NOT NULL,
                imagen_url TEXT,
                origen TEXT NOT NULL,
                creado_en TEXT NOT NULL,
                riesgo_real TEXT,
                puntaje_riesgo REAL DEFAULT 0,
                tiempo_ms REAL DEFAULT 0,
                factores TEXT DEFAULT '[]',
                metodo_ia TEXT DEFAULT 'Híbrido: reglas agroclimáticas + aptitud provincial + Random Forest',
                aptitud_cultivo TEXT DEFAULT 'Sin referencia',
                impacto_ubicacion REAL DEFAULT 0,
                detalle_aptitud TEXT DEFAULT '',
                responsable_validacion TEXT DEFAULT '',
                fecha_validacion TEXT DEFAULT '',
                observacion_validacion TEXT DEFAULT '',
                riesgo_modelo TEXT DEFAULT '',
                riesgo_reglas TEXT DEFAULT '',
                bloqueo_critico INTEGER DEFAULT 0,
                zonas_recomendadas TEXT DEFAULT '[]',
                arbol_decision TEXT DEFAULT '{}'
            )
            """
        )
        columnas_existentes = {fila[1] for fila in conexion.execute("PRAGMA table_info(evaluaciones)").fetchall()}
        for columna, definicion in COLUMNAS_NUEVAS.items():
            if columna not in columnas_existentes:
                conexion.execute(f"ALTER TABLE evaluaciones ADD COLUMN {columna} {definicion}")
        conexion.commit()


def fila_a_diccionario(fila: sqlite3.Row) -> dict[str, Any]:
    dato = dict(fila)
    for campo in ["recomendaciones", "factores", "zonas_recomendadas"]:
        try:
            dato[campo] = json.loads(dato.get(campo) or "[]")
        except json.JSONDecodeError:
            dato[campo] = []
    try:
        dato["arbol_decision"] = json.loads(dato.get("arbol_decision") or "{}")
    except json.JSONDecodeError:
        dato["arbol_decision"] = {}
    return dato