"""``{% if rock|visible_to:user %}``: hide a linked private Rock from people who are not on it."""
from django import template

register = template.Library()


@register.filter
def visible_to(rock, user):
    return bool(rock) and rock.is_visible_to(user)
