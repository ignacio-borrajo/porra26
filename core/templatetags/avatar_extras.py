from django import template

register = template.Library()


@register.filter
def avatar_hue(user) -> int:
    """Replica el algoritmo del prototipo: charCode del último char del id × 47 mod 360."""
    pk = getattr(user, "pk", None)
    pk_str = str(pk) if pk is not None else "?"
    return (ord(pk_str[-1]) * 47) % 360


@register.filter
def get_item(mapping, key):
    """Acceso a un dict por clave (para `top_users|get_item:r.top_user_id`)."""
    if mapping is None:
        return None
    try:
        return mapping.get(key)
    except AttributeError:
        return None
