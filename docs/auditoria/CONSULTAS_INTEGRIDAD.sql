-- Ejecutar solo sobre una copia de prueba ya migrada.
-- Cada consulta de incoherencias debe devolver 0 filas o contador 0.

-- Una entrega cerrada debe tener una calificación final.
SELECT e.id
FROM entregas AS e
LEFT JOIN calificaciones AS c ON c.entrega_id = e.id
WHERE e.cerrada = TRUE AND c.id IS NULL;

-- Una entrega cerrada debe tener una respuesta por pregunta asignada.
SELECT e.id,
       COUNT(DISTINCT pa.pregunta_id) AS asignadas,
       COUNT(DISTINCT ra.pregunta_id) AS respondidas
FROM entregas AS e
JOIN preguntas_asignadas AS pa ON pa.entrega_id = e.id
LEFT JOIN respuestas_alumno AS ra ON ra.entrega_id = e.id
WHERE e.cerrada = TRUE
GROUP BY e.id
HAVING COUNT(DISTINCT pa.pregunta_id) <> COUNT(DISTINCT ra.pregunta_id);

-- Ninguna entrega cerrada conserva una reserva activa.
SELECT id, reserva_id, reserva_expira_en
FROM entregas
WHERE cerrada = TRUE
  AND (procesando = TRUE OR reserva_id IS NOT NULL OR reserva_expira_en IS NOT NULL);

-- No existen calificaciones huérfanas ni duplicadas.
SELECT c.entrega_id, COUNT(*)
FROM calificaciones AS c
LEFT JOIN entregas AS e ON e.id = c.entrega_id
GROUP BY c.entrega_id
HAVING COUNT(*) <> 1 OR MAX(e.id) IS NULL;

-- No existen dos intentos para el mismo alumno y examen.
SELECT alumno_id, examen_id, COUNT(*)
FROM entregas
GROUP BY alumno_id, examen_id
HAVING COUNT(*) > 1;

-- Las respuestas pertenecen a preguntas realmente asignadas al intento.
SELECT ra.entrega_id, ra.pregunta_id
FROM respuestas_alumno AS ra
LEFT JOIN preguntas_asignadas AS pa
  ON pa.entrega_id = ra.entrega_id AND pa.pregunta_id = ra.pregunta_id
WHERE pa.id IS NULL;

-- Los borradores no sobreviven a un envío finalizado.
SELECT b.entrega_id, COUNT(*)
FROM borradores_respuestas AS b
JOIN entregas AS e ON e.id = b.entrega_id
WHERE e.cerrada = TRUE
GROUP BY b.entrega_id;

-- Las evidencias tienen propietario indirecto, tamaño y duración coherentes.
SELECT ev.id
FROM evidencias_auditoria AS ev
LEFT JOIN eventos_auditoria AS ea ON ea.id = ev.evento_id
LEFT JOIN entregas AS e ON e.id = ea.entrega_id
WHERE ea.id IS NULL
   OR e.id IS NULL
   OR ev.tamano_bytes <= 0
   OR ev.duracion_ms < 0
   OR ev.duracion_ms > 15000;
