def set_css_attribute(target: any, key: str, value: str) -> None:
    target.setProperty(key, value)
    target.style().unpolish(target)
    target.style().polish(target)
    return