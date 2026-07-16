import { obtenerToken } from './sesion.js';

const API_BASE_URL = window.API_BASE_URL || `http://${window.location.hostname || '127.0.0.1'}:8000`;

async function leerRespuesta(response) {
  const contentType = response.headers.get('content-type') || '';
  if (contentType.includes('application/json')) {
    return response.json();
  }
  return response.text();
}

export async function peticionApi(ruta, opciones = {}) {
  const headers = new Headers(opciones.headers || {});
  const token = obtenerToken();

  if (token && !headers.has('Authorization')) {
    headers.set('Authorization', `Bearer ${token}`);
  }

  if (opciones.body && !(opciones.body instanceof FormData) && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json');
  }

  try {
    const response = await fetch(`${API_BASE_URL}${ruta}`, { ...opciones, headers });
    const datos = await leerRespuesta(response);
    if (response.ok) {
      return { ok: true, status: response.status, datos, error: null };
    }
    return {
      ok: false,
      status: response.status,
      datos,
      error: datos?.detail || 'No se pudo completar la operacion.',
    };
  } catch {
    return { ok: false, status: 0, datos: null, error: 'No se pudo contactar con el servidor.' };
  }
}

export function obtenerConsentimiento() {
  return peticionApi('/consentimiento');
}

export function acceder(rol, correoInstitucional) {
  return peticionApi('/auth/acceder', {
    method: 'POST',
    body: JSON.stringify({ rol, correo_institucional: correoInstitucional }),
  });
}

export function iniciarExamen(consentimientoVersion, aceptaGrabacion, permisosVerificados) {
  return peticionApi('/examen/iniciar', {
    method: 'POST',
    body: JSON.stringify({
      consentimiento_version: consentimientoVersion,
      acepta_grabacion: aceptaGrabacion,
      permisos_evidencia_verificados: permisosVerificados,
    }),
  });
}

export function enviarEntrega(entregaId, respuestas, entregadoAutomaticamente = false) {
  return peticionApi('/entregas/enviar', {
    method: 'POST',
    body: JSON.stringify({
      entrega_id: entregaId,
      respuestas,
      entregado_automaticamente: entregadoAutomaticamente,
    }),
  });
}

export function obtenerResultado(entregaId) {
  return peticionApi(`/entregas/${entregaId}/resultado`);
}

export function registrarEventoAuditoria(tipo, metadata = {}) {
  return peticionApi('/auditoria/eventos', {
    method: 'POST',
    body: JSON.stringify({
      tipo,
      timestamp_cliente: new Date().toISOString(),
      metadata,
    }),
  });
}

export function subirEvidencia(formData) {
  return peticionApi('/auditoria/evidencias', {
    method: 'POST',
    body: formData,
  });
}

function consultaProfesor(filtros = {}) {
  const parametros = new URLSearchParams();
  Object.entries(filtros).forEach(([clave, valor]) => {
    if (valor !== undefined && valor !== null && valor !== '') {
      parametros.set(clave, valor);
    }
  });
  return parametros.size ? `?${parametros.toString()}` : '';
}

export function listarEntregasProfesor(filtros = {}) {
  return peticionApi(`/profesor/entregas${consultaProfesor(filtros)}`);
}

export function obtenerDetalleEntregaProfesor(entregaId) {
  return peticionApi(`/profesor/entregas/${entregaId}`);
}

export function obtenerEstadisticasProfesor() {
  return peticionApi('/profesor/estadisticas');
}

export function revisarRespuestaProfesor(entregaId, preguntaId, nota, comentario) {
  return peticionApi(`/profesor/entregas/${entregaId}/revisiones/${preguntaId}`, {
    method: 'POST',
    body: JSON.stringify({ nota, comentario }),
  });
}

export function listarExamenesProfesor() {
  return peticionApi('/profesor/examenes');
}

export function listarVersionesExamenProfesor(examenId) {
  return peticionApi(`/profesor/examenes/${examenId}/versiones`);
}

export function versionarExamenProfesor(examenId, datos) {
  return peticionApi(`/profesor/examenes/${examenId}/versiones`, {
    method: 'POST',
    body: JSON.stringify(datos),
  });
}

export function listarPreguntasProfesor(filtros = {}) {
  const parametros = new URLSearchParams();
  if (filtros.tipo) {
    parametros.set('tipo', filtros.tipo);
  }
  if (filtros.estado) {
    parametros.set('estado', filtros.estado);
  }
  const consulta = parametros.size ? `?${parametros.toString()}` : '';
  return peticionApi(`/profesor/preguntas${consulta}`);
}

export function crearPreguntaProfesor(datos) {
  return peticionApi('/profesor/preguntas', {
    method: 'POST',
    body: JSON.stringify(datos),
  });
}

export function versionarPreguntaProfesor(preguntaId, datos) {
  return peticionApi(`/profesor/preguntas/${preguntaId}/versiones`, {
    method: 'POST',
    body: JSON.stringify(datos),
  });
}

export function actualizarEstadoPreguntaProfesor(preguntaId, estado) {
  return peticionApi(`/profesor/preguntas/${preguntaId}/estado`, {
    method: 'POST',
    body: JSON.stringify({ estado }),
  });
}

export function exportarCsvProfesor(filtros = {}) {
  return peticionApi(`/profesor/exportar${consultaProfesor(filtros)}`);
}

export async function descargarEvidencia(evidenciaId) {
  const headers = new Headers();
  const token = obtenerToken();
  if (token) {
    headers.set('Authorization', `Bearer ${token}`);
  }
  const response = await fetch(`${API_BASE_URL}/profesor/evidencias/${evidenciaId}`, { headers });
  if (!response.ok) {
    return { ok: false, error: 'No se pudo descargar la evidencia.' };
  }
  return { ok: true, blob: await response.blob() };
}
