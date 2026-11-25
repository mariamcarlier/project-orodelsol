# 0003 · VM-18: por qué NO se implementó la cotización

**Estado:** pendiente de definición funcional
**Fecha:** 2026-11-19
**Historia:** VM-18 (colchón del sprint `mayoristas-epica`)

## Decisión

VM-18 **no se implementa** en este sprint. No se crean modelos, estados,
reglas comerciales ni persistencia. Lo único que se entrega es este
documento con el análisis de lo que haría falta.

## Por qué

El alcance de VM-18 no está definido en ningún sitio autorizado. Se buscó en
`docs/`, en los commits del sprint y en las decisiones registradas: no hay
enunciado funcional, ni criterios de aceptación, ni una decisión comercial
sobre qué produce el mayorista desde la ficha de producto.

Las reglas vigentes sí dicen tres cosas que acotan el problema:

1. **Los precios del catálogo B2B son referencias, no ofertas.** (DEC-03)
2. **La negociación de precios, cantidades y condiciones se hace fuera de la
   plataforma.**
3. **El pedido mayorista solo se registra después de cerrar y registrar la
   negociación mediante un asesor autorizado.**

De ahí se sigue que una cotización generada por el mayorista **no puede ser
el pedido**: sería un documento con precios que la plataforma no está
autorizada a fijar. Cualquier implementación tendría que decidir qué es
entonces, y esa decisión no está tomada.

Añadir un modelo ahora significaría inventar la regla comercial y crear deuda:
un esquema en base de datos es lo más caro de revertir del sprint.

## Qué haría falta para implementarla

Tres alternativas, con lo que ya existe en el código y lo que habría que
crear. Ninguna está implementada.

### Alternativa A — Cálculo en pantalla, sin persistencia

El mayorista elige variante y cantidad y ve el precio unitario con el tramo
aplicado. Nada se guarda.

| Pieza | Estado |
|---|---|
| `selectors.variantes_disponibles_de(producto)` | **ya existe** (VM-03) |
| `servicios.precio_con_tramo(precio, cantidad)` | **ya existe** (VM-16) |
| `selectors.tramo_para_cantidad(cantidad)` | **ya existe** (VM-16) |
| Plantilla de ficha + formulario GET | habría que crearla |
| Vista `DetalleProductoMayoristaView` | habría que crearla |

Es la única que **no contradice** las reglas vigentes: muestra un precio de
referencia calculado, con la etiqueta de DEC-03, y no promete nada. Aun así
requiere que la propietaria confirme que ver un precio por tramo no se
confunde con un precio en firme.

### Alternativa B — Cotización guardada

Se crea un documento con líneas (producto, variante, cantidad, precio
calculado) que el mayorista consulta después.

| Pieza | Estado |
|---|---|
| Cálculo de precio | **ya existe** |
| `SolicitudMayorista` como punto de partida | **ya existe** |
| Modelo `Cotizacion` + `LineaCotizacion` | habría que crearlos |
| Migración | habría que crearla |
| Estados y quién puede cambiarlos | **sin definir** |
| Permisos de consulta | **sin definir** |

Lo que falta no es código, es la regla: quién puede crear una cotización, si
caduca, si se puede modificar, y qué la convierte en pedido. Sin eso, el
modelo nacería con estados que nadie sabe cuándo usar.

### Alternativa C — Pedido formal

El modelo completo de pedido del que habla `docs/estrategia-negocio.md` §4
(con copia de precio, código y grabado en la línea, para que un cambio
posterior no reescriba un pedido anterior).

Exige, además de B: numeración, ciclo de vida, gestión de pagos y la
integración con el grabado que describe §2. Es una épica, no una historia de
colchón.

## Dependencias que ya estarían resueltas

Si se aprueba cualquiera de las tres, estas piezas ya están listas y no hay
que rehacerlas:

- Precio por tramo con DEC-18 (sin porcentaje no se calcula): `0005`/VM-16.
- Variantes disponibles y precio «Desde» con la misma fórmula que
  `precio_final`: VM-03.
- Solo MAYORISTA aprobado entra al canal: VM-03 (`AccesoMayoristaMixin`).
- Etiqueta de referencia obligatoria: DEC-03, ya aplicada en el catálogo.

## Qué haría falta decidir antes de tocar código

1. ¿Qué es exactamente lo que produce el mayorista: una vista, una
   cotización guardada o un pedido?
2. ¿Quién puede crear cada cosa y quién puede cambiarla?
3. ¿Los tramos se aplican por línea o sobre el total de unidades?
4. ¿Una cotización caduca? ¿En cuánto tiempo?
5. ¿Qué relación tiene con `SolicitudMayorista` y con el asesor autorizado
   que cierra la negociación?

Con esas cinco respuestas, la Alternativa A es trabajo de una historia
pequeña y las otras dos son historias propias con sus criterios.
