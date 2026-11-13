"use strict";

// =====================================================
// Control de Transferencias — interfaz
// Todo el comportamiento está aquí (no hay onclick en el HTML): los
// botones se conectan con addEventListener al cargar la página.
// =====================================================

const $ = (id) => document.getElementById(id);

// Las mismas medidas que la rejilla de styles.css: por debajo, una sola columna.
const PANTALLA_ESTRECHA = window.matchMedia("(max-width: 899px)");
const PANTALLA_TACTIL = window.matchMedia("(pointer: coarse)");

const estado = {
    persona: null,   // se elige al cargar la lista de personas
    personas: [],
    mes: mesActual(),
    // Cada recarga incrementa este número. Si llega una respuesta de una
    // recarga antigua (por ejemplo, tras cambiar rápido de persona), se ignora.
    version: 0,
    anunciar: false, // al cambiar de mes o persona, se lee el nuevo resumen
};


// -----------------------------------------------------
// UTILIDADES
// -----------------------------------------------------

function mesActual() {
    const hoy = new Date();
    return `${hoy.getFullYear()}-${String(hoy.getMonth() + 1).padStart(2, "0")}`;
}

function hoyISO() {
    const hoy = new Date();
    return `${mesActual()}-${String(hoy.getDate()).padStart(2, "0")}`;
}

function sumarMeses(mes, cantidad) {
    const [anio, numero] = mes.split("-").map(Number);
    const fecha = new Date(anio, numero - 1 + cantidad, 1);
    return `${fecha.getFullYear()}-${String(fecha.getMonth() + 1).padStart(2, "0")}`;
}

function nombreMes(mes) {
    const [anio, numero] = mes.split("-").map(Number);
    const texto = new Date(anio, numero - 1, 1)
        .toLocaleDateString("es-ES", { month: "long", year: "numeric" });
    return texto.charAt(0).toUpperCase() + texto.slice(1);
}

// "2026-10-28" → "28/10/2026"
function formatearFechaNumerica(iso) {
    const [anio, mes, dia] = iso.split("-");
    return `${dia}/${mes}/${anio}`;
}

// Muestra la fecha del campo nativo en DD/MM/AAAA en su caja (.caja-fecha).
function pintarFecha(input) {
    input.closest(".caja-fecha").querySelector(".texto-fecha").textContent =
        input.value ? formatearFechaNumerica(input.value) : "";
}

// El campo nativo es invisible. Al usar el teclado se muestra (.con-teclado)
// para ver qué parte de la fecha se está escribiendo; al salir se vuelve a ocultar.
function prepararTeclado(input) {
    const caja = input.parentElement;
    input.addEventListener("keyup", () => caja.classList.add("con-teclado"));
    input.addEventListener("blur", () => caja.classList.remove("con-teclado"));
}

function prepararCampoFecha(input) {
    prepararTeclado(input);
    input.addEventListener("change", () => pintarFecha(input));
    input.addEventListener("input", () => pintarFecha(input));
    // En ordenador, un clic no abre el calendario por sí solo: se pide.
    input.addEventListener("click", () => {
        try { input.showPicker(); } catch { /* navegador sin showPicker */ }
    });
    pintarFecha(input);
}

// Los importes llegan del servidor como texto ("1070.00") para no perder
// precisión; aquí solo se convierten a número para mostrarlos.
function formatearDinero(valor) {
    const numero = new Intl.NumberFormat("es-ES", {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2,
    }).format(Number(valor) || 0);
    return `${numero} €`;
}

// "transferencia" o "retirada", para los textos de avisos y preguntas.
function nombreTipo(tipo) {
    return tipo === "retirada" ? "retirada" : "transferencia";
}

// Con mayúscula inicial, para empezar una frase ("Retirada añadida…").
function nombreTipoFrase(tipo) {
    const nombre = nombreTipo(tipo);
    return nombre[0].toUpperCase() + nombre.slice(1);
}

function formatearPorcentaje(valor) {
    return `${new Intl.NumberFormat("es-ES", { maximumFractionDigits: 1 }).format(valor)} %`;
}

// Convierte lo escrito en un importe para la API: acepta "1070,50", "1070.50" y
// "1.070,50" y devuelve "1070.50". Devuelve null si no es válido o no es mayor
// que 0. "1.070" sin coma no se acepta: no se sabe si son 1070 € o 1,07 €.
function leerImporte(texto) {
    let limpio = texto.replace(/[\s€]/g, "");
    if (limpio.includes(",")) limpio = limpio.replace(/\./g, "").replace(",", ".");
    return /^\d+(\.\d{1,2})?$/.test(limpio) && Number(limpio) > 0 ? limpio : null;
}

function guardarPreferencia(clave, valor) {
    try { localStorage.setItem(clave, valor); } catch { /* modo privado: no pasa nada */ }
}

function leerPreferencia(clave) {
    try { return localStorage.getItem(clave); } catch { return null; }
}

// Muestra un aviso temporal. Usa textContent, nunca innerHTML, para que
// ningún texto se interprete como HTML.
function avisar(texto, tipo = "exito") {
    const aviso = document.createElement("div");
    aviso.className = `aviso-flotante ${tipo}`;
    aviso.textContent = texto;
    // Los errores se anuncian enseguida (role="alert") y duran más en pantalla,
    // para que dé tiempo a leerlos.
    const esError = tipo === "error";
    if (esError) aviso.setAttribute("role", "alert");
    // Con la ventana de personas abierta, el aviso se muestra dentro de ella.
    const contenedor = document.querySelector("dialog[open] .avisos") || $("avisos");
    contenedor.append(aviso);
    // Como mucho 3 avisos a la vez: se quitan los más antiguos.
    while (contenedor.children.length > 3) contenedor.firstElementChild.remove();
    setTimeout(() => aviso.remove(), esError ? 8000 : 4000);
}

// Pone un botón en estado "cargando" y devuelve una función para restaurarlo.
function ocupar(boton, texto) {
    const original = boton.textContent;
    boton.disabled = true;
    boton.setAttribute("aria-busy", "true");
    boton.textContent = texto;
    return () => {
        boton.disabled = false;
        boton.removeAttribute("aria-busy");
        boton.textContent = original;
    };
}

function mostrarErrorCampo(input, idError, mensaje) {
    $(idError).textContent = mensaje;
    input.setAttribute("aria-invalid", "true");
    input.focus();
}

function limpiarErrorCampo(input, idError) {
    $(idError).textContent = "";
    input.removeAttribute("aria-invalid");
}


// -----------------------------------------------------
// LLAMADAS A LA API
// -----------------------------------------------------

class ErrorApi extends Error {
    constructor(mensaje, codigo) {
        super(mensaje);
        this.codigo = codigo;
    }
}

async function api(url, { metodo = "GET", datos } = {}) {
    const opciones = { method: metodo, credentials: "same-origin", headers: {} };
    if (datos !== undefined) {
        opciones.headers["Content-Type"] = "application/json";
        opciones.body = JSON.stringify(datos);
    }

    let respuesta;
    try {
        respuesta = await fetch(url, opciones);
    } catch {
        throw new ErrorApi("Sin conexión con el servidor", 0);
    }

    let cuerpo = null;
    try { cuerpo = await respuesta.json(); } catch { /* respuesta sin JSON */ }

    // Si la sesión caduca en mitad del uso, se vuelve al login.
    if (respuesta.status === 401 && url !== "/login" && url !== "/check-auth") {
        mostrarLogin("Tu sesión ha caducado. Vuelve a entrar.");
    }

    if (!respuesta.ok) {
        throw new ErrorApi(cuerpo?.error || "Error en la petición", respuesta.status);
    }
    return cuerpo;
}

function consulta(ruta, parametros) {
    return `${ruta}?${new URLSearchParams(parametros)}`;
}


// -----------------------------------------------------
// VISTAS (carga, login, app)
// -----------------------------------------------------

function mostrarVista(id) {
    for (const vista of ["vista-carga", "vista-login", "vista-app"]) {
        $(vista).hidden = vista !== id;
    }
}

function mostrarLogin(mensaje = "") {
    // Una ventana modal abierta dejaría el login sin poder usarse.
    document.querySelector("dialog[open]")?.close();
    mostrarVista("vista-login");
    $("error-login").textContent = mensaje;
    $("pin").value = "";
    $("pin").focus();
}

async function mostrarApp() {
    mostrarVista("vista-app");
    proponerFecha();
    // Sin la lista de personas no se sabe qué datos pedir, así que va primero.
    try {
        await cargarPersonas();
    } catch (error) {
        mostrarEstadoLista("error", `No se pudieron cargar las personas: ${error.message}`, mostrarApp);
        return;
    }
    recargar();
}

async function iniciar() {
    pintarMes();

    try {
        await api("/check-auth");
        mostrarApp();
    } catch {
        mostrarLogin();
    }
}

async function entrar(evento) {
    evento.preventDefault();
    const pin = $("pin").value.trim();
    $("pin").removeAttribute("aria-invalid");
    if (!pin) {
        $("error-login").textContent = "Introduce el PIN";
        $("pin").setAttribute("aria-invalid", "true");
        $("pin").focus();
        return;
    }

    const restaurar = ocupar(evento.submitter || evento.target.querySelector("button"), "Entrando…");
    try {
        await api("/login", { metodo: "POST", datos: { pin } });
        $("error-login").textContent = "";
        mostrarApp();
        $("principal").focus();   // el botón de entrar ya no se ve: el foco no se pierde
    } catch (error) {
        $("error-login").textContent = error.codigo === 401 ? "PIN incorrecto" : error.message;
        $("pin").setAttribute("aria-invalid", "true");
        $("pin").select();
    } finally {
        restaurar();
    }
}

async function salir() {
    try { await api("/logout", { metodo: "POST" }); } catch { /* da igual: se sale igualmente */ }
    mostrarLogin();
}


// -----------------------------------------------------
// RESUMEN
// -----------------------------------------------------

async function cargarResumen(version) {
    const tarjeta = $("resumen");
    tarjeta.setAttribute("aria-busy", "true");
    tarjeta.classList.add("cargando");

    try {
        const datos = await api(consulta("/resumen", {
            persona: estado.persona, mes: estado.mes,
        }));
        if (version !== estado.version) return;
        pintarResumen(datos);
    } catch (error) {
        if (version !== estado.version) return;
        pintarResumenConError(error.message);
    } finally {
        if (version === estado.version) {
            tarjeta.setAttribute("aria-busy", "false");
            tarjeta.classList.remove("cargando");
        }
    }
}

// Tramos de la barra de progreso, del más alto al más bajo.
const TRAMOS = [
    { desde: 66, clase: "tramo-casi", texto: "Ya casi está" },
    { desde: 33, clase: "tramo-mitad", texto: "A mitad de camino" },
    { desde: 0, clase: "tramo-lejos", texto: "Lejos del objetivo" },
];
const TRAMO_CUMPLIDO = { clase: "tramo-cumplido", texto: "¡Objetivo cumplido!" };

function tramoProgreso(porcentaje, cumplido) {
    // "cumplido" viene de restante <= 0: así el verde coincide exactamente
    // con el mensaje "Objetivo cumplido", aunque el % esté redondeado.
    if (cumplido) return TRAMO_CUMPLIDO;
    // Con retiradas el % puede ser negativo: entonces, el tramo más bajo.
    return TRAMOS.find((tramo) => porcentaje >= tramo.desde) ?? TRAMOS[TRAMOS.length - 1];
}

// Si el resumen no se puede cargar, no debe quedar ningún dato anterior a la
// vista: podría ser de otra persona o de otro mes y parecer el actual.
function pintarResumenConError(mensaje) {
    $("titulo-resumen").textContent = `${nombreMes(estado.mes)} · ${estado.persona}`;

    const tarjeta = $("resumen");
    tarjeta.classList.remove("cumplido");
    for (const { clase } of [...TRAMOS, TRAMO_CUMPLIDO]) tarjeta.classList.remove(clase);

    $("restante-etiqueta").textContent = "Falta por recibir";
    $("restante").textContent = "–";
    $("restante-detalle").textContent = `No se pudo cargar el resumen: ${mensaje}`;
    estado.anunciar = false;
    $("btn-reintentar-resumen").hidden = false;

    $("barra-confirmado").style.width = "0%";
    $("barra-pendiente").style.width = "0%";
    $("barra").setAttribute("aria-valuenow", "0");
    $("barra").setAttribute("aria-valuetext", "Sin datos");
    $("estado-progreso").textContent = "";
    $("texto-progreso").textContent = "–";

    for (const id of ["confirmado", "pendiente", "objetivo", "retirado"]) $(id).textContent = "–";
    $("nuevo-objetivo").placeholder = "";
}

function pintarResumen(datos) {
    const restante = Number(datos.restante);
    const cumplido = restante <= 0;

    $("titulo-resumen").textContent = `${nombreMes(datos.mes)} · ${estado.persona}`;
    $("btn-reintentar-resumen").hidden = true;

    $("resumen").classList.toggle("cumplido", cumplido);
    $("restante-etiqueta").textContent = cumplido ? "Objetivo cumplido · recibido" : "Falta por recibir";

    if (cumplido) {
        // Con el objetivo cumplido se muestra lo recibido y cuánto se ha superado.
        $("restante").textContent = formatearDinero(datos.total_confirmado);
        $("restante-detalle").textContent = restante < 0
            ? `Superado en ${formatearDinero(-restante)}`
            : "Justo el objetivo";
    } else {
        $("restante").textContent = formatearDinero(restante);
        const trasPendiente = Number(datos.restante_tras_pendiente);
        $("restante-detalle").textContent = Number(datos.pendiente) > 0
            ? (trasPendiente <= 0
                ? "Con lo pendiente se alcanzaría el objetivo"
                : `Con lo pendiente faltarían ${formatearDinero(trasPendiente)}`)
            : "";
    }

    // Barra: la parte sólida es lo confirmado y la rayada lo pendiente.
    // Se recorta a 0–100: con retiradas, lo confirmado o lo pendiente pueden ser negativos.
    const confirmadoPct = Math.max(0, Math.min(datos.porcentaje, 100));
    const pendientePct = Math.max(0, Math.min(datos.porcentaje_pendiente, 100 - confirmadoPct));
    $("barra-confirmado").style.width = `${confirmadoPct}%`;
    $("barra-pendiente").style.width = `${pendientePct}%`;
    $("barra").setAttribute("aria-valuenow", String(Math.round(confirmadoPct)));

    const tramo = tramoProgreso(datos.porcentaje, cumplido);
    const tarjeta = $("resumen");
    for (const { clase } of [...TRAMOS, TRAMO_CUMPLIDO]) tarjeta.classList.remove(clase);
    tarjeta.classList.add(tramo.clase);
    $("estado-progreso").textContent = tramo.texto;

    $("texto-progreso").textContent = `${formatearPorcentaje(datos.porcentaje)} confirmado`;
    // Lo que lee un lector de pantalla al llegar a la barra
    $("barra").setAttribute("aria-valuetext",
        `${formatearPorcentaje(datos.porcentaje)} confirmado. ${tramo.texto}`);

    $("confirmado").textContent = formatearDinero(datos.total_confirmado);
    $("pendiente").textContent = formatearDinero(datos.pendiente);
    $("objetivo").textContent = formatearDinero(datos.objetivo);
    // "Retirado" solo aparece si este mes se ha cogido dinero del pote.
    const hayRetiradas = Number(datos.retirado) > 0;
    $("retirado").textContent = formatearDinero(datos.retirado);
    $("cifra-retirado").hidden = !hayRetiradas;
    $("cifra-retirado").parentElement.classList.toggle("con-retirado", hayRetiradas);
    // Con el formato del resto de la app ("1070,00 €"), no el de la API ("1070.00")
    $("nuevo-objetivo").placeholder = `Actual: ${formatearDinero(datos.objetivo)}`;

    if (estado.anunciar) {
        estado.anunciar = false;
        $("anuncios").textContent = `${$("titulo-resumen").textContent}. ` +
            `${$("restante-etiqueta").textContent}: ${$("restante").textContent}`;
    }
}


// -----------------------------------------------------
// MES PARA EL QUE CUENTA UNA TRANSFERENCIA
// -----------------------------------------------------
// Normalmente una transferencia cuenta para el mes de su fecha, pero puede
// ser un adelanto (recibida en octubre para noviembre) o un atraso.

// Diferencia en meses entre dos "AAAA-MM" (ej.: de 2026-10 a 2026-11 → 1).
function mesesEntre(desde, hasta) {
    const [a1, m1] = desde.split("-").map(Number);
    const [a2, m2] = hasta.split("-").map(Number);
    return (a2 - a1) * 12 + (m2 - m1);
}

// Rellena el <select> con el mes de la fecha y el siguiente (un adelanto).
// No se ofrece el mes anterior: no tiene sentido contar para un mes pasado.
// "desplazamiento" indica cuál queda elegido (0 o 1).
function pintarOpcionesMes(select, fecha, desplazamiento = 0) {
    if (!fecha) return;
    const base = fecha.slice(0, 7);

    select.replaceChildren(...[0, 1].map((d) => {
        const mes = sumarMeses(base, d);
        // El mes de la fecha va sin coletilla: "(mes actual)" era falso si la
        // fecha es de otro mes. Solo se marca la opción del adelanto.
        const texto = nombreMes(mes) + (d === 0 ? "" : " (adelantada)");
        const opcion = new Option(texto, mes);
        opcion.dataset.desplazamiento = d;
        opcion.dataset.texto = texto;   // marcarMesesCompletos() le añade "completo"
        return opcion;
    }));
    select.value = sumarMeses(base, desplazamiento === 1 ? 1 : 0);
    delete select.dataset.autoElegido;
}

// Propone en el formulario una fecha del mes que se está viendo: hoy si es el
// mes actual y, si no, el día 1. Así lo añadido no acaba en otro mes por descuido.
function proponerFecha() {
    $("fecha").value = estado.mes === mesActual() ? hoyISO() : `${estado.mes}-01`;
    pintarFecha($("fecha"));
    pintarOpcionesMes($("mes-cuenta"), $("fecha").value);
}

// Si cambia la fecha, se mantiene la elección relativa ("el mes siguiente"),
// salvo que el adelanto lo eligiera la app por estar completo el mes.
function alCambiarFecha(inputFecha, select) {
    const elegida = select.selectedOptions[0];
    const desplazamiento = select.dataset.autoElegido ? 0 : Number(elegida?.dataset.desplazamiento || 0);
    pintarOpcionesMes(select, inputFecha.value, desplazamiento);
}

// Cada comprobación incrementa este número; si llega una respuesta antigua
// (por ejemplo, tras cambiar rápido la fecha o la persona), se ignora.
let versionCompletos = 0;

// En el formulario de nueva transferencia, desactiva el mes que ya tiene el
// objetivo cumplido (lo confirmado llega al objetivo, igual que la barra
// verde) y elige el otro. Es solo una ayuda de la interfaz: la API no lo
// impide. Si los dos meses están completos, se dejan ambos con un aviso para
// no quedarse nunca sin poder guardar.
async function marcarMesesCompletos() {
    const select = $("mes-cuenta");
    const ayuda = $("ayuda-mes-cuenta");
    if (!$("fecha").value || !estado.persona) return;

    const version = ++versionCompletos;
    const meses = [...select.options].map((opcion) => opcion.value);
    let completos;
    try {
        completos = await Promise.all(meses.map(async (mes) => {
            const datos = await api(consulta("/resumen", { persona: estado.persona, mes }));
            return Number(datos.restante) <= 0;
        }));
    } catch {
        return;   // sin datos, el selector se queda como estaba
    }
    if (version !== versionCompletos) return;

    const todos = completos.every(Boolean);
    [...select.options].forEach((opcion, i) => {
        opcion.disabled = completos[i] && !todos;
        opcion.textContent = opcion.dataset.texto + (completos[i] ? " · completo" : "");
    });

    // Si lo elegido quedó desactivado, se pasa al otro mes. Y si fue la app
    // quien eligió el adelanto y el mes vuelve a tener hueco, se deshace.
    const [delMes, siguiente] = select.options;
    if (select.selectedOptions[0]?.disabled) {
        select.value = siguiente.disabled ? delMes.value : siguiente.value;
        select.dataset.autoElegido = "1";
    } else if (select.dataset.autoElegido && !delMes.disabled) {
        select.value = delMes.value;
        delete select.dataset.autoElegido;
    }

    ayuda.dataset.normal ??= ayuda.textContent;
    if (todos) {
        ayuda.textContent = "Los dos meses ya tienen el objetivo cumplido.";
    } else if (delMes.disabled) {
        ayuda.textContent = `${nombreMes(delMes.value)} ya tiene el objetivo cumplido, ` +
            `así que cuenta para ${nombreMes(siguiente.value).toLowerCase()}.`;
    } else {
        ayuda.textContent = ayuda.dataset.normal;
    }
}


// -----------------------------------------------------
// HISTORIAL
// -----------------------------------------------------

function mostrarEstadoLista(tipo, texto, alPulsar = null, textoBoton = "Reintentar") {
    const caja = $("estado-lista");
    caja.replaceChildren();
    caja.className = `estado-lista ${tipo}`;
    if (!tipo) return;

    const parrafo = document.createElement("p");
    parrafo.textContent = texto;
    caja.append(parrafo);

    if (alPulsar) {
        const boton = document.createElement("button");
        boton.type = "button";
        boton.className = "boton secundario pequeno";
        boton.textContent = textoBoton;
        boton.addEventListener("click", alPulsar);
        caja.append(boton);
    }
}

function pintarEsqueleto() {
    const lista = $("lista-transferencias");
    lista.replaceChildren();
    for (let i = 0; i < 3; i++) {
        const fila = document.createElement("li");
        fila.className = "movimiento esqueleto";
        fila.setAttribute("aria-hidden", "true");
        lista.append(fila);
    }
}

// "silenciosa": sin esqueleto, para las recargas tras una acción. La lista sigue
// a la vista hasta que llegan los datos, sin parpadeo ni saltos de scroll.
async function cargarTransferencias(version, silenciosa) {
    const lista = $("lista-transferencias");
    lista.setAttribute("aria-busy", "true");
    mostrarEstadoLista("", "");
    if (!silenciosa) pintarEsqueleto();

    try {
        const datos = await api(consulta("/transferencias", {
            persona: estado.persona, mes: estado.mes,
        }));
        if (version !== estado.version) return;
        pintarTransferencias(datos);
    } catch (error) {
        if (version !== estado.version) return;
        lista.replaceChildren();
        $("contador").textContent = "";
        $("leyenda-historial").hidden = true;
        mostrarEstadoLista("error", `No se pudo cargar el historial: ${error.message}`, recargar);
    } finally {
        if (version === estado.version) lista.setAttribute("aria-busy", "false");
    }
}

function pintarTransferencias(datos) {
    const lista = $("lista-transferencias");
    const transferencias = datos.transferencias;

    lista.replaceChildren(...transferencias.map((t) => crearElemento(t)));

    const n = transferencias.length;
    $("contador").textContent = n === 1 ? "1 transferencia" : `${n} transferencias`;
    $("leyenda-historial").hidden = n === 0;
    if (n === 0) {
        mostrarEstadoLista("vacio", `No hay transferencias en ${nombreMes(datos.mes).toLowerCase()}.`,
            abrirFormularioNueva, "Añadir transferencia");
    }
}

function crearElemento(t) {
    const elemento = $("plantilla-transferencia").content.firstElementChild.cloneNode(true);
    elemento.dataset.id = t.id;
    // Se guardan los datos originales para poder editar sin depender del
    // texto mostrado, que lleva formato español ("1.070,00 €").
    elemento.dataset.monto = t.monto;
    elemento.dataset.fecha = t.fecha;
    elemento.dataset.descripcion = t.descripcion;
    elemento.dataset.mesCuenta = t.mes_cuenta;
    elemento.dataset.tipo = t.tipo;
    elemento.classList.toggle("confirmada", t.confirmada);
    const retirada = t.tipo === "retirada";
    elemento.classList.toggle("movimiento-retirada", retirada);
    elemento.querySelector(".etiqueta-retirada").hidden = !retirada;
    // Una adelantada no lleva etiqueta: su fecha (de otro mes) ya lo indica.

    // Las retiradas restan del pote: se muestran con un "−" delante.
    elemento.querySelector(".movimiento-monto").textContent =
        (retirada ? "−" : "") + formatearDinero(t.monto);
    // Solo se etiquetan las pendientes (lo que falta por confirmar).
    elemento.querySelector(".estado").hidden = t.confirmada;

    const fecha = elemento.querySelector(".movimiento-fecha");
    fecha.dateTime = t.fecha;
    fecha.textContent = formatearFechaNumerica(t.fecha);
    elemento.querySelector(".movimiento-desc").textContent = t.descripcion || "Sin descripción";

    const descripcion = t.descripcion || formatearFechaNumerica(t.fecha);
    const confirmar = elemento.querySelector("[data-accion=confirmar]");
    confirmar.textContent = t.confirmada ? "Marcar pendiente" : "Confirmar";
    confirmar.classList.add(t.confirmada ? "suave" : "exito");
    confirmar.setAttribute("aria-label", `${confirmar.textContent}: ${descripcion}`);

    // Las confirmadas no se pueden editar ni eliminar (el servidor también lo
    // impide). La ayuda que lo explica sale una vez, encima de la lista.
    for (const accion of ["editar", "eliminar"]) {
        const boton = elemento.querySelector(`[data-accion=${accion}]`);
        if (t.confirmada) boton.remove();
        else boton.setAttribute("aria-label", `${boton.textContent}: ${descripcion}`);
    }
    return elemento;
}

function abrirFormularioNueva() {
    $("plegable-nueva").open = true;
    $("monto").focus();
}

// Un solo "escuchador" para todos los botones de la lista (delegación de
// eventos): funciona aunque la lista se vuelva a pintar.
async function accionLista(evento) {
    const boton = evento.target.closest("[data-accion]");
    if (!boton) return;
    const elemento = boton.closest(".movimiento");
    const id = elemento.dataset.id;

    if (boton.dataset.accion === "confirmar") await alternarConfirmacion(id, boton);
    if (boton.dataset.accion === "editar") abrirEdicion(elemento);
    if (boton.dataset.accion === "eliminar") await eliminar(id, boton, elemento);
    if (boton.dataset.accion === "cancelar") cancelarEdicion(elemento);
}

// Tras repintar la lista, devuelve el foco a la misma transferencia para que
// quien usa el teclado o un lector de pantalla no vuelva al principio de la
// página. Si la fila ya no está (se eliminó o pasó a otro mes), va al título.
function devolverFoco(id, accion) {
    const fila = $("lista-transferencias").querySelector(`.movimiento[data-id="${id}"]`);
    const destino = fila?.querySelector(`[data-accion=${accion}]`)
        || fila?.querySelector("[data-accion]")
        || $("titulo-historial");
    destino.focus();
}

async function alternarConfirmacion(id, boton) {
    const nombre = nombreTipoFrase(boton.closest(".movimiento").dataset.tipo);
    const restaurar = ocupar(boton, "Procesando…");
    try {
        const { confirmada } = await api(`/transferencias/${id}/confirmar`, { metodo: "PATCH" });
        avisar(confirmada ? `${nombre} confirmada` : `${nombre} marcada como pendiente`);
        await recargar({ silenciosa: true });
        devolverFoco(id, "confirmar");
    } catch (error) {
        avisar(error.message, "error");
        restaurar();
    }
}

async function eliminar(id, boton, elemento) {
    const { monto, fecha, tipo } = elemento.dataset;
    const pregunta = `¿Eliminar la ${nombreTipo(tipo)} de ${formatearDinero(monto)} del ` +
        `${formatearFechaNumerica(fecha)}? No se puede deshacer.`;
    if (!confirm(pregunta)) return;
    const restaurar = ocupar(boton, "Eliminando…");
    try {
        await api(`/transferencias/${id}`, { metodo: "DELETE" });
        avisar(`${nombreTipoFrase(tipo)} eliminada`);
        await recargar({ silenciosa: true });
        devolverFoco(id, "eliminar");
    } catch (error) {
        avisar(error.message, "error");
        restaurar();
    }
}

function abrirEdicion(elemento) {
    const id = elemento.dataset.id;
    const formulario = $("plantilla-edicion").content.firstElementChild.cloneNode(true);

    // Ids únicos para que cada etiqueta quede asociada a su campo.
    for (const etiqueta of formulario.querySelectorAll("label[data-para]")) {
        const campo = formulario.elements[etiqueta.dataset.para];
        campo.id = `editar-${etiqueta.dataset.para}-${id}`;
        etiqueta.htmlFor = campo.id;
    }
    // El mensaje de error queda asociado a los campos que valida, como en el alta.
    const error = formulario.querySelector(".error-campo");
    error.id = `error-editar-${id}`;
    for (const nombre of ["monto", "fecha"]) {
        formulario.elements[nombre].setAttribute("aria-describedby", error.id);
    }
    formulario.elements.monto.value = elemento.dataset.monto.replace(".", ",");
    formulario.elements.fecha.value = elemento.dataset.fecha;
    formulario.elements.descripcion.value = elemento.dataset.descripcion;
    formulario.elements.tipo.value = elemento.dataset.tipo;

    const { fecha, mes_cuenta: mesCuenta } = formulario.elements;
    pintarOpcionesMes(mesCuenta, elemento.dataset.fecha,
        mesesEntre(elemento.dataset.fecha.slice(0, 7), elemento.dataset.mesCuenta));
    fecha.addEventListener("change", () => alCambiarFecha(fecha, mesCuenta));
    prepararCampoFecha(fecha);

    formulario.addEventListener("submit", (evento) => guardarEdicion(evento, id));
    elemento.classList.add("editando");
    elemento.replaceChildren(formulario);
    formulario.elements.monto.focus();
}

// Cancelar solo vuelve a pintar esta fila con sus datos originales (guardados
// en data-*), sin recargar toda la lista. Solo se editan las pendientes.
function cancelarEdicion(elemento) {
    const fila = crearElemento({
        id: elemento.dataset.id,
        monto: elemento.dataset.monto,
        fecha: elemento.dataset.fecha,
        descripcion: elemento.dataset.descripcion,
        mes_cuenta: elemento.dataset.mesCuenta,
        tipo: elemento.dataset.tipo,
        confirmada: false,
    });
    elemento.replaceWith(fila);
    fila.querySelector("[data-accion=editar]").focus();
}

async function guardarEdicion(evento, id) {
    evento.preventDefault();
    const formulario = evento.target;
    const { monto, fecha, descripcion, tipo, mes_cuenta: mesCuenta } = formulario.elements;
    const error = formulario.querySelector(".error-campo");
    limpiarErrorCampo(monto, error.id);
    limpiarErrorCampo(fecha, error.id);

    const importe = leerImporte(monto.value);
    if (!importe) {
        return mostrarErrorCampo(monto, error.id, "Introduce un importe mayor que 0, como 1070,50");
    }
    if (!fecha.value) {
        return mostrarErrorCampo(fecha, error.id, "Elige una fecha");
    }

    const restaurar = ocupar(evento.submitter || formulario.querySelector("[type=submit]"), "Guardando…");
    try {
        await api(`/transferencias/${id}`, {
            metodo: "PUT",
            datos: {
                monto: importe,
                fecha: fecha.value,
                descripcion: descripcion.value,
                mes_cuenta: mesCuenta.value,
                tipo: tipo.value,
            },
        });
        const nombre = nombreTipoFrase(tipo.value);
        avisar(mesCuenta.value === estado.mes
            ? `${nombre} actualizada`
            : `${nombre} actualizada y movida a ${nombreMes(mesCuenta.value).toLowerCase()}`);
        await cambiarMes(mesCuenta.value);
        devolverFoco(id, "editar");
    } catch (e) {
        error.textContent = e.message;
        restaurar();
    }
}


// -----------------------------------------------------
// FORMULARIOS
// -----------------------------------------------------

async function agregarTransferencia(evento) {
    evento.preventDefault();
    const monto = $("monto");
    const fecha = $("fecha");
    limpiarErrorCampo(monto, "error-monto");
    limpiarErrorCampo(fecha, "error-fecha");
    $("error-nueva").textContent = "";

    const importe = leerImporte(monto.value);
    if (!importe) {
        return mostrarErrorCampo(monto, "error-monto", "Introduce un importe mayor que 0, como 1070,50");
    }
    if (!fecha.value) {
        return mostrarErrorCampo(fecha, "error-fecha", "Elige una fecha");
    }

    const mesCuenta = $("mes-cuenta").value;
    const tipo = tipoNuevo();
    const restaurar = ocupar($("btn-agregar"), "Guardando…");
    try {
        const { id } = await api("/transferencias", {
            metodo: "POST",
            datos: {
                monto: importe,
                fecha: fecha.value,
                descripcion: $("descripcion").value,
                persona: estado.persona,
                mes_cuenta: mesCuenta,
                tipo,
            },
        });
        avisar(`${nombreTipoFrase(tipo)} añadida a ${nombreMes(mesCuenta).toLowerCase()}`);
        monto.value = "";
        $("descripcion").value = "";
        // Lo habitual es apuntar transferencias recibidas: se vuelve a ese tipo.
        $("tipo-ingreso").checked = true;
        // La próxima vuelve a contar por defecto para el mes de su fecha.
        pintarOpcionesMes($("mes-cuenta"), fecha.value);
        // En móvil se pliega el formulario para ver el historial.
        if (PANTALLA_ESTRECHA.matches) $("plegable-nueva").open = false;
        // Se muestra el mes para el que cuenta la transferencia recién creada.
        await cambiarMes(mesCuenta);
        $("lista-transferencias").querySelector(`.movimiento[data-id="${id}"]`)?.classList.add("recien");
        // Con teclado físico se sigue añadiendo; en táctil, enfocar el campo
        // reabriría el teclado en pantalla, que tapa la lista y los avisos.
        if (PANTALLA_ESTRECHA.matches || PANTALLA_TACTIL.matches) devolverFoco(id, "confirmar");
        else monto.focus();
    } catch (error) {
        // Junto al formulario y sin desaparecer: lo escrito sigue ahí para corregirlo.
        $("error-nueva").textContent = error.message;
    } finally {
        restaurar();
        pintarTipoNuevo();   // después de restaurar(), que repone el texto anterior del botón
    }
}

async function guardarObjetivo(evento) {
    evento.preventDefault();
    const input = $("nuevo-objetivo");
    limpiarErrorCampo(input, "error-objetivo");

    const objetivo = leerImporte(input.value);
    if (!objetivo) {
        return mostrarErrorCampo(input, "error-objetivo", "Introduce un objetivo mayor que 0, como 1070,50");
    }

    const restaurar = ocupar(evento.submitter || evento.target.querySelector("button"), "Guardando…");
    try {
        await api("/objetivo", {
            metodo: "POST",
            datos: { objetivo, persona: estado.persona },
        });
        avisar("Objetivo actualizado");
        input.value = "";
        evento.target.closest("details").open = false;
        recargar({ silenciosa: true });
    } catch (error) {
        mostrarErrorCampo(input, "error-objetivo", error.message);
    } finally {
        restaurar();
    }
}


// -----------------------------------------------------
// PERSONAS
// -----------------------------------------------------

// Pide las personas al servidor y repinta el selector y la lista de "Personas".
async function cargarPersonas() {
    estado.personas = await api("/personas");
    const nombres = estado.personas.map((p) => p.nombre);

    // Si la persona elegida ya no existe (se eliminó), se usa la guardada o la primera.
    if (!nombres.includes(estado.persona)) {
        const guardada = leerPreferencia("persona");
        estado.persona = nombres.includes(guardada) ? guardada : nombres[0];
    }
    pintarSelectorPersonas();
    pintarListaPersonas();
}

function pintarSelectorPersonas() {
    const selector = $("selector-personas");
    const leyenda = selector.querySelector("legend");
    const opciones = estado.personas.flatMap((p) => {
        const radio = document.createElement("input");
        radio.type = "radio";
        radio.name = "persona";
        radio.id = `persona-${p.id}`;
        radio.value = p.nombre;
        radio.checked = p.nombre === estado.persona;
        radio.addEventListener("change", () => elegirPersona(p.nombre));

        const etiqueta = document.createElement("label");
        etiqueta.htmlFor = radio.id;
        etiqueta.textContent = p.nombre;
        return [radio, etiqueta];
    });
    selector.replaceChildren(leyenda, ...opciones);
    // Con una sola persona el selector no aporta nada: su nombre ya sale en el resumen.
    selector.hidden = estado.personas.length < 2;
    pintarTituloNueva();
}

// Tipo elegido en el formulario de alta: "ingreso" o "retirada".
function tipoNuevo() {
    return $("tipo-retirada").checked ? "retirada" : "ingreso";
}

// El formulario dice siempre a quién se le apunta y si es una transferencia
// recibida o una retirada del pote.
function pintarTituloNueva() {
    $("titulo-nueva").textContent = `Nueva ${nombreTipo(tipoNuevo())} · ${estado.persona}`;
}

// Al cambiar el tipo cambian el título, el botón y la etiqueta del mes.
function pintarTipoNuevo() {
    const retirada = tipoNuevo() === "retirada";
    pintarTituloNueva();
    $("btn-agregar").textContent = retirada ? "Añadir retirada" : "Añadir transferencia";
    $("etiqueta-mes-cuenta").textContent = retirada ? "Del pote de" : "Para el pote de";
}

function elegirPersona(nombre) {
    estado.persona = nombre;
    estado.anunciar = true;
    guardarPreferencia("persona", nombre);
    pintarTituloNueva();
    recargar();
}

function pintarListaPersonas() {
    const unica = estado.personas.length === 1;

    $("lista-personas").replaceChildren(...estado.personas.map((p) => {
        const fila = $("plantilla-persona").content.firstElementChild.cloneNode(true);
        fila.dataset.id = p.id;
        fila.dataset.nombre = p.nombre;
        fila.querySelector(".fila-persona-nombre").textContent = p.nombre;

        const n = p.transferencias;
        let detalle = `Objetivo ${formatearDinero(p.objetivo)} · ${n === 1 ? "1 transferencia" : `${n} transferencias`}`;

        // Mismas reglas que el servidor: no se elimina a quien tiene
        // transferencias ni a la última persona.
        const eliminar = fila.querySelector("[data-accion=eliminar-persona]");
        if (n > 0 || unica) {
            eliminar.disabled = true;
            detalle += n > 0 ? " · tiene transferencias, no se puede eliminar" : " · es la única persona";
        }
        eliminar.setAttribute("aria-label", `Eliminar a ${p.nombre}`);
        fila.querySelector("[data-accion=renombrar]").setAttribute("aria-label", `Renombrar a ${p.nombre}`);
        fila.querySelector(".fila-persona-detalle").textContent = detalle;
        return fila;
    }));
}

async function accionPersonas(evento) {
    const boton = evento.target.closest("[data-accion]");
    if (!boton) return;
    const fila = boton.closest(".fila-persona");

    if (boton.dataset.accion === "renombrar") abrirRenombrar(fila);
    if (boton.dataset.accion === "cancelar-persona") pintarListaPersonas();
    if (boton.dataset.accion === "eliminar-persona") await eliminarPersona(fila, boton);
}

function abrirRenombrar(fila) {
    const formulario = $("plantilla-renombrar").content.firstElementChild.cloneNode(true);
    const campo = formulario.elements.nombre;
    campo.id = `renombrar-${fila.dataset.id}`;
    formulario.querySelector("label").htmlFor = campo.id;
    campo.value = fila.dataset.nombre;
    // El mensaje de error queda asociado al campo, como en el alta.
    const error = formulario.querySelector(".error-campo");
    error.id = `error-renombrar-${fila.dataset.id}`;
    campo.setAttribute("aria-describedby", error.id);

    formulario.addEventListener("submit", (evento) => guardarNombre(evento, fila.dataset.id, fila.dataset.nombre));
    fila.replaceChildren(formulario);
    campo.select();
}

async function guardarNombre(evento, id, nombreAnterior) {
    evento.preventDefault();
    const formulario = evento.target;
    const campo = formulario.elements.nombre;
    const nombre = campo.value.trim();
    const error = formulario.querySelector(".error-campo");
    limpiarErrorCampo(campo, error.id);

    if (!nombre) {
        return mostrarErrorCampo(campo, error.id, "Escribe un nombre");
    }

    const restaurar = ocupar(evento.submitter || formulario.querySelector("[type=submit]"), "Guardando…");
    try {
        const persona = await api(`/personas/${id}`, { metodo: "PUT", datos: { nombre } });
        if (estado.persona === nombreAnterior) {
            estado.persona = persona.nombre;
            guardarPreferencia("persona", persona.nombre);
        }
        avisar("Nombre actualizado");
        await cargarPersonas();
        recargar();
    } catch (e) {
        mostrarErrorCampo(campo, error.id, e.message);
        restaurar();
    }
}

async function eliminarPersona(fila, boton) {
    if (!confirm(`¿Eliminar a ${fila.dataset.nombre}? No se puede deshacer.`)) return;

    const restaurar = ocupar(boton, "Eliminando…");
    try {
        await api(`/personas/${fila.dataset.id}`, { metodo: "DELETE" });
        avisar(`Persona eliminada: ${fila.dataset.nombre}`);
        await cargarPersonas();   // si era la persona elegida, pasa a la primera
        recargar();
    } catch (error) {
        avisar(error.message, "error");
        restaurar();
    }
}

async function agregarPersona(evento) {
    evento.preventDefault();
    const nombre = $("nombre-persona");
    const objetivo = $("objetivo-persona");
    limpiarErrorCampo(nombre, "error-persona");
    limpiarErrorCampo(objetivo, "error-persona");

    if (!nombre.value.trim()) {
        return mostrarErrorCampo(nombre, "error-persona", "Escribe un nombre");
    }
    // Es opcional: vacío, el servidor pone el objetivo inicial.
    const importe = objetivo.value.trim() ? leerImporte(objetivo.value) : "";
    if (importe === null) {
        return mostrarErrorCampo(objetivo, "error-persona", "Introduce un objetivo mayor que 0, como 1070,50");
    }

    const restaurar = ocupar($("btn-persona"), "Guardando…");
    try {
        const persona = await api("/personas", {
            metodo: "POST",
            datos: { nombre: nombre.value, objetivo: importe },
        });
        avisar(`Persona añadida: ${persona.nombre}`);
        nombre.value = "";
        objetivo.value = "";
        await cargarPersonas();
    } catch (error) {
        mostrarErrorCampo(nombre, "error-persona", error.message);
    } finally {
        restaurar();
    }
}


// -----------------------------------------------------
// FILTROS
// -----------------------------------------------------

// El resumen y el historial se cargan siempre juntos y con el mismo mes.
// Devuelve una promesa que termina cuando los dos están pintados (las dos
// cargas gestionan sus propios errores, así que nunca falla).
function recargar({ silenciosa = false } = {}) {
    estado.version += 1;
    marcarMesesCompletos();
    return Promise.all([cargarResumen(estado.version), cargarTransferencias(estado.version, silenciosa)]);
}

function pintarMes() {
    $("filtro-mes").value = estado.mes;
    $("texto-mes").textContent = nombreMes(estado.mes);
    // El enlace para volver solo tiene sentido si se está viendo otro mes.
    const boton = $("btn-mes-actual");
    boton.hidden = estado.mes === mesActual();
    boton.textContent = `Volver a ${nombreMes(mesActual()).toLowerCase()}`;
}

function cambiarMes(mes) {
    if (!/^\d{4}-\d{2}$/.test(mes)) return Promise.resolve();
    const mismoMes = mes === estado.mes;
    if (!mismoMes) {
        estado.mes = mes;
        estado.anunciar = true;
        proponerFecha();
    }
    pintarMes();
    return recargar({ silenciosa: mismoMes });
}


// -----------------------------------------------------
// ARRANQUE
// -----------------------------------------------------

document.addEventListener("DOMContentLoaded", () => {
    $("form-login").addEventListener("submit", entrar);
    $("btn-logout").addEventListener("click", salir);

    // Firefox y Safari de escritorio no tienen selector de mes: sería un texto
    // invisible. Sin él se queda el nombre del mes y se cambia con las flechas.
    if ($("filtro-mes").type === "month") {
        prepararTeclado($("filtro-mes"));
    } else {
        $("filtro-mes").hidden = true;
        $("texto-mes").removeAttribute("aria-hidden");
    }
    $("filtro-mes").addEventListener("change", (evento) => cambiarMes(evento.target.value));
    // En ordenador, un clic en la caja no abre el calendario por sí solo: se pide.
    $("filtro-mes").addEventListener("click", (evento) => {
        try { evento.target.showPicker(); } catch { /* navegador sin showPicker */ }
    });
    $("mes-anterior").addEventListener("click", () => cambiarMes(sumarMeses(estado.mes, -1)));
    $("mes-siguiente").addEventListener("click", () => cambiarMes(sumarMeses(estado.mes, 1)));
    $("btn-mes-actual").addEventListener("click", () => {
        cambiarMes(mesActual());
        // El enlace se oculta al pulsarlo: el foco pasa a las flechas
        // para no perderlo si se usa el teclado.
        $("mes-anterior").focus();
    });

    $("btn-reintentar-resumen").addEventListener("click", recargar);
    $("plegable-nueva").open = !PANTALLA_ESTRECHA.matches;
    $("form-nueva").addEventListener("submit", agregarTransferencia);
    for (const radio of document.querySelectorAll("#form-nueva input[name=tipo]")) {
        radio.addEventListener("change", pintarTipoNuevo);
    }
    $("fecha").addEventListener("change", () => {
        alCambiarFecha($("fecha"), $("mes-cuenta"));
        marcarMesesCompletos();
    });
    prepararCampoFecha($("fecha"));
    $("form-objetivo").addEventListener("submit", guardarObjetivo);
    $("lista-transferencias").addEventListener("click", accionLista);
    $("form-persona").addEventListener("submit", agregarPersona);

    const dialogo = $("dialogo-personas");
    $("btn-personas").addEventListener("click", () => dialogo.showModal());
    $("btn-cerrar-personas").addEventListener("click", () => dialogo.close());
    // Un clic en el fondo oscuro (fuera del contenido) también la cierra.
    dialogo.addEventListener("click", (evento) => {
        if (evento.target === dialogo) dialogo.close();
    });
    // Al cerrarla se descarta cualquier renombrado a medias.
    dialogo.addEventListener("close", pintarListaPersonas);
    $("lista-personas").addEventListener("click", accionPersonas);

    iniciar();
});
