from django.conf import settings
from django.http import HttpResponseRedirect
from django.core.urlresolvers import reverse
from django.shortcuts import get_object_or_404

from shrubbery.views import render

from vacuous.wiki.forms import PageForm
from vacuous.wiki.models import Page
from vacuous.backends import load_backend
from vacuous.transactions import commit_on_success


def page_list(request):
    return render(request, 'vacuous/wiki/page_list.html', {
        'pages': Page.objects.order_by('slug'),
    })


def view_page(request, slug=None):
    try:
        page = Page.objects.get(slug=slug)
    except Page.DoesNotExist:
        return HttpResponseRedirect(reverse('vacuous.wiki.views.edit_page', kwargs={'slug': slug}))

    return render(request, 'vacuous/wiki/view_page.html', {
        'page': page,
    })
    

def page_history(request, slug=None):
    page = get_object_or_404(Page, slug=slug)
    history = page.vacuous.history()

    return render(request, 'vacuous/wiki/page_history.html', {
        'page': page,
        'history': history,
    })


def edit_page(request, slug=None):
    try:
        page = Page.objects.get(slug=slug)
    except Page.DoesNotExist:
        page = None
        
    form = PageForm(request.POST or None, instance=page)
    
    if form.is_valid():
        with commit_on_success(message=form.cleaned_data['message'], committer='Johannes Dollinger <emulbreh@e6h.de>'):
            page = form.save(commit=False)
            page.slug = slug
            page.save()
        return HttpResponseRedirect(reverse('vacuous.wiki.views.view_page', kwargs={'slug': slug}))
        
    return render(request, 'vacuous/wiki/edit_page.html', {
        'slug': slug,
        'page': page,
        'form': form,
    })