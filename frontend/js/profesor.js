import { descargarEvidencia, exportarCsvProfesor, listarEntregasProfesor } from './api.js';
import { obtenerRol, obtenerToken } from './sesion.js';

const contenedor = document.getElementById('entregas');
const mensaje = document.getElementById('mensaje-profesor');
const descargar = document.getElementById('descargar-csv');

function enlacesEvidencias(eventos) {
  const ids = eventos.flatMap((evento) => evento.evidencias);
  if (!ids.length) {
    return '<span class="muted">Sin evidencias</span>';
  }
  return ids
    .map((id) => `<button class="boton-secundario" type="button" data-evidencia="${id}">Evidencia ${id}</button>`)
    .join('<br>');
}

function renderizarTabla(entregas) {
  if (!entregas.length) {
    contenedor.innerHTML = '<p class="muted">Todavia no hay entregas.</p>';
    return;
  }
  contenedor.innerHTML = `
    <table>
      <thead>
        <tr>
          <th>Alumno</th>
          <th>Nota</th>
          <th>Estado</th>
          <th>Eventos</th>
          <th>Evidencias</th>
        </tr>
      </thead>
      <tbody>
        ${entregas.map((entrega) => `
          <tr>
            <td>${entrega.alumno}<br><span class="muted">${entrega.correo}</span></td>
            <td>${entrega.nota_global === null ? '-' : entrega.nota_global.toFixed(2)}</td>
            <td>
              <span class="${entrega.preguntas_pendientes ? 'estado-aviso' : 'estado-ok'}">
                ${entrega.preguntas_pendientes ? 'Revision pendiente' : 'Corregida'}
              </span>
            </td>
            <td>${entrega.eventos.map((evento) => evento.tipo).join('<br>') || '-'}</td>
            <td>${enlacesEvidencias(entrega.eventos)}</td>
          </tr>
        `).join('')}
      </tbody>
    </table>
  `;
}

async function cargarEntregas() {
  const response = await listarEntregasProfesor();
  if (!response.ok) {
    mensaje.textContent = response.error;
    return;
  }
  renderizarTabla(response.datos);
}

descargar?.addEventListener('click', async () => {
  const response = await exportarCsvProfesor();
  if (!response.ok) {
    mensaje.textContent = response.error;
    return;
  }
  const blob = new Blob([response.datos], { type: 'text/csv;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = 'entregas_tfg.csv';
  link.click();
  URL.revokeObjectURL(url);
});

contenedor?.addEventListener('click', async (event) => {
  const boton = event.target.closest('[data-evidencia]');
  if (!boton) {
    return;
  }
  const evidenciaId = boton.dataset.evidencia;
  const response = await descargarEvidencia(evidenciaId);
  if (!response.ok) {
    mensaje.textContent = response.error;
    return;
  }
  const url = URL.createObjectURL(response.blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = `evidencia-${evidenciaId}.webm`;
  link.click();
  URL.revokeObjectURL(url);
});

if (!obtenerToken() || obtenerRol() !== 'profesor') {
  window.location.href = './index.html';
} else {
  cargarEntregas();
}
