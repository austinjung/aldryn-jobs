import reversion
import six
from datetime import datetime, timedelta

from django.db import transaction
from django.contrib.auth.models import User
from parler.utils.context import switch_language

from aldryn_reversion.core import create_revision_with_placeholders

from ..models import (JobCategory, JobOffer, JobApplication, NewsletterSignup,
NewsletterSignupUser, JobApplicationAttachment)

from .base import JobsBaseTestCase, tz_datetime


class ReversionTestCase(JobsBaseTestCase):
    """
    Cover reversion support, test cases:
     * revisions are created (reversions and self test)
     * revisions are reverted (reversions and self test)
     * not translated fields are changed when new revision is created
     * not translated fields are being reverted correctly
     * translated fields are changed on save with revision (latest change should be shown)
     * translated fields are reverted correctly
     * placeholder fields are reverted with correct plugins (according to revision)
     * [TBD] placeholder fields for translated objects should serve correct plugins for translation
     * [TBD] placeholder fields for translated objects should server correct plugins for translation
       after revision revert.
    """

    def create_revision(self, obj, content=None, **kwargs):
        with transaction.atomic():
            with reversion.create_revision():
                # populate event with new values
                for property, value in six.iteritems(kwargs):
                    setattr(obj, property, value)
                if content:
                    # get correct plugin for language. do not update the same one.
                    language = obj.get_current_language()
                    plugins = obj.content.get_plugins().filter(language=language)
                    plugin = plugins[0].get_plugin_instance()[0]
                    plugin.body = content
                    plugin.save()
                obj.save()

    def revert_to(self, object_with_revision, revision_number):
        """
        Revert <object with revision> to revision number.
        """
        # get by position, since reversion_id is not reliable,
        version = list(reversed(
            reversion.get_for_object(object_with_revision)))[revision_number - 1]
        version.revision.revert()

    # Following tests does not covers translations!
    def test_revision_is_created_on_job_category_object_create(self):
        with transaction.atomic():
            with reversion.create_revision():
                job_category = JobCategory.objects.create(
                    app_config=self.app_config,
                    **self.category_values_raw['en'])
        self.assertEqual(len(reversion.get_for_object(job_category)), 1)

    def test_revision_is_created_on_job_offer_object_created(self):
        with transaction.atomic():
            with reversion.create_revision():
                job_offer = JobOffer.objects.create(
                    app_config=self.app_config,
                    category=self.default_category,
                    **self.offer_values_raw['en'])
        self.assertEqual(len(reversion.get_for_object(job_offer)), 1)

    def test_category_revision_is_created(self):
        category = JobCategory.objects.create(
            app_config=self.app_config,
            **self.category_values_raw['en'])
        self.assertEqual(len(reversion.get_for_object(category)), 0)
        new_values_en_1 = self.make_new_values(self.category_values_raw['en'], 1)
        self.create_revision(category, **new_values_en_1)
        self.assertEqual(len(reversion.get_for_object(category)), 1)

    def test_job_offer_revision_is_created(self):
        job_offer = self.create_default_job_offer()
        self.assertEqual(len(reversion.get_for_object(job_offer)), 0)

        new_values_en_1 = self.make_new_values(self.default_job_values['en'], 1)
        self.create_revision(job_offer, **new_values_en_1)
        self.assertEqual(len(reversion.get_for_object(job_offer)), 1)

    def test_category_with_one_revision_contains_latest_values(self):
        category = JobCategory.objects.create(
            app_config=self.app_config,
            **self.category_values_raw['en'])
        new_values_en_1 = self.make_new_values(self.category_values_raw['en'], 1)
        # revision 1
        self.create_revision(category, **new_values_en_1)
        for prop in new_values_en_1.keys():
            self.assertEqual(getattr(category, prop), new_values_en_1[prop])

        # the same but with re-getting category object
        category = JobCategory.objects.get(pk=category.pk)
        for prop in new_values_en_1.keys():
            self.assertEqual(getattr(category, prop), new_values_en_1[prop])

    def test_offer_with_one_revision_contains_latest_values(self):
        job_offer = self.create_default_job_offer()
        # revision 1
        new_values_en_1 = self.make_new_values(self.offer_values_raw['en'], 1)
        content_en_1 = self.plugin_values_raw['en'].format(1)
        self.create_revision(job_offer, content=content_en_1, **new_values_en_1)

        job_offer = JobOffer.objects.get(pk=job_offer.pk)
        for prop in new_values_en_1.keys():
            self.assertEqual(getattr(job_offer, prop), new_values_en_1[prop])

    def test_offer_with_one_revision_serves_latest_content(self):
        job_offer = self.create_default_job_offer()
        # revision 1
        new_values_en_1 = self.make_new_values(self.offer_values_raw['en'], 1)
        content_en_1 = self.plugin_values_raw['en'].format(1)
        self.create_revision(job_offer, content=content_en_1, **new_values_en_1)

        # test url and served content
        with switch_language(job_offer, 'en'):
            url_1 = job_offer.get_absolute_url()
        response = self.client.get(url_1)
        self.assertContains(response, new_values_en_1['title'])
        self.assertContains(response, content_en_1)

    def test_category_with_two_revision_contains_latest_values(self):
        category = JobCategory.objects.create(
            app_config=self.app_config,
            **self.category_values_raw['en'])
        # revision 1
        new_values_en_1 = self.make_new_values(self.category_values_raw['en'], 1)
        self.create_revision(category, **new_values_en_1)

        # revision 2
        new_values_en_2 = self.make_new_values(self.category_values_raw['en'], 2)
        self.create_revision(category, **new_values_en_2)

        for prop in new_values_en_2.keys():
            self.assertEqual(getattr(category, prop), new_values_en_2[prop])

        # the same but with re-getting category object
        category = JobCategory.objects.get(pk=category.pk)
        for prop in new_values_en_2.keys():
            self.assertEqual(getattr(category, prop), new_values_en_2[prop])

    def test_offer_with_two_revision_contains_latest_values(self):
        job_offer = self.create_default_job_offer()

        # revision 1
        new_values_en_1 = self.make_new_values(self.offer_values_raw['en'], 1)
        content_en_1 = self.plugin_values_raw['en'].format(1)
        self.create_revision(job_offer, content=content_en_1, **new_values_en_1)

        # revision 2
        new_values_en_2 = self.make_new_values(self.offer_values_raw['en'], 2)
        content_en_2 = self.plugin_values_raw['en'].format(2)
        self.create_revision(job_offer, content=content_en_2, **new_values_en_2)

        job_offer = JobOffer.objects.get(pk=job_offer.pk)
        for prop in new_values_en_2.keys():
            self.assertEqual(getattr(job_offer, prop), new_values_en_2[prop])

    def test_offer_with_two_revision_serves_latest_content(self):
        job_offer = self.create_default_job_offer()

        # revision 1
        new_values_en_1 = self.make_new_values(self.offer_values_raw['en'], 1)
        content_en_1 = self.plugin_values_raw['en'].format(1)
        self.create_revision(job_offer, content=content_en_1, **new_values_en_1)

        # revision 2
        new_values_en_2 = self.make_new_values(self.offer_values_raw['en'], 2)
        content_en_2 = self.plugin_values_raw['en'].format(2)
        self.create_revision(job_offer, content=content_en_2, **new_values_en_2)

        # test served title
        job_offer = JobOffer.objects.get(pk=job_offer.pk)
        with switch_language(job_offer, 'en'):
            url = job_offer.get_absolute_url()
        response = self.client.get(url)
        self.assertContains(response, new_values_en_2['title'])
        self.assertContains(response, content_en_2)
        # legacy values/content
        self.assertNotContains(response, new_values_en_1['title'])
        self.assertNotContains(response, content_en_1)

    def test_category_revisions_are_reverted(self):
        # no revisions at this point
        category = JobCategory.objects.create(
            app_config=self.app_config,
            **self.category_values_raw['en'])

        # revision 1
        new_values_en_1 = self.make_new_values(self.category_values_raw['en'], 1)
        self.create_revision(category, **new_values_en_1)

        # revision 2
        new_values_en_2 = self.make_new_values(self.category_values_raw['en'], 2)
        self.create_revision(category, **new_values_en_2)

        # revert to 1
        self.revert_to(category, 1)

        category = JobCategory.objects.get(pk=category.pk)
        for prop in new_values_en_1.keys():
            self.assertEqual(getattr(category, prop), new_values_en_1[prop])

    def test_offer_revisions_are_reverted(self):
        job_offer = self.create_default_job_offer()

        # revision 1
        new_values_en_1 = self.make_new_values(self.offer_values_raw['en'], 1)
        content_en_1 = self.plugin_values_raw['en'].format(1)
        self.create_revision(job_offer, content=content_en_1, **new_values_en_1)

        # revision 2
        new_values_en_2 = self.make_new_values(self.offer_values_raw['en'], 2)
        content_en_2 = self.plugin_values_raw['en'].format(2)
        new_category = JobCategory.objects.create(
            app_config=self.app_config,
            **self.make_new_values(self.category_values_raw['en'], 2))
        new_values_en_2['category'] = new_category
        self.create_revision(job_offer, content=content_en_2, **new_values_en_2)

        # revert to 1
        self.revert_to(job_offer, 1)
        job_offer = JobOffer.objects.get(pk=job_offer.pk)
        new_values_en_1['category'] = self.default_category
        for prop in new_values_en_1.keys():
            self.assertEqual(getattr(job_offer, prop), new_values_en_1[prop])
        self.assertNotEqual(job_offer.category, new_category)

    def test_offer_reverted_revision_serves_appropriate_content(self):
        job_offer = self.create_default_job_offer()

        # revision 1
        new_values_en_1 = self.make_new_values(self.offer_values_raw['en'], 1)
        content_en_1 = self.plugin_values_raw['en'].format(1)
        self.create_revision(job_offer, content=content_en_1, **new_values_en_1)

        # revision 2
        new_values_en_2 = self.make_new_values(self.offer_values_raw['en'], 2)
        content_en_2 = self.plugin_values_raw['en'].format(2)
        self.create_revision(job_offer, content=content_en_2, **new_values_en_2)

        # revert to 1
        job_offer = JobOffer.objects.get(pk=job_offer.pk)
        self.revert_to(job_offer, 1)
        job_offer = JobOffer.objects.get(pk=job_offer.pk)
        with switch_language(job_offer, 'en'):
            url = job_offer.get_absolute_url()
        response = self.client.get(url)
        self.assertContains(response, new_values_en_1['title'])
        self.assertContains(response, content_en_1)
        self.assertNotContains(response, new_values_en_2['title'])
        self.assertNotContains(response, content_en_2)

    def test_edit_plugin_directly(self):
        job_offer = self.create_default_job_offer()

        # revision 1
        content_en_1 = self.plugin_values_raw['en'].format(1)
        self.create_revision(job_offer, content=content_en_1)

        self.assertEqual(len(reversion.get_for_object(job_offer)), 1)

        # revision 2
        content_en_2 = self.plugin_values_raw['en'].format(2)
        with transaction.atomic():
            with reversion.create_revision():
                language = job_offer.get_current_language()
                plugins = job_offer.content.get_plugins().filter(language=language)
                plugin = plugins[0].get_plugin_instance()[0]
                plugin.body = content_en_2
                plugin.save()
                create_revision_with_placeholders(job_offer)
        self.assertEqual(len(reversion.get_for_object(job_offer)), 2)

        with switch_language(job_offer, 'en'):
            url = job_offer.get_absolute_url()
        response = self.client.get(url)

        self.assertContains(response, content_en_2)
        self.assertNotContains(response, content_en_1)

        self.revert_to(job_offer, 1)
        job_offer = JobOffer.objects.get(pk=job_offer.pk)
        response = self.client.get(job_offer.get_absolute_url())
        self.assertContains(response, content_en_1)
        self.assertNotContains(response, content_en_2)

    def test_category_revert_revision_contains_correct_values_for_diverged_translations(self):
        category = self.default_category
        self.assertEqual(len(reversion.get_for_object(category)), 0)
        # revision 1: en 1, de 0
        new_values = self.make_new_values(self.category_values_raw['en'], 1)
        with switch_language(category, 'en'):
            self.create_revision(category, **new_values)

        # revision 2: en 1, de 1
        new_values_2 = self.make_new_values(self.category_values_raw['de'], 1)
        with switch_language(category, 'de'):
            self.create_revision(category, **new_values_2)

        # revision 3: en 1, de 2
        new_values_3 = self.make_new_values(self.category_values_raw['de'], 2)
        with switch_language(category, 'de'):
            self.create_revision(category, **new_values_3)

        # revision 4: en 2, de 2
        with switch_language(category, 'en'):
            new_values_4 = self.make_new_values(self.category_values_raw['en'], 2)
            self.create_revision(category, **new_values_4)

        # revert to 3: en 1, de 2
        self.revert_to(category, 3)
        category = JobCategory.objects.get(pk=category.pk)
        # test en values
        # switch_language(category,
        with switch_language(category, 'en'):
            for prop in new_values.keys():
                self.assertEqual(getattr(category, prop), new_values[prop])
        # test de values
        with switch_language(category, 'de'):
            for prop in new_values_3.keys():
                self.assertEqual(getattr(category, prop), new_values_3[prop])

    def test_offer_revert_revision_contains_correct_values_for_diverged_translations(self):
        offer = self.create_default_job_offer(translated=True)
        self.assertEqual(len(reversion.get_for_object(offer)), 0)
        initial_values = {
            'category': self.default_category,
            'is_active': True,
            'can_apply': True,
        }
        # revision 1: en 1, de 0
        new_values_en_1 = self.make_new_values(self.offer_values_raw['en'], 1)
        with switch_language(offer, 'en'):
            self.create_revision(offer, **new_values_en_1)

        # revision 2: en 1, de 1
        new_values_de_1 = self.make_new_values(self.offer_values_raw['de'], 1)
        with switch_language(offer, 'de'):
            self.create_revision(offer, **new_values_de_1)

        # revision 3: en 1, de 2
        new_values_de_2 = self.make_new_values(self.offer_values_raw['de'], 2)
        with switch_language(offer, 'de'):
            self.create_revision(offer, **new_values_de_2)

        # revision 4: en 2, de 2, also contains updated category and bool fields
        new_values_en_2 = self.make_new_values(self.offer_values_raw['en'], 2)
        new_category = JobCategory.objects.create(
            app_config=self.app_config,
            **self.make_new_values(self.category_values_raw['en'], 2))
        new_values_en_2['category'] = new_category
        new_values_en_2['is_active'] = False
        new_values_en_2['can_apply'] = False
        with switch_language(offer, 'en'):
            self.create_revision(offer, **new_values_en_2)

        # revert to 3: en 1, de 2
        self.revert_to(offer, 3)
        offer = JobOffer.objects.get(pk=offer.pk)
        # test en values
        with switch_language(offer, 'en'):
            for prop in new_values_en_1.keys():
                self.assertEqual(getattr(offer, prop), new_values_en_1[prop])
            # test untranslated fields, should be the same as atm of reverted revision
            for prop in initial_values.keys():
                self.assertEqual(getattr(offer, prop), initial_values[prop])

        # test de values
        with switch_language(offer, 'de'):
            for prop in new_values_de_2.keys():
                self.assertEqual(getattr(offer, prop), new_values_de_2[prop])
            # test untranslated fields shouldn't be changed regardless of language
            for prop in initial_values.keys():
                self.assertEqual(getattr(offer, prop), initial_values[prop])

    def test_offer_revert_revision_serves_correct_values_for_diverged_translations(self):
        offer = self.create_default_job_offer(translated=True)
        self.assertEqual(len(reversion.get_for_object(offer)), 0)

        # revision 1: en 1, de 0
        new_values_en_1 = self.make_new_values(self.offer_values_raw['en'], 1)
        content_en_1 = self.plugin_values_raw['en'].format(1)
        with switch_language(offer, 'en'):
            self.create_revision(offer, content=content_en_1, **new_values_en_1)

        # revision 2: en 1, de 1
        new_values_de_1 = self.make_new_values(self.offer_values_raw['de'], 1)
        content_de_1 = self.plugin_values_raw['de'].format(1)
        with switch_language(offer, 'de'):
            self.create_revision(offer, content=content_de_1, **new_values_de_1)

        # revision 3: en 1, de 2
        new_values_de_2 = self.make_new_values(self.offer_values_raw['de'], 2)
        content_de_2 = self.plugin_values_raw['de'].format(2)
        with switch_language(offer, 'de'):
            self.create_revision(offer, content=content_de_2,  **new_values_de_2)

        # revision 4: en 2, de 2
        content_en_2 = self.plugin_values_raw['en'].format(2)
        new_values_en_2 = self.make_new_values(self.offer_values_raw['en'], 2)
        with switch_language(offer, 'en'):
            self.create_revision(offer, content=content_en_2, **new_values_en_2)

        # revert to 3: en 1, de 2
        self.revert_to(offer, 3)
        offer = JobOffer.objects.get(pk=offer.pk)
        # test en values
        with switch_language(offer, 'en'):
            url_reverted_en = offer.get_absolute_url()
        response = self.client.get(url_reverted_en)
        self.assertContains(response, new_values_en_1['title'])
        self.assertContains(response, content_en_1)
        # ensure that there is no latest values (rev 4)
        self.assertNotContains(response, new_values_en_2['title'])
        self.assertNotContains(response, content_en_2)
        # test de values
        with switch_language(offer, 'de'):
            url_reverted_de = offer.get_absolute_url()
        response = self.client.get(url_reverted_de)
        self.assertContains(response, new_values_de_2['title'])
        self.assertContains(response, content_de_2)
        # ensure that there is no previous values (rev 2)
        self.assertNotContains(response, new_values_de_1['title'])
        self.assertNotContains(response, content_de_1)

    def test_offer_is_reverted_if_fk_object_was_deleted(self):
        offer = self.create_default_job_offer(translated=True)
        self.assertEqual(len(reversion.get_for_object(offer)), 0)

        # revision 1: en 1, de 0
        category_1 = self.default_category
        new_values_en_1 = self.make_new_values(self.offer_values_raw['en'], 1)
        with switch_language(offer, 'en'):
            self.create_revision(offer, **new_values_en_1)

        # revision 2: en 1, de 1
        new_values_de_1 = self.make_new_values(self.offer_values_raw['de'], 1)
        # update category
        category_2 = JobCategory.objects.create(
            app_config=self.app_config,
            **self.make_new_values(self.category_values_raw['en'], 2))
        new_values_de_1['category'] = category_2
        with switch_language(offer, 'de'):
            self.create_revision(offer, **new_values_de_1)

        # delete category_1
        with transaction.atomic():
            category_1.delete()
        self.assertEqual(JobCategory.objects.all().count(), 1)

        # revert to 1
        self.revert_to(offer, 1)
        offer = JobOffer.objects.get(pk=offer.pk)
        self.assertNotEqual(offer.category, category_2)
        self.assertEqual(JobCategory.objects.all().count(), 2)

    # JobApplication
    def test_job_application_revision_is_created(self):
        job_offer = self.create_default_job_offer()
        application = JobApplication.objects.create(
            app_config=self.app_config,
            job_offer=job_offer,
            **self.application_default_values)
        self.assertEqual(len(reversion.get_for_object(application)), 0)

        # revision 1
        new_values_1 = self.make_new_values(self.application_values_raw, 1)
        self.create_revision(application, **new_values_1)
        self.assertEqual(len(reversion.get_for_object(application)), 1)

    def test_job_application_contains_latest_values(self):
        job_offer = self.create_default_job_offer()
        application = JobApplication.objects.create(
            app_config=self.app_config,
            job_offer=job_offer,
            **self.application_default_values)

        # revision 1
        new_values_1 = self.make_new_values(self.application_values_raw, 1)
        self.create_revision(application, **new_values_1)
        self.assertEqual(len(reversion.get_for_object(application)), 1)

        application = JobApplication.objects.get(pk=application.pk)
        for prop in new_values_1.keys():
            self.assertEqual(getattr(application, prop), new_values_1[prop])

        # revision 2
        new_values_2 = self.make_new_values(self.application_values_raw, 2)
        new_offer = JobOffer.objects.create(
            app_config=self.app_config,
            category=self.default_category,
            **self.make_new_values(self.offer_values_raw['en'], 2))
        new_values_2['job_offer'] = new_offer
        self.create_revision(application, **new_values_2)
        self.assertEqual(len(reversion.get_for_object(application)), 2)

        application = JobApplication.objects.get(pk=application.pk)
        for prop in new_values_2.keys():
            self.assertEqual(getattr(application, prop), new_values_2[prop])

    def test_job_application_revision_is_reverted(self):
        job_offer = self.create_default_job_offer()
        application = JobApplication.objects.create(
            job_offer=job_offer, **self.application_default_values)

        # revision 1
        new_values_1 = self.make_new_values(self.application_values_raw, 1)
        self.create_revision(application, **new_values_1)
        self.assertEqual(len(reversion.get_for_object(application)), 1)

        # revision 2
        new_values_2 = self.make_new_values(self.application_values_raw, 2)
        new_offer = JobOffer.objects.create(
            app_config=self.app_config,
            category=self.default_category,
            **self.make_new_values(self.offer_values_raw['en'], 2))
        new_values_2['job_offer'] = new_offer
        self.create_revision(application, **new_values_2)
        self.assertEqual(len(reversion.get_for_object(application)), 2)

        # revert to 1
        self.revert_to(application, 1)
        application = JobApplication.objects.get(pk=application.pk)
        # add initial job_offer to values list to be checked
        new_values_1['job_offer'] = job_offer
        for prop in new_values_1.keys():
            self.assertEqual(getattr(application, prop), new_values_1[prop])

    def test_job_application_revision_is_reverted_if_fk_obj_was_deleted(self):
        job_offer = self.create_default_job_offer()
        application = JobApplication.objects.create(
            job_offer=job_offer, **self.application_default_values)

        # revision 1
        new_values_1 = self.make_new_values(self.application_values_raw, 1)
        self.create_revision(application, **new_values_1)
        self.assertEqual(len(reversion.get_for_object(application)), 1)

        # revision 2
        new_values_2 = self.make_new_values(self.application_values_raw, 2)
        new_offer = JobOffer.objects.create(
            app_config=self.app_config,
            category=self.default_category,
            **self.make_new_values(self.offer_values_raw['en'], 2))
        new_values_2['job_offer'] = new_offer
        self.create_revision(application, **new_values_2)
        self.assertEqual(len(reversion.get_for_object(application)), 2)

        # delete initial offer
        with transaction.atomic():
            job_offer.delete()

        # revert to 1
        self.revert_to(application, 1)
        application = JobApplication.objects.get(pk=application.pk)
        self.assertEqual(JobOffer.objects.all().count(), 2)
        # get restored job offer
        job_offer = JobOffer.objects.all().exclude(pk=new_offer.pk).get()
        # add initial job_offer to values list to be checked
        new_values_1['job_offer'] = job_offer
        for prop in new_values_1.keys():
            self.assertEqual(getattr(application, prop), new_values_1[prop])

    # NewsletterSignup
    def test_signup_revision_is_created(self):
        signup = NewsletterSignup.objects.create(**self.signup_default_values)
        self.assertEqual(len(reversion.get_for_object(signup)), 0)

        # revision 1
        new_values_1 = self.make_new_values(self.signup_values_raw, 1)
        self.create_revision(signup, **new_values_1)
        self.assertEqual(len(reversion.get_for_object(signup)), 1)

    def test_signup_revision_contains_latest_values(self):
        signup = NewsletterSignup.objects.create(**self.signup_default_values)

        # revision 1
        new_values_1 = self.make_new_values(self.signup_values_raw, 1)
        self.create_revision(signup, **new_values_1)

        # revision 2
        new_values_2 = {
            'is_verified': True,
            'is_disabled': True,
        }
        self.create_revision(signup, **new_values_2)
        signup = NewsletterSignup.objects.get(pk=signup.pk)
        for prop in new_values_2.keys():
            self.assertEqual(getattr(signup, prop), new_values_2[prop])
        # check that not changed values are the same
        for prop in new_values_1.keys():
            self.assertEqual(getattr(signup, prop), new_values_1[prop])

        # revision 3
        new_values_3 = self.make_new_values(self.signup_values_raw, 3)
        new_values_3.update({
            'is_verified': False,
            'is_disabled': False,
        })
        self.create_revision(signup, **new_values_3)
        signup = NewsletterSignup.objects.get(pk=signup.pk)
        for prop in new_values_3.keys():
            self.assertEqual(getattr(signup, prop), new_values_3[prop])

    def test_signup_revision_is_reverted(self):
        signup = NewsletterSignup.objects.create(**self.signup_default_values)

        # revision 1
        new_values_1 = self.make_new_values(self.signup_values_raw, 1)
        self.create_revision(signup, **new_values_1)

        # revision 2
        new_values_2 = {
            'is_verified': True,
            'is_disabled': True,
        }
        self.create_revision(signup, **new_values_2)

        # revision 3
        new_values_3 = self.make_new_values(self.signup_values_raw, 3)
        new_values_3.update({
            'is_verified': False,
            'is_disabled': False,
        })
        self.create_revision(signup, **new_values_3)

        # revert to 2
        self.revert_to(signup, 2)
        signup = NewsletterSignup.objects.get(pk=signup.pk)
        # since that revision is a mix-up prepare values at that revision
        new_values_1.update(new_values_2)
        for prop in new_values_1.keys():
            self.assertEqual(getattr(signup, prop), new_values_1[prop])

    # NewsletterSignupUser
    def test_signup_user_revision_is_created(self):
        signup = NewsletterSignup.objects.create(**self.signup_default_values)
        user = User.objects.create(
            username='test_user', first_name='First_name',
            last_name='Last_name')

        signup_user = NewsletterSignupUser.objects.create(signup=signup, user=user)
        self.assertEqual(len(reversion.get_for_object(signup_user)), 0)
        signup_2 = NewsletterSignup.objects.create(
            **self.make_new_values(self.signup_values_raw, 1))

        # revision 1
        self.create_revision(signup_user, signup=signup_2)
        self.assertEqual(len(reversion.get_for_object(signup_user)), 1)

    def test_signup_user_revision_is_reverted(self):
        signup = NewsletterSignup.objects.create(**self.signup_default_values)
        user = User.objects.create(
            username='test_user', first_name='First_name',
            last_name='Last_name')

        signup_user = NewsletterSignupUser.objects.create(signup=signup, user=user)
        signup_1 = NewsletterSignup.objects.create(
            **self.make_new_values(self.signup_values_raw, 1))

        # revision 1
        self.create_revision(signup_user, signup=signup_1)

        # revision 2
        signup_2 = NewsletterSignup.objects.create(
            **self.make_new_values(self.signup_values_raw, 3))
        self.create_revision(signup_user, signup=signup_2)

        # revert to 1
        self.revert_to(signup_user, 1)
        signup_user = NewsletterSignupUser.objects.get(pk=signup_user.pk)
        self.assertEqual(signup_user.signup, signup_1)

    def test_signup_user_revision_reverted_if_fk_was_deleted(self):
        signup = NewsletterSignup.objects.create(**self.signup_default_values)
        user = User.objects.create(
            username='test_user', first_name='First_name',
            last_name='Last_name')

        # revision 1
        signup_user = NewsletterSignupUser.objects.create(signup=signup, user=user)
        signup_1 = NewsletterSignup.objects.create(
            **self.make_new_values(self.signup_values_raw, 1))
        self.create_revision(signup_user, signup=signup_1)

        # revision 2
        signup_2 = NewsletterSignup.objects.create(
            **self.make_new_values(self.signup_values_raw, 3))
        self.create_revision(signup_user, signup=signup_2)
        # delete revision 1 signup
        signup_1.delete()
        self.assertEqual(NewsletterSignup.objects.count(), 2)

        # revert to 1
        self.revert_to(signup_user, 1)
        signup_user = NewsletterSignupUser.objects.get(pk=signup_user.pk)
        self.assertEqual(NewsletterSignup.objects.count(), 3)
        # get deleted signup
        signup_restored = NewsletterSignup.objects.all().exclude(
            pk__in=(signup.pk, signup_2.pk)).get()
        self.assertEqual(signup_user.signup, signup_restored)