def to_python_type(value):
    if hasattr(value, "tolist") and not isinstance(value, (str, bytes, bytearray)):
        try:
            return value.tolist()
        except Exception:
            pass
    if hasattr(value, "item"):
        try:
            return value.item()
        except Exception:
            pass
    return value


def sanitize_response(obj):
    if isinstance(obj, dict):
        return {k: sanitize_response(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [sanitize_response(i) for i in obj]
    if isinstance(obj, tuple):
        return [sanitize_response(i) for i in obj]
    return to_python_type(obj)
