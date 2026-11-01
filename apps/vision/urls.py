from django.urls import path
from . import views

app_name = 'vision'

urlpatterns = [
    path('', views.VTODetailView.as_view(), name='detail'),
    path('print/', views.VTOPrintView.as_view(), name='print'),
    path('edit/<str:key>/', views.VTOSectionEditView.as_view(), name='section_edit'),
    path('core-values/add/', views.CoreValueCreateView.as_view(), name='cv_add'),
    path('core-values/<int:pk>/edit/', views.CoreValueUpdateView.as_view(), name='cv_edit'),
    path('core-values/<int:pk>/delete/', views.CoreValueDeleteView.as_view(), name='cv_delete'),
]
