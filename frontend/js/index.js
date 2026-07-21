import { acceder, iniciarExamen, obtenerConsentimiento } from './api.js';
import { activarEvidencias, listarCamaras } from './flujos-evidencia.js';
import { guardarExamen, guardarSesion, limpiarSesion } from './sesion.js';

const formulario = document.getElementById('formulario-acceso');
const mensaje = document.getElementById('mensaje-acceso');
const bloqueConsentimiento = document.getElementById('bloque-consentimiento');
const textoConsentimiento = document.getElementById('texto-consentimiento');
const aceptaGrabacion = document.getElementById('acepta-grabacion');
const selectorCamara = document.getElementById('selector-camara');
let consentimientoVersion = '';

async function verificarPermisosEvidencia() {
  try {
    await activarEvidencias(selectorCamara.value);
    await cargarCamaras();
    return true;
  } catch {
    return false;
  }
}

async function cargarCamaras() {
  const seleccion = selectorCamara.value;
  const camaras = await listarCamaras();
  selectorCamara.innerHTML = '<option value="">Camara predeterminada</option>';
  camaras.forEach((camara) => {
    const opcion = document.createElement('option');
    opcion.value = camara.id;
    opcion.textContent = camara.etiqueta;
    opcion.selected = camara.id === seleccion;
    selectorCamara.append(opcion);
  });
}

async function mostrarExamenSinCerrarFlujos() {
  const response = await fetch('./examen.html', { cache: 'no-store' });
  if (!response.ok) {
    throw new Error('No se pudo abrir la pantalla del examen.');
  }
  const documento = new DOMParser().parseFromString(await response.text(), 'text/html');
  document.title = documento.title;
  document.body.innerHTML = documento.body.innerHTML;
  window.history.pushState({}, '', './examen.html');
  await import('./examen.js');
}

function rolSeleccionado() {
  return formulario.elements.rol.value;
}

function actualizarConsentimiento() {
  bloqueConsentimiento.classList.toggle('hidden', rolSeleccionado() !== 'alumno');
}

async function cargarConsentimiento() {
  const response = await obtenerConsentimiento();
  if (!response.ok) {
    textoConsentimiento.textContent = 'No se pudo cargar el consentimiento.';
    return;
  }
  consentimientoVersion = response.datos.version;
  textoConsentimiento.textContent = response.datos.texto;
}

formulario?.addEventListener('change', actualizarConsentimiento);

formulario?.addEventListener('submit', async (event) => {
  event.preventDefault();
  mensaje.textContent = '';

  const rol = rolSeleccionado();
  const correo = String(formulario.elements.correo.value || '').trim().toLowerCase();
  if (!correo) {
    mensaje.textContent = 'Indica el correo institucional.';
    return;
  }
  if (rol === 'alumno' && !aceptaGrabacion.checked) {
    mensaje.textContent = 'Debes aceptar el consentimiento para empezar.';
    return;
  }

  let permisosEvidenciaVerificados = false;
  if (rol === 'alumno') {
    mensaje.textContent = 'Comprueba los permisos de pantalla, cámara y micrófono.';
    permisosEvidenciaVerificados = await verificarPermisosEvidencia();
    if (!permisosEvidenciaVerificados) {
      mensaje.textContent = 'Debes conceder pantalla, cámara y micrófono para iniciar el examen.';
      return;
    }
  }

  limpiarSesion();
  const acceso = await acceder(rol, correo);
  if (!acceso.ok) {
    mensaje.textContent = acceso.error;
    return;
  }

  guardarSesion(acceso.datos);
  if (rol === 'profesor') {
    window.location.href = './profesor.html';
    return;
  }

  const examen = await iniciarExamen(
    consentimientoVersion,
    aceptaGrabacion.checked,
    permisosEvidenciaVerificados,
  );
  if (!examen.ok) {
    mensaje.textContent = examen.error;
    return;
  }
  guardarExamen(examen.datos);
  try {
    await mostrarExamenSinCerrarFlujos();
  } catch (error) {
    mensaje.textContent = error.message;
  }
});

actualizarConsentimiento();
cargarConsentimiento();
cargarCamaras();
