# Contexto del sprint — Épica Productos (Oro del Sol)

> Objetivo: trabajar historia por historia, con código simple y sin reescribir
> lo que ya funciona. Este documento es la fuente de verdad del sprint.

## 1. Negocio (lo que muestran las referencias)

- **Ficha pública** (David Yurman / Retrouvaí): un anillo con galería de fotos,
  variantes visibles por **talla y piedra/material** (selector de tallas y de
  piedras), precio, número de estilo/referencia y botón *Add to Bag*.
- **Panel admin** (*Add Product*): el administrador carga fotos, categoría,
  nombre, talla, quilates/material y precio. Todo lo demás (código, SKU,
  stock) es gestión interna.
- Conclusión: el cliente compra una **variante** (talla + material/piedra);
  el administrador gestiona el **producto base** y sus variantes.

## 2. Estrategia simple (decisión del equipo)

| Principio | Cómo se aplica |
|---|---|
| Monolito Django, sin API nueva | Se reutilizan `core/dashboard.py` (panel), `core/views.py` (vistas clásicas) y `core/admin.py`. |
| `Producto` = lo que el anillo **es** | Nombre, colección, precio base, código, borrador. |
| `VarianteProducto` = lo que **se vende** | Talla + material + SKU + peso + `precio_adicional` + stock. Precio final = `precio + precio_adicional`. |
| Validación en 3 capas | BD (unique/check), modelo (`clean()`), formulario. Mensajes con SweetAlert (ya existe en `templates/partials/sweetalert-messages.html`). |
| Migraciones por pasos | Esquema → datos → restricciones (0003/0004/0005), para no romper productos existentes. |
| Autorización | `is_staff` + permiso Django (`add/change/view/delete_producto`). Sin permiso → 403. |

## 3. Mapa del sprint y estado auditado en `main`

| Historia | Jira | Estado en `main` (commit `1f00391`) | Falta / riesgo |
|---|---|---|---|
| **PROD-04** Código y referencia | JODS-27 (+274/276) | ✅ `Producto.codigo` único, auto `AN-NNNN`, bloqueado al editar, visible en panel/admin, migraciones 0003–0005, 31 tests en `test_variantes.py` | Cerrado en este cambio: faltaba en el listado clásico y en `__str__`. |
| **PROD-05** Variantes | JODS-28 (+282/283) | ✅ Modelo + `UniqueConstraint(producto,talla,material)` + SKU único + formset en panel al editar + inline en admin. Verificado end-to-end desde el panel (`test_variante_panel.py`) | Solo se gestionan desde panel/admin, **no** desde `/productos/editar` (vista clásica). Decisión: se mantiene así (el panel es la vía principal); la vista clásica queda para datos base del producto. |
| **PROD-08** Precios | JODS-31 (+300/301) | ✅ `precio > 0` en formulario y modelo, `precio_adicional >= 0`, `precio_final` | No hay historial de precios. Si se exige, es historia nueva. |
| **PROD-11** Tallas y materiales | JODS-34 (+332–335) | ✅ `Talla` (US + diámetro verificado + nacional), `Material`, M2M permitidos, seed idempotente | ⚠️ El criterio menciona **piedras** activables por producto: no existe modelo `Piedra`. Decidir si entra en este sprint. |
| **PROD-12** Borrador | JODS-35 (+338–340) | ⚠️ Parcial: `es_borrador`, `publicos()`, `clean()` exime imagen/nombre/precio | ❌ El formulario exige `precio > 0` y nombre siempre, así que un borrador sin precio/nombre **no se puede guardar** desde el panel. Corregir al llegar a esta historia. |

> Nota sobre el patch `producto-variante.patch` (5 commits): **no se borró**.
> Ya está aplicado en `main` (migraciones 0003–0005, modelos, panel, admin,
> seed y `test_variantes.py`), más 0006 (talla nacional/diámetros) y 0007
> (galería). Los 31 tests del patch pasan. El "conflicto" fue al reaplicarlo
> sobre una base que ya lo contenía.

## 4. PROD-04 — cierre (este cambio)

Criterios → dónde se cumplen:

1. *Formulario permite registrar código* → `ProductoForm.codigo`
   ("Déjalo vacío para generarlo automáticamente").
2. *Valida que no esté duplicado* → `unique=True` en BD + validador del
   ModelForm (error legible, también en minúsculas).
3. *Código asociado al producto* → `asegurar_codigo()` en `save()`.
4. *Código visible en información administrativa* → panel (columna + búsqueda
   `codigo__icontains`), admin (`list_display`/`search_fields`) y, desde este
   cambio, listado clásico `/productos/`.
5. *Identificar productos por código* → búsqueda en panel/admin/listado y
   `Producto.__str__` = `"AN-0001 - Nombre"`.
6. *Sin autorización → denegado* → `is_staff` + `core.add/change_producto`
   (403), cubierto por `test_autorizacion_vistas.py`.

Tests nuevos: `core/test_codigo_producto.py` (7 tests). Total `core`: 324 OK.

## 5. Decisiones tomadas (con el equipo)

1. **Código**: libre al crear, vacío = `AN-NNNN` autogenerado, bloqueado al
   editar. ✅ (implementación actual, sin cambios)
2. **Código público**: también visible en la tienda como `Ref. AN-0001`
   (como *Style Number* en Retrouvaí). ✅ Implementado en la tarjeta de
   producto de `templates/core/index.html`. Nota: aún no existe página de
   detalle/ficha del producto; cuando se cree, el código va ahí también.
3. **Siguiente historia**: PROD-05 Variantes. ✅ Auditada y verificada
   end-to-end desde el panel.

## 6. PROD-05 — cierre (este cambio)

Criterios → dónde se cumplen:

1. *Crear variantes asociadas a un producto base* → formset en el panel al
   editar (`VarianteFormSet`, `extra=1`, `can_delete=True`) + inline en admin.
2. *Cada variante con sus características* → talla, material, SKU, peso,
   `precio_adicional`, stock, `activa`.
3. *Relación con el producto principal* → FK `producto` (`related_name="variantes"`).
4. *Disponibilidad por variante* → `activa` + `stock`.
5. *Evitar duplicadas (misma combinación)* → `UniqueConstraint` en BD +
   revisión en `VarianteProducto.clean()` para mensaje legible en formularios
   inline (antes: error 500). Corregido en este cambio.
6. *Sin autorización → denegado* → panel exige `change_producto` (403).

Tests nuevos: `core/test_variante_panel.py` (3 tests: crear desde panel,
duplicada rechazada con error legible, sin permiso 403).

## 7. Decisiones pendientes (para las próximas historias)

1. **Piedras (PROD-11)**: ¿se crea catálogo de piedras activables por producto
   en este sprint o se recorta a tallas/materiales?
2. **Borrador (PROD-12)**: ¿precio `0` y sin nombre permitidos en borrador?
   (Implica relajar `ProductoForm.clean_precio` solo si `es_borrador`.)
3. **Ficha pública**: ¿se crea página de detalle del producto (galería,
   selector de talla/piedra, *Add to Bag*) o sigue solo la tarjeta en inicio?
