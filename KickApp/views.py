from django.shortcuts import render, redirect, get_object_or_404
import requests
from django.http import JsonResponse, HttpResponseBadRequest, HttpResponseForbidden
from django.views.decorators.http import require_GET
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.views.decorators.http import require_http_methods
from django.db import transaction, models
from .models import KickAccount, KickAccountAssignment
from ServiceApp.models import User, UserRole

# Create your views here.

@login_required
def kick_chat(request):
    return render(request, 'KickApp/chat.html')

def kick_index(request):
    return render(request, 'KickApp/index.html')

@login_required
@user_passes_test(lambda u: u.is_staff)
def kick_stats(request):
    return render(request, 'KickApp/stats.html')

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

@login_required
def kick_accounts_dashboard(request):
    """
    Дашборд для управления Kick аккаунтами
    """
    user = request.user
    
    # Проверяем права доступа
    if not (user.is_staff or user.is_admin):
        messages.error(request, 'У вас нет прав для доступа к управлению аккаунтами.')
        return redirect('kick_accounts_dashboard')
    
    if user.is_super_admin:
        # Супер админ видит все аккаунты
        kick_accounts = KickAccount.objects.all()
        assignments = KickAccountAssignment.objects.all()
        active_assignments = KickAccountAssignment.objects.filter(is_active=True)
        my_accounts = KickAccount.objects.filter(owner=user)
        my_assignments = KickAccountAssignment.objects.filter(assigned_by=user)
    elif user.is_admin:
        # Обычный админ видит ВСЕ аккаунты
        kick_accounts = KickAccount.objects.all()
        assignments = KickAccountAssignment.objects.all()
        active_assignments = KickAccountAssignment.objects.filter(is_active=True)
        my_accounts = KickAccount.objects.filter(owner=user)
        my_assignments = KickAccountAssignment.objects.filter(assigned_by=user)
    else:
        # Обычные пользователи не имеют доступа
        messages.error(request, 'У вас нет прав для доступа к управлению аккаунтами.')
        return redirect('kick_accounts_dashboard')
    
    # Обработка фильтра
    filter_type = request.GET.get('filter')
    if filter_type == 'my_assignments':
        kick_accounts = my_assignments.values_list('kick_account', flat=True)
        kick_accounts = KickAccount.objects.filter(id__in=kick_accounts)
        assignments = my_assignments
    
    context = {
        'kick_accounts': kick_accounts,
        'assignments': assignments,
        'active_assignments': active_assignments,
        'my_accounts': my_accounts,
        'my_assignments': my_assignments,
        'user': user,
    }
    
    return render(request, 'KickApp/kick_accounts_dashboard.html', context)

@login_required
def assign_kick_account(request, account_id):
    """
    Назначить Kick аккаунт пользователю
    """
    if not request.user.is_admin:
        messages.error(request, 'У вас нет прав для назначения аккаунтов.')
        return redirect('kick_accounts_dashboard')
    
    kick_account = get_object_or_404(KickAccount, id=account_id)
    
    if request.method == 'POST':
        user_id = request.POST.get('user_id')
        assignment_type = request.POST.get('assignment_type', 'admin_assigned')
        notes = request.POST.get('notes', '')
        
        try:
            user = User.objects.get(id=user_id)
            
            with transaction.atomic():
                assignment, created = KickAccountAssignment.objects.get_or_create(
                    kick_account=kick_account,
                    user=user,
                    defaults={
                        'assigned_by': request.user,
                        'assignment_type': assignment_type,
                        'notes': notes,
                        'is_active': True
                    }
                )
                
                if not created:
                    # Обновляем существующее назначение
                    assignment.assigned_by = request.user
                    assignment.assignment_type = assignment_type
                    assignment.notes = notes
                    assignment.is_active = True
                    assignment.save()
                
                messages.success(request, f'Аккаунт {kick_account.login} успешно назначен пользователю {user.username}')
                return redirect('kick_accounts_dashboard')
                
        except User.DoesNotExist:
            messages.error(request, 'Пользователь не найден.')
        except Exception as e:
            messages.error(request, f'Ошибка при назначении аккаунта: {str(e)}')
    
    # Получаем список пользователей для назначения
    if request.user.is_super_admin:
        users = User.objects.all()
    else:
        # Обычный админ может назначать только обычным пользователям
        users = User.objects.filter(role__name='user')
    
    context = {
        'kick_account': kick_account,
        'users': users,
    }
    
    return render(request, 'KickApp/assign_kick_account.html', context)

@login_required
def unassign_kick_account(request, assignment_id):
    """
    Отменить назначение Kick аккаунта
    """
    try:
        assignment = get_object_or_404(KickAccountAssignment, id=assignment_id)
        
        # Проверяем права
        if not (request.user.is_admin or 
                (request.user == assignment.user and assignment.can_user_edit)):
            messages.error(request, 'У вас нет прав для отмены этого назначения.')
            return redirect('kick_accounts_dashboard')
        
        if request.method == 'POST':
            # Удаляем назначение полностью
            account_login = assignment.kick_account.login
            user_username = assignment.user.username
            assignment.delete()
            
            messages.success(request, f'Назначение аккаунта {account_login} пользователю {user_username} отменено.')
            return redirect('kick_accounts_dashboard')
        
        context = {
            'assignment': assignment,
        }
        
        return render(request, 'KickApp/unassign_kick_account.html', context)
        
    except Exception as e:
        messages.error(request, f'Ошибка при отмене назначения: {str(e)}')
        return redirect('kick_accounts_dashboard')

@login_required
def add_own_kick_account(request):
    """
    Админ добавляет новый Kick аккаунт
    """
    print(f"[ADD_OWN_KICK_ACCOUNT] User: {request.user.username}")
    print(f"[ADD_OWN_KICK_ACCOUNT] Is admin: {request.user.is_admin}")
    print(f"[ADD_OWN_KICK_ACCOUNT] Role: {request.user.role.name if hasattr(request.user, 'role') and request.user.role else 'None'}")
    
    if not request.user.is_admin:
        messages.error(request, 'У вас нет прав для добавления аккаунтов.')
        return redirect('kick_accounts_dashboard')
    
    if request.method == 'POST':
        login = request.POST.get('login')
        token = request.POST.get('token')
        password = request.POST.get('password', '')
        
        print(f"[ADD_OWN_KICK_ACCOUNT] POST data: login={login}, token={'*' * len(token) if token else 'None'}")
        
        if not all([login, token]):
            messages.error(request, 'Пожалуйста, заполните все обязательные поля.')
            return redirect('add_own_kick_account')
        
        try:
            with transaction.atomic():
                # Создаем аккаунт
                kick_account = KickAccount.objects.create(
                    login=login,
                    token=token,
                    password=password,
                    owner=request.user
                )
                
                print(f"[ADD_OWN_KICK_ACCOUNT] Account created: {kick_account.id}")
                messages.success(request, f'Аккаунт {login} успешно добавлен.')
                return redirect('kick_accounts_dashboard')
                
        except Exception as e:
            print(f"[ADD_OWN_KICK_ACCOUNT] Error: {str(e)}")
            if "UNIQUE constraint failed" in str(e):
                messages.error(request, f'Аккаунт с логином {login} уже существует.')
            else:
                messages.error(request, f'Ошибка при добавлении аккаунта: {str(e)}')
    
    return render(request, 'KickApp/add_own_kick_account.html')

@login_required
@require_http_methods(["POST"])
def ajax_get_users(request):
    """
    AJAX endpoint для получения списка пользователей
    """
    if not request.user.is_admin:
        return JsonResponse({'error': 'Нет прав'}, status=403)
    
    search = request.POST.get('search', '')
    
    if request.user.is_super_admin:
        users = User.objects.all()
    else:
        # Обычные админы видят только обычных пользователей
        users = User.objects.filter(role__name='user')
    
    if search:
        users = users.filter(username__icontains=search)
    
    users_data = [{'id': user.id, 'username': user.username} for user in users[:10]]
    
    print(f"[AJAX_GET_USERS] Search: '{search}', Found users: {len(users_data)}")
    print(f"[AJAX_GET_USERS] User role: {request.user.role.name if hasattr(request.user, 'role') and request.user.role else 'None'}")
    print(f"[AJAX_GET_USERS] Is admin: {request.user.is_admin}")
    
    return JsonResponse({'users': users_data})
