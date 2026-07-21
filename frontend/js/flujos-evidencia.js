let flujoPantalla = null;
let flujoCamaraAudio = null;

function detenerFlujo(flujo) {
  flujo?.getTracks().forEach((pista) => pista.stop());
}

function flujoActivo(flujo) {
  return Boolean(flujo) && flujo.getTracks().some((pista) => pista.readyState === 'live');
}

function vigilarFin(flujo, limpiar) {
  flujo?.getTracks().forEach((pista) => {
    pista.addEventListener('ended', limpiar, { once: true });
  });
}

export function evidenciasActivas() {
  return flujoActivo(flujoPantalla)
    && flujoPantalla.getVideoTracks().some((pista) => pista.readyState === 'live')
    && flujoActivo(flujoCamaraAudio)
    && flujoCamaraAudio.getVideoTracks().some((pista) => pista.readyState === 'live')
    && flujoCamaraAudio.getAudioTracks().some((pista) => pista.readyState === 'live');
}

export function construirFlujoEvidencia() {
  if (!evidenciasActivas()) {
    return null;
  }
  return new MediaStream([
    ...flujoPantalla.getTracks().filter((pista) => pista.readyState === 'live'),
    ...flujoCamaraAudio.getTracks().filter((pista) => pista.readyState === 'live'),
  ]);
}

export async function activarEvidencias(dispositivoCamara = '') {
  if (!navigator.mediaDevices?.getDisplayMedia || !navigator.mediaDevices?.getUserMedia) {
    throw new Error('El navegador no permite capturar pantalla, camara y microfono.');
  }
  detenerEvidencias();
  try {
    flujoPantalla = await navigator.mediaDevices.getDisplayMedia({
      video: true,
      audio: true,
    });
    flujoCamaraAudio = await navigator.mediaDevices.getUserMedia({
      video: dispositivoCamara
        ? { deviceId: { exact: dispositivoCamara } }
        : { facingMode: 'user' },
      audio: true,
    });
    if (!evidenciasActivas()) {
      throw new Error('Falta algun flujo obligatorio de pantalla, camara o microfono.');
    }
    vigilarFin(flujoPantalla, () => { flujoPantalla = null; });
    vigilarFin(flujoCamaraAudio, () => { flujoCamaraAudio = null; });
    return true;
  } catch (error) {
    detenerEvidencias();
    throw error;
  }
}

export async function listarCamaras() {
  if (!navigator.mediaDevices?.enumerateDevices) {
    return [];
  }
  const dispositivos = await navigator.mediaDevices.enumerateDevices();
  return dispositivos
    .filter((dispositivo) => dispositivo.kind === 'videoinput')
    .map((dispositivo, indice) => ({
      id: dispositivo.deviceId,
      etiqueta: dispositivo.label || `Camara ${indice + 1}`,
    }));
}

export function detenerEvidencias() {
  detenerFlujo(flujoPantalla);
  detenerFlujo(flujoCamaraAudio);
  flujoPantalla = null;
  flujoCamaraAudio = null;
}
