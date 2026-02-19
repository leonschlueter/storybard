import structlog

log = structlog.get_logger()

MAX_LEN = 8000  # avoid terminal flooding

def log_llm_input(role: str, system: str, user: str):
    log.info(
        "llm_input",
        role=role,
        system=system[:MAX_LEN],
        user=user[:MAX_LEN],
    )

def log_llm_output(role: str, output):
    try:
        data = output.model_dump()
    except Exception:
        data = str(output)

    log.info(
        "llm_output",
        role=role,
        output=data,
    )
