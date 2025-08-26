from .auth_views import resolve_role

def role_from_request(request):
    role = request.session.get("active_role")
    if role:
        return {"active_role": role}
    if request.user.is_authenticated:
        role = resolve_role(request.user)
        request.session["active_role"] = role
        return {"active_role": role}
    return {"active_role": None}
