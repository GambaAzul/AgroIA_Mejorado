const estado = {
    evaluaciones: [],
    resumen: null,
    metricas: null,
    catalogo: {},
    coordenadas: {},
    segmentosRiesgo: [],
    barrasCultivo: [],
    parcelas: [],
    mapaLeaflet: null,
    capaMarcadores: null,
    capaBaseNormal: null,
    capaBaseSatelital: null,
    soloLectura: false
};

const coloresRiesgo = {
    Alto: '#db3a34',
    Medio: '#f4b23e',
    Bajo: '#33c481'
};

const limitesPeru = {
    latMin: -18.7,
    latMax: 0.2,
    lonMin: -81.6,
    lonMax: -68.0
};

const contornoPeru = [
    [-80.6, -3.4], [-80.2, -4.8], [-80.8, -6.0], [-79.4, -7.4], [-79.1, -8.3],
    [-78.7, -9.6], [-77.4, -10.8], [-76.8, -12.2], [-76.3, -13.4], [-75.5, -14.6],
    [-74.3, -16.1], [-73.2, -17.2], [-71.6, -17.4], [-70.3, -18.2], [-69.4, -17.1],
    [-69.8, -15.2], [-69.0, -13.6], [-69.6, -12.2], [-68.7, -10.8], [-70.0, -9.9],
    [-70.3, -8.4], [-69.2, -7.1], [-70.5, -5.8], [-70.0, -4.1], [-71.7, -3.1],
    [-73.4, -3.7], [-74.7, -2.4], [-76.1, -1.2], [-77.8, -0.4], [-79.4, -1.6]
];

const rutaPeruSvg = 'M 37.60 31.45 L 38.79 35.61 L 37.00 39.18 L 41.17 43.35 L 42.06 46.02 L 43.25 49.89 L 47.12 53.46 L 48.90 57.63 L 50.39 61.20 L 52.77 64.77 L 56.34 69.23 L 59.61 72.50 L 64.37 73.10 L 68.24 75.48 L 70.92 72.21 L 69.73 66.55 L 72.11 61.79 L 70.32 57.63 L 73.00 53.46 L 69.13 50.79 L 68.24 46.32 L 71.51 42.45 L 67.64 38.59 L 69.13 33.53 L 64.07 30.55 L 59.02 32.34 L 55.15 28.47 L 50.98 24.90 L 45.93 22.52 L 41.17 26.09 Z';

const lineasInternasPeru = [
    'M 44.60 35.20 L 63.40 35.20',
    'M 43.80 42.20 L 67.80 42.20',
    'M 43.40 49.30 L 69.60 49.30',
    'M 45.40 56.60 L 69.30 56.60',
    'M 48.30 63.70 L 68.50 63.70',
    'M 52.60 70.00 L 66.80 70.00',
    'M 47.40 31.00 L 48.70 64.80',
    'M 54.10 27.50 L 56.20 72.60',
    'M 61.10 30.50 L 63.20 73.40'
];

document.addEventListener('DOMContentLoaded', async () => {
    enlazarEventos();
    establecerFechaInicial();
    await cargarCatalogo();
    await cargarParcelasVerificadas();
    configurarSimulador();
    await cargarResumen();
});

function enlazarEventos() {
    document.getElementById('btnDemo').addEventListener('click', cargarDemo);
    document.getElementById('btnLimpiarDemo').addEventListener('click', limpiarDemo);
    document.getElementById('btnMapaNormal')?.addEventListener('click', () => cambiarCapaMapa('normal'));
    document.getElementById('btnMapaSatelital')?.addEventListener('click', () => cambiarCapaMapa('satelital'));
    document.getElementById('campoParcelaVerificada')?.addEventListener('change', aplicarParcelaVerificada);
    document.getElementById('btnClimaAutomatico').addEventListener('click', traerClimaAutomatico);
    document.getElementById('formEvaluacion').addEventListener('submit', crearEvaluacion);
    document.getElementById('formImportar').addEventListener('submit', importarCsv);
    document.getElementById('imagenParcela').addEventListener('change', previsualizarImagen);
    document.getElementById('cerrarModal').addEventListener('click', cerrarModal);
    document.querySelectorAll('[data-actualizar]').forEach((boton) => boton.addEventListener('click', cargarResumen));
    ['buscarTexto', 'filtroRiesgo', 'filtroOrigen'].forEach((id) => {
        document.getElementById(id).addEventListener('input', renderizarTabla);
    });
    document.getElementById('graficoRiesgo').addEventListener('mousemove', moverSobreRiesgo);
    document.getElementById('graficoCultivos').addEventListener('mousemove', moverSobreCultivos);
    document.getElementById('graficoRiesgo').addEventListener('mouseleave', ocultarTooltip);
    document.getElementById('graficoCultivos').addEventListener('mouseleave', ocultarTooltip);
    document.getElementById('campoDepartamento').addEventListener('change', actualizarProvincias);
    document.getElementById('campoProvincia').addEventListener('change', actualizarDistritos);
    document.getElementById('campoDistrito').addEventListener('change', () => { actualizarCoordenadasEstimadas(); actualizarParcelasDisponibles(true); });
}

function establecerFechaInicial() {
    const campoFecha = document.querySelector('input[name="fecha_siembra"]');
    const fecha = new Date();
    fecha.setDate(fecha.getDate() - 65);
    campoFecha.value = fecha.toISOString().slice(0, 10);
}

async function cargarCatalogo() {
    const respuesta = await fetch('/api/catalogo');
    const datos = await respuesta.json();
    estado.catalogo = datos.catalogo || {};
    estado.coordenadas = datos.coordenadas || {};
    llenarDepartamentos();
}

function construirCatalogoDesdeParcelas(parcelas) {
    const catalogo = {};
    parcelas.forEach((item) => {
        if (!item.departamento || !item.provincia || !item.distrito) return;
        catalogo[item.departamento] = catalogo[item.departamento] || {};
        catalogo[item.departamento][item.provincia] = catalogo[item.departamento][item.provincia] || [];
        if (!catalogo[item.departamento][item.provincia].includes(item.distrito)) {
            catalogo[item.departamento][item.provincia].push(item.distrito);
        }
    });
    Object.values(catalogo).forEach((provincias) => {
        Object.keys(provincias).forEach((provincia) => {
            provincias[provincia].sort((a, b) => a.localeCompare(b, 'es'));
        });
    });
    return catalogo;
}

async function cargarParcelasVerificadas() {
    try {
        const respuesta = await fetch('/api/parcelas_verificadas');
        const datos = await respuesta.json();
        estado.parcelas = datos.parcelas || [];

        if (estado.parcelas.length) {
            estado.catalogo = construirCatalogoDesdeParcelas(estado.parcelas);
            llenarDepartamentos();
        }
        actualizarParcelasDisponibles(true);
    } catch (error) {
        estado.parcelas = [];
        console.warn('No se pudo cargar parcelas verificadas', error);
    }
}


function limpiarNombreParcela(nombre = '') {
    return String(nombre)
        .replace(/\s[-–]\s*(papa nativa|quinua|ma[ií]z|papa|tub[eé]rculos|quinua y papa|papa y ma[ií]z).*$/i, '')
        .replace(/\s+$/g, '');
}

function actualizarParcelasDisponibles(aplicarPrimera = false) {
    const selector = document.getElementById('campoParcelaVerificada');
    if (!selector) return;
    const departamento = document.getElementById('campoDepartamento')?.value || '';
    const provincia = document.getElementById('campoProvincia')?.value || '';
    const distrito = document.getElementById('campoDistrito')?.value || '';
    const parcelas = estado.parcelas.filter((item) =>
        (!departamento || item.departamento === departamento) &&
        (!provincia || item.provincia === provincia) &&
        (!distrito || item.distrito === distrito)
    );

    selector.innerHTML = parcelas.map((item) =>
        `<option value="${escapar(item.id)}">${escapar(limpiarNombreParcela(item.nombre_parcela))}</option>`
    ).join('');
    selector.disabled = !parcelas.length;

    const nota = document.getElementById('notaParcela');
    if (nota) {
        nota.textContent = parcelas.length
            ? `${parcelas.length} zona agrícola rural disponible para esta ubicación.`
            : 'Sin zona agrícola registrada para esta combinación.';
    }

    if (parcelas.length && (aplicarPrimera || !parcelas.some((item) => item.id === selector.value))) {
        selector.value = parcelas[0].id;
        aplicarParcelaVerificada(true);
    } else if (!parcelas.length) {
        limpiarGeodatosParcela();
    }
}

function limpiarGeodatosParcela() {
    ['campoLatitud', 'campoLongitud', 'campoAltitud', 'campoArea'].forEach((id) => {
        const campo = document.getElementById(id);
        if (campo) campo.value = '';
    });
}

function aplicarParcelaVerificada(silencioso = false) {
    const id = document.getElementById('campoParcelaVerificada')?.value;
    const parcela = estado.parcelas.find((item) => item.id === id);
    if (!parcela) return;
    document.querySelector('input[name="productor"]').value = parcela.productor || parcela.nombre_parcela || '';
    document.getElementById('campoLatitud').value = Number(parcela.latitud).toFixed(6);
    document.getElementById('campoLongitud').value = Number(parcela.longitud).toFixed(6);
    document.getElementById('campoAltitud').value = Math.round(Number(parcela.altitud_msnm || 0));
    const area = document.querySelector('input[name="area_hectareas"]');
    if (area && parcela.area_hectareas) area.value = Number(parcela.area_hectareas).toFixed(2);
    if (!silencioso || silencioso instanceof Event) mostrarNotificacion('Zona agrícola aplicada. Coordenadas, altitud y hectáreas rellenadas. Puedes elegir papa, maíz o quinua libremente.');
}

function llenarDepartamentos() {
    const selector = document.getElementById('campoDepartamento');
    const departamentos = Object.keys(estado.catalogo).sort((a, b) => a.localeCompare(b, 'es'));
    selector.innerHTML = departamentos.map((departamento) => `<option value="${escapar(departamento)}">${escapar(departamento)}</option>`).join('');
    if (departamentos.includes('Cusco')) selector.value = 'Cusco';
    actualizarProvincias();
}

function actualizarProvincias() {
    const departamento = document.getElementById('campoDepartamento').value;
    const selectorProvincia = document.getElementById('campoProvincia');
    const provincias = Object.keys(estado.catalogo[departamento] || {}).sort((a, b) => a.localeCompare(b, 'es'));
    selectorProvincia.innerHTML = provincias.map((provincia) => `<option value="${escapar(provincia)}">${escapar(provincia)}</option>`).join('');
    actualizarDistritos();
    actualizarParcelasDisponibles(true);
}

function actualizarDistritos() {
    const departamento = document.getElementById('campoDepartamento').value;
    const provincia = document.getElementById('campoProvincia').value;
    const selectorDistrito = document.getElementById('campoDistrito');
    const distritos = estado.catalogo[departamento]?.[provincia] || [];
    selectorDistrito.innerHTML = distritos.map((distrito) => `<option value="${escapar(distrito)}">${escapar(distrito)}</option>`).join('');
    actualizarCoordenadasEstimadas();
    actualizarParcelasDisponibles(true);
}

function actualizarCoordenadasEstimadas() {
    // En modo V16 ya no se autocompleta con centro urbano del distrito.
    // Las coordenadas se llenan desde parcelas/zonas agrícolas registradas en CSV.
    limpiarGeodatosParcela();
}

async function cargarResumen() {
    const respuesta = await fetch('/api/resumen');
    estado.resumen = await respuesta.json();
    estado.evaluaciones = estado.resumen.evaluaciones || [];

    const respuestaMetricas = await fetch('/api/metricas');
    estado.metricas = await respuestaMetricas.json();

    actualizarKpis();
    dibujarGraficoRiesgo();
    dibujarGraficoCultivos();
    renderizarMapa();
    renderizarUltimaAlerta();
    renderizarMetricasIA();
    renderizarTabla();
}

async function cargarDemo() {
    bloquearBoton('btnDemo', true, 'Cargando demo...');
    try {
        const respuesta = await fetch('/api/demo/cargar', { method: 'POST' });
        const datos = await respuesta.json();
        mostrarNotificacion(`${datos.creados.length} evaluaciones demo cargadas correctamente.`);
        await cargarResumen();
        document.getElementById('panel').scrollIntoView({ behavior: 'smooth' });
    } finally {
        bloquearBoton('btnDemo', false, 'Cargar modo demo');
    }
}

async function limpiarDemo() {
    const confirmado = confirm('Se eliminarán solo los registros demo. Los datos reales se conservarán. ¿Continuar?');
    if (!confirmado) return;
    await fetch('/api/demo/limpiar', { method: 'DELETE' });
    mostrarNotificacion('Datos demo eliminados. Los datos reales siguen guardados.');
    await cargarResumen();
}

async function restaurarDemo() {
    if (estado.soloLectura) {
        mostrarNotificacion('Modo lectura activo: no se puede restaurar demo desde esta vista.');
        return;
    }
    const confirmado = confirm('Se restaurará la demo original. Los datos reales se conservan. ¿Continuar?');
    if (!confirmado) return;
    bloquearBoton('btnRestaurarDemo', true, 'Restaurando...');
    try {
        const respuesta = await fetch('/api/demo/restaurar', { method: 'POST' });
        const datos = await respuesta.json();
        mostrarNotificacion(`${datos.creados.length} registros demo restaurados.`);
        await cargarResumen();
    } finally {
        bloquearBoton('btnRestaurarDemo', false, 'Restaurar demo');
    }
}

function alternarModoLectura() {
    const url = new URL(window.location.href);
    if (estado.soloLectura) {
        url.searchParams.delete('lectura');
    } else {
        url.searchParams.set('lectura', '1');
    }
    window.location.href = url.toString();
}

function aplicarModoLectura() {
    // Botón retirado en V17. Se deja la función vacía para compatibilidad interna.
}

async function cargarEstadoServidor() {
    const contenedor = document.getElementById('estadoServidor');
    if (!contenedor) return;
    try {
        const respuesta = await fetch('/api/estado_servidor');
        const datos = await respuesta.json();
        const minutos = Math.floor((datos.uptime_segundos || 0) / 60);
        contenedor.innerHTML = `<strong>Servidor ${escapar(datos.estado)}</strong><br>${escapar(datos.modo)}<br><small>Uptime aprox.: ${minutos} min · ${escapar(datos.version)}</small>`;
    } catch (error) {
        contenedor.textContent = 'Servidor: no se pudo leer estado.';
    }
}

async function cargarExperimentosIA() {
    const contenedor = document.getElementById('experimentosIA');
    if (!contenedor) return;
    try {
        const respuesta = await fetch('/api/experimentos');
        const datos = await respuesta.json();
        const modelos = (datos.modelos || []).map((item) => `${item.modelo}: F1 ${item.f1_score}%`).join(' · ');
        const variables = (datos.importancia_variables || []).slice(0, 4).map((item) => `${item.variable} ${item.peso}%`).join(' · ');
        contenedor.innerHTML = `<strong>Experimentos IA / Comet-ready</strong><br>${escapar(modelos)}<br><small>Variables clave: ${escapar(variables)}</small>`;
    } catch (error) {
        contenedor.textContent = 'Experimentos IA: no se pudo leer.';
    }
}



async function traerClimaAutomatico() {
    const latitud = document.getElementById('campoLatitud').value;
    const longitud = document.getElementById('campoLongitud').value;
    if (!latitud || !longitud) {
        mostrarNotificacion('Primero coloca latitud y longitud. Apachurra provincia/distrito si quieres autocompletar.');
        return;
    }
    bloquearBoton('btnClimaAutomatico', true, 'Consultando clima...');
    try {
        const respuesta = await fetch(`/api/clima?latitud=${encodeURIComponent(latitud)}&longitud=${encodeURIComponent(longitud)}`);
        const datos = await respuesta.json();
        if (!respuesta.ok) throw new Error(datos.detail || 'No se pudo traer clima automático.');
        document.getElementById('campoTemperatura').value = datos.temperatura_minima;
        document.getElementById('campoLluvia').value = datos.lluvia_acumulada;
        document.getElementById('campoHumedad').value = datos.humedad_suelo;
        mostrarNotificacion(`Clima cargado desde ${datos.fuente}: ${datos.temperatura_minima} °C, ${datos.lluvia_acumulada} mm.`);
    } catch (error) {
        mostrarNotificacion(error.message);
    } finally {
        bloquearBoton('btnClimaAutomatico', false, 'Traer clima automático');
    }
}

async function crearEvaluacion(evento) {
    evento.preventDefault();
    if (estado.soloLectura) { mostrarNotificacion('Modo lectura activo: no se registran evaluaciones.'); return; }
    const formulario = evento.currentTarget;
    const datos = new FormData(formulario);
    datos.set('origen', 'real');

    const boton = formulario.querySelector('button[type="submit"]');
    const datosVista = extraerDatosFormulario(datos);
    boton.disabled = true;
    boton.textContent = 'Analizando con IA...';
    mostrarAnimacionAnalisis(datosVista);
    const inicioAnimacion = Date.now();

    try {
        const respuesta = await fetch('/api/evaluaciones', {
            method: 'POST',
            body: datos
        });
        if (!respuesta.ok) {
            const error = await respuesta.json();
            throw new Error(error.detail || 'No se pudo crear la evaluación.');
        }
        const evaluacion = await respuesta.json();
        await esperar(Math.max(1500 - (Date.now() - inicioAnimacion), 0));
        completarAnimacionAnalisis(evaluacion);
        formulario.reset();
        establecerFechaInicial();
        llenarDepartamentos();
        document.getElementById('vistaImagen').innerHTML = '<span>Vista previa</span>';
        await cargarResumen();
    } catch (error) {
        mostrarNotificacion(error.message);
    } finally {
        boton.disabled = false;
        boton.textContent = 'Analizar riesgo con IA';
    }
}

async function importarCsv(evento) {
    evento.preventDefault();
    if (estado.soloLectura) { mostrarNotificacion('Modo lectura activo: importación bloqueada.'); return; }
    const formulario = evento.currentTarget;
    const datos = new FormData(formulario);
    const boton = formulario.querySelector('button');
    boton.disabled = true;
    boton.textContent = 'Importando...';
    try {
        const respuesta = await fetch('/api/importar_csv', { method: 'POST', body: datos });
        const resultado = await respuesta.json();
        mostrarNotificacion(`Importación lista: ${resultado.creados} filas creadas, ${resultado.errores.length} errores.`);
        await cargarResumen();
        formulario.reset();
    } finally {
        boton.disabled = false;
        boton.textContent = 'Importar CSV';
    }
}

function previsualizarImagen(evento) {
    const archivo = evento.target.files[0];
    const contenedor = document.getElementById('vistaImagen');
    if (!archivo) {
        contenedor.innerHTML = '<span>Vista previa</span>';
        return;
    }
    const lector = new FileReader();
    lector.onload = () => {
        contenedor.innerHTML = `<img src="${lector.result}" alt="Vista previa de parcela">`;
    };
    lector.readAsDataURL(archivo);
}



function prepararCanvas(canvasId, altoDeseado = 300) {
    const canvas = document.getElementById(canvasId);
    if (!canvas) return null;
    const ancho = Math.max(220, Math.round(canvas.parentElement?.clientWidth || canvas.clientWidth || canvas.width || 220));
    const alto = Math.max(200, altoDeseado);
    canvas.width = ancho;
    canvas.height = alto;
    canvas.style.width = '100%';
    canvas.style.height = `${alto}px`;
    return canvas.getContext('2d');
}


function configurarSimulador() {
    ['simTemperatura', 'simLluvia', 'simHumedad', 'simEtapa'].forEach((id) => {
        const elemento = document.getElementById(id);
        if (elemento) elemento.addEventListener('input', actualizarSimulador);
    });
    actualizarSimulador();
}

function actualizarSimulador() {
    const temperatura = Number(document.getElementById('simTemperatura')?.value || 0);
    const lluvia = Number(document.getElementById('simLluvia')?.value || 0);
    const humedad = document.getElementById('simHumedad')?.value || 'Baja';
    const etapa = document.getElementById('simEtapa')?.value || 'Floración';

    const puntosFrio = temperatura <= 0 ? 32 : temperatura <= 3 ? 24 : temperatura <= 7 ? 12 : 0;
    const puntosLluvia = lluvia >= 65 ? 30 : lluvia >= 40 ? 18 : lluvia <= 5 ? 14 : 6;
    const puntosHumedad = humedad === 'Alta' ? 20 : humedad === 'Muy baja' ? 18 : humedad === 'Baja' ? 10 : 6;
    const puntosEtapa = ['Emergencia', 'Floración', 'Llenado de grano'].includes(etapa) ? 18 : 8;
    const puntaje = Math.min(100, Math.round(puntosFrio + puntosLluvia + puntosHumedad + puntosEtapa));
    const riesgo = puntaje >= 70 ? 'Alto' : puntaje >= 42 ? 'Medio' : 'Bajo';
    const impacto = estimarImpactoEconomico({ riesgo, puntaje_riesgo: puntaje, area_hectareas: 3.5 });

    document.getElementById('simTemperaturaTexto').textContent = `${temperatura} °C`;
    document.getElementById('simLluviaTexto').textContent = `${lluvia} mm`;
    document.getElementById('simRiesgo').textContent = `Riesgo ${riesgo.toLowerCase()}`;
    document.getElementById('simRiesgo').className = `riesgo-simulado ${riesgo.toLowerCase()}`;
    document.getElementById('simPuntaje').textContent = `${puntaje}/100`;
    document.getElementById('simImpacto').textContent = `S/ ${impacto.ahorroPotencial.toLocaleString('es-PE')}`;
    document.getElementById('simExplicacion').textContent = riesgo === 'Alto'
        ? 'Escenario crítico: conviene priorizar técnico, drenaje/riego o medida preventiva.'
        : riesgo === 'Medio'
            ? 'Escenario de vigilancia: todavía se puede prevenir antes de que escale.'
            : 'Escenario estable: mantener monitoreo y no gastar recursos de más.';
}

function estimarImpactoEconomico(item) {
    const area = Math.max(0.1, Number(item.area_hectareas || 1));
    const puntaje = Math.max(0, Number(item.puntaje_riesgo || 0));
    const factorRiesgo = item.riesgo === 'Alto' ? 0.34 : item.riesgo === 'Medio' ? 0.18 : 0.07;
    const valorReferencialHa = item.cultivo === 'Maíz' ? 3600 : item.cultivo === 'Quinua' ? 4200 : 4800;
    const perdidaEstimada = Math.round(area * valorReferencialHa * factorRiesgo * (0.7 + puntaje / 180));
    const costoPreventivo = Math.round(area * 420);
    const ahorroPotencial = Math.max(0, perdidaEstimada - costoPreventivo);
    return { perdidaEstimada, costoPreventivo, ahorroPotencial };
}

function actualizarKpis() {
    const resumen = estado.resumen || {};
    const metricas = estado.metricas || {};
    document.getElementById('kpiTotal').textContent = resumen.total || 0;
    document.getElementById('kpiAlto').textContent = resumen.riesgo_alto || 0;
    document.getElementById('kpiPorcentaje').textContent = `${resumen.porcentaje_alto || 0}% del total`;
    document.getElementById('kpiArea').textContent = `${resumen.area_total || 0} ha`;
    document.getElementById('kpiAreaAlta').textContent = `${resumen.area_alta || 0} ha`;
    document.getElementById('kpiF1').textContent = metricas.disponible ? `${metricas.f1_score}%` : '--';
    document.getElementById('kpiTiempoIA').textContent = metricas.disponible ? `${metricas.tiempo_promedio_ms} ms` : '-- ms';
}

function dibujarGraficoRiesgo() {
    const canvas = document.getElementById('graficoRiesgo');
    const ctx = prepararCanvas('graficoRiesgo', window.innerWidth <= 430 ? 230 : 300);
    if (!canvas || !ctx) return;
    const datos = estado.resumen?.por_riesgo || {};
    const valores = ['Alto', 'Medio', 'Bajo'].map((nombre) => ({ nombre, valor: datos[nombre] || 0, color: coloresRiesgo[nombre] }));
    const total = valores.reduce((suma, item) => suma + item.valor, 0);
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    estado.segmentosRiesgo = [];

    const centroX = canvas.width / 2;
    const centroY = canvas.height / 2;
    const radio = Math.max(58, Math.min(105, Math.min(canvas.width, canvas.height) / 2 - 34));
    const grosor = Math.max(22, Math.min(42, radio * 0.38));

    if (!total) {
        dibujarTextoCentro(ctx, 'Sin datos', centroX, centroY);
        document.getElementById('leyendaRiesgo').innerHTML = '';
        return;
    }

    let inicio = -Math.PI / 2;
    valores.forEach((item) => {
        const angulo = (item.valor / total) * Math.PI * 2;
        const fin = inicio + angulo;
        ctx.beginPath();
        ctx.arc(centroX, centroY, radio, inicio, fin);
        ctx.lineWidth = grosor;
        ctx.strokeStyle = item.color;
        ctx.lineCap = 'round';
        ctx.stroke();
        estado.segmentosRiesgo.push({ ...item, inicio, fin, total, centroX, centroY, radio });
        inicio = fin;
    });

    ctx.beginPath();
    ctx.arc(centroX, centroY, radio - grosor, 0, Math.PI * 2);
    ctx.fillStyle = 'rgba(0,0,0,0.18)';
    ctx.fill();
    dibujarTextoCentro(ctx, `${total}`, centroX, centroY - 8, 'Evaluaciones');

    document.getElementById('leyendaRiesgo').innerHTML = valores.map((item) => `
        <span class="item-leyenda"><span class="color-leyenda" style="background:${item.color}"></span>${item.nombre}: ${item.valor}</span>
    `).join('');
}

function dibujarGraficoCultivos() {
    const canvas = document.getElementById('graficoCultivos');
    const ctx = prepararCanvas('graficoCultivos', window.innerWidth <= 430 ? 240 : 300);
    if (!canvas || !ctx) return;
    const datos = estado.resumen?.por_cultivo || {};
    const entradas = Object.entries(datos).sort((a, b) => b[1] - a[1]);
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    estado.barrasCultivo = [];

    if (!entradas.length) {
        dibujarTextoCentro(ctx, 'Sin datos', canvas.width / 2, canvas.height / 2);
        return;
    }

    const margen = window.innerWidth <= 430 ? 22 : 48;
    const anchoDisponible = canvas.width - margen * 2;
    const altoDisponible = canvas.height - 70;
    const maximo = Math.max(...entradas.map(([, valor]) => valor));
    const anchoBarra = Math.min(86, anchoDisponible / entradas.length - 18);

    ctx.strokeStyle = 'rgba(255,255,255,0.14)';
    ctx.lineWidth = 1;
    for (let i = 0; i <= 4; i++) {
        const y = 28 + (altoDisponible / 4) * i;
        ctx.beginPath();
        ctx.moveTo(margen, y);
        ctx.lineTo(canvas.width - margen, y);
        ctx.stroke();
    }

    entradas.forEach(([nombre, valor], indice) => {
        const x = margen + indice * (anchoDisponible / entradas.length) + 18;
        const alto = (valor / maximo) * (altoDisponible - 18);
        const y = 28 + altoDisponible - alto;
        const degradado = ctx.createLinearGradient(0, y, 0, y + alto);
        degradado.addColorStop(0, '#f4b23e');
        degradado.addColorStop(1, '#33c481');
        ctx.fillStyle = degradado;
        redondearRectangulo(ctx, x, y, anchoBarra, alto, 14);
        ctx.fill();
        ctx.fillStyle = '#f9fbf4';
        ctx.font = '800 18px system-ui';
        ctx.textAlign = 'center';
        ctx.fillText(valor, x + anchoBarra / 2, y - 10);
        ctx.fillStyle = '#b9c9bd';
        ctx.font = `${window.innerWidth <= 430 ? '600 10px' : '700 12px'} system-ui`;
        ctx.fillText(nombre, x + anchoBarra / 2, canvas.height - 18);
        estado.barrasCultivo.push({ nombre, valor, x, y, ancho: anchoBarra, alto });
    });
}

function renderizarMapa() {
    const contenedor = document.getElementById('mapaPeru');
    const evaluaciones = estado.evaluaciones || [];
    const entradas = agruparEvaluacionesGeograficas(evaluaciones);

    if (!window.L) {
        renderizarMapaFallback(contenedor, entradas);
        return;
    }

    if (!estado.mapaLeaflet) {
        contenedor.innerHTML = `
            <div class="mapa-leaflet" id="mapaLeaflet"></div>
            <div class="leyenda-mapa">
                <span><i class="alto"></i> Alto</span>
                <span><i class="medio"></i> Medio</span>
                <span><i class="bajo"></i> Bajo</span>
                <small>Mapa real con OpenStreetMap. Los puntos se colocan por latitud y longitud.</small>
            </div>
        `;

        const limites = L.latLngBounds(
            L.latLng(-18.70, -81.65),
            L.latLng(0.30, -68.00)
        );

        estado.mapaLeaflet = L.map('mapaLeaflet', {
            zoomControl: true,
            scrollWheelZoom: false,
            maxBounds: limites.pad(0.40),
            maxBoundsViscosity: 0.75
        }).setView([-9.19, -75.02], 5);

        estado.capaBaseNormal = L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
            maxZoom: 18,
            attribution: '&copy; OpenStreetMap contributors'
        }).addTo(estado.mapaLeaflet);

        estado.capaBaseSatelital = L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', {
            maxZoom: 18,
            attribution: 'Tiles &copy; Esri, Maxar, Earthstar Geographics'
        });

        estado.capaMarcadores = L.layerGroup().addTo(estado.mapaLeaflet);
    }

    estado.capaMarcadores.clearLayers();

    if (!entradas.length) {
        estado.mapaLeaflet.setView([-9.19, -75.02], 5);
        setTimeout(() => estado.mapaLeaflet.invalidateSize(), 150);
        return;
    }

    const limitesMarcadores = [];

    entradas.forEach((dato) => {
        const color = dato.alto > 0 ? coloresRiesgo.Alto : dato.medio > 0 ? coloresRiesgo.Medio : coloresRiesgo.Bajo;
        const textoRiesgo = dato.alto > 0 ? `${dato.alto} alto` : dato.medio > 0 ? `${dato.medio} medio` : `${dato.bajo} bajo`;
        const posicion = [Number(dato.latitud), Number(dato.longitud)];
        limitesMarcadores.push(posicion);

        const marcador = L.circleMarker(posicion, {
            radius: dato.alto > 0 ? 9 : 7,
            color: '#ffffff',
            weight: 2,
            fillColor: color,
            fillOpacity: 0.92
        });

        marcador.bindPopup(`
            <strong>${escapar(dato.distrito)}</strong><br>
            ${escapar(dato.provincia)}, ${escapar(dato.departamento)}<br>
            <b>${dato.total}</b> evaluaciones · ${textoRiesgo}<br>
            Lat ${Number(dato.latitud).toFixed(5)} · Lon ${Number(dato.longitud).toFixed(5)}<br>
            Altitud: ${Math.round(Number(dato.altitud_msnm || 0))} msnm
        `);

        marcador.bindTooltip(escapar(dato.distrito), {
            permanent: false,
            direction: 'top',
            className: 'tooltip-mapa-peru'
        });

        marcador.addTo(estado.capaMarcadores);
    });

    if (limitesMarcadores.length === 1) {
        estado.mapaLeaflet.setView(limitesMarcadores[0], 7);
    } else {
        estado.mapaLeaflet.fitBounds(limitesMarcadores, { padding: [36, 36], maxZoom: 7 });
    }

    setTimeout(() => estado.mapaLeaflet.invalidateSize(), 150);
}

function cambiarCapaMapa(tipo) {
    if (!estado.mapaLeaflet || !estado.capaBaseNormal || !estado.capaBaseSatelital) {
        mostrarNotificacion('El mapa todavía está cargando.');
        return;
    }
    if (tipo === 'satelital') {
        if (estado.mapaLeaflet.hasLayer(estado.capaBaseNormal)) estado.mapaLeaflet.removeLayer(estado.capaBaseNormal);
        if (!estado.mapaLeaflet.hasLayer(estado.capaBaseSatelital)) estado.capaBaseSatelital.addTo(estado.mapaLeaflet);
        mostrarNotificacion('Mapa satelital activado.');
    } else {
        if (estado.mapaLeaflet.hasLayer(estado.capaBaseSatelital)) estado.mapaLeaflet.removeLayer(estado.capaBaseSatelital);
        if (!estado.mapaLeaflet.hasLayer(estado.capaBaseNormal)) estado.capaBaseNormal.addTo(estado.mapaLeaflet);
        mostrarNotificacion('Mapa normal activado.');
    }
    setTimeout(() => estado.mapaLeaflet.invalidateSize(), 120);
}

function agruparEvaluacionesGeograficas(evaluaciones) {
    const agrupadas = new Map();

    evaluaciones.forEach((item) => {
        const coordenadas = obtenerCoordenadasEvaluacion(item);
        if (!coordenadas) return;
        const clave = `${item.departamento || ''}|${item.provincia || ''}|${item.distrito || ''}`;
        const actual = agrupadas.get(clave) || {
            total: 0,
            alto: 0,
            medio: 0,
            bajo: 0,
            departamento: item.departamento || '',
            provincia: item.provincia || '',
            distrito: item.distrito || '',
            latitud: coordenadas.latitud,
            longitud: coordenadas.longitud,
            altitud_msnm: coordenadas.altitud_msnm
        };
        actual.total += 1;
        if (item.riesgo === 'Alto') actual.alto += 1;
        if (item.riesgo === 'Medio') actual.medio += 1;
        if (item.riesgo === 'Bajo') actual.bajo += 1;
        agrupadas.set(clave, actual);
    });

    return Array.from(agrupadas.values())
        .filter((dato) => Number.isFinite(Number(dato.latitud)) && Number.isFinite(Number(dato.longitud)))
        .sort((a, b) => b.total - a.total)
        .slice(0, 40);
}

function renderizarMapaFallback(contenedor, entradas) {
    const marcadores = entradas.map((dato) => {
        const punto = proyectarPeru(dato.latitud, dato.longitud);
        const clase = dato.alto > 0 ? 'alto' : dato.medio > 0 ? 'medio' : 'bajo';
        return `
            <button class="marcador-mapa ${clase}" style="left:${punto.x}%; top:${punto.y}%" type="button" aria-label="${escapar(dato.distrito)}">
                <span class="pulso-marcador"></span>
                <span class="punta-marcador"></span>
                <strong>${escapar(dato.distrito)}</strong>
                <small>${escapar(dato.provincia)}, ${escapar(dato.departamento)}</small>
                <em>Lat ${Number(dato.latitud).toFixed(4)} · Lon ${Number(dato.longitud).toFixed(4)}</em>
            </button>
        `;
    }).join('');

    const lineasInternas = lineasInternasPeru.map((ruta) => `<path d="${ruta}" class="peru-interno" />`).join('');
    contenedor.innerHTML = `
        <div class="mapa-peru-cuadrado mapa-real-cuadrado">
            <svg class="svg-peru" viewBox="0 0 100 100" role="img" aria-label="Mapa local del Perú con alertas">
                <defs>
                    <linearGradient id="gradienteMar" x1="0" x2="1" y1="0" y2="1">
                        <stop offset="0%" stop-color="#0c3140" />
                        <stop offset="100%" stop-color="#0c2231" />
                    </linearGradient>
                    <linearGradient id="gradienteTierra" x1="0" x2="1" y1="0" y2="1">
                        <stop offset="0%" stop-color="#2fb573" />
                        <stop offset="58%" stop-color="#1d7a56" />
                        <stop offset="100%" stop-color="#b48a34" />
                    </linearGradient>
                    <clipPath id="recortePeru"><path d="${rutaPeruSvg}" /></clipPath>
                </defs>
                <rect x="0" y="0" width="100" height="100" class="mar-fondo" />
                <path d="${rutaPeruSvg}" class="peru-silueta" />
                <path d="${rutaPeruSvg}" class="peru-borde" />
                <g clip-path="url(#recortePeru)">${lineasInternas}</g>
                <text x="56" y="18" class="texto-peru">PERÚ</text>
            </svg>
            <div class="capa-marcadores">${marcadores}</div>
            ${!entradas.length ? '<div class="estado-vacio mapa-vacio">Sin coordenadas registradas. Carga el modo demo o llena latitud y longitud.</div>' : ''}
        </div>
        <div class="leyenda-mapa">
            <span><i class="alto"></i> Alto</span>
            <span><i class="medio"></i> Medio</span>
            <span><i class="bajo"></i> Bajo</span>
            <small>Vista local de respaldo. Para el mapa real usa conexión a internet.</small>
        </div>
    `;
}

function obtenerCoordenadasEvaluacion(item) {
    const latitud = Number(item.latitud);
    const longitud = Number(item.longitud);
    if (Number.isFinite(latitud) && Number.isFinite(longitud)) {
        return {
            latitud,
            longitud,
            altitud_msnm: Number(item.altitud_msnm || 0)
        };
    }
    return obtenerReferenciaCoordenadas(item.departamento, item.provincia, item.distrito);
}

function obtenerReferenciaCoordenadas(departamento, provincia, distrito) {
    const porDepartamento = estado.coordenadas?.[departamento] || {};
    const porProvincia = porDepartamento?.[provincia] || {};
    return porProvincia?.[distrito] || porProvincia?._centro || null;
}

function proyectarPeru(latitud, longitud) {
    const x = ((Number(longitud) - limitesPeru.lonMin) / (limitesPeru.lonMax - limitesPeru.lonMin)) * 100;
    const y = ((limitesPeru.latMax - Number(latitud)) / (limitesPeru.latMax - limitesPeru.latMin)) * 100;
    return {
        x: Math.max(2.5, Math.min(97.5, x)),
        y: Math.max(2.5, Math.min(97.5, y))
    };
}

function renderizarUltimaAlerta() {
    const contenedor = document.getElementById('ultimaAlerta');
    const ultima = estado.evaluaciones[0];
    if (!ultima) {
        contenedor.className = 'estado-vacio';
        contenedor.textContent = 'Aún no hay evaluaciones. Carga el modo demo o registra datos reales.';
        return;
    }
    contenedor.className = 'alerta-ia';
    contenedor.innerHTML = construirTarjetaResultado(ultima, false);
}

function renderizarMetricasIA() {
    const metricas = estado.metricas || {};
    const ids = {
        metAccuracy: 'accuracy',
        metPrecision: 'precision',
        metRecall: 'recall',
        metF1: 'f1_score',
        metError: 'tasa_error',
        metVarError: 'variabilidad_error'
    };

    Object.entries(ids).forEach(([id, clave]) => {
        const elemento = document.getElementById(id);
        if (!elemento) return;
        if (!metricas.disponible) {
            elemento.textContent = '--';
            return;
        }
        elemento.textContent = clave === 'variabilidad_error' ? metricas[clave] : `${metricas[clave]}%`;
    });

    const contenedor = document.getElementById('matrizConfusion');
    const nota = document.getElementById('notaMetricas');
    if (!metricas.disponible) {
        contenedor.innerHTML = '<div class="estado-vacio">Valida registros desde Historial para calcular la matriz.</div>';
        nota.textContent = metricas.mensaje || 'Sin métricas disponibles.';
        return;
    }

    const clases = metricas.clases || ['Alto', 'Medio', 'Bajo'];
    const matriz = metricas.matriz || [];
    const encabezado = clases.map((clase) => `<th>Pred. ${clase}</th>`).join('');
    const filas = matriz.map((fila, indice) => `
        <tr>
            <th>Real ${clases[indice]}</th>
            ${fila.map((valor, columna) => `<td class="${indice === columna ? 'acierto' : 'error'}">${valor}</td>`).join('')}
        </tr>
    `).join('');
    contenedor.innerHTML = `
        <table class="tabla-matriz">
            <thead><tr><th></th>${encabezado}</tr></thead>
            <tbody>${filas}</tbody>
        </table>
        <div class="resumen-validacion">Registros validados: ${metricas.total_validacion} · Error medio ordinal: ${metricas.error_medio_ordinal}</div>
    `;
    nota.textContent = metricas.nota || '';
}

function renderizarTabla() {
    const cuerpo = document.getElementById('tablaEvaluaciones');
    const texto = document.getElementById('buscarTexto').value.toLowerCase().trim();
    const riesgo = document.getElementById('filtroRiesgo').value;
    const origen = document.getElementById('filtroOrigen').value;

    const filtradas = estado.evaluaciones.filter((item) => {
        const coincideTexto = !texto || `${item.productor} ${item.cultivo} ${item.distrito} ${item.provincia} ${item.departamento}`.toLowerCase().includes(texto);
        const coincideRiesgo = !riesgo || item.riesgo === riesgo;
        const coincideOrigen = !origen || item.origen === origen;
        return coincideTexto && coincideRiesgo && coincideOrigen;
    });

    if (!filtradas.length) {
        cuerpo.innerHTML = '<tr><td colspan="10">No hay registros para mostrar.</td></tr>';
        return;
    }

    cuerpo.innerHTML = filtradas.map((item) => `
        <tr>
            <td>#${item.id}</td>
            <td><strong>${escapar(item.productor)}</strong><br><small>${formatearFecha(item.creado_en)}</small></td>
            <td>${escapar(item.cultivo)}<br><small>${escapar(item.etapa)}</small></td>
            <td>${escapar(item.distrito)}<br><small>${escapar(item.provincia)}, ${escapar(item.departamento || '')}</small><br><small>${formatearGeodatos(item)}</small></td>
            <td>${item.temperatura_minima} °C<br><small>${item.humedad_suelo} / ${item.lluvia_acumulada} mm</small></td>
            <td><span class="insignia-riesgo riesgo-${String(item.riesgo).toLowerCase()}">${item.riesgo} ${item.probabilidad}%</span><br><small>${item.puntaje_riesgo || 0}/100 pts</small></td>
            <td>${item.riesgo_real ? `<span class="insignia-real">${item.riesgo_real}</span><br><small>${escapar(item.responsable_validacion || 'Validado')}</small>` : '<small>Sin validar</small>'}</td>
            <td><span class="insignia-aptitud">${escapar(item.aptitud_cultivo || 'Sin ref.')}</span><br><small>${item.impacto_ubicacion || 0} pts</small></td>
            <td><span class="pastilla ${item.origen}">${item.origen}</span></td>
            <td>
                <button class="boton mini" onclick='verDetalle(${item.id})'>Ver</button>
                <button class="boton mini" onclick='reproducirAnalisis(${item.id})'>Árbol IA</button>
                <button class="boton mini" onclick='abrirReporte(${item.id})'>Reporte</button>
                ${item.riesgo === 'Alto' ? `<button class="boton mini" onclick='enviarAlertaGmail(${item.id})'>Gmail</button>` : ''}
                ${estado.soloLectura ? '' : `<button class="boton mini" onclick='abrirValidacion(${item.id})'>Validar</button><button class="boton mini" onclick='eliminarEvaluacion(${item.id})'>Eliminar</button>`}
            </td>
        </tr>
    `).join('');
}


function extraerDatosFormulario(datos) {
    const objeto = {};
    for (const [clave, valor] of datos.entries()) {
        if (valor instanceof File) {
            objeto[clave] = valor.name || '';
        } else {
            objeto[clave] = valor;
        }
    }
    return objeto;
}

function esperar(ms) {
    return new Promise((resolver) => setTimeout(resolver, ms));
}

function mostrarAnimacionAnalisis(datos) {
    const ubicacion = [datos.distrito, datos.provincia, datos.departamento].filter(Boolean).join(', ');
    document.getElementById('contenidoModal').innerHTML = `
        <span class="subtitulo">Árbol IA en tiempo real</span>
        <h2>Construyendo ramas de evaluación...</h2>
        <p class="nota-metrica">AgroIA está armando un árbol visual con territorio, clima, etapa del cultivo, Random Forest y reglas críticas.</p>
        <div class="analisis-ia arbol-cargando">
            <div class="analisis-datos">
                <div><span>Cultivo</span><strong>${escapar(datos.cultivo || '-')}</strong></div>
                <div><span>Ubicación</span><strong>${escapar(ubicacion || '-')}</strong></div>
                <div><span>Temperatura</span><strong>${escapar(datos.temperatura_minima || '-')} °C</strong></div>
                <div><span>Humedad</span><strong>${escapar(datos.humedad_suelo || '-')}</strong></div>
                <div><span>Lluvia</span><strong>${escapar(datos.lluvia_acumulada || '-')} mm</strong></div>
                <div><span>Etapa</span><strong>${escapar(datos.etapa || '-')}</strong></div>
            </div>
            <div class="arbol-decision arbol-provisional">
                <div class="nodo-arbol estado-neutro" style="--orden:1; --retardo:0ms">
                    <span>Entrada recibida</span>
                    <strong>${escapar(datos.cultivo || 'Cultivo')} · ${escapar(ubicacion || 'Ubicación')}</strong>
                    <small>Preparando ramas de análisis...</small>
                </div>
                <div class="ramas-arbol">
                    <div class="nodo-arbol estado-neutro" style="--orden:2; --retardo:1000ms"><span>Territorio</span><strong>Evaluando provincia</strong><small>Aptitud cultivo-zona</small></div>
                    <div class="nodo-arbol estado-neutro" style="--orden:3; --retardo:2000ms"><span>Clima</span><strong>Evaluando umbrales</strong><small>Temperatura, humedad y lluvia</small></div>
                    <div class="nodo-arbol estado-neutro" style="--orden:4; --retardo:3000ms"><span>Modelo</span><strong>Random Forest</strong><small>Votos de árboles internos</small></div>
                    <div class="nodo-arbol estado-neutro" style="--orden:5; --retardo:4000ms"><span>Reglas</span><strong>Buscando bloqueos</strong><small>Helada, sequía o exceso de lluvia</small></div>
                </div>
            </div>
            <p class="estado-analisis">Desplegando ramas como mapa mental de decisión...</p>
        </div>
    `;
    document.getElementById('modalResultado').classList.add('abierto', 'modal-arbol-abierto');
}

function completarAnimacionAnalisis(evaluacion) {
    const factores = Array.isArray(evaluacion.factores) ? evaluacion.factores : [];
    const recomendaciones = Array.isArray(evaluacion.recomendaciones) ? evaluacion.recomendaciones : [];
    const zonas = Array.isArray(evaluacion.zonas_recomendadas) ? evaluacion.zonas_recomendadas : [];
    const arbol = evaluacion.arbol_decision && evaluacion.arbol_decision.raiz ? evaluacion.arbol_decision : construirArbolDesdeEvaluacion(evaluacion);
    const votos = construirVotosVisuales(evaluacion);
    const totalNodosArbol = contarNodosArbol(arbol.raiz);
    const retardoFinal = Math.min((totalNodosArbol + 1) * 1000, 24000);
    document.getElementById('contenidoModal').innerHTML = `
        <span class="subtitulo">Árbol visual de decisión</span>
        <h2>Así se ramificó la evaluación IA</h2>
        <p class="nota-metrica">Esta vista representa el razonamiento operativo del sistema: no muestra cada árbol interno real del Random Forest, sino una explicación visual de las decisiones usadas por AgroIA.</p>
        <div class="resultado-animado">
            <div class="decision-final decision-final-animada riesgo-${String(evaluacion.riesgo).toLowerCase()}" style="--retardo-final:${retardoFinal}ms">
                <span>Decisión final</span>
                <strong>Riesgo ${escapar(evaluacion.riesgo)}</strong>
                <small>Confianza ${evaluacion.probabilidad}% · Puntaje ${evaluacion.puntaje_riesgo}/100</small>
            </div>
            <div class="arbol-layout arbol-layout-compacto">
                ${construirArbolCompacto(arbol.raiz)}
            </div>
            <div class="panel-random-forest">
                <h3>Votos simulados del bosque</h3>
                <p>Sirve para explicar visualmente cómo un Random Forest compara clases antes de combinarse con reglas críticas.</p>
                <div class="votos-bosque">
                    ${votos.map((voto) => `<div><small>${voto.nombre}</small><span><i style="width:${voto.valor}%"></i></span><b>${voto.valor}%</b></div>`).join('')}
                </div>
            </div>
            ${construirBloqueZonas(zonas, evaluacion.cultivo, evaluacion.aptitud_cultivo)}
            <div class="factores-detectados">
                <h3>Factores detectados</h3>
                <div>
                    ${factores.map((factor) => `<span>${escapar(factor)}</span>`).join('') || '<span>Condiciones dentro de rangos manejables.</span>'}
                </div>
            </div>
            <div class="mini-recomendaciones">
                <h3>Recomendaciones generadas</h3>
                <ul>${recomendaciones.slice(0, 5).map((item) => `<li>${escapar(item)}</li>`).join('')}</ul>
            </div>
            <div class="acciones-formulario">
                <button class="boton primario" type="button" onclick="mostrarResultadoPorId(${Number(evaluacion.id) || 0})">Ver resultado completo</button>
                <button class="boton secundario" type="button" onclick="cerrarModal()">Cerrar</button>
            </div>
        </div>
    `;
    document.getElementById('modalResultado').classList.add('abierto', 'modal-arbol-abierto');
}

function contarNodosArbol(nodo) {
    if (!nodo) return 0;
    const hijos = Array.isArray(nodo.hijos) ? nodo.hijos : [];
    return 1 + hijos.reduce((total, hijo) => total + contarNodosArbol(hijo), 0);
}

function construirArbolCompacto(raiz) {
    const contador = { valor: 0 };
    const hijos = Array.isArray(raiz.hijos) ? raiz.hijos : [];
    contador.valor += 1;
    const raizHtml = construirNodoCompacto(raiz, contador.valor, 'nodo-raiz-compacto');
    const ramasHtml = hijos.map((hijo) => construirRamaCompacta(hijo, contador)).join('');
    return `
        <div class="mapa-arbol-compacto">
            <div class="raiz-mapa">
                ${raizHtml}
            </div>
            <div class="tronco-mapa" style="--retardo:900ms"></div>
            <div class="ramas-compactas">
                ${ramasHtml}
            </div>
        </div>
    `;
}

function construirRamaCompacta(nodo, contador) {
    contador.valor += 1;
    const ordenRama = contador.valor;
    const hijos = Array.isArray(nodo.hijos) ? nodo.hijos : [];
    const hijosHtml = hijos.map((hijo) => {
        contador.valor += 1;
        return construirSubnodoCompacto(hijo, contador.valor);
    }).join('');
    const claseEstado = obtenerClaseEstado(nodo.estado);
    return `
        <article class="rama-compacta ${claseEstado}" style="--orden:${ordenRama}; --retardo:${(ordenRama - 1) * 1000}ms">
            <div class="conector-rama"></div>
            <span>${escapar(nodo.titulo || 'Decisión')}</span>
            <strong>${escapar(nodo.valor || '-')}</strong>
            <small>${escapar(nodo.detalle || '')}</small>
            ${hijosHtml ? `<div class="subramas-compactas">${hijosHtml}</div>` : ''}
        </article>
    `;
}

function construirNodoCompacto(nodo, orden, claseExtra = '') {
    const claseEstado = obtenerClaseEstado(nodo.estado);
    return `
        <div class="nodo-compacto ${claseEstado} ${claseExtra}" style="--orden:${orden}; --retardo:${(orden - 1) * 1000}ms">
            <span>${escapar(nodo.titulo || 'Decisión')}</span>
            <strong>${escapar(nodo.valor || '-')}</strong>
            <small>${escapar(nodo.detalle || '')}</small>
        </div>
    `;
}

function construirSubnodoCompacto(nodo, orden) {
    const claseEstado = obtenerClaseEstado(nodo.estado);
    return `
        <div class="subnodo-compacto ${claseEstado}" style="--orden:${orden}; --retardo:${(orden - 1) * 1000}ms">
            <span>${escapar(nodo.titulo || 'Revisión')}</span>
            <strong>${escapar(nodo.valor || '-')}</strong>
            <small>${escapar(nodo.detalle || '')}</small>
        </div>
    `;
}

function construirArbolVisual(nodo, nivel = 0, contador = { valor: 0 }) {
    contador.valor += 1;
    const hijos = Array.isArray(nodo.hijos) ? nodo.hijos : [];
    const claseEstado = obtenerClaseEstado(nodo.estado);
    return `
        <div class="arbol-nivel nivel-${nivel}">
            <div class="nodo-arbol ${claseEstado}" style="--orden:${contador.valor}; --retardo:${(contador.valor - 1) * 1000}ms">
                <span>${escapar(nodo.titulo || 'Decisión')}</span>
                <strong>${escapar(nodo.valor || '-')}</strong>
                <small>${escapar(nodo.detalle || '')}</small>
            </div>
            ${hijos.length ? `<div class="ramas-arbol">${hijos.map((hijo) => construirArbolVisual(hijo, nivel + 1, contador)).join('')}</div>` : ''}
        </div>
    `;
}

function obtenerClaseEstado(estado) {
    const limpio = String(estado || 'neutro').normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase();
    if (limpio.includes('critico')) return 'estado-critico';
    if (limpio.includes('alerta')) return 'estado-alerta';
    if (limpio.includes('bueno')) return 'estado-bueno';
    return 'estado-neutro';
}

function construirBloqueZonas(zonas, cultivo, aptitud) {
    if (!Array.isArray(zonas) || zonas.length === 0) {
        return '';
    }
    return `
        <div class="zonas-recomendadas">
            <h3>Mejores zonas sugeridas para ${escapar(cultivo || 'el cultivo')}</h3>
            <p>Como la aptitud actual es <b>${escapar(aptitud || 'no ideal')}</b>, el sistema sugiere revisar provincias con mayor compatibilidad territorial.</p>
            <div class="rejilla-zonas">
                ${zonas.map((zona) => `
                    <article>
                        <span>${escapar(zona.aptitud || 'Buena')}</span>
                        <strong>${escapar(zona.provincia || '-')}</strong>
                        <small>${escapar(zona.departamento || '')}</small>
                        <p>${escapar(zona.descripcion || '')}</p>
                    </article>
                `).join('')}
            </div>
        </div>
    `;
}

function construirArbolDesdeEvaluacion(evaluacion) {
    return {
        raiz: {
            titulo: 'Parcela evaluada',
            valor: `${evaluacion.cultivo || 'Cultivo'} · ${evaluacion.distrito || ''}, ${evaluacion.provincia || ''}`,
            estado: 'neutro',
            detalle: 'Reconstrucción visual generada desde el historial.',
            hijos: [
                { titulo: 'Aptitud territorial', valor: evaluacion.aptitud_cultivo || 'Sin referencia', estado: Number(evaluacion.impacto_ubicacion || 0) >= 20 ? 'crítico' : 'bueno', detalle: evaluacion.detalle_aptitud || '', hijos: [] },
                { titulo: 'Temperatura mínima', valor: `${evaluacion.temperatura_minima || 0} °C`, estado: Number(evaluacion.temperatura_minima || 0) <= 2 ? 'crítico' : 'bueno', detalle: 'Umbral climático usado por las reglas.', hijos: [] },
                { titulo: 'Humedad del suelo', valor: evaluacion.humedad_suelo || '-', estado: ['Muy baja', 'Baja'].includes(evaluacion.humedad_suelo) ? 'alerta' : 'bueno', detalle: 'Condición hídrica registrada.', hijos: [] },
                { titulo: 'Random Forest', valor: `Voto base: ${evaluacion.riesgo_modelo || evaluacion.riesgo}`, estado: evaluacion.riesgo_modelo === 'Alto' ? 'crítico' : evaluacion.riesgo_modelo === 'Medio' ? 'alerta' : 'bueno', detalle: 'Clase estimada por el modelo supervisado.', hijos: [] },
                { titulo: 'Decisión final', valor: `Riesgo ${evaluacion.riesgo}`, estado: evaluacion.riesgo === 'Alto' ? 'crítico' : evaluacion.riesgo === 'Medio' ? 'alerta' : 'bueno', detalle: `Puntaje ${evaluacion.puntaje_riesgo || 0}/100`, hijos: [] },
            ],
        },
    };
}

function construirVotosVisuales(evaluacion) {
    const dominante = evaluacion.riesgo_modelo || evaluacion.riesgo;
    const confianza = Math.max(52, Math.min(96, Number(evaluacion.probabilidad || 70)));
    const restante = 100 - confianza;
    const valores = { Alto: 0, Medio: 0, Bajo: 0 };
    valores[dominante] = Math.round(confianza);
    const otros = Object.keys(valores).filter((riesgo) => riesgo !== dominante);
    valores[otros[0]] = Math.round(restante * 0.58);
    valores[otros[1]] = Math.max(0, 100 - valores[dominante] - valores[otros[0]]);
    return ['Alto', 'Medio', 'Bajo'].map((nombre) => ({ nombre, valor: valores[nombre] }));
}

function reproducirAnalisis(id) {
    const evaluacion = estado.evaluaciones.find((item) => item.id === id);
    if (!evaluacion) {
        mostrarNotificacion('Primero actualiza el panel para encontrar la evaluación.');
        return;
    }
    mostrarAnimacionAnalisis(evaluacion);
    setTimeout(() => completarAnimacionAnalisis(evaluacion), 700);
}

function mostrarResultadoPorId(id) {
    const evaluacion = estado.evaluaciones.find((item) => item.id === id);
    if (evaluacion) {
        mostrarResultado(evaluacion);
    } else {
        cerrarModal();
    }
}

function mostrarResultado(evaluacion) {
    document.getElementById('modalResultado').classList.remove('modal-arbol-abierto');
    document.getElementById('contenidoModal').innerHTML = construirTarjetaResultado(evaluacion, true);
    document.getElementById('modalResultado').classList.add('abierto');
}

function construirBloqueImpactoEconomico(item) {
    const impacto = estimarImpactoEconomico(item);
    return `
        <div class="impacto-economico">
            <article><span>Pérdida estimada sin acción</span><strong>S/ ${impacto.perdidaEstimada.toLocaleString('es-PE')}</strong></article>
            <article><span>Costo preventivo aprox.</span><strong>S/ ${impacto.costoPreventivo.toLocaleString('es-PE')}</strong></article>
            <article><span>Ahorro potencial</span><strong>S/ ${impacto.ahorroPotencial.toLocaleString('es-PE')}</strong></article>
        </div>
    `;
}

function construirTarjetaResultado(item, mostrarTitulo) {
    const recomendaciones = Array.isArray(item.recomendaciones) ? item.recomendaciones : [];
    const zonas = Array.isArray(item.zonas_recomendadas) ? item.zonas_recomendadas : [];
    return `
        ${mostrarTitulo ? '<span class="subtitulo">Resultado IA</span><h2>Evaluación registrada correctamente</h2>' : ''}
        <div class="insignia-riesgo riesgo-${String(item.riesgo).toLowerCase()}">Riesgo ${item.riesgo} · Confianza ${item.probabilidad}%</div>
        <p><strong>${escapar(item.cultivo)}</strong> en ${escapar(item.distrito)}, ${escapar(item.provincia)}, ${escapar(item.departamento || '')}.</p>
        <p>${escapar(item.causa)}</p>
        <div class="detalle-ia">
            <span>Método: ${escapar(item.metodo_ia || 'Híbrido')}</span>
            <span>Random Forest: ${escapar(item.riesgo_modelo || 'sin detalle')}</span>
            <span>Reglas críticas: ${escapar(item.riesgo_reglas || 'sin detalle')}</span>
            <span>Bloqueo crítico: ${Number(item.bloqueo_critico || 0) ? 'Sí' : 'No'}</span>
            <span>Puntaje: ${item.puntaje_riesgo || 0}/100</span>
            <span>Aptitud: ${escapar(item.aptitud_cultivo || 'Sin referencia')}</span>
            <span>Impacto ubicación: ${item.impacto_ubicacion || 0} pts</span>
            <span>Geodatos: ${formatearGeodatos(item)}</span>
            <span>Tiempo: ${item.tiempo_ms || 0} ms</span>
            ${item.riesgo_real ? `<span>Validación técnica: riesgo real ${item.riesgo_real}</span>` : '<span>Validación técnica: pendiente</span>'}
        </div>
        ${construirBloqueImpactoEconomico(item)}
        ${item.detalle_aptitud ? `<p><strong>Lectura territorial:</strong> ${escapar(item.detalle_aptitud)}</p>` : ''}
        ${construirBloqueZonas(zonas, item.cultivo, item.aptitud_cultivo)}
        ${item.imagen_url ? `<img src="${item.imagen_url}" alt="Imagen de evaluación" style="width:100%;max-height:260px;object-fit:cover;border-radius:22px;margin:8px 0 14px;">` : ''}
        <ul class="lista-recomendaciones">
            ${recomendaciones.map((recomendacion) => `<li>${escapar(recomendacion)}</li>`).join('')}
        </ul>
        <div class="acciones-formulario">
            <button class="boton secundario" type="button" onclick="reproducirAnalisis(${Number(item.id) || 0})">Reproducir árbol IA</button>
            <button class="boton fantasma" type="button" onclick="abrirReporte(${Number(item.id) || 0})">Reporte técnico</button>
            ${item.riesgo === 'Alto' ? `<button class="boton primario" type="button" onclick="enviarAlertaGmail(${Number(item.id) || 0})">Enviar Gmail</button>` : ''}
        </div>
    `;
}

function cerrarModal() {
    document.getElementById('modalResultado').classList.remove('abierto', 'modal-arbol-abierto');
}

function verDetalle(id) {
    const evaluacion = estado.evaluaciones.find((item) => item.id === id);
    if (evaluacion) mostrarResultado(evaluacion);
}

function abrirValidacion(id) {
    if (estado.soloLectura) { mostrarNotificacion('Modo lectura activo: validación bloqueada.'); return; }
    document.getElementById('modalResultado').classList.remove('modal-arbol-abierto');
    const evaluacion = estado.evaluaciones.find((item) => item.id === id);
    if (!evaluacion) return;
    const fecha = new Date().toISOString().slice(0, 10);
    document.getElementById('contenidoModal').innerHTML = `
        <span class="subtitulo">Validación técnica post-cultivo</span>
        <h2>Validar evaluación #${evaluacion.id}</h2>
        <p><strong>${escapar(evaluacion.cultivo)}</strong> en ${escapar(evaluacion.distrito)}, ${escapar(evaluacion.provincia)}. La IA predijo <strong>${escapar(evaluacion.riesgo)}</strong>.</p>
        <form id="formValidacion" class="formulario validacion-formulario">
            <div class="campo">
                <label>Riesgo real observado</label>
                <select name="riesgo_real" required>
                    <option ${evaluacion.riesgo_real === 'Alto' ? 'selected' : ''}>Alto</option>
                    <option ${evaluacion.riesgo_real === 'Medio' ? 'selected' : ''}>Medio</option>
                    <option ${evaluacion.riesgo_real === 'Bajo' ? 'selected' : ''}>Bajo</option>
                </select>
            </div>
            <div class="campo">
                <label>Responsable</label>
                <input name="responsable_validacion" placeholder="Ej. Técnico agrícola" value="${escapar(evaluacion.responsable_validacion || '')}">
            </div>
            <div class="campo">
                <label>Fecha de validación</label>
                <input type="date" name="fecha_validacion" value="${escapar(evaluacion.fecha_validacion || fecha)}">
            </div>
            <div class="campo ancho-total">
                <label>Observación técnica</label>
                <textarea name="observacion_validacion" rows="3" placeholder="Ej. Se verificó daño por helada en hojas y baja humedad del suelo.">${escapar(evaluacion.observacion_validacion || '')}</textarea>
            </div>
            <div class="acciones-formulario ancho-total">
                <button class="boton primario" type="submit">Guardar validación</button>
                <button class="boton secundario" type="button" onclick="cerrarModal()">Cancelar</button>
            </div>
        </form>
        <p class="nota-metrica">Con esta validación se actualizan automáticamente la matriz de confusión, Accuracy, precisión, recall, F1-Score, tasa de error y variabilidad del error.</p>
    `;
    document.getElementById('modalResultado').classList.add('abierto');
    document.getElementById('formValidacion').addEventListener('submit', (evento) => guardarValidacion(evento, id));
}

async function guardarValidacion(evento, id) {
    evento.preventDefault();
    const datos = new FormData(evento.currentTarget);
    const cuerpo = Object.fromEntries(datos.entries());
    const respuesta = await fetch(`/api/evaluaciones/${id}/validacion`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(cuerpo)
    });
    if (!respuesta.ok) {
        const error = await respuesta.json();
        mostrarNotificacion(error.detail || 'No se pudo guardar la validación.');
        return;
    }
    mostrarNotificacion('Validación técnica guardada. Métricas actualizadas.');
    cerrarModal();
    await cargarResumen();
}

async function eliminarEvaluacion(id) {
    if (estado.soloLectura) { mostrarNotificacion('Modo lectura activo: eliminación bloqueada.'); return; }
    const confirmado = confirm(`¿Eliminar la evaluación #${id}?`);
    if (!confirmado) return;
    await fetch(`/api/evaluaciones/${id}`, { method: 'DELETE' });
    mostrarNotificacion('Evaluación eliminada.');
    await cargarResumen();
}

function abrirReporte(id) {
    window.open(`/api/evaluaciones/${id}/reporte_tecnico`, '_blank');
}

async function enviarAlertaGmail(id) {
    const evaluacion = estado.evaluaciones.find((item) => item.id === id);
    if (!evaluacion) return;
    if (evaluacion.riesgo !== 'Alto') {
        mostrarNotificacion('Solo se envía Gmail automático para riesgo Alto.');
        return;
    }
    const destino = prompt('Correo destino para la alerta Gmail. Si lo dejas vacío, Render usará GMAIL_DESTINO si está configurado:', '');
    const datos = new FormData();
    datos.append('destino', destino || '');
    try {
        const respuesta = await fetch(`/api/evaluaciones/${id}/alerta_gmail`, { method: 'POST', body: datos });
        const resultado = await respuesta.json();
        if (!respuesta.ok) throw new Error(resultado.detail || 'No se pudo enviar la alerta.');
        mostrarNotificacion(resultado.mensaje || (resultado.enviado ? 'Alerta enviada.' : 'Alerta simulada.'));
        if (!resultado.enviado && resultado.asunto) {
            console.info('Alerta Gmail simulada:', resultado);
        }
    } catch (error) {
        mostrarNotificacion(error.message);
    }
}

function moverSobreRiesgo(evento) {
    const canvas = evento.currentTarget;
    const rect = canvas.getBoundingClientRect();
    const x = (evento.clientX - rect.left) * (canvas.width / rect.width);
    const y = (evento.clientY - rect.top) * (canvas.height / rect.height);
    const segmento = estado.segmentosRiesgo.find((item) => {
        const dx = x - item.centroX;
        const dy = y - item.centroY;
        const distancia = Math.sqrt(dx * dx + dy * dy);
        let angulo = Math.atan2(dy, dx);
        if (angulo < -Math.PI / 2) angulo += Math.PI * 2;
        return distancia >= item.radio - 34 && distancia <= item.radio + 34 && angulo >= item.inicio && angulo <= item.fin;
    });
    if (segmento) {
        mostrarTooltip(evento.clientX, evento.clientY, `${segmento.nombre}: ${segmento.valor} evaluaciones`);
    } else {
        ocultarTooltip();
    }
}

function moverSobreCultivos(evento) {
    const canvas = evento.currentTarget;
    const rect = canvas.getBoundingClientRect();
    const x = (evento.clientX - rect.left) * (canvas.width / rect.width);
    const y = (evento.clientY - rect.top) * (canvas.height / rect.height);
    const barra = estado.barrasCultivo.find((item) => x >= item.x && x <= item.x + item.ancho && y >= item.y && y <= item.y + item.alto);
    if (barra) {
        mostrarTooltip(evento.clientX, evento.clientY, `${barra.nombre}: ${barra.valor} evaluaciones`);
    } else {
        ocultarTooltip();
    }
}

function mostrarTooltip(x, y, texto) {
    const tooltip = document.getElementById('tooltipGrafico');
    tooltip.textContent = texto;
    tooltip.style.left = `${x + 12}px`;
    tooltip.style.top = `${y + 12}px`;
    tooltip.style.display = 'block';
}

function ocultarTooltip() {
    document.getElementById('tooltipGrafico').style.display = 'none';
}

function dibujarTextoCentro(ctx, texto, x, y, subtitulo = '') {
    ctx.fillStyle = '#f9fbf4';
    ctx.font = '900 34px system-ui';
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    ctx.fillText(texto, x, y);
    if (subtitulo) {
        ctx.fillStyle = '#b9c9bd';
        ctx.font = '700 13px system-ui';
        ctx.fillText(subtitulo, x, y + 28);
    }
}

function redondearRectangulo(ctx, x, y, ancho, alto, radio) {
    const r = Math.min(radio, ancho / 2, alto / 2);
    ctx.beginPath();
    ctx.moveTo(x + r, y);
    ctx.arcTo(x + ancho, y, x + ancho, y + alto, r);
    ctx.arcTo(x + ancho, y + alto, x, y + alto, r);
    ctx.arcTo(x, y + alto, x, y, r);
    ctx.arcTo(x, y, x + ancho, y, r);
    ctx.closePath();
}

function mostrarNotificacion(mensaje) {
    const notificacion = document.getElementById('notificacion');
    notificacion.textContent = mensaje;
    notificacion.classList.add('visible');
    setTimeout(() => notificacion.classList.remove('visible'), 3400);
}

function bloquearBoton(id, bloqueado, texto) {
    const boton = document.getElementById(id);
    boton.disabled = bloqueado;
    boton.textContent = texto;
}

function escapar(valor) {
    return String(valor ?? '').replace(/[&<>'"]/g, (caracter) => ({
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        "'": '&#39;',
        '"': '&quot;'
    }[caracter]));
}

function formatearGeodatos(item) {
    const latitud = Number(item.latitud);
    const longitud = Number(item.longitud);
    const altitud = Number(item.altitud_msnm);
    const partes = [];
    if (Number.isFinite(latitud) && Number.isFinite(longitud)) partes.push(`${latitud.toFixed(4)}, ${longitud.toFixed(4)}`);
    if (Number.isFinite(altitud) && altitud > 0) partes.push(`${Math.round(altitud)} msnm`);
    return partes.join(' · ') || 'sin geodatos';
}

function formatearFecha(valor) {
    if (!valor) return '';
    return new Date(valor).toLocaleString('es-PE', { dateStyle: 'short', timeStyle: 'short' });
}


window.addEventListener('resize', () => {
    clearTimeout(window.__agroiaResizeTimer);
    window.__agroiaResizeTimer = setTimeout(() => {
        dibujarGraficoRiesgo();
        dibujarGraficoCultivos();
        if (estado.mapaLeaflet) {
            estado.mapaLeaflet.invalidateSize();
        }
    }, 140);
});