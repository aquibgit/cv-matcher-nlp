"""
URL configuration for cvmatch project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/4.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
# jobs/urls.py
from django.urls import path
from . import views

urlpatterns = [
    path("", views.requirements_list, name="home"),
    path("requirements/", views.requirements_list, name="requirements_list"),
    path("requirements/add/", views.add_requirement, name="add_requirement"),
    path("requirements/upload-cv/", views.upload_cv_view, name="upload_cv"),
    path("requirements/<int:pk>/", views.requirement_detail, name="requirement_detail"),
]

