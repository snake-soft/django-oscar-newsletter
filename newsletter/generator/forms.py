from django import forms
from django.utils.translation import gettext_lazy as _
from apps.offer.models import ConditionalOffer
from ..models import Newsletter, Message


class MessageGeneratorForm(forms.Form):
    price = forms.BooleanField(
        label=_('Preis'),
        required=False,
        initial=True,
    )
    newsletter = forms.ChoiceField(
        label=_('Newsletter'),
        initial=None,
        required=False,
    )
    attach_message = forms.ChoiceField(
        label=_('Nachricht anhängen'),
        initial=None,
        required=False,
    )

    def __init__(self, request, *args, **kwargs):
        self.request = request
        super().__init__(*args, **kwargs)
        self.fields['newsletter'].choices = self.get_newsletter_choices()
        self.fields['attach_message'].choices = self.get_message_choices()

    def get_newsletter_choices(self):
        return [
            (None, 100 * '-'),
            *Newsletter.objects.values_list('id', 'title'),
        ]

    def get_message_choices(self):
        qs = Message.objects.order_by('-id').filter(submission=None)
        return [
            (None, 100 * '-'),
            *qs.values_list('id', 'title'),
        ]

    def clean(self):
        cleaned_data = super().clean()
        if not any((
            cleaned_data['newsletter'],
            cleaned_data['attach_message']
        )):
            raise forms.ValidationError(
                _('Entweder "Newsletter" oder "Nachricht kombinieren" muss '
                  'ausgewählt werden.'),
                code='missing_field',
            )
        if cleaned_data['newsletter']:
            cleaned_data['newsletter'] = Newsletter.objects.get(
                pk=cleaned_data['newsletter']
            )
        if cleaned_data['attach_message']:
            cleaned_data['attach_message'] = Message.objects.get(
                pk=cleaned_data['attach_message']
            )
        cleaned_data['offer'] = ConditionalOffer.objects.get(
                pk=self.request.POST['offer_pk']
            )
        return cleaned_data
