const CLAVES = {
  TOKEN: 'tfg_token',
  ROL: 'tfg_rol',
  NOMBRE: 'tfg_nombre',
  EXAMEN: 'tfg_examen',
  ENTREGA_ID: 'tfg_entrega_id',
};

export function guardarSesion({ token, rol, nombre }) {
  sessionStorage.setItem(CLAVES.TOKEN, token);
  sessionStorage.setItem(CLAVES.ROL, rol);
  sessionStorage.setItem(CLAVES.NOMBRE, nombre);
}

export function obtenerToken() {
  return sessionStorage.getItem(CLAVES.TOKEN);
}

export function obtenerRol() {
  return sessionStorage.getItem(CLAVES.ROL);
}

export function guardarExamen(examen) {
  sessionStorage.setItem(CLAVES.EXAMEN, JSON.stringify(examen));
  sessionStorage.setItem(CLAVES.ENTREGA_ID, String(examen.entrega_id));
}

export function obtenerExamen() {
  const raw = sessionStorage.getItem(CLAVES.EXAMEN);
  return raw ? JSON.parse(raw) : null;
}

export function guardarEntregaId(entregaId) {
  sessionStorage.setItem(CLAVES.ENTREGA_ID, String(entregaId));
}

export function obtenerEntregaId() {
  return sessionStorage.getItem(CLAVES.ENTREGA_ID);
}

export function limpiarSesion() {
  sessionStorage.clear();
}
