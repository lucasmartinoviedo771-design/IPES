from django.contrib import admin
from .models import RequisitosIngreso

@admin.register(RequisitosIngreso)
class RequisitosIngresoAdmin(admin.ModelAdmin):
    list_display = ("inscripcion", "req_dni", "req_titulo_sec", "req_titulo_sup", "req_condicion", "creado")
    search_fields = ("inscripcion__id",)
