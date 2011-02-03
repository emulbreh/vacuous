from django.conf.urls.defaults import *
from django.conf import settings

SLUG = r'[a-zA-Z0-9/_.-]+'

urlpatterns = patterns('vacuous.wiki.views',
    url(r'^$', 'page_list'),
    url(r'^wiki/(?P<slug>%s)$' % SLUG, 'view_page'),
    url(r'^wiki/(?P<slug>%s)~$' % SLUG, 'edit_page'),
    url(r'^history/(?P<slug>%s)$' % SLUG, 'page_history'),
    url(r'^git/(?P<repo_name>wiki)\.git/', include('vacuous.backends.dulwich.urls')),
)

if settings.DEVELOPMENT:
    urlpatterns += patterns('', 
        url(r'^static/(?P<path>.*)$', 'django.views.static.serve', {'document_root': '/Users/emulbreh/Projekte/Verlag/pbbx.net/lib/djff/static'}),
    )
    