from __future__ import unicode_literals
from django.contrib import admin
from django.core.urlresolvers import reverse
from myhpom.models.state import State
from myhpom.models.state_requirement import StateRequirement
from myhpom.models.state_requirement_link import StateRequirementLink
from myhpom.models.document import AdvanceDirective, DocumentUrl
from myhpom.models.cloudfactory import CloudFactoryDocumentRun
from myhpom.tasks import (
    CloudFactoryAbortDocumentRun,
    CloudFactoryUpdateDocumentRun,
)

from django.utils.safestring import mark_safe


class StateRequirementLinkAdmin(admin.TabularInline):
    model = StateRequirementLink


class StateRequirementAdmin(admin.ModelAdmin):
    model = StateRequirement
    inlines = [StateRequirementLinkAdmin]


class StateRequirementInlineAdmin(admin.TabularInline):
    model = StateRequirement
    fields = ('text', 'admin_link')
    readonly_fields = ('admin_link',)


class StateAdmin(admin.ModelAdmin):
    model = State
    inlines = [StateRequirementInlineAdmin]


class DocumentUrlInlineAdmin(admin.StackedInline):
    model = DocumentUrl
    fields = ('url_as_link', 'expiration', 'cloud_factory_runs')
    readonly_fields = ('url_as_link', 'cloud_factory_runs')
    extra = 0

    def url_as_link(self, obj):
        return mark_safe(
            '<a href="%s" target="_blank" rel="noopener noreferrer">%s</a>' % (obj.url, obj.url)
        )

    def cloud_factory_runs(self, obj):
        return mark_safe(
            '<ul>'
            + ''.join(
                # Is there a better way to get a URL in the mmh-admin? I don't find a resolver.
                '<li><a href="%s">%s</a></li>'
                % (reverse("admin:myhpom_cloudfactorydocumentrun_change", args=[cf_run.id]), cf_run)
                for cf_run in obj.cloudfactorydocumentrun_set.all()
            )
            + '</ul>'
        )


class AdvanceDirectiveAdmin(admin.ModelAdmin):
    model = AdvanceDirective
    inlines = [DocumentUrlInlineAdmin]


class CloudFactoryDocumentRunAdmin(admin.ModelAdmin):
    model = CloudFactoryDocumentRun
    fields = (
        ('document_url', 'inserted_at', 'document_host'),
        ('status', 'run_id'),
        ('created_at', 'processed_at'),
        'post_data',
        'response_content',
    )
    readonly_fields = [
        'document_url',
        'inserted_at',
        'document_host',
        'status',
        'run_id',
        'created_at',
        'processed_at',
        'post_data',
        'response_content',
    ]
    list_display = [
        'document_url',
        'document_host',
        'run_id',
        'status',
        'created_at',
        'processed_at',
    ]
    actions = ['abort_runs', 'update_runs']

    def delete_selected(self, request, queryset):
        self.abort_runs(request, queryset)
        super(CloudFactoryDocumentRunAdmin, self).delete_selected(request, queryset)

    def abort_runs(self, request, queryset):
        for cf_run in queryset:
            CloudFactoryAbortDocumentRun(cf_run.id)

    abort_runs.short_description = "Abort the selected document runs at CloudFactory."

    def update_runs(self, request, queryset):
        for cf_run in queryset:
            CloudFactoryUpdateDocumentRun(cf_run.id)

    update_runs.short_description = "Update the selected document runs by querying CloudFactory."


admin.site.register(State, StateAdmin)
admin.site.register(StateRequirement, StateRequirementAdmin)
admin.site.register(AdvanceDirective, AdvanceDirectiveAdmin)
admin.site.register(CloudFactoryDocumentRun, CloudFactoryDocumentRunAdmin)
