import re


def render_template(template: str, data: dict) -> str:
    def replace_match(match: re.Match[str]):
        path_str = match.group(1)
        fallback_paths = path_str.split("|")
        for fallback_path in fallback_paths:
            fallback_path = fallback_path.strip()
            keys = fallback_path.split(".")
            current = data
            try:
                for key in keys:
                    if isinstance(current, dict):
                        current = current[key]
                    elif isinstance(current, list):
                        current = current[int(key)]
                    else:
                        raise KeyError(
                            f"Cannot access key '{key}' on non-dict/list value"
                        )
                if current is not None:
                    return str(current)
            except (KeyError, IndexError, ValueError, TypeError):
                continue
        return match.group(0)

    return re.compile(r"\{([^{}]+)\}").sub(replace_match, template)
