import { obtenerResultado } from './api.js';
import { obtenerEntregaId } from './sesion.js';

const resultadoNodo = document.getElementById('resultado');
const mensaje = document.getElementById('mensaje-resultado');
const params = new URLSearchParams(window.location.search);
const entregaId = params.get('entrega_id') || obtenerEntregaId();

function filaPregunta(item) {
  const nota = item.nota === null ? 'Pendiente' : item.nota.toFixed(2);
  return `<li>${item.tipo}: ${nota} (${item.estado})</li>`;
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
    <p class="muted">${resultado.preguntas_pendientes} preguntas pendientes de revision docente.</p>
    <ul>${resultado.desglose.map(filaPregunta).join('')}</ul>
  `;
}

cargarResultado();
