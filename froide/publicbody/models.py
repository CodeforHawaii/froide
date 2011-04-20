# -*- coding: utf-8 -*-
import json

from django.db import models
from django.utils.translation import ugettext as _
from django.contrib.auth.models import User, AnonymousUser
from django.contrib.sites.models import Site
from django.contrib.sites.managers import CurrentSiteManager
from django.core.urlresolvers import reverse
from django.conf import settings
from django.utils.text import truncate_words



class PublicBodyManager(CurrentSiteManager):
    def get_for_homepage(self, count=5):
        return self.get_query_set()[:count]

    def get_for_search_index(self):
        return self.get_query_set()


class FoiLaw(models.Model):
    name = models.CharField(max_length=255)
    slug = models.SlugField(_("Slug"), max_length=255)
    description = models.TextField(blank=True)
    letter_start = models.TextField(blank=True)
    letter_end = models.TextField(blank=True)
    jurisdiction = models.CharField(max_length=255)
    max_response_time = models.IntegerField(null=True, blank=True, default=30) # in days
    refusal_reasons = models.TextField(_(u"Possible Refusal Reasons, one per line, e.g §X.Y: Privacy Concerns"))
    site = models.ForeignKey(Site, verbose_name=_("Site"),
            null=True, on_delete=models.SET_NULL,
            default=settings.SITE_ID)

    class Meta:
        verbose_name = _("Freedom of Information Law")
        verbose_name_plural = _("Freedom of Information Laws")

    def __unicode__(self):
        return u"%s (%s)" % (self.name, self.jurisdiction)

    def get_refusal_reason_choices(self):
        return tuple([(x, truncate_words(x, 12)) for x in self.refusal_reasons.splitlines()])


class PublicBody(models.Model):
    name = models.CharField(_("Name"), max_length=255)
    slug = models.SlugField(_("Slug"), max_length=255)
    description = models.TextField(_("Description"), blank=True)
    topic = models.CharField(_("Topic"), max_length=255, blank=True)
    url = models.URLField(_("URL"), null=True, blank=True, verify_exists=False)
    parent = models.ForeignKey('PublicBody', null=True, blank=True, default=None,
            on_delete=models.SET_NULL, related_name="children")
    root = models.ForeignKey('PublicBody', null=True, blank=True, default=None, 
            on_delete=models.SET_NULL, related_name="descendants")
    depth = models.SmallIntegerField(default=0)
    classification = models.CharField(_("Classification"), max_length=255,
            blank=True)
    
    email = models.EmailField(_("Email"), null=True, blank=True)
    contact = models.TextField(_("Contact"), blank=True)
    address = models.TextField(_("Address"), blank=True)
    website_dump = models.TextField(_("Website Dump"), null=True, blank=True)
    
    _created_by = models.ForeignKey(User, verbose_name=_("Created by"),
            blank=True, null=True, related_name='public_body_creators',
            on_delete=models.SET_NULL)
    _updated_by = models.ForeignKey(User, verbose_name=_("Updated by"),
            blank=True, null=True, related_name='public_body_updaters',
            on_delete=models.SET_NULL)
    confirmed = models.BooleanField(_("confirmed"), default=True)
    
    number_of_requests = models.IntegerField(_("Number of requests"),
            default=0)
    site = models.ForeignKey(Site, verbose_name=_("Site"),
            null=True, on_delete=models.SET_NULL, default=settings.SITE_ID)
    
    geography = models.CharField(_("Geography"), max_length=255)

    laws = models.ManyToManyField(FoiLaw,
            verbose_name=_("Freedom of Information Laws"))
    
    objects = PublicBodyManager()
    
    class Meta:
        verbose_name = _("Public Body")
        verbose_name_plural = _("Public Bodies")

    serializable_fields = ('name', 'slug',
            'description', 'topic', 'url', 'email', 'contact',
            'address', 'geography', 'domain')
        
    def __unicode__(self):
        return u"%s (%s)" % (self.name, self.geography)

    @property
    def created_by(self):
        return self._created_by or AnonymousUser()

    @property
    def updated_by(self):
        return self._updated_by or AnonymousUser()

    @property
    def domain(self):
        if self.url:
            return self.url.split("/")[2]
        return None

    @property
    def default_law(self):
        return self.laws.all()[0]

    def get_absolute_url(self):
        return reverse('publicbody-show', kwargs={"slug": self.slug})

    def as_json(self):
        d = {}
        for field in self.serializable_fields:
            d[field] = getattr(self, field)
        d['laws'] = [{"pk": l.pk, "name": l.name, "letter_start": l.letter_start,
                "letter_end": l.letter_end} for l in self.laws.all()]
        return json.dumps(d)

    @property
    def children_count(self):
        return len(PublicBody.objects.filter(parent=self))

    @classmethod
    def export_csv(cls):
        import csv
        from StringIO import StringIO
        s = StringIO()
        fields =  ("name", "classification", "depth", "children_count", "email", "parent", "description",
                "url", "website_dump", "contact", "address")
        writer = csv.DictWriter(s, fields)
        for pb in PublicBody.objects.all():
            d = {}
            for field in fields:
                value = getattr(pb, field)
                if value is None:
                    d[field] = value
                elif isinstance(value, unicode):
                    d[field] = value.encode("utf-8")
                else:
                    d[field] = unicode(value).encode("utf-8")
            writer.writerow(d)
        s.seek(0)
        return s.read()
