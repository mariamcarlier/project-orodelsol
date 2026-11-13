# Estrategia de negocio — lo que el catálogo debe respetar

> Decisiones de la dueña que condicionan el modelo de datos, la tienda y el
> panel. No describe cómo está hecho el código (eso está en
> `docs/galeria-imagenes.md` y `docs/contexto-sprint-productos.md`): dice qué
> tiene que cumplir.
>
> Fuente: respuestas de Mariam Carlier, 2026-11-12. Lo que aquí aparece como
> «decidido» lo dijo ella; lo que aparece como «por decidir» no está decidido y
> no debe implementarse por suposición.

## 1. Tallas y taller

### Decidido

| Tema | Decisión |
|---|---|
| Instrumento de medida | **Cartabón** (así lo llama la empresa; es el mandril/medidor de tallas del taller) |
| Marcas del cartabón | Números **enteros y medias tallas** (5, 5.5, 6, 6.5…) |
| Cómo se talla | El taller usa **la marca del cartabón**. **No mide el diámetro interior** del anillo terminado |
| Precios | **Varían según la talla**: las tallas más grandes cuestan más por el material |
| Mercado | Hoy **solo Colombia**. Vender en Estados Unidos es una posibilidad, **no está decidido** |
| Referencia | El cartabón trae tres escalas nacionales. Las **rojas son nacionales** y las **negras americanas**; la numeración americana es la misma en todo el mundo |

### Escala nacional de la empresa

19 tallas, de la US 4 a la US 13 en medias tallas. Los valores coinciden con
los que hoy carga `seed_tallas_materiales`.

| US | Nacional (CO) | US | Nacional (CO) |
|---|---|---|---|
| 4 | 6 | 8.5 | 15 |
| 4.5 | 7 | 9 | 16 |
| 5 | 8 | 9.5 | 17 |
| 5.5 | 9 | 10 | 18 |
| 6 | 10 | 10.5 | 19 |
| 6.5 | 11 | 11 | 20 |
| 7 | 12 | 11.5 | 21 |
| 7.5 | 13 | 12 | 22 |
| 8 | 14 | 12.5 | 23 |
| | | 13 | 24 |

### Implicaciones

- La talla US es la referencia comercial; **la nacional (CO) es la que ve el
  cliente colombiano**. El campo `Talla.talla_nacional` debe llenarse con la
  tabla de arriba, fila por fila. La semejanza con el hueco de media talla en la
  numeración americana es casualidad: **manda la tabla, no la fórmula**.
- **No hay dato de diámetro interior.** Ningún documento de la empresa ni el
  taller lo aportan. `Talla.diametro_interno_mm` existe en el esquema y debe
  quedar **vacío**; no se rellena con tablas de referencia de terceros y no
  debe mostrarse en la tienda salvo que `diametro_verificado` sea verdadero.
  Hoy la semilla carga 19 diámetros copiados de una tabla externa con
  `diametro_verificado=False`: contradice esta decisión y está pendiente de
  retirar (ver §6).
- **El ajuste de precio por talla vive en la variante**
  (`VarianteProducto.precio_adicional`), nunca en el producto: el precio final
  es `Producto.precio + precio_adicional`. Un producto con tallas que cuestan
  distinto necesita una variante por talla.
- **Una sola escala nacional por ahora.** El cartabón trae CO, EU y MX, pero el
  campo actual guarda una. Añadir las otras dos es un cambio de esquema que
  solo se justifica cuando se decida vender fuera; con «solo Colombia» no hace
  falta.
- El cartabón es un instrumento físico: el sistema no lo modela. Solo se
  registra la talla resultante.

## 2. Personalización de un anillo

### Decidido

El catálogo tiene anillos de tres clases y la personalización **no depende de
tener piedras**:

| Clase | Descripción | Qué exige el sistema |
|---|---|---|
| Sin personalización | Diseños, acabados o modelos genéricos; se venden tal cual | Nada: se publica sin piedras ni texto |
| Con piedras | El diseño admite circonitas u otras piedras | Al menos una piedra disponible para poder publicarse |
| Con grabado | El diseño admite grabado, tenga piedras o no | Nada de piedras; el cliente escribe el texto |

Casos reales que motivaron la decisión: los anillos de matrimonio suelen ser
**sin piedras** y aun así los clientes piden **grabados** con frecuencia; hay
anillos de figura o acabado que son genéricos y **no admiten nada**.

Una misma pieza puede admitir piedras **y** grabado; las dos opciones se
configuran por separado y no se implican entre sí.

### Implicaciones

- La condición «personalizable exige al menos una piedra» **no puede ser la
  única forma de personalizar**. Hoy el código la aplica a `personalizable`;
  eso es correcto para la personalización con piedras, pero no puede
  extenderse al grabado.
- **El grabado no entra en PROD-11.** Se tratará como historia nueva, con sus
  propios criterios y alcance, y ligada a la futura gestión de pedidos: no debe
  quedar como una casilla visual. Un grabado es una decisión del cliente que
  viaja con la línea del pedido (texto, límite de caracteres, precio si lo
  tiene) y no puede depender del estado del producto cuando se consulte el
  pedido.
- **Propiedad de las piedras:** la relación «qué piedras admite este producto»
  es de **PROD-11** (`Producto.piedras`). PROD-09 define reglas de negocio
  *sobre* esas relaciones, sin trasladar su propiedad ni duplicar la gestión
  del catálogo maestro. PROD-10 (compatibilidad bicolor) y PROD-19 (selección
  en la tienda) construyen sobre lo mismo.
- La validación de la personalización con piedras debe ser **una sola regla
  compartida** por el formulario del panel, la vista clásica, el admin y la
  activación en bloque. Si cada pantalla la repite, el mismo defecto reaparece
  por otra puerta.

### Por decidir

- Límite de caracteres del grabado y si cuesta más.
- Si el grabado se ofrece también en piezas con piedras (la decisión de arriba
  dice que sí puede combinarse; falta la regla comercial).
- Si el stock se lleva por piedra (hoy el stock es por talla y material; dos
  colores de piedra comparten stock).

## 3. Imágenes y catálogo

### Decidido

| Tema | Decisión |
|---|---|
| Fotografías por producto | Máximo **10**, administradas desde el panel |
| Fotografía principal | Una por producto; en la tienda va **primero** |
| Portada de colección | Se **conserva el original** y la tienda usa una versión optimizada |
| Catálogo vacío | Un producto publicado **tiene que tener imagen**; una galería vacía no vuelve a la dirección antigua |

### Implicaciones

- Las imágenes se suben y se ordenan desde el panel, y quien las gestiona es
  personal con permiso de cambiar productos.
- El original se guarda para conservar calidad; lo que se sirve al cliente es
  la versión optimizada (WebP).
- **Producción tiene que servir `/media/`**: sin eso, las fotografías se suben
  bien pero la tienda recibe 404. La copia de seguridad es la base de datos y
  `media/` juntas. Detalle en `docs/galeria-imagenes.md` §3.
- La tienda es la que decide qué se ve: la galería existe aunque todavía no
  haya una página de detalle del producto.

### Por decidir

- La página de detalle del producto (dónde se ven todas sus fotografías).
- Qué hacer con las fotografías históricas guardadas en `imagen_url`.

## 4. Pedido y carrito

### Estado real

El carrito **vive en el navegador** (`localStorage`) y no existe ningún modelo
de pedido: hoy no hay forma de que un pedido llegue al servidor. Nada de lo que
el cliente elige (talla, piedra, grabado) se conserva del lado del servidor.

### Implicaciones

- El precio que se muestra es informativo: **el servidor tendrá que recalcularlo
  al crear el pedido** (precio del producto + ajuste de la variante + lo que
  cueste la personalización).
- El pedido deberá **copiar** el código del producto, el texto del grabado y
  los precios del momento, no leerlos del producto vivo: un cambio de precio
  posterior no puede reescribir un pedido anterior.
- Las políticas de envío, garantía y devolución dependen de esta pieza; hoy no
  están conectadas a nada.

## 5. Reglas de trabajo

- **Ramas separadas por línea de trabajo**: seguridad del panel, galería,
  correcciones de productos. Cada una con su PR revisable por separado.
- **Una sola rama abierta a la vez que modifique migraciones de `core`.** La
  que fusione de segunda renumera. Antes se perdió tiempo comprobando que dos
  ramas creaban la misma `0010` y el proyecto no arrancaba.
- **No se cambia la numeración de una migración ya fusionada**, ni se tocan las
  migraciones de otra persona.
- **No se cambian las referencias de Jira por inferencia.** Las claves del
  repositorio (PROD-11 = JODS-34, PROD-08 = JODS-31, PROD-12 = JODS-35) están
  pendientes de verificar contra Jira y se conservan como están hasta entonces.
- **Nada de `git add .`**: hay archivos sin seguimiento de trabajo local que no
  deben viajar al repositorio.

## 6. Pendientes que nacen de este documento

1. Retirar de `seed_tallas_materiales` los 19 diámetros copiados de una tabla
   externa (§1) y ajustar el docstring que dice lo contrario.
2. Corregir la validación de personalización con piedras para que el estado
   final del formulario se tenga en cuenta y para que la activación en bloque
   aplique la misma regla.
3. Abrir la historia de grabado (§2) con sus criterios y su enlace al pedido.
4. Decidir si el diámetro interior se medirá algún día; mientras tanto, el
   campo se queda vacío.
