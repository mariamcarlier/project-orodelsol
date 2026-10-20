$(function () {
  const table = $('#tabla-colecciones');
  if (!table.length) return;

  if (!$.fn.DataTable) {
    console.error('DataTables no se cargó; no se puede inicializar el listado de colecciones.');
    return;
  }

  table.DataTable({
    pageLength: 8,
    lengthMenu: [8, 15, 25],
    language: {
      emptyTable: 'Aún no hay colecciones registradas.',
      info: 'Mostrando _START_ a _END_ de _TOTAL_ colecciones',
      infoEmpty: 'Mostrando 0 colecciones',
      infoFiltered: '(filtrado de _MAX_ colecciones en total)',
      lengthMenu: 'Mostrar _MENU_',
      loadingRecords: 'Cargando...',
      processing: 'Procesando...',
      search: 'Buscar:',
      zeroRecords: 'No se encontraron colecciones.',
      paginate: {
        first: 'Primera',
        last: 'Última',
        next: 'Siguiente',
        previous: 'Anterior'
      }
    }
  });
});
