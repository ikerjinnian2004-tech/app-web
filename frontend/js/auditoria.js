import { registrarEventoAuditoria, subirEvidencia } from './api.js';
import { construirFlujoEvidencia } from './flujos-evidencia.js';

const DURACION_EVIDENCIA_MS = 14000;
let grabando = false;

function mimeGrabacionSoportado() {
  const candidatos = [
    'video/webm;codecs=vp9,opus',
    'video/webm;codecs=vp8,opus',
    'video/webm',
  ];
  return candidatos.find((mime) => MediaRecorder.isTypeSupported(mime)) || '';
}

async function enviarBlob(eventoId, blob, duracionMs) {
  const formData = new FormData();
  formData.append('evento_id', String(eventoId));
  formData.append('tipo', 'pantalla_camara_audio');
  formData.append('mime_type', (blob.type || 'video/webm').split(';')[0]);
  formData.append('duracion_ms', String(duracionMs));
  formData.append('archivo', blob, `evidencia-${eventoId}.webm`);
  return subirEvidencia(formData);
}

async function grabarEvidencia(eventoId, avisar) {
  if (grabando || !navigator.mediaDevices || !window.MediaRecorder) {
    return;
  }

  grabando = true;
  let stream;
  try {
    stream = construirFlujoEvidencia();
    if (!stream) {
      throw new Error('Los flujos de evidencia ya no estan activos.');
    }
    const fragmentos = [];
    const inicioGrabacion = performance.now();
    const mimeType = mimeGrabacionSoportado();
    const recorder = mimeType
      ? new MediaRecorder(stream, { mimeType })
      : new MediaRecorder(stream);
    recorder.addEventListener('dataavailable', (event) => {
      if (event.data.size > 0) {
        fragmentos.push(event.data);
      }
    });
    recorder.addEventListener('stop', () => {
      const blob = new Blob(fragmentos, { type: recorder.mimeType || 'video/webm' });
      const duracionMs = Math.max(1, Math.round(performance.now() - inicioGrabacion));
      enviarBlob(eventoId, blob, duracionMs)
        .then((response) => {
          avisar(response.ok
            ? 'Evidencia adjuntada al evento de auditoria.'
            : 'El evento se registro, pero la evidencia fue rechazada.');
        })
        .finally(() => {
          grabando = false;
        });
    });
    recorder.start();
    avisar('Grabando evidencia breve asociada al evento.');
    window.setTimeout(() => recorder.stop(), DURACION_EVIDENCIA_MS);
  } catch {
    grabando = false;
    await registrarEventoAuditoria('EVIDENCIA_DENEGADA', { evento_origen_id: eventoId });
    avisar('Evento registrado sin evidencia adjunta.');
  }
}

async function registrar(tipo, metadata, avisar) {
  const response = await registrarEventoAuditoria(tipo, metadata);
  if (!response.ok) {
    return;
  }
  avisar(`Evento registrado: ${tipo}.`);
  if (response.datos.grabar_evidencia) {
    await grabarEvidencia(response.datos.evento_id, avisar);
  }
}

export function iniciarAuditoria(avisar) {
  document.addEventListener('visibilitychange', () => {
    if (document.hidden) {
      registrar('CAMBIO_PESTANA', { origen: 'visibilitychange' }, avisar);
    }
  });
  window.addEventListener('blur', () => {
    registrar('PERDIDA_FOCO', { origen: 'blur' }, avisar);
  });
  window.addEventListener('focus', () => {
    registrar('VENTANA_RECUPERADA', { origen: 'focus' }, avisar);
  });
}
