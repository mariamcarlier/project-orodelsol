document.addEventListener('click', async (event) => {
  if (!(event.target instanceof Element)) return;

  const button = event.target.closest('.js-confirm-delete');
  if (!button) return;

  const formId = button.dataset.confirmForm;
  const form = formId ? document.getElementById(formId) : null;
  if (!(form instanceof HTMLFormElement)) {
    console.error('No se encontró el formulario POST asociado al botón de eliminación.');
    return;
  }

  if (!window.Swal) {
    console.error('SweetAlert2 no se cargó; se cancela la eliminación por seguridad.');
    return;
  }

  const itemName = button.dataset.itemName || 'este elemento';
  const result = await window.Swal.fire({
    title: '¿Eliminar registro?',
    text: `Se eliminará "${itemName}". Esta acción no se puede deshacer.`,
    icon: 'warning',
    showCancelButton: true,
    confirmButtonText: 'Sí, eliminar',
    cancelButtonText: 'Cancelar',
    reverseButtons: true,
    focusCancel: true,
    confirmButtonColor: '#785041',
    cancelButtonColor: '#9a7e68',
    background: '#fffefa',
    color: '#2c1a10'
  });

  if (result.isConfirmed) {
    form.requestSubmit();
  }
});
