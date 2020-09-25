from django.urls import path
from . import views, api

app_name = 'chatrooms'
urlpatterns = [
    path('', views.welcome, name='welcome'),
    path('goodbye', views.goodbye, name='goodbye'),
    path('main', views.main, name='main'),

    # API endpoints:
    path('login', api.UserLoginView.as_view()),
    path('register', api.UserCreateView.as_view()),
    path('logout', api.UserLogoutView)
]
