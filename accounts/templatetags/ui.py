from django import template

register = template.Library()


@register.filter
def as_input(bound_field):
    """Render a form field with the designv2 `input` class (allauth builds its own forms, so we cannot set it in __init__)."""
    return bound_field.as_widget(attrs={'class': 'input'})
