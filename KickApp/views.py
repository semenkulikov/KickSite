from django.shortcuts import render
import requests
from django.http import JsonResponse, HttpResponseBadRequest
from django.views.decorators.http import require_GET

# Create your views here.

def kick_chat(request):
    return render(request, 'KickApp/chat.html')

def kick_index(request):
    return render(request, 'KickApp/index.html')

@require_GET
def channel_info(request):
    channel_name = request.GET.get('channel_name')
    if not channel_name:
        return HttpResponseBadRequest('Missing channel_name')
    url = f'https://kick.com/api/v2/channels/{channel_name}'
    resp = requests.get(url)
    return JsonResponse(resp.json(), safe=False)

@require_GET
def channel_stream(request):
    channel_id = request.GET.get('channel_id')
    if not channel_id:
        return HttpResponseBadRequest('Missing channel_id')
    url = f'https://kick.com/api/v2/channels/{channel_id}/livestream'
    resp = requests.get(url)
    return JsonResponse(resp.json(), safe=False)

@require_GET
def streams_list(request):
    # Прокси для получения списка стримов с kick.com
    url = 'https://kick.com/api/v2/livestreams'
    resp = requests.get(url)
    return JsonResponse(resp.json(), safe=False)

# TODO: добавить views для управления KickAccount, если нужно (list/create/delete)
