# Galería de imágenes y portadas — notas de operación

> Qué guarda el módulo, qué necesita en producción y qué no hay que hacer.
> Complementa a `docs/contexto-sprint-productos.md`. Aquí solo va lo que no se
> ve leyendo una pantalla; el detalle de cada regla está en el código citado.
>
> Las decisiones de negocio que este módulo tiene que respetar están en
> `docs/estrategia-negocio.md` (§3). El porqué del diseño, en
> `docs/decisiones/0001-galeria-de-imagenes.md`.

## 1. Decisiones vigentes

| Decisión | Valor | Dónde vive |
|---|---|---|
| Máximo de fotografías por producto | **10** | `MAX_IMAGENES_POR_PRODUCTO` en `core/servicio_galeria.py` (único lugar donde se cambia) |
| Portada de una colección | **Se conserva el original**; la tienda enseña una versión optimizada | `Coleccion.imagen` (original) e `imagen_detalle` (optimizada); `core/portadas.py` |
| Producto que ya usa la galería y la deja vacía | **Queda sin fotografía**: no vuelve a `imagen_url` y no se puede publicar | `Producto.tiene_imagen`, `Producto.imagen_catalogo`, `Producto.clean()` |
| Orden en la tienda | **Primero la principal**; después las demás, por posición | `Producto.fotografias_tienda` |

Límites de carga (los mismos para fotografías y portadas, en `core/imagenes.py`):
JPG, PNG o WebP; 10 MB por imagen; 30 MB por envío.

## 2. Qué se guarda en `media/`

| Ruta | Qué es |
|---|---|
| `productos/<id>/<uuid>.<ext>` | Original limpio de una fotografía |
| `productos/<id>/derivados/<uuid>.webp` | Sus dos versiones optimizadas: detalle (1200 px) y miniatura (400 px) |
| `colecciones/<uuid>.<ext>` | Original limpio de una portada |
| `colecciones/derivados/<uuid>.webp` | Su versión optimizada (1200 px), la que enseña la tienda |

- «Original limpio» es lo que entrega `core/imagenes.py`: el mismo formato y
  las mismas medidas que el archivo subido, con su perfil de color, ya girado
  según su orientación y **sin metadatos** (ubicación, cámara). Para quitarlos
  se vuelve a codificar (JPG y WebP con calidad 92; PNG sin pérdida): no es
  idéntico byte a byte al archivo que se subió. Una imagen en CMYK se guarda
  convertida a RGB.
- El nombre que trae el archivo nunca llega al disco: todo se guarda con un UUID.
- La carpeta `productos/<id>/` es de ese producto y de nadie más. Al eliminar
  el producto se vacía. Estas rutas las fija `core/upload_paths.py`, que no se
  puede renombrar: las migraciones lo citan por su nombre.

## 3. Producción: hay que servir `/media/`

`app/urls.py` solo publica `media/` cuando `DEBUG` está activo. Con
`DJANGO_DEBUG=False`, Django **no** entrega esos archivos: las fotografías y
las portadas subidas se guardan bien, pero la tienda las pide y recibe un 404.

Antes de publicar el sitio:

1. El servidor web (Nginx, Apache, IIS o el que se use) tiene que servir la
   carpeta `MEDIA_ROOT` (`media/` en la raíz del proyecto) en la dirección
   `MEDIA_URL` (`/media/`).
2. `media/` tiene que estar en un disco que sobreviva a cada despliegue. Está en
   `.gitignore`: no viaja con el código.
3. La copia de seguridad es **la base de datos y `media/` juntas**. Restaurar
   una sin la otra deja fotografías que apuntan a archivos que no existen, o
   archivos que nadie usa.
4. Hay que definir `LOGGING` en `app/settings.py` (o, como mínimo, `ADMINS`).
   El proyecto no define ninguno de los dos, y así, con `DJANGO_DEBUG=False`,
   Django **no deja constancia de sus propios errores**: ni de un error 500 del
   sitio ni de un fallo imprevisto al limpiar archivos. Con `DEBUG` activo sí
   salen por la consola; por eso en desarrollo no se nota.

## 4. Cambiar una imagen: siempre con `save()` o con el servicio

| Qué | Vía correcta |
|---|---|
| Fotografías de un producto | `core/servicio_galeria.py` (lo que usan las pantallas) |
| Portada de una colección | `ColeccionForm`, o asignar el campo y llamar a `coleccion.save()` |

**No usar `QuerySet.update()` ni `bulk_update()` para cambiar `Coleccion.imagen`
o `Coleccion.imagen_detalle`.** Esas dos vías no pasan por `Coleccion.save()`, y
es `save()` quien:

- borra del disco los archivos de la portada anterior;
- mantiene `imagen_detalle` como la versión optimizada de `imagen` (si no, la
  tienda seguiría enseñando la portada anterior).

Hoy ningún código del proyecto lo hace: los `update()` que tocan colecciones
solo cambian `activa`. Si alguna vez hace falta un cambio en bloque de
portadas, se recorre la lista y se llama a `save()` en cada colección.

Lo mismo vale para los archivos de `ProductoImagen`: se cambian con el servicio.

## 5. Migraciones del módulo

| Migración | Qué hace | Datos |
|---|---|---|
| `0007_galeria_imagenes_esquema` | Crea `ProductoImagen`; añade `Coleccion.imagen` y `Producto.galeria_gestionada` | No cambia ninguna fila |
| `0010_coleccion_imagen_detalle` | Añade `Coleccion.imagen_detalle` (vacío) | No cambia ninguna fila ni toca archivos |

Orden para aplicar cualquier migración sobre datos reales, cada paso por separado:

1. **Copia de seguridad** de `db.sqlite3` (y de `media/` si la migración toca archivos).
2. **Revisión**: `python manage.py showmigrations core` y
   `python manage.py sqlmigrate core <número>`.
3. **Migrar**: `python manage.py migrate`.

Deshacer la 0010 (`python manage.py migrate core 0009`) quita la columna y deja
las colecciones como estaban. Las versiones optimizadas que ya se hubieran
subido quedan en `media/colecciones/derivados/` sin uso: se borran a mano.

### SQLite y el contador de identificadores

Hay cambios de esquema (añadir una columna que no admite nulos, añadir una
restricción) para los que Django, en SQLite, **reconstruye la tabla entera**.
Al hacerlo, el contador de identificadores vuelve al mayor `id` que quede: si
el último producto creado se había eliminado, el siguiente producto **recibe
su mismo `id`**.

En este módulo eso importa porque `media/productos/<id>/` se nombra con el
`id`: si del producto eliminado quedó algún archivo sin borrar, el producto
nuevo hereda esa carpeta.

Regla para cualquier migración futura que reconstruya `core_producto` o
`core_coleccion`: guardar el contador antes y restaurarlo después, como hacen
la 0007 y la 0010 (en esta, `guardar_contador` y `restaurar_contador`). Se
sabe con `python manage.py sqlmigrate core <número>`: si aparece
`CREATE TABLE "new__core_producto"`, la tabla se reconstruye.

`0008_piedras_catalogo` y `0009_precio_no_negativo` reconstruyen
`core_producto` sin ese cuidado. Donde se apliquen después de haber eliminado
el último producto creado, ese `id` se vuelve a usar; el contador anterior no
queda guardado en ningún sitio, así que no se puede reponer después. Por eso
`borrar_carpeta_de_producto` se niega a vaciar la carpeta de un producto que
existe (punto 6).

## 6. Cuando un archivo no se deja borrar

Borrar archivos nunca hace fallar una operación que ya se guardó: si un archivo
está en uso o falta un permiso, se borra lo demás, el archivo se queda en el
disco y queda un aviso en el registro. **No hay reintento automático.**

| Aviso (registro) | Qué quedó | Cómo terminarlo, desde `python manage.py shell` |
|---|---|---|
| `core.servicio_galeria`: «Quedaron archivos sin borrar en 'productos/7'…» | Archivos de un producto eliminado | `from core import servicio_galeria`<br>`servicio_galeria.borrar_carpeta_de_producto(7)` |
| `core.portadas`: «No se pudo borrar la portada 'colecciones/….jpg'.» | Un archivo de una portada sustituida, quitada o eliminada | `from core import portadas`<br>`from core.models import Coleccion`<br>`portadas.borrar_si_nadie_la_usa(Coleccion, "colecciones/….jpg")` |

Las dos funciones devuelven `True` cuando ya no queda nada, se pueden repetir
sin riesgo y se niegan a borrar lo que sigue en uso: la primera, si existe un
producto con ese `id`; la segunda, si alguna colección usa ese archivo.

Los avisos de la tabla los escribe el propio módulo y salen siempre por la
salida de errores del servidor: en producción conviene guardarla en un archivo.
Un fallo que nadie previó lo anota Django, y en producción solo se ve si se
definió `LOGGING` (punto 3).

## 7. Límites conocidos

- **Una transacción que se revierte después de guardar.** Django no avisa: los
  archivos nuevos ya están en el disco y quedan sin fila que los use. Ninguna
  pantalla del proyecto sube archivos dentro de una transacción propia; solo
  puede pasar con código nuevo que lo haga.
- **Fallo del disco a mitad de una escritura.** Puede quedar un archivo
  incompleto cuyo nombre no llega a conocerse.
- **Dos guardados de la misma colección en el mismo instante.** Si uno cambia
  la portada mientras el otro —que leyó la colección justo antes— guarda otros
  datos, el segundo vuelve a escribir la portada anterior (cuyos archivos ya se
  borraron) y borra la nueva. La colección queda con la portada rota hasta que
  se sube otra. Hace falta que las dos peticiones se crucen en milésimas de
  segundo; no se ha añadido bloqueo para ese caso.
- **Restaurar la base de datos sin `media/`** (o al revés): ver el punto 3.

## 8. Pendientes

- **Migración de datos de `imagen_url`** (pasar las imágenes históricas de los
  productos a la galería): no está hecha ni autorizada. Sería la `0011`.
- **Página de detalle del producto**: todavía no existe. Cuando se haga, debe
  leer `Producto.fotografias_tienda`; hoy la tienda solo enseña la primera.
- **Videos**: fuera del alcance de este módulo.
