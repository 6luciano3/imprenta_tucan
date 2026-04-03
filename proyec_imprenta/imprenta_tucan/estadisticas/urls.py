from django.urls import path
from . import views
app_name = "estadisticas"
urlpatterns = [
    path("", views.dashboard_estadisticas, name="dashboard"),
    path("api/pedidos-por-estado/", views.api_pedidos_por_estado, name="api_pedidos_por_estado"),
    path("api/ingresos-por-mes/", views.api_ingresos_por_mes, name="api_ingresos_por_mes"),
    path("api/top-productos/", views.api_top_productos, name="api_top_productos"),
    path("api/kpis/", views.api_kpis, name="api_kpis"),
    path("api/top-clientes-score/", views.api_top_clientes_score, name="api_top_clientes_score"),
    path("api/insumos-urgentes/", views.api_insumos_urgentes, name="api_insumos_urgentes"),
    path("api/proyeccion-demanda/", views.api_proyeccion_demanda, name="api_proyeccion_demanda"),
    path("api/resumen-inteligencia/", views.api_resumen_inteligencia, name="api_resumen_inteligencia"),
    path("api/descriptiva/clientes/", views.api_estadistica_clientes, name="api_desc_clientes"),
    path("api/descriptiva/pedidos/", views.api_estadistica_pedidos, name="api_desc_pedidos"),
    path("api/descriptiva/productos/", views.api_estadistica_productos, name="api_desc_productos"),
    path("api/descriptiva/insumos/", views.api_estadistica_insumos, name="api_desc_insumos"),
    path("api/descriptiva/presupuestos/", views.api_estadistica_presupuestos, name="api_desc_presupuestos"),
    path("api/descriptiva/proveedores/", views.api_estadistica_proveedores, name="api_desc_proveedores"),
    path("api/descriptiva/compras/", views.api_estadistica_compras, name="api_desc_compras"),
    path('informe-pdf/pedidos/', views.informe_pdf_pedidos, name='informe_pdf_pedidos'),
    path('informe-pdf/clientes/', views.informe_pdf_clientes, name='informe_pdf_clientes'),
    path('informe-pdf/productos/', views.informe_pdf_productos, name='informe_pdf_productos'),
    path('informe-pdf/proveedores/', views.informe_pdf_proveedores, name='informe_pdf_proveedores'),
    path('informe-pdf/insumos/', views.informe_pdf_insumos, name='informe_pdf_insumos'),
    path('informe-pdf/compras/', views.informe_pdf_compras, name='informe_pdf_compras'),
    path('informe-pdf/presupuestos/', views.informe_pdf_presupuestos, name='informe_pdf_presupuestos'),
]