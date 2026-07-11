import { registrarEventoAuditoria, subirEvidencia } from './api.js';

const DURACION_EVIDENCIA_MS = 15000;
let grabando = false;

function detenerPistas(stream) {
  stream.getTracks().forEach((track) => track.stop());
}

async function construirStreamEvidencia() {
  const pantalla = await navigator.mediaDevices.getDisplayMedia({ video: true, audio: true });
  const camaraAudio = await navigator.mediaDevices.getUserMedia({ video: true, audio: true });
  const pistas = [...pantalla.getTracks(), ...camaraAudio.getTracks()];
  return new MediaStream(pistas);
}

async function enviarBlob(eventoId, blob) {
  const formData = new FormData();
  formData.append('evento_id', String(eventoId));
  formData.append('tipo', 'pantalla_camara_audio');
  formData.append('mime_type', blob.type || 'video/webm');
  formData.append('archivo', blob, `evidencia-${eventoId}.webm`);
  await subirEvidencia(formData);
}

async function grabarEvidencia(eventoId, avisar) {
  if (grabando || !navigator.mediaDevices || !window.MediaRecorder) {
    return;
  }

  grabando = true;
  let stream;
  try {
    stream = await construirStreamEvidencia();
    const fragmentos = [];
    const recorder = new MediaRecorder(stream, { mimeType: 'video/webm' });
    recorder.addEventListener('dataavailable', (event) => {
      if (event.data.size > 0) {
        fragmentos.push(event.data);
      }
    });
    recorder.addEventListener('stop', () => {
      const blob = new Blob(fragmentos, { type: 'video/webm' });
      enviarBlob(eventoId, blob).finally(() => {
        detenerPistas(stream);
        grabando = false;
        avisar('Evidencia adjuntada al evento de auditoria.');
      });
    });
    recorder.start();
    avisar('Grabando evidencia breve asociada al evento.');
    window.setTimeout(() => recorder.stop(), DURACION_EVIDENCIA_MS);
  } catch {
    if (stream) {
      detenerPistas(stream);
    }
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
