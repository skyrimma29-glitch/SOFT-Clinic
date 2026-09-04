from .environment import set_current_environment_id
from .models import Environment


class EnvironmentMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        environment_id = request.session.get('environment_id', 1)
        if not Environment.objects.filter(pk=environment_id).exists():
            environment_id = 1
            request.session['environment_id'] = environment_id
        set_current_environment_id(environment_id)
        request.environment = Environment.objects.get(pk=environment_id)
        return self.get_response(request)