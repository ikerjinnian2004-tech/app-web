import {
  actualizarEstadoPreguntaProfesor,
  crearPreguntaProfesor,
  descargarEvidencia,
  exportarCsvProfesor,
  listarEntregasProfesor,
  listarExamenesProfesor,
  listarPreguntasProfesor,
  listarVersionesExamenProfesor,
  obtenerDetalleEntregaProfesor,
  obtenerEstadisticasProfesor,
  revisarRespuestaProfesor,
  versionarExamenProfesor,
  versionarPreguntaProfesor,
} from './api.js';
import { obtenerRol, obtenerToken } from './sesion.js';

const contenedorEntregas = document.getElementById('entregas');
const contenedorCatalogo = document.getElementById('catalogo-preguntas');
const mensaje = document.getElementById('mensaje-profesor');
const descargar = document.getElementById('descargar-csv');
const filtros = document.getElementById('filtros-preguntas');
const editor = document.getElementById('editor-pregunta');
const formulario = document.getElementById('formulario-pregunta');
const tituloEditor = document.getElementById('titulo-editor');
const listaCasos = document.getElementById('lista-casos-prueba');
const formularioConfiguracion = document.getElementById('formulario-configuracion');
const versionExamen = document.getElementById('version-examen');
const historialExamen = document.getElementById('historial-examen');
const filtrosEntregas = document.getElementById('filtros-entregas');
const estadisticasEntregas = document.getElementById('estadisticas-entregas');
const detalleEntrega = document.getElementById('detalle-entrega');
const contenidoDetalle = document.getElementById('contenido-detalle-entrega');
let preguntasActuales = [];

function escaparHtml(valor) {
  return String(valor ?? '')
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#039;');
}

function etiquetaTipo(tipo) {
  return {
    rellenar_huecos: 'Rellenar huecos',
    corregir_codigo: 'Corregir código',
    tipo_test: 'Tipo test',
    respuesta_corta: 'Respuesta corta',
  }[tipo] || tipo;
}

function fechaParaControl(iso) {
  if (!iso) {
    return '';
  }
  const fecha = new Date(iso);
  const local = new Date(fecha.getTime() - fecha.getTimezoneOffset() * 60000);
  return local.toISOString().slice(0, 16);
}

function fechaParaApi(valor) {
  return valor ? new Date(valor).toISOString() : null;
}

function mostrarConfiguracion(examen) {
  formularioConfiguracion.elements.examen_id.value = examen.id;
  formularioConfiguracion.elements.titulo.value = examen.titulo;
  formularioConfiguracion.elements.descripcion.value = examen.descripcion;
  formularioConfiguracion.elements.duracion_minutos.value = examen.duracion_segundos / 60;
  formularioConfiguracion.elements.estado.value = examen.estado;
  formularioConfiguracion.elements.modo_calificacion.value = examen.modo_calificacion;
  formularioConfiguracion.elements.apertura_en.value = fechaParaControl(examen.apertura_en);
  formularioConfiguracion.elements.cierre_en.value = fechaParaControl(examen.cierre_en);
  const seleccion = examen.seleccion_por_tipo || {};
  formularioConfiguracion.elements.cantidad_rellenar_huecos.value = seleccion.rellenar_huecos || 0;
  formularioConfiguracion.elements.cantidad_corregir_codigo.value = seleccion.corregir_codigo || 0;
  formularioConfiguracion.elements.cantidad_tipo_test.value = seleccion.tipo_test || 0;
  formularioConfiguracion.elements.cantidad_respuesta_corta.value = seleccion.respuesta_corta || 0;
  versionExamen.textContent = `Versión ${examen.version}`;
}

async function cargarHistorialExamen(examenId) {
  const response = await listarVersionesExamenProfesor(examenId);
  if (!response.ok) {
    historialExamen.textContent = response.error;
    return;
  }
  const cantidad = response.datos.length;
  historialExamen.textContent = cantidad === 1
    ? '1 versión conservada'
    : `${cantidad} versiones conservadas`;
}

async function cargarConfiguracionExamen() {
  const response = await listarExamenesProfesor();
  if (!response.ok || !response.datos.length) {
    mensaje.textContent = response.error || 'No hay ningún examen configurado.';
    return;
  }
  mostrarConfiguracion(response.datos[0]);
  await cargarHistorialExamen(response.datos[0].id);
}

function enlacesEvidencias(eventos) {
  const ids = eventos.flatMap((evento) => evento.evidencias);
  if (!ids.length) {
    return '<span class="muted">Sin evidencias</span>';
  }
  return ids
    .map((id) => `<button class="boton-secundario" type="button" data-evidencia="${id}">Evidencia ${id}</button>`)
    .join('<br>');
}

function renderizarEntregas(entregas) {
  if (!entregas.length) {
    contenedorEntregas.innerHTML = '<p class="muted">Todavía no hay entregas.</p>';
    return;
  }
  contenedorEntregas.innerHTML = `
    <table>
      <thead>
        <tr>
          <th>Alumnado</th>
          <th>Nota</th>
          <th>Estado</th>
          <th>Eventos</th>
          <th>Evidencias</th>
          <th>Detalle</th>
        </tr>
      </thead>
      <tbody>
        ${entregas.map((entrega) => `
          <tr>
            <td>${escaparHtml(entrega.alumno)}<br><span class="muted">${escaparHtml(entrega.correo)}</span></td>
            <td>${entrega.nota_global === null ? '-' : entrega.nota_global.toFixed(2)}</td>
            <td>
              <span class="${entrega.preguntas_pendientes ? 'estado-aviso' : 'estado-ok'}">
                ${entrega.preguntas_pendientes ? 'Revisión pendiente' : 'Corregida'}
              </span>
            </td>
            <td>${entrega.eventos.map((evento) => escaparHtml(evento.tipo)).join('<br>') || '-'}</td>
            <td>${enlacesEvidencias(entrega.eventos)}</td>
            <td><button class="boton-secundario" type="button" data-detalle-entrega="${entrega.entrega_id}">Ver informe</button></td>
          </tr>
        `).join('')}
      </tbody>
    </table>
  `;
}

function renderizarEstadisticas(datos) {
  estadisticasEntregas.innerHTML = `
    <div class="tarjeta-estadistica"><span>Total</span><strong>${datos.total_entregas}</strong></div>
    <div class="tarjeta-estadistica"><span>Corregidas</span><strong>${datos.corregidas}</strong></div>
    <div class="tarjeta-estadistica"><span>Pendientes</span><strong>${datos.pendientes_revision}</strong></div>
    <div class="tarjeta-estadistica"><span>Nota media</span><strong>${datos.nota_media === null ? '—' : datos.nota_media.toFixed(2)}</strong></div>
  `;
}

function casosDePregunta(pregunta) {
  if (!pregunta.casos_prueba.length) {
    return '<p class="muted">Sin casos automáticos.</p>';
  }
  return `
    <details>
      <summary>${pregunta.casos_prueba.length} casos de prueba</summary>
      ${pregunta.casos_prueba.map((caso) => `
        <div>
          <strong>${escaparHtml(caso.descripcion)}</strong>
          <span class="muted"> · ${caso.visible ? 'visible' : 'oculto'} · peso ${caso.peso}</span>
          <pre>${escaparHtml(caso.codigo_test)}</pre>
        </div>
      `).join('')}
    </details>
  `;
}

function renderizarDetalle(datos) {
  const resultados = new Map(datos.desglose.map((item) => [item.pregunta_id, item]));
  contenidoDetalle.innerHTML = `
    <p><strong>${escaparHtml(datos.alumno)}</strong> · ${escaparHtml(datos.correo)}</p>
    <p class="muted">${escaparHtml(datos.examen)} v${datos.version_examen} · ${escaparHtml(datos.modo_calificacion)}</p>
    <div class="detalle-preguntas">
      ${datos.preguntas.map((pregunta) => {
        const resultado = resultados.get(pregunta.id) || {};
        return `
          <article class="detalle-pregunta">
            <p class="tipo-pregunta">${escaparHtml(etiquetaTipo(pregunta.tipo))} · peso ${pregunta.peso} · ${escaparHtml(pregunta.clave)} v${pregunta.version}</p>
            <h3>${pregunta.orden}. ${escaparHtml(pregunta.titulo)}</h3>
            <p>${escaparHtml(pregunta.enunciado)}</p>
            <h4>Respuesta</h4>
            <pre>${escaparHtml(pregunta.respuesta || '(sin contenido)')}</pre>
            <p><strong>Resultado:</strong> ${resultado.nota === null || resultado.nota === undefined ? 'Revisión pendiente' : `${resultado.nota.toFixed(2)} / 10`}</p>
            ${casosDePregunta(pregunta)}
            ${resultado.estado === 'pendiente_revision' ? `
              <form class="formulario-revision" data-form-revision data-entrega-id="${datos.entrega_id}" data-pregunta-id="${pregunta.id}">
                <label>Nota
                  <input name="nota" type="number" min="0" max="10" step="0.1" required>
                </label>
                <label>Comentario
                  <input name="comentario" type="text" maxlength="10000">
                </label>
                <button class="boton-principal" type="submit">Guardar revisión</button>
              </form>
            ` : ''}
          </article>
        `;
      }).join('')}
    </div>
    <h3>Eventos y evidencias</h3>
    ${datos.eventos_detalle.length ? datos.eventos_detalle.map((evento) => `
      <p>${escaparHtml(evento.tipo)} · ${escaparHtml(evento.registrado_en || '')}
        ${evento.evidencias.map((evidencia) => `<button class="boton-secundario" type="button" data-evidencia="${evidencia.id}">${escaparHtml(evidencia.nombre_archivo)}</button>`).join(' ')}
      </p>
    `).join('') : '<p class="muted">Sin eventos registrados.</p>'}
  `;
  detalleEntrega.classList.remove('hidden');
  detalleEntrega.scrollIntoView({ behavior: 'smooth', block: 'start' });
}

function renderizarCatalogo(preguntas) {
  if (!preguntas.length) {
    contenedorCatalogo.innerHTML = '<p class="muted">No hay preguntas con estos filtros.</p>';
    return;
  }
  contenedorCatalogo.innerHTML = `
    <table>
      <thead>
        <tr>
          <th>Clave y versión</th>
          <th>Pregunta</th>
          <th>Tipo</th>
          <th>Peso</th>
          <th>Estado</th>
          <th>Acciones</th>
        </tr>
      </thead>
      <tbody>
        ${preguntas.map((pregunta) => `
          <tr>
            <td><strong>${escaparHtml(pregunta.clave)}</strong><br><span class="muted">v${pregunta.version}</span></td>
            <td>${escaparHtml(pregunta.titulo)}</td>
            <td>${escaparHtml(etiquetaTipo(pregunta.tipo))}</td>
            <td>${pregunta.peso}</td>
            <td><span class="${pregunta.estado === 'publicada' ? 'estado-ok' : 'estado-aviso'}">${escaparHtml(pregunta.estado)}</span></td>
            <td class="acciones-tabla">
              <button class="boton-secundario" type="button" data-editar="${pregunta.id}">Nueva versión</button>
              <button class="boton-secundario" type="button" data-estado="${pregunta.id}" data-nuevo-estado="${pregunta.estado === 'publicada' ? 'retirada' : 'publicada'}">
                ${pregunta.estado === 'publicada' ? 'Retirar' : 'Publicar'}
              </button>
            </td>
          </tr>
        `).join('')}
      </tbody>
    </table>
  `;
}

function anadirCaso(caso = {}) {
  const fila = document.createElement('div');
  fila.className = 'caso-prueba-editor';
  fila.innerHTML = `
    <label>Descripción
      <input data-caso="descripcion" type="text" maxlength="200">
    </label>
    <label>Peso
      <input data-caso="peso" type="number" min="0.1" max="100" step="0.1" value="1">
    </label>
    <label class="fila-check">Visible
      <input data-caso="visible" type="checkbox">
    </label>
    <label class="codigo-caso">Código de comprobación
      <textarea data-caso="codigo_test" maxlength="20000"></textarea>
    </label>
    <label class="codigo-caso">Salida esperada (opcional)
      <textarea data-caso="salida_esperada" maxlength="10000"></textarea>
    </label>
    <button class="boton-secundario" type="button" data-eliminar-caso>Eliminar caso</button>
  `;
  fila.querySelector('[data-caso="descripcion"]').value = caso.descripcion || '';
  fila.querySelector('[data-caso="peso"]').value = caso.peso || 1;
  fila.querySelector('[data-caso="visible"]').checked = Boolean(caso.visible);
  fila.querySelector('[data-caso="codigo_test"]').value = caso.codigo_test || '';
  fila.querySelector('[data-caso="salida_esperada"]').value = caso.salida_esperada || '';
  listaCasos.appendChild(fila);
}

function abrirEditor(pregunta = null) {
  formulario.reset();
  listaCasos.replaceChildren();
  formulario.elements.examen_id.disabled = Boolean(pregunta);
  formulario.elements.clave.disabled = Boolean(pregunta);
  formulario.elements.pregunta_id.value = pregunta?.id || '';
  tituloEditor.textContent = pregunta ? `Nueva versión de ${pregunta.clave}` : 'Nueva pregunta';

  if (pregunta) {
    formulario.elements.examen_id.value = pregunta.examen_id;
    formulario.elements.clave.value = pregunta.clave;
    formulario.elements.tipo.value = pregunta.tipo;
    formulario.elements.estado.value = pregunta.estado === 'retirada' ? 'borrador' : pregunta.estado;
    formulario.elements.orden.value = pregunta.orden;
    formulario.elements.peso.value = pregunta.peso;
    formulario.elements.titulo.value = pregunta.titulo;
    formulario.elements.enunciado.value = pregunta.enunciado;
    formulario.elements.codigo_plantilla.value = pregunta.codigo_plantilla || '';
    formulario.elements.codigo_solucion.value = pregunta.codigo_solucion || '';
    formulario.elements.opciones.value = (pregunta.opciones || []).join('\n');
    formulario.elements.respuesta_correcta.value = pregunta.respuesta_correcta || '';
    formulario.elements.limites_caracteres.value = (pregunta.limites_caracteres || []).join(', ');
    pregunta.casos_prueba.forEach(anadirCaso);
  } else {
    formulario.elements.examen_id.value = 1;
    formulario.elements.orden.value = 1;
    formulario.elements.peso.value = 1;
    formulario.elements.estado.value = 'borrador';
  }
  editor.classList.remove('hidden');
  editor.scrollIntoView({ behavior: 'smooth', block: 'start' });
}

function casosDelFormulario() {
  return [...listaCasos.querySelectorAll('.caso-prueba-editor')]
    .map((fila) => ({
      descripcion: fila.querySelector('[data-caso="descripcion"]').value.trim(),
      codigo_test: fila.querySelector('[data-caso="codigo_test"]').value.trim(),
      salida_esperada: fila.querySelector('[data-caso="salida_esperada"]').value,
      peso: Number(fila.querySelector('[data-caso="peso"]').value),
      visible: fila.querySelector('[data-caso="visible"]').checked,
    }))
    .filter((caso) => caso.descripcion || caso.codigo_test);
}

function datosDelFormulario() {
  const opciones = formulario.elements.opciones.value
    .split('\n')
    .map((opcion) => opcion.trim())
    .filter(Boolean);
  const limites = formulario.elements.limites_caracteres.value
    .split(',')
    .map((limite) => limite.trim())
    .filter(Boolean)
    .map(Number);
  return {
    examen_id: Number(formulario.elements.examen_id.value),
    clave: formulario.elements.clave.value.trim(),
    tipo: formulario.elements.tipo.value,
    titulo: formulario.elements.titulo.value.trim(),
    enunciado: formulario.elements.enunciado.value.trim(),
    codigo_plantilla: formulario.elements.codigo_plantilla.value.trim() || null,
    codigo_solucion: formulario.elements.codigo_solucion.value.trim() || null,
    opciones: opciones.length ? opciones : null,
    respuesta_correcta: formulario.elements.respuesta_correcta.value.trim() || null,
    limites_caracteres: limites.length ? limites : null,
    orden: Number(formulario.elements.orden.value),
    peso: Number(formulario.elements.peso.value),
    estado: formulario.elements.estado.value,
    casos_prueba: casosDelFormulario(),
  };
}

function filtrosEntregaActuales() {
  return {
    correo: filtrosEntregas?.elements.correo.value.trim() || '',
    estado: filtrosEntregas?.elements.estado.value || '',
  };
}

async function cargarEntregas() {
  const response = await listarEntregasProfesor(filtrosEntregaActuales());
  if (!response.ok) {
    mensaje.textContent = response.error;
    return;
  }
  renderizarEntregas(response.datos);
}

async function cargarEstadisticas() {
  const response = await obtenerEstadisticasProfesor();
  if (!response.ok) {
    mensaje.textContent = response.error;
    return;
  }
  renderizarEstadisticas(response.datos);
}

async function cargarDetalleEntrega(entregaId) {
  const response = await obtenerDetalleEntregaProfesor(entregaId);
  if (!response.ok) {
    mensaje.textContent = response.error;
    return;
  }
  renderizarDetalle(response.datos);
}

async function cargarPreguntas() {
  const response = await listarPreguntasProfesor({
    tipo: filtros.elements.tipo.value,
    estado: filtros.elements.estado.value,
  });
  if (!response.ok) {
    mensaje.textContent = response.error;
    return;
  }
  preguntasActuales = response.datos;
  renderizarCatalogo(preguntasActuales);
}

filtros?.addEventListener('submit', (event) => {
  event.preventDefault();
  cargarPreguntas();
});

filtrosEntregas?.addEventListener('submit', (event) => {
  event.preventDefault();
  cargarEntregas();
});

document.getElementById('nueva-pregunta')?.addEventListener('click', () => abrirEditor());
document.getElementById('cerrar-editor')?.addEventListener('click', () => editor.classList.add('hidden'));
document.getElementById('anadir-caso')?.addEventListener('click', () => anadirCaso());
document.getElementById('cerrar-detalle-entrega')?.addEventListener('click', () => detalleEntrega.classList.add('hidden'));

listaCasos?.addEventListener('click', (event) => {
  const boton = event.target.closest('[data-eliminar-caso]');
  boton?.closest('.caso-prueba-editor').remove();
});

formulario?.addEventListener('submit', async (event) => {
  event.preventDefault();
  mensaje.textContent = '';
  const preguntaId = formulario.elements.pregunta_id.value;
  const datos = datosDelFormulario();
  let response;
  if (preguntaId) {
    delete datos.examen_id;
    delete datos.clave;
    response = await versionarPreguntaProfesor(preguntaId, datos);
  } else {
    response = await crearPreguntaProfesor(datos);
  }
  if (!response.ok) {
    mensaje.textContent = response.error;
    return;
  }
  mensaje.textContent = `Pregunta ${response.datos.clave} v${response.datos.version} guardada.`;
  editor.classList.add('hidden');
  await cargarPreguntas();
});

formularioConfiguracion?.addEventListener('submit', async (event) => {
  event.preventDefault();
  mensaje.textContent = '';
  const examenId = Number(formularioConfiguracion.elements.examen_id.value);
  const datos = {
    titulo: formularioConfiguracion.elements.titulo.value.trim(),
    descripcion: formularioConfiguracion.elements.descripcion.value.trim(),
    duracion_segundos: Math.round(Number(formularioConfiguracion.elements.duracion_minutos.value) * 60),
    estado: formularioConfiguracion.elements.estado.value,
    modo_calificacion: formularioConfiguracion.elements.modo_calificacion.value,
    seleccion_por_tipo: {
      rellenar_huecos: Number(formularioConfiguracion.elements.cantidad_rellenar_huecos.value),
      corregir_codigo: Number(formularioConfiguracion.elements.cantidad_corregir_codigo.value),
      tipo_test: Number(formularioConfiguracion.elements.cantidad_tipo_test.value),
      respuesta_corta: Number(formularioConfiguracion.elements.cantidad_respuesta_corta.value),
    },
    apertura_en: fechaParaApi(formularioConfiguracion.elements.apertura_en.value),
    cierre_en: fechaParaApi(formularioConfiguracion.elements.cierre_en.value),
  };
  const response = await versionarExamenProfesor(examenId, datos);
  if (!response.ok) {
    mensaje.textContent = response.error;
    return;
  }
  mostrarConfiguracion(response.datos);
  await cargarHistorialExamen(examenId);
  mensaje.textContent = `Configuración v${response.datos.version} guardada.`;
});

contenedorCatalogo?.addEventListener('click', async (event) => {
  const botonEditar = event.target.closest('[data-editar]');
  if (botonEditar) {
    const pregunta = preguntasActuales.find((item) => item.id === Number(botonEditar.dataset.editar));
    if (pregunta) {
      abrirEditor(pregunta);
    }
    return;
  }
  const botonEstado = event.target.closest('[data-estado]');
  if (!botonEstado) {
    return;
  }
  const response = await actualizarEstadoPreguntaProfesor(
    botonEstado.dataset.estado,
    botonEstado.dataset.nuevoEstado,
  );
  if (!response.ok) {
    mensaje.textContent = response.error;
    return;
  }
  mensaje.textContent = `La pregunta queda ${response.datos.estado}.`;
  await cargarPreguntas();
});

descargar?.addEventListener('click', async () => {
  const response = await exportarCsvProfesor(filtrosEntregaActuales());
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

contenedorEntregas?.addEventListener('click', async (event) => {
  const botonDetalle = event.target.closest('[data-detalle-entrega]');
  if (botonDetalle) {
    await cargarDetalleEntrega(botonDetalle.dataset.detalleEntrega);
    return;
  }
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

contenidoDetalle?.addEventListener('submit', async (event) => {
  const formularioRevision = event.target.closest('[data-form-revision]');
  if (!formularioRevision) {
    return;
  }
  event.preventDefault();
  const response = await revisarRespuestaProfesor(
    formularioRevision.dataset.entregaId,
    formularioRevision.dataset.preguntaId,
    Number(formularioRevision.elements.nota.value),
    formularioRevision.elements.comentario.value.trim(),
  );
  if (!response.ok) {
    mensaje.textContent = response.error;
    return;
  }
  mensaje.textContent = `Revisión guardada. Nota global: ${response.datos.nota_global.toFixed(2)}.`;
  await cargarDetalleEntrega(formularioRevision.dataset.entregaId);
  await cargarEntregas();
  await cargarEstadisticas();
});

contenidoDetalle?.addEventListener('click', async (event) => {
  const boton = event.target.closest('[data-evidencia]');
  if (!boton) {
    return;
  }
  const response = await descargarEvidencia(boton.dataset.evidencia);
  if (!response.ok) {
    mensaje.textContent = response.error;
    return;
  }
  const url = URL.createObjectURL(response.blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = `evidencia-${boton.dataset.evidencia}.webm`;
  link.click();
  URL.revokeObjectURL(url);
});

if (!obtenerToken() || obtenerRol() !== 'profesor') {
  window.location.href = './index.html';
} else {
  cargarConfiguracionExamen();
  cargarPreguntas();
  cargarEntregas();
  cargarEstadisticas();
}
