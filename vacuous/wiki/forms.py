from django import forms
from vacuous.wiki.models import Page

class PageForm(forms.ModelForm):
    class Meta:
        model = Page
        fields = ('text',)
        
    message = forms.CharField()