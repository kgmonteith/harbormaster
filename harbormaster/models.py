from __future__ import unicode_literals
from django.contrib.postgres.fields import ArrayField, JSONField
from django.db import models
from django.utils import timezone
import harbormaster.util as util
import ais
import logging

logger = logging.getLogger(__name__)
mmsi_countries = util.mmsi_codes()

class CollectionLabel(models.Model):
	name = models.CharField(max_length=64)
	start_date = models.DateTimeField(null=True)
	end_date = models.DateTimeField(null=True)

	def __str__(self):
		return self.name

class Contact(models.Model):
	mmsi = models.CharField(db_index=True, max_length=24)
	name = models.CharField(max_length=64, blank=True)
	first_sighting = models.DateTimeField(db_index=True, auto_now_add=True)
	last_sighting = models.DateTimeField(null=True)
	
	# Fields that are likely to remain static
	imo = models.IntegerField(null=True)
	ais_class = models.CharField(max_length=1, null=True)
	flag = models.CharField(max_length=12)
	nationality = models.CharField(max_length=255)
	ship_type = models.IntegerField(null=True)
	mmsi_type = models.CharField(max_length=255, null=True)
	callsign = models.CharField(max_length=12, null=True)
	dim_to_bow = models.IntegerField(null=True)
	dim_to_stern = models.IntegerField(null=True)
	dim_to_port = models.IntegerField(null=True)
	dim_to_starboard = models.IntegerField(null=True)

	# Fields that are likely to be queried frequently.
	# These will updated by the most recent type 5/24 sentences
	draught = models.FloatField(null=True)
	max_speed = models.FloatField(null=True)
	destination = models.CharField(max_length=255, null=True)

	# Highly mutable fields for prepopulating streaming data
	latest_lat = models.FloatField(null=True)
	latest_lng = models.FloatField(null=True)
	latest_speed = models.FloatField(null=True)
	latest_heading = models.FloatField(null=True)
	latest_navigation_status = models.IntegerField(null=True)

	def __str__(self):
		if len(self.name) > 0:
			return "%s (%s, %s, %s)" % (self.mmsi, self.name, util.readable_ship_type(self.ship_type), self.nationality)
		else:
			return self.mmsi

	def save(self, *args, **kw):
		(mid, self.mmsi_type) = util.get_mid_from_mmsi(self.mmsi)
		try:
			self.nationality = mmsi_countries[int(mid)]
		except KeyError:
			self.nationality = "Unknown"
		self.flag = util.itu_to_iso(self.nationality)
		super(Contact, self).save(*args, **kw)


# Raw reports are logged AIVDM messages. They may contain messages that failed to decode.
class RawReport(models.Model):
	collection_label = models.ForeignKey('CollectionLabel', db_index=True, on_delete=models.CASCADE, null=True)
	sentence = models.TextField()
	fill_bits = models.IntegerField()
	decode_error = models.BooleanField(default=False)
	time_received = models.DateTimeField(db_index=True, auto_now_add=True)

# Reports successfully decoded and have an associated contact
class Report(RawReport):
	contact = models.ForeignKey('Contact', db_index=True, on_delete=models.CASCADE)
	report_type = models.IntegerField(db_index=True)
	decoded = JSONField()

	def __str__(self):
		return "%s (type %i, %s, %s)" % (self.time_received, self.report_type, self.contact.mmsi, self.contact.name)

	def save(self, *args, **kw):
		super(Report, self).save(*args, **kw)
		if(self.contact.last_sighting is None or self.time_received > self.contact.last_sighting):
			self.update_contact()
		

	def update_contact(self):
		if (self.report_type == 5):
			self.contact.ais_class = 'A'
		elif (self.report_type == 24):
			self.contact.ais_class = 'B'

		if("imo_num" in self.decoded.keys()):
			self.contact.imo = self.decoded['imo_num']
		if("name" in self.decoded.keys()):
			self.contact.name = util.strip_text(self.decoded['name'])
		if("destination" in self.decoded.keys()):
			self.contact.destination = util.strip_text(self.decoded['destination'])
		if("sog" in self.decoded.keys()):
			speed = round(self.decoded['sog'], 1)
			if(speed > self.contact.max_speed):
				self.contact.max_speed = speed
		if("draught" in self.decoded.keys()):
			self.contact.draught = round(self.decoded['draught'], 1)
		if("type_and_cargo" in self.decoded.keys()):
			self.contact.ship_type = self.decoded['type_and_cargo']
		if("callsign" in self.decoded.keys()):
			self.contact.callsign = self.decoded['callsign']

		if("dim_a" in self.decoded.keys()):
			self.contact.dim_to_bow = self.decoded['dim_a']
		if("dim_b" in self.decoded.keys()):
			self.contact.dim_to_stern = self.decoded['dim_b']
		if("dim_c" in self.decoded.keys()):
			self.contact.dim_to_port = self.decoded['dim_c']
		if("dim_d" in self.decoded.keys()):
			self.contact.dim_to_starboard = self.decoded['dim_d']

		if("x" in self.decoded.keys()):
			self.contact.latest_lng = self.decoded['x']
		if("y" in self.decoded.keys()):
			self.contact.latest_lat = self.decoded['y']
		if("sog" in self.decoded.keys()):
			self.contact.latest_speed = round(self.decoded['sog'], 1)
		if("true_heading" in self.decoded.keys()):
			heading = self.decoded['true_heading']
			if(heading == 511 and self.decoded['cog'] > 0):
				heading = self.decoded['cog']
			self.contact.latest_heading = heading
		if("nav_status" in self.decoded.keys()):
			self.contact.latest_navigation_status = self.decoded['nav_status']
		
		self.contact.last_sighting = self.time_received
		self.contact.save()	