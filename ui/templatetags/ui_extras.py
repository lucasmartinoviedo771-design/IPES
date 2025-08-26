from django import template
register = template.Library()

@register.filter
def classname(obj):
    return type(obj).__name__
