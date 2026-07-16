import { enviarEntrega, registrarEventoAuditoria } from './api.js';
import { iniciarAuditoria } from './auditoria.js';
import { guardarEntregaId, obtenerExamen, obtenerRol } from './sesion.js';

const examen = obtenerExamen();
const formulario = document.getElementById('formulario-examen');
const preguntasNodo = document.getElementById('preguntas');
const titulo = document.getElementById('titulo-examen');
const tiempoRestante = document.getElementById('tiempo-restante');
const estadoExamen = document.getElementById('estado-examen');
const contador = document.getElementById('contador-respuestas');
const aviso = document.getElementById('aviso-auditoria');
let enviando = false;
let intervalo = null;
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

async function enviar(automatico = false) {
  if (enviando) {
    return;
  }
  enviando = true;
  formulario.querySelector('button[type="submit"]').disabled = true;
  await registrarEventoAuditoria(automatico ? 'ENVIO_TIEMPO' : 'ENVIO_MANUAL', {});

  const response = await enviarEntrega(examen.entrega_id, recopilarRespuestas(), automatico);
  if (!response.ok) {
    mostrarAviso(response.error);
    enviando = false;
    formulario.querySelector('button[type="submit"]').disabled = false;
    return;
  }
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

if (!examen || obtenerRol() !== 'alumno') {
  window.location.href = './index.html';
} else {
  titulo.textContent = examen.titulo;
  preguntasNodo.innerHTML = examen.preguntas.map(renderizarPregunta).join('');
  formulario.addEventListener('input', actualizarContador);
  formulario.addEventListener('submit', (event) => {
    event.preventDefault();
    enviar(false);
  });
  actualizarContador();
  actualizarTiempo();
  intervalo = window.setInterval(actualizarTiempo, 1000);
  iniciarAuditoria(mostrarAviso);
}
