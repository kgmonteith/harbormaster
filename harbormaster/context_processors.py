from harbormaster import secrets

def set_api_keys(request):
    return {'GOOGLE_MAPS_API_KEY': secrets.GOOGLE_MAPS_API_KEY}
