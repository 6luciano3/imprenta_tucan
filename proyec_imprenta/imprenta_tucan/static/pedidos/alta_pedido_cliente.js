// Autocompleta datos del cliente al seleccionarlo en el formulario de pedido

document.addEventListener('DOMContentLoaded', function() {
    const clienteSelect = document.getElementById('id_cliente');
    const razonSocialInput = document.getElementById('razonSocialCliente');
    const cuitInput = document.getElementById('cuitCliente');
    const emailInput = document.getElementById('emailCliente');
    const telefonoInput = document.getElementById('telefonoCliente');

    // Debes exponer un diccionario de clientes en el template
    if (!window.clientesData) return;

    function actualizarDatosCliente() {
        const clienteId = parseInt(clienteSelect.value);
        const datos = window.clientesData.find(c => c.id === clienteId);
        if (datos) {
            razonSocialInput.value = datos.razon_social || '';
            // Si tienes un campo CUIT real, usa datos.cuit, si no, deja vacío o usa otro campo
            cuitInput.value = datos.cuit || '';
            emailInput.value = datos.email || '';
            telefonoInput.value = datos.telefono || '';
        } else {
            razonSocialInput.value = '';
            cuitInput.value = '';
            emailInput.value = '';
            telefonoInput.value = '';
        }
    }

    clienteSelect.addEventListener('change', actualizarDatosCliente);
    // Inicializar si ya hay valor
    actualizarDatosCliente();
});
