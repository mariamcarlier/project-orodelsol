# ADR 0002 — Las piedras se asignan por producto; las reglas se definen aparte

- **Estado:** propuesto (pendiente de aprobación y de reflejarse en Jira).
- **Fecha:** 2026-11-12.
- **Contexto de negocio:** `docs/estrategia-negocio.md` §2.

## Contexto

La épica **JODS-1 — Gestión de Catálogo y Productos** reparte las piedras en
varias historias:

| Historia | En el repositorio | Responsabilidad |
|---|---|---|
| PROD-11 | JODS-34 | Gestionar tallas, materiales **y piedras por producto** |
| PROD-09 | (sin implementar) | Piedras permitidas por diseño de anillo |
| PROD-10 | (sin implementar) | Compatibilidad de piedras en anillos bicolor |
| PROD-19 | (sin implementar) | Selección de la piedra permitida en la tienda |
| PROD-20 | (sin implementar) | Anillo con dos piedras o colores |

Las claves de Jira están pendientes de verificación: el listado que compartió la
dueña numera PROD-08 como JODS-30 y PROD-11 como JODS-33, mientras el
repositorio cita JODS-31 y JODS-34. **Este documento no cambia esas citas.**

PROD-11 ya está implementada y en `main`: catálogo maestro `Piedra` con las 9
referencias, relación `Producto.piedras` (asignada = disponible para ese
producto), bandera `personalizable` y selector de piedra en la tarjeta de la
tienda. PROD-09, PROD-10 y PROD-19 no existen todavía.

El riesgo es conocido: si cada historia administra «qué piedras admite este
producto» a su manera, se duplica la gestión y los datos se contradicen.

## Decisión

1. **La relación «qué piedras admite este producto» es `Producto.piedras` y su
   dueña es PROD-11.** Se administra desde el panel del producto.
2. **PROD-09 define reglas de negocio sobre esa relación**, sin trasladar su
   propiedad: puede exigir una piedra, impedir combinaciones, marcar
   obligatorias u ordenarlas, pero no crea otra tabla ni otro lugar donde se
   decida qué piedras acepta un producto.
3. **PROD-10 y PROD-20 añaden lo suyo encima**: la compatibilidad entre dos
   piedras o colores es una regla nueva sobre la misma relación, no un
   reemplazo.
4. **PROD-19 es la experiencia de la tienda**: qué ve y elige el cliente, con
   las reglas de PROD-09 aplicadas.
5. **La condición «personalizable exige al menos una piedra» es una sola
   regla**, implementada en un único lugar y reutilizada por todas las puertas
   de guardado y publicación (formulario del panel, vista clásica, admin y
   activación en bloque). No se implementa en `Model.clean()` como única
   barrera, porque ahí no se ven las relaciones que el formulario está
   enviando.
6. **Personalizar no es solo elegir piedra.** Un producto puede admitir
   grabado sin piedras, o ninguna personalización. El grabado es una historia
   nueva y no un criterio implícito de PROD-11.

## Consecuencias

- PROD-09 puede cumplirse sin migrar datos: las relaciones ya existen.
- Si PROD-09 necesita piedras que hoy no se asignan por producto, **se añaden**
  a la relación, no se reemplaza la relación.
- Cualquier cambio en la forma de asignar piedras por producto pasa por PROD-11.
- El código que necesite saber qué piedras acepta un producto consulta siempre
  `Producto.piedras`; ningún otro sitio guarda esa información.
- La validación de publicación deja de estar repetida en cada pantalla: es la
  misma función para todas.

## Alternativa descartada

**Mover la propiedad a PROD-09** (que PROD-09 administre las piedras permitidas
y PROD-11 deje de hacerlo). Se descarta porque PROD-11 ya está fusionada y
probada, porque obligaría a cambiar modelo, panel y pruebas de una historia
cerrada, y porque no aporta nada al negocio: PROD-09 puede definir sus reglas
sobre las relaciones existentes.

## Cómo se refleja en Jira

- **PROD-11:** «Administra tallas, materiales y las relaciones de piedras por
  producto (`Producto.piedras`)».
- **PROD-09:** «Define y valida las reglas de piedras permitidas sobre las
  relaciones que administra PROD-11. No crea ni mueve la relación».
- **PROD-10:** «Reglas de compatibilidad para anillos bicolor, sobre la misma
  relación».
- **PROD-19:** «Selección de la piedra permitida en la tienda».
- **Historia nueva (grabado):** «Personalización por grabado», ligada a la
  configuración del producto y a la gestión de pedidos.

## Referencias

- `docs/estrategia-negocio.md` — decisiones de la dueña que motivan este ADR.
- `docs/contexto-sprint-productos.md` §6c — cierre de PROD-11 tal como se
  implementó.
- `docs/galeria-imagenes.md` — ADR 0001 (galería y portadas).
