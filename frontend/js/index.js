import { acceder, iniciarExamen, obtenerConsentimiento } from './api.js';
import { guardarExamen, guardarSesion, limpiarSesion } from './sesion.js';

const formulario = document.getElementById('formulario-acceso');
const mensaje = document.getElementById('mensaje-acceso');
const bloqueConsentimiento = document.getElementById('bloque-consentimiento');
const textoConsentimiento = document.getElementById('texto-consentimiento');
const aceptaGrabacion = document.getElementById('acepta-grabacion');
let consentimientoVersion = '';

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

  const examen = await iniciarExamen(consentimientoVersion, aceptaGrabacion.checked);
  if (!examen.ok) {
    mensaje.textContent = examen.error;
    return;
  }
  guardarExamen(examen.datos);
  window.location.href = './examen.html';
});

actualizarConsentimiento();
cargarConsentimiento();
