import logging

from django.urls import path

logger = logging.getLogger(__name__)

from django.db import models

from django.conf import settings

from django.contrib import admin, messages
from django.contrib.sites.models import Site

from django.core import serializers
from django.core.exceptions import PermissionDenied

from django.http import HttpResponse, HttpResponseRedirect, Http404

from django.shortcuts import render

from django.utils.html import format_html
from django.utils.translation import gettext as _, ngettext
from django.utils.formats import date_format

from django.views.decorators.clickjacking import xframe_options_sameorigin
try:
    from django.views.i18n import JavaScriptCatalog
    HAS_CBV_JSCAT = True
except ImportError:  # Django < 1.10
    from django.views.i18n import javascript_catalog
    HAS_CBV_JSCAT = False

# Conditional imports as only one Thumbnail app is required
try:
    from sorl.thumbnail.admin import AdminImageMixin
except ImportError:
    pass

try:
    from easy_thumbnails.widgets import ImageClearableFileInput
except (ImportError, RuntimeError):
    pass

from .models import (
    Newsletter, Subscription, Attachment, Article, Message, Submission,
    get_additional_context,
)

from django.utils.timezone import now
from django.urls import reverse

from .admin_forms import (
    SubmissionAdminForm, SubscriptionAdminForm, ImportForm, ConfirmForm,
    ArticleFormSet
)
from .admin_utils import ExtendibleModelAdminMixin, make_subscription
from .fields import DynamicImageField
from .settings import newsletter_settings

# Construct URL's for icons
ICON_URLS = {
    'yes': '%snewsletter/admin/img/icon-yes.gif' % settings.STATIC_URL,
    'wait': '%snewsletter/admin/img/waiting.gif' % settings.STATIC_URL,
    'submit': '%snewsletter/admin/img/submitting.gif' % settings.STATIC_URL,
    'no': '%snewsletter/admin/img/icon-no.gif' % settings.STATIC_URL
}


class NewsletterAdmin(admin.ModelAdmin):
    list_display = (
        'title', 'admin_subscriptions', 'admin_messages', 'admin_submissions'
    )
    fields = ('title', 'slug', 'email', 'sender', 'visible',
              'footer_template_html', 'footer_template_text')
    prepopulated_fields = {'slug': ('title',)}

    """ List extensions """
    def _admin_url(self, obj, model, text):
        url = reverse('admin:%s_%s_changelist' %
                      (model._meta.app_label, model._meta.model_name),
                      current_app=self.admin_site.name)

        return format_html(
            '<a href="{}?newsletter__id={}">{}</a>', url, obj.id, text
        )

    def admin_messages(self, obj):
        return self._admin_url(obj, Message, _("Messages"))
    admin_messages.short_description = ''

    def admin_subscriptions(self, obj):
        return self._admin_url(obj, Subscription, _("Subscriptions"))
    admin_subscriptions.short_description = ''

    def admin_submissions(self, obj):
        return self._admin_url(obj, Submission, _("Submissions"))
    admin_submissions.short_description = ''


class NewsletterAdminLinkMixin:
    def admin_newsletter(self, obj):
        opts = Newsletter._meta
        newsletter = obj.newsletter
        url = reverse('admin:%s_%s_change' % (opts.app_label, opts.model_name),
                      args=(newsletter.id,), current_app=self.admin_site.name)

        return format_html('<a href="{}">{}</a>', url, newsletter)
    admin_newsletter.short_description = _('newsletter')


class SubmissionAdmin(NewsletterAdminLinkMixin, ExtendibleModelAdminMixin,
                      admin.ModelAdmin):
    form = SubmissionAdminForm
    list_display = (
        'admin_message', 'admin_newsletter', 'admin_publish_date', #'publish',
        'admin_status_text', 'admin_status'
    )
    date_hierarchy = 'publish_date'
    list_filter = ('newsletter', 'publish', 'sent')
    save_as = True
    filter_horizontal = ('subscriptions',)

    """ List extensions """
    def admin_message(self, obj):
        return format_html('<a href="{}/">{}</a>', obj.id, obj.message.title)
    admin_message.short_description = _('submission')

    def admin_publish_date(self, obj):
        if obj.publish_date:
            return date_format(obj.publish_date, 'DATETIME_FORMAT')
        else:
            return ''
    admin_publish_date.short_description = _("publish date")

    def admin_status(self, obj):
        if obj.prepared:
            if obj.sent:
                return format_html(
                    '<img src="{}" width="10" height="10" alt="{}"/>',
                    ICON_URLS['yes'], self.admin_status_text(obj)
                )
            else:
                if obj.publish_date > now():
                    return format_html(
                        '<img src="{}" width="10" height="10" alt="{}"/>',
                        ICON_URLS['wait'], self.admin_status_text(obj)
                    )
                else:
                    return format_html(
                        '<img src="{}" width="12" height="12" alt="{}"/>',
                        ICON_URLS['wait'], self.admin_status_text(obj)
                    )
        else:
            return format_html(
                '<img src="{}" width="10" height="10" alt="{}"/>',
                ICON_URLS['no'], self.admin_status_text(obj)
            )
    admin_status.short_description = ''

    def admin_status_text(self, obj):
        if obj.prepared:
            if obj.sent:
                return _("Sent.")
            else:
                if obj.publish_date > now():
                    return _("Delayed submission.")
                else:
                    return _("Submitting.")
        else:
            return _("Not sent.")
    admin_status_text.short_description = _('Status')

    """ Views """
    def submit(self, request, object_id):
        submission = self._getobj(request, object_id)

        if submission.sent or submission.prepared:
            messages.info(request, _("Submission already sent."))
            change_url = reverse(
                'admin:newsletter_submission_change', args=[object_id]
            )
            return HttpResponseRedirect(change_url)

        submission.prepared = True
        submission.save()

        messages.info(request, _("Your submission is being sent."))

        changelist_url = reverse('admin:newsletter_submission_changelist')
        return HttpResponseRedirect(changelist_url)

    """ URLs """
    def get_urls(self):
        urls = super().get_urls()

        my_urls = [
            path(
                '<object_id>/submit/',
                self._wrap(self.submit),
                name=self._view_name('submit')
            )
        ]

        return my_urls + urls


class AttachmentInline(admin.TabularInline):
    model = Attachment
    extra = 1

    def has_change_permission(self, request, obj=None):
        """ Prevent change of the file (instead needs to be deleted) """
        return False


StackedInline = admin.StackedInline
if (
        newsletter_settings.RICHTEXT_WIDGET
        and newsletter_settings.RICHTEXT_WIDGET.__name__ == "ImperaviWidget"
):
    # Imperavi works a little differently
    # It's not just a field, it's also a media class and a method.
    # To avoid complications, we reuse ImperaviStackedInlineAdmin
    try:
        from imperavi.admin import ImperaviStackedInlineAdmin
        StackedInline = ImperaviStackedInlineAdmin
    except ImportError:
        # Log a warning when import fails as to aid debugging.
        logger.warning(
            'Error importing ImperaviStackedInlineAdmin. '
            'Imperavi WYSIWYG text editor might not work.'
        )

# Creates a base class for the ArticleInline to inherit depending on
# if the user has decided to use sorl-thumbnail or not
# https://sorl-thumbnail.readthedocs.io/en/latest/examples.html#admin-examples
if newsletter_settings.THUMBNAIL == 'sorl-thumbnail':
    ArticleInlineClassTuple = (AdminImageMixin, StackedInline)
else:
    ArticleInlineClassTuple = (StackedInline,)

BaseArticleInline = type('BaseArticleInline', ArticleInlineClassTuple, {})

class ArticleInline(BaseArticleInline):
    model = Article
    extra = 0
    formset = ArticleFormSet
    fields = ('image', 'url', 'sortorder')
    '''
    fieldsets = (
        (_('Optional'), {
            'fields': ('sortorder', 'title', 'text'),
            'classes': ('collapse', 'mb-5')
        }),
        (None, {
            'fields': ('image', 'url')
        }),
    )
    '''


    # Perform any formfield overrides depending on specified settings
    formfield_overrides = {}

    if newsletter_settings.RICHTEXT_WIDGET:
        formfield_overrides[models.TextField] = {
            'widget': newsletter_settings.RICHTEXT_WIDGET
        }

    # https://easy-thumbnails.readthedocs.io/en/latest/usage/#forms
    if newsletter_settings.THUMBNAIL == 'easy-thumbnails':
        formfield_overrides[DynamicImageField] = {
            'widget': ImageClearableFileInput
        }


class HasSubmissionFilter(admin.SimpleListFilter):
    title = 'Ausgabe(n) erstellt'
    parameter_name = 'has_submissions'

    def lookups(self, request, model_admin):
        return (
            ('True', 'Yes'),
            ('False', 'No'),
        )

    def queryset(self, request, queryset):
        if self.value() == 'True':
            return queryset.filter(submission__isnull=False)
        elif self.value() == 'False':
            return queryset.filter(submission__isnull=True)
        else:
            return queryset


class MessageAdmin(NewsletterAdminLinkMixin, ExtendibleModelAdminMixin,
                   admin.ModelAdmin):
    save_as = True
    list_display = (
        'admin_title', 'admin_newsletter', 'admin_preview', 'date_create',
        'date_modify'
    )
    list_filter = ('newsletter', HasSubmissionFilter)
    date_hierarchy = 'date_create'
    prepopulated_fields = {'slug': ('title',)}

    inlines = [ArticleInline, AttachmentInline, ]

    """ List extensions """
    def admin_title(self, obj):
        return format_html('<a href="{}/">{}</a>', obj.id, obj.title)
    admin_title.short_description = _('message')

    def admin_preview(self, obj):
        url = reverse('admin:' + self._view_name('preview'), args=(obj.id,),
                      current_app=self.admin_site.name)
        return format_html('<a href="{}">{}</a>', url, _("Preview"))
    admin_preview.short_description = ''

    """ Views """
    def preview(self, request, object_id):
        return render(
            request,
            "admin/newsletter/message/preview.html",
            {'message': self._getobj(request, object_id),
             'attachments': Attachment.objects.filter(message_id=object_id)},
        )

    @xframe_options_sameorigin
    def preview_html(self, request, object_id):
        message = self._getobj(request, object_id)

        if not message.html_template:
            raise Http404(_(
                'No HTML template associated with the newsletter this '
                'message belongs to.'
            ))

        c = {
            'message': message,
            'site': Site.objects.get_current(),
            'newsletter': message.newsletter,
            'date': now(),
            'STATIC_URL': settings.STATIC_URL,
            'MEDIA_URL': settings.MEDIA_URL
        }
        c = get_additional_context(c)

        return HttpResponse(message.html_template.render(c))

    @xframe_options_sameorigin
    def preview_text(self, request, object_id):
        message = self._getobj(request, object_id)

        c = {
            'message': message,
            'site': Site.objects.get_current(),
            'newsletter': message.newsletter,
            'date': now(),
            'STATIC_URL': settings.STATIC_URL,
            'MEDIA_URL': settings.MEDIA_URL
        }
        c = get_additional_context(c)

        return HttpResponse(
            message.text_template.render(c),
            content_type='text/plain'
        )

    def submit(self, request, object_id):
        submission = Submission.from_message(self._getobj(request, object_id))

        change_url = reverse(
            'admin:newsletter_submission_change', args=[submission.id])

        return HttpResponseRedirect(change_url)

    def subscribers_json(self, request, object_id):
        message = self._getobj(request, object_id)

        json = serializers.serialize(
            "json", message.newsletter.get_subscriptions(), fields=()
        )
        return HttpResponse(json, content_type='application/json')

    """ URLs """
    def get_urls(self):
        urls = super().get_urls()

        my_urls = [
            path('<object_id>/preview/',
                 self._wrap(self.preview),
                 name=self._view_name('preview')),
            path('<object_id>/preview/html/',
                 self._wrap(self.preview_html),
                 name=self._view_name('preview_html')),
            path('<object_id>/preview/text/',
                 self._wrap(self.preview_text),
                 name=self._view_name('preview_text')),
            path('<object_id>/submit/',
                 self._wrap(self.submit),
                 name=self._view_name('submit')),
            path('<object_id>/subscribers/json/',
                 self._wrap(self.subscribers_json),
                 name=self._view_name('subscribers_json')),
        ]

        return my_urls + urls


class SubscriptionAdmin(NewsletterAdminLinkMixin, ExtendibleModelAdminMixin,
                        admin.ModelAdmin):
    form = SubscriptionAdminForm
    list_display = (
        'name', 'email', 'admin_newsletter', 'admin_subscribe_date',
        'admin_unsubscribe_date', 'admin_status_text', 'admin_status'
    )
    list_display_links = ('name', 'email')
    list_filter = (
        'newsletter', 'subscribed', 'unsubscribed', 'subscribe_date'
    )
    search_fields = (
        'name_field', 'email_field', 'user__first_name', 'user__last_name',
        'user__email'
    )
    readonly_fields = (
        'ip', 'subscribe_date', 'unsubscribe_date', 'activation_code'
    )
    date_hierarchy = 'subscribe_date'
    actions = ['make_subscribed', 'make_unsubscribed']
    exclude = ['unsubscribed']

    """ List extensions """
    def admin_status(self, obj):
        img_tag = '<img src="{}" width="10" height="10" alt="{}"/>'
        alt_txt = self.admin_status_text(obj)
        if obj.unsubscribed:
            return format_html(img_tag, ICON_URLS['no'], alt_txt)

        if obj.subscribed:
            return format_html(img_tag, ICON_URLS['yes'], alt_txt)
        else:
            return format_html(img_tag, ICON_URLS['wait'], alt_txt)
    admin_status.short_description = ''

    def admin_status_text(self, obj):
        if obj.subscribed:
            return _("Subscribed")
        elif obj.unsubscribed:
            return _("Unsubscribed")
        else:
            return _("Unactivated")
    admin_status_text.short_description = _('Status')

    def admin_subscribe_date(self, obj):
        if obj.subscribe_date:
            return date_format(obj.subscribe_date)
        else:
            return ''
    admin_subscribe_date.short_description = _("subscribe date")

    def admin_unsubscribe_date(self, obj):
        if obj.unsubscribe_date:
            return date_format(obj.unsubscribe_date)
        else:
            return ''
    admin_unsubscribe_date.short_description = _("unsubscribe date")

    """ Actions """
    def make_subscribed(self, request, queryset):
        rows_updated = queryset.update(subscribed=True)
        self.message_user(
            request,
            ngettext(
                "%d user has been successfully subscribed.",
                "%d users have been successfully subscribed.",
                rows_updated
            ) % rows_updated
        )
    make_subscribed.short_description = _("Subscribe selected users")

    def make_unsubscribed(self, request, queryset):
        rows_updated = queryset.update(subscribed=False)
        self.message_user(
            request,
            ngettext(
                "%d user has been successfully unsubscribed.",
                "%d users have been successfully unsubscribed.",
                rows_updated
            ) % rows_updated
        )
    make_unsubscribed.short_description = _("Unsubscribe selected users")

    """ Views """
    def subscribers_import(self, request):
        if not request.user.has_perm('newsletter.add_subscription'):
            raise PermissionDenied()
        if request.POST:
            form = ImportForm(request.POST, request.FILES)
            if form.is_valid():
                request.session['addresses'] = form.get_addresses()
                request.session['newsletter_pk'] = \
                    form.cleaned_data['newsletter'].pk

                confirm_url = reverse(
                    'admin:newsletter_subscription_import_confirm'
                )
                return HttpResponseRedirect(confirm_url)
        else:
            form = ImportForm()

        return render(
            request,
            "admin/newsletter/subscription/importform.html",
            {'form': form},
        )

    def subscribers_import_confirm(self, request):
        # If no addresses are in the session, start all over.

        if 'addresses' not in request.session:
            import_url = reverse('admin:newsletter_subscription_import')
            return HttpResponseRedirect(import_url)

        addresses = request.session['addresses']
        newsletter = Newsletter.objects.get(
            pk=request.session['newsletter_pk']
        )

        logger.debug('Confirming addresses: %s', addresses)

        if request.POST:
            form = ConfirmForm(request.POST)
            if form.is_valid():
                try:
                    for email, name in addresses.items():
                        address_inst = make_subscription(
                            newsletter, email, name
                        )
                        address_inst.save()
                finally:
                    del request.session['addresses']
                    del request.session['newsletter_pk']

                messages.success(
                    request,
                    ngettext(
                        "%d subscription has been successfully added.",
                        "%d subscriptions have been successfully added.",
                        len(addresses)
                    ) % len(addresses)
                )

                changelist_url = reverse(
                    'admin:newsletter_subscription_changelist'
                )
                return HttpResponseRedirect(changelist_url)
        else:
            form = ConfirmForm()

        return render(
            request,
            "admin/newsletter/subscription/confirmimportform.html",
            {'form': form, 'subscribers': addresses},
        )

    """ URLs """
    def get_urls(self):
        urls = super().get_urls()

        my_urls = [
            path('import/',
                 self._wrap(self.subscribers_import),
                 name=self._view_name('import')),
            path('import/confirm/',
                 self._wrap(self.subscribers_import_confirm),
                 name=self._view_name('import_confirm')),
        ]
        # Translated JS strings - these should be app-wide but are
        # only used in this part of the admin. For now, leave them here.
        if HAS_CBV_JSCAT:
            my_urls.append(path('jsi18n/',
                           JavaScriptCatalog.as_view(packages=('newsletter',)),
                           name='newsletter_js18n'))
        else:
            my_urls.append(path('jsi18n/',
                                javascript_catalog,
                                {'packages': ('newsletter',)},
                                name='newsletter_js18n'))

        return my_urls + urls


admin.site.register(Newsletter, NewsletterAdmin)
admin.site.register(Submission, SubmissionAdmin)
admin.site.register(Message, MessageAdmin)
admin.site.register(Subscription, SubscriptionAdmin)
