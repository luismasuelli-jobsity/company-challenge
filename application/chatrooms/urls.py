from django.urls import path
from . import views, api

app_name = 'chatrooms'
urlpatterns = [
    path('', views.index, name='index'),

    # API endpoints:
    path('profile', api.MyProfileView.as_view()),
    path('login', api.UserLoginView.as_view()),
    path('register', api.UserCreateView.as_view()),
    path('logout', api.UserLogoutView)
]
