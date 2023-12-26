from django.views.generic.edit import FormView
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.shortcuts import redirect
from .forms import MessageGeneratorForm
from .utils import MessageGenerator


class SuperUserRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    def test_func(self):
        return self.request.user.is_superuser


class MessageGeneratorView(SuperUserRequiredMixin, FormView):
    methods = ['post']
    template_name = 'newsletter/message_generator_error.html'
    form_class = MessageGeneratorForm

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['request'] = self.request
        return kwargs

    def form_valid(self, form):
        generator = MessageGenerator(
            self.request,
            form.cleaned_data['offer'],
            form.cleaned_data['price'],
        )
        if form.cleaned_data['attach_message']:
            message = form.cleaned_data['attach_message']
            message = generator.attach_message(message)
        elif form.cleaned_data['newsletter']:
            message = generator.generate(form.cleaned_data['newsletter'])
        else:
            AttributeError('Either attach_message or newsletter is required.')
        return redirect('admin:newsletter_message_change', object_id=message.id)

    def form_invalid(self, form):
        return FormView.form_invalid(self, form)
