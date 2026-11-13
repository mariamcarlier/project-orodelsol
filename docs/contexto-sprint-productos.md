# Contexto del sprint — Épica Productos (Oro del Sol)

> Objetivo: trabajar historia por historia, con código simple y sin reescribir
> lo que ya funciona. Este documento es la fuente de verdad del sprint.
>
> Las **decisiones de negocio** de la dueña (tallas y cartabón, tipos de
> personalización, imágenes) están en `docs/estrategia-negocio.md` y mandan
> sobre lo que aquí se describa como pendiente. El reparto de responsabilidad
> sobre las piedras está en `docs/decisiones/0002-piedras-por-producto.md`.

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

## 3. Mapa del sprint y estado (todas las historias cerradas)

| Historia | Jira | Estado en `main` (commit `1f00391`) | Falta / riesgo |
|---|---|---|---|
| **PROD-04** Código y referencia | JODS-27 (+274/276) | ✅ `Producto.codigo` único, auto `AN-NNNN`, bloqueado al editar, visible en panel/admin, migraciones 0003–0005, 31 tests en `test_variantes.py` | Cerrado en este cambio: faltaba en el listado clásico y en `__str__`. |
| **PROD-05** Variantes | JODS-28 (+282/283) | ✅ Modelo + `UniqueConstraint(producto,talla,material)` + SKU único + formset en panel al editar + inline en admin. Verificado end-to-end desde el panel (`test_variante_panel.py`) | Solo se gestionan desde panel/admin, **no** desde `/productos/editar` (vista clásica). Decisión: se mantiene así (el panel es la vía principal); la vista clásica queda para datos base del producto. |
| **PROD-08** Precios | JODS-31 (+300/301) | ✅ `precio > 0` al publicar, `precio_adicional >= 0`, `precio_final`, `CheckConstraint` de no negativo en BD, cambio reflejado al instante. Tests en `test_precios.py` | Cerrado. Sin historial de precios (decisión del equipo). |
| **PROD-11** Tallas, materiales y piedras | JODS-34 (+332–335) | ✅ `Talla` (US + diámetro verificado + nacional), `Material`, `Piedra` (A–I), M2M `tallas`/`materiales`/`piedras`, bandera `personalizable`, seed idempotente. Tests en `test_piedras.py` | Cerrado. |
| **PROD-12** Borrador | JODS-35 (+338–340) | ✅ `es_borrador`, `publicos()`, `Producto.clean()` exime requisitos al borrador y **`ProductoForm` ya permite guardar incompleto** (nombre vacío / precio 0). Activar masivamente un borrador completo lo publica. Tests en `test_borrador.py` | Cerrado. |

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

## 6b. PROD-12 — cierre (borrador)

Regla simple: **la casilla "Borrador" es la que relaja la validación**.
`activo` solo controla visibilidad; no afecta qué se exige.

| Caso | Nombre | Precio | Imagen | Resultado |
|---|---|---|---|---|
| Borrador (`es_borrador` ✔) | opcional | opcional (0) | opcional | Se guarda. No aparece en la tienda. |
| No borrador | **obligatorio** | **> 0 obligatorio** | obligatoria | Se guarda y se publica. |

- `ProductoForm`: `nombre` y `precio` dejan de ser obligatorios a nivel HTML
  (`required=False`) y la validación se decide en `clean()` según
  `es_borrador`. Sin esto Django rechazaba el envío antes de llegar a `clean()`.
- Escenario 2 (datos obligatorios incompletos): error **específico por campo**
  — *"El nombre es obligatorio para publicar."* / *"El precio debe ser mayor a
  cero para publicar."* — y el formulario se queda abierto con los datos.
- El borrador conserva sus datos y se completa después; al desmarcar
  "Borrador" con todo completo queda publicado.
- Activación masiva: un borrador **completo** se marca `activo=True` **y**
  `es_borrador=False` (antes quedaba "activo" pero invisible). Los incompletos
  se omiten con aviso, igual que antes.

Tests nuevos: `core/test_borrador.py` (8 tests). Total `core`: 332 OK.

## 6c. PROD-11 — cierre (tallas, materiales y piedras)

Decisiones del equipo:

| Tema | Decisión |
|---|---|
| Catálogo de piedras | Las **9 referencias** de la tabla de colores de la empresa, con sus imágenes (copiadas del repo de referencia y optimizadas a 200 px). |
| Activar/desactivar por producto | **M2M `Producto.piedras`**: asignada = disponible; quitarla = desactivarla para ese producto. |
| Producto personalizable | Bandera `personalizable`. Si está activa, el producto **debe** tener al menos una piedra para publicarse. |
| Cliente | Elige la piedra en la **tarjeta del inicio**; solo ve las asignadas. El servidor valida antes de escribir en el carrito. |

Piezas nuevas:

- `core/models.py`: modelo `Piedra` (`ref` único, `nombre`, `imagen` en `static/`, `orden`),
  M2M `Producto.piedras`, `Producto.personalizable`, `piedras_disponibles()` y
  validación en `Producto.clean()`.
- `core/migrations/0008_piedras_catalogo.py`.
- `core/management/commands/seed_tallas_materiales.py`: ahora también carga las
  9 piedras (sigue siendo idempotente).
- `core/dashboard.py`: campos `personalizable` y `piedras` en el formulario
  (casillas = maestro de piedras), columna "Personalizable" y error específico
  si falta la piedra.
- `core/admin.py`: registro de `Piedra` y `piedras` en `filter_horizontal`.
- `core/views.py` + `core/urls.py`: `core:producto_piedra_disponible`
  (`GET /productos/<pk>/piedras/<ref>/disponible/`) devuelve 200/400; es la
  guarda de servidor que impide agregar al carrito una piedra desactivada.
- `templates/core/index.html`, `static/css/components.css`, `static/js/main.js`:
  selector de piedra en la tarjeta, piedra guardada en el carrito y validación
  antes de añadir.

Comandos en tu máquina (una vez):

```powershell
python manage.py migrate
python manage.py seed_tallas_materiales
```

Tests nuevos: `core/test_piedras.py` (16 tests). Total `core`: 348·OK, proyecto: 481·OK.

## 6d. PROD-08 — cierre (precios)

Decisión: **sin historial de precios**. Los criterios solo piden validar el
valor y reflejarlo; una tabla de histórico agrega código que hoy nadie
consulta. Si el negocio lo pide después, se agrega como historia nueva.

| Criterio | Cómo se cumple |
|---|---|
| Actualizar el precio | `ProductoForm.precio` en panel, admin y vista clásica. |
| Valor numérico | `DecimalField`: un texto como "un millón" da error de campo. |
| Valor positivo | > 0 obligatorio al **publicar**; 0 permitido solo en borrador (PROD-12); negativo **nunca** (modelo + BD). |
| Reflejo inmediato | Sin caché: la tarjeta y el panel leen de BD en cada petición (`test_precios.py`). |
| Precio de la variante | `precio_final = producto.precio + precio_adicional`, se recalcula al actualizar. |
| Sin autorización | `is_staff` + `change_producto` → 403. |

Nuevo: `core/migrations/0009_precio_no_negativo.py` (`CheckConstraint`
`producto_precio_no_negativo`) y validación de negativos en `Producto.clean()`.

Tests nuevos: `core/test_precios.py` (10 tests). Total `core`: 358·OK, proyecto: 491·OK.

## 7. Pendiente fuera de estas 5 historias

1. **Ficha pública**: no existe página de detalle del producto (galería,
   selector de talla/piedra, *Add to Bag* como en las referencias). Hoy el
   cliente elige la piedra en la tarjeta del inicio.
2. **Historial de precios**: descartado por ahora; es historia nueva si el
   negocio lo pide.
