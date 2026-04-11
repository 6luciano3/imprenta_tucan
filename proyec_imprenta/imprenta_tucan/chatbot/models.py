from django.db import models
from clientes.models import Cliente


class ConversacionChatbot(models.Model):
    """Guarda las conversaciones del chatbot con los clientes y el personal interno."""

    cliente = models.ForeignKey(
        Cliente,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='conversaciones_chatbot'
    )
    usuario = models.ForeignKey(
        'usuarios.Usuario',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='conversaciones_chatbot',
        help_text='Usuario interno (staff) que inició la conversación.',
    )
    session_id = models.CharField(max_length=100, blank=True, help_text="ID de sesión para usuarios sin login")
    mensaje = models.TextField()
    respuesta = models.TextField()
    es_cliente = models.BooleanField(default=True, help_text="True si es mensaje del cliente, False si es del bot")
    fecha = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-fecha']
        verbose_name = 'Conversación Chatbot'
        verbose_name_plural = 'Conversaciones Chatbot'
    
    def __str__(self):
        return f"Conversación {self.id} - {self.fecha.strftime('%d/%m/%Y %H:%M')}"
