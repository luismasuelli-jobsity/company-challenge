from django.urls import path
from . import views, api

app_name = 'chatrooms'
urlpatterns = [
    path('', views.index, name='index'),

    # API endpoints:
    path('profile', api.MyProfileView.as_view(), name="profile"),
    path('login', api.UserLoginView.as_view(), name="login"),
    path('register', api.UserCreateView.as_view(), name="register"),
    path('logout', api.UserLogoutView.as_view(), name="logout")
]
