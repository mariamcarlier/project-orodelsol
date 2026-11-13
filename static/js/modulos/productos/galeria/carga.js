/*
 * galeria/carga.js — la parte del navegador del bloque de galería.
 *
 * Hace tres cosas y ninguna es indispensable: sin este archivo la galería
 * funciona igual (se eligen archivos, se suben, se reordena y se elimina con el
 * formulario clásico).
 *
 *   1. Vista previa y validación temprana de los archivos elegidos, con los
 *      MISMOS límites y los MISMOS mensajes que el servidor. Llegan en
 *      `core.mensajes_galeria` y `core.vistas_galeria`, dentro del JSON que
 *      pinta la plantilla; aquí no se escribe ni un límite a mano. Se revisan
 *      tamaño, tipo permitido, archivo vacío, peso por envío, duplicados,
 *      huecos libres y dimensiones; la firma de los bytes se mira al enviar.
 *   2. Orden con botones (subir / bajar): recalcula los `posicion-<pk>` que ya
 *      esperaba el servidor desde el Paso 03c. El orden del envío no cambia.
 *   3. Aviso de cambios sin guardar y estado «Subiendo…» para no enviar dos
 *      veces. La carga sigue siendo un POST síncrono: no hay progreso por
 *      archivo porque el navegador no lo da al enviar un formulario.
 *   4. Marca el bloque con la clase `js-galeria`, que es la que autoriza al CSS
 *      a ocultar visualmente el campo de archivos y a usar el envío de la
 *      selección.
 *
 * Nada de aquí sustituye a la validación del servidor: si el JavaScript está
 * desactivado o modificado, el servidor rechaza lo mismo.
 */
(function () {
  'use strict';

  const bloques = document.querySelectorAll('[data-galeria]');
  if (!bloques.length) return;

  const reducido = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  /* ─── Utilidades ─────────────────────────────────────────────── */

  function configuracion(bloque) {
    const fuente = document.getElementById(bloque.dataset.configId);
    if (!fuente) return null;
    try {
      return JSON.parse(fuente.textContent);
    } catch (error) {
      console.warn('La configuración de la galería no se pudo leer.', error);
      return null;
    }
  }

  function formatoDePeso(bytes) {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} KB`;
    // Un decimal basta para decidir si un archivo se acerca al límite.
    return `${(bytes / (1024 * 1024)).toFixed(1).replace('.0', '')} MB`;
  }

  function textoMensaje(cfg, codigo, datos) {
    const plantilla = cfg.mensajes[codigo];
    if (!plantilla) return '';
    return plantilla.replace(/\{(\w+)\}/g, (_, clave) =>
      datos && clave in datos ? datos[clave] : `{${clave}}`
    );
  }

  function etiquetar(cfg, nombre, mensaje) {
    return cfg.etiquetaArchivo
      .replace('{nombre}', nombre)
      .replace('{mensaje}', mensaje);
  }

  /* ─── 1. Archivos elegidos: previa y validación ───────────────── */

  /**
   * ¿Los bytes parecen una imagen de los formatos que el servidor acepta?
   *
   * El tipo MIME del navegador sale de la extensión, así que un archivo de
   * texto llamado `anillo.jpg` llegaría hasta el servidor y se rechazaría
   * después de subir 10 MB. Se miran las firmas de los formatos permitidos
   * (JPEG, PNG y WebP) y, si no coinciden, se pinta el archivo igualmente
   * pero clasificado como «no parece una imagen». No sustituye a Pillow: es
   * el mismo aviso, antes de enviar.
   *
   * La lectura es perezosa: solo al pulsar «Subir fotografías». Para la vista
   * previa basta el navegador.
   */
  function pareceImagenDeLosPermitidos(archivo) {
    return archivo.slice(0, 12).arrayBuffer().then((buffer) => {
      const bytes = new Uint8Array(buffer);
      const empiezaPor = (...firma) => firma.every((valor, i) => bytes[i] === valor);

      const jpeg = empiezaPor(0xff, 0xd8, 0xff);
      const png = empiezaPor(0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a);
      // «RIFF» + tamaño + «WEBP»: la firma de WebP.
      const webp =
        empiezaPor(0x52, 0x49, 0x46, 0x46) &&
        bytes[8] === 0x57 && bytes[9] === 0x45 && bytes[10] === 0x42 && bytes[11] === 0x50;

      return jpeg || png || webp;
    });
  }

  function prepararCarga(bloque, cfg) {
    const formulario = bloque.querySelector('[data-subir]');
    if (!formulario) return;
    const entrada = formulario.querySelector('[data-archivo]');
    const zona = formulario.querySelector('[data-zona]');
    const seleccion = formulario.querySelector('[data-seleccion]');
    const lista = formulario.querySelector('[data-previa]');
    const titulo = formulario.querySelector('[data-seleccion-titulo]');
    const aviso = formulario.querySelector('[data-previa-error]');
    const enviar = formulario.querySelector('[data-enviar]');
    const enviarSinJs = formulario.querySelector('[data-enviar-sin-js]');
    if (!entrada || !seleccion || !lista) return;

    // A partir de aquí el bloque puede usar el aspecto «con JavaScript»: el
    // campo real se oculta visualmente y el botón de envío es el de la
    // selección. Sin esta clase, el campo se ve y se usa el envío clásico.
    bloque.classList.add('js-galeria');
    if (enviarSinJs) enviarSinJs.hidden = true;

    /** Archivos elegidos, con su estado ya calculado. */
    let elegidos = [];
    let enviando = false;

    function liberar(item) {
      if (item.url) URL.revokeObjectURL(item.url);
      item.url = null;
    }

    function liberarTodos() {
      elegidos.forEach(liberar);
    }

    /** Límites del servidor, comprobados sobre lo que el navegador puede saber. */
    function revisar(archivo, pesoAcumulado) {
      // Un archivo de 0 bytes no tiene firma ni tamaño: el servidor lo rechaza
      // antes de abrirlo y dice lo mismo que aquí.
      if (!archivo.size) {
        return textoMensaje(cfg, 'vacio');
      }
      if (!archivo.type.startsWith('image/')) {
        return textoMensaje(cfg, 'no_imagen');
      }
      // `accept` solo filtra el diálogo del sistema: un GIF o un SVG se puede
      // seguir eligiendo. El servidor los rechaza; aquí se avisa antes de enviar.
      const punto = archivo.name.lastIndexOf('.');
      const extension = punto === -1 ? '' : archivo.name.slice(punto).toLowerCase();
      if (extension && !cfg.tipos.includes(extension)) {
        return textoMensaje(cfg, 'formato', {
          formato: extension.slice(1).toUpperCase(),
        });
      }
      if (archivo.size > cfg.maximoPorImagen) {
        return textoMensaje(cfg, 'pesada', { mb_por_imagen: cfg.mbPorImagen });
      }
      if (pesoAcumulado + archivo.size > cfg.maximoPorEnvio) {
        return textoMensaje(cfg, 'envio_pesado', { mb_por_envio: cfg.mbPorEnvio });
      }
      return '';
    }

    /**
     * Las dimensiones solo se pueden comprobar con la imagen ya decodificada.
     * Si no se puede leer, no se avisa: el servidor la revisa igual.
     */
    function revisarDimensiones(item) {
      return new Promise((resolver) => {
        if (!item.url || item.error) {
          resolver();
          return;
        }
        const imagen = new Image();
        imagen.onload = () => {
          if (imagen.naturalWidth > cfg.ladoMaximo || imagen.naturalHeight > cfg.ladoMaximo
              || imagen.naturalWidth * imagen.naturalHeight > cfg.megapixelesMaximos * 1_000_000) {
            item.error = textoMensaje(cfg, 'dimensiones', {
              medida: `mide ${imagen.naturalWidth}×${imagen.naturalHeight} px y `,
              lado: cfg.ladoMaximo,
              megapixeles: cfg.megapixelesMaximos,
            });
          }
          resolver();
        };
        imagen.onerror = () => resolver(); // lo dirá el servidor
        imagen.src = item.url;
      });
    }

    function pintar() {
      lista.replaceChildren();
      const conError = elegidos.filter((item) => item.error).length;
      const peso = elegidos.reduce((total, item) => total + item.archivo.size, 0);

      elegidos.forEach((item, posicion) => {
        const fila = document.createElement('li');
        fila.className = 'galeria-admin__previa-foto';
        if (item.error) fila.classList.add('tiene-error');

        const marco = document.createElement('div');
        marco.className = 'galeria-admin__previa-marco';
        if (item.url) {
          const imagen = document.createElement('img');
          imagen.src = item.url;
          imagen.alt = '';
          imagen.loading = 'lazy';
          // Un archivo que el navegador no puede pintar deja el hueco con un
          // icono roto: mejor un marcador neutro. No se dice que sea inválido
          // porque aquí todavía no se sabe; el servidor lo dirá al enviar.
          imagen.addEventListener('error', () => {
            imagen.remove();
            const sinPrevia = document.createElement('span');
            sinPrevia.className = 'galeria-admin__previa-icono';
            sinPrevia.setAttribute('aria-hidden', 'true');
            sinPrevia.textContent = '?';
            marco.append(sinPrevia);
            const nota = document.createElement('span');
            nota.className = 'galeria-admin__previa-tamano';
            nota.textContent = 'Sin vista previa en el navegador.';
            datos.append(nota);
          });
          marco.append(imagen);
        } else {
          const icono = document.createElement('span');
          icono.className = 'galeria-admin__previa-icono';
          icono.setAttribute('aria-hidden', 'true');
          icono.textContent = '!';
          marco.append(icono);
        }

        const datos = document.createElement('div');
        datos.className = 'galeria-admin__previa-datos';
        const nombre = document.createElement('span');
        nombre.className = 'galeria-admin__previa-nombre';
        nombre.textContent = item.archivo.name;
        const tamano = document.createElement('span');
        tamano.className = 'galeria-admin__previa-tamano';
        tamano.textContent = formatoDePeso(item.archivo.size);
        datos.append(nombre, tamano);

        const estado = document.createElement('span');
        estado.className = 'galeria-admin__previa-estado';
        estado.textContent = item.error ? 'No válida' : 'Lista para subir';
        if (item.error) {
          const detalle = document.createElement('span');
          detalle.className = 'galeria-admin__previa-error';
          detalle.textContent = item.error;
          datos.append(estado, detalle);
        } else {
          datos.append(estado);
        }

        const quitar = document.createElement('button');
        quitar.type = 'button';
        quitar.className = 'galeria-admin__previa-quitar';
        quitar.textContent = 'Quitar';
        quitar.setAttribute('aria-label', `Quitar «${item.archivo.name}» de la selección`);
        quitar.addEventListener('click', () => {
          liberar(item);
          elegidos = elegidos.filter((otro) => otro !== item);
          pintar();
          if (!elegidos.length) reiniciar();
        });

        fila.append(marco, datos, quitar);
        lista.append(fila);
        // Se conserva un orden estable aunque el usuario reordene la lista.
        fila.dataset.indice = String(posicion);
      });

      const valido = elegidos.length > 0 && conError === 0;
      seleccion.hidden = elegidos.length === 0;
      aviso.hidden = conError === 0;
      aviso.textContent = conError
        ? `${conError} de los archivos elegidos ${conError === 1 ? 'no se puede' : 'no se pueden'} subir. Quita ${conError === 1 ? 'ese archivo' : 'esos archivos'} para continuar.`
        : '';
      if (enviar) {
        enviar.disabled = !valido || enviando;
        enviar.textContent = enviando ? 'Subiendo…' : 'Subir fotografías';
        enviar.setAttribute('aria-busy', enviando ? 'true' : 'false');
      }
      // El resumen de la selección es una región viva: al elegir archivos se
      // anuncia cuántos entraron y cuántos no, sin mover el foco.
      titulo.setAttribute('role', 'status');
      titulo.setAttribute('aria-live', 'polite');
      titulo.textContent = elegidos.length
        ? `${elegidos.length} ${elegidos.length === 1 ? 'imagen seleccionada' : 'imágenes seleccionadas'} · ${formatoDePeso(peso)}`
        : '';
      entrada.setCustomValidity(
        valido || !elegidos.length
          ? ''
          : 'Quita los archivos marcados con error antes de subir.'
      );
    }

    function reiniciar() {
      seleccion.hidden = true;
      aviso.hidden = true;
      entrada.setCustomValidity('');
      if (enviarSinJs) enviarSinJs.hidden = true;
    }

    /** Vuelve a leer el `input` y valida lo elegido (y solo lo elegido). */
    function leer() {
      liberarTodos();
      const archivos = Array.from(entrada.files || []);
      const libres = cfg.libres;
      let acumulado = 0;
      elegidos = archivos.map((archivo, posicion) => {
        let error = '';
        if (posicion >= libres) {
          error = textoMensaje(cfg, 'limite_navegador', { maximo: cfg.maximo });
        } else {
          error = revisar(archivo, acumulado);
        }
        const repetido = archivos
          .slice(0, posicion)
          .some((otro) => otro.name === archivo.name && otro.size === archivo.size);
        if (!error && repetido) {
          error = textoMensaje(cfg, 'duplicada', { nombre: archivo.name });
        }
        if (!error) acumulado += archivo.size;
        const url = error && !archivo.type.startsWith('image/') ? null : URL.createObjectURL(archivo);
        return { archivo, error, url };
      });
      pintar();

      // Las dimensiones necesitan que la imagen esté decodificada: se revisan
      // a continuación y solo se vuelve a pintar si alguna no cumple.
      Promise.all(elegidos.map(revisarDimensiones)).then(() => {
        if (elegidos.some((item) => item.error)) pintar();
      });
    }

    entrada.addEventListener('change', leer);

    /* Arrastrar y soltar: solo se rellena el `input`; nada más. */
    if (zona && entrada && !entrada.disabled) {
      const textos = {
        titulo: zona.querySelector('[data-zona-titulo]'),
        texto: zona.querySelector('[data-zona-texto]'),
      };
      const tituloOriginal = textos.titulo.textContent.trim();
      let profundidad = 0;

      const resaltar = (activo) => {
        zona.classList.toggle('is-dragover', activo);
        textos.titulo.textContent = activo ? 'Suelta las imágenes aquí' : tituloOriginal;
      };

      ['dragenter', 'dragover'].forEach((evento) => {
        zona.addEventListener(evento, (eventoReal) => {
          eventoReal.preventDefault();
          if (evento === 'dragenter') profundidad += 1;
          resaltar(true);
        });
      });
      ['dragleave', 'dragend'].forEach((evento) => {
        zona.addEventListener(evento, () => {
          profundidad = Math.max(profundidad - 1, 0);
          if (!profundidad) resaltar(false);
        });
      });
      zona.addEventListener('drop', (evento) => {
        evento.preventDefault();
        profundidad = 0;
        resaltar(false);
        const soltados = Array.from(evento.dataTransfer?.files || []);
        if (!soltados.length) return;
        const transferencia = new DataTransfer();
        soltados.forEach((archivo) => transferencia.items.add(archivo));
        entrada.files = transferencia.files;
        entrada.dispatchEvent(new Event('change', { bubbles: true }));
      });
    }

    /* Estado «Subiendo…»: evita el doble envío y no pierde la selección. */
    function anunciarEnvio() {
      enviando = true;
      if (enviarSinJs) {
        enviarSinJs.disabled = true;
        enviarSinJs.textContent = 'Subiendo…';
        enviarSinJs.setAttribute('aria-busy', 'true');
      }
      pintar();
      // Si el navegador cancela la navegación (error de red), vuelve a estar listo.
      window.setTimeout(() => {
        enviando = false;
        if (document.body.contains(formulario)) pintar();
      }, 8000);
      if (reducido) formulario.setAttribute('aria-busy', 'true');
    }

    formulario.addEventListener('submit', (evento) => {
      if (enviando) {
        evento.preventDefault();
        return;
      }
      const conError = elegidos.filter((item) => item.error).length;
      if (conError) {
        evento.preventDefault();
        aviso.hidden = false;
        aviso.focus();
        return;
      }
      if (!elegidos.length) return; // lo impide el atributo `required`

      // Última comprobación antes de enviar: ¿los bytes son de verdad una
      // imagen de las permitidas? Se hace aquí, y no al elegir el archivo,
      // para no leer dos veces lo que quizá nunca se envíe.
      const porRevisar = elegidos.filter((item) => !item.revisado);
      if (!porRevisar.length) {
        anunciarEnvio();
        return; // el envío sigue su curso normal
      }
      evento.preventDefault();
      Promise.all(
        porRevisar.map((item) =>
          pareceImagenDeLosPermitidos(item.archivo).then(
            (esImagen) => {
              item.revisado = true;
              if (!esImagen && !item.error) item.error = textoMensaje(cfg, 'no_imagen');
            },
            () => {
              // Si el navegador no deja leerlo, decide el servidor.
              item.revisado = true;
            }
          )
        )
      ).then(() => {
        if (elegidos.some((item) => item.error)) {
          pintar();
          aviso.hidden = false;
          aviso.focus();
          return;
        }
        // Vuelve a enviarse; en esta segunda pasada ya no hay nada que revisar
        // y el envío ocurre con la validación del navegador intacta.
        if (typeof formulario.requestSubmit === 'function') formulario.requestSubmit();
        else HTMLFormElement.prototype.submit.call(formulario);
      });
    });
  }

  /* ─── 2 y 3. Orden con botones y cambios sin guardar ──────────── */

  function prepararOrden(bloque, cfg) {
    const formulario = bloque.querySelector('[data-organizar]');
    if (!formulario) return;
    const lista = formulario.querySelector('[data-lista]');
    const guardar = formulario.querySelector('[data-guardar]');
    const estado = formulario.querySelector('[data-estado-guardado]');
    const pendiente = document.getElementById(bloque.dataset.mensajesId);
    if (!lista || !guardar) return;

    // Mientras se envía, el navegador no debe preguntar si abandonar la página:
    // la persona ya eligió guardar.
    let guardando = false;

    const avisoGeneral = `Tienes cambios en el orden o en la foto principal sin guardar. Pulsa «Guardar orden y principal» para conservarlos.`;

    /** Huella del estado visible: qué foto ocupa cada lugar y cuál es la principal. */
    function huella() {
      return Array.from(lista.querySelectorAll('[data-foto]'))
        .map((foto) => {
          const campo = foto.querySelector('[data-posicion-campo]');
          const principal = foto.querySelector('input[name="principal"]').checked;
          return `${campo.name}:${principal ? 1 : 0}`;
        })
        .join('|');
    }

    // Huella tal como llegó del servidor: cualquier diferencia es un cambio.
    const inicial = huella();

    function marcarPendiente(hay) {
      if (guardar) guardar.disabled = !hay;
      if (estado) estado.textContent = hay ? 'Hay cambios sin guardar.' : 'Sin cambios por guardar.';
      if (pendiente) {
        pendiente.hidden = !hay;
        pendiente.textContent = hay ? avisoGeneral : '';
      }
    }

    /** Renumera los campos ocultos y pinta la posición visible. */
    function renumerar() {
      Array.from(lista.querySelectorAll('[data-foto]')).forEach((foto, indice) => {
        foto.querySelector('[data-posicion-campo]').value = String(indice + 1);
        const numero = foto.querySelector('[data-indice]');
        if (numero) numero.textContent = String(indice + 1);
      });
      const fotos = Array.from(lista.querySelectorAll('[data-foto]'));
      fotos.forEach((foto, indice) => {
        foto.querySelector('[data-mover="subir"]').disabled = indice === 0;
        foto.querySelector('[data-mover="bajar"]').disabled = indice === fotos.length - 1;
      });
      marcarPendiente(huella() !== inicial);
    }

    lista.addEventListener('click', (evento) => {
      const boton = evento.target.closest('[data-mover]');
      if (boton) {
        const foto = boton.closest('[data-foto]');
        const hermanos = Array.from(lista.querySelectorAll('[data-foto]'));
        const indice = hermanos.indexOf(foto);
        const destino = boton.dataset.mover === 'subir' ? indice - 1 : indice + 1;
        if (destino < 0 || destino >= hermanos.length) return;
        if (boton.dataset.mover === 'subir') {
          lista.insertBefore(foto, hermanos[destino]);
        } else {
          lista.insertBefore(hermanos[destino], foto);
        }
        renumerar();
        // El foco se queda en el mismo botón, ya en su nueva posición.
        boton.focus();
        return;
      }

      const eliminar = evento.target.closest('[data-eliminar]');
      if (eliminar) {
        // El botón es un `submit` del formulario de borrado de esa foto: sin
        // JavaScript borra de una vez (la forma clásica). Con JavaScript se
        // detiene para preguntar antes, dentro de la tarjeta y sin el
        // `confirm()` del navegador, que un lector de pantalla no puede leer.
        evento.preventDefault();
        const foto = eliminar.closest('[data-foto]');
        const confirmar = foto.querySelector('[data-confirmar]');
        if (confirmar) {
          confirmar.hidden = false;
          eliminar.hidden = true;
          confirmar.querySelector('.galeria-admin__confirmar-si').focus();
        }
        return;
      }

      const cancelar = evento.target.closest('[data-cancelar]');
      if (cancelar) {
        const foto = cancelar.closest('[data-foto]');
        foto.querySelector('[data-confirmar]').hidden = true;
        foto.querySelector('[data-eliminar]').hidden = false;
        foto.querySelector('[data-eliminar]').focus();
      }
    });

    lista.addEventListener('change', (evento) => {
      if (evento.target.matches('input[name="principal"]')) {
        lista.querySelectorAll('[data-foto]').forEach((foto) => {
          const marcada = foto.querySelector('input[name="principal"]').checked;
          foto.classList.toggle('es-principal', marcada);
        });
        marcarPendiente(huella() !== inicial);
      }
    });

    // Cambios sin guardar: navegador, cierre de la ficha y envío de otro formulario.
    const salir = (evento) => {
      if (guardando || huella() === inicial) return;
      evento.preventDefault();
      evento.returnValue = '';
      return '';
    };
    window.addEventListener('beforeunload', salir);

    formulario.addEventListener('submit', () => {
      guardando = true;
      marcarPendiente(false);
      guardar.disabled = true;
      guardar.textContent = 'Guardando…';
    });

    renumerar();
  }

  /* ─── Arranque (una vez por bloque) ──────────────────────────── */

  bloques.forEach((bloque) => {
    if (bloque.dataset.galeriaLista) return;
    bloque.dataset.galeriaLista = '1';
    const cfg = configuracion(bloque);
    if (!cfg) return;
    prepararCarga(bloque, cfg);
    prepararOrden(bloque, cfg);
  });
})();
