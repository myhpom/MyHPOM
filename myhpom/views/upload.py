from django.conf import settings
from django.views.decorators.http import require_GET, require_POST, require_http_methods
from django.shortcuts import render, redirect
from django.http import HttpResponseForbidden, HttpResponseRedirect
from django.core.urlresolvers import reverse
from django.utils.timezone import now

from myhpom.decorators import require_ajax_login
from myhpom.forms.upload_requirements import SharingForm, UploadRequirementsForm
from myhpom.models import AdvanceDirective, StateRequirement, DocumentUrl, CloudFactoryDocumentRun
from myhpom.tasks import CloudFactorySubmitDocumentRun


@require_GET
@require_ajax_login
def upload_index(request):
    return render(request, 'myhpom/upload/index.html')


@require_GET
@require_ajax_login
def upload_current_ad(request):
    if not hasattr(request.user, 'advancedirective'):
        return HttpResponseForbidden()

    return render(request, 'myhpom/upload/current_ad.html', {
        'advancedirective': request.user.advancedirective,
        'yes_or_na': CloudFactoryDocumentRun.YES_OR_NA,
    })


@require_http_methods(['GET', 'POST'])
@require_ajax_login
def upload_requirements(request):
    """
    GET: show the upload/state_requirements form for the current user/state
    POST: store the advance directive date, redirect to the upload/submit view.
    """
    if hasattr(request.user, 'advancedirective'):
        return redirect(reverse("myhpom:upload_current_ad"))

    directive = AdvanceDirective(user=request.user, share_with_ehs=False)
    if request.method == "POST":
        form = UploadRequirementsForm(request.POST, request.FILES, instance=directive)
        if form.is_valid():
            form.save()

            # start the verification process for the AD:
            document_url = DocumentUrl.objects.create(advancedirective=form.instance)
            CloudFactorySubmitDocumentRun.delay(document_url.pk, request.get_host())

            if request.user.userdetails.state.advance_directive_template:
                return redirect(reverse("myhpom:upload_sharing"))
            return redirect(reverse("myhpom:upload_current_ad"))
    else:
        form = UploadRequirementsForm(instance=directive)

    MIN_YEAR = 1950
    context = {
        'user': request.user,
        'form': form,
        'requirements': StateRequirement.for_state(request.user.userdetails.state),
        'MAX_AD_SIZE': settings.MAX_AD_SIZE,
        'MIN_YEAR': MIN_YEAR,
        'MAX_YEAR': now().year
    }
    return render(request, "myhpom/upload/requirements.html", context=context)


@require_http_methods(['GET', 'POST'])
@require_ajax_login
def upload_sharing(request):
    if not hasattr(request.user, 'advancedirective'):
        return HttpResponseForbidden()

    if request.method == 'POST':
        form = SharingForm(request.POST, instance=request.user.advancedirective)
        if form.is_valid():
            form.save()
            return HttpResponseRedirect(reverse('myhpom:upload_current_ad'))

    form = SharingForm(instance=request.user.advancedirective)
    return render(request, 'myhpom/upload/sharing.html', {
        'form': form,
    })


@require_POST
@require_ajax_login
def upload_delete_ad(request):
    if hasattr(request.user, 'advancedirective'):
        request.user.advancedirective.delete()
        return HttpResponseRedirect(request.GET.get('redirect', (reverse('myhpom:upload_index'))))
    else:
        return HttpResponseRedirect(reverse('myhpom:upload_current_ad'))
