"use strict";

// =====================================================
// Control de Transferencias — interfaz
// Todo el comportamiento está aquí (no hay onclick en el HTML): los
// botones se conectan con addEventListener al cargar la página.
// =====================================================

const $ = (id) => document.getElementById(id);

const SIMBOLOS = { EUR: "€", USD: "$", GBP: "£" };

const estado = {
    persona: null,   // se elige al cargar la lista de personas
    personas: [],
    moneda: "EUR",
    mes: mesActual(),
    // Cada recarga incrementa este número. Si llega una respuesta de una
    // recarga antigua (por ejemplo, tras cambiar rápido de persona), se ignora.
    version: 0,
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

// "2026-10-05" → "5 oct 2026". Se construye la fecha con año/mes/día
// locales para evitar que la zona horaria la mueva al día anterior.
function formatearFecha(iso) {
    const [anio, mes, dia] = iso.split("-").map(Number);
    return new Date(anio, mes - 1, dia)
        .toLocaleDateString("es-ES", { day: "numeric", month: "short", year: "numeric" });
}

// Los importes llegan del servidor como texto ("1070.00") para no perder
// precisión; aquí solo se convierten a número para mostrarlos.
function formatearDinero(valor, moneda = estado.moneda) {
    const numero = new Intl.NumberFormat("es-ES", {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2,
    }).format(Number(valor) || 0);
    return `${numero} ${SIMBOLOS[moneda] || moneda}`;
}

function formatearPorcentaje(valor) {
    return `${new Intl.NumberFormat("es-ES", { maximumFractionDigits: 1 }).format(valor)} %`;
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
    // Con la ventana de personas abierta, el aviso se muestra dentro de ella.
    const contenedor = document.querySelector("dialog[open] .avisos") || $("avisos");
    contenedor.append(aviso);
    // Como mucho 3 avisos a la vez: se quitan los más antiguos.
    while (contenedor.children.length > 3) contenedor.firstElementChild.remove();
    setTimeout(() => aviso.remove(), 4000);
}

// Pone un botón en estado "cargando" y devuelve una función para restaurarlo.
function ocupar(boton, texto) {
    const original = boton.textContent;
    boton.disabled = true;
    boton.textContent = texto;
    return () => {
        boton.disabled = false;
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
    mostrarVista("vista-login");
    $("error-login").textContent = mensaje;
    $("pin").value = "";
    $("pin").focus();
}

async function mostrarApp() {
    mostrarVista("vista-app");
    $("fecha").value = hoyISO();
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
    const moneda = leerPreferencia("moneda");
    if (moneda && SIMBOLOS[moneda]) {
        estado.moneda = moneda;
        $("moneda").value = moneda;
    }
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
    if (!pin) {
        $("error-login").textContent = "Introduce el PIN";
        return;
    }

    const restaurar = ocupar(evento.submitter || evento.target.querySelector("button"), "Entrando…");
    try {
        await api("/login", { metodo: "POST", datos: { pin } });
        $("error-login").textContent = "";
        mostrarApp();
    } catch (error) {
        $("error-login").textContent = error.codigo === 401 ? "PIN incorrecto" : error.message;
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
            persona: estado.persona, moneda: estado.moneda, mes: estado.mes,
        }));
        if (version !== estado.version) return;
        pintarResumen(datos);
    } catch (error) {
        if (version !== estado.version) return;
        $("restante").textContent = "–";
        $("restante-detalle").textContent = `No se pudo cargar el resumen: ${error.message}`;
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
    return TRAMOS.find((tramo) => porcentaje >= tramo.desde);
}

function pintarResumen(datos) {
    const moneda = datos.moneda;
    const restante = Number(datos.restante);
    const cumplido = restante <= 0;

    $("titulo-resumen").textContent = `${nombreMes(datos.mes)} · ${estado.persona}`;

    const aviso = $("aviso-moneda");
    aviso.hidden = !datos.aviso;
    aviso.textContent = datos.aviso || "";

    $("resumen").classList.toggle("cumplido", cumplido);
    $("restante-etiqueta").textContent = cumplido ? "Objetivo cumplido · recibido" : "Falta por recibir";

    if (cumplido) {
        // Con el objetivo cumplido se muestra lo recibido y cuánto se ha superado.
        $("restante").textContent = formatearDinero(datos.total_confirmado, moneda);
        $("restante-detalle").textContent = restante < 0
            ? `Superado en ${formatearDinero(-restante, moneda)}`
            : "Justo el objetivo";
    } else {
        $("restante").textContent = formatearDinero(restante, moneda);
        const trasPendiente = Number(datos.restante_tras_pendiente);
        $("restante-detalle").textContent = Number(datos.pendiente) > 0
            ? (trasPendiente <= 0
                ? "Con lo pendiente se alcanzaría el objetivo"
                : `Con lo pendiente faltarían ${formatearDinero(trasPendiente, moneda)}`)
            : "";
    }

    // Barra: la parte verde es lo confirmado y la rayada lo pendiente.
    const confirmadoPct = Math.min(datos.porcentaje, 100);
    const pendientePct = Math.min(datos.porcentaje_pendiente, 100 - confirmadoPct);
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

    $("confirmado").textContent = formatearDinero(datos.total_confirmado, moneda);
    $("pendiente").textContent = formatearDinero(datos.pendiente, moneda);
    $("objetivo").textContent = formatearDinero(datos.objetivo, moneda);
    $("nuevo-objetivo").placeholder = datos.objetivo_eur;
}


// -----------------------------------------------------
// HISTORIAL
// -----------------------------------------------------

function mostrarEstadoLista(tipo, texto, alReintentar = null) {
    const caja = $("estado-lista");
    caja.replaceChildren();
    caja.className = `estado-lista ${tipo}`;
    if (!tipo) return;

    const parrafo = document.createElement("p");
    parrafo.textContent = texto;
    caja.append(parrafo);

    if (alReintentar) {
        const boton = document.createElement("button");
        boton.type = "button";
        boton.className = "boton secundario pequeno";
        boton.textContent = "Reintentar";
        boton.addEventListener("click", alReintentar);
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

async function cargarTransferencias(version) {
    const lista = $("lista-transferencias");
    lista.setAttribute("aria-busy", "true");
    mostrarEstadoLista("", "");
    pintarEsqueleto();

    try {
        const datos = await api(consulta("/transferencias", {
            persona: estado.persona, moneda: estado.moneda, mes: estado.mes,
        }));
        if (version !== estado.version) return;
        pintarTransferencias(datos);
    } catch (error) {
        if (version !== estado.version) return;
        lista.replaceChildren();
        $("contador").textContent = "";
        mostrarEstadoLista("error", `No se pudo cargar el historial: ${error.message}`, recargar);
    } finally {
        if (version === estado.version) lista.setAttribute("aria-busy", "false");
    }
}

function pintarTransferencias(datos) {
    const lista = $("lista-transferencias");
    const transferencias = datos.transferencias;

    lista.replaceChildren(...transferencias.map((t) => crearElemento(t, datos.moneda)));

    const n = transferencias.length;
    $("contador").textContent = n === 1 ? "1 transferencia" : `${n} transferencias`;
    if (n === 0) {
        mostrarEstadoLista("vacio", `No hay transferencias en ${nombreMes(datos.mes).toLowerCase()}.`);
    }
}

function crearElemento(t, moneda) {
    const elemento = $("plantilla-transferencia").content.firstElementChild.cloneNode(true);
    elemento.dataset.id = t.id;
    // Se guardan los datos originales (importe en EUR) para poder editar
    // sin depender del texto mostrado, que puede estar en otra moneda.
    elemento.dataset.montoEur = t.monto_eur;
    elemento.dataset.fecha = t.fecha;
    elemento.dataset.descripcion = t.descripcion;
    elemento.classList.toggle("confirmada", t.confirmada);

    elemento.querySelector(".movimiento-monto").textContent = formatearDinero(t.monto, moneda);
    const etiqueta = elemento.querySelector(".estado");
    etiqueta.textContent = t.confirmada ? "✓ Confirmada" : "Pendiente";

    const fecha = elemento.querySelector(".movimiento-fecha");
    fecha.dateTime = t.fecha;
    fecha.textContent = formatearFecha(t.fecha);
    elemento.querySelector(".movimiento-desc").textContent = t.descripcion || "Sin descripción";

    const descripcion = t.descripcion || formatearFecha(t.fecha);
    const confirmar = elemento.querySelector("[data-accion=confirmar]");
    confirmar.textContent = t.confirmada ? "Desconfirmar" : "Confirmar";
    confirmar.classList.add(t.confirmada ? "secundario" : "exito");
    confirmar.setAttribute("aria-label", `${confirmar.textContent}: ${descripcion}`);

    // Las confirmadas no se pueden editar ni eliminar (el servidor también lo impide).
    for (const accion of ["editar", "eliminar"]) {
        const boton = elemento.querySelector(`[data-accion=${accion}]`);
        if (t.confirmada) boton.remove();
        else boton.setAttribute("aria-label", `${boton.textContent}: ${descripcion}`);
    }
    return elemento;
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
    if (boton.dataset.accion === "eliminar") await eliminar(id, boton);
    if (boton.dataset.accion === "cancelar") recargar();
}

async function alternarConfirmacion(id, boton) {
    const restaurar = ocupar(boton, "Procesando…");
    try {
        const { confirmada } = await api(`/transferencias/${id}/confirmar`, { metodo: "PATCH" });
        avisar(confirmada ? "Transferencia confirmada" : "Transferencia marcada como pendiente");
        recargar();
    } catch (error) {
        avisar(error.message, "error");
        restaurar();
    }
}

async function eliminar(id, boton) {
    if (!confirm("¿Eliminar esta transferencia? No se puede deshacer.")) return;
    const restaurar = ocupar(boton, "Eliminando…");
    try {
        await api(`/transferencias/${id}`, { metodo: "DELETE" });
        avisar("Transferencia eliminada");
        recargar();
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
    formulario.elements.monto.value = elemento.dataset.montoEur;
    formulario.elements.fecha.value = elemento.dataset.fecha;
    formulario.elements.descripcion.value = elemento.dataset.descripcion;

    formulario.addEventListener("submit", (evento) => guardarEdicion(evento, id));
    elemento.classList.add("editando");
    elemento.replaceChildren(formulario);
    formulario.elements.monto.focus();
}

async function guardarEdicion(evento, id) {
    evento.preventDefault();
    const formulario = evento.target;
    const { monto, fecha, descripcion } = formulario.elements;
    const error = formulario.querySelector(".error-campo");

    if (!monto.value || Number(monto.value) <= 0 || !fecha.value) {
        error.textContent = "Monto y fecha son obligatorios";
        return;
    }

    const restaurar = ocupar(evento.submitter || formulario.querySelector("[type=submit]"), "Guardando…");
    try {
        await api(`/transferencias/${id}`, {
            metodo: "PUT",
            datos: { monto: monto.value, fecha: fecha.value, descripcion: descripcion.value },
        });
        avisar("Transferencia actualizada");
        cambiarMes(fecha.value.slice(0, 7));
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

    if (!monto.value || Number(monto.value) <= 0) {
        return mostrarErrorCampo(monto, "error-monto", "Introduce un importe mayor que 0");
    }
    if (!fecha.value) {
        return mostrarErrorCampo(fecha, "error-fecha", "Elige una fecha");
    }

    const restaurar = ocupar($("btn-agregar"), "Guardando…");
    try {
        await api("/transferencias", {
            metodo: "POST",
            datos: {
                monto: monto.value,
                fecha: fecha.value,
                descripcion: $("descripcion").value,
                persona: estado.persona,
            },
        });
        avisar("Transferencia añadida");
        monto.value = "";
        $("descripcion").value = "";
        // Se muestra el mes de la transferencia recién creada.
        cambiarMes(fecha.value.slice(0, 7));
        monto.focus();
    } catch (error) {
        avisar(error.message, "error");
    } finally {
        restaurar();
    }
}

async function guardarObjetivo(evento) {
    evento.preventDefault();
    const input = $("nuevo-objetivo");
    limpiarErrorCampo(input, "error-objetivo");

    if (!input.value || Number(input.value) <= 0) {
        return mostrarErrorCampo(input, "error-objetivo", "Introduce un objetivo mayor que 0");
    }

    const restaurar = ocupar(evento.submitter || evento.target.querySelector("button"), "Guardando…");
    try {
        await api("/objetivo", {
            metodo: "POST",
            datos: { objetivo: input.value, persona: estado.persona },
        });
        avisar("Objetivo actualizado");
        input.value = "";
        evento.target.closest("details").open = false;
        recargar();
    } catch (error) {
        mostrarErrorCampo(input, "error-objetivo", error.message);
    } finally {
        restaurar();
    }
}

async function convertirCantidad(evento) {
    evento.preventDefault();
    const cantidad = $("cantidad").value;
    const de = $("de").value;
    const a = $("a").value;
    const resultado = $("resultado-conversion");

    if (!cantidad || Number(cantidad) <= 0) {
        resultado.textContent = "Introduce una cantidad válida";
        $("tasa-info").textContent = "";
        return;
    }

    resultado.textContent = "Calculando…";
    $("tasa-info").textContent = "";
    try {
        const datos = await api(consulta("/convertir", { cantidad, de, a }));
        resultado.textContent = `${formatearDinero(datos.cantidad, de)} = ${formatearDinero(datos.resultado, a)}`;
        $("tasa-info").textContent = `1 ${de} = ${datos.tasa} ${a}`;
    } catch (error) {
        resultado.textContent = error.message;
    }
}

function invertirMonedas() {
    const de = $("de").value;
    $("de").value = $("a").value;
    $("a").value = de;
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
}

function elegirPersona(nombre) {
    estado.persona = nombre;
    guardarPreferencia("persona", nombre);
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
        let detalle = `Objetivo ${formatearDinero(p.objetivo, "EUR")} · ${n === 1 ? "1 transferencia" : `${n} transferencias`}`;

        // Mismas reglas que el servidor: no se elimina a quien tiene
        // transferencias ni a la última persona.
        const eliminar = fila.querySelector("[data-accion=eliminar-persona]");
        if (n > 0 || unica) {
            eliminar.disabled = true;
            detalle += n > 0 ? " · no se puede eliminar" : " · es la única persona";
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

    formulario.addEventListener("submit", (evento) => guardarNombre(evento, fila.dataset.id, fila.dataset.nombre));
    fila.replaceChildren(formulario);
    campo.select();
}

async function guardarNombre(evento, id, nombreAnterior) {
    evento.preventDefault();
    const formulario = evento.target;
    const nombre = formulario.elements.nombre.value.trim();
    const error = formulario.querySelector(".error-campo");

    if (!nombre) {
        error.textContent = "Escribe un nombre";
        return;
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
        error.textContent = e.message;
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

    if (!nombre.value.trim()) {
        return mostrarErrorCampo(nombre, "error-persona", "Escribe un nombre");
    }

    const restaurar = ocupar($("btn-persona"), "Guardando…");
    try {
        const persona = await api("/personas", {
            metodo: "POST",
            datos: { nombre: nombre.value, objetivo: objetivo.value },
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
function recargar() {
    estado.version += 1;
    cargarResumen(estado.version);
    cargarTransferencias(estado.version);
}

function pintarMes() {
    $("filtro-mes").value = estado.mes;
    $("texto-mes").textContent = nombreMes(estado.mes);
    // "Mes actual" solo tiene sentido si se está viendo otro mes.
    $("btn-mes-actual").disabled = estado.mes === mesActual();
}

function cambiarMes(mes) {
    if (!/^\d{4}-\d{2}$/.test(mes)) return;
    estado.mes = mes;
    pintarMes();
    recargar();
}


// -----------------------------------------------------
// ARRANQUE
// -----------------------------------------------------

document.addEventListener("DOMContentLoaded", () => {
    $("form-login").addEventListener("submit", entrar);
    $("btn-logout").addEventListener("click", salir);

    $("moneda").addEventListener("change", (evento) => {
        estado.moneda = evento.target.value;
        guardarPreferencia("moneda", estado.moneda);
        recargar();
    });

    $("filtro-mes").addEventListener("change", (evento) => cambiarMes(evento.target.value));
    // En ordenador, un clic en la caja no abre el calendario por sí solo: se pide.
    $("filtro-mes").addEventListener("click", (evento) => {
        try { evento.target.showPicker(); } catch { /* navegador sin showPicker */ }
    });
    $("mes-anterior").addEventListener("click", () => cambiarMes(sumarMeses(estado.mes, -1)));
    $("mes-siguiente").addEventListener("click", () => cambiarMes(sumarMeses(estado.mes, 1)));
    $("btn-mes-actual").addEventListener("click", () => cambiarMes(mesActual()));

    $("form-nueva").addEventListener("submit", agregarTransferencia);
    $("form-objetivo").addEventListener("submit", guardarObjetivo);
    $("form-conversor").addEventListener("submit", convertirCantidad);
    $("btn-invertir").addEventListener("click", invertirMonedas);
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
