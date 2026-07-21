import {
  enviarEntrega,
  guardarBorrador,
  obtenerBorradores,
  registrarEventoAuditoria,
} from './api.js';
import { iniciarAuditoria } from './auditoria.js';
import { activarEvidencias, detenerEvidencias, evidenciasActivas } from './flujos-evidencia.js';
import { guardarEntregaId, obtenerExamen, obtenerRol } from './sesion.js';

const examen = obtenerExamen();
const formulario = document.getElementById('formulario-examen');
const preguntasNodo = document.getElementById('preguntas');
const titulo = document.getElementById('titulo-examen');
const tiempoRestante = document.getElementById('tiempo-restante');
const estadoExamen = document.getElementById('estado-examen');
const contador = document.getElementById('contador-respuestas');
const aviso = document.getElementById('aviso-auditoria');
const estadoAutosalvado = document.getElementById('estado-autosalvado');
const estadoPermisos = document.getElementById('estado-permisos');
const reactivarPermisos = document.getElementById('reactivar-permisos');
let enviando = false;
let intervalo = null;
let intervaloAutosalvado = null;
const versionesBorrador = new Map();
const preguntasSucias = new Set();
const temporizadoresGuardado = new Map();
const colasGuardado = new Map();
const RETARDO_AUTOSALVADO_MS = 1200;
const INTERVALO_AUTOSALVADO_MS = 15000;
const desfaseServidorMs = examen
  ? Date.parse(examen.hora_actual_servidor) - Date.now()
  : 0;

function escapeHtml(texto) {
  return String(texto)
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;');
}

function mostrarAviso(texto) {
  aviso.textContent = texto;
  aviso.classList.remove('hidden');
}

function mostrarEstadoAutosalvado(texto, estado = 'ok') {
  estadoAutosalvado.textContent = texto;
  estadoAutosalvado.dataset.estado = estado;
}

function actualizarEstadoPermisos() {
  const activos = evidenciasActivas();
  estadoPermisos.textContent = activos
    ? 'Pantalla, camara y microfono activos.'
    : 'Permisos inactivos. Reactivalos para mantener la supervision.';
  estadoPermisos.dataset.estado = activos ? 'ok' : 'error';
  reactivarPermisos.classList.toggle('hidden', activos);
}

async function reactivarFlujos() {
  reactivarPermisos.disabled = true;
  try {
    await activarEvidencias();
  } catch {
    mostrarAviso('No se pudieron reactivar pantalla, camara y microfono.');
  } finally {
    reactivarPermisos.disabled = false;
    actualizarEstadoPermisos();
  }
}

function etiquetaTipo(tipo) {
  return {
    rellenar_huecos: 'Rellenar huecos',
    corregir_codigo: 'Corregir código',
    tipo_test: 'Tipo test',
    respuesta_corta: 'Respuesta corta',
  }[tipo];
}

function controlRespuesta(pregunta) {
  if (pregunta.tipo === 'tipo_test') {
    const opciones = (pregunta.opciones || [])
      .map((opcion) => `<option value="${escapeHtml(opcion)}">${escapeHtml(opcion)}</option>`)
      .join('');
    return `<select id="pregunta-${pregunta.id}" name="pregunta-${pregunta.id}" data-pregunta-id="${pregunta.id}" required><option value="">Selecciona una opción</option>${opciones}</select>`;
  }

  if (pregunta.tipo === 'rellenar_huecos' && pregunta.numero_huecos > 1) {
    const controles = Array.from({ length: pregunta.numero_huecos }, (_, indice) => `
      <label for="pregunta-${pregunta.id}-hueco-${indice}">Hueco ${indice + 1}</label>
      <textarea
        id="pregunta-${pregunta.id}-hueco-${indice}"
        data-hueco-indice="${indice}"
        required
        ${pregunta.limites_caracteres?.[indice] ? `maxlength="${pregunta.limites_caracteres[indice]}"` : ''}
      ></textarea>
    `).join('');
    return `<div data-pregunta-multiple="${pregunta.id}">${controles}</div>`;
  }

  const valorInicial = pregunta.tipo === 'corregir_codigo' ? pregunta.codigo_plantilla || '' : '';
  const limite = pregunta.limites_caracteres?.[0];
  return `<textarea id="pregunta-${pregunta.id}" name="pregunta-${pregunta.id}" data-pregunta-id="${pregunta.id}" required ${limite ? `maxlength="${limite}"` : ''}>${escapeHtml(valorInicial)}</textarea>`;
}

function renderizarPregunta(pregunta) {
  const plantilla = pregunta.codigo_plantilla
    ? `<pre>${escapeHtml(pregunta.codigo_plantilla)}</pre>`
    : '';
  const etiquetaRespuesta = pregunta.tipo === 'rellenar_huecos' && pregunta.numero_huecos > 1
    ? '<p><strong>Respuesta</strong></p>'
    : `<label for="pregunta-${pregunta.id}">Respuesta</label>`;
  return `
    <article class="pregunta">
      <header>
        <div>
          <p class="tipo-pregunta">${etiquetaTipo(pregunta.tipo)}</p>
          <h2>${pregunta.orden}. ${escapeHtml(pregunta.titulo)}</h2>
        </div>
      </header>
      <p>${escapeHtml(pregunta.enunciado)}</p>
      ${plantilla}
      ${etiquetaRespuesta}
      ${controlRespuesta(pregunta)}
    </article>
  `;
}

function actualizarContador() {
  const simples = [...formulario.querySelectorAll('[data-pregunta-id]')]
    .filter((control) => String(control.value || '').trim().length > 0).length;
  const multiples = [...formulario.querySelectorAll('[data-pregunta-multiple]')]
    .filter((grupo) => [...grupo.querySelectorAll('textarea')]
      .some((control) => String(control.value || '').trim().length > 0)).length;
  const respondidas = simples + multiples;
  contador.textContent = respondidas === 1 ? '1 respuesta' : `${respondidas} respuestas`;
}

function recopilarRespuestas() {
  const simples = [...formulario.querySelectorAll('[data-pregunta-id]')].map((control) => ({
    pregunta_id: Number(control.dataset.preguntaId),
    contenido: String(control.value || ''),
  }));
  const multiples = [...formulario.querySelectorAll('[data-pregunta-multiple]')].map((grupo) => ({
    pregunta_id: Number(grupo.dataset.preguntaMultiple),
    contenido: JSON.stringify([...grupo.querySelectorAll('textarea')]
      .map((control) => String(control.value || ''))),
  }));
  return [...simples, ...multiples];
}

function contenidoPregunta(preguntaId) {
  const simple = formulario.querySelector(`[data-pregunta-id="${preguntaId}"]`);
  if (simple) {
    return String(simple.value || '');
  }
  const grupo = formulario.querySelector(`[data-pregunta-multiple="${preguntaId}"]`);
  if (!grupo) {
    return null;
  }
  return JSON.stringify([...grupo.querySelectorAll('textarea')]
    .map((control) => String(control.value || '')));
}

function aplicarContenidoBorrador(preguntaId, contenido) {
  const simple = formulario.querySelector(`[data-pregunta-id="${preguntaId}"]`);
  if (simple) {
    simple.value = contenido;
    return;
  }
  const grupo = formulario.querySelector(`[data-pregunta-multiple="${preguntaId}"]`);
  if (!grupo) {
    return;
  }
  let valores;
  try {
    valores = JSON.parse(contenido);
  } catch {
    valores = [];
  }
  [...grupo.querySelectorAll('textarea')].forEach((control, indice) => {
    control.value = String(valores[indice] || '');
  });
}

function preguntaIdDesdeControl(control) {
  if (control.dataset?.preguntaId) {
    return Number(control.dataset.preguntaId);
  }
  const grupo = control.closest('[data-pregunta-multiple]');
  return grupo ? Number(grupo.dataset.preguntaMultiple) : null;
}

async function guardarPreguntaAhora(preguntaId) {
  const contenido = contenidoPregunta(preguntaId);
  if (contenido === null || !preguntasSucias.has(preguntaId)) {
    return true;
  }
  const versionEsperada = versionesBorrador.get(preguntaId) || 0;
  mostrarEstadoAutosalvado('Guardando borrador…', 'guardando');
  const response = await guardarBorrador(
    examen.entrega_id,
    preguntaId,
    contenido,
    versionEsperada,
  );
  if (!response.ok) {
    mostrarEstadoAutosalvado(response.error, 'error');
    return false;
  }
  versionesBorrador.set(preguntaId, response.datos.version);
  if (contenidoPregunta(preguntaId) === contenido) {
    preguntasSucias.delete(preguntaId);
  }
  const hora = new Date(response.datos.actualizado_en).toLocaleTimeString();
  mostrarEstadoAutosalvado(`Borrador guardado a las ${hora}`);
  return true;
}

function encolarGuardado(preguntaId) {
  const anterior = colasGuardado.get(preguntaId) || Promise.resolve(true);
  const actual = anterior
    .catch(() => false)
    .then(() => guardarPreguntaAhora(preguntaId));
  colasGuardado.set(preguntaId, actual);
  actual.finally(() => {
    if (colasGuardado.get(preguntaId) === actual) {
      colasGuardado.delete(preguntaId);
    }
  });
  return actual;
}

function programarGuardado(preguntaId) {
  if (!preguntaId) {
    return;
  }
  preguntasSucias.add(preguntaId);
  window.clearTimeout(temporizadoresGuardado.get(preguntaId));
  temporizadoresGuardado.set(
    preguntaId,
    window.setTimeout(() => {
      temporizadoresGuardado.delete(preguntaId);
      encolarGuardado(preguntaId);
    }, RETARDO_AUTOSALVADO_MS),
  );
  mostrarEstadoAutosalvado('Cambios pendientes de guardar', 'guardando');
}

async function guardarPendientes() {
  temporizadoresGuardado.forEach((temporizador) => window.clearTimeout(temporizador));
  temporizadoresGuardado.clear();
  const pendientes = [...preguntasSucias];
  if (!pendientes.length) {
    return true;
  }
  const resultados = await Promise.all(pendientes.map(encolarGuardado));
  return resultados.every(Boolean);
}

async function recuperarBorradores() {
  const response = await obtenerBorradores(examen.entrega_id);
  if (!response.ok) {
    mostrarEstadoAutosalvado(response.error, 'error');
    return;
  }
  response.datos.forEach((borrador) => {
    versionesBorrador.set(borrador.pregunta_id, borrador.version);
    aplicarContenidoBorrador(borrador.pregunta_id, borrador.contenido);
  });
  actualizarContador();
  mostrarEstadoAutosalvado(
    response.datos.length ? 'Borradores recuperados del servidor' : 'Sin cambios pendientes',
  );
}

async function enviar(automatico = false) {
  if (enviando) {
    return;
  }
  enviando = true;
  formulario.querySelector('button[type="submit"]').disabled = true;
  const guardadoCorrecto = await guardarPendientes();
  if (!guardadoCorrecto && !automatico) {
    mostrarAviso('No se pudo confirmar el borrador. Revisa el aviso antes de enviar.');
    enviando = false;
    formulario.querySelector('button[type="submit"]').disabled = false;
    return;
  }
  await registrarEventoAuditoria(automatico ? 'ENVIO_TIEMPO' : 'ENVIO_MANUAL', {});

  const response = await enviarEntrega(examen.entrega_id, recopilarRespuestas(), automatico);
  if (!response.ok) {
    mostrarAviso(response.error);
    enviando = false;
    formulario.querySelector('button[type="submit"]').disabled = false;
    return;
  }
  window.clearInterval(intervaloAutosalvado);
  detenerEvidencias();
  guardarEntregaId(response.datos.entrega_id);
  window.location.href = `./resultado.html?entrega_id=${response.datos.entrega_id}`;
}

function actualizarTiempo() {
  const fin = Date.parse(examen.hora_limite_servidor);
  const ahoraServidor = Date.now() + desfaseServidorMs;
  const restante = Math.max(0, Math.ceil((fin - ahoraServidor) / 1000));
  const minutos = String(Math.floor(restante / 60)).padStart(2, '0');
  const segundos = String(restante % 60).padStart(2, '0');
  tiempoRestante.textContent = `${minutos}:${segundos}`;
  estadoExamen.textContent = restante < 300 ? 'Tramo final' : 'En curso';
  if (restante === 0) {
    window.clearInterval(intervalo);
    enviar(true);
  }
}

async function inicializarExamen() {
  titulo.textContent = examen.titulo;
  preguntasNodo.innerHTML = examen.preguntas.map(renderizarPregunta).join('');
  formulario.addEventListener('input', (event) => {
    actualizarContador();
    programarGuardado(preguntaIdDesdeControl(event.target));
  });
  formulario.addEventListener('change', (event) => {
    const preguntaId = preguntaIdDesdeControl(event.target);
    programarGuardado(preguntaId);
    encolarGuardado(preguntaId);
  });
  formulario.addEventListener('focusout', (event) => {
    const preguntaId = preguntaIdDesdeControl(event.target);
    if (preguntaId && preguntasSucias.has(preguntaId)) {
      encolarGuardado(preguntaId);
    }
  });
  formulario.addEventListener('submit', (event) => {
    event.preventDefault();
    enviar(false);
  });
  await recuperarBorradores();
  actualizarEstadoPermisos();
  reactivarPermisos.addEventListener('click', reactivarFlujos);
  window.setInterval(actualizarEstadoPermisos, 2000);
  actualizarTiempo();
  intervalo = window.setInterval(actualizarTiempo, 1000);
  intervaloAutosalvado = window.setInterval(guardarPendientes, INTERVALO_AUTOSALVADO_MS);
  document.addEventListener('visibilitychange', () => {
    if (document.hidden) {
      guardarPendientes();
    }
  });
  iniciarAuditoria(mostrarAviso);
}

if (!examen || obtenerRol() !== 'alumno') {
  window.location.href = './index.html';
} else {
  inicializarExamen();
}
