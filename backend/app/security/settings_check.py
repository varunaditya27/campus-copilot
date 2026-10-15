import re

_ORIGIN = re.compile(r"^https?://[A-Za-z0-9.-]+(:\d{1,5})?$")


def origin_problems(origins: list[str]) -> list[str]:
    """What is wrong with the allowed origins: each must look like https://host or http://host:port, with no path."""
    problems = []
    for origin in origins:
        if origin == "*":
            problems.append("CORS_ORIGINS must name the sites allowed to call the API, not '*' (cookies are sent with the requests).")
        elif not _ORIGIN.match(origin):
            problems.append(f"CORS_ORIGINS has '{origin}', which is not an origin like https://campus.example.org (a scheme, '://', a host, no path).")
    return problems


def production_problems(
    environment: str, origins: list[str], cookie_secure: bool, jwt_secret_set: bool
) -> list[str]:
    """What must be fixed before the application may run in production. Empty outside production."""
    if environment != "production":
        return []
    problems = origin_problems(origins)
    problems += [f"CORS_ORIGINS has '{o}': production must use https." for o in origins if o.startswith("http://")]
    if not cookie_secure:
        problems.append("COOKIE_SECURE must be true in production, so the session cookie is only sent over HTTPS.")
    if not jwt_secret_set:
        problems.append("JWT_SECRET must be set in production (openssl rand -hex 32), or every restart signs everyone out.")
    return problems
