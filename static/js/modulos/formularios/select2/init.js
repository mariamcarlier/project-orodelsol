$(document).ready(function () {
  const selects = $('.select2');
  if (!selects.length) return;

  if (!$.fn.select2) {
    console.error('Select2 no se cargó; los campos de selección no se pudieron mejorar.');
    return;
  }

  selects.select2({
    placeholder: 'Selecciona una colección',
    width: '100%'
  });
});
