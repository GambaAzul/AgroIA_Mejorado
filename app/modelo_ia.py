from __future__ import annotations

from pathlib import Path
from time import perf_counter
from typing import Any

import joblib
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestClassifier
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from .ubicaciones import (
    buscar_departamento_por_provincia,
    debe_sugerir_zonas,
    evaluar_aptitud_provincial,
    listar_distritos,
    listar_provincias,
    obtener_zonas_recomendadas,
)

RUTA_MODELO = Path(__file__).resolve().parent / "modelo" / "modelo_riesgo.pkl"
RUTA_MODELO.parent.mkdir(parents=True, exist_ok=True)

CULTIVOS = ["Papa nativa", "Maíz", "Quinua"]
PROVINCIAS = listar_provincias()
DISTRITOS = listar_distritos()
ETAPAS = ["Siembra", "Emergencia", "Crecimiento", "Floración", "Llenado de grano", "Maduración", "Cosecha"]
HUMEDADES = ["Muy baja", "Baja", "Media", "Alta"]
RIESGOS = ["Bajo", "Medio", "Alto"]
PESO_RIESGO = {"Bajo": 0, "Medio": 1, "Alto": 2}


class ServicioModeloIA:
    """Servicio híbrido: reglas agroclimáticas + Random Forest.

    El modelo no depende solo de datos sintéticos. Primero calcula un puntaje de riesgo
    con reglas explicables y luego usa Random Forest como apoyo. Las reglas críticas
    tienen prioridad para evitar resultados absurdos en heladas, sequías o zonas no aptas.
    """

    def __init__(self) -> None:
        self.entrenar_modelo()
        self.modelo: Pipeline = joblib.load(RUTA_MODELO)

    def entrenar_modelo(self) -> None:
        generador = np.random.default_rng(97)
        filas: list[dict[str, Any]] = []
        etiquetas: list[str] = []

        for _ in range(3600):
            cultivo = str(generador.choice(CULTIVOS))
            provincia = str(generador.choice(PROVINCIAS))
            distrito = str(generador.choice(DISTRITOS))
            departamento = buscar_departamento_por_provincia(provincia)
            etapa = str(generador.choice(ETAPAS))
            humedad_suelo = str(generador.choice(HUMEDADES, p=[0.18, 0.31, 0.33, 0.18]))
            temperatura_minima = float(np.round(generador.normal(5.0, 5.3), 1))
            lluvia_acumulada = float(np.round(max(0, generador.gamma(2.4, 11.5)), 1))
            historial_perdidas = int(generador.choice([0, 1], p=[0.62, 0.38]))
            area_hectareas = float(np.round(generador.uniform(0.3, 12.0), 2))

            datos = {
                "departamento": departamento,
                "cultivo": cultivo,
                "provincia": provincia,
                "distrito": distrito,
                "etapa": etapa,
                "temperatura_minima": temperatura_minima,
                "humedad_suelo": humedad_suelo,
                "lluvia_acumulada": lluvia_acumulada,
                "historial_perdidas": historial_perdidas,
                "area_hectareas": area_hectareas,
            }
            regla = evaluar_reglas_agroclimaticas(datos)
            filas.append(datos)
            etiquetas.append(regla["riesgo"])

        datos_entrenamiento = pd.DataFrame(filas)
        columnas_texto = ["departamento", "cultivo", "provincia", "distrito", "etapa", "humedad_suelo"]
        columnas_numericas = ["temperatura_minima", "lluvia_acumulada", "historial_perdidas", "area_hectareas"]

        preprocesador = ColumnTransformer(
            transformers=[
                ("texto", OneHotEncoder(handle_unknown="ignore"), columnas_texto),
                ("numerico", StandardScaler(), columnas_numericas),
            ]
        )

        modelo = Pipeline(
            steps=[
                ("preprocesador", preprocesador),
                ("clasificador", RandomForestClassifier(n_estimators=260, max_depth=16, random_state=97, class_weight="balanced")),
            ]
        )
        modelo.fit(datos_entrenamiento, etiquetas)
        joblib.dump(modelo, RUTA_MODELO)

    def predecir(self, datos: dict[str, Any]) -> dict[str, Any]:
        inicio = perf_counter()
        datos_normalizados = normalizar_datos(datos)
        entrada = pd.DataFrame([datos_normalizados])

        riesgo_modelo = str(self.modelo.predict(entrada)[0])
        probabilidades = self.modelo.predict_proba(entrada)[0]
        clases = list(self.modelo.classes_)
        probabilidad_modelo = float(probabilidades[clases.index(riesgo_modelo)])

        resultado_reglas = evaluar_reglas_agroclimaticas(datos_normalizados)
        riesgo_final = seleccionar_riesgo_final(riesgo_modelo, resultado_reglas["riesgo"], resultado_reglas["bloqueo_critico"])

        confianza_reglas = min(0.97, 0.50 + resultado_reglas["puntaje"] / 145)
        confianza_final = max(probabilidad_modelo, confianza_reglas if riesgo_final == resultado_reglas["riesgo"] else 0.56)

        causa = construir_causa(riesgo_final, resultado_reglas["factores"])
        recomendaciones = construir_recomendaciones(datos_normalizados, riesgo_final, resultado_reglas["factores"], resultado_reglas["aptitud"])
        zonas_recomendadas = obtener_zonas_recomendadas(datos_normalizados["cultivo"], 6) if debe_sugerir_zonas(resultado_reglas["aptitud"]) else []
        arbol_decision = construir_arbol_decision(datos_normalizados, resultado_reglas, riesgo_modelo, riesgo_final, probabilidad_modelo, zonas_recomendadas)
        tiempo_ms = round((perf_counter() - inicio) * 1000, 2)

        return {
            "riesgo": riesgo_final,
            "probabilidad": round(confianza_final * 100, 2),
            "causa": causa,
            "recomendaciones": recomendaciones,
            "puntaje_riesgo": resultado_reglas["puntaje"],
            "factores": resultado_reglas["factores"],
            "metodo_ia": "Híbrido: reglas agroclimáticas + aptitud provincial + Random Forest",
            "tiempo_ms": tiempo_ms,
            "aptitud_cultivo": resultado_reglas["aptitud"],
            "impacto_ubicacion": resultado_reglas["impacto_ubicacion"],
            "detalle_aptitud": resultado_reglas["detalle_aptitud"],
            "riesgo_modelo": riesgo_modelo,
            "riesgo_reglas": resultado_reglas["riesgo"],
            "bloqueo_critico": int(resultado_reglas["bloqueo_critico"]),
            "zonas_recomendadas": zonas_recomendadas,
            "arbol_decision": arbol_decision,
        }


def normalizar_datos(datos: dict[str, Any]) -> dict[str, Any]:
    provincia = str(datos.get("provincia", ""))
    return {
        "departamento": str(datos.get("departamento") or buscar_departamento_por_provincia(provincia)),
        "cultivo": str(datos["cultivo"]),
        "provincia": provincia,
        "distrito": str(datos["distrito"]),
        "etapa": str(datos["etapa"]),
        "temperatura_minima": float(datos["temperatura_minima"]),
        "humedad_suelo": str(datos["humedad_suelo"]),
        "lluvia_acumulada": float(datos["lluvia_acumulada"]),
        "historial_perdidas": int(datos["historial_perdidas"]),
        "area_hectareas": float(datos["area_hectareas"]),
    }


def evaluar_reglas_agroclimaticas(datos: dict[str, Any]) -> dict[str, Any]:
    cultivo = str(datos["cultivo"])
    provincia = str(datos["provincia"])
    etapa = str(datos["etapa"])
    humedad = str(datos["humedad_suelo"])
    temperatura = float(datos["temperatura_minima"])
    lluvia = float(datos["lluvia_acumulada"])
    historial = int(datos["historial_perdidas"])

    puntaje = 0
    factores: list[str] = []
    bloqueo_critico = False
    etapa_sensible = etapa in ["Emergencia", "Floración", "Llenado de grano"]

    aptitud = evaluar_aptitud_provincial(cultivo, provincia)
    impacto_ubicacion = int(aptitud["impacto_puntaje"])
    puntaje += impacto_ubicacion
    if aptitud["aptitud"] == "Élite":
        factores.append(f"aptitud provincial élite para {cultivo}: reduce el riesgo base")
    elif aptitud["aptitud"] in ["Muy bueno", "Bueno"]:
        factores.append(f"aptitud provincial favorable para {cultivo}: {aptitud['aptitud']}")
    elif aptitud["aptitud"] in ["Malo", "Pésimo"]:
        factores.append(f"aptitud provincial {aptitud['aptitud'].lower()} para {cultivo}: {aptitud['descripcion']}")
    else:
        factores.append(aptitud["descripcion"])

    if temperatura <= 0:
        puntaje += 45
        factores.append("helada severa por temperatura mínima igual o menor a 0 °C")
        bloqueo_critico = True
    elif temperatura <= 2:
        puntaje += 34
        factores.append("temperatura mínima crítica con alta probabilidad de helada")
    elif temperatura <= 4:
        puntaje += 22
        factores.append("temperatura mínima baja para cultivo andino")
    elif temperatura <= 7:
        puntaje += 10
        factores.append("noche fría que requiere vigilancia")

    if humedad == "Muy baja":
        puntaje += 28
        factores.append("humedad del suelo muy baja")
    elif humedad == "Baja":
        puntaje += 18
        factores.append("humedad del suelo baja")
    elif humedad == "Alta":
        puntaje += 8
        factores.append("humedad alta que puede favorecer problemas por exceso de agua")

    if lluvia < 5:
        puntaje += 22
        factores.append("déficit de lluvia acumulada menor a 5 mm")
    elif lluvia < 12:
        puntaje += 12
        factores.append("lluvia acumulada insuficiente entre 5 y 12 mm")
    elif lluvia > 65:
        puntaje += 32
        factores.append("lluvia acumulada excesiva mayor a 65 mm con riesgo de encharcamiento")
    elif lluvia > 45:
        puntaje += 22
        factores.append("exceso de lluvia acumulada entre 45 y 65 mm")

    if etapa_sensible:
        puntaje += 18
        factores.append("etapa fenológica sensible")
    elif etapa in ["Siembra", "Crecimiento"]:
        puntaje += 8
        factores.append("etapa que requiere seguimiento preventivo")

    if cultivo == "Papa nativa" and temperatura <= 3:
        puntaje += 12
        factores.append("papa nativa expuesta a helada")
    if cultivo == "Maíz" and etapa_sensible and temperatura <= 4:
        puntaje += 10
        factores.append("maíz en etapa sensible ante baja temperatura")
    if cultivo == "Quinua" and humedad in ["Muy baja", "Baja"]:
        puntaje += 10
        factores.append("quinua con estrés hídrico probable")
    if cultivo == "Quinua" and lluvia > 45 and humedad == "Alta":
        puntaje += 12
        factores.append("quinua con presión de humedad que puede favorecer enfermedades")

    if historial:
        puntaje += 10
        factores.append("antecedente de pérdidas en campañas previas")

    # Bloqueos críticos para evitar clasificaciones absurdas.
    if temperatura <= 2 and etapa_sensible:
        bloqueo_critico = True
        puntaje = max(puntaje, 76)
        factores.append("combinación crítica: helada probable + etapa sensible")
    if temperatura <= 2 and humedad in ["Muy baja", "Baja"]:
        bloqueo_critico = True
        puntaje = max(puntaje, 78)
        factores.append("combinación crítica: helada probable + baja humedad")
    if temperatura <= 2 and lluvia > 45:
        bloqueo_critico = True
        puntaje = max(puntaje, 82)
        factores.append("combinación crítica: helada probable + exceso de lluvia")
    if lluvia > 65 and etapa_sensible:
        bloqueo_critico = True
        puntaje = max(puntaje, 74)
        factores.append("combinación crítica: exceso de lluvia + etapa sensible")
    if humedad == "Muy baja" and lluvia < 5 and etapa_sensible:
        bloqueo_critico = True
        puntaje = max(puntaje, 80)
        factores.append("combinación crítica: déficit hídrico + etapa sensible")
    if aptitud["aptitud"] == "Pésimo":
        puntaje = max(puntaje, 72)
        factores.append("bloqueo agronómico: cultivo no recomendable para la provincia seleccionada")
        bloqueo_critico = True
    elif aptitud["aptitud"] == "Malo" and (etapa_sensible or temperatura <= 4 or lluvia > 45 or humedad == "Muy baja"):
        puntaje = max(puntaje, 68)
        factores.append("alerta agronómica: mala aptitud provincial combinada con factor climático")

    puntaje = max(0, min(100, int(round(puntaje))))
    if bloqueo_critico or puntaje >= 70:
        riesgo = "Alto"
    elif puntaje >= 40:
        riesgo = "Medio"
    else:
        riesgo = "Bajo"

    factores_unicos = list(dict.fromkeys(factores)) or ["condiciones climáticas dentro de rangos manejables"]
    return {
        "riesgo": riesgo,
        "puntaje": puntaje,
        "factores": factores_unicos,
        "bloqueo_critico": bloqueo_critico,
        "aptitud": aptitud["aptitud"],
        "impacto_ubicacion": impacto_ubicacion,
        "detalle_aptitud": aptitud["descripcion"],
    }


def seleccionar_riesgo_final(riesgo_modelo: str, riesgo_reglas: str, bloqueo_critico: bool) -> str:
    if bloqueo_critico:
        return "Alto"
    if PESO_RIESGO[riesgo_reglas] > PESO_RIESGO[riesgo_modelo]:
        return riesgo_reglas
    return riesgo_modelo


def construir_causa(riesgo: str, factores: list[str]) -> str:
    return f"Riesgo {riesgo.lower()} calculado por IA híbrida. Factores detectados: " + "; ".join(factores) + "."


def construir_recomendaciones(datos: dict[str, Any], riesgo: str, factores: list[str], aptitud: str) -> list[str]:
    recomendaciones: list[str] = []
    temperatura = float(datos["temperatura_minima"])
    lluvia = float(datos["lluvia_acumulada"])
    humedad = str(datos["humedad_suelo"])
    etapa = str(datos["etapa"])

    if aptitud == "Pésimo":
        recomendaciones.append("Reevaluar el cultivo elegido para esta provincia; la aptitud territorial es desfavorable.")
        recomendaciones.append("Comparar con un cultivo alternativo más compatible con el piso agroecológico local.")
    elif aptitud == "Malo":
        recomendaciones.append("Solicitar revisión técnica de aptitud del cultivo antes de ampliar área sembrada.")

    if temperatura <= 3:
        recomendaciones.append("Activar riego nocturno ligero o riego de madrugada en zonas sensibles.")
        recomendaciones.append("Priorizar monitoreo durante las próximas 24 horas por posible helada.")
    if humedad in ["Muy baja", "Baja"]:
        recomendaciones.append("Revisar humedad del suelo y programar riego preventivo por sectores.")
    if lluvia < 8:
        recomendaciones.append("Planificar riego complementario y seguimiento diario del cultivo.")
    if lluvia > 45:
        recomendaciones.append("Verificar drenaje para evitar encharcamiento y daño radicular.")
        recomendaciones.append("Evitar labores que compacten el suelo mientras exista exceso de humedad.")
    if etapa in ["Floración", "Emergencia", "Llenado de grano"]:
        recomendaciones.append("Dar prioridad a las parcelas en etapa sensible del cultivo.")
    if riesgo == "Alto":
        recomendaciones.append("Generar alerta inmediata para técnico agrícola o responsable de la cooperativa.")
        recomendaciones.append("Registrar evidencia fotográfica y actualizar la evaluación al día siguiente.")
    elif riesgo == "Medio":
        recomendaciones.append("Mantener vigilancia y actualizar datos climáticos en la siguiente evaluación.")
    else:
        recomendaciones.append("Continuar monitoreo normal y conservar el registro para trazabilidad.")

    return list(dict.fromkeys(recomendaciones))


def calcular_revision_temperatura(temperatura: float) -> tuple[str, str, str]:
    if temperatura <= 0:
        return "crítico", "Helada severa", "Temperatura igual o menor a 0 °C: se activa una rama de alto riesgo."
    if temperatura <= 2:
        return "crítico", "Helada probable", "Temperatura igual o menor a 2 °C: condición crítica para cultivos sensibles."
    if temperatura <= 4:
        return "alerta", "Frío significativo", "Temperatura baja: requiere vigilancia preventiva."
    if temperatura <= 7:
        return "alerta", "Noche fría", "Condición manejable, pero debe observarse si hay etapa sensible."
    return "bueno", "Temperatura manejable", "No se detecta umbral fuerte de helada por temperatura mínima."


def calcular_revision_humedad(humedad: str) -> tuple[str, str, str]:
    if humedad == "Muy baja":
        return "crítico", "Humedad muy baja", "Estrés hídrico probable; aumenta el puntaje de riesgo."
    if humedad == "Baja":
        return "alerta", "Humedad baja", "Puede generar estrés si se combina con poca lluvia o etapa sensible."
    if humedad == "Alta":
        return "alerta", "Humedad alta", "Puede favorecer problemas por exceso de agua si se combina con lluvia acumulada alta."
    return "bueno", "Humedad media", "Condición hídrica inicial dentro de rango manejable."


def calcular_revision_lluvia(lluvia: float) -> tuple[str, str, str]:
    if lluvia < 5:
        return "crítico", "Déficit de lluvia", "Menos de 5 mm: señal fuerte de déficit hídrico."
    if lluvia < 12:
        return "alerta", "Lluvia insuficiente", "Entre 5 y 12 mm: puede requerir riego complementario."
    if lluvia > 65:
        return "crítico", "Lluvia excesiva", "Más de 65 mm: riesgo de encharcamiento y problemas radiculares."
    if lluvia > 45:
        return "alerta", "Exceso de lluvia", "Entre 45 y 65 mm: revisar drenaje y compactación."
    return "bueno", "Lluvia manejable", "La lluvia acumulada no supera umbrales críticos."


def calcular_revision_etapa(etapa: str) -> tuple[str, str, str]:
    if etapa in ["Emergencia", "Floración", "Llenado de grano"]:
        return "alerta", "Etapa sensible", "La etapa fenológica amplifica el daño por helada, sequía o exceso de agua."
    if etapa in ["Siembra", "Crecimiento"]:
        return "neutro", "Etapa de seguimiento", "Requiere monitoreo preventivo, pero no activa una alerta crítica por sí sola."
    return "bueno", "Etapa menos sensible", "No se considera una de las fases más sensibles del cultivo."


def calcular_revision_aptitud(aptitud: str, impacto: int, detalle: str) -> tuple[str, str, str]:
    if aptitud in ["Élite", "Muy bueno", "Bueno"]:
        return "bueno", f"Aptitud {aptitud}", f"{detalle} Impacto territorial: {impacto:+d} puntos."
    if aptitud == "Regular":
        return "alerta", "Aptitud regular", f"{detalle} No bloquea el cultivo, pero conviene comparar alternativas."
    if aptitud in ["Malo", "Pésimo"]:
        return "crítico", f"Aptitud {aptitud}", f"{detalle} Impacto territorial: {impacto:+d} puntos."
    return "neutro", "Aptitud sin referencia", f"{detalle} Se recomienda validar con fuente local o especialista."


def construir_nodo(titulo: str, valor: str, estado: str, detalle: str, hijos: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    return {
        "titulo": titulo,
        "valor": valor,
        "estado": estado,
        "detalle": detalle,
        "hijos": hijos or [],
    }


def construir_arbol_decision(
    datos: dict[str, Any],
    reglas: dict[str, Any],
    riesgo_modelo: str,
    riesgo_final: str,
    probabilidad_modelo: float,
    zonas_recomendadas: list[dict[str, Any]],
) -> dict[str, Any]:
    temperatura = float(datos["temperatura_minima"])
    lluvia = float(datos["lluvia_acumulada"])
    humedad = str(datos["humedad_suelo"])
    etapa = str(datos["etapa"])
    historial = int(datos["historial_perdidas"])
    aptitud = str(reglas["aptitud"])
    impacto = int(reglas["impacto_ubicacion"])
    detalle = str(reglas["detalle_aptitud"])

    estado_temp, titulo_temp, detalle_temp = calcular_revision_temperatura(temperatura)
    estado_humedad, titulo_humedad, detalle_humedad = calcular_revision_humedad(humedad)
    estado_lluvia, titulo_lluvia, detalle_lluvia = calcular_revision_lluvia(lluvia)
    estado_etapa, titulo_etapa, detalle_etapa = calcular_revision_etapa(etapa)
    estado_aptitud, titulo_aptitud, detalle_aptitud = calcular_revision_aptitud(aptitud, impacto, detalle)
    estado_historial = "alerta" if historial else "bueno"
    estado_final = "crítico" if riesgo_final == "Alto" else "alerta" if riesgo_final == "Medio" else "bueno"

    hijos_territorio = [
        construir_nodo("Provincia", str(datos["provincia"]), estado_aptitud, detalle_aptitud),
    ]
    if zonas_recomendadas:
        hijos_territorio.append(construir_nodo(
            "Zonas sugeridas",
            ", ".join(f"{zona['provincia']} ({zona['departamento']})" for zona in zonas_recomendadas[:4]),
            "bueno",
            "Estas provincias tienen aptitud territorial más favorable para el cultivo seleccionado.",
        ))

    return {
        "titulo": "Árbol visual de evaluación AgroIA",
        "subtitulo": "Cada rama muestra una decisión evaluada antes de llegar al riesgo final.",
        "raiz": construir_nodo(
            "Parcela evaluada",
            f"{datos['cultivo']} · {datos['distrito']}, {datos['provincia']}",
            "neutro",
            "Entrada principal enviada al modelo híbrido.",
            [
                construir_nodo(
                    "Aptitud territorial",
                    titulo_aptitud,
                    estado_aptitud,
                    "El sistema cruza cultivo y provincia antes de confiar solo en el clima.",
                    hijos_territorio,
                ),
                construir_nodo(
                    "Clima inmediato",
                    "Temperatura, lluvia y humedad",
                    "alerta" if any(estado in ["alerta", "crítico"] for estado in [estado_temp, estado_humedad, estado_lluvia]) else "bueno",
                    "Ramas climáticas principales usadas para el puntaje 0 a 100.",
                    [
                        construir_nodo("Temperatura mínima", f"{temperatura:g} °C · {titulo_temp}", estado_temp, detalle_temp),
                        construir_nodo("Humedad del suelo", f"{humedad} · {titulo_humedad}", estado_humedad, detalle_humedad),
                        construir_nodo("Lluvia acumulada", f"{lluvia:g} mm · {titulo_lluvia}", estado_lluvia, detalle_lluvia),
                    ],
                ),
                construir_nodo(
                    "Cultivo y manejo",
                    etapa,
                    estado_etapa,
                    "El riesgo sube si el cultivo está en una fase fenológica sensible.",
                    [
                        construir_nodo("Etapa fenológica", etapa, estado_etapa, detalle_etapa),
                        construir_nodo(
                            "Historial de pérdidas",
                            "Sí" if historial else "No",
                            estado_historial,
                            "Si la parcela ya tuvo pérdidas, se suma riesgo por vulnerabilidad histórica." if historial else "No agrega penalización histórica al puntaje.",
                        ),
                    ],
                ),
                construir_nodo(
                    "Random Forest",
                    f"Voto base: {riesgo_modelo}",
                    "alerta" if riesgo_modelo == "Medio" else "crítico" if riesgo_modelo == "Alto" else "bueno",
                    f"El clasificador supervisado entrega una clase base con confianza aproximada de {round(probabilidad_modelo * 100, 2)}%.",
                ),
                construir_nodo(
                    "Reglas críticas",
                    "Bloqueo activo" if reglas["bloqueo_critico"] else "Sin bloqueo crítico",
                    "crítico" if reglas["bloqueo_critico"] else "bueno",
                    "Si aparece una combinación peligrosa, la regla preventiva puede elevar el riesgo final.",
                ),
                construir_nodo(
                    "Decisión final",
                    f"Riesgo {riesgo_final} · {reglas['puntaje']}/100",
                    estado_final,
                    "Resultado final después de combinar Random Forest, reglas agroclimáticas y aptitud territorial.",
                ),
            ],
        ),
    }
