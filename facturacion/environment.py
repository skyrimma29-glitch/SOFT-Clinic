from contextvars import ContextVar


CURRENT_ENVIRONMENT_ID = ContextVar('current_environment_id', default=1)


def get_current_environment_id():
    return CURRENT_ENVIRONMENT_ID.get()


def set_current_environment_id(environment_id):
    return CURRENT_ENVIRONMENT_ID.set(int(environment_id))