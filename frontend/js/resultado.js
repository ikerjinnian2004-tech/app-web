import { obtenerResultado } from './api.js';
import { obtenerEntregaId } from './sesion.js';

const resultadoNodo = document.getElementById('resultado');
const mensaje = document.getElementById('mensaje-resultado');
const params = new URLSearchParams(window.location.search);
const entregaId = params.get('entrega_id') || obtenerEntregaId();

function filaPregunta(item) {
  const tipos = {
    rellenar_huecos: 'Rellenar huecos',
    corregir_codigo: 'Corregir código',
    tipo_test: 'Tipo test',
    respuesta_corta: 'Respuesta corta',
  };
  const nota = item.nota === null ? 'Pendiente' : item.nota.toFixed(2);
  const contribucion = item.contribucion === null ? '' : ` · nota × peso ${item.contribucion.toFixed(2)}`;
  return `<li><strong>${tipos[item.tipo] || item.tipo}</strong>: ${nota} / 10 · peso ${item.peso}${contribucion}</li>`;
}

async function cargarResultado() {
  if (!entregaId) {
    mensaje.textContent = 'No hay entrega seleccionada.';
    return;
  }
  const response = await obtenerResultado(entregaId);
  if (!response.ok) {
    mensaje.textContent = response.error;
    return;
  }
  const resultado = response.datos;
  resultadoNodo.innerHTML = `
    <p class="nota-final">${resultado.nota_global.toFixed(2)} / 10</p>
    <p class="muted">${resultado.preguntas_pendientes === 1
      ? '1 pregunta pendiente de revisión docente.'
      : `${resultado.preguntas_pendientes} preguntas pendientes de revisión docente.`}</p>
    <ul>${resultado.desglose.map(filaPregunta).join('')}</ul>
  `;
}

cargarResultado();
