$(function () {
  const table = $('#tabla-productos');
  if (!table.length) return;

  if (!$.fn.DataTable) {
    console.error('DataTables no se cargó; no se puede inicializar el listado de productos.');
    return;
  }

  table.DataTable({
    pageLength: 8,
    lengthMenu: [8, 15, 25],
    language: {
      emptyTable: 'Aún no hay productos registrados.',
      info: 'Mostrando _START_ a _END_ de _TOTAL_ productos',
      infoEmpty: 'Mostrando 0 productos',
      infoFiltered: '(filtrado de _MAX_ productos en total)',
      lengthMenu: 'Mostrar _MENU_',
      loadingRecords: 'Cargando...',
      processing: 'Procesando...',
      search: 'Buscar:',
      zeroRecords: 'No se encontraron productos.',
      paginate: {
        first: 'Primera',
        last: 'Última',
        next: 'Siguiente',
        previous: 'Anterior'
      }
    }
  });
});
