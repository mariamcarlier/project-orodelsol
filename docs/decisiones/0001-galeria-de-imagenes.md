# ADR 0001 — La galería del producto es la única fuente de sus fotografías

- **Estado:** aprobado e implementado (pasos 03a–04 del módulo de galería).
- **Fecha:** 2026-11-12.
- **Notas de operación:** `docs/galeria-imagenes.md`.

## Contexto

Antes de la galería, cada producto tenía **una** imagen: la dirección escrita a
mano en `Producto.imagen_url`. Eso traía tres problemas:

- La imagen vivía fuera del sitio; si la dirección se caía, el producto se
  quedaba sin foto.
- Una sola imagen por producto: no había forma de enseñar el anillo desde
  varios ángulos.
- Nada garantizaba que un producto publicado tuviera imagen.

Se añadió `ProductoImagen`: varias fotografías por producto, con archivo propio
o dirección externa, una principal y un orden.

## Decisión

1. **Desde que un producto usa la galería (`galeria_gestionada`), la galería es
   su única fuente de fotografías.** `imagen_url` deja de contar en la tienda y
   no se vuelve a ella si la galería se queda vacía.
2. **Máximo 10 fotografías** por producto.
3. **Cada fotografía se guarda en dos piezas:** el original limpio (mismo
   formato y medidas, sin metadatos, ya girado) y sus versiones optimizadas en
   WebP (detalle 1200 px y miniatura 400 px). La tienda sirve las optimizadas.
4. **Una fotografía es principal y el orden es independiente.** En la tienda va
   primero la principal y después las demás por posición; elegir la principal no
   la mueve.
5. **Un producto publicado no puede quedarse sin su única fotografía**, y
   `imagen_url` ya no sirve para publicar mientras la galería esté gestionada.
6. **Las portadas de colección siguen la misma idea**: se conserva el original
   (`Coleccion.imagen`) y la tienda usa una versión optimizada
   (`imagen_detalle`).
7. **Los archivos se cambian con el servicio de galería o con `save()`**, nunca
   con `QuerySet.update()` ni `bulk_update()`: esos caminos no borran el archivo
   anterior ni mantienen la versión optimizada.
8. **Al eliminar un producto se vacía su carpeta**, en el commit y sin dejar que
   un fallo de disco tumbe la operación.

## Consecuencias

- La copia de seguridad es la base de datos **y** `media/` juntas.
- Producción tiene que servir `/media/`; con `DEBUG` apagado Django no entrega
  esos archivos.
- La tienda necesita una página de detalle para mostrar todas las fotografías;
  hasta que exista, solo se ve la principal en la tarjeta.
- La migración de datos que pasaría las direcciones históricas de `imagen_url`
  a la galería **no está hecha ni autorizada**.

## Relación con ADR 0002

Este ADR es independiente de `0002-piedras-por-producto.md`: la galería trata
fotografías y portadas; el otro, piedras y personalización. Sus cambios no deben
mezclarse en una misma rama si tocan migraciones de `core`.
