# 💍 Joyas Oro del Sol

> **Joyas Oro del Sol** es una plataforma web de e-commerce y gestión para una joyería especializada en **anillos de oro 18K**, con venta al detal (B2C) y al por mayor (B2B), y un proceso de producción basado en moldes y fundición.

Proyecto de formación — SENA, Tecnólogo en Análisis y Desarrollo de Software (ADSO).

---

## 📚 Contenido

1. [Stack tecnológico](#-stack-tecnológico)
2. [Puesta en marcha](#-puesta-en-marcha)
3. [Estructura del proyecto](#-estructura-del-proyecto)
4. [Flujo de trabajo: Jira → rama → commit → PR](#-flujo-de-trabajo)
5. [Convención de ramas](#-convención-de-ramas)
6. [Convención de commits](#-convención-de-commits)
7. [Definición de "Terminada"](#-definición-de-terminada)
8. [Reglas para migraciones y base de datos](#-migraciones-y-base-de-datos)
9. [Seguridad y archivos que nunca se suben](#-seguridad)
10. [Consejos de buenas prácticas](#-consejos-de-buenas-prácticas)

---

## 🛠️ Stack tecnológico

| Capa | Tecnología |
| :--- | :--- |
| Backend | Python + Django (templates del servidor) |
| Autenticación | Modelo de usuario propio (`usuarios.Usuario`) + django-allauth (registro y Google) |
| Base de datos | SQLite (desarrollo) |
| Frontend | HTML, CSS (variables `--color-*` en `tokens.css`), JavaScript modular |
| Gestión | Jira (proyecto **JODS**) + GitHub |

---

## 🚀 Puesta en marcha

```bash
# 1. Clonar y entrar
git clone https://github.com/mariamcarlier/project-orodelsol.git
cd project-orodelsol

# 2. Entorno virtual
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

# 3. Dependencias
pip install -r requirements.txt

# 4. Variables de entorno: crea un archivo .env en la raíz (NO se sube a Git)
#    EMAIL_HOST_USER=tu_correo@gmail.com
#    EMAIL_HOST_PASSWORD=tu_clave_de_aplicacion
#    DJANGO_DEBUG=True
#    DJANGO_SECRET_KEY=una_clave_larga_y_aleatoria   (obligatoria si DEBUG=False)
#    GOOGLE_OAUTH_CLIENT_ID= / GOOGLE_OAUTH_CLIENT_SECRET=   (opcionales, van juntas)

# 5. Base de datos y datos base
python manage.py migrate
python manage.py seed_tallas_materiales
python manage.py createsuperuser

# 6. Ejecutar
python manage.py runserver
```

### Comandos del día a día

| Qué quieres hacer | Comando |
| :--- | :--- |
| Correr todas las pruebas | `python manage.py test` |
| Correr pruebas de una app | `python manage.py test usuarios` |
| Crear migraciones tras cambiar un modelo | `python manage.py makemigrations` |
| Revisar el proyecto antes de subir | `python manage.py check` |

---

## 🗂️ Estructura del proyecto

```text
project-orodelsol/
├── app/             # Configuración del proyecto (settings, urls)
├── core/            # Catálogo: colecciones, productos, variantes, tallas, materiales + panel admin
├── usuarios/        # Usuario, roles, perfil, registro, login, "Mi cuenta"
├── configuracion/   # Parámetros, impuestos, monedas, idiomas, envíos, pagos, políticas, documentos
├── templates/       # base.html, partials/ (header, footer), admin_custom/, usuarios/, registration/
├── static/          # css/ · js/ · img/
└── manage.py
```

> 💡 **Regla de oro:** una carpeta = una responsabilidad. Si un archivo empieza a mezclar temas (por ejemplo, CSS de header dentro de `styles.css`), divídelo.

---

## 🔄 Flujo de trabajo

Jira es el mapa del proyecto. Cada pieza de código debe poder rastrearse hasta una historia o una necesidad técnica justificada.

```text
Historia en Jira (JODS-123)
        ↓
Rama nueva desde main
        ↓
Commits pequeños (con la clave de Jira)
        ↓
Pruebas + criterios de aceptación
        ↓
Pull Request → revisión → merge a main
        ↓
Historia → "Terminada"
```

1. **Elige** la historia (por ejemplo `JODS-197` = CFG-08 Políticas comerciales).
2. **Actualiza** `main` y crea la rama: `git switch main && git pull && git switch -c feature/JODS-197-politicas-comerciales`
3. **Trabaja** en commits pequeños.
4. **Prueba** (`python manage.py test`) y valida cada escenario de los criterios de aceptación.
5. **Abre el Pull Request** y enlázalo a la historia.
6. **Mueve** la historia a *Terminada* solo cuando el código esté en `main`.

---

## 🌿 Convención de ramas

Formato: `<tipo>/<CLAVE-JIRA>-<descripcion-corta-en-minusculas>`

| Prefijo | Uso | Ejemplo |
| :--- | :--- | :--- |
| `feature/` | Nueva funcionalidad (historia) | `feature/JODS-195-medios-de-pago` |
| `fix/` | Corrección de error | `fix/JODS-176-limite-intentos-login` |
| `refactor/` | Reorganizar sin cambiar comportamiento | `refactor/panel-admin-menu-lateral` |
| `docs/` | Solo documentación | `docs/readme-convenciones` |
| `chore/` | Configuración, dependencias | `chore/actualizar-requirements` |

Reglas:

- ❌ **Nunca** trabajes directamente en `main`.
- ✅ Una rama = una historia (o un grupo muy pequeño de tareas relacionadas).
- ✅ Ramas cortas: si una rama vive más de una semana, divídela.
- ✅ Antes de abrir el PR, trae los cambios de `main`: `git fetch && git merge origin/main`.

---

## 🛠️ Convención de commits

Seguimos [Conventional Commits](https://www.conventionalcommits.org/) para que el historial se lea como una bitácora del proyecto.

### 🏷️ Tipos

| Tipo | Categoría | Descripción | Ejemplo de uso |
| :---: | :--- | :--- | :--- |
| 🚀 | **`feat`** | Nueva funcionalidad | `feat(productos): agregar variantes por talla y material` |
| 🐛 | **`fix`** | Corrección de un error | `fix(login): bloquear tras 5 intentos fallidos` |
| 🎨 | **`style`** | CSS o formato (sin cambiar lógica) | `style(header): ajustar barra de categorías en móvil` |
| ♻️ | **`refactor`** | Reestructurar sin cambiar el comportamiento | `refactor(panel): separar menú lateral en grupos` |
| 📝 | **`docs`** | Documentación | `docs: actualizar guía de puesta en marcha` |
| 🔧 | **`chore`** | Configuración, paquetes, tareas | `chore(deps): fijar versiones en requirements.txt` |
| 🧪 | **`test`** | Pruebas | `test(configuracion): probar versionado de plantillas` |
| ⚡ | **`perf`** | Rendimiento / consultas a la BD | `perf(catalogo): usar select_related en el listado` |
| 📦 | **`build`** | Construcción o despliegue | `build: preparar settings para producción` |
| 👷 | **`ci`** | Integración continua | `ci: ejecutar pruebas en GitHub Actions` |
| ⏪ | **`revert`** | Revertir un commit previo | `revert: "feat(carrito): agregar reserva de stock"` |

### 📍 Módulos (scope) sugeridos

Usa el nombre del módulo de la matriz funcional para que el historial coincida con Jira:

`catalogo` · `categorias` · `productos` · `colecciones` · `carrito` · `checkout` · `pagos` · `pedidos` · `clientes` · `usuarios` · `perfil` · `auth` · `roles` · `mayoristas` · `inventario` · `logistica` · `descuentos` · `notificaciones` · `resenas` · `marketing` · `personalizacion` · `reportes` · `config` · `panel` · `ui`

### 📐 Formato del mensaje

```text
<tipo>(<módulo opcional>): <descripción breve en minúsculas y en presente>

[cuerpo opcional: qué cambia y POR QUÉ, no cómo]

[pie opcional: clave de Jira]
```

**Ejemplo completo:**

```text
feat(config): agregar políticas comerciales como registro único

Centraliza el monto mínimo B2B/B2C y el envío gratis en un solo
modelo para que checkout y carrito consulten la misma regla.

Refs: JODS-197
```

### 🔗 Enlazar con Jira

Incluye la clave de la historia en el pie del commit (o en el nombre de la rama). Así Jira muestra los commits dentro de la historia y puedes demostrar que cada historia terminada tiene código real.

```text
feat(pagos): registrar comprobante de transferencia

Refs: JODS-58
```

### ✅ Buenas prácticas de commits

- **Un commit = un cambio lógico.** Si en el mensaje necesitas la palabra "y", probablemente son dos commits.
- **Descripción en presente e imperativo corto:** "agregar", "corregir", "ajustar" (no "agregué" ni "arreglando").
- **Máximo ~72 caracteres** en la primera línea.
- **No mezcles tipos:** no metas un `style` dentro de un `feat`. Separa el CSS del cambio de lógica.
- **No uses mensajes vagos:** `fix`, `cambios`, `listo`, `prueba`, `arreglos varios` ❌
- **Revisa antes de confirmar:** `git status` y `git diff --staged` para ver exactamente qué subes.
- **Evita `git add .` a ciegas.** Agrega los archivos que realmente son parte del cambio.

| ❌ Mal | ✅ Bien |
| :--- | :--- |
| `cambios` | `fix(carrito): evitar cantidades negativas` |
| `Arreglé el login y el header` | Dos commits: `fix(login): ...` y `style(header): ...` |
| `feat: todo el módulo de pagos` | Varios commits: modelo, formulario, vista, pruebas |

---

## ✔️ Definición de "Terminada"

Una historia **solo** se mueve a *Terminada* en Jira cuando cumple **todo** esto:

- [ ] El código está en `main` (PR aprobado y fusionado).
- [ ] Cada **escenario de los criterios de aceptación** fue probado (el exitoso y el alterno/de error).
- [ ] Existen **pruebas automáticas** que cubren el comportamiento (`python manage.py test` en verde).
- [ ] Si cambió un modelo, hay **migración** incluida en el commit.
- [ ] Los permisos están verificados: un usuario sin el rol correcto **no** puede ejecutar la acción.
- [ ] Los textos para el usuario están en español y los mensajes de error son claros.
- [ ] La interfaz funciona en móvil y respeta el estilo visual (tokens de `tokens.css`).
- [ ] Las subtareas `[Backend]`, `[Frontend]` y `[Pruebas]` de la historia están completas.

> 🎓 **Por qué importa:** Jira es evidencia académica y profesional. Una historia marcada como terminada sin código real resta credibilidad a todo el tablero.

---

## 🗄️ Migraciones y base de datos

- ✅ **Sí se suben** las migraciones (`*/migrations/00xx_*.py`).
- ❌ **Nunca edites** una migración que ya se aplicó o se compartió. Si hay un error, crea una **migración nueva** que lo corrija.
- ❌ **No se sube** `db.sqlite3` (cada persona tiene su base local).
- ✅ Cambios de modelo y su migración van **en el mismo commit**.
- ✅ Datos base (tallas, materiales) se cargan con comandos idempotentes (`seed_tallas_materiales`), no copiando la base.
- ⚠️ Si dos personas crean migraciones a la vez en la misma app, Django pedirá una *migración de fusión* (`python manage.py makemigrations --merge`). Coordina antes de tocar la misma app.
- 💡 Antes de borrar un campo o cambiar su tipo, piensa en los datos existentes: primero añade como opcional, luego rellena, luego restringe (así se hizo con el `codigo` de productos).

---

## 🔐 Seguridad

### Nunca subas a Git

| Archivo / dato | Por qué |
| :--- | :--- |
| `.env` | Contiene claves de correo, Google OAuth y `SECRET_KEY` |
| `db.sqlite3` | Datos reales de usuarios y pedidos |
| `media/` | Archivos subidos (comprobantes, certificados, fotos) |
| `__pycache__/`, `*.pyc` | Archivos generados |
| `.venv/` | Entorno virtual local |

- 🚨 **Si subes una clave por error**, no basta con borrarla en un commit nuevo: queda en el historial. **Cámbiala de inmediato** en el servicio (Google, Gmail, etc.).
- ✅ Las claves se leen siempre con `os.environ.get(...)`, nunca escritas en el código.
- ✅ En producción: `DJANGO_DEBUG=False`, `DJANGO_SECRET_KEY` propia y `ALLOWED_HOSTS` explícitos.
- ✅ Datos de tarjetas: **nunca** se guardan en el sistema (lo exige el backlog de pagos).

---

## 💡 Consejos de buenas prácticas

### Organización del trabajo
1. **Un sprint, un incremento utilizable.** Cada sprint debe terminar con algo que se pueda ejecutar y demostrar, no solo configuración.
2. **Respeta las dependencias.** Catálogo → carrito → checkout → pago → pedido → logística → reportes. Programar al revés genera trabajo que se rehace.
3. **Mide tu velocidad real.** Los puntos de historia son estimaciones; tras los primeros sprints ajusta cuánto cabe realmente.
4. **Escribe primero la prueba del criterio de aceptación.** Si el escenario "Dado / Cuando / Entonces" no se puede probar, la historia está mal definida: pregunta antes de programar.

### Calidad del código
5. **Reutiliza, no copies.** Antes de crear un estilo o componente nuevo, revisa `tokens.css` y `components.css`.
6. **Nombres sin espacios** en carpetas y archivos (`inicio_sesion`, no `Inicio de Sesion`): los espacios causan errores silenciosos en rutas.
7. **JavaScript modular:** un archivo por responsabilidad, sin `onclick="..."` dentro del HTML.
8. **Validación doble:** valida en el formulario del navegador **y** en el servidor. El servidor es el que manda.
9. **Permisos en el servidor.** Ocultar un botón no es seguridad; la vista debe rechazar al usuario sin permiso.
10. **Accesibilidad desde el inicio:** etiquetas en formularios, contraste suficiente, foco visible, navegación por teclado.

### Diseño y experiencia (e-commerce premium)
11. **Menos es más.** Mucho espacio en blanco, tipografía elegante, una sola acción principal por pantalla (inspiración: Glamira, Enigma, Entrelazos).
12. **Fotografía primero.** En joyería vende la imagen: usa imágenes de buena calidad, mismo encuadre y fondo coherente.
13. **Reduce fricción en la compra:** pocos pasos de checkout, precios claros en COP, tiempos de entrega visibles y certificado de autenticidad destacado.
14. **Prueba en celular.** La mayoría de tus compradores navegarán desde el teléfono.

### Trabajo en equipo
15. **Pull Requests pequeños** (idealmente menos de ~400 líneas): se revisan mejor y se fusionan más rápido.
16. **Revisa el código de tus compañeros** y deja comentarios concretos y amables.
17. **Sincroniza seguido:** `git pull` antes de empezar el día y antes de abrir un PR.
18. **Comunica los cambios que afectan a otros** (modelos compartidos, `base.html`, `tokens.css`).
19. **Documenta decisiones**, no solo código: por qué se eligió una regla de negocio queda en el PR o en este README.

### Antes de cada Pull Request

```text
□ python manage.py check            → sin errores
□ python manage.py test             → todo en verde
□ git status                        → no hay archivos que no deban subirse
□ Migraciones incluidas si cambié modelos
□ Commits con formato Conventional Commits + clave de Jira
□ Probé los escenarios de aceptación (éxito y error)
□ Revisé en móvil
```

---

## 👥 Equipo

Ivan Leonardo Gómez · Mariam Carlier Alvarado · Julian Andrés Univio · 

---

<sub>© 2026 Joyas Oro del Sol — Proyecto académico SENA ADSO.</sub>
