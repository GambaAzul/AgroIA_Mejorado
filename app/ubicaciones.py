from __future__ import annotations

import unicodedata
from typing import Any

CATALOGO_UBICACIONES: dict[str, dict[str, list[str]]] = {
    "Huancavelica": {
        "Tayacaja": ["Pampas", "Acraquia", "Ahuaycha", "Colcabamba", "Daniel Hernández", "Huaribamba", "Quichuas"],
        "Huancavelica": ["Huancavelica", "Acoria", "Ascensión", "Yauli", "Palca"],
    },
    "Cusco": {
        "Paucartambo": ["Paucartambo", "Caicay", "Challabamba", "Colquepata", "Huancarani", "Kosñipata"],
        "Quispicanchi": ["Urcos", "Andahuaylillas", "Oropesa", "Lucre", "Quiquijana", "Cusipata"],
        "Urubamba": ["Urubamba", "Ollantaytambo", "Yucay", "Maras", "Chinchero", "Machupicchu"],
        "Calca": ["Calca", "Pisac", "Lamay", "Coya", "San Salvador", "Taray"],
        "Anta": ["Anta", "Zurite", "Ancahuasi", "Cachimayo", "Huarocondo"],
        "Espinar": ["Espinar", "Coporaque", "Pallpata", "Pichigua", "Suyckutambo"],
        "Chumbivilcas": ["Santo Tomás", "Colquemarca", "Llusco", "Quiñota", "Velille"],
    },
    "Huánuco": {
        "Huánuco": ["Huánuco", "Amarilis", "Pillco Marca", "Santa María del Valle", "Chinchao"],
        "Pachitea": ["Panao", "Chaglla", "Molino", "Umari"],
    },
    "Apurímac": {
        "Andahuaylas": ["Andahuaylas", "Talavera", "San Jerónimo", "Pacucha", "Kishuara"],
        "Abancay": ["Abancay", "Curahuasi", "Tamburco", "Huanipaca", "Lambrama"],
    },
    "Puno": {
        "San Román": ["Juliaca", "Cabana", "Cabanillas", "Caracoto", "San Miguel"],
        "Azángaro": ["Azángaro", "Asillo", "Arapa", "Chupa", "Santiago de Pupuja"],
        "El Collao": ["Ilave", "Capazo", "Pilcuyo", "Santa Rosa", "Conduriri"],
        "San Antonio de Putina": ["Putina", "Ananea", "Pedro Vilca Apaza", "Quilcapuncu", "Sina"],
    },
    "Ayacucho": {
        "Huamanga": ["Ayacucho", "Acocro", "Acos Vinchos", "Chiara", "Quinua", "Pacaycasa"],
    },
    "Arequipa": {
        "Caylloma": ["Chivay", "Majes", "Yanque", "Cabanaconde", "Achoma", "Coporaque"],
    },
    "Áncash": {
        "Carhuaz": ["Carhuaz", "Marcará", "Acopampa", "Anta", "Ataquero", "Tinco"],
    },
    "Loreto": {
        "Maynas": ["Iquitos", "Punchana", "San Juan Bautista", "Belén", "Indiana"],
    },
    "Ucayali": {
        "Coronel Portillo": ["Callería", "Yarinacocha", "Manantay", "Campo Verde", "Nueva Requena"],
    },
    "Madre de Dios": {
        "Tambopata": ["Tambopata", "Inambari", "Las Piedras", "Laberinto"],
    },
}


COORDENADAS_REFERENCIA: dict[str, dict[str, dict[str, dict[str, float]]]] = {
    "Huancavelica": {
        "Tayacaja": {
            "_centro": {"latitud": -12.3667, "longitud": -74.8667, "altitud_msnm": 3270},
            "Pampas": {"latitud": -12.3989, "longitud": -74.8667, "altitud_msnm": 3276},
        },
        "Huancavelica": {"_centro": {"latitud": -12.7864, "longitud": -74.9756, "altitud_msnm": 3676}},
    },
    "Cusco": {
        "Paucartambo": {"_centro": {"latitud": -13.3150, "longitud": -71.5942, "altitud_msnm": 2906}},
        "Quispicanchi": {"_centro": {"latitud": -13.6890, "longitud": -71.6230, "altitud_msnm": 3150}},
        "Urubamba": {
            "_centro": {"latitud": -13.3047, "longitud": -72.1167, "altitud_msnm": 2871},
            "Urubamba": {"latitud": -13.3047, "longitud": -72.1167, "altitud_msnm": 2871},
            "Ollantaytambo": {"latitud": -13.2581, "longitud": -72.2633, "altitud_msnm": 2792},
            "Chinchero": {"latitud": -13.3922, "longitud": -72.0478, "altitud_msnm": 3760},
        },
        "Calca": {"_centro": {"latitud": -13.3214, "longitud": -71.9561, "altitud_msnm": 2928}},
        "Anta": {"_centro": {"latitud": -13.4706, "longitud": -72.1486, "altitud_msnm": 3345}, "Anta": {"latitud": -13.4706, "longitud": -72.1486, "altitud_msnm": 3345}},
        "Espinar": {"_centro": {"latitud": -14.7939, "longitud": -71.4142, "altitud_msnm": 3927}},
        "Chumbivilcas": {"_centro": {"latitud": -14.4500, "longitud": -72.0800, "altitud_msnm": 3660}},
    },
    "Huánuco": {
        "Huánuco": {"_centro": {"latitud": -9.9306, "longitud": -76.2422, "altitud_msnm": 1894}},
        "Pachitea": {"_centro": {"latitud": -9.8978, "longitud": -75.9944, "altitud_msnm": 2560}},
    },
    "Apurímac": {
        "Andahuaylas": {
            "_centro": {"latitud": -13.6556, "longitud": -73.3872, "altitud_msnm": 2926},
            "Talavera": {"latitud": -13.6533, "longitud": -73.4303, "altitud_msnm": 2820},
            "Andahuaylas": {"latitud": -13.6556, "longitud": -73.3872, "altitud_msnm": 2926},
        },
        "Abancay": {
            "_centro": {"latitud": -13.6339, "longitud": -72.8814, "altitud_msnm": 2378},
            "Abancay": {"latitud": -13.6339, "longitud": -72.8814, "altitud_msnm": 2378},
        },
    },
    "Puno": {
        "San Román": {
            "_centro": {"latitud": -15.4997, "longitud": -70.1333, "altitud_msnm": 3825},
            "Juliaca": {"latitud": -15.4997, "longitud": -70.1333, "altitud_msnm": 3825},
        },
        "Azángaro": {"_centro": {"latitud": -14.9086, "longitud": -70.1961, "altitud_msnm": 3859}},
        "El Collao": {"_centro": {"latitud": -16.0833, "longitud": -69.6333, "altitud_msnm": 3850}},
        "San Antonio de Putina": {
            "_centro": {"latitud": -14.9144, "longitud": -69.8681, "altitud_msnm": 3875},
            "Putina": {"latitud": -14.9144, "longitud": -69.8681, "altitud_msnm": 3875},
        },
    },
    "Ayacucho": {
        "Huamanga": {
            "_centro": {"latitud": -13.1631, "longitud": -74.2236, "altitud_msnm": 2761},
            "Quinua": {"latitud": -13.0492, "longitud": -74.1381, "altitud_msnm": 3270},
            "Ayacucho": {"latitud": -13.1631, "longitud": -74.2236, "altitud_msnm": 2761},
        },
    },
    "Arequipa": {"Caylloma": {"_centro": {"latitud": -15.6383, "longitud": -71.6011, "altitud_msnm": 3635}}},
    "Áncash": {"Carhuaz": {"_centro": {"latitud": -9.2811, "longitud": -77.6458, "altitud_msnm": 2638}}},
    "La Libertad": {
        "Trujillo": {
            "_centro": {"latitud": -8.1116, "longitud": -79.0287, "altitud_msnm": 34},
            "Trujillo": {"latitud": -8.1116, "longitud": -79.0287, "altitud_msnm": 34},
            "Moche": {"latitud": -8.1714, "longitud": -79.0097, "altitud_msnm": 4},
            "Huanchaco": {"latitud": -8.0797, "longitud": -79.1203, "altitud_msnm": 23},
        },
        "Sánchez Carrión": {"_centro": {"latitud": -7.8147, "longitud": -78.0458, "altitud_msnm": 3169}},
    },
    "Loreto": {"Maynas": {"_centro": {"latitud": -3.7437, "longitud": -73.2516, "altitud_msnm": 106}}},
    "Ucayali": {"Coronel Portillo": {"_centro": {"latitud": -8.3791, "longitud": -74.5539, "altitud_msnm": 154}}},
    "Madre de Dios": {
        "Tambopata": {
            "_centro": {"latitud": -12.5933, "longitud": -69.1891, "altitud_msnm": 186},
            "Tambopata": {"latitud": -12.5933, "longitud": -69.1891, "altitud_msnm": 186},
        },
    },
}

APTITUD_PROVINCIAL: dict[str, dict[str, tuple[str, str]]] = {
    "Tayacaja": {
        "Papa nativa": ("Élite", "Altura y tradición favorable para papa nativa."),
        "Quinua": ("Muy bueno", "Zona altoandina compatible con quinua."),
        "Maíz": ("Pésimo", "Altitud dominante fría; el maíz amiláceo puede pasmarse."),
    },
    "Paucartambo": {
        "Papa nativa": ("Élite", "Comunidades altoandinas guardianas de variedades nativas."),
        "Quinua": ("Bueno", "Compatible en zonas altas con manejo adecuado."),
        "Maíz": ("Regular", "Mejor en zonas templadas específicas."),
    },
    "Quispicanchi": {
        "Papa nativa": ("Élite", "Zonas altoandinas con buena aptitud para papa nativa."),
        "Quinua": ("Muy bueno", "Altura y radiación favorables para quinua."),
        "Maíz": ("Regular", "Viable en valles, sensible en zonas altas."),
    },
    "Huánuco": {
        "Papa nativa": ("Muy bueno", "Zonas andinas con tradición papera."),
        "Quinua": ("Regular", "Requiere manejo por variación de pisos."),
        "Maíz": ("Bueno", "Valles interandinos aptos."),
    },
    "Pachitea": {
        "Papa nativa": ("Muy bueno", "Áreas altoandinas favorables para papa."),
        "Quinua": ("Regular", "Viable con control de humedad."),
        "Maíz": ("Regular", "Depende del valle y altitud."),
    },
    "Andahuaylas": {
        "Papa nativa": ("Élite", "Tierras altoandinas reconocidas por papa."),
        "Quinua": ("Bueno", "Zonas altas compatibles."),
        "Maíz": ("Regular", "Mejor en zonas más templadas."),
    },
    "San Román": {
        "Papa nativa": ("Regular", "Resiste en altiplano, pero enfrenta heladas frecuentes."),
        "Quinua": ("Élite", "Altiplano con condiciones muy favorables para quinua."),
        "Maíz": ("Pésimo", "Altitud y heladas hacen inviable el maíz amiláceo en muchos casos."),
    },
    "Azángaro": {
        "Papa nativa": ("Regular", "Puede resistir, pero con alto riesgo de helada."),
        "Quinua": ("Élite", "Zona altiplánica favorable para quinua."),
        "Maíz": ("Pésimo", "Demasiado frío para maíz amiláceo."),
    },
    "El Collao": {
        "Papa nativa": ("Regular", "Requiere manejo preventivo de heladas."),
        "Quinua": ("Élite", "Altiplano apropiado para quinua."),
        "Maíz": ("Pésimo", "Heladas y altura limitan severamente el maíz."),
    },
    "Huamanga": {
        "Papa nativa": ("Bueno", "Zonas altas aptas para tubérculos andinos."),
        "Quinua": ("Muy bueno", "Produce quinua blanca y roja de buena calidad."),
        "Maíz": ("Regular", "Depende de valles y disponibilidad hídrica."),
    },
    "Caylloma": {
        "Papa nativa": ("Bueno", "Zonas altoandinas viables."),
        "Quinua": ("Muy bueno", "Microclimas andinos favorables para quinua."),
        "Maíz": ("Regular", "Viable en zonas templadas, limitado por altura."),
    },
    "Urubamba": {
        "Papa nativa": ("Malo", "La geografía dominante de valle favorece más al maíz que a la papa nativa pura."),
        "Quinua": ("Regular", "Puede funcionar en sectores altos, no es su ventaja principal."),
        "Maíz": ("Élite", "Valle protegido y clima favorable para maíz amiláceo."),
    },
    "Calca": {
        "Papa nativa": ("Regular", "Mejor en zonas altas de la provincia."),
        "Quinua": ("Regular", "Depende de altitud y humedad."),
        "Maíz": ("Élite", "Valle favorable para maíz amiláceo."),
    },
    "Abancay": {
        "Papa nativa": ("Regular", "Mejor en pisos más altos."),
        "Quinua": ("Regular", "Viable con manejo climático."),
        "Maíz": ("Muy bueno", "Valles interandinos templados favorables."),
    },
    "Carhuaz": {
        "Papa nativa": ("Bueno", "Zonas andinas aptas para tubérculos."),
        "Quinua": ("Bueno", "Clima andino compatible."),
        "Maíz": ("Muy bueno", "Callejón de Huaylas con clima templado y agua disponible."),
    },
    "Trujillo": {
        "Papa nativa": ("Pésimo", "Provincia costera; calor y condiciones no dominantes para cultivo andino de altura."),
        "Quinua": ("Pésimo", "Costa con mayor presión de calor y salinidad para quinua andina."),
        "Maíz": ("Pésimo", "No corresponde al entorno dominante del maíz amiláceo andino."),
    },
    "Maynas": {
        "Papa nativa": ("Pésimo", "Selva baja cálida y húmeda; alto riesgo de pudrición."),
        "Quinua": ("Pésimo", "Calor y lluvias constantes elevan riesgo de hongos."),
        "Maíz": ("Malo", "No es zona dominante para maíz amiláceo andino."),
    },
    "Coronel Portillo": {
        "Papa nativa": ("Pésimo", "Selva baja con calor y humedad extrema."),
        "Quinua": ("Pésimo", "Alta presión de hongos por humedad y calor."),
        "Maíz": ("Malo", "No es aptitud principal para maíz amiláceo andino."),
    },
    "Tambopata": {
        "Papa nativa": ("Pésimo", "Ambiente amazónico húmedo y cálido."),
        "Quinua": ("Pésimo", "Riesgo alto de mildiú y hongos por humedad constante."),
        "Maíz": ("Malo", "No es entorno dominante para maíz amiláceo andino."),
    },
}

PUNTAJE_APTITUD = {
    "Élite": -10,
    "Muy bueno": -6,
    "Bueno": -3,
    "Regular": 0,
    "Malo": 20,
    "Pésimo": 38,
}


def normalizar_texto(valor: str) -> str:
    texto = unicodedata.normalize("NFKD", str(valor or ""))
    texto = "".join(caracter for caracter in texto if not unicodedata.combining(caracter))
    return texto.strip().lower()


def buscar_departamento_por_provincia(provincia: str) -> str:
    objetivo = normalizar_texto(provincia)
    for departamento, provincias in CATALOGO_UBICACIONES.items():
        for nombre_provincia in provincias:
            if normalizar_texto(nombre_provincia) == objetivo:
                return departamento
    return "Sin especificar"


def buscar_distritos(provincia: str) -> list[str]:
    objetivo = normalizar_texto(provincia)
    for provincias in CATALOGO_UBICACIONES.values():
        for nombre_provincia, distritos in provincias.items():
            if normalizar_texto(nombre_provincia) == objetivo:
                return distritos
    return []


def evaluar_aptitud_provincial(cultivo: str, provincia: str) -> dict[str, Any]:
    cultivo_limpio = str(cultivo)
    provincia_objetivo = normalizar_texto(provincia)
    provincia_real = None
    for provincia_catalogo in APTITUD_PROVINCIAL:
        if normalizar_texto(provincia_catalogo) == provincia_objetivo:
            provincia_real = provincia_catalogo
            break

    if provincia_real is None:
        return {
            "aptitud": "Sin referencia",
            "impacto_puntaje": 4,
            "descripcion": "Provincia sin referencia agronómica específica; se aplica penalización leve por incertidumbre.",
        }

    aptitud, descripcion = APTITUD_PROVINCIAL[provincia_real].get(
        cultivo_limpio,
        ("Regular", "No existe referencia específica para el cruce cultivo-provincia."),
    )
    return {
        "aptitud": aptitud,
        "impacto_puntaje": PUNTAJE_APTITUD.get(aptitud, 0),
        "descripcion": descripcion,
    }


def obtener_zonas_recomendadas(cultivo: str, limite: int = 6) -> list[dict[str, Any]]:
    """Devuelve provincias con mejor aptitud para orientar al usuario.

    Es un catálogo demostrativo y priorizado para exposición; no reemplaza un
    estudio agronómico detallado por parcela.
    """
    prioridad = {"Élite": 0, "Muy bueno": 1, "Bueno": 2, "Regular": 3, "Malo": 4, "Pésimo": 5}
    zonas: list[dict[str, Any]] = []
    for provincia, cultivos in APTITUD_PROVINCIAL.items():
        if cultivo not in cultivos:
            continue
        aptitud, descripcion = cultivos[cultivo]
        if aptitud in {"Élite", "Muy bueno", "Bueno"}:
            zonas.append({
                "departamento": buscar_departamento_por_provincia(provincia),
                "provincia": provincia,
                "aptitud": aptitud,
                "descripcion": descripcion,
            })
    zonas.sort(key=lambda item: (prioridad.get(item["aptitud"], 9), item["departamento"], item["provincia"]))
    return zonas[:limite]


def debe_sugerir_zonas(aptitud: str) -> bool:
    return aptitud in {"Regular", "Malo", "Pésimo", "Sin referencia"}


def obtener_catalogo_para_api() -> dict[str, Any]:
    return {
        "catalogo": CATALOGO_UBICACIONES,
        "cultivos": ["Papa nativa", "Maíz", "Quinua"],
        "etapas": ["Siembra", "Emergencia", "Crecimiento", "Floración", "Llenado de grano", "Maduración", "Cosecha"],
        "humedades": ["Muy baja", "Baja", "Media", "Alta"],
        "zonas_recomendadas": {cultivo: obtener_zonas_recomendadas(cultivo, 8) for cultivo in ["Papa nativa", "Maíz", "Quinua"]},
        "coordenadas": COORDENADAS_REFERENCIA,
        "nota": "Catálogo agrícola priorizado para exposición. Para producción debe reemplazarse por UBIGEO oficial completo.",
    }


def listar_provincias() -> list[str]:
    provincias: list[str] = []
    for provincias_departamento in CATALOGO_UBICACIONES.values():
        provincias.extend(provincias_departamento.keys())
    return sorted(provincias)


def listar_distritos() -> list[str]:
    distritos: list[str] = []
    for provincias_departamento in CATALOGO_UBICACIONES.values():
        for distritos_provincia in provincias_departamento.values():
            distritos.extend(distritos_provincia)
    return sorted(set(distritos))
