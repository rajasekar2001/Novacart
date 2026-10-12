"""Readable, escaped-friendly rows from nested product specifications."""
from django import template
from django.utils.text import capfirst

register = template.Library()


def humanize(value):
    return capfirst(str(value).replace("_", " ").replace("-", " ").strip())


@register.filter
def flatten_specifications(specifications):
    """Return (label, value) pairs, including nested dictionaries and lists."""
    rows = []

    def walk(value, path=""):
        if isinstance(value, dict):
            for key, child in value.items():
                label = f"{path} / {humanize(key)}" if path else humanize(key)
                walk(child, label)
        elif isinstance(value, (list, tuple)):
            if all(not isinstance(item, (dict, list, tuple)) for item in value):
                rows.append((path, ", ".join(format_scalar(item) for item in value)))
            else:
                for index, child in enumerate(value, start=1):
                    walk(child, f"{path} / {index}")
        elif value is not None and value != "":
            rows.append((path, format_scalar(value)))

    def format_scalar(value):
        if value is True:
            return "Yes"
        if value is False:
            return "No"
        if value is None:
            return "Not specified"
        return str(value)

    if isinstance(specifications, (dict, list, tuple)):
        walk(specifications)
    return rows
