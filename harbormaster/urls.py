from django.conf.urls import url

from . import views

urlpatterns = [
    url(r'^list$', views.list, name='list'),
    url(r'^list/active/ships$', views.list, {'active': 'active ships'}, name='list_active_ships'),
    url(r'^list/active/other$', views.list, {'active': 'active other'}, name='list_active_other'),
    url(r'^list/historic/ships$', views.list, {'active': 'historic ships'}, name='list_historic_ships'),
    url(r'^list/historic/other$', views.list, {'active': 'historic other'}, name='list_historic_other'),
    url(r'^input$', views.input, name='input'),
    url(r'^input/(?P<collection_label>[\w\- ]+)$', views.input),
    url(r'^map$', views.map, name='map'),
    url(r'^json/contact/(?P<mmsi>[\d]+)$', views.getContactJson, name="get_contact_json"),
    url(r'^reprocess$', views.reprocess, name='reprocess'),
]