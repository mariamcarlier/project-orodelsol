document.addEventListener('DOMContentLoaded', () => {
  const messages = document.querySelectorAll('.js-django-messages > span');
  if (!messages.length) return;

  if (!window.Swal) {
    console.error('SweetAlert2 no se cargó; los mensajes de Django no se pudieron mostrar.');
    return;
  }

  messages.forEach((message) => {
    window.Swal.fire({
      toast: true,
      position: 'top-end',
      icon: message.dataset.icon || 'info',
      title: message.textContent.trim(),
      showConfirmButton: false,
      timer: 3800,
      timerProgressBar: true
    });
  });
});
