// Script para setear automáticamente la fecha de entrega sumando 10 días a la fecha de pedido


document.addEventListener('DOMContentLoaded', function() {
    const fechaPedidoInput = document.getElementById('fechaPedido');
    const fechaEntregaInput = document.getElementById('id_fecha_entrega');

    if (fechaPedidoInput && fechaEntregaInput) {
        function sumarDias(fecha, dias) {
            const nueva = new Date(fecha);
            nueva.setDate(nueva.getDate() + dias);
            return nueva.toISOString().slice(0, 10);
        }

        function actualizarEntrega() {
            const valor = fechaPedidoInput.value;
            if (valor) {
                fechaEntregaInput.value = sumarDias(valor, 10);
            }
        }

        fechaPedidoInput.addEventListener('change', actualizarEntrega);
        // Inicializar si ya hay valor
        actualizarEntrega();
    }
});
