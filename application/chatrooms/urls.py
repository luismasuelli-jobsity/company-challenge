from django.urls import path
from . import views

app_name = 'chatrooms'
urlpatterns = [
    path('', views.welcome, name='welcome'),
    path('goodbye', views.goodbye, name='goodbye'),
    path('main', views.main, name='main')
]
