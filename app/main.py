from __future__ import annotations

import csv
import io
import json
import os
import shutil
import smtplib
import urllib.parse
import urllib.request
import uuid
from datetime import datetime, timezone
from pathlib import Path
from email.message import EmailMessage
from statistics import mean, pstdev
from typing import Any

from fastapi import FastAPI, File, Form, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from starlette.requests import Request

from .base_datos import fila_a_diccionario, iniciar_base_datos, obtener_conexion
from .modelo_ia import ServicioModeloIA
from .ubicaciones import buscar_departamento_por_provincia, obtener_catalogo_para_api

RUTA_APP = Path(__file__).resolve().parent
RUTA_UPLOADS = RUTA_APP / "static" / "uploads"
RUTA_PARCELAS = RUTA_APP / "static" / "parcelas_verificadas.csv"
RUTA_UPLOADS.mkdir(parents=True, exist_ok=True)
RIESGOS = ["Alto", "Medio", "Bajo"]
VALOR_RIESGO = {"Bajo": 0, "Medio": 1, "Alto": 2}
CULTIVOS_VALIDOS = {"Papa nativa", "Maíz", "Quinua"}
ETAPAS_VALIDAS = {"Siembra", "Emergencia", "Crecimiento", "Floración", "Llenado de grano", "Maduración"}
HUMEDADES_VALIDAS = {"Muy baja", "Baja", "Media", "Alta"}
INICIO_SERVIDOR = datetime.now(timezone.utc)

app = FastAPI(title="AgroIA Perú Blindado", version="19.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.mount("/static", StaticFiles(directory=RUTA_APP / "static"), name="static")
templates = Jinja2Templates(directory=RUTA_APP / "templates")
servicio_ia: ServicioModeloIA | None = None


class ValidacionTecnica(BaseModel):
    riesgo_real: str
    responsable_validacion: str = ""
    fecha_validacion: str = ""
    observacion_validacion: str = ""


@app.on_event("startup")
def al_iniciar() -> None:
    global servicio_ia
    iniciar_base_datos()
    servicio_ia = ServicioModeloIA()


@app.get("/", response_class=HTMLResponse)
def inicio(request: Request) -> HTMLResponse:
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/salud")
def salud() -> dict[str, str]:
    return {"estado": "AgroIA Perú activo", "version": "19.0 parcelas agrícolas rurales y cultivo libre"}


@app.get("/api/catalogo")
def catalogo() -> dict[str, Any]:
    return obtener_catalogo_para_api()




def leer_parcelas_registradas() -> list[dict[str, Any]]:
    """Carga zonas/parcelas agrícolas del CSV local.

    La regla de V19 es simple: el software solo muestra ubicaciones que existen
    dentro de este catálogo. Así se evita caer en centros urbanos o plazas.
    """
    parcelas: list[dict[str, Any]] = []
    if not RUTA_PARCELAS.exists():
        return parcelas
    with RUTA_PARCELAS.open("r", encoding="utf-8-sig", newline="") as archivo:
        lector = csv.DictReader(archivo, delimiter=";")
        for fila in lector:
            try:
                fila["latitud"] = float(fila.get("latitud") or 0)
                fila["longitud"] = float(fila.get("longitud") or 0)
                fila["altitud_msnm"] = float(fila.get("altitud_msnm") or 0)
                fila["area_hectareas"] = float(fila.get("area_hectareas") or 0)
            except ValueError:
                continue
            if not fila.get("id") or not fila.get("departamento") or not fila.get("provincia") or not fila.get("distrito"):
                continue
            parcelas.append(fila)
    return parcelas


def obtener_parcela_registrada(parcela_id: str) -> dict[str, Any] | None:
    parcela_id = (parcela_id or "").strip()
    if not parcela_id:
        return None
    for parcela in leer_parcelas_registradas():
        if parcela.get("id") == parcela_id:
            return parcela
    return None


@app.get("/api/parcelas_verificadas")
def parcelas_verificadas() -> dict[str, Any]:
    """Devuelve solo zonas/parcelas cargadas desde el CSV agrícola.

    Si una ciudad o distrito no tiene una zona agrícola registrada en este CSV,
    no aparece en el formulario.
    """
    parcelas = leer_parcelas_registradas()
    return {
        "parcelas": parcelas,
        "nota": "Catálogo V19: solo se listan zonas agrícolas rurales del CSV local. Para producción real, reemplazar por GPS/catastro validado.",
    }

@app.get("/api/estado_servidor")
def estado_servidor() -> dict[str, Any]:
    segundos = int((datetime.now(timezone.utc) - INICIO_SERVIDOR).total_seconds())
    return {
        "estado": "activo",
        "modo": "Render Free / demo académica",
        "version": "19.0 parcelas agrícolas rurales y cultivo libre",
        "uptime_segundos": segundos,
        "iniciado_en": INICIO_SERVIDOR.isoformat(timespec="seconds"),
        "mensaje": "Servidor despierto. Si estuvo dormido, Render puede demorar unos segundos en levantarlo.",
    }


@app.get("/api/clima")
def obtener_clima_automatico(
    latitud: float = Query(..., ge=-18.7, le=0.2),
    longitud: float = Query(..., ge=-81.6, le=-68.0),
) -> dict[str, Any]:
    parametros = urllib.parse.urlencode({
        "latitude": latitud,
        "longitude": longitud,
        "daily": "temperature_2m_min,precipitation_sum",
        "timezone": "auto",
        "past_days": 7,
        "forecast_days": 1,
    })
    url = f"https://api.open-meteo.com/v1/forecast?{parametros}"
    try:
        with urllib.request.urlopen(url, timeout=8) as respuesta:
            datos = json.loads(respuesta.read().decode("utf-8"))
    except Exception as error:
        raise HTTPException(status_code=502, detail="No se pudo consultar Open-Meteo. Revisa conexión o vuelve a intentar.") from error

    diario = datos.get("daily") or {}
    temperaturas = [float(valor) for valor in diario.get("temperature_2m_min", []) if valor is not None]
    lluvias = [float(valor) for valor in diario.get("precipitation_sum", []) if valor is not None]
    if not temperaturas or not lluvias:
        raise HTTPException(status_code=502, detail="Open-Meteo respondió sin datos suficientes para esta ubicación.")

    lluvia_total = round(sum(lluvias), 1)
    temperatura_minima = round(min(temperaturas), 1)
    humedad_estimada = estimar_humedad_por_lluvia(lluvia_total)
    return {
        "fuente": "Open-Meteo",
        "latitud": latitud,
        "longitud": longitud,
        "temperatura_minima": temperatura_minima,
        "lluvia_acumulada": lluvia_total,
        "humedad_suelo": humedad_estimada,
        "dias_analizados": len(lluvias),
        "periodo": diario.get("time", []),
        "nota": "La humedad del suelo es una estimación simple basada en lluvia acumulada; para producción real conviene sensor o validación técnica.",
    }


@app.get("/api/experimentos")
def experimentos_modelo() -> dict[str, Any]:
    return {
        "mensaje": "Bloque compatible con Comet ML: aquí se muestran resultados de experimentos ligeros sin entrenar modelos pesados dentro de Render Free.",
        "modelos": [
            {"modelo": "Random Forest", "accuracy": 85.19, "f1_score": 85.19, "uso": "Modelo principal por estabilidad y mezcla de variables."},
            {"modelo": "Decision Tree", "accuracy": 78.4, "f1_score": 76.8, "uso": "Bueno para explicar reglas, pero más inestable."},
            {"modelo": "Regresión logística", "accuracy": 71.2, "f1_score": 69.5, "uso": "Ligero, pero flojo con relaciones no lineales."},
        ],
        "importancia_variables": [
            {"variable": "lluvia_acumulada", "peso": 28},
            {"variable": "temperatura_minima", "peso": 24},
            {"variable": "aptitud_territorial", "peso": 20},
            {"variable": "etapa_cultivo", "peso": 13},
            {"variable": "historial_perdidas", "peso": 9},
            {"variable": "altitud_msnm", "peso": 6},
        ],
    }


@app.post("/api/evaluaciones")
async def crear_evaluacion(
    productor: str = Form(...),
    departamento: str = Form("Sin especificar"),
    cultivo: str = Form(...),
    provincia: str = Form(...),
    distrito: str = Form(...),
    latitud: str = Form(""),
    longitud: str = Form(""),
    altitud_msnm: str = Form(""),
    etapa: str = Form(...),
    fecha_siembra: str = Form(...),
    area_hectareas: float = Form(...),
    temperatura_minima: float = Form(...),
    humedad_suelo: str = Form(...),
    lluvia_acumulada: float = Form(...),
    historial_perdidas: int = Form(...),
    observaciones: str = Form(""),
    origen: str = Form("real"),
    riesgo_real: str = Form(""),
    responsable_validacion: str = Form(""),
    fecha_validacion: str = Form(""),
    observacion_validacion: str = Form(""),
    parcela_id: str = Form(""),
    imagen: UploadFile | None = File(None),
) -> dict[str, Any]:
    if servicio_ia is None:
        raise HTTPException(status_code=503, detail="El modelo IA aún no está listo.")

    parcela = obtener_parcela_registrada(parcela_id)
    if parcela is None:
        raise HTTPException(status_code=400, detail="Selecciona una parcela/zona agrícola registrada del catálogo. No se aceptan coordenadas manuales para evitar centros urbanos.")

    productor = parcela.get("productor") or productor
    departamento = parcela.get("departamento") or departamento
    provincia = parcela.get("provincia") or provincia
    distrito = parcela.get("distrito") or distrito
    latitud = str(parcela.get("latitud", ""))
    longitud = str(parcela.get("longitud", ""))
    altitud_msnm = str(parcela.get("altitud_msnm", ""))
    area_hectareas = float(parcela.get("area_hectareas") or area_hectareas)
    latitud_valor = limpiar_numero_opcional(latitud, -18.7, 0.2, "latitud")
    longitud_valor = limpiar_numero_opcional(longitud, -81.6, -68.0, "longitud")
    altitud_valor = limpiar_numero_opcional(altitud_msnm, 0, 6900, "altitud")
    validar_entrada_productiva(cultivo, etapa, area_hectareas, temperatura_minima, humedad_suelo, lluvia_acumulada, historial_perdidas, fecha_siembra, latitud_valor, longitud_valor)
    datos = construir_datos_modelo(departamento, cultivo, provincia, distrito, etapa, temperatura_minima, humedad_suelo, lluvia_acumulada, historial_perdidas, area_hectareas)
    resultado = servicio_ia.predecir(datos)
    imagen_url = await guardar_imagen(imagen)
    creado_en = datetime.now().isoformat(timespec="seconds")
    riesgo_real_limpio = limpiar_riesgo_real(riesgo_real)

    with obtener_conexion() as conexion:
        cursor = conexion.execute(
            """
            INSERT INTO evaluaciones (
                productor, departamento, cultivo, provincia, distrito, latitud, longitud, altitud_msnm,
                etapa, fecha_siembra, area_hectareas, temperatura_minima, humedad_suelo, lluvia_acumulada,
                historial_perdidas, observaciones, riesgo, probabilidad, causa,
                recomendaciones, imagen_url, origen, creado_en, riesgo_real,
                puntaje_riesgo, tiempo_ms, factores, metodo_ia, aptitud_cultivo,
                impacto_ubicacion, detalle_aptitud, responsable_validacion,
                fecha_validacion, observacion_validacion, riesgo_modelo, riesgo_reglas,
                bloqueo_critico, zonas_recomendadas, arbol_decision
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                productor.strip(),
                datos["departamento"],
                cultivo,
                provincia.strip(),
                distrito.strip(),
                latitud_valor,
                longitud_valor,
                altitud_valor,
                etapa,
                fecha_siembra,
                area_hectareas,
                temperatura_minima,
                humedad_suelo,
                lluvia_acumulada,
                historial_perdidas,
                observaciones.strip(),
                resultado["riesgo"],
                resultado["probabilidad"],
                resultado["causa"],
                json.dumps(resultado["recomendaciones"], ensure_ascii=False),
                imagen_url,
                origen,
                creado_en,
                riesgo_real_limpio,
                resultado["puntaje_riesgo"],
                resultado["tiempo_ms"],
                json.dumps(resultado["factores"], ensure_ascii=False),
                resultado["metodo_ia"],
                resultado["aptitud_cultivo"],
                resultado["impacto_ubicacion"],
                resultado["detalle_aptitud"],
                responsable_validacion.strip(),
                fecha_validacion.strip(),
                observacion_validacion.strip(),
                resultado.get("riesgo_modelo", ""),
                resultado.get("riesgo_reglas", ""),
                int(resultado.get("bloqueo_critico", 0)),
                json.dumps(resultado.get("zonas_recomendadas", []), ensure_ascii=False),
                json.dumps(resultado.get("arbol_decision", {}), ensure_ascii=False),
            ),
        )
        conexion.commit()
        identificador = cursor.lastrowid

    return obtener_evaluacion(identificador)


@app.get("/api/evaluaciones")
def listar_evaluaciones() -> dict[str, Any]:
    with obtener_conexion() as conexion:
        filas = conexion.execute("SELECT * FROM evaluaciones ORDER BY id DESC").fetchall()
    return {"evaluaciones": [fila_a_diccionario(fila) for fila in filas]}


@app.get("/api/evaluaciones/{identificador}")
def obtener_evaluacion(identificador: int) -> dict[str, Any]:
    with obtener_conexion() as conexion:
        fila = conexion.execute("SELECT * FROM evaluaciones WHERE id = ?", (identificador,)).fetchone()
    if fila is None:
        raise HTTPException(status_code=404, detail="Evaluación no encontrada.")
    return fila_a_diccionario(fila)


@app.put("/api/evaluaciones/{identificador}/validacion")
def validar_evaluacion(identificador: int, validacion: ValidacionTecnica) -> dict[str, Any]:
    riesgo_limpio = limpiar_riesgo_real(validacion.riesgo_real)
    if riesgo_limpio is None:
        raise HTTPException(status_code=400, detail="El riesgo real debe ser Alto, Medio o Bajo.")
    fecha = validacion.fecha_validacion.strip() or datetime.now().date().isoformat()
    with obtener_conexion() as conexion:
        fila = conexion.execute("SELECT id FROM evaluaciones WHERE id = ?", (identificador,)).fetchone()
        if fila is None:
            raise HTTPException(status_code=404, detail="Evaluación no encontrada.")
        conexion.execute(
            """
            UPDATE evaluaciones
            SET riesgo_real = ?, responsable_validacion = ?, fecha_validacion = ?, observacion_validacion = ?
            WHERE id = ?
            """,
            (
                riesgo_limpio,
                validacion.responsable_validacion.strip(),
                fecha,
                validacion.observacion_validacion.strip(),
                identificador,
            ),
        )
        conexion.commit()
    return obtener_evaluacion(identificador)


@app.delete("/api/evaluaciones/{identificador}")
def eliminar_evaluacion(identificador: int) -> dict[str, str]:
    with obtener_conexion() as conexion:
        fila = conexion.execute("SELECT imagen_url FROM evaluaciones WHERE id = ?", (identificador,)).fetchone()
        conexion.execute("DELETE FROM evaluaciones WHERE id = ?", (identificador,))
        conexion.commit()
    if fila and fila["imagen_url"]:
        ruta = RUTA_APP / fila["imagen_url"].lstrip("/")
        if ruta.exists() and ruta.is_file():
            ruta.unlink(missing_ok=True)
    return {"mensaje": "Evaluación eliminada"}


@app.post("/api/demo/cargar")
def cargar_demo() -> dict[str, Any]:
    if servicio_ia is None:
        raise HTTPException(status_code=503, detail="El modelo IA aún no está listo.")

    # V19: cada vez que se carga el demo, se limpian los registros demo
    # anteriores para no arrastrar coordenadas viejas que apuntaban a ciudades.
    limpiar_demo()

    escenarios = {
        "CUS-ANTA-ZURITE-01": {"cultivo": "Papa nativa", "etapa": "Floración", "temperatura_minima": 1.4, "humedad_suelo": "Baja", "lluvia_acumulada": 5.8, "historial_perdidas": 1, "riesgo_real": "Alto", "observacion_validacion": "Helada afectó hojas en etapa sensible."},
        "CUS-URUB-MARAS-01": {"cultivo": "Maíz", "etapa": "Crecimiento", "temperatura_minima": 8.1, "humedad_suelo": "Media", "lluvia_acumulada": 22.0, "historial_perdidas": 0, "riesgo_real": "Bajo", "observacion_validacion": "Condición estable de valle agrícola."},
        "CUS-URUB-CHIN-01": {"cultivo": "Quinua", "etapa": "Emergencia", "temperatura_minima": 0.8, "humedad_suelo": "Baja", "lluvia_acumulada": 6.2, "historial_perdidas": 1, "riesgo_real": "Alto", "observacion_validacion": "Riesgo por baja temperatura en zona altoandina."},
        "PUN-SROM-CABANA-01": {"cultivo": "Quinua", "etapa": "Maduración", "temperatura_minima": 6.5, "humedad_suelo": "Media", "lluvia_acumulada": 20.0, "historial_perdidas": 0, "riesgo_real": "Bajo", "observacion_validacion": "Quinua estable en zona altiplánica."},
        "PUN-COLL-COND-01": {"cultivo": "Papa nativa", "etapa": "Emergencia", "temperatura_minima": -1.2, "humedad_suelo": "Baja", "lluvia_acumulada": 5.0, "historial_perdidas": 1, "riesgo_real": "Alto", "observacion_validacion": "Helada temprana en etapa de emergencia."},
        "APU-ANDA-PACU-01": {"cultivo": "Maíz", "etapa": "Floración", "temperatura_minima": 5.5, "humedad_suelo": "Muy baja", "lluvia_acumulada": 4.2, "historial_perdidas": 0, "riesgo_real": "Medio", "observacion_validacion": "Estrés hídrico parcial."},
        "AYA-HUAM-ACOCRO-01": {"cultivo": "Papa nativa", "etapa": "Crecimiento", "temperatura_minima": 3.4, "humedad_suelo": "Baja", "lluvia_acumulada": 9.0, "historial_perdidas": 1, "riesgo_real": "Medio", "observacion_validacion": "Vigilancia por déficit hídrico."},
        "HVC-TAYA-ACRAQ-01": {"cultivo": "Quinua", "etapa": "Floración", "temperatura_minima": 1.2, "humedad_suelo": "Baja", "lluvia_acumulada": 5.5, "historial_perdidas": 1, "riesgo_real": "Alto", "observacion_validacion": "Daño visible en hojas por helada."},
    }

    parcelas_por_id = {parcela["id"]: parcela for parcela in leer_parcelas_registradas()}
    muestras: list[dict[str, Any]] = []
    for parcela_id, escenario in escenarios.items():
        parcela = parcelas_por_id.get(parcela_id)
        if not parcela:
            continue
        muestra = {
            "productor": parcela.get("productor") or parcela.get("nombre_parcela"),
            "latitud": parcela["latitud"],
            "longitud": parcela["longitud"],
            "altitud_msnm": parcela["altitud_msnm"],
            "departamento": parcela["departamento"],
            "cultivo": escenario.get("cultivo") or parcela.get("cultivo_principal") or "Papa nativa",
            "provincia": parcela["provincia"],
            "distrito": parcela["distrito"],
            "fecha_siembra": "2026-03-24",
            "area_hectareas": parcela.get("area_hectareas") or 1.0,
            "responsable_validacion": "Técnico demo",
            "fecha_validacion": "2026-05-12",
            "observaciones": "Evaluación demo de zona agrícola rural.",
            **escenario,
        }
        muestras.append(muestra)

    creados: list[dict[str, Any]] = []
    for muestra in muestras:
        creado = guardar_muestra_demo(muestra)
        creados.append(creado)
    return {"creados": creados}


@app.delete("/api/demo/limpiar")
def limpiar_demo() -> dict[str, str]:
    with obtener_conexion() as conexion:
        filas = conexion.execute("SELECT imagen_url FROM evaluaciones WHERE origen = 'demo'").fetchall()
        conexion.execute("DELETE FROM evaluaciones WHERE origen = 'demo'")
        conexion.commit()
    for fila in filas:
        if fila["imagen_url"]:
            ruta = RUTA_APP / fila["imagen_url"].lstrip("/")
            if ruta.exists() and ruta.is_file() and ruta.name != "parcela-demo.svg":
                ruta.unlink(missing_ok=True)
    return {"mensaje": "Datos demo eliminados"}


@app.post("/api/demo/restaurar")
def restaurar_demo() -> dict[str, Any]:
    limpiar_demo()
    resultado = cargar_demo()
    return {"mensaje": "Demo restaurada desde cero", "creados": resultado["creados"]}


@app.post("/api/importar_csv")
async def importar_csv(archivo: UploadFile = File(...)) -> dict[str, Any]:
    if servicio_ia is None:
        raise HTTPException(status_code=503, detail="El modelo IA aún no está listo.")
    contenido = (await archivo.read()).decode("utf-8-sig")
    muestra = contenido[:4096]
    try:
        dialecto = csv.Sniffer().sniff(muestra, delimiters=",;")
        delimitador = dialecto.delimiter
    except csv.Error:
        delimitador = ";" if muestra.count(";") >= muestra.count(",") else ","
    lector = csv.DictReader(io.StringIO(contenido), delimiter=delimitador)
    creados = 0
    errores: list[str] = []

    for indice, fila in enumerate(lector, start=2):
        try:
            departamento = fila.get("departamento") or buscar_departamento_por_provincia(fila["provincia"])
            latitud_valor = limpiar_numero_opcional(fila.get("latitud", ""), -18.7, 0.2, "latitud")
            longitud_valor = limpiar_numero_opcional(fila.get("longitud", ""), -81.6, -68.0, "longitud")
            altitud_valor = limpiar_numero_opcional(fila.get("altitud_msnm", fila.get("altitud", "")), 0, 6900, "altitud")
            cultivo_csv = fila["cultivo"]
            etapa_csv = fila["etapa"]
            area_csv = float(fila["area_hectareas"])
            temperatura_csv = float(fila["temperatura_minima"])
            humedad_csv = fila["humedad_suelo"]
            lluvia_csv = float(fila["lluvia_acumulada"])
            historial_csv = int(fila["historial_perdidas"])
            validar_entrada_productiva(cultivo_csv, etapa_csv, area_csv, temperatura_csv, humedad_csv, lluvia_csv, historial_csv, fila["fecha_siembra"], latitud_valor, longitud_valor)
            datos = construir_datos_modelo(
                departamento,
                cultivo_csv,
                fila["provincia"],
                fila["distrito"],
                etapa_csv,
                temperatura_csv,
                humedad_csv,
                lluvia_csv,
                historial_csv,
                area_csv,
            )
            resultado = servicio_ia.predecir(datos)
            with obtener_conexion() as conexion:
                conexion.execute(
                    """
                    INSERT INTO evaluaciones (
                        productor, departamento, cultivo, provincia, distrito, latitud, longitud, altitud_msnm,
                        etapa, fecha_siembra, area_hectareas, temperatura_minima, humedad_suelo, lluvia_acumulada,
                        historial_perdidas, observaciones, riesgo, probabilidad, causa,
                        recomendaciones, imagen_url, origen, creado_en, riesgo_real,
                        puntaje_riesgo, tiempo_ms, factores, metodo_ia, aptitud_cultivo,
                        impacto_ubicacion, detalle_aptitud, responsable_validacion,
                        fecha_validacion, observacion_validacion, riesgo_modelo, riesgo_reglas,
                        bloqueo_critico, zonas_recomendadas, arbol_decision
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        fila["productor"], datos["departamento"], datos["cultivo"], datos["provincia"], datos["distrito"],
                        latitud_valor, longitud_valor, altitud_valor, datos["etapa"], fila["fecha_siembra"],
                        datos["area_hectareas"], datos["temperatura_minima"], datos["humedad_suelo"], datos["lluvia_acumulada"],
                        datos["historial_perdidas"], fila.get("observaciones", ""), resultado["riesgo"], resultado["probabilidad"],
                        resultado["causa"], json.dumps(resultado["recomendaciones"], ensure_ascii=False), None, "real",
                        datetime.now().isoformat(timespec="seconds"), limpiar_riesgo_real(fila.get("riesgo_real", "")),
                        resultado["puntaje_riesgo"], resultado["tiempo_ms"], json.dumps(resultado["factores"], ensure_ascii=False), resultado["metodo_ia"],
                        resultado["aptitud_cultivo"], resultado["impacto_ubicacion"], resultado["detalle_aptitud"],
                        fila.get("responsable_validacion", ""), fila.get("fecha_validacion", ""), fila.get("observacion_validacion", ""),
                        resultado.get("riesgo_modelo", ""), resultado.get("riesgo_reglas", ""), int(resultado.get("bloqueo_critico", 0)),
                        json.dumps(resultado.get("zonas_recomendadas", []), ensure_ascii=False), json.dumps(resultado.get("arbol_decision", {}), ensure_ascii=False),
                    ),
                )
                conexion.commit()
            creados += 1
        except Exception as error:
            errores.append(f"Fila {indice}: {error}")
    return {"creados": creados, "errores": errores}


@app.get("/api/resumen")
def resumen() -> dict[str, Any]:
    evaluaciones = obtener_todas_las_evaluaciones()
    total = len(evaluaciones)
    por_riesgo = contar_por(evaluaciones, "riesgo")
    por_cultivo = contar_por(evaluaciones, "cultivo")
    por_origen = contar_por(evaluaciones, "origen")
    por_distrito = contar_por(evaluaciones, "distrito")
    por_provincia = contar_por(evaluaciones, "provincia")
    riesgo_alto = sum(1 for item in evaluaciones if item["riesgo"] == "Alto")
    area_total = round(sum(float(item["area_hectareas"]) for item in evaluaciones), 2)
    area_alta = round(sum(float(item["area_hectareas"]) for item in evaluaciones if item["riesgo"] == "Alto"), 2)
    porcentaje_alto = round((riesgo_alto / total) * 100, 1) if total else 0
    return {
        "total": total,
        "por_riesgo": por_riesgo,
        "por_cultivo": por_cultivo,
        "por_origen": por_origen,
        "por_distrito": por_distrito,
        "por_provincia": por_provincia,
        "riesgo_alto": riesgo_alto,
        "porcentaje_alto": porcentaje_alto,
        "area_total": area_total,
        "area_alta": area_alta,
        "evaluaciones": evaluaciones,
    }


@app.get("/api/metricas")
def metricas_modelo() -> dict[str, Any]:
    evaluaciones = [item for item in obtener_todas_las_evaluaciones() if item.get("riesgo_real") in RIESGOS]
    if not evaluaciones:
        return {"disponible": False, "mensaje": "Agrega validación técnica post-cultivo con riesgo real observado para calcular métricas del modelo."}

    matriz = [[0 for _ in RIESGOS] for _ in RIESGOS]
    for item in evaluaciones:
        real = item["riesgo_real"]
        predicho = item["riesgo"]
        matriz[RIESGOS.index(real)][RIESGOS.index(predicho)] += 1

    total = len(evaluaciones)
    correctos = sum(matriz[i][i] for i in range(len(RIESGOS)))
    accuracy = correctos / total if total else 0
    tasa_error = 1 - accuracy

    precisiones: list[float] = []
    recalls: list[float] = []
    f1s: list[float] = []
    por_clase: dict[str, dict[str, float]] = {}

    for indice, riesgo in enumerate(RIESGOS):
        vp = matriz[indice][indice]
        fp = sum(matriz[fila][indice] for fila in range(len(RIESGOS)) if fila != indice)
        fn = sum(matriz[indice][columna] for columna in range(len(RIESGOS)) if columna != indice)
        precision = vp / (vp + fp) if (vp + fp) else 0
        recall = vp / (vp + fn) if (vp + fn) else 0
        f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) else 0
        precisiones.append(precision)
        recalls.append(recall)
        f1s.append(f1)
        por_clase[riesgo] = {
            "precision": round(precision * 100, 2),
            "recall": round(recall * 100, 2),
            "f1": round(f1 * 100, 2),
            "soporte": sum(matriz[indice]),
        }

    tiempos = [float(item.get("tiempo_ms") or 0) for item in evaluaciones]
    errores_ordinales = [abs(VALOR_RIESGO[item["riesgo"]] - VALOR_RIESGO[item["riesgo_real"]]) for item in evaluaciones]
    variabilidad_error = pstdev(errores_ordinales) if len(errores_ordinales) > 1 else 0
    error_medio_ordinal = mean(errores_ordinales) if errores_ordinales else 0

    return {
        "disponible": True,
        "clases": RIESGOS,
        "matriz": matriz,
        "total_validacion": total,
        "accuracy": round(accuracy * 100, 2),
        "precision": round(mean(precisiones) * 100, 2),
        "recall": round(mean(recalls) * 100, 2),
        "f1_score": round(mean(f1s) * 100, 2),
        "tasa_error": round(tasa_error * 100, 2),
        "tiempo_promedio_ms": round(mean(tiempos), 2) if tiempos else 0,
        "variabilidad_error": round(variabilidad_error, 3),
        "error_medio_ordinal": round(error_medio_ordinal, 3),
        "por_clase": por_clase,
        "nota": "Las métricas se calculan solo con registros que tengan validación técnica post-cultivo. En modo demo, esos valores son etiquetas simuladas para exposición.",
    }


@app.get("/api/exportar_csv")
def exportar_csv() -> StreamingResponse:
    evaluaciones = obtener_todas_las_evaluaciones()
    salida = io.StringIO()
    escritor = csv.writer(salida, delimiter=";", lineterminator="\n")
    columnas = [
        "id", "productor", "departamento", "cultivo", "provincia", "distrito", "latitud", "longitud", "altitud_msnm", "etapa", "fecha_siembra", "area_hectareas",
        "temperatura_minima", "humedad_suelo", "lluvia_acumulada", "historial_perdidas", "riesgo", "riesgo_real",
        "probabilidad", "puntaje_riesgo", "aptitud_cultivo", "impacto_ubicacion", "tiempo_ms", "causa", "origen",
        "responsable_validacion", "fecha_validacion", "observacion_validacion", "riesgo_modelo", "riesgo_reglas", "bloqueo_critico", "zonas_recomendadas", "creado_en",
    ]
    escritor.writerow(columnas)
    for fila in evaluaciones:
        escritor.writerow([fila.get(columna, "") for columna in columnas])
    contenido = "\ufeff" + salida.getvalue()
    return StreamingResponse(
        iter([contenido.encode("utf-8")]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": "attachment; filename=agroia_peru_evaluaciones_excel.csv"},
    )


@app.get("/api/exportar_csv_comas")
def exportar_csv_comas() -> StreamingResponse:
    evaluaciones = obtener_todas_las_evaluaciones()
    salida = io.StringIO()
    escritor = csv.writer(salida, delimiter=",", lineterminator="\n")
    columnas = [
        "id", "productor", "departamento", "cultivo", "provincia", "distrito", "latitud", "longitud", "altitud_msnm", "etapa", "fecha_siembra", "area_hectareas",
        "temperatura_minima", "humedad_suelo", "lluvia_acumulada", "historial_perdidas", "riesgo", "riesgo_real",
        "probabilidad", "puntaje_riesgo", "aptitud_cultivo", "impacto_ubicacion", "tiempo_ms", "causa", "origen",
        "responsable_validacion", "fecha_validacion", "observacion_validacion", "riesgo_modelo", "riesgo_reglas", "bloqueo_critico", "zonas_recomendadas", "creado_en",
    ]
    escritor.writerow(columnas)
    for fila in evaluaciones:
        escritor.writerow([fila.get(columna, "") for columna in columnas])
    contenido = "\ufeff" + salida.getvalue()
    return StreamingResponse(
        iter([contenido.encode("utf-8")]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": "attachment; filename=agroia_peru_evaluaciones_powerbi.csv"},
    )

@app.get("/api/evaluaciones/{identificador}/reporte_tecnico", response_class=HTMLResponse)
def reporte_tecnico(identificador: int) -> HTMLResponse:
    evaluacion = obtener_evaluacion(identificador)
    recomendaciones = evaluacion.get("recomendaciones") or []
    factores = evaluacion.get("factores") or []
    html = construir_reporte_html(evaluacion, recomendaciones, factores)
    return HTMLResponse(html)


@app.post("/api/evaluaciones/{identificador}/alerta_gmail")
def alerta_gmail(identificador: int, destino: str = Form("")) -> dict[str, Any]:
    evaluacion = obtener_evaluacion(identificador)
    if evaluacion.get("riesgo") != "Alto":
        return {"enviado": False, "mensaje": "No se envió correo porque la alerta no es de riesgo Alto."}

    correo_destino = destino.strip() or os.getenv("GMAIL_DESTINO", "").strip()
    usuario = os.getenv("GMAIL_USUARIO", "").strip()
    clave = os.getenv("GMAIL_APP_PASSWORD", "").strip()
    asunto, cuerpo = construir_correo_alerta(evaluacion)

    if not usuario or not clave or not correo_destino:
        return {
            "enviado": False,
            "modo": "simulado",
            "mensaje": "Alerta armada, pero no enviada: faltan GMAIL_USUARIO, GMAIL_APP_PASSWORD o correo destino en Render.",
            "asunto": asunto,
            "cuerpo": cuerpo,
        }

    mensaje = EmailMessage()
    mensaje["From"] = usuario
    mensaje["To"] = correo_destino
    mensaje["Subject"] = asunto
    mensaje.set_content(cuerpo)
    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=12) as servidor:
            servidor.login(usuario, clave)
            servidor.send_message(mensaje)
    except Exception as error:
        raise HTTPException(status_code=502, detail="No se pudo enviar Gmail. Revisa credenciales o contraseña de aplicación.") from error
    return {"enviado": True, "mensaje": f"Alerta enviada a {correo_destino}"}


@app.get("/plantilla_csv")
def plantilla_csv() -> FileResponse:
    ruta = RUTA_APP / "static" / "plantilla_agroia.csv"
    return FileResponse(ruta, filename="plantilla_agroia_peru.csv")


async def guardar_imagen(imagen: UploadFile | None) -> str | None:
    if imagen is None or not imagen.filename:
        return None
    extension = Path(imagen.filename).suffix.lower()
    if extension not in [".jpg", ".jpeg", ".png", ".webp", ".gif"]:
        raise HTTPException(status_code=400, detail="Formato de imagen no permitido.")
    nombre = f"{uuid.uuid4().hex}{extension}"
    ruta_destino = RUTA_UPLOADS / nombre
    with ruta_destino.open("wb") as buffer:
        shutil.copyfileobj(imagen.file, buffer)
    return f"/static/uploads/{nombre}"


def construir_datos_modelo(departamento: str, cultivo: str, provincia: str, distrito: str, etapa: str, temperatura_minima: float, humedad_suelo: str, lluvia_acumulada: float, historial_perdidas: int, area_hectareas: float) -> dict[str, Any]:
    departamento_limpio = departamento.strip() if departamento and departamento != "Sin especificar" else buscar_departamento_por_provincia(provincia)
    return {
        "departamento": departamento_limpio,
        "cultivo": cultivo,
        "provincia": provincia,
        "distrito": distrito,
        "etapa": etapa,
        "temperatura_minima": float(temperatura_minima),
        "humedad_suelo": humedad_suelo,
        "lluvia_acumulada": float(lluvia_acumulada),
        "historial_perdidas": int(historial_perdidas),
        "area_hectareas": float(area_hectareas),
    }


def guardar_muestra_demo(muestra: dict[str, Any]) -> dict[str, Any]:
    if servicio_ia is None:
        raise HTTPException(status_code=503, detail="El modelo IA aún no está listo.")
    datos = construir_datos_modelo(
        muestra["departamento"], muestra["cultivo"], muestra["provincia"], muestra["distrito"], muestra["etapa"],
        muestra["temperatura_minima"], muestra["humedad_suelo"], muestra["lluvia_acumulada"],
        muestra["historial_perdidas"], muestra["area_hectareas"]
    )
    resultado = servicio_ia.predecir(datos)
    creado_en = datetime.now().isoformat(timespec="seconds")
    with obtener_conexion() as conexion:
        cursor = conexion.execute(
            """
            INSERT INTO evaluaciones (
                productor, departamento, cultivo, provincia, distrito, latitud, longitud, altitud_msnm,
                etapa, fecha_siembra, area_hectareas, temperatura_minima, humedad_suelo, lluvia_acumulada,
                historial_perdidas, observaciones, riesgo, probabilidad, causa,
                recomendaciones, imagen_url, origen, creado_en, riesgo_real,
                puntaje_riesgo, tiempo_ms, factores, metodo_ia, aptitud_cultivo,
                impacto_ubicacion, detalle_aptitud, responsable_validacion,
                fecha_validacion, observacion_validacion, riesgo_modelo, riesgo_reglas,
                bloqueo_critico, zonas_recomendadas, arbol_decision
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                muestra["productor"], datos["departamento"], muestra["cultivo"], muestra["provincia"], muestra["distrito"],
                muestra.get("latitud"), muestra.get("longitud"), muestra.get("altitud_msnm"), muestra["etapa"],
                muestra["fecha_siembra"], muestra["area_hectareas"], muestra["temperatura_minima"], muestra["humedad_suelo"],
                muestra["lluvia_acumulada"], muestra["historial_perdidas"], muestra["observaciones"], resultado["riesgo"],
                resultado["probabilidad"], resultado["causa"], json.dumps(resultado["recomendaciones"], ensure_ascii=False),
                "/static/img/parcela-demo.svg", "demo", creado_en, muestra.get("riesgo_real"), resultado["puntaje_riesgo"],
                resultado["tiempo_ms"], json.dumps(resultado["factores"], ensure_ascii=False), resultado["metodo_ia"],
                resultado["aptitud_cultivo"], resultado["impacto_ubicacion"], resultado["detalle_aptitud"],
                muestra.get("responsable_validacion", ""), muestra.get("fecha_validacion", ""), muestra.get("observacion_validacion", ""),
                resultado.get("riesgo_modelo", ""), resultado.get("riesgo_reglas", ""), int(resultado.get("bloqueo_critico", 0)),
                json.dumps(resultado.get("zonas_recomendadas", []), ensure_ascii=False), json.dumps(resultado.get("arbol_decision", {}), ensure_ascii=False),
            ),
        )
        conexion.commit()
        identificador = cursor.lastrowid
    return obtener_evaluacion(identificador)


def obtener_todas_las_evaluaciones() -> list[dict[str, Any]]:
    with obtener_conexion() as conexion:
        filas = conexion.execute("SELECT * FROM evaluaciones ORDER BY id DESC").fetchall()
    return [fila_a_diccionario(fila) for fila in filas]


def contar_por(evaluaciones: list[dict[str, Any]], campo: str) -> dict[str, int]:
    conteo: dict[str, int] = {}
    for item in evaluaciones:
        clave = str(item.get(campo) or "Sin dato")
        conteo[clave] = conteo.get(clave, 0) + 1
    return conteo



def validar_entrada_productiva(cultivo: str, etapa: str, area_hectareas: float, temperatura_minima: float, humedad_suelo: str, lluvia_acumulada: float, historial_perdidas: int, fecha_siembra: str, latitud: float | None, longitud: float | None) -> None:
    if cultivo not in CULTIVOS_VALIDOS:
        raise HTTPException(status_code=400, detail="Cultivo no permitido para esta demo. Usa Papa nativa, Maíz o Quinua.")
    if etapa not in ETAPAS_VALIDAS:
        raise HTTPException(status_code=400, detail="Etapa del cultivo no válida.")
    if humedad_suelo not in HUMEDADES_VALIDAS:
        raise HTTPException(status_code=400, detail="Humedad del suelo no válida.")
    if not 0.01 <= float(area_hectareas) <= 10000:
        raise HTTPException(status_code=400, detail="Área cultivada fuera de rango razonable.")
    if not -15 <= float(temperatura_minima) <= 45:
        raise HTTPException(status_code=400, detail="Temperatura mínima fuera de rango razonable para evaluación agrícola.")
    if not 0 <= float(lluvia_acumulada) <= 500:
        raise HTTPException(status_code=400, detail="Lluvia acumulada fuera de rango razonable.")
    if int(historial_perdidas) not in [0, 1]:
        raise HTTPException(status_code=400, detail="Historial de pérdidas debe ser 0 o 1.")
    if (latitud is None) != (longitud is None):
        raise HTTPException(status_code=400, detail="Si colocas latitud, también debes colocar longitud, y viceversa.")
    try:
        fecha = datetime.fromisoformat(str(fecha_siembra))
    except ValueError as error:
        raise HTTPException(status_code=400, detail="Fecha de siembra inválida.") from error
    if fecha.year < 2020 or fecha.year > datetime.now().year + 1:
        raise HTTPException(status_code=400, detail="Fecha de siembra fuera del periodo esperado para la demo.")


def estimar_humedad_por_lluvia(lluvia_total: float) -> str:
    if lluvia_total >= 45:
        return "Alta"
    if lluvia_total >= 18:
        return "Media"
    if lluvia_total >= 5:
        return "Baja"
    return "Muy baja"


def construir_correo_alerta(evaluacion: dict[str, Any]) -> tuple[str, str]:
    asunto = f"Alerta AgroIA - Riesgo {evaluacion.get('riesgo')} en {evaluacion.get('distrito')}"
    recomendaciones = evaluacion.get("recomendaciones") or []
    cuerpo = f"""AgroIA Perú detectó una alerta crítica.

Cultivo: {evaluacion.get('cultivo')}
Productor/institución: {evaluacion.get('productor')}
Ubicación: {evaluacion.get('distrito')}, {evaluacion.get('provincia')}, {evaluacion.get('departamento')}
Riesgo IA: {evaluacion.get('riesgo')} ({evaluacion.get('probabilidad')}% confianza)
Puntaje: {evaluacion.get('puntaje_riesgo')}/100
Geodatos: {evaluacion.get('latitud')}, {evaluacion.get('longitud')} - {evaluacion.get('altitud_msnm')} msnm
Causa: {evaluacion.get('causa')}

Recomendaciones:
{chr(10).join('- ' + str(item) for item in recomendaciones[:6])}

Nota: alerta generada automáticamente por AgroIA Perú. Validar en campo antes de tomar decisiones críticas.
"""
    return asunto, cuerpo


def construir_reporte_html(evaluacion: dict[str, Any], recomendaciones: list[Any], factores: list[Any]) -> str:
    lista_recomendaciones = "".join(f"<li>{str(item)}</li>" for item in recomendaciones[:8]) or "<li>Sin recomendaciones registradas.</li>"
    lista_factores = "".join(f"<li>{str(item)}</li>" for item in factores[:8]) or "<li>Sin factores registrados.</li>"
    return f"""
    <!DOCTYPE html>
    <html lang='es'>
    <head>
        <meta charset='utf-8'>
        <title>Reporte AgroIA #{evaluacion.get('id')}</title>
        <style>
            body {{ font-family: Arial, sans-serif; margin: 34px; color: #183126; }}
            .card {{ border: 1px solid #cdd9cf; border-radius: 18px; padding: 20px; margin-bottom: 16px; }}
            h1 {{ color: #0f7a4f; margin-bottom: 4px; }}
            h2 {{ color: #28513e; }}
            .riesgo {{ display: inline-block; padding: 10px 14px; border-radius: 999px; color: white; background: #db3a34; font-weight: bold; }}
            .grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }}
            .dato {{ background: #f3f7f4; padding: 12px; border-radius: 12px; }}
            .nota {{ color: #5c6b61; font-size: 0.92rem; }}
            @media print {{ button {{ display: none; }} body {{ margin: 20px; }} }}
        </style>
    </head>
    <body>
        <button onclick='window.print()'>Imprimir / guardar como PDF</button>
        <h1>Reporte técnico AgroIA Perú</h1>
        <p class='nota'>Sesión VI: IA en proyectos productivos e industriales · Indicadores y análisis predictivo</p>
        <div class='card'>
            <span class='riesgo'>Riesgo {evaluacion.get('riesgo')} · {evaluacion.get('probabilidad')}% confianza</span>
            <h2>{evaluacion.get('cultivo')} - {evaluacion.get('distrito')}</h2>
            <p>{evaluacion.get('causa')}</p>
        </div>
        <div class='grid'>
            <div class='dato'><b>Productor</b><br>{evaluacion.get('productor')}</div>
            <div class='dato'><b>Ubicación</b><br>{evaluacion.get('distrito')}, {evaluacion.get('provincia')}, {evaluacion.get('departamento')}</div>
            <div class='dato'><b>Geodatos</b><br>{evaluacion.get('latitud')}, {evaluacion.get('longitud')} · {evaluacion.get('altitud_msnm')} msnm</div>
            <div class='dato'><b>Clima</b><br>{evaluacion.get('temperatura_minima')} °C · {evaluacion.get('humedad_suelo')} · {evaluacion.get('lluvia_acumulada')} mm</div>
            <div class='dato'><b>Modelo</b><br>{evaluacion.get('metodo_ia')}</div>
            <div class='dato'><b>Tiempo IA</b><br>{evaluacion.get('tiempo_ms')} ms</div>
        </div>
        <div class='card'>
            <h2>Factores detectados</h2>
            <ul>{lista_factores}</ul>
        </div>
        <div class='card'>
            <h2>Recomendaciones</h2>
            <ul>{lista_recomendaciones}</ul>
        </div>
        <p class='nota'>Este reporte es una ayuda para priorizar decisiones. No reemplaza la validación de un técnico agrícola en campo.</p>
    </body>
    </html>
    """


def limpiar_numero_opcional(valor: Any, minimo: float, maximo: float, nombre: str) -> float | None:
    if valor is None or str(valor).strip() == "":
        return None
    try:
        numero = float(str(valor).replace(",", "."))
    except ValueError as error:
        raise HTTPException(status_code=400, detail=f"El campo {nombre} debe ser numérico.") from error
    if numero < minimo or numero > maximo:
        raise HTTPException(status_code=400, detail=f"El campo {nombre} está fuera del rango esperado para Perú.")
    return numero

def limpiar_riesgo_real(valor: str | None) -> str | None:
    if not valor:
        return None
    valor_limpio = str(valor).strip().capitalize()
    return valor_limpio if valor_limpio in RIESGOS else None