# quoteflow/context_processors.py

from .models import UserUpdateStatus

def notifications_context(request):
    if request.user.is_authenticated:
        unread_count = UserUpdateStatus.objects.filter(user=request.user, has_read=False).count()
        # Pega as 5 últimas notificações não lidas para exibir no dropdown
        unread_list = UserUpdateStatus.objects.filter(user=request.user, has_read=False).select_related('post').order_by('-post__publication_date')[:5]
        
        return {
            'unread_updates_count': unread_count,
            'unread_updates_list': unread_list,
        }
    return {}